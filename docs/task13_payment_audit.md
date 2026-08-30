# Task 13 — Razorpay Payment Lifecycle Audit

> **Status:** AUDIT COMPLETE — awaiting approval before any code changes.
> **Date:** 2026-08-30
> **Scope:** End-to-end payment lifecycle in Merchant Maxx production codebase.

---

## 1. Current Flow

The complete payment lifecycle currently traces:

```
User selects product in chat
  ↓
Scout → stage_purchase_intent tool call
  ↓
scout_node() fetches server-side price from Supabase `products` table
  ↓
Creates purchase_intent_id (pi_{uuid}) → inserts into `purchase_intents`
  ↓
Sets purchase_state = PRODUCT_SELECTED, user_confirmed = false
  ↓
Booster → fetch_recommendations tool call (optional cross-sell)
  ↓
purchase_state → RECOMMENDATION_SHOWN | PURCHASE_PENDING
  ↓
User confirms (regex match in chat.py CONFIRM_RE)
  ↓
chat.py updates purchase_intents: purchase_state = USER_CONFIRMED, user_confirmed = true
  ↓
Route → Closer agent
  ↓
Closer calls create_razorpay_order tool
  ↓
tools.py: Guardian validation → basket re-validation → server-side amount calc
  ↓
razorpay_service/orders.py: rzp.order.create(amount, "INR", receipt=intent_id, notes={})
  ↓
tools.py: Insert local `orders` row + `order_items` + `entity_mapping`
  ↓
Update purchase_intents: purchase_state = PAYMENT_PENDING, razorpay_order_id = rzp_order_id
  ↓
LLM returns order ID to user in chat (text-based)
  ↓
*** NO FRONTEND CHECKOUT MODAL EXISTS ***
  ↓
User would need to manually use the Razorpay order for payment
  ↓
Webhook at POST /razorpay/webhook handles payment.captured / payment.failed
  ↓
Updates `payments`, `purchase_intents`, `recommendation_events`
```

### Key Observation: No Frontend Checkout Integration

The frontend (`AgentChat.jsx`) has **no Razorpay Checkout modal**. There is no `checkout.js` script loaded, no `window.Razorpay` usage, and no dedicated checkout route. The `checkout_plan.md` doc describes a planned but **unimplemented** integration. Payment flow currently terminates at "order created, awaiting payment" — with the Razorpay order ID returned as text in chat.

---

## 2. Existing State Machine

States observed in code (across `scout.py`, `booster.py`, `closer.py`, `chat.py`, `tools.py`, `maxx.py`, `webhooks.py`):

```
IDLE                (implicit default in maxx.py route_next_node)
    ↓
PRODUCT_SELECTED    (scout_node → stage_purchase_intent)
    ↓
RECOMMENDATION_SHOWN (booster_node, if recs exist)
    ↓                                         ↓
PURCHASE_PENDING     (booster fallback/skip)  ↓
    ↓                                         ↓
USER_CONFIRMED       (chat.py CONFIRM_RE match, sets user_confirmed=true)
    ↓
GUARDIAN_APPROVED    (referenced in maxx.py routing but never explicitly set)
    ↓
ORDER_CREATED        (set in orders table purchase_state, tools.py line 138)
    ↓
PAYMENT_PENDING      (set on purchase_intents after Razorpay order creation, tools.py line 142)
    ↓
PAYMENT_SUCCESS      (webhook: payment.captured)
PAYMENT_FAILED       (webhook: payment.failed; also check_payment_status can detect)
PAYMENT_UNKNOWN      (check_payment_status inconclusive)
RECOVERY_PENDING     (referenced in reset_purchase_intent valid reset states)
```

### Transition Guardrails Currently in Place:
- `create_razorpay_order` requires `purchase_state == USER_CONFIRMED` AND `user_confirmed == true`
- Constitutional rule RULE_06 blocks order creation if state != USER_CONFIRMED
- Constitutional rule RULE_05 blocks duplicates if existing order detected
- Constitutional rule RULE_08 blocks retries on PAYMENT_FAILED/UNKNOWN
- `reset_purchase_intent` only works from PAYMENT_FAILED/UNKNOWN/RECOVERY_PENDING

