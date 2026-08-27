# Merchant Maxx — Agent Architecture Overhaul

Revised plan integrating all 43 specification points. Preserves the existing FastAPI + LangGraph + Supabase + Razorpay architecture. Single merchant (`merchant_mxx_001`). No unnecessary infrastructure.

---

## Core Principle

```
DATA → intelligence → bounded agent decision → explicit authorization
→ deterministic Guardian → actual Razorpay Test transaction
→ verified outcome → revenue attribution → audit trail
```

---

## P0 — Core Agent Infrastructure

### P0.1 — Structured AgentState + Purchase State Machine

> [!IMPORTANT]
> The LLM **requests** payment actions. It does **not** authorize them. Payment authorization comes from structured application state + Guardian.

#### [MODIFY] [maxx.py](file:///c:/building%20projs/razorpay_proj/backend/agents/maxx.py)

Replace the current `AgentState = {messages}` with full structured state:

```python
class PurchaseContext(TypedDict, total=False):
    product_id: str              # Supabase products.product_id
    product_name: str
    amount_paise: int
    customer_email: str
    customer_contact: str
    purchase_intent_id: str      # Idempotency key (uuid, one per purchase attempt)
    razorpay_order_id: str       # Filled after Razorpay order creation
    razorpay_payment_id: str     # Filled after payment
    razorpay_plink_id: str       # Filled if payment link used

PURCHASE_STATES = [
    "IDLE", "PRODUCT_SELECTED", "PURCHASE_PENDING", "USER_CONFIRMED",
    "GUARDIAN_APPROVED", "GUARDIAN_BLOCKED", "ORDER_CREATED",
    "PAYMENT_PENDING", "PAYMENT_SUCCESS", "PAYMENT_FAILED",
    "PAYMENT_UNKNOWN", "RECOVERY_PENDING", "COMPLETED", "CANCELLED"
]

VALID_TRANSITIONS = {
    "IDLE":              ["PRODUCT_SELECTED"],
    "PRODUCT_SELECTED":  ["PURCHASE_PENDING", "IDLE"],
    "PURCHASE_PENDING":  ["USER_CONFIRMED", "CANCELLED", "IDLE"],
    "USER_CONFIRMED":    ["GUARDIAN_APPROVED", "GUARDIAN_BLOCKED"],
    "GUARDIAN_APPROVED":  ["ORDER_CREATED", "PAYMENT_PENDING"],
    "GUARDIAN_BLOCKED":   ["IDLE", "CANCELLED"],
    "ORDER_CREATED":     ["PAYMENT_PENDING"],
    "PAYMENT_PENDING":   ["PAYMENT_SUCCESS", "PAYMENT_FAILED", "PAYMENT_UNKNOWN"],
    "PAYMENT_SUCCESS":   ["COMPLETED"],
    "PAYMENT_FAILED":    ["RECOVERY_PENDING", "CANCELLED"],
    "PAYMENT_UNKNOWN":   ["RECOVERY_PENDING"],
    "RECOVERY_PENDING":  ["USER_CONFIRMED", "CANCELLED", "IDLE"],  # after state inspection
    "COMPLETED":         ["IDLE"],  # new purchase
    "CANCELLED":         ["IDLE"],
}

def transition_state(current: str, target: str) -> str:
    """Enforces valid state transitions. Raises ValueError on illegal transition."""
    if target not in VALID_TRANSITIONS.get(current, []):
        raise ValueError(f"Illegal state transition: {current} → {target}")
    return target

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    purchase_state: str                 # From PURCHASE_STATES
    purchase_context: PurchaseContext
    user_confirmed: bool                # Set by router, NEVER by LLM
    session_id: str
    customer_id: str
    recommendation_ids: list            # Track shown reco IDs for attribution
    error: str                          # For failure recovery messaging
```

State transitions are enforced **programmatically by router functions**, not by agent prompts or LLM tool call arguments.

---

### P0.2 — MAXX Graph Rewiring

#### [MODIFY] [maxx.py](file:///c:/building%20projs/razorpay_proj/backend/agents/maxx.py)

New graph topology:

```
Entry → Scout → [tools] → Scout
                ↓ (PRODUCT_SELECTED + opportunity exists)
              Booster → [tools] → Booster → END
                ↓ (USER_CONFIRMED)
              Closer → [tools] → Closer → END
                ↓
              END

Separate merchant-growth path (not in checkout flow):
  Scout detects campaign/analytics intent → Campaigner → [tools] → END
```

Key rules:
- **Booster does NOT always run** — only when `purchase_state == PRODUCT_SELECTED` AND the product has affinity data
- **Campaigner is NOT in the checkout flow** — activates only for merchant analytics/growth queries ("how to increase sales", "campaign ideas", discount analysis)
- No unnecessary agent loops

```python
workflow = StateGraph(AgentState)

workflow.add_node("scout", scout_node)
workflow.add_node("booster", booster_node)
workflow.add_node("campaigner", campaigner_node)
workflow.add_node("closer", closer_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

workflow.set_entry_point("scout")

def route_after_scout(state) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    ps = state.get("purchase_state", "IDLE")
    if ps == "PRODUCT_SELECTED":
        return "booster"       # Booster evaluates recommendation opportunity
    if ps == "USER_CONFIRMED":
        return "closer"        # Skip to Closer for confirmed purchases
    return END

def route_after_booster(state) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END                  # Booster presents recommendations, user continues

def route_after_tools(state) -> str:
    for msg in reversed(state["messages"]):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_name = msg.tool_calls[0]["name"]
            if tool_name in ("create_razorpay_order", "create_payment_link_for_product"):
                return "closer"
            if tool_name == "fetch_recommendations":
                return "booster"
            if tool_name == "analyze_campaign_opportunities":
                return "campaigner"
            return "scout"
    return "scout"

workflow.add_conditional_edges("scout", route_after_scout)
workflow.add_conditional_edges("booster", route_after_booster)
workflow.add_conditional_edges("campaigner", should_use_tools_or_end)
workflow.add_conditional_edges("closer", should_use_tools_or_end)
workflow.add_conditional_edges("tools", route_after_tools)
```

#### [MODIFY] [__init__.py](file:///c:/building%20projs/razorpay_proj/backend/agents/__init__.py)

Update exports to include all node functions and new state types.

---

### P0.3 — Remove LLM Payment Authorization

> [!CAUTION]
> `user_confirmed` must come **only** from trusted server-side `AgentState`. Do NOT inject authorization fields into LLM tool-call arguments and then treat those arguments as trusted. The payment tool must **resolve** confirmation and purchase state from the trusted application state directly — never from tool call args.

