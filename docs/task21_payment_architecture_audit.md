> **Project status — Under Development**
>
> Merchant Maxx is under active development. The core application source is maintained in `backend/` and `frontend/`, with supporting documentation in `docs/`.
>
> **Current state:**
> - The production application is deployed through the existing backend/frontend deployment setup.
> - The restored development history contains **108 commits** with original author/committer metadata and timestamps preserved through the security rewrite.
> - Previously exposed credentials were scrubbed from reachable Git history; real credentials must remain in environment/secret-manager configuration and must not be committed.
> - The latest local backend validation recorded **156 passing tests and 1 xpassed**. The GitHub Actions backend test check still needs to be resolved before calling CI fully green.
> - Development-only artifacts have been moved into `underConstruction/` so the repository root stays focused on the application and required project files.
>
> This status block is intentionally kept current as the project continues through development, testing, hardening, and deployment work.
>
> ---
>
# Task 21 — Payment Architecture Audit

This report contains a comprehensive production audit of the Merchant Maxx payment architecture, following the strict read-only audit constraints.

## 1. Scout Correctness & Mutability
**Status:** 🔴 **Vulnerable (P0 TOCTOU Race Condition)**
- **Intended Design:** `scout.py` checks if a `razorpay_order_id` exists on the `purchase_intent` or if a local `order` exists. If so, it treats the intent as locked and creates a new one.
- **Actual Implementation:** The lock check is a non-atomic `select()`. Concurrently, `scout` updates `purchase_intents` with `{"basket": new_basket, "amount_paise": new_amount}`. If `create_razorpay_order` (in `tools.py`) is running simultaneously, it reads the *old* basket, calculates the *old* amount, creates the Razorpay order, and then updates `purchase_intents.razorpay_order_id`. The final DB state is a mutated basket (e.g., Laptop + Mouse) associated with an old Razorpay order ID (Laptop only).

## 2. Booster Correctness
**Status:** 🟢 **Secure (Advisory Only)**
- Booster executes concurrently but only suggests products.
- `merger.py` enforces that Booster's recommendations do not override Scout's authoritative `basket_items`.

## 3. Merger Correctness
**Status:** 🟢 **Secure**
- `merger.py` correctly syncs state and drops Booster recommendations if they conflict with Scout's authoritative selection.
- Validates transitions via `can_transition()`.

## 4. Closer Correctness
**Status:** 🟡 **Partial Risk (Ghost Orders)**
- Closer strictly recalculates the subtotal server-side by checking the `products` table, rejecting mismatched amounts.
- However, if the local Supabase `orders.insert()` fails for reasons *other* than a unique constraint violation (e.g., DB downtime), the Razorpay order is still created but not mapped locally, resulting in a "ghost" order that leaks.

## 5. State Machine Invariants
**Status:** 🟢 **Secure**
- `payment_state.py` defines strict transitions.
- `webhooks.py` uses `is_terminal()` to prevent downgrades (e.g., `PAYMENT_SUCCESS` → `PAYMENT_FAILED` is blocked).
- `chat.py` securely limits direct `USER_CONFIRMED` updates to intents that are in `PURCHASE_PENDING` or `RECOMMENDATION_SHOWN`.

## 6. Supabase DB Constraints
**Status:** 🟢 **Secure**
- `002_payment_hardening.sql` added a partial unique index `uq_orders_purchase_intent` on `orders(purchase_intent_id)`.
- This correctly prevents duplicate local orders for a single intent, guaranteeing idempotency during `create_razorpay_order`.

## 7. Webhook Security
**Status:** 🟢 **Secure (But exploits TOCTOU in Scout)**
- Webhooks mandate signature verification and drop unverified payloads.
- **Amount Validation:** Validates `amount != int(order.get("total_paise") or 0)`. It correctly compares against the immutable `orders` table rather than the mutable `purchase_intents`.
- **Note on TOCTOU Impact:** Because the webhook validates against `orders` (which is locked at creation), the webhook succeeds for the old amount. However, the application uses `purchase_intents` (mutated by Scout) as the source of truth for fulfillment, allowing the user to get additional items for free.

## 8. Edge Case: Supabase Failure Post-Order Creation
**Status:** 🟡 **P2 Ghost Order Leak**
- If Supabase `orders` insertion fails (e.g., connection lost), the Razorpay order is orphaned. The transaction gracefully fails for the user, but leaves unused orders in Razorpay.

## 9. Edge Case: Duplicate Webhooks
**Status:** 🟢 **Secure**
- Idempotency is enforced using the `webhook_events` table and the `event_id` primary key. Duplicates are logged and safely ignored.

## 10. Edge Case: Conflicting Parallel Cart Updates
**Status:** 🔴 **P0 Vulnerability**
- As detailed in Section 1, the lack of atomic locking (e.g., optimistic concurrency control or row-level `FOR UPDATE` locks) on `purchase_intents` allows parallel cart updates to bypass the locking mechanism during the `create_razorpay_order` window.

## 11. Frontend Payment Integrity
**Status:** 🟢 **Secure**
- `AgentChat.jsx` parses the `order_id` from the AI's response using regex.
- Crucially, it does **not** pass an `amount` parameter to the `Razorpay(options)` initialization. This prevents the client from tampering with the amount; Razorpay strictly uses the server-side generated order's amount.

---

## 12. CURRENT VERDICT
**FAILED — P0 TOCTOU Vulnerability Discovered.**
While the architecture is largely solid and the unique indices prevent duplicate orders, a critical Time-Of-Check to Time-Of-Use (TOCTOU) race condition exists between `scout.py` (cart mutations) and `tools.py` (`create_razorpay_order`). Scout performs a non-atomic `select()` to check if an intent is locked before updating the basket in `purchase_intents`. If a concurrent checkout happens, the intent's basket is overwritten *after* the Razorpay order is priced but *before* the Razorpay order ID is written to the DB. This allows a user to pay for a cheaper basket but have a larger basket marked as `PAYMENT_SUCCESS`.

## 13. NEXT TASK
**TASK 22 — Atomic Payment State Locking**
Implement optimistic concurrency control or atomic conditional updates in `scout.py` to prevent modifying `purchase_intents` when `razorpay_order_id` is concurrently set. Ensure that `create_razorpay_order` is fully isolated from parallel basket mutations.
