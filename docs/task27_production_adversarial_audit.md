# Task 27: Production Adversarial & Failure-Injection Audit

## Phase 0: Exact Production State
**1. Current git HEAD:** `68041f1b4f4ba45299335d8dcd3fc6aac1291ec9`
**2. Current Cloud Run revision:** `merchant-maxx-api-00028-sxw`
**3. Corresponds to current HEAD:** Yes.
**4. Production environment configuration:**
- `APP_ENV=development` (Note: running development env in Cloud Run)
- Contains `JWT_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.
**5. Active database migrations:** 001_purchase_intents.sql, 002_payment_hardening.sql, 003_recommendation_idempotency.sql, 004_inventory_fulfillment.sql
**6. Relevant production tables:** `orders`, `purchase_intents`, `inventory_decrement_events`, `entity_mapping`.

---

## Phase 1: Complete Payment Lifecycle Trace
**Lifecycle:** Scout -> `purchase_intents` -> USER_CONFIRMED -> Closer -> `create_razorpay_order` -> `orders` -> Razorpay -> `payment.captured` -> webhook -> `atomic_inventory_decrement` -> `purchase_intents` update to PAYMENT_SUCCESS.
**Findings:** The `purchase_intents` table is the authoritative source for the basket, mitigating client-side price manipulation. Webhooks correctly validate amount against `orders.total_paise`.

## Phase 2: Payment State-Machine Fuzzing
**Finding 1 (P0): TOCTOU in `chat.py` State Mutation**
- **Location:** `backend/routes/chat.py:96`
- **Issue:** The frontend chat route directly executes `supabase.table("purchase_intents").update({"purchase_state": "USER_CONFIRMED"}).eq(...)` without enforcing atomic state conditions (e.g., `.eq("purchase_state", "PURCHASE_PENDING")`). If a webhook transitions the intent to `PAYMENT_SUCCESS` concurrently, the user typing "confirm" will downgrade the state from `PAYMENT_SUCCESS` to `USER_CONFIRMED`, violating terminal state rules and potentially allowing infinite checkout re-entry for a paid order.

## Phase 3: Inventory Adversarial Testing
**Finding 2 (SECURE): Inventory Decrement Atomicity**
- **Location:** `backend/db/migrations/004_inventory_fulfillment.sql`
- **Issue:** The `atomic_inventory_decrement` RPC secures inventory perfectly. It uses `inventory_decrement_events` with `order_id` as the primary idempotency key. It uses deterministic sorting (`ORDER BY product_id`) for row locking, preventing deadlocks. Negative inventory is impossible due to `current_qty < item.quantity` checks.

## Phase 4: Payment + Inventory Race
**Finding 3 (SECURE): Multi-Customer Race**
- **Scenario:** Two customers reach checkout for the last unit. Both Razorpay orders are created.
- **Result:** Both can pay Razorpay (since reservation is at capture-time). The first webhook locks the row and decrements inventory. The second webhook locks the row, sees `current_qty < item.quantity`, and throws an exception. This routes the second payment to the `UNFULFILLED` status and triggers an automated refund.

## Phase 5: Webhook Adversarial Audit
**Finding 4 (P1): `orders` Table Downgrade Vulnerability**
- **Location:** `backend/routes/webhooks.py:198-202`
- **Issue:** While `purchase_intents` is protected from downgrade via `.neq("purchase_state", "PAYMENT_SUCCESS")` (line 195), the subsequent `orders` table update lacks this protection. An adversarial or delayed `payment.failed` webhook (with a novel `event_id`) will downgrade `orders.status` to `FAILED` and `fulfillment_status` to `PENDING`, even after the inventory was fulfilled and the intent reached `PAYMENT_SUCCESS`.

## Phase 6: Refund / Unfulfilled Path
**Finding 5 (P2): Lack of Refund Idempotency Persistence**
- **Location:** `backend/routes/webhooks.py:186`
- **Issue:** The webhook triggers `initiate_refund()` but does not persist the refund ID defensively before calling the external API. If the server crashes immediately after Razorpay accepts the refund, the system state (`UNFULFILLED`) might cause the refund to be re-attempted during reconciliation.

## Phase 7: Order Creation Failure Matrix
**Finding 6 (P2): Ghost Orders during Persistence**
- **Location:** `backend/agents/tools.py:217`
- **Issue:** If `create_razorpay_order` succeeds but the local Supabase `purchase_intents` update fails (e.g., timeout), the customer receives a Razorpay checkout URL, but the server loses the `razorpay_order_id` mapping. The webhook `_local_order` fallback will fail, ignoring the payment. Money is captured but lost to the merchant dashboard.

## Phase 8: Authorization / IDOR Complete Audit
**Finding 7 (P0): `audit.py` is Unauthenticated**
- **Location:** `backend/routes/audit.py`
- **Issue:** `GET /audit` and `GET /audit/{log_id}` require no authentication. Anyone can read the entire `audit_log` table containing agent logic, PII, and financial decision histories.
**Finding 8 (P1): `recommendations.py` is Unauthenticated**
- **Location:** `backend/routes/recommendations.py`
- **Issue:** All routes (shown, clicked, accepted, dismissed) lack authentication and ownership verification. Anyone can spoof recommendation metrics for any `rec_id`.
**Finding 9 (P2): `traces.py` lacks Merchant Authorization**
- **Location:** `backend/routes/traces.py`
- **Issue:** It enforces `get_current_user` but doesn't verify if the user is an admin or the correct merchant, allowing any authenticated user to view global LangSmith traces containing other users' chat histories.

## Phase 9: Frontend Trust-Boundary Audit
**Finding 10 (SECURE): Price/Amount Integrity**
- **Location:** `backend/agents/tools.py`
- **Issue:** The backend recalculates the basket total from `products.price_paise`, preventing the frontend from manipulating the price of an item.

## Phase 10: Agent / LLM Security
**Finding 11 (P0): LLM Can Bypass User Confirmation**
- **Location:** `backend/agents/tools.py:195`
- **Issue:** `create_razorpay_order` trusts the LLM implicitly. It does not verify `purchase_intents.user_confirmed == True` or `purchase_state == "USER_CONFIRMED"` from the database. It hardcodes `{"user_confirmed": True, "purchase_state": "USER_CONFIRMED"}` when passing the intent to `Guardian.validate_action()`. An adversarial LLM can bypass the confirmation step and generate a payment link instantly.
**Finding 12 (P1): LLM Can Supply Negative Quantities**
- **Location:** `backend/agents/tools.py:177`
- **Issue:** The LLM can pass a negative quantity for an item (e.g., `qty = -5`). Since Python doesn't check `qty > 0`, the line total becomes negative, reducing the total checkout amount. Although `atomic_inventory_decrement` will eventually fail and refund the order due to `qty <= 0` SQL checks, the Razorpay order is maliciously created for a lower amount.

## Phase 11: Database Integrity Audit
**Finding 13 (P0): Row Level Security Bypass (Allow All)**
- **Location:** `backend/db/schema.sql:198`
- **Issue:** All tables have RLS enabled but use a policy: `CREATE POLICY "Allow all on {table}" ON {table} FOR ALL USING (true)`. This renders RLS useless. Since `SUPABASE_ANON_KEY` is public (used by frontend apps), anyone can connect directly to the Supabase REST API and perform arbitrary CRUD operations on `products`, `orders`, `purchase_intents`, etc.

## Phase 12: Secret / Infrastructure Audit
**Finding 14 (SECURE): Secrets in Cloud Run**
- **Location:** Cloud Run Environment
- **Issue:** `JWT_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are properly injected via environment variables. The default insecure JWT fallback was removed in Task 25.

