# Task 35: Final Pre-Rotation Production Security & Architecture Audit

## 1. Executive Summary
The Merchant Maxx system has undergone extensive hardening. The AI agent boundary, payment reconciliation pipeline, database RLS, and IDOR defenses are highly resilient and architecturally sound. 

However, **two critical infrastructure/deployment vulnerabilities (P0) remain unresolved**, directly impacting production safety and deployment consistency. As a result, the system is **NOT production-ready** until these are remediated.

---

## 2. Source-of-Truth Matrix
- **Git HEAD**: `Mon Aug 31 13:21:16 2026 +0530` (Task 34 completion).
- **Cloud Run Active Revision**: `merchant-maxx-api-00034-gzf` (deployed `2026-08-30 21:20:10 UTC`).
- **Cloud Run Latest Revision**: `merchant-maxx-api-1788163017520` **FAILED TO START** (Health check timeout on PORT=8080). Production traffic is currently serving an outdated, vulnerable revision.
- **Database Migrations**: Production Database has migration 008 (`refunds` table) applied, but `backend/db/schema.sql` has drifted and does **not** contain the 008 definitions.

## 3. Secret Exposure Matrix
> [!CAUTION]
> **Credential rotation is deferred to September 5th.** The following files must be untracked/deleted before rotation occurs.

| Provider | Credential Type | File/Path | Status | Severity | Remediation |
|---|---|---|---|---|---|
| All | All Production Secrets | `service.json` | **Tracked in Git** | **P0** | Untrack and delete from Git HEAD. Use GCP Secret Manager. |
| All | All Production Secrets | `_env_restore.txt` / `.yaml` | Untracked (Working Tree) | P2 | Add to `.gitignore` and delete from working tree. |
| Git History | `.env` credentials | `git log` | In Git History | P1 | Deferred to September 5 rotation. |

## 4. Authentication Matrix
- **JWT Verification**: Strict. `auth.py` validates tokens.
- **Fail-Safe**: `config.py` raises `ValueError` if `JWT_SECRET` is missing in the production environment.
- **Session Binding**: `get_current_user` properly extracts `user_id` from valid tokens.

## 5. Authorization / IDOR Matrix
- **Conversations**: `verify_conversation_ownership` strictly matches the token's `user_id` against the database `user_id`. Handles `guest` sessions safely.
- **Purchase Intents**: `tools.py` validates `intent.conversation_id == state.session_id`.
- **Database (RLS)**: Enforces Deny-All for `public`, `anon`, and `authenticated` roles.

## 6. AI & Tool Security Matrix
- **LLM Boundary**: Maintained. The LLM cannot independently mutate the database. It can only emit state parameters, which are validated by strict tools.
- **`create_razorpay_order`**: Verifies intent ownership, checks Guardian constraints, performs server-side amount validation, and uses optimistic concurrency control to prevent race conditions.
- **`check_payment_status`**: Read-only validation that safely integrates with `resolve_payment_status`.

## 7. Payment Lifecycle Matrix
- **Basket Confirmation**: `chat.py` atomically verifies basket state.
- **Webhook Idempotency**: Handled strictly via `webhook_events` deduplication.
- **Authoritative Resolution**: Both webhooks and reconciliation utilize `resolve_payment_status`, ensuring unified state logic.
- **Finality**: `is_terminal` checks prevent status downgrades (e.g., `PAYMENT_SUCCESS` cannot revert to `PAYMENT_FAILED`).

## 8. Webhook Event Matrix
| Event | Implemented | Idempotent | State-Changing | Financial Mutation |
|---|---|---|---|---|
| `payment.authorized` | Yes | Yes | Yes (to `PAYMENT_PENDING`) | No |
| `payment.captured` | Yes | Yes | Yes (to `PAYMENT_SUCCESS`) | Yes (triggers fulfillment) |
| `order.paid` | Yes | Yes | Yes (to `PAYMENT_SUCCESS`) | Yes |
| `payment.failed` | Yes | Yes | Yes (to `PAYMENT_FAILED`) | No |

## 9. Database Security Matrix
- **RLS**: Enabled on all 20 tables. Migration 005 successfully dropped permissive policies.
- **Service Role**: Backend correctly utilizes `SUPABASE_SERVICE_KEY` to bypass RLS.
- **Triggers**: `enforce_refund_finality` prevents downgrades from `REFUNDED`.

## 10. Infrastructure Matrix
- **Cloud Run Deployment**: **P0 FINDING**. The most recent Cloud Run deployment (`1788163017520`) failed with a startup probe timeout. Traffic remains on a legacy revision (`00034-gzf`), which does not contain the Task 34 architecture fixes.

## 11. Dependency & Code Quality Findings
- **Dependencies**: `pytest` is included in `requirements.txt`. It should be moved to a dev-dependency block. No SSRF/SQLi patterns were found.

## 12. Failure & Resilience Matrix
- **Local Persistence Failure**: Handled via `_recover_local_order` during webhook processing.
- **Inventory Failure**: `atomic_inventory_decrement` gracefully cascades to asynchronous refund workflows (`initiate_refund`).
- **Concurrent Webhooks**: Prevented via unique constraints on `webhook_events.event_id` and atomic state updates on `purchase_intents`.

## 13. Test Suite Verification
- `npm run build`: Completed successfully (1823 modules transformed).
- `pytest backend/tests/ -v`: All 138 tests verified passing.

## 14. Production Read-Only Verification
- Safe queries executed against production Supabase using the `SUPABASE_ANON_KEY`.
- Verified that `SELECT` operations on `products`, `orders`, `conversations`, and `refunds` return 0 rows under anonymous context, proving RLS Deny-All policies are actively enforced.

---

## Final Scorecard & Verdict

- **P0 Findings**:
  1. `service.json` containing all production credentials is tracked in Git HEAD.
  2. Cloud Run deployment is failing, leaving production exposed to pre-Task-34 vulnerabilities.
- **P1 Findings**:
  1. `schema.sql` is missing the `008_refund_idempotency.sql` definitions (drift).
- **P2 Findings**:
  1. `_env_restore` files present in working tree.
  2. `pytest` in production `requirements.txt`.

### Verdict
**PRODUCTION READY: NO**

**Launch Blocker**: The system cannot be considered ready until `service.json` is untracked and the Cloud Run deployment succeeds so that production actually runs the secure architecture. Credential rotation will follow on September 5th.
