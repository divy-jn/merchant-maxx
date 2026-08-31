# Task 26A: Atomic Inventory & Fulfillment Audit

## Executive Summary
**FINAL VERDICT: VULNERABLE (P0 - Infinite Inventory / Overselling)**

A complete, read-only audit of the Merchant Maxx repository and deployed environment has revealed that **inventory is never decremented at any point in the lifecycle**. While the application correctly *validates* inventory levels before creating a purchase intent or a Razorpay order, it fails to *reserve* or *decrement* that inventory upon order creation or payment success.

This guarantees overselling and allows infinite purchases of any product with `inventory_qty > 0`.

### Current Environment Status
- **Git HEAD**: `68041f1b4f4ba45299335d8dcd3fc6aac1291ec9`
- **Cloud Run Revision**: `merchant-maxx-api-00027-6cb`
- **Match Status**: Verified — The currently serving revision matches the latest git HEAD.

---

## Lifecycle Analysis

### 1. Where inventory is currently validated
Inventory is validated in three places via simple `SELECT` queries:
- **`backend/agents/scout.py`**: Validates `inventory_qty >= quantity` when staging or modifying a purchase intent.
- **`backend/agents/tools.py`**: 
  - Validates `inventory_qty > 0` before recommending products.
  - Re-validates `inventory_qty >= qty` inside `create_razorpay_order` before generating the Razorpay payload.
- **`backend/routes/chat.py`**: Validates `inventory_qty >= 1` when accepting a contextual recommendation.

### 2. Where inventory is currently reserved
**Nowhere.** Generating a purchase intent and creating a Razorpay order do not reserve inventory in the database.

### 3. Where inventory is decremented
**Nowhere.** There are no SQL `UPDATE` statements, RPCs, or triggers targeting `products.inventory_qty` in the codebase.

### 4. Decrement timing (Before vs After payment)
N/A (Since it never occurs). However, because Razorpay does not guarantee payment success at checkout creation, the industry-standard approach is either to temporarily reserve inventory upon checkout creation and release it on timeout, OR to decrement it atomically inside the webhook upon `payment.captured` (while accepting the risk of checkout-time races).

### 5. Concurrent purchases of the last unit
**VULNERABLE.** Since inventory is never decremented, if two customers attempt to buy a product with `inventory_qty = 1` concurrently:
1. Both call `create_razorpay_order`.
2. Both evaluate the Python `SELECT`: `inventory_qty (1) >= qty (1)` -> True.
3. Both get active Razorpay orders.
4. Both pay successfully.
5. Both receive `PAYMENT_SUCCESS`. 
The merchant now owes 2 units but only has 1.

### 6. Duplicate webhooks and double decrementing
**NOT VERIFIED (N/A).** Since no decrement occurs, double decrementing doesn't happen yet. The webhook does have an idempotency layer (`webhook_events` table), but when inventory decrements are implemented, they must be tightly coupled to this idempotency lock.

### 7. Failed/refunded payments restore inventory
**NOT VERIFIED (N/A).** Failed webhooks transition the state to `PAYMENT_FAILED` but do not alter inventory.

### 8. Multi-product baskets
**VULNERABLE.** Baskets contain multiple items, but because no inventory mutation exists, partial fulfillment or multi-row atomic decrements are currently unhandled.

### 9. Quantity > 1 atomicity
**VULNERABLE.** Because there is no atomic `UPDATE ... WHERE inventory >= X`, all logic relies on vulnerable Python-level `SELECT` checks (Time-Of-Check to Time-Of-Use race conditions).

### 10. Inventory changes racing with cart modification
**VULNERABLE.** Even though `create_razorpay_order` re-validates inventory, a merchant could theoretically update inventory to 0 *after* the order is created but *before* the customer enters their card details.

### 11. State inconsistency
**VULNERABLE.** Payment state and inventory state are entirely disconnected. `PAYMENT_SUCCESS` implies fulfillment, but `inventory_qty` remains completely static.

### 12. Supabase RPC / Transactional Logic required?
**YES.** Supabase (PostgreSQL) RPCs are absolutely required. Python cannot safely update multiple rows atomically (for multi-product baskets) without a transaction. If Python performs a `SELECT` followed by an `UPDATE` for each item, it introduces TOCTOU races and partial failure risks (e.g., product A succeeds, product B fails, leaving the database in an inconsistent state).

---

## Proposed Remediation (Task 26B Implementation Plan)

### Core Invariant
> *Inventory must only be decremented exactly once per successful order, and it must never fall below zero. Multi-item baskets must succeed or fail as a single atomic unit.*

### Recommended Approach
1. **Database RPC (Atomic Decrement):**
   Create a PostgreSQL function (RPC) via a migration that takes a JSON payload of `[{"product_id": "...", "qty": N}]`. 
   The function will:
   - Start a transaction.
   - Lock the affected product rows (`SELECT ... FOR UPDATE`).
   - Check if `inventory_qty >= qty` for all products.
   - If ANY product lacks inventory, `ROLLBACK` and raise an exception.
   - If ALL products have sufficient inventory, `UPDATE` their quantities.
   - `COMMIT`.
   
2. **Webhook Integration:**
   Modify `webhooks.py`. When a `payment.captured` or `order.paid` event is received, execute the RPC exactly once *during* the state transition to `PAYMENT_SUCCESS`.

3. **Strict Webhook Idempotency:**
   Ensure the RPC is conditionally tied to the `webhook_events` idempotency check, so a duplicate webhook cannot trigger the RPC twice.

4. **Failure State / Refunds:**
   (Optional/P2) Create an RPC to *restore* inventory if a payment fails *after* decrement (if reservations are implemented), or if a refund is processed.

> [!IMPORTANT]
> Because Razorpay orders are created *before* payment capture, customers might pay for an item that sells out while they are entering their card details. If the RPC fails during the webhook due to insufficient inventory, we must transition the state to `PAYMENT_SUCCESS_BUT_UNFULFILLED` (or automatically trigger a refund). Please advise if you prefer **Checkout-time Reservation** (decrementing at order creation and restoring via cron if unpaid) or **Capture-time Decrement** (decrementing at webhook success and alerting the merchant if out of stock).