## Phase 13 & 14: Failure Injection & Concurrency
**Finding 15 (SECURE): Webhook Concurrency**
- **Issue:** Concurrent `payment.captured` webhooks are dropped by the `webhook_events.event_id` unique constraint. If the payload is spoofed with a new `event_id`, the `inventory_decrement_events.order_id` constraint prevents duplicate fulfillment, and the state downgrade protection prevents `PAYMENT_SUCCESS` from being reverted.

## Phase 15: Final Scorecard

### Invariant Verification
1. **One successful order → exactly one inventory decrement:** YES (Secured by RPC).
2. **Inventory can never become negative:** YES (Secured by RPC).
3. **Multi-item inventory decrement is atomic:** YES (Secured by RPC).
4. **Duplicate webhook → zero additional inventory decrement:** YES.
5. **PAYMENT_SUCCESS can never be downgraded:** NO (P0: `chat.py` TOCTOU allows downgrade; P1: `orders.status` lacks downgrade protection in webhooks).
6. **Payment success is independent from fulfillment success:** YES.
7. **One order cannot produce multiple successful payment records:** YES.
8. **A client cannot control authoritative price:** YES.
9. **A client cannot modify another user's resources:** NO (P0: DB RLS is "Allow all").
10. **An LLM cannot authorize payment:** NO (P0: LLM can bypass confirmation in `tools.py`).
11. **A stale agent result cannot overwrite newer payment state:** NO (P0: `chat.py` TOCTOU).
12. **A failed DB operation cannot silently report successful payment/order creation:** NO (P2: Ghost orders if intent update fails).
13. **A refund cannot be executed twice:** NO (P2: Lack of refund idempotency persistence).
14. **A payment cannot be lost because local mapping temporarily fails:** NO (P2: Missing order fallback drops payment).

### Final Verdict: NOT PRODUCTION READY
**P0 count:** 4
**P1 count:** 3
**P2 count:** 3
**P3 count:** 0

The application has resolved checkout races and JWT IDORs, but suffers from fatal flaws in RLS database integrity, LLM implicit trust (confirmation bypass), unauthenticated PII endpoints (`audit.py`), and webhook TOCTOU downgrades. No further features should be built until these P0/P1 items are remediated.
