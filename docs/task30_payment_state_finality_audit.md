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
# TASK 30: Payment State Finality & TOCTOU Audit Report

## Phase 1: State Mutation Matrix

| Location | Actor | State Read | State Written | Atomic? | Can Downgrade SUCCESS? |
|---|---|---|---|---|---|
| `chat.py:71` | User (accept rec) | Python (`intent`) | `USER_CONFIRMED` | No | **YES** |
| `chat.py:96` | User (confirm) | Python (`intent`) | `USER_CONFIRMED` | No | **YES** |
| `merger.py:67` | Agent (Merger) | Python (`current_state`) | `PRODUCT_SELECTED`, etc. | No | **YES** |
| `scout.py:151` | Agent (Scout) | Database | `PRODUCT_SELECTED` / `IDLE` | Yes (using `.in_`) | NO |
| `webhooks.py:190` | Webhook | Database | `PAYMENT_SUCCESS` / `FAILED` | Yes (using `.neq`)| NO |
| `webhooks.py:198` | Webhook | Python (`order`) | `FAILED` | No | **YES** (`orders` table) |
| `tools.py:223` | Guardian (create) | DB (already locked) | `PAYMENT_PENDING` | Yes | NO |
| `tools.py:270` | Guardian (rollback)| Python | `USER_CONFIRMED` | No | **YES** |
| `tools.py:280` | Guardian (rollback)| Database | `USER_CONFIRMED` | Yes (`.eq` lock) | NO |
| `tools.py:327` | Reconciler | Python | `PAYMENT_SUCCESS` | No | NO (Success is safe) |
| `tools.py:337` | Reconciler | Python | `PAYMENT_FAILED` | No | **YES** |

## Phase 2: Audit Terminal-State Guarantees

`PAYMENT_SUCCESS` is **not truly terminal** at the database level. Several parts of the application rely on Python-level checks (reading state at the beginning of an operation and writing it back later), which creates massive Time-of-Check to Time-of-Use (TOCTOU) vulnerabilities.

## Phase 3: `chat.py` Audit

**Vulnerability:** A stale user request can downgrade `PAYMENT_SUCCESS` to `USER_CONFIRMED`.
If a webhook sets `PAYMENT_SUCCESS` during the several seconds it takes for the LangGraph agent to process a turn, the hardcoded `update` calls in `chat.py` (lines 71 & 96) will blindly overwrite the database state because they rely on the `intent` object fetched at the *beginning* of the request.

## Phase 4: `merger.py` Audit

**Vulnerability:** Merger can downgrade `PAYMENT_SUCCESS` to `PRODUCT_SELECTED` or `PURCHASE_PENDING`.
Merger checks `if current_state == "PAYMENT_SUCCESS"` using the `state` dictionary provided by LangGraph, which is populated at the beginning of the turn. It does an unchecked `.update().eq(id)` which will overwrite a terminal state achieved via webhook during the LLM execution.

## Phase 5: `check_payment_status` Audit

**Vulnerability:** Reconciler can downgrade `PAYMENT_SUCCESS` to `PAYMENT_FAILED`.
The `check_payment_status` tool reads the DB, makes a network request to Razorpay, and then updates the DB. If a late-capture webhook arrives during the network request and sets the DB to `PAYMENT_SUCCESS`, the reconciler will blindly overwrite it to `PAYMENT_FAILED` based on its slightly older API response.

## Phase 6: Webhook Audit & Orders Table (Phase 9)

**Vulnerability:** The `orders` table is not protected against downgrades.
While `purchase_intents` is correctly protected by `.neq("purchase_state", "PAYMENT_SUCCESS")` in `webhooks.py`, the `orders` table update (line 198) has no such protection. A delayed or out-of-order `payment.failed` webhook will blindly update `orders.status` to `FAILED` and `fulfillment_status` to `PENDING`, breaking fulfillment for an already-paid order.

## Phase 7: State-Machine Audit

**Terminal States:** `PAYMENT_SUCCESS` (for intents), `CAPTURED` (for orders).
The state machine defined in `payment_state.py` is robust, but it is purely advisory. The application code routinely bypasses `can_transition()` by making direct Supabase `.update()` calls, meaning the state machine is not actually enforced.

## Phase 8: Concurrency Scenarios

- **A (Webhook SUCCESS vs Chat USER_CONFIRMED):** Fails. Chat overwrites SUCCESS (Downgrade).
- **B (Webhook SUCCESS vs Merger PRODUCT_SELECTED):** Fails. Merger overwrites SUCCESS (Downgrade).
- **C (Webhook SUCCESS vs payment.failed):** Fails for `orders` table (Downgraded to FAILED).
- **D (payment.failed vs payment.captured):** Fails for `orders` table if `failed` arrives last.
- **E (check_payment_status vs payment.failed):** Fails. Reconciler overwrites SUCCESS to FAILED.
- **F (Two reconciliations):** Fails. Last writer wins, susceptible to API delays.
- **G (Duplicate webhook with new event_id):** Fails. Bypasses `event_id` idempotency and can downgrade the `orders` table.

## Phase 10: Database-Level Enforcement Strategy

Relying on developers to remember `.neq("purchase_state", "PAYMENT_SUCCESS")` on every single `.update()` call is unsustainable and has already led to at least 5 distinct vulnerabilities.

**Recommendation:** Implement PostgreSQL `BEFORE UPDATE` triggers.
A trigger is the most reliable, architecturally sound enforcement mechanism because it acts as an absolute final barrier against ANY application-level mistake.

```sql
CREATE OR REPLACE FUNCTION prevent_terminal_state_downgrade()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.purchase_state = 'PAYMENT_SUCCESS' AND NEW.purchase_state != 'PAYMENT_SUCCESS' THEN
        RAISE EXCEPTION 'Cannot downgrade purchase_intent from PAYMENT_SUCCESS';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```
A similar trigger should be applied to the `orders` table to protect `status = 'CAPTURED'`.

## Phase 11: Final Verdict

**Verdict:** NOT PRODUCTION READY

**Severity:** P0
**Production Risk:** High. Concurrent webhooks and LLM turns are virtually guaranteed to overlap under load, leading to paid orders being marked as failed, unpaid, or pending, resulting in lost inventory, unfulfilled orders, and accounting mismatches.