### State Inconsistency Issues:
1. `GUARDIAN_APPROVED` is listed in `maxx.py` routing conditions but never written anywhere
2. `ORDER_CREATED` is set on the `orders` table row but `purchase_intents` goes directly to `PAYMENT_PENDING`
3. Webhook writes `PAYMENT_SUCCESS` but `check_payment_status` returns `PAYMENT_SUCCESS` string — however `_load_active_intent` in `chat.py` does NOT include `PAYMENT_SUCCESS` or `PAYMENT_PENDING` in its filter, so post-payment intents are invisible to the chat route

---

## 3. Existing DB Schema

### `purchase_intents` (authoritative payment state)

| Column | Type | Notes |
|--------|------|-------|
| purchase_intent_id | TEXT PK | `pi_{uuid12}` |
| conversation_id | UUID FK | Nullable |
| customer_id | TEXT FK | Nullable |
| merchant_id | TEXT | Default 'merchant_mxx_001' |
| purchase_state | TEXT NOT NULL | Default 'PURCHASE_PENDING' |
| basket | JSONB | `[{product_id, quantity}]` |
| subtotal_paise | BIGINT | Server-calculated |
| discount_paise | BIGINT | |
| tax_paise | BIGINT | |
| amount_paise | BIGINT | Total after discount+tax |
| user_confirmed | BOOLEAN | |
| razorpay_order_id | TEXT | Set after order creation |
| razorpay_payment_id | TEXT | Set by webhook |
| recommendation_id | TEXT | Added by migration 001 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| expires_at | TIMESTAMPTZ | |

**Indexes:** customer_id, conversation_id, purchase_state
**Missing:** No unique constraint on razorpay_order_id

### `orders`

| Column | Type | Notes |
|--------|------|-------|
| order_id | TEXT PK | `ord_{uuid12}` |
| purchase_intent_id | TEXT | Added by migration 001, NO unique constraint |
| merchant_id | TEXT | |
| customer_id | TEXT FK | |
| status | TEXT | |
| subtotal_paise | BIGINT | |
| discount_paise | BIGINT | |
| tax_paise | BIGINT | |
| total_paise | BIGINT | |
| currency | TEXT | |
| source | TEXT | |
| purchase_state | TEXT | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**No UNIQUE constraint on `purchase_intent_id`** — multiple orders can be created for the same intent.

### `entity_mapping`

| Column | Type | Notes |
|--------|------|-------|
| mapping_id | UUID PK | |
| merchant_id | TEXT | |
| synthetic_id | TEXT NOT NULL | |
| entity_type | TEXT NOT NULL | |
| razorpay_id | TEXT NOT NULL | |
| created_at | TIMESTAMPTZ | |

**Has unique indexes:** `(merchant_id, entity_type, razorpay_id)` and `(merchant_id, entity_type, synthetic_id)`

### `payments`

| Column | Type | Notes |
|--------|------|-------|
| payment_id | TEXT PK | `pay_{rzp_payment_id}` |
| order_id | TEXT FK | |
| customer_id | TEXT FK | |
| amount_paise | BIGINT | |
| currency | TEXT | |
| status | TEXT | |
| method | TEXT | |
| failure_code | TEXT | |
| failure_reason | TEXT | |
| razorpay_payment_id | TEXT | |
| initiated_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |

### `webhook_events`

| Column | Type | Notes |
|--------|------|-------|
| event_id | TEXT PK | Used as idempotency key |
| event_type | TEXT NOT NULL | |
| razorpay_entity_id | TEXT | |
| received_at | TIMESTAMPTZ | |
| processed_at | TIMESTAMPTZ | |
| status | TEXT | Default 'RECEIVED' |
| error | TEXT | |

**Missing columns:** razorpay_order_id, razorpay_payment_id (separate from entity_id)

---

## 4. Existing Razorpay Integration

### Client Setup
- `razorpay_service/client.py`: Creates `razorpay.Client(auth=(KEY_ID, KEY_SECRET))` singleton
- Key and secret loaded from `config.py` via `.env`
- Secret is **server-side only** — not exposed to frontend

### Order Creation
- `razorpay_service/orders.py`: `create_order(amount_paise, currency, receipt, notes)`
- Called from `tools.py` `create_razorpay_order` tool
- Receipt is set to `purchase_intent_id`
- Notes include `purchase_intent_id` and `merchant_id`

### Payment Status Check
- `tools.py` `check_payment_status`: Fetches order payments via `rzp.order.payments(order_id)`
- Maps: any `captured` → SUCCESS, all `failed` → FAILED, else → UNKNOWN
- **Does NOT update DB** — only returns text to LLM

