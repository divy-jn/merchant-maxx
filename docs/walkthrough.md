# Walkthrough: Merchant Maxx Core Flow & Attribution

All Phase 1 and Phase 2 tasks from the implementation plan have been completed. The backend has been completely rewired to use a data-driven architecture that correctly routes through LangGraph, enforces state transitions strictly, generates real recommendations, and produces auditable transaction records.

## 1. Agent Infrastructure (Phase 1)
- **Scout, Booster, Closer**: The LangGraph state machine is fully implemented. The agent flow is controlled structurally by the backend application state, eliminating any risk of the LLM forcefully overriding a purchase intent (`user_confirmed=True`).
- **Data-Driven Booster & Campaigner**: Replaced stub recommendation functions with real `fetch_recommendations` logic that queries `product_affinity` and `customer_metrics` from Supabase to provide data-backed up-sells.
- **Strict Guardian Enforcements**: The `Guardian` now verifies actions using the injected server-side purchase context.
  - **RULE_06** ensures `create_razorpay_order` can only be executed in a valid `USER_CONFIRMED` state.
  - **RULE_08** ensures no blind retries on failed payments.
- **Razorpay Orders & Recovery**: The `create_razorpay_order` tool uses validated basket totals. If a transaction fails or reaches an unknown state, the new `reset_purchase_intent` tool enables generating a fresh `purchase_intent_id`, ensuring completely separated auditing.

## 2. Tracking & Attribution (Phase 2)
- **Recommendation Lifecycle**: A rigorous state-tracking lifecycle (`GENERATED → SHOWN → CLICKED → ACCEPTED → CONVERTED`) is in place. Recommendations are saved to the `recommendation_events` table when generated.
- **Webhook Integration**: Added `routes/webhooks.py` to capture `payment.captured` and `payment.failed` events. 
- **Revenue Attribution**: During `payment.captured` webhook processing, the system attributes revenue to the successful recommendation if it was `ACCEPTED` and correctly logs it.
- **Entity Mapping**: Integrated `entity_mapping` within the `create_razorpay_order` tool to connect synthetic `ord_*` identifiers directly with `order_*` from Razorpay.
- **Ledger & Auditing**: Detailed logging continues tracking all critical security dimensions of AI agent interactions, now with robust linkage to session and customer identifiers, directly to the `agent_audit` ledger.

## Verifications Completed
- **Pipeline Check**: Scripts ran cleanly (Exit Code 0).
- **Graph & Type check**: LangGraph schema compiles and passes all checks.
- **App Startup**: Uvicorn spins up without API errors (`uvicorn main:app --port 8000`).

## Next Steps
You can now proceed with:
- **E2E Test 1**: Happy-path Razorpay Test Mode transaction via the application frontend.
- **E2E Test 2**: FAILED/UNKNOWN recovery scenario testing.
