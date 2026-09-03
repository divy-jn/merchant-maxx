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

## Phase 3 — Resilience & State Integrity

- `[x]` 21. `purchase_intents` table in schema + RLS policy
- `[x]` 22. Chat route (`routes/chat.py`) — loads/persists authoritative purchase state from Supabase per turn
- `[x]` 23. Webhook handler rewrite (`routes/webhooks.py`)
  - `[x]` 23a. Idempotency checks (payment dedup)
  - `[x]` 23b. Entity mapping lookup (Razorpay Order ID → local `order_id`)
  - `[x]` 23c. Payment recording in `payments` table
  - `[x]` 23d. Order status updates (COMPLETED / FAILED)
  - `[x]` 23e. Revenue attribution via `purchase_intent_id` receipt → CONVERTED
  - `[x]` 23f. Failed-payment handling with FAILED propagation
- `[x]` 24. Guardian constitutional hardening (`audit/constitutional.py`)
  - `[x]` 24a. `auth_intent` param for server-side authoritative checks
  - `[x]` 24b. RULE_05: Real idempotency via `razorpay_order_id` existence
  - `[x]` 24c. RULE_07 (new): Amount-match validation
  - `[x]` 24d. RULE_02: Reads `user_confirmed` from authoritative state
- `[x]` 25. Tool refactoring (`agents/tools.py`)
  - `[x]` 25a. Scoped tool sets (`SCOUT_TOOLS`, `BOOSTER_TOOLS`, `CAMPAIGNER_TOOLS`, `PAYMENT_TOOLS`)
  - `[x]` 25b. `stage_purchase_intent` — system-determined pricing (no LLM amounts)
  - `[x]` 25c. `confirm_and_pay` removed → `check_payment_status` added
  - `[x]` 25d. `create_razorpay_order` creates local `orders` + `order_items` + `entity_mapping`
  - `[x]` 25e. `fetch_recommendations` — `lift_score > 1.0` threshold + category fallback
  - `[x]` 25f. `analyze_campaign_opportunities` — correct `lifetime_value_paise` column
- `[x]` 26. Scout agent — authoritative pricing + recommendation tracking
- `[x]` 27. MAXX orchestrator — `MemorySaver` checkpointer + expanded routing + defensive `.get()`
- `[x]` 28. Guardian agent — passes `auth_intent` to evaluator

## Verification

- `[x]` Pipeline runs clean (exit 0)
- `[x]` DB seeded successfully
- `[x]` LangGraph compiles
- `[ ]` Guardian rules pass unit tests
- `[x]` Server starts without errors
- `[ ]` **E2E Test 1**: Happy-path Razorpay Test Mode transaction
- `[ ]` **E2E Test 2**: FAILED/UNKNOWN recovery scenario
