# Task 14 — Parallel Architecture Audit

## 1. Current StateGraph Topology (from `backend/agents/maxx.py`)
Currently, the topology is fully sequential and state-machine-driven via conditional edges.
The `route_next_node` function dynamically directs the graph on every step:
- If `PAYMENT_FAILED`/`UNKNOWN`/`RECOVERY_PENDING` → `closer`
- If last message is a tool call → `tools`
- If `PRODUCT_SELECTED` → `booster`
- If `PURCHASE_PENDING`, `RECOMMENDATION_SHOWN`, `USER_CONFIRMED`, `GUARDIAN_APPROVED`, `ORDER_CREATED`, `PAYMENT_PENDING` → `closer`
- If text contains campaign keywords → `campaigner`
- Else → `scout`

There is no fan-out. The execution trace currently follows: `Scout` → `Tools (stage_intent)` → `Scout (process response)` → Route checks `PRODUCT_SELECTED` → `Booster` → `Tools (recommendation)` → `Booster` → sets `RECOMMENDATION_SHOWN` → `Closer`.

## 2. Current AgentState Fields
```python
class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    customer_id: str
    purchase_state: str
    purchase_context: PurchaseContext
    user_confirmed: bool
```
The state relies heavily on `messages` (additive) and direct mutation of `purchase_state`, `purchase_context`, and `user_confirmed`.

## 3. Current Scout Inputs/Outputs
- **Inputs:** `messages` (user intent).
- **Outputs:** Modifies `messages` (appends AI responses/tool calls).
- **Tool Side Effects:** If `stage_purchase_intent` is called, it queries Supabase for the product, creates a `pi_` ID, sets `purchase_state="PRODUCT_SELECTED"`, populates `purchase_context`, and sets `user_confirmed=False`. It natively inserts a row into `purchase_intents` in Supabase.

## 4. Current Booster Inputs/Outputs
- **Inputs:** `messages`, `purchase_context` (expects `basket_items`), `customer_id`.
- **Outputs:** Modifies `messages` (appends AI responses/tool calls).
- **Logic:** Calls `fetch_recommendations`.
- **Tool Side Effects:** `fetch_recommendations` upserts `recommendation_events` into Supabase.
- **Node Side Effects:** Booster manually modifies `purchase_state` to `RECOMMENDATION_SHOWN` (if recommendations exist) or `PURCHASE_PENDING` (if not or if it fails). Also directly updates `purchase_intents` in Supabase with this state.

## 5. Current Closer Inputs/Outputs
- **Inputs:** `messages`, `purchase_state`, `user_confirmed`, `purchase_context`.
- **Outputs:** Appends to `messages`.
- **Tool Side Effects:** Can call `create_razorpay_order` (which invokes Razorpay API and creates `orders` in Supabase), `check_payment_status`, or `reset_purchase_intent`.

## 6. Current Side Effects
- **Scout:** Database insert into `purchase_intents`.
- **Booster:** Database upsert into `recommendation_events`. Database update to `purchase_intents` (`purchase_state` modification).
- **Closer:** Razorpay API calls. Database inserts into `orders`, `order_items`, `entity_mapping`. Database updates to `purchase_intents`.

## 7. Current Supabase Writes
- `purchase_intents` table (Insert by Scout, Update by Booster, Update by Closer).
- `recommendation_events` table (Upsert by Booster tool).
- `orders`, `order_items`, `entity_mapping` (Insert by Closer tool).

## 8. Current Routing Conditions
Fully handled by `route_next_node` and `route_after_tools` in a sequential manner. `route_after_tools` directs back to the agent that called the tool.

## 9. Which Operations are Safe to Parallelize
- Information retrieval (Scout processing user intent vs. Booster calculating/retrieving affinities).
- In a parallel model, Scout deciding on a product and Booster retrieving recommendations *for* that product cannot be strictly parallelized if Booster needs Scout's output (the selected product). 
- **However**, if Scout and Booster execute simultaneously on the user's initial input, Scout would perform product discovery while Booster analyzes past history or cart context to suggest items. If the cart is currently *empty*, Booster has nothing to augment. 
- Wait, the requirement asks to parallelize "independent customer-discovery and recommendation work". If the user asks for a laptop, Scout finds it. Can Booster run in parallel? No, Booster needs to know what Scout found to cross-sell a mouse.
- Alternatively, if the fan-out is *after* the product is selected, then Scout is already done.
- Let's re-read the core requirement: 
```text
           SCOUT            BOOSTER
             │                 │
             └────────┬────────┘
                      ▼
              MERGER / VALIDATOR
```
This implies Scout and Booster run *in parallel*. But how does Booster know what to recommend if Scout hasn't decided yet? 
"Booster should consume immutable/contextual product information... Booster should generate cross-sell recommendations rather than blindly recommending another laptop."
If Scout and Booster run in parallel on the *same* user turn, Booster only knows the `purchase_context` that already existed before this turn (or it extracts intent itself, which is redundant).
If Scout finds the product *and then* we parallelize? "SCOUT + BOOSTER -> MERGER". This strongly implies they run as siblings on the user's input.
If they are siblings, they both receive the same state. If they both use LLMs, they process the user intent concurrently. 
Wait, the prompt says: "SCOUT and BOOSTER may execute independently/in parallel ONLY when their inputs are available and neither requires the other to mutate state first."

## 10. Which Operations MUST Remain Sequential
- `stage_purchase_intent` (inserting intent) must happen before `Booster` tries to update its state or `Closer` tries to pay.
- `Closer` and Razorpay payment must strictly follow the output of the Merger/Validator. 
- Side effect writes to `purchase_intents` (modifying `purchase_state`) should not be done simultaneously by two nodes to avoid race conditions.

## 11. LangGraph StateGraph Support
LangGraph version 1.1.6 supports parallel execution implicitly. If you add edges from node A to both node B and node C, LangGraph executes B and C concurrently. When they both finish, they reduce into the state, and you can transition to node D.
Because `messages` uses `operator.add`, both Scout and Booster would append messages. If they both append at the exact same time, LangGraph 1.1.6 handles list addition safely. 
However, for scalar fields (like `purchase_state`), the last writer wins unless a custom reducer is used, which creates race conditions.

## 12. Reducer/State-Conflict Issues
- `purchase_state`: If Scout sets it to `PRODUCT_SELECTED` and Booster tries to set it to `RECOMMENDATION_SHOWN`, they will conflict.
- `purchase_context`: If Scout populates it and Booster reads it simultaneously, Booster will read the *old* context (before Scout populated it).
This violates "neither requires the other to mutate state first."
Therefore, Scout MUST run first to populate `purchase_context`, OR Scout and Booster must output strictly disjoint state fields (e.g. `scout_result`, `booster_result`) which the Merger combines.

## 13. Rollback Strategy
If parallelism causes issues, we revert to the linear `Scout -> Booster -> Closer` execution by replacing the parallel fan-out with the standard `route_next_node` logic. No DB drops are needed.
