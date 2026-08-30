# Task 17 — Deterministic Agent Correctness Hardening

## Executive Summary

Task 17 hardens the Merchant Maxx agent system with deterministic safety boundaries that do not depend on LLM behavior. Three areas were addressed:

1. **Scout Ambiguity Guard** — A server-side check that validates the product_id the LLM wants to stage was actually surfaced in prior search/discovery tool results.
2. **Merger Conflict Detection** — An explicit guard that prevents Booster from overriding Scout's authoritative purchase product.
3. **Recommendation Idempotency** — A database migration adding a unique index on `recommendation_events.recommendation_id`.

All 50 tests pass. Frontend builds cleanly. No existing behavior regresses.

## Exact Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `backend/agents/scout.py` | MODIFIED | Added `_extract_product_ids_from_history()`, quantity validation (try/except, upper bound), product history guard |
| `backend/agents/merger.py` | MODIFIED | Added Booster conflict detection: if Booster's product_id differs from Scout's, it's logged and ignored |
| `backend/db/migrations/003_recommendation_idempotency.sql` | NEW | Unique index on `recommendation_events.recommendation_id` |
| `backend/tests/test_intelligence.py` | REWRITTEN | 9 tests covering ambiguity, quantity, casual interest, hallucinated product_ids |
| `backend/tests/test_merger.py` | NEW | 6 tests covering same-product merge, no-rec, failure, conflict, terminal state |

## Phase 1 — Scout Ambiguity Behavior

### What was added
- `_extract_product_ids_from_history(messages)` scans all `ToolMessage` objects in the conversation for product IDs matching the pattern `ID: item_*` or `Product ID: item_*`.
- Before staging a purchase intent, Scout checks: if there are known product IDs from prior search results AND the LLM's requested product_id is NOT among them → the staging is blocked.
- If there are NO prior tool results (first turn, or the LLM calls stage_purchase_intent directly without searching), the guard is permissive — it only blocks when it has evidence the product was never shown.

### What was NOT done (and why)
- **No keyword-based "casual interest" detection.** The task spec explicitly prohibits fragile keyword lists. Casual interest is handled by the LLM prompt. The deterministic guard focuses on product identity, not intent classification.
- **No multi-product ambiguity counter.** Counting how many products appeared in history and blocking if count > 1 would break legitimate flows where the user browsed 3 products and then explicitly said "I want the Lenovo one." The guard instead validates the specific product_id, not the count.

### Quantity validation
- `try/except (ValueError, TypeError)` → defaults to 1
- `< 1` → clamped to 1
- `> 99` → clamped to 99 (MAX_QUANTITY)

## Phase 2 — Merger Conflict Behavior

### What was added
- After applying Scout's intent staging, Merger extracts Scout's authoritative `product_id` from `purchase_context.basket_items[0]`.
- It checks if `booster_result` contains a `product_id` field. If it does and it differs from Scout's, a warning is logged and the Booster product is ignored.
- Booster remains advisory. It can only influence `purchase_state` transitions (RECOMMENDATION_SHOWN / PURCHASE_PENDING), never the basket contents.

### Existing behavior preserved
- PAYMENT_SUCCESS downgrade protection remains intact.
- Booster failure/skip/unavailable → PURCHASE_PENDING (checkout safe).
- All 11 existing parallel agent tests pass unchanged.

## Phase 3 — Database Constraint Status

### Existing constraints (verified)
| Constraint | Table | Column | Migration |
|-----------|-------|--------|-----------|
| `uq_orders_purchase_intent` | `orders` | `purchase_intent_id` (partial, non-null) | 002 |
| `uq_purchase_intents_rzp_order` | `purchase_intents` | `razorpay_order_id` (partial, non-null) | 002 |

### New constraint
| Constraint | Table | Column | Migration |
|-----------|-------|--------|-----------|
| `uq_recommendation_events_rec_id` | `recommendation_events` | `recommendation_id` | 003 |

The application uses `upsert` with `recommendation_id` as the key, but without a database-level unique constraint, concurrent requests could insert duplicates. Migration 003 adds `CREATE UNIQUE INDEX IF NOT EXISTS` — safe to re-run, non-destructive. A de-duplication query is provided in comments if needed before first application.

