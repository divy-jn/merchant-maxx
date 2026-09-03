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
# Task 13 — Razorpay Payment Lifecycle Hardening

> **Completed:** 2026-08-30
> **Status:** All code changes complete. Deployment blocked on webhook secret provisioning.

---

## 1. Audit Findings

### Critical Risks Fixed

| Risk | Issue | Fix |
|------|-------|-----|
| R1 | **Duplicate Razorpay orders** — TOCTOU race in Python check, no DB unique constraint | Added `UNIQUE INDEX` on `orders.purchase_intent_id` + idempotency check on `purchase_intents.razorpay_order_id` before API call |
| R2 | **Webhook signature bypass** — `RAZORPAY_WEBHOOK_SECRET` not in Settings class, `getattr()` always returned `None` | Added field to `Settings` class + made verification mandatory (fail closed) |
| R3 | **No frontend checkout** — Order created but user couldn't pay | Added Razorpay Checkout.js integration with Pay Now button, double-click prevention |

### High Risks Fixed

| Risk | Fix |
|------|-----|
| R4: Race condition | DB-level unique constraint catches concurrent inserts |
| R5: Provider error leak | Sanitized all error returns in tools.py |
| R6: Webhook detail leak | Generic "Validation failed" instead of specific field names |
| R7: State downgrade | `payment_state.py` terminal state protection — `PAYMENT_SUCCESS → PAYMENT_FAILED` is blocked |
| R8: Product detail leak | Generic "Unable to fetch" instead of `{exc}` |

### Medium Risks Fixed

| Risk | Fix |
|------|-----|
| R9: Type name leak | Removed `exc.__class__.__name__` from error_handler.py |
| R12: Weak event ID fallback | Simplified to `f"{event}:{rzp_payment_id}"` (no timestamp dependency) |

---

## 2. Files Changed

| File | Change |
|------|--------|
| `backend/config.py` | Added `RAZORPAY_WEBHOOK_SECRET` field |
| `backend/agents/tools.py` | Idempotent order creation, sanitized errors, reconciliation |
| `backend/agents/payment_state.py` | **NEW** — State machine with transition validation |
| `backend/routes/webhooks.py` | Mandatory signature verification, state downgrade protection, `payment.authorized`/`order.paid` support |
| `backend/middleware/error_handler.py` | Removed type name from 500 responses |
| `backend/db/migrations/002_payment_hardening.sql` | **NEW** — Unique indexes, webhook columns |
| `backend/tests/test_payment_hardening.py` | **NEW** — 16 payment hardening tests |
| `backend/tests/conftest.py` | **NEW** — Test fixture for isolated imports |
| `frontend/index.html` | Added Checkout.js script, fixed title |
| `frontend/src/pages/AgentChat.jsx` | Razorpay Checkout modal with Pay Now button |
| `frontend/src/pages/AgentChat.css` | Pay Now button styles |
| `frontend/.env.example` | Added `VITE_RAZORPAY_KEY_ID` |
| `docs/task13_payment_audit.md` | **NEW** — Full audit document |

---

## 3. DB Migrations