### Webhook Handler
- `routes/webhooks.py`: `POST /razorpay/webhook`
- Signature verification: Uses `rzp.utility.verify_webhook_signature()`
- **BUT**: Verification is conditional — `if secret:` means if `RAZORPAY_WEBHOOK_SECRET` is not set, **all webhooks are accepted without verification**
- Idempotency: Uses `event_id` PK on `webhook_events` table, catches duplicate insert exception
- Processes only `payment.captured` and `payment.failed` events
- Amount validation: Checks webhook amount matches local order total
- Updates `payments` table via upsert
- Updates `purchase_intents.purchase_state` to PAYMENT_SUCCESS/PAYMENT_FAILED

### Missing:
- `RAZORPAY_WEBHOOK_SECRET` is not in `config.py` Settings class — it's accessed via `getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)` which will always return `None` since the field isn't declared
- No `payment.authorized` event handling (relevant if auto-capture is off)
- No `order.paid` event handling

---

## 5. Identified Risks

### CRITICAL

| # | Risk | Location | Severity |
|---|------|----------|----------|
| R1 | **Duplicate Razorpay orders possible** — No DB-level unique constraint on `orders.purchase_intent_id`. If `create_razorpay_order` is called twice rapidly (agent retry, Cloud Run duplicate, double-click), two different Razorpay orders can be created for the same intent. Guardian RULE_05 checks `orders` table for existing rows but there's a TOCTOU race. | `tools.py:119-120` | Critical |
| R2 | **Webhook signature bypass** — `RAZORPAY_WEBHOOK_SECRET` is not declared in `Settings` class. `getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)` always returns `None`, so the `if secret:` guard is never active. All webhooks are accepted unverified in production. | `config.py`, `webhooks.py:26-31` | Critical |
| R3 | **No frontend checkout** — Users cannot complete payment. The Razorpay order is created but there's no checkout modal to pay. This means the payment flow is incomplete. | `AgentChat.jsx` | Critical |

### HIGH

| # | Risk | Location | Severity |
|---|------|----------|----------|
| R4 | **Race condition in idempotency check** — `tools.py:119-120` checks for existing orders via SELECT, then creates if none found. Under concurrent requests, both can pass the check before either inserts. | `tools.py:119-120` | High |
| R5 | **`check_payment_status` leaks provider error** — The except clause returns `f"PAYMENT_UNKNOWN: unable to verify safely ({exc})"` which can include Razorpay API URLs and error details. | `tools.py:160` | High |
| R6 | **Webhook amount mismatch raises HTTPException** — If amount doesn't match, it raises `HTTPException(400, detail="Payment amount does not match local order")` which tells the attacker what validation failed. | `webhooks.py:61` | High |
| R7 | **No downgrade protection** — Nothing prevents a duplicate PAYMENT_FAILED webhook from overwriting PAYMENT_SUCCESS state. The upsert in `payments` and update in `purchase_intents` will execute regardless of current state. | `webhooks.py:84-87` | High |
| R8 | **`get_product_details` leaks exception** — Returns `f"Error fetching product details: {exc}"` which can contain Razorpay API URLs/internal errors. | `tools.py:54` | High |

### MEDIUM

| # | Risk | Location | Severity |
|---|------|----------|----------|
| R9 | `GlobalErrorMiddleware` includes `exc.__class__.__name__` in 500 responses — leaks internal type names. | `error_handler.py:24` | Medium |
| R10 | `GUARDIAN_APPROVED` state referenced but never set — dead state in routing. | `maxx.py:38` | Medium |
| R11 | `ORDER_CREATED` set on `orders.purchase_state` but `purchase_intents` jumps directly to `PAYMENT_PENDING` — inconsistent state across tables. | `tools.py:138,142` | Medium |
| R12 | Webhook derives `event_id` with fallback `f"{event}:{rzp_payment_id}:{payload.get('created_at', '')}"` — Razorpay does provide a stable `id` field at the top level, so this fallback is rarely needed but could produce non-unique IDs if `created_at` is missing. | `webhooks.py:40` | Medium |

---

## 6. Proposed Minimal Changes

### Phase 2: Idempotent Order Creation

**File:** `tools.py`

1. In `create_razorpay_order`, **before** the Razorpay API call, check if `purchase_intents.razorpay_order_id` is already set:
   - If set → return existing order ID immediately (idempotent return)
   - If not set → proceed with creation
2. This uses the existing `razorpay_order_id` column as the idempotency marker.
3. No new identity system needed — `purchase_intent_id` already provides uniqueness.