#### [MODIFY] [closer.py](file:///c:/building%20projs/razorpay_proj/backend/agents/closer.py)

**Delete** the B25 override block (lines 48–52) that sets `user_confirmed=True` unconditionally.

Closer no longer touches authorization fields at all. The LLM may request a payment action, but the **tool itself** resolves authorization from server-side state:

```python
def closer_node(state: dict):
    messages = state.get("messages", [])
    # ... system prompt setup ...
    llm = get_llm().bind_tools(PAYMENT_TOOLS)
    response = llm.invoke(messages)
    # Closer does NOT inject user_confirmed, purchase_state, or any auth fields
    # into tool call args. The tool resolves these from trusted AgentState.
    return {"messages": [response]}
```

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py) — payment tools

Payment tools (`create_razorpay_order`, `create_payment_link_for_product`) must **not accept** `user_confirmed` or `purchase_state` as arguments. Instead, they receive a reference to the trusted state (e.g., `session_id`) and resolve authorization server-side:

```python
@tool
def create_razorpay_order(product_id: str, session_id: str = None) -> str:
    """Creates a Razorpay Order. Authorization is resolved from server-side
    purchase state — this tool does NOT accept user_confirmed as an argument."""

    # 1. Resolve trusted state from server-side session/state store
    purchase_state = get_purchase_state(session_id)  # trusted server lookup
    user_confirmed = purchase_state.user_confirmed    # from AgentState, not LLM
    purchase_intent_id = purchase_state.purchase_intent_id
    customer_id = purchase_state.customer_id

    # 2. Build action_intent from trusted state
    action_intent = {
        "user_confirmed": user_confirmed,
        "purchase_state": purchase_state.state,
        "purchase_intent_id": purchase_intent_id,
        "item_id": product_id,
        "session_id": session_id,
        "action_type": "create_razorpay_order",
    }

    # 3. Guardian validates
    validate_action("Closer", "create_razorpay_order", action_intent, amount)
    # ... Razorpay API call, local DB writes, audit ...
```

**Update** `closer_prompt` — remove "Always set user_confirmed=True". Replace with:
```
You receive structured purchase state from the system.
Do NOT set user_confirmed — the system handles authorization.
Your job: prepare the transaction, present the result, handle errors gracefully.
```

---

### P0.4 — Data-Driven Booster (Real DB Queries)

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py) — `fetch_recommendations`

Replace the hardcoded stub with real Supabase queries:

```python
@tool
def fetch_recommendations(product_id: str = None, customer_id: str = None,
                          category: str = None, session_id: str = None) -> str:
    """Fetches data-driven product recommendations from product_affinity,
    customer_metrics, and products tables. Returns ranked results."""
    if not supabase:
        return "Recommendation service unavailable."
    results = []

    # Strategy 1: Product affinity (co-purchase data from RetailRocket patterns)
    if product_id:
        affinity = supabase.table("product_affinity") \
            .select("related_product_id, confidence_score, lift_score, co_purchase_count") \
            .eq("product_id", product_id) \
            .order("confidence_score", desc=True) \
            .limit(10).execute()
        if affinity.data:
            related_ids = [r["related_product_id"] for r in affinity.data]
            products_res = supabase.table("products") \
                .select("product_id, name, price_paise, category, active, inventory_qty, rating") \
                .in_("product_id", related_ids) \
                .eq("active", True).execute()
            product_map = {p["product_id"]: p for p in products_res.data}

            for aff in affinity.data:
                p = product_map.get(aff["related_product_id"])
                if not p:
                    continue
                # Eligibility filters (item 14)
                if not p["active"] or p.get("inventory_qty", 0) <= 0:
                    continue
                if p["product_id"] == product_id:  # same product
                    continue
                results.append({
                    "product_id": p["product_id"],
                    "name": p["name"],
                    "price": p["price_paise"] / 100,
                    "category": p["category"],
                    "confidence": aff["confidence_score"],
                    "lift": aff["lift_score"],
                    "reason": f"co_purchase (confidence: {aff['confidence_score']}, lift: {aff['lift_score']})"
                })

    # Strategy 2: Customer preference fallback
    if not results and customer_id:
        metrics = supabase.table("customer_metrics") \
            .select("preferred_category, avg_order_value_paise") \
            .eq("customer_id", customer_id).execute()
        if metrics.data:
            pref_cat = metrics.data[0].get("preferred_category")
            if pref_cat:
                cat_products = supabase.table("products") \
                    .select("product_id, name, price_paise, category, rating") \
                    .eq("category", pref_cat).eq("active", True) \
                    .order("rating", desc=True).limit(5).execute()
                for p in cat_products.data:
                    results.append({...})  # format similarly

    if not results:
        return "No data-backed recommendations available for this product."

    # Format for LLM consumption (LLM explains, does NOT invent relationships)
    formatted = []
    for r in results[:5]:
        formatted.append(
            f"- {r['name']} (ID: {r['product_id']})\n"
            f"  Price: Rs. {r['price']:,.2f} | Category: {r['category']}\n"
            f"  Basis: {r['reason']}"
        )
    return "Data-backed recommendations:\n\n" + "\n\n".join(formatted)
```

> [!IMPORTANT]
> The LLM role is to **explain and personalize** recommendations. It must NOT invent recommendation relationships. Only products returned by the tool may be recommended.

#### [MODIFY] [booster.py](file:///c:/building%20projs/razorpay_proj/backend/agents/booster.py)

- Bind `BOOSTER_TOOLS = [fetch_recommendations]` only (not all DISCOVERY_TOOLS)
- Update prompt to read `purchase_context.product_id` from state and call `fetch_recommendations` with it
- Add eligibility reminder: do not recommend inactive, out-of-stock, same product, or over-budget items

---

### P0.5 — Data-Driven Campaigner (Real DB Queries)

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py) — `analyze_campaign_opportunities`

Replace hardcoded stub:

