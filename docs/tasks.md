# Merchant Maxx — Overhaul Task Tracker

## Phase 0 — Data Foundation

- `[x]` 1. Schema migration (FK constraints, new columns in `agent_audit`, `recommendation_events`)
- `[x]` 2. Data pipeline fixes
  - `[x]` 2a. `transform_retailrocket.py` — preserve useful hashed properties
  - `[x]` 2b. `generate_synthetic_data.py` — funnel calibration from real RR data
  - `[x]` 2c. `generate_synthetic_data.py` — basket reconstruction from co-purchase data
  - `[x]` 2d. `generate_synthetic_data.py` — single discount model (order-level only)
  - `[x]` 2e. `generate_synthetic_data.py` — payment distribution totals 100%
  - `[x]` 2f. `generate_synthetic_data.py` — workflow-driven agent audit
  - `[x]` 2g. `generate_synthetic_data.py` — Indian context (expanded cities, categories)
  - `[x]` 2h. `generate_synthetic_data.py` — recommendation events lifecycle
  - `[x]` 2i. `validate_data.py` — comprehensive validation + proper exit codes
  - `[x]` 2j. `build_customer_metrics.py` — preferred_category from real data
- `[x]` 3. Demo fixtures (`demo_fixtures.py`)
- `[x]` 4. Run pipeline end-to-end
- `[x]` 5. Seed DB (`seed_database.py`)

## Phase 1 — Agent Infrastructure

- `[x]` 6. `AgentState` + purchase state machine in `maxx.py`
- `[x]` 7. MAXX graph rewiring (Scout → Booster when appropriate → Closer)
- `[x]` 8. Closer Agent: Remove LLM-driven `user_confirmed=True` blind overrides. Read from trusted `AgentState`.
- `[x]` 9. Real Booster DB queries in `tools.py` + `booster.py`
- `[x]` 10. Real Campaigner DB queries in `tools.py` + `campaigner.py`
- `[x]` 11. Guardian RULE_01–08 in `constitutional.py` + `guardian.py`
- `[x]` 12. Purchase state transitions enforced in router
- `[x]` 13. `create_razorpay_order` tool + Razorpay Order flow (basket-total amounts)
- `[x]` 14. Webhook handler (`webhooks.py`)
- `[x]` 15. Failure/UNKNOWN recovery (new `purchase_intent_id` on retry)
- `[x]` 16. Audit logging updates in `ledger.py`

## Phase 2 — Tracking & Attribution

- `[x]` 17. `recommendation_events` real lifecycle (GENERATED → SHOWN → CONVERTED)
- `[x]` 18. Revenue attribution (CONVERTED only when order contains product + payment verified)
- `[x]` 19. Entity mapping
- `[x]` 20. Validation improvements (input validation in tools + chat)

## Verification

- `[x]` Pipeline runs clean (exit 0)
- `[x]` DB seeded successfully
- `[x]` LangGraph compiles
- `[ ]` Guardian rules pass unit tests
- `[x]` Server starts without errors
- `[ ]` **E2E Test 1**: Happy-path Razorpay Test Mode transaction
- `[ ]` **E2E Test 2**: FAILED/UNKNOWN recovery scenario
