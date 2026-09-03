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
# Task 30C — Production Payment State Finality Activation

## Date: 2026-08-31

## Objective

Deploy the Task 30B Payment State Finality & TOCTOU Remediation to production, including migration 007 and the hardened application code.

---

## Core Invariant (Enforced)

> Once `purchase_intents.purchase_state = PAYMENT_SUCCESS`, it must **NEVER** transition to any other purchase state.
> Once `orders.status = CAPTURED`, it must **NEVER** transition to any other order status.

Enforcement: PostgreSQL `BEFORE UPDATE` triggers at the database level, plus atomic application-level `.neq()` guards.

---

## Phase 1 — Preflight Verification ✅

| Check | Result |
|---|---|
| Git HEAD | `297c6b6` — "Task 30B: Payment State Finality & TOCTOU Remediation" |
| Previous Cloud Run revision | `merchant-maxx-api-00033-hd7` |
| `test_payment_state_finality.py` | 13 passed, 1 xfailed ✅ |
| Full regression (`backend/tests/`) | 127 passed, 1 xfailed ✅ |
| Frontend build (`npm run build`) | ✅ |
| Migration 007 not yet applied | Confirmed — triggers did not exist |

---

## Phase 2 — Production Migration 007 ✅

Applied via Supabase MCP `execute_sql`:

### Trigger 1: `enforce_intent_finality`
- **Table**: `purchase_intents`
- **Function**: `trg_prevent_intent_downgrade()`
- **Behavior**: `RAISE EXCEPTION` if `OLD.purchase_state = 'PAYMENT_SUCCESS'` and `NEW.purchase_state != 'PAYMENT_SUCCESS'`
- Allows non-state column updates (e.g., metadata) on finalized rows

### Trigger 2: `enforce_order_finality`
- **Table**: `orders`
- **Function**: `trg_prevent_order_downgrade()`
- **Behavior**: `RAISE EXCEPTION` if `OLD.status = 'CAPTURED'` and `NEW.status != 'CAPTURED'`
- Allows non-status column updates on finalized rows

---

## Phase 3 — Production Trigger Verification ✅

```sql
SELECT tgname, relname FROM pg_trigger
JOIN pg_class ON pg_trigger.tgrelid = pg_class.oid
WHERE tgname IN ('enforce_intent_finality', 'enforce_order_finality');
```

| tgname | relname |
|---|---|
| `enforce_intent_finality` | `purchase_intents` |
| `enforce_order_finality` | `orders` |

Both triggers confirmed present in production database.

---

## Phase 4 — Cloud Run Deployment ✅

| Item | Value |
|---|---|
| Deploy command | `gcloud run deploy merchant-maxx-api --source backend --region us-central1 --allow-unauthenticated` |
| New revision | `merchant-maxx-api-00034-gzf` |
| Traffic | **100%** |
| Service URL | `https://merchant-maxx-api-1066165000716.us-central1.run.app` |

---

## Phase 5 — Production Smoke Tests ✅

| Test | Expected | Result |
|---|---|---|
| `GET /` | 200 | ✅ 200 — `{"status":"ok"}` |
| `GET /catalog` | 200 + products | ✅ 200, products returned |
| Authenticated chat | 200 + LLM response | ✅ Conversation created, MAXX responded |
| Cross-user IDOR | 403 | ✅ 403 — "Not authorized to access this conversation" |
| Unsigned webhook | 400 | ✅ 400 — "Invalid signature" |
| DB connectivity | Confirmed via chat | ✅ |

---

## Phase 6 — Git Push ✅

```
git push origin main
e36071d..297c6b6  main -> main
```

Branch is up to date with `origin/main`.

---

## Files Deployed (Task 30B Commit)

| File | Change |
|---|---|
| `backend/db/migrations/007_payment_state_finality.sql` | **NEW** — DB triggers |
| `backend/tests/test_payment_state_finality.py` | **NEW** — 14-test regression suite |
| `backend/routes/chat.py` | Atomic `.neq()` guard on intent updates |
| `backend/routes/webhooks.py` | Dual-layer terminal state protection |
| `backend/agents/merger.py` | Terminal state protection on sync |
| `backend/agents/tools.py` | Rollback guard + order mapping protection |

---

## Security Guarantees Preserved

- **Task 28**: RLS hardening — ✅ (anon access blocked)
- **Task 29**: LLM payment authorization bypass — ✅ (DB-authoritative confirmation)
- **Task 30B**: Payment state finality — ✅ (DB triggers + atomic app guards)
- **IDOR protection**: ✅ (403 on cross-user access)
- **Webhook signature verification**: ✅ (400 on unsigned)

---

## Status: COMPLETE ✅

All phases executed successfully. No secrets exposed. No real payments performed. No existing records modified.
