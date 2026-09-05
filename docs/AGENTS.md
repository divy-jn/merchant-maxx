# Agents: Merchant MAXX

## Repository Structure
All agent-related code resides in `backend/agents/`:
- `maxx.py`: The LangGraph orchestrator connecting all sub-agents.
- `scout.py`: Product discovery and cart building.
- `closer.py`: Checkout and payment logic.
- `guardian.py`: Constitutional AI safety gate.
- `ledger.py`: Audit logging.
- `booster.py` & `campaigner.py`: Data-driven upsells and promotions.
- `tools.py`: JSON schemas and implementations for agent capabilities.

## AgentState & LangGraph Routing
Merchant MAXX uses a LangGraph `StateGraph` with a defined `AgentState`.
The graph explicitly structures transitions to prevent the LLM from hallucinating state changes:
- `Scout` → `Tools` → `Closer`
- `Closer` → `Guardian` → `Ledger`

## Agent Responsibilities
- **MAXX**: The unified, customer-safe response boundary. Internal agents are invisible to the user.
- **Scout**: Interprets intent, searches catalog (`search_catalog`), fetches details (`get_product_details`), and manages the basket.
- **Closer**: Finalizes purchase intent and generates Razorpay payment links (`create_payment_link_for_product`, `create_razorpay_order`).
- **Guardian**: Enforces invariants (e.g., no payments without `user_confirmed=True`, no retries on failed payments). Overrides LLM hallucinations deterministically.
- **Ledger**: Writes immutable, non-repudiable audit logs to the `agent_audit` table.

## Important Concepts

### Quantity Semantics (ADD vs SET)
When modifying the cart, tools differentiate between:
- **ADD**: Incrementing the quantity of an existing item (e.g., "add another laptop").
- **SET**: Explicitly setting the quantity of an item (e.g., "I want exactly 3 laptops").
This prevents ambiguous updates when processing consecutive user messages. Strict bounds checking handles negative, zero, or malformed quantities gracefully.

### `pending_action`
State transitions often emit a `pending_action` indicating a required user interaction (e.g., payment confirmation) or internal routing decision.

### Customer-Safe Response Boundary
MAXX acts as a firewall. Internal agent names (Scout, Closer) and raw tool outputs are stripped or synthesized into a single, cohesive customer-facing persona.

### Important Invariants
1. **Server-Authoritative State**: `purchase_intents` in Supabase is the single source of truth for the cart. The LLM cannot hallucinate cart totals.
2. **Middleware Ordering**: `GlobalErrorMiddleware` → `RateLimitMiddleware` → `CORSMiddleware`.
3. **Strict Guardian Rules**: `RULE_06` guarantees `create_razorpay_order` only happens if the state is `USER_CONFIRMED`. `RULE_08` prevents blind retries on failed payments.

## Instructions for Future Coding Agents
- **Do not modify** `backend/agents/guardian.py` without strict review. It is the safety firewall.
- **Maintain Tool Isolation**: Agents should only bind tools they strictly need (`SCOUT_TOOLS`, `PAYMENT_TOOLS`, etc.). Do not share all tools globally.
- Ensure all cart modifications persist to `purchase_intents` prior to order creation to prevent TOCTOU race conditions.

## Test Commands
- Run E2E Backend Tests: `python backend/scripts/e2e_test.py`
- Run Pytest Suite: `pytest backend/tests/`