**Migration:** `002_payment_hardening.sql`
- Add `UNIQUE` constraint on `orders.purchase_intent_id`
- Add `UNIQUE` index on `purchase_intents.razorpay_order_id` (where not null)

### Phase 3: Payment State Machine

Minimal state model (reusing existing states):

```
PRODUCT_SELECTED → RECOMMENDATION_SHOWN → PURCHASE_PENDING → USER_CONFIRMED
    → PAYMENT_PENDING → PAYMENT_SUCCESS | PAYMENT_FAILED
```

Remove dead states: `GUARDIAN_APPROVED`, `ORDER_CREATED` (from purchase_intents context).
Add valid transition enforcement function.

**Key rule:** `PAYMENT_SUCCESS → PAYMENT_FAILED` is **never** allowed.
`PAYMENT_SUCCESS → PAYMENT_SUCCESS` is a no-op (idempotent).

### Phase 4: Supabase Schema

Add to migration:
- `webhook_events.razorpay_order_id TEXT`
- `webhook_events.razorpay_payment_id TEXT`
- `purchase_intents.payment_updated_at TIMESTAMPTZ`
- Unique indexes as described above

### Phase 5: Webhook Hardening

**File:** `config.py`
- Add `RAZORPAY_WEBHOOK_SECRET: str = ""` to Settings class

**File:** `webhooks.py`
1. Make signature verification **mandatory** (not conditional)
2. Add state downgrade protection
3. Handle `payment.authorized` event (maps to PAYMENT_PENDING if auto-capture off)
4. Sanitize all error responses

### Phase 6: Webhook Idempotency

Already partially in place via `event_id` PK. Improvements:
- Add state downgrade check before DB mutations
- Use database-level constraint as primary guard (already done via PK)
- Ensure the caught exception path returns 200 for legitimate duplicates

### Phase 7: Payment Status Tool

**File:** `tools.py`
- Remove exception details from return strings
- Add DB state update as a reconciliation step
- Handle Razorpay API failures with safe generic message

### Phase 8: Closer Safety

Already well-implemented. Minor improvements:
- Verify Closer prompt cannot override state checks (it can't — tools enforce)

### Phase 9: Frontend Checkout

Add Razorpay Checkout.js integration. Since no frontend checkout exists:
- Add `checkout.js` script to `index.html`
- Add `VITE_RAZORPAY_KEY_ID` to frontend `.env.example`
- Create payment trigger in chat response (detect Razorpay order ID in bot response → show "Pay Now" button)
- Implement checkout modal with double-click prevention
- Verify payment via backend after checkout callback

### Phase 10: Security

- Remove `exc.__class__.__name__` from error middleware
- Sanitize all tool error returns
- Grep for secret leaks after changes

---

## 7. Rollback Strategy

### Pre-Change Safeguards
1. All schema changes via numbered migrations (002_payment_hardening.sql)
2. Migration uses `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` for safe re-runs
3. No column drops or renames — all changes are additive

### Code Rollback
1. Git branch: `task13-payment-hardening`
2. All changes committed atomically
3. Previous Cloud Run revision remains available

### Database Rollback
- No destructive schema changes proposed
- New indexes/constraints can be dropped without data loss
- Migration 002 is a forward-only additive migration
- If constraints conflict with existing data, migration will fail safely (no partial apply)

### Cloud Run Rollback
- Deploy as new revision
- Keep previous revision serving
- Only route traffic after smoke tests pass
- Instant rollback by re-routing to previous revision

---

## Summary of Files to Modify

| File | Change Type | Risk |
|------|------------|------|
| `backend/config.py` | Add RAZORPAY_WEBHOOK_SECRET field | Low |
| `backend/agents/tools.py` | Idempotent order creation, sanitize errors | Medium |
| `backend/routes/webhooks.py` | Mandatory signature verification, state guard | Medium |
| `backend/middleware/error_handler.py` | Remove type name leak | Low |
| `backend/db/migrations/002_payment_hardening.sql` | New additive migration | Low |
| `backend/db/schema.sql` | Keep in sync | Low |
| `frontend/index.html` | Add checkout.js script | Low |
| `frontend/src/pages/AgentChat.jsx` | Add checkout trigger | Medium |
| `frontend/.env.example` | Add VITE_RAZORPAY_KEY_ID | Low |
| `.env.example` | Already has RAZORPAY_WEBHOOK_SECRET | None |
| `backend/tests/test_payment_hardening.py` | New test file | None |