### `002_payment_hardening.sql`

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_purchase_intent
    ON orders(purchase_intent_id) WHERE purchase_intent_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_intents_rzp_order
    ON purchase_intents(razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS razorpay_payment_id TEXT;
ALTER TABLE purchase_intents ADD COLUMN IF NOT EXISTS payment_updated_at TIMESTAMPTZ;
```

All operations are idempotent (IF NOT EXISTS). No drops. Safe to re-run.

---

## 4. State Machine

```
PRODUCT_SELECTED
    ├──→ RECOMMENDATION_SHOWN
    └──→ PURCHASE_PENDING
         ↓
USER_CONFIRMED
    ↓
PAYMENT_PENDING
    ├──→ PAYMENT_SUCCESS  (terminal — no outgoing transitions)
    └──→ PAYMENT_FAILED
              ↓
         RECOVERY_PENDING
              ↓
         PURCHASE_PENDING  (new intent cycle)
```

**Terminal states:** `PAYMENT_SUCCESS` — can never be downgraded.

---

## 5. Idempotency Design

### Order Creation

1. `create_razorpay_order` checks `purchase_intents.razorpay_order_id`
2. If already set → return existing order ID (no Razorpay API call)
3. If not set → create order, then save to DB
4. DB `UNIQUE INDEX` on `orders.purchase_intent_id` catches concurrent races
5. On unique constraint violation → query existing order and return it

### Webhook Processing

1. `webhook_events.event_id` is PRIMARY KEY (natural idempotency)
2. Insert attempt catches duplicate → returns `{"status": "duplicate"}`
3. State machine prevents downgrade even if duplicate slips through

---

## 6. Webhook Design

### Verification
- **Mandatory** — if `RAZORPAY_WEBHOOK_SECRET` is empty, returns 500 (fail closed)
- Uses `rzp.utility.verify_webhook_signature()` with raw body

### Events Handled
| Event | Action |
|-------|--------|
| `payment.authorized` | Log only (awaiting capture) |
| `payment.captured` | → `PAYMENT_SUCCESS` |
| `order.paid` | → `PAYMENT_SUCCESS` |
| `payment.failed` | → `PAYMENT_FAILED` |
| Other events | Ignored with `{"status": "ignored"}` |

### State Protection
- Reads current `purchase_state` before update
- If current is `PAYMENT_SUCCESS`, rejects any downgrade
- Uses `can_transition()` from `payment_state.py`

---

## 7. Security Validation

| Check | Result |
|-------|--------|
| `RAZORPAY_KEY_SECRET` only server-side | ✅ Not in frontend code |
| `RAZORPAY_WEBHOOK_SECRET` only server-side | ✅ Not in frontend code |
| No secrets in git | ✅ `.env` in `.gitignore` |
| No provider URLs in error responses | ✅ All sanitized |
| Invalid webhook → safe 4xx | ✅ Returns "Invalid signature" |
| Missing webhook secret → safe 500 | ✅ Returns "Webhook processing unavailable" |
| Error handler no type leak | ✅ `__class__.__name__` removed |

---

## 8. Tests Executed

```
tests/test_payment_hardening.py   16 passed  (17.67s)
tests/test_guardian.py             7 passed  (0.05s)
test_routing.py                    9 passed  (11.11s)
frontend npm run build             ✅ success (373ms)
```

---

## 9. Test Results

| Test | Status |
|------|--------|
| 1. Idempotent order creation | ✅ PASS |
| 2. Duplicate webhook detection | ✅ PASS |
| 3. Invalid webhook signature rejected | ✅ PASS |
| 4. Missing webhook secret rejected | ✅ PASS |
| 5. payment.failed → PAYMENT_FAILED | ✅ PASS |
| 6. payment.captured → PAYMENT_SUCCESS | ✅ PASS |
| 7. No downgrade from PAYMENT_SUCCESS | ✅ PASS |
| 8. No reverse transition | ✅ PASS |
| 9. Amount mismatch blocks order | ✅ PASS |
| 10. Error messages don't leak URLs | ✅ PASS |
| 11. Error handler no type leak | ✅ PASS |
| 12. State machine prevents double creation | ✅ PASS |
| 13. Full happy path transitions | ✅ PASS |
| 14. Failure recovery path | ✅ PASS |
| 15. Guardian rules regression | ✅ PASS |
| 16. Frontend build | ✅ PASS |

---

## 10. Deployment

### Pre-deployment Checklist

- [ ] Generate `RAZORPAY_WEBHOOK_SECRET` from Razorpay Dashboard → Webhooks → Active webhook → copy secret
- [ ] Add `RAZORPAY_WEBHOOK_SECRET` to Cloud Run environment variables
- [ ] Add `VITE_RAZORPAY_KEY_ID` to Vercel environment variables (value: `[MASKED_RAZORPAY_KEY]` for test)
- [ ] Run migration `002_payment_hardening.sql` against Supabase
- [ ] Deploy backend to Cloud Run (new revision)
- [ ] Deploy frontend to Vercel
- [ ] Verify webhook endpoint responds 400 to unsigned requests
- [ ] Test checkout flow end-to-end with test card (`4111 1111 1111 1111`)

---

## 11. Rollback

| Layer | Rollback Method |
|-------|----------------|
| Backend code | Revert to previous Cloud Run revision |
| Frontend code | Revert to previous Vercel deployment |
| Database | Migration is additive-only — drop indexes if needed |
| Config | Remove `RAZORPAY_WEBHOOK_SECRET` env var |

---

## 12. Known Limitations

1. **Webhook secret not yet provisioned** — Must be generated from Razorpay Dashboard and added to Cloud Run before webhooks will work. Until then, all webhooks return 500.

2. **Auto-capture assumption** — The implementation assumes Razorpay is in auto-capture mode. If manual capture is configured, `payment.authorized` events will be logged but the payment won't transition to `PAYMENT_SUCCESS` until `payment.captured` arrives.

3. **Frontend checkout key** — `VITE_RAZORPAY_KEY_ID` must be set in Vercel env vars. Without it, the Pay Now button shows a configuration error message.

4. **RLS policies are permissive** — All tables have `USING (true)` policies. Row-level security by user/merchant is not enforced at the DB level (only at the app level via `customer_id` matching).

5. **No concurrent DB transaction** — The idempotency check uses sequential reads/writes via Supabase REST API, not a database transaction. The UNIQUE constraint is the safety net for true concurrent races.

---

## 13. Final Production-Readiness Verdict

```
PAYMENT HARDENING:           PASS
ORDER IDEMPOTENCY:           PASS
WEBHOOK VERIFICATION:        PASS (code complete; needs secret provisioned)
WEBHOOK IDEMPOTENCY:         PASS
PAYMENT STATE MACHINE:       PASS
SECURITY:                    PASS
REGRESSION:                  PASS (32/32 tests + build)
PRODUCTION:                  NOT READY — blocked on:
                             1. RAZORPAY_WEBHOOK_SECRET not provisioned
                             2. VITE_RAZORPAY_KEY_ID not in Vercel
                             3. Migration 002 not applied to Supabase
```

> **The code is production-hardened. Deployment is blocked on three environment configuration steps that require manual action in the Razorpay Dashboard, Cloud Run console, and Vercel dashboard.**