```python
@tool
def analyze_campaign_opportunities(category: str = None,
                                    segment: str = None) -> str:
    """Analyzes real customer_metrics, orders, and product data to identify
    campaign opportunities. Returns structured opportunities with evidence."""
    if not supabase:
        return "Campaign analysis service unavailable."
    opportunities = []

    # 1. Churn-risk high-value customers
    churn_query = supabase.table("customer_metrics") \
        .select("customer_id, churn_probability, lifetime_value_paise, segment") \
        .gte("churn_probability", 0.6) \
        .order("lifetime_value_paise", desc=True).limit(20).execute()
    if churn_query.data:
        total_ltv = sum(c["lifetime_value_paise"] for c in churn_query.data)
        opportunities.append({
            "opportunity": "REACTIVATION",
            "target": f"{len(churn_query.data)} high-value churn-risk customers",
            "recommended_action": "Personalized discount or loyalty offer",
            "baseline": f"At-risk LTV: Rs. {total_ltv / 100:,.2f}",
            "estimated_impact": f"Estimated retention uplift: 10-20%",
            "confidence": "Medium — based on churn_probability >= 0.6",
            "evidence": f"customer_metrics: {len(churn_query.data)} customers with churn_probability >= 0.6"
        })

    # 2. Low-conversion categories (views >> purchases)
    # Query customer_events for VIEW vs PURCHASE counts by category...

    # 3. Active campaigns check (avoid overlap)
    active = supabase.table("campaigns").select("campaign_id, name, target_category, status") \
        .eq("status", "ACTIVE").execute()

    # 4. Strong cross-sell relationships (high-lift pairs undermarketed)
    # Query product_affinity for high-lift pairs...

    # Format as structured opportunities
    # Use "estimated uplift" / "predicted impact", NOT "causal" / "incremental"
    ...
```

#### [MODIFY] [campaigner.py](file:///c:/building%20projs/razorpay_proj/backend/agents/campaigner.py)

- Bind `CAMPAIGNER_TOOLS = [analyze_campaign_opportunities]` only
- Update prompt: Campaigner detects opportunities from **real data**, returns structured findings
- Never claim causal uplift — use "estimated uplift" and "predicted impact"

---

### P0.6 — Guardian RULE_01 through RULE_08

#### [MODIFY] [constitutional.py](file:///c:/building%20projs/razorpay_proj/backend/audit/constitutional.py)

All 8 rules implemented with real checks:

```python
def evaluate_safety(action_intent: dict, amount_paise: int = 0) -> ConstitutionalCheckResult:
    violations = []
    risk = 0.0

    # RULE_01: Max transaction limit (deterministic)
    if amount_paise > settings.GUARDIAN_MAX_TRANSACTION_PAISE:
        violations.append("RULE_01_MAX_TX_LIMIT: ...")
        risk += 0.8

    # RULE_02: User confirmation (from structured state, NOT LLM)
    if settings.GUARDIAN_REQUIRE_CONFIRMATION and not action_intent.get("user_confirmed", False):
        violations.append("RULE_02_USER_CONFIRMATION: ...")
        risk += 0.6

    # RULE_03: PII protection (deterministic scan of action_intent description)
    desc = str(action_intent.get("description", ""))
    if re.search(r'\b\d{16}\b', desc):  # crude card number check
        violations.append("RULE_03_PII_PROTECTION: Possible card number in action description")
        risk += 0.9

    # RULE_04: No self-dealing — entity must belong to merchant
    entity_id = action_intent.get("item_id") or action_intent.get("product_id")
    if entity_id and supabase:
        product = supabase.table("products").select("merchant_id") \
            .eq("product_id", entity_id).execute()
        if product.data and product.data[0].get("merchant_id") != "merchant_mxx_001":
            violations.append("RULE_04_NO_SELF_DEALING: Entity does not belong to merchant")
            risk += 0.9

    # RULE_05: Idempotency — check purchase_intent_id
    intent_id = action_intent.get("purchase_intent_id")
    if intent_id and supabase:
        existing = supabase.table("agent_audit") \
            .select("audit_id") \
            .eq("entity_id", intent_id) \
            .eq("action_type", action_intent.get("action_type", "")) \
            .eq("status", "SUCCESS").execute()
        if existing.data:
            violations.append("RULE_05_IDEMPOTENCY: purchase_intent_id already executed")
            risk += 0.9

    # RULE_06: Valid purchase state transition
    purchase_state = action_intent.get("purchase_state", "")
    action_type = action_intent.get("action_type", "")
    REQUIRED_STATES = {
        "create_razorpay_order": ["GUARDIAN_APPROVED"],
        "create_payment_link": ["GUARDIAN_APPROVED", "USER_CONFIRMED"],
        "retry_payment": ["RECOVERY_PENDING"],
    }
    if action_type in REQUIRED_STATES:
        if purchase_state not in REQUIRED_STATES[action_type]:
            violations.append(
                f"RULE_06_VALID_STATE: Cannot '{action_type}' from state '{purchase_state}'. "
                f"Required: {REQUIRED_STATES[action_type]}"
            )
            risk += 0.8

    # RULE_07: Valid entity — product exists, is active, belongs to merchant
    if entity_id and supabase:
        product = supabase.table("products") \
            .select("product_id, active, merchant_id") \
            .eq("product_id", entity_id).execute()
        if not product.data:
            violations.append("RULE_07_VALID_ENTITY: Product does not exist")
            risk += 0.9
        elif not product.data[0].get("active"):
            violations.append("RULE_07_VALID_ENTITY: Product is inactive")
            risk += 0.7

    # RULE_08: No blind retry after FAILED/UNKNOWN
    if purchase_state in ("PAYMENT_FAILED", "PAYMENT_UNKNOWN"):
        if not action_intent.get("state_inspected", False):
            violations.append("RULE_08_NO_BLIND_RETRY: Must inspect actual Razorpay state before retry")
            risk += 1.0

    passed = len(violations) == 0
    reasoning = "All safety checks passed." if passed else f"Blocked: {'; '.join(violations)}"
    return ConstitutionalCheckResult(
        passed=passed, violations=violations,
        risk_score=min(risk, 1.0), reasoning=reasoning
    )
```

#### [MODIFY] [guardian.py](file:///c:/building%20projs/razorpay_proj/backend/agents/guardian.py)

Update `validate_action` signature to accept the full structured intent including `purchase_intent_id`, `purchase_state`, `session_id`, `customer_id`.

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py) — payment tool

Update `create_payment_link_for_product` (and new `create_razorpay_order`) to pass all structured fields to Guardian:

```python
action_intent = {
    "description": f"Create order for {item['name']}",
    "user_confirmed": user_confirmed,        # From AgentState, not LLM
    "purchase_state": purchase_state,         # From AgentState
    "purchase_intent_id": purchase_intent_id, # Idempotency key
    "item_id": item_id,
    "session_id": session_id,
    "action_type": "create_razorpay_order",
}
validate_action(agent_name="Closer", action_type="create_razorpay_order",
                action_intent=action_intent, amount_paise=item_amount)
```

---

### P0.7 — Purchase State Transitions

#### [MODIFY] [maxx.py](file:///c:/building%20projs/razorpay_proj/backend/agents/maxx.py)

Router functions enforce transitions using `transition_state()`:

- Scout selects product → router sets `PRODUCT_SELECTED`
- User confirms → router detects confirmation in message → `transition_state("PURCHASE_PENDING", "USER_CONFIRMED")`, sets `user_confirmed=True`
- Guardian approves → `GUARDIAN_APPROVED`
- Guardian blocks → `GUARDIAN_BLOCKED`
- Razorpay order created → `ORDER_CREATED`
- Payment pending → `PAYMENT_PENDING`
- Webhook/status confirms → `PAYMENT_SUCCESS` or `PAYMENT_FAILED`

Any illegal transition raises `ValueError` → logged to Ledger → user gets graceful error.

#### [MODIFY] [chat.py](file:///c:/building%20projs/razorpay_proj/backend/routes/chat.py)

Pass `session_id` and `customer_id` into MAXX invocation. Initialize `purchase_state="IDLE"` for new conversations. Restore purchase state from previous messages for continuing conversations.

---

### P0.8 — Razorpay Order + Payment Flow

> [!IMPORTANT]
> **Primary demo path** must be: Merchant Maxx purchase intent → Guardian → Razorpay Order → payment → verification/webhook → local state → audit/attribution. Payment Links are kept as a fallback, but the primary demo should use the Razorpay Order flow.

> [!WARNING]
> For multi-item/upsell orders, the Razorpay order amount must come from the **validated purchase basket/order total**, not from only one product's `price_paise`. The tool must compute the total from all items in the purchase context.

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py)

**New tool** `create_razorpay_order` — the primary checkout path.