## Tests Added

### `test_intelligence.py` (9 tests)
1. `test_multiple_products_no_purchase_intent` — search_catalog call, no staging
2. `test_ambiguous_purchase_no_intent` — hallucinated product_id blocked by history guard
3. `test_explicit_single_product_staged` — valid product in history → staging succeeds
4. `test_casual_interest_no_intent` — "Looks good" → no staging
5. `test_quantity_two_preserved` — quantity=2 with server-side pricing
6. `test_quantity_zero_defaults_to_one` — 0 → 1
7. `test_quantity_negative_defaults_to_one` — -5 → 1
8. `test_quantity_malformed_defaults_to_one` — "abc" → 1
9. `test_stage_purchase_intent_tool_schema` — schema and tool validation

### `test_merger.py` (6 tests)
1. `test_scout_booster_same_product_merges` — normal merge path
2. `test_booster_no_recommendation_continues` — skipped → PURCHASE_PENDING
3. `test_booster_failure_preserves_checkout` — unavailable → PURCHASE_PENDING
4. `test_booster_conflicting_product_logged_and_ignored` — conflict logged, product unchanged
5. `test_payment_success_remains_terminal` — no downgrade
6. `test_payment_success_is_terminal` — state machine validation

## Full Test Results

```
50 passed, 3 warnings in 14.68s
```

All existing test suites pass:
- `test_audit.py` (3/3) — infinite loop, LLM fallback, merger contradictions
- `test_guardian.py` (7/7) — constitutional safety
- `test_intelligence.py` (9/9) — scout ambiguity & quantity
- `test_merger.py` (6/6) — merger conflict handling
- `test_parallel_agents.py` (9/9) — parallel Scout+Booster
- `test_payment_hardening.py` (16/16) — Razorpay lifecycle

## Frontend Build Result

```
✓ built in 731ms
dist/index.html                   0.53 kB
dist/assets/index-B0BLtM1x.css    8.95 kB
dist/assets/index-K3T899wW.js   244.50 kB
```

No build errors or warnings.

## Security Scan Result

| Check | Result |
|-------|--------|
| Hardcoded API keys in source | ✅ None found |
| Razorpay secrets in frontend | ✅ Only `VITE_RAZORPAY_KEY_ID` (public key) |
| `RAZORPAY_WEBHOOK_SECRET` exposure | ✅ Server-side only, via `settings` |
| Stack traces in HTTP responses | ✅ `GlobalErrorMiddleware` sanitizes |
| `__class__.__name__` in errors | ✅ Not present |
| `str(e)` in HTTP responses | ⚠️ Found in `routes/catalog.py:44` and `routes/audit.py:24` — pre-existing, not introduced by this task |

## Production Revision + Commit

| Item | Value |
|------|-------|
| Git commit (pre-deploy) | `e36071d` |
| Previous revision | `merchant-maxx-api-00022-8hn` |
| Previous commit | `05b3b27` |
| **Deployed revision** | **`merchant-maxx-api-00023-nrw`** |
| Traffic | 100% |

## Smoke Test Results

| Endpoint | Method | Expected | Actual | Status |
|----------|--------|----------|--------|--------|
| `/` | GET | 200 + JSON | `{"status":"ok","message":"Merchant Maxx API is running"}` | ✅ |
| `/catalog` | GET | 200 | 200 | ✅ |
| `/razorpay/webhook` | POST (invalid sig) | 400 | 400 | ✅ |

## Remaining Known Limitations

1. **Scout ambiguity is partially LLM-dependent.** The server-side guard blocks hallucinated product_ids, but whether the LLM asks for clarification vs. guessing among known products still depends on prompt adherence. This is documented rather than papered over with a fragile keyword list.
2. **`str(e)` in audit.py and catalog.py** — Pre-existing security concern in error responses. Not in scope for Task 17 but noted for future cleanup.
3. **Migration 003 requires manual application** — The migration creates `uq_recommendation_events_rec_id`. If duplicate `recommendation_id` rows exist in production, run the de-duplication query in the migration comments first.
4. **Booster conflict guard is defensive** — Booster currently never sets `product_id` in its result dict. The guard is proactive; it prevents future regressions if Booster's code changes.
