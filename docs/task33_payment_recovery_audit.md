# TASK 33: Payment & Order Failure-Recovery / Financial Integrity Audit

## Executive Summary
A comprehensive, adversarial, read-only audit of the Merchant Maxx repository and its production architecture was conducted against commit `b0604c4` and Cloud Run revision `merchant-maxx-api-00034-gzf`.

While previous tasks successfully hardened IDOR, Payment Authorization (LLM boundary), and DB schemas (RLS), this audit uncovered **Three Critical (P0) Financial Integrity Vulnerabilities** within the failure-recovery and reconciliation mechanisms.

**Final Verdict: 🔴 NOT PRODUCTION READY.** The system can lose track of paid orders, skip inventory fulfillment during reconciliation, and silently drop refunds.

---

## 1. Razorpay Order Creation Failure Matrix (Phase 2)
**VULNERABILITY (P0): Permanently Orphaned Payments**
- **Scenario:** The Razorpay order is successfully created, but the local Supabase mapping (`orders`, `order_items`, `entity_mapping`) fails or times out.
- **Code Reference:** `agents/tools.py` -> `create_razorpay_order` (Line 266-273).
- **Flaw:** The error handler intentionally rolls back the intent: `update({"purchase_state": "USER_CONFIRMED", "razorpay_order_id": None})`. 
- **Impact:** The system completely forgets the `razorpay_order_id`. When the customer pays the Razorpay link, the webhook arrives, fails to find the local order, and fails to fallback to the intent (since it was cleared). The money is collected by Razorpay, but the local system drops the event completely (`{"status": "ignored", "reason": "unmapped order"}`). The customer loses their money, and the merchant has no automated way to reconcile it.

## 2. Payment State Reconciliation (Phase 5)
**VULNERABILITY (P0): Reconciliation Bypasses Fulfillment**
- **Scenario:** A webhook is dropped or delayed. The customer or agent triggers `check_payment_status` to reconcile the payment state manually with Razorpay.
- **Code Reference:** `agents/tools.py` -> `check_payment_status` (Line 325-332).
- **Flaw:** The reconciliation logic discovers a `captured` payment on Razorpay and updates `purchase_intents` to `PAYMENT_SUCCESS`. However, it **never** calls `atomic_inventory_decrement`, nor does it update the `orders` table to `CAPTURED`, nor does it handle fulfillment logic. 
- **Impact:** The customer's payment is marked as successful, but the merchant never ships the item, and inventory is never decremented.

## 3. Refund Failure & Idempotency Audit (Phase 6)
**VULNERABILITY (P0): Mocked Refunds & No Idempotency**
- **Scenario:** An order is paid but inventory is unavailable (`UNFULFILLED`). The webhook triggers an automatic refund.
- **Code Reference:** `services/refund_service.py` (Line 15-17).
- **Flaw:** The entire `refund_service.py` is a mock. It simply returns `True` and logs an error. It does not call Razorpay. 
- **Impact:** Refunds are silently dropped. The customer never receives their money back. Furthermore, there is no `refunds` table, meaning if it *did* call Razorpay, it would have no local idempotency, allowing concurrent or retry loops to issue multiple refunds for the same payment.

## 4. Webhook Failure Matrix & Idempotency (Phase 3)
🟢 **SECURE**
- **Signature Verification:** Enforced correctly before payload parsing.
- **Event Idempotency:** Duplicate `event_id`s are caught by the `webhook_events` primary key.
- **State Transition Idempotency:** If Razorpay sends two different webhook events for the same captured payment, the database atomic query `.neq("purchase_state", "PAYMENT_SUCCESS")` successfully prevents state downgrades and duplicate processing.

## 5. Inventory / Fulfillment Consistency (Phase 7)
🟢 **SECURE (via Webhooks)**
- The `atomic_inventory_decrement` RPC correctly utilizes a `UNIQUE(order_id)` constraint on the `inventory_decrement_events` table.
- A duplicate call to the RPC gracefully catches `unique_violation` and returns `already_processed`, strictly guaranteeing that one order cannot decrement inventory twice.

## 6. Concurrency Audit (Phase 9)
🟢 **SECURE**
- **Order Creation Race:** `purchase_intents` uses an atomic `update().eq("purchase_state", "USER_CONFIRMED")` which effectively locks the row and prevents two concurrent requests from creating duplicate Razorpay orders.
- **Webhook Race:** TOCTOU is prevented at the database level by requiring `.neq("status", "CAPTURED")` and `.neq("purchase_state", "PAYMENT_SUCCESS")`.

## 7. Financial Invariants (Phase 10)
| Invariant | Status | Proof / Location |
| :--- | :--- | :--- |
| 1. One Razorpay payment cannot create multiple successful local payments. | **PASS** | `entity_mapping` uniqueness and `update().neq("PAYMENT_SUCCESS")` |
| 2. One order cannot be fulfilled twice. | **PASS** | `UNIQUE(order_id)` on `inventory_decrement_events` |
| 3. One order cannot decrement inventory twice. | **PASS** | Handled natively by RPC `atomic_inventory_decrement` |
| 4. A failed payment cannot decrement inventory. | **PASS** | Webhook routes to `CAPTURED` block only |
| 5. A captured payment cannot become an unpaid state. | **PASS** | `payment_state.py` + DB `.neq("PAYMENT_SUCCESS")` guard |
| 6. A duplicate webhook cannot cause another financial side effect. | **PASS** | `webhook_events` PK constraint + DB state guards |
| 7. A payment cannot become permanently orphaned. | **FAIL (P0)** | `create_razorpay_order` exception handler clears `razorpay_order_id` |
| 8. A refund cannot be silently reported as successful when it failed. | **FAIL (P0)** | `refund_service.py` is mocked and returns `True` always |
| 9. The same payment cannot be refunded twice. | **FAIL (P0)** | No `refunds` table or local idempotency exists |
| 10. Unfulfilled payment eventually enters recoverable refund state. | **FAIL (P0)** | Webhook triggers mock refund, failing silently |
| 11. Inventory and payment outcomes remain consistent globally. | **FAIL (P0)** | `check_payment_status` skips inventory fulfillment |

## 8. Recovery Runbook (Phase 14)
- **Customer paid but webhook never arrived:** The operator can call `check_payment_status`. However, due to P0 #2, the operator must MANUALLY decrement inventory and fulfill the order because the system skips it.
- **Customer paid but local order mapping is missing (P0 #1):** **UNRECOVERABLE AUTOMATICALLY.** The operator must log into the Razorpay Dashboard, find the payment, extract the `notes.purchase_intent_id`, manually insert the order into the Supabase database, and trigger fulfillment.
- **Customer paid but inventory is unavailable:** The system automatically initiates a refund, but due to P0 #3, the refund is mocked. The operator must manually refund the user from the Razorpay Dashboard.

## 9. Final Scorecard (Phase 15)
### Security: 🟢 SECURE
Authentication, Authorization, IDOR defenses, and Webhook verification are rock solid. LLMs cannot authorize payments.

### Reliability & Concurrency: 🟢 SECURE
Database-level atomicity, RLS, conditional updates, and unique constraints successfully prevent race conditions and duplicate webhook side-effects.

### Financial Integrity & Recovery: 🔴 CRITICAL (P0)
The application logic completely fails to handle network partitions gracefully during order creation, silently skips fulfillment during reconciliation, and mocks refunds.

### Next Steps
Task 33 is complete. The system requires immediate remediation (Task 34) to fix the orphaned order rollback, implement true reconciliation fulfillment, and build a robust, idempotent refund persistence layer before any real transactions can occur.