This tool does NOT accept `user_confirmed` or `purchase_state` as arguments. It resolves authorization from trusted server-side state (per correction #1):

```python
@tool
def create_razorpay_order(product_id: str, session_id: str = None) -> str:
    """Creates a Razorpay Order for the selected product. This is the primary
    checkout path. Authorization is resolved from server-side purchase state."""

    # 1. Resolve trusted state from server-side session store
    purchase_state = get_purchase_state(session_id)
    user_confirmed = purchase_state.user_confirmed
    purchase_intent_id = purchase_state.purchase_intent_id
    customer_id = purchase_state.customer_id

    # 2. Fetch product from Supabase products table
    product = supabase.table("products").select("*").eq("product_id", product_id).single().execute()
    item = product.data

    # 3. Compute order amount from purchase basket (not just one product)
    #    For single-product orders, basket total == product price
    #    For multi-item/upsell orders, sum all items in purchase_context
    basket_items = purchase_state.basket_items or [{"product_id": product_id, "quantity": 1}]
    order_total = 0
    order_items_data = []
    for bi in basket_items:
        p = supabase.table("products").select("product_id, name, price_paise") \
            .eq("product_id", bi["product_id"]).single().execute()
        item_total = p.data["price_paise"] * bi.get("quantity", 1)
        order_total += item_total
        order_items_data.append({
            "product_id": bi["product_id"],
            "quantity": bi.get("quantity", 1),
            "unit_price_paise": p.data["price_paise"],
            "total_paise": item_total
        })

    # 4. Guardian validation (from trusted state, not tool args)
    action_intent = {
        "description": f"Create order for {item['name']}",
        "user_confirmed": user_confirmed,
        "purchase_state": purchase_state.state,
        "purchase_intent_id": purchase_intent_id,
        "item_id": product_id,
        "session_id": session_id,
        "action_type": "create_razorpay_order",
    }
    validate_action("Closer", "create_razorpay_order", action_intent, order_total)

    # 5. Create Razorpay Order (real test mode API call)
    from razorpay_service import orders
    rzp_order = orders.create_order(
        amount_paise=order_total,     # From validated basket total
        currency="INR",
        receipt=purchase_intent_id,
        notes={"product_id": product_id, "session_id": session_id}
    )

    # 6. Record in local orders table
    local_order_id = f"ord_{uuid4().hex[:12]}"
    supabase.table("orders").insert({
        "order_id": local_order_id,
        "merchant_id": "merchant_mxx_001",
        "customer_id": customer_id,
        "status": "CREATED",
        "subtotal_paise": order_total,
        "discount_paise": 0,
        "tax_paise": 0,
        "total_paise": order_total,
        "currency": "INR",
        "source": "AI_AGENT",
        "purchase_state": "ORDER_CREATED",
    }).execute()

    # 7. Entity mapping (local → Razorpay)
    supabase.table("entity_mapping").insert({
        "synthetic_id": local_order_id,
        "entity_type": "order",
        "razorpay_id": rzp_order["id"]
    }).execute()

    # 8. Order items (from validated basket)
    for oi in order_items_data:
        supabase.table("order_items").insert({
            "order_item_id": f"oi_{uuid4().hex[:12]}",
            "order_id": local_order_id,
            "product_id": oi["product_id"],
            "quantity": oi["quantity"],
            "unit_price_paise": oi["unit_price_paise"],
            "discount_paise": 0,
            "total_paise": oi["total_paise"]
        }).execute()

    # 9. Audit
    log_agent_action(agent_name="Closer", action_type="create_razorpay_order",
                     status="SUCCESS", purchase_state="ORDER_CREATED",
                     razorpay_entity_id=rzp_order["id"],
                     session_id=session_id, customer_id=customer_id,
                     entity_type="ORDER", entity_id=local_order_id,
                     amount_paise=order_total,
                     reasoning=f"Order created for {item['name']}")

    return (f"Order created!\n"
            f"Product: {item['name']}\n"
            f"Amount: Rs. {order_total/100:,.2f}\n"
            f"Razorpay Order ID: {rzp_order['id']}\n"
            f"Status: {rzp_order['status']}\n"
            f"Use the Razorpay Order ID to complete payment.")
```

**Keep** `create_payment_link_for_product` as a supported fallback but:
- Also resolves authorization from server-side state (not tool args)
- Write to `entity_mapping` (`payment_link` type)
- Write to `orders` table with `purchase_state`
- Write to `payments` table
- **Never** store `plink_id` as `order_id`
- Uses validated basket total for amount (same as `create_razorpay_order`)

**Update** `PAYMENT_TOOLS` and `ALL_TOOLS` to include the new tool.

---

### P0.9 — Webhook / Status Verification

#### [NEW] [routes/webhooks.py](file:///c:/building%20projs/razorpay_proj/backend/routes/webhooks.py)

```python
@router.post("/razorpay/webhook")
async def handle_razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # 1. Verify webhook signature
    try:
        rzp.utility.verify_webhook_signature(body.decode(), signature, webhook_secret)
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event", "")
    entity = payload.get("payload", {})

    # 2. Identify order/payment
    if event == "payment.captured":
        payment_entity = entity.get("payment", {}).get("entity", {})
        rzp_order_id = payment_entity.get("order_id")
        rzp_payment_id = payment_entity.get("id")

        # 3. Update local state via entity_mapping
        mapping = supabase.table("entity_mapping") \
            .select("synthetic_id").eq("razorpay_id", rzp_order_id).execute()
        if mapping.data:
            local_order_id = mapping.data[0]["synthetic_id"]
            supabase.table("orders").update({
                "status": "COMPLETED",
                "purchase_state": "PAYMENT_SUCCESS"
            }).eq("order_id", local_order_id).execute()

            # 4. Record payment
            supabase.table("payments").insert({
                "payment_id": f"pay_{uuid4().hex[:12]}",
                "order_id": local_order_id,
                "amount_paise": payment_entity.get("amount"),
                "status": "CAPTURED",
                "method": payment_entity.get("method", "").upper(),
                "razorpay_payment_id": rzp_payment_id,
            }).execute()

            # 5. Entity mapping for payment
            supabase.table("entity_mapping").insert({
                "synthetic_id": local_order_id,
                "entity_type": "payment",
                "razorpay_id": rzp_payment_id
            }).execute()

        # 6. Audit
        log_agent_action(agent_name="Webhook", action_type="payment_captured",
                         status="SUCCESS", razorpay_entity_id=rzp_payment_id,
                         purchase_state="PAYMENT_SUCCESS", ...)

    elif event == "payment.failed":
        # Similar — update to PAYMENT_FAILED, record failure_code/reason
        ...

    return {"status": "ok"}
```

#### [MODIFY] [main.py](file:///c:/building%20projs/razorpay_proj/backend/main.py)

Add `from routes import webhooks` and `app.include_router(webhooks.router)`.

**Also add** a status-check tool for manual verification (when webhooks haven't arrived yet):

```python
@tool
def check_payment_status(razorpay_order_id: str) -> str:
    """Checks actual payment status from Razorpay API. Use for UNKNOWN state resolution."""
    from razorpay_service import orders
    rzp_order = orders.fetch_order(razorpay_order_id)
    payments = orders.fetch_order_payments(razorpay_order_id)
    # Return actual status, update local state if needed
    ...
```

---

### P0.10 — Failure / UNKNOWN Recovery

> [!IMPORTANT]
> Any payment retry after `PAYMENT_FAILED` or `PAYMENT_UNKNOWN` **must** create a new `purchase_intent_id` and go through fresh authorization (Guardian validation from scratch). The old `purchase_intent_id` is consumed and cannot be reused as retry authorization.

#### [MODIFY] [maxx.py](file:///c:/building%20projs/razorpay_proj/backend/agents/maxx.py)

When `purchase_state` is `PAYMENT_FAILED` or `PAYMENT_UNKNOWN`:

1. Router sets state to `RECOVERY_PENDING`
2. **Must** call `check_payment_status` to inspect actual Razorpay state
3. If Razorpay says success → finalize locally (`PAYMENT_SUCCESS`)
4. If Razorpay says failed → offer user choice: retry or abandon
   - **Retry creates a new `purchase_intent_id`** (old intent is dead)
   - Retry goes through `USER_CONFIRMED → GUARDIAN_APPROVED → ORDER_CREATED` again from scratch
   - Guardian sees a fresh intent, not a reused one (RULE_05 won't fire)
5. If still unknown → escalate to user with explanation
6. All recovery actions logged to Ledger

Guardian's RULE_08 enforces: no blind retry without `state_inspected=True`.
Guardian's RULE_05 enforces: old `purchase_intent_id` cannot be re-executed.

---

### P0.11 — Audit Logging

#### [MODIFY] [ledger.py](file:///c:/building%20projs/razorpay_proj/backend/agents/ledger.py)

Update `log_agent_action` to include all required fields for money actions:

```python
def log_agent_action(
    agent_name, action_type, status,
    input_summary="", output_summary="", reasoning="",
    risk_score=0.0, constitutional_check=None,
    razorpay_entity_id=None, session_id=None, customer_id=None,
    entity_type=None, entity_id=None, purchase_state=None,
    amount_paise=0, user_confirmed=False, guardian_approved=False,
    failure_code=None, failure_reason=None
):
```

Write to both `audit_log` (backward compat) and `agent_audit` (comprehensive).

All money action audit records must include: agent, action, session, customer, entity, amount, purchase state, user_confirmed, guardian result, risk_score, reasoning, razorpay entity, final status, failure/recovery info.

---

## P1 — Tracking & Attribution

### P1.1 — Recommendation Events (Real Lifecycle)

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py)

When `fetch_recommendations` returns results, **generate** recommendation records but do **NOT** mark them as `SHOWN` yet:

```python
# Inside fetch_recommendations, after results are assembled:
rec_ids = []
for r in results[:5]:
    rec_id = f"rec_{uuid4().hex[:12]}"
    supabase.table("recommendation_events").insert({
        "recommendation_id": rec_id,
        "session_id": session_id,
        "customer_id": customer_id,
        "merchant_id": "merchant_mxx_001",
        "source_product_id": product_id,
        "recommended_product_id": r["product_id"],
        "recommendation_type": "CROSS_SELL",
        "agent_name": "Booster",
        "score": r["confidence"],
        "reason": r["reason"],
        "status": "GENERATED"   # NOT "SHOWN" — that happens when frontend displays it
    }).execute()
    rec_ids.append(rec_id)
```

Recommendation lifecycle:
```
GENERATED → SHOWN → CLICKED → ACCEPTED → CONVERTED (or DISMISSED at any stage)
```

Strict lifecycle rules:
- `GENERATED`: Tool returned the recommendation. This is NOT the same as showing it.
- `SHOWN`: Only when the recommendation is actually surfaced to the user/AI buyer (frontend or agent response confirms display).
- `CLICKED`: User interacted with the recommendation.
- `ACCEPTED`: User explicitly chose the recommended product.
- `CONVERTED`: **Only** when the resulting order **actually contains the recommended product** AND **payment is verified** (CAPTURED/SUCCESS). Both conditions must be true.
- `DISMISSED`: User saw it but did not act on it.

#### [NEW] Recommendation status update endpoints in routes

```python
@router.post("/recommendations/{rec_id}/shown")
@router.post("/recommendations/{rec_id}/clicked")
@router.post("/recommendations/{rec_id}/accepted")
@router.post("/recommendations/{rec_id}/dismissed")
```

---

### P1.2 — Revenue Attribution

When a purchase completes, check if the resulting order actually contains the recommended product AND payment is verified:

```python
# In webhook handler or payment success flow:
# 1. Get order items for this order
order_items = supabase.table("order_items") \
    .select("product_id").eq("order_id", local_order_id).execute()
purchased_product_ids = {oi["product_id"] for oi in order_items.data}

# 2. Only mark CONVERTED for recommendations whose product is actually in the order
accepted_recos = supabase.table("recommendation_events") \
    .select("recommendation_id, recommended_product_id") \
    .eq("session_id", session_id) \
    .eq("status", "ACCEPTED").execute()

for reco in accepted_recos.data:
    if reco["recommended_product_id"] in purchased_product_ids:
        supabase.table("recommendation_events").update({
            "resulting_order_id": local_order_id,
            "revenue_paise": amount_for_product,  # from order_items, not order total
            "status": "CONVERTED"
        }).eq("recommendation_id", reco["recommendation_id"]).execute()
```

Track:
- `recommendation_associated_revenue` — revenue from orders where a recommendation was shown
- `AI_assisted_revenue` — revenue from AI_AGENT sourced orders
- `AI_attributed_revenue` — revenue from orders where the specific recommended product was purchased

**Never** call it "incremental" or "causal" revenue.

---

### P1.3 — Entity Mapping

Lightweight mapping layer in `entity_mapping` table:

| synthetic_id | entity_type | razorpay_id |
|---|---|---|
| `prod_0001` | `item` | `item_NzGkXYZ` |
| `ord_abc123` | `order` | `order_RzpDef` |
| `ord_abc123` | `payment` | `pay_RzpGhi` |
| `ord_abc123` | `payment_link` | `plink_RzpJkl` |
| `rfnd_xyz` | `refund` | `rfnd_RzpMno` |

Do NOT duplicate entire Razorpay objects. Store only IDs.

---

### P1.4 — Validation Hardening

#### [MODIFY] [tools.py](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py)

- `search_catalog`: Validate query non-empty, max 200 chars
- `get_product_details`: Validate product_id format
- `create_razorpay_order`: Validate all IDs, amount > 0, email format

#### [MODIFY] [chat.py](file:///c:/building%20projs/razorpay_proj/backend/routes/chat.py)

- `message`: Non-empty, max 2000 chars
- `conversation_id`: Valid UUID when provided
- Graceful error response wrapping MAXX invocation

---

## Data Pipeline Fixes

These fix the synthetic data generator and pipeline scripts. Changes apply to files in [`dataset/scripts/`](file:///c:/building%20projs/razorpay_proj/dataset/scripts).

---

### Pipeline Fix 1 — RetailRocket Hashed Properties

#### [MODIFY] [transform_retailrocket.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/transform_retailrocket.py)

Current `process_item_properties()` only keeps `categoryid`, `available`, property `790`, and property `888`. Per item 4:

- Inspect all hashed properties
- Identify non-constant properties with enough variance to be useful for clustering/similarity
- Preserve useful anonymous features (as `feature_XXX` columns) for item similarity graphs
- Discard genuinely useless (constant) properties
- Never expose raw hashes in UI or claim semantic meaning

```python
def process_item_properties():
    # ... existing streaming logic ...
    # NEW: track property value distributions
    property_value_counts = defaultdict(Counter)
    for row in reader:
        property_value_counts[row['property']][row['value']] += 1

    # Identify useful properties: non-constant, enough distinct values
    useful_props = {}
    for prop, values in property_value_counts.items():
        if len(values) > 1 and len(values) < 10000:  # not constant, not unique per item
            useful_props[prop] = {"distinct_values": len(values), "total": sum(values.values())}

    # Save useful anonymous features alongside known ones
    ...
```

---

### Pipeline Fix 2 — Funnel Calibration from Real Data

#### [MODIFY] [generate_synthetic_data.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/generate_synthetic_data.py)

Do NOT hardcode `60% views, 25% cart, 8% purchase`. Instead:

```python
patterns = load_patterns()
rr_funnel = patterns.get('rr_funnel_rates.json', {})
rr_sessions = patterns.get('rr_session_patterns.json', {})

# Use actual RetailRocket distributions
view_to_cart_rate = rr_funnel.get('view_cart', 0.025) + rr_funnel.get('view_cart_buy', 0.008)
cart_to_purchase_rate = rr_funnel.get('view_cart_buy', 0.008) / max(view_to_cart_rate, 0.001)

# Diverse behavioral types (calibrated from session patterns)
BEHAVIORAL_TYPES = {
    "browser":           {"view_prob": 1.0, "cart_prob": 0.05, "buy_prob": 0.01, "sessions": (3, 10)},
    "high_intent_buyer": {"view_prob": 1.0, "cart_prob": 0.8,  "buy_prob": 0.7,  "sessions": (1, 3)},
    "repeat_visitor":    {"view_prob": 1.0, "cart_prob": 0.3,  "buy_prob": 0.15, "sessions": (5, 15)},
    "cart_abandoner":    {"view_prob": 1.0, "cart_prob": 0.7,  "buy_prob": 0.05, "sessions": (2, 6)},
    "one_session_buyer": {"view_prob": 1.0, "cart_prob": 0.9,  "buy_prob": 0.8,  "sessions": (1, 1)},
    "price_sensitive":   {"view_prob": 1.0, "cart_prob": 0.4,  "buy_prob": 0.1,  "sessions": (3, 8)},
}
```

---

### Pipeline Fix 3 — Transaction Basket Reconstruction

#### [MODIFY] [generate_synthetic_data.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/generate_synthetic_data.py)

Use co-purchase data from RetailRocket `transactionid` (already extracted in `rr_co_purchase.json`) to create realistic multi-item baskets:

```python
co_purchase = patterns.get('rr_co_purchase.json', {})

# When generating a multi-item basket, prefer items that co-occur
# Never assume one transaction event = one order
```

---

### Pipeline Fix 4 — Discount Accounting

#### [MODIFY] [generate_synthetic_data.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/generate_synthetic_data.py)

Single discount model — discount at **order level only**, not double-applied:

```python
# order_item.total_paise = quantity × unit_price_paise  (NO item-level discount)
# order.subtotal_paise = SUM(order_item.total_paise)
# order.discount_paise = order-level discount (from campaign, 0 if none)
# order.tax_paise = calculated tax
# order.total_paise = subtotal - discount + tax
```

---

### Pipeline Fix 5 — Payment Distribution Totals 100%

Already correct in current code (`PAYMENT_DIST` sums to 1.0). Verify:
- `CAPTURED ~88%, FAILED ~5%, AUTHORIZED ~3%, CREATED ~2%, UNKNOWN ~2%`
- REFUNDED is NOT an initial payment state — it's a subsequent action against eligible CAPTURED payments
- Refund rate: 2–8% of CAPTURED payments (current 5% is within range)

---

### Pipeline Fix 6 — Workflow-Driven Agent Audit

#### [MODIFY] [generate_synthetic_data.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/generate_synthetic_data.py)

Current audit generation is basic. Replace with workflow simulation:

```python
if source == "AI_AGENT":
    sess_id = generate_id("chat")
    intent_id = generate_id("intent")

    # Step 1: Scout search
    audit_events.append(audit_row("Scout", "SEARCH", "SUCCESS", ...))

    # Step 2: Booster recommendation (50% chance for multi-product baskets)
    if basket_size > 1 and random.random() < 0.5:
        audit_events.append(audit_row("Booster", "RECOMMEND", "SUCCESS", ...))
        recommendation_events.append(...)  # with proper lifecycle status

    # Step 3: Closer purchase intent
    audit_events.append(audit_row("Closer", "PURCHASE_INTENT", "SUCCESS",
                                  purchase_state="PURCHASE_PENDING", ...))

    # Step 4: Guardian validate
    guardian_status = "APPROVED" if p_status != "BLOCKED" else "BLOCKED"
    audit_events.append(audit_row("Guardian", "VALIDATE", guardian_status,
                                  user_confirmed=True, guardian_approved=(guardian_status=="APPROVED"),
                                  risk_score=0.0 if guardian_status=="APPROVED" else 0.8, ...))

    # Step 5: Razorpay result
    audit_events.append(audit_row("Closer", "PAYMENT_RESULT", p_status,
                                  razorpay_entity_id=rzp_pay_id, purchase_state=purchase_state, ...))

    # Step 6: Failure workflow
    if p_status == "FAILED":
        audit_events.append(audit_row("Guardian", "INSPECT_STATE", "SUCCESS",
                                      purchase_state="RECOVERY_PENDING", ...))
        audit_events.append(audit_row("Guardian", "BLOCK_BLIND_RETRY", "BLOCKED",
                                      failure_code="RULE_08", ...))
```

---

### Pipeline Fix 7 — Validation Script Exit Code

#### [MODIFY] [validate_data.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/validate_data.py)

```python
def validate():
    errors = []
    # ... all checks ...

    # Add: FK integrity, duplicate IDs, null checks, status validity,
    # negative quantities, orphan records, timestamp consistency,
    # Guardian BLOCK → no SUCCESS money action, CONVERTED reco → order exists, etc.

    if errors:
        print(f"FAILED with {len(errors)} errors:")
        for e in errors: print(f" - {e}")
        sys.exit(1)     # NON-ZERO exit code
    else:
        print("SUCCESS! All validations passed.")
        sys.exit(0)
```

---

### Pipeline Fix 8 — Indian Context

Already partially done in current code. Expand:

- **Cities**: Add Noida, Ahmedabad, Jaipur, Kolkata, Kochi, Chandigarh, Lucknow, Indore (+ corresponding states)
- **Categories**: Add "Health & Wellness", "Travel", "Pet Supplies" to existing list
- **Brands**: Keep synthetic Indian brands (UrbanPulse, TechVista, etc.)
- **Payment methods**: Already correct (UPI, CARD, NETBANKING, WALLET, EMI)

---

### Pipeline Fix 9 — Demo Fixtures

#### [NEW] [dataset/scripts/demo_fixtures.py](file:///c:/building%20projs/razorpay_proj/dataset/scripts/demo_fixtures.py)

Deterministic, documented test cases:

```python
DEMO_FIXTURES = [
    {
        "name": "Running Shoes Search",
        "scenario": "User searches 'running shoes under ₹3,000'",
        "product_id": "prod_0042",  # linked to a shoe product
        "expected": "Scout finds shoes, Booster recommends socks"
    },
    {
        "name": "Cross-sell: Shoes → Socks",
        "scenario": "Product affinity shows shoes→socks with confidence 0.85",
        "source_product": "prod_0042",
        "recommended_product": "prod_0089",
    },
    {
        "name": "Guardian Block — Over Limit",
        "scenario": "₹15,000 item exceeds ₹10,000 max transaction",
        "amount_paise": 1500000,
        "expected_rule": "RULE_01"
    },
    # ... failed payment, unknown payment, VIP churn-risk customer,
    #     converting recommendation, campaign opportunity
]
```

These are clearly labeled as demo fixtures, not historical data.

---

## Database Schema

#### [MODIFY] [db/schema.sql](file:///c:/building%20projs/razorpay_proj/backend/db/schema.sql)

Changes needed:

1. **Add `amount_paise`, `user_confirmed`, `guardian_approved` columns to `agent_audit`** (already partially present in synthetic generator but not in schema)
2. **Add `score` and `reason` columns to `recommendation_events`** (currently has `affinity_score` — rename to `score`, add `reason`)
3. **Add foreign keys** where practical (with `ON DELETE SET NULL` to avoid cascade issues with synthetic data):
   ```sql
   ALTER TABLE orders ADD CONSTRAINT fk_orders_customer
       FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL;
   ALTER TABLE order_items ADD CONSTRAINT fk_oi_order
       FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE;
   ALTER TABLE order_items ADD CONSTRAINT fk_oi_product
       FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE SET NULL;
   -- ... etc per item 32
   ```
4. **Ensure TIMESTAMPTZ** for all timestamp columns (already done in current schema)
5. **Ensure BIGINT** for all paise columns (already done)
6. **Add webhook_secret to config** for signature verification

---

## Summary of File Changes

| File | Action | Items Addressed |
|------|--------|----------------|
| [`maxx.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/maxx.py) | Major rewrite — AgentState, graph, state machine, routing | 1,4,8,16,17,27,28 |
| [`tools.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/tools.py) | Major rewrite — real DB queries, new Razorpay order tool, validation, attribution | 2,3,7,9,10,11,12,13,14,15,22,24,34 |
| [`closer.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/closer.py) | Remove override, use structured state | 5,17,18 |
| [`booster.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/booster.py) | Specific tools, eligibility filters | 13,14,28 |
| [`campaigner.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/campaigner.py) | Specific tools, real DB queries | 15,29 |
| [`constitutional.py`](file:///c:/building%20projs/razorpay_proj/backend/audit/constitutional.py) | Implement all 8 rules with real checks | 6,19,20,21,22 |
| [`guardian.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/guardian.py) | Updated signature with structured fields | 6,19 |
| [`ledger.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/ledger.py) | Extended audit fields | 9,30 |
| [`chat.py`](file:///c:/building%20projs/razorpay_proj/backend/routes/chat.py) | Validation, session/state passthrough | 34 |
| [`webhooks.py`](file:///c:/building%20projs/razorpay_proj/backend/routes/webhooks.py) | **[NEW]** Razorpay webhook handler | 25,26 |
| [`main.py`](file:///c:/building%20projs/razorpay_proj/backend/main.py) | Add webhook router | 25 |
| [`__init__.py`](file:///c:/building%20projs/razorpay_proj/backend/agents/__init__.py) | Updated exports | — |
| [`config.py`](file:///c:/building%20projs/razorpay_proj/backend/config.py) | Add RAZORPAY_WEBHOOK_SECRET | 25 |
| [`schema.sql`](file:///c:/building%20projs/razorpay_proj/backend/db/schema.sql) | FK constraints, new columns | 31,32,33 |
| [`generate_synthetic_data.py`](file:///c:/building%20projs/razorpay_proj/dataset/scripts/generate_synthetic_data.py) | Funnel calibration, baskets, discounts, audit workflows | 5,6,7,8,9,10,38 |
| [`transform_retailrocket.py`](file:///c:/building%20projs/razorpay_proj/dataset/scripts/transform_retailrocket.py) | Preserve useful hashed properties | 4 |
| [`validate_data.py`](file:///c:/building%20projs/razorpay_proj/dataset/scripts/validate_data.py) | Comprehensive validation, proper exit codes | 34,35 |
| [`demo_fixtures.py`](file:///c:/building%20projs/razorpay_proj/dataset/scripts/demo_fixtures.py) | **[NEW]** Controlled demo cases | 37 |

---

## Implementation Order

> [!IMPORTANT]
> Data pipeline correctness comes **before** agent integration. The agents need real data in Supabase to function. Without seeded `products`, `product_affinity`, and `customer_metrics`, Booster and Campaigner have nothing to query.

**Phase 0 — Data Foundation (do first):**
1. Schema migration (FK constraints, new columns in `agent_audit`, `recommendation_events`)
2. Data pipeline fixes (RetailRocket hashed properties, funnel calibration, basket reconstruction, discount accounting, payment distribution, workflow-driven audit, Indian context, validation exit codes)
3. Demo fixtures
4. Run pipeline: inspect → transform RR → transform Olist → optional UCI → generate synthetic → build affinity → build metrics → validate
5. Seed DB: `python seed_database.py`

**Phase 1 — Agent Infrastructure (after data is seeded):**
6. `AgentState` + purchase state machine in `maxx.py`
7. MAXX graph rewiring (Scout → Booster when appropriate → Closer)
8. Remove `user_confirmed=True` override — payment tools resolve auth from server-side state
9. Real Booster DB queries in `tools.py` + `booster.py`
10. Real Campaigner DB queries in `tools.py` + `campaigner.py`
11. Guardian RULE_01–08 in `constitutional.py` + `guardian.py`
12. Purchase state transitions enforced in router
13. `create_razorpay_order` tool + Razorpay Order flow (basket-total amounts)
14. Webhook handler (`webhooks.py`)
15. Failure/UNKNOWN recovery (new `purchase_intent_id` on retry)
16. Audit logging updates in `ledger.py`

**Phase 2 — Tracking & Attribution (after agents work):**
17. `recommendation_events` real lifecycle (GENERATED → SHOWN → CONVERTED)
18. Revenue attribution (CONVERTED only when order contains product + payment verified)
19. Entity mapping
20. Validation improvements (input validation in tools + chat)

---

## Verification Plan

### Automated
```bash
# 1. Pipeline + validation (run FIRST)
cd dataset/scripts && python run_pipeline.py
# Must exit 0. If validation fails, fix data before proceeding.

# 2. Seed DB
python seed_database.py

# 3. Syntax/import check
cd backend && python -c "from agents.maxx import maxx_app; print('Graph compiled:', list(maxx_app.get_graph().nodes))"

# 4. Guardian rules
python -c "
from audit.constitutional import evaluate_safety
# RULE_02: no confirmation
r = evaluate_safety({'user_confirmed': False}, 500000)
assert not r.passed, 'RULE_02 should block'
# RULE_06: wrong state
r = evaluate_safety({'user_confirmed': True, 'purchase_state': 'IDLE', 'action_type': 'create_razorpay_order'}, 500000)
assert not r.passed, 'RULE_06 should block'
print('Guardian rules verified')
"

# 5. Server starts
uvicorn main:app --port 8002
```

### Mandatory End-to-End Tests (must pass before declaring completion)

> [!CAUTION]
> Before declaring completion, run **one real happy-path Razorpay Test Mode transaction** and **one FAILED/UNKNOWN recovery scenario** end-to-end.

**Test 1 — Happy Path (Razorpay Test Mode):**
1. Search for a product (Scout)
2. Booster shows data-backed recommendation from `product_affinity`
3. User confirms purchase → `USER_CONFIRMED` in AgentState
4. Guardian validates → `GUARDIAN_APPROVED`
5. `create_razorpay_order` → **actual Razorpay Order created** (real `order_` ID)
6. Verify order status via Razorpay API or webhook
7. Local state updated to `PAYMENT_SUCCESS` / `COMPLETED`
8. `entity_mapping` has local→Razorpay mapping
9. `agent_audit` has full workflow trace
10. If recommendation was accepted and product in order, `recommendation_events` → `CONVERTED`

**Test 2 — Failure Recovery:**
1. Simulate or trigger a failed/unknown payment state
2. Verify `RECOVERY_PENDING` state is set
3. `check_payment_status` inspects actual Razorpay state
4. Attempt retry → verify new `purchase_intent_id` is generated
5. Verify old `purchase_intent_id` is not reusable (RULE_05)
6. Verify RULE_08 blocks blind retry without state inspection
7. All recovery steps logged to `agent_audit`

### Manual Verification Checklist
1. Product search → Scout returns results from Supabase `products`
2. Data-backed recommendation → Booster queries `product_affinity`
3. Confirmation block → unconfirmed purchase rejected (RULE_02)
4. Guardian approval → structured state `GUARDIAN_APPROVED`
5. Actual Razorpay test transaction → real `order_id` returned
6. Payment status verification → webhook or `check_payment_status`
7. Failed payment recovery → no blind retry (RULE_08), new intent required
8. Recommendation attribution → CONVERTED only when order contains product + payment verified
9. Campaign analysis → Campaigner queries real `customer_metrics`
10. Complete audit trail → `agent_audit` reflects full workflow causality
