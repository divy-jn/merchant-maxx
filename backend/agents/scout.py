import logging
import re
from langchain_core.messages import SystemMessage, ToolMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from config import settings
from .tools import SCOUT_TOOLS
import uuid

logger = logging.getLogger(__name__)

scout_prompt = """You are MAXX, a highly capable and natural human-like sales representative for Merchant Maxx.
Help customers discover products and build a purchase intent organically.

CRITICAL BEHAVIOR RULES:
1. Be Natural: Act like a real sales representative, NOT a questionnaire or form. Sound warm, concise, and commercially useful.
2. Broad category requests: If the customer names a category but gives no preferences (for example, "recommend a mouse" or "show me keyboards"), give a SHORT shortlist of 2-3 genuinely relevant products from the search results, then ask at most 1-2 useful questions to refine the choice. For example, ask use case (gaming/work/everyday) and budget. Do not dump the entire search result.
3. Gift requests: If the customer says they want a gift but gives little context (for example, "something for my brother"), do NOT immediately dump generic catalog items. Ask naturally for the two most useful missing details, usually budget and what the recipient is into / the occasion. You may mention 1-2 broad examples only when they are genuinely plausible, but do not pretend they are personalized without enough information.
4. Context matters: Adapt the questions to the request. Gifts -> recipient interests/occasion + budget. Fashion -> occasion/style + budget. Shoes -> use case/occasion + budget. Electronics -> use case + important preference such as platform, size, or budget. Never ask a fixed questionnaire.
5. Minimal Clarification: Ask no more than 2 questions in one response. Once the customer answers, use that context in the next search/recommendation instead of asking the same questions again. If enough context is already available, stop asking and recommend.
6. Discovery: Use `search_catalog` and `get_product_details` to find products. For broad searches, treat tool results as candidates, not as text to copy. Select the 2-3 best matches for the customer's stated needs. Do not present every result.
7. Presentation: NEVER expose internal product IDs (e.g. item_...), database IDs, vector IDs, recommendation IDs, scores, or internal tool names to the customer. Never copy the tool's raw output verbatim. Use clean Markdown and customer-facing product names, prices, and concise useful descriptions.
8. Selection: If the user chooses a product, call `stage_purchase_intent` with the exact product_id. If multiple products were discussed and the choice is ambiguous, ask which one they mean naturally.
9. State Consistency: Do not contradict the "Current Cart" provided in the system prompt. Never authorize payment, generate payment links, or hallucinate a completed order.
10. No IDs in prose: Product IDs are implementation details used only for tool calls. They must never appear in your final response, even if a tool returned them.

Examples:
User: "Recommend me a mouse."
MAXX: (calls search_catalog) "A few good options:
- **Ergonomic Wireless Mouse** — a comfortable choice for everyday work.
- **Gaming Mouse** — better if you're after gaming performance.
What will you mainly use it for, and roughly what budget do you have in mind?"

User: "I want something to gift my brother."
MAXX: "Absolutely — I can make this much more personal. What's your rough budget, and what is he into (gaming, tech, fitness, music, etc.)?"

User: "I'm looking for shoes."
MAXX: "Sure — are they mainly for everyday/casual wear, work, sports, or a particular occasion? And what budget would you like me to stay around?"

User: "I'll take the ergonomic one."
MAXX: (calls stage_purchase_intent) "Great choice! I've added the Ergonomic Wireless Mouse to your cart. We can proceed to checkout whenever you're ready."
"""

MAX_QUANTITY = 99  # Sane upper bound

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])


def _extract_product_ids_from_history(messages: list) -> set:
    """Scan ToolMessage results for product IDs that were actually shown to the user.
    Returns the set of product IDs found in search_catalog / get_product_details results."""
    ids = set()
    id_pattern = re.compile(r"(?:ID:\s*|Product ID:\s*)(item_\w+)", re.IGNORECASE)
    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = str(getattr(msg, "content", ""))
            ids.update(id_pattern.findall(content))
    return ids


def _sanitize_customer_response(text: str) -> str:
    """Remove implementation-only identifiers from text before it reaches the customer."""
    text = re.sub(r"\s*\(?(?:ID|Product ID|Rec ID)\s*:\s*item_[A-Za-z0-9_-]+\)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bitem_[A-Za-z0-9_-]+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\brec_[A-Za-z0-9_-]+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def scout_node(state: dict):
    """Discovery only. Staging is persisted, but it never authorizes payment."""
    import time
    state_update = {"scout_start": time.time()}
    messages = list(state.get("messages", []))
    
    ctx = state.get("purchase_context", {})
    basket = ctx.get("basket_items", [])
    basket_str = "Current Cart: " + ", ".join([f"{item.get('quantity', 1)}x {item['product_id']}" for item in basket]) if basket else "Current Cart: Empty"
    
    sys_msg = scout_prompt + "\n\n" + basket_str
    
    if not messages or not getattr(messages[0], "content", "").startswith("You are MAXX"):
        messages.insert(0, SystemMessage(content=sys_msg))
    else:
        messages[0] = SystemMessage(content=sys_msg)
        
    from langchain_core.messages import merge_message_runs
    messages_to_invoke = merge_message_runs(messages)
    response = get_llm().bind_tools(SCOUT_TOOLS).invoke(messages_to_invoke)
    if isinstance(getattr(response, "content", None), list):
        response.content = "".join(str(b.get("text", "")) for b in response.content if isinstance(b, dict))
    if isinstance(getattr(response, "content", None), str):
        response.content = _sanitize_customer_response(response.content)
    state_update["messages"] = [response]

    existing_ctx = state.get("purchase_context") or {}
    intent_id = existing_ctx.get("purchase_intent_id")
    basket_items = list(existing_ctx.get("basket_items") or [])

    for tc in getattr(response, "tool_calls", []) or []:
        if tc["name"] != "stage_purchase_intent":
            continue
        product_id = tc["args"].get("product_id")
        if not product_id:
            continue

        # ── Deterministic guard: product must have appeared in prior tool results ──
        known_ids = _extract_product_ids_from_history(messages)
        if known_ids and product_id not in known_ids:
            logger.warning("Scout tried to stage product %s not found in conversation history %s — blocking",
                           product_id, known_ids)
            continue
            
        # ── Quantity validation ──
        try:
            quantity = int(tc["args"].get("quantity", 1))
        except (ValueError, TypeError):
            quantity = 1
            
        if quantity < 0:
            logger.warning("Scout invalid negative quantity — ignoring")
            continue
        elif quantity > MAX_QUANTITY:
            quantity = MAX_QUANTITY

        existing_item_idx = next((i for i, item in enumerate(basket_items) if item.get("product_id") == product_id), -1)

        from utils.supabase_client import supabase
        if quantity == 0:
            if existing_item_idx == -1:
                logger.warning("Scout tried to remove product %s not in basket — ignoring", product_id)
                continue
            basket_items.pop(existing_item_idx)
        else:
            product = None
            if supabase:
                try:
                    result = (supabase.table("products").select("product_id,price_paise,active,inventory_qty")
                              .eq("product_id", product_id).eq("merchant_id", "merchant_mxx_001").maybe_single().execute())
                    product = getattr(result, "data", None) if result else None
                except Exception as e:
                    logger.error("Error fetching product %s: %s", product_id, e)

            if not product or not product.get("active") or (product.get("inventory_qty") or 0) < quantity:
                logger.warning("Scout invalid quantity/product %s — ignoring", product_id)
                continue
                
            if existing_item_idx != -1:
                basket_items[existing_item_idx]["quantity"] = quantity
            else:
                basket_items.append({"product_id": product_id, "quantity": quantity})

        if not intent_id:
            intent_id = f"pi_{uuid.uuid4().hex[:12]}"
            
        # ── Server-side authoritative amount calculation ──
        total_amount = 0
        valid_basket = []
        if supabase:
            for item in basket_items:
                try:
                    p_res = supabase.table("products").select("product_id,price_paise,active").eq("product_id", item["product_id"]).eq("merchant_id", "merchant_mxx_001").maybe_single().execute()
                    p_data = getattr(p_res, "data", None) if p_res is not None else None
                    if p_data and p_data.get("active"):
                        qty = int(item["quantity"])
                        total_amount += int(p_data["price_paise"]) * qty
                        valid_basket.append({"product_id": item["product_id"], "quantity": qty})
                except Exception as e:
                    logger.error("Error recalculating product %s: %s", item["product_id"], e)
            basket_items = valid_basket

        ctx = {
            "purchase_intent_id": intent_id,
            "basket_items": basket_items,
            "amount_paise": total_amount,
            "intent_description": f"Purchase intent for {sum(item['quantity'] for item in basket_items)} items"
        }
        
        if supabase:
            try:
                mutation_success = False
                if existing_ctx.get("purchase_intent_id"):
                    # ── Atomic conditional update ──
                    # Fails safely (updates 0 rows) if intent is locked by order creation.
                    res = supabase.table("purchase_intents").update({
                        "basket": ctx["basket_items"],
                        "amount_paise": total_amount,
                        "purchase_state": "PRODUCT_SELECTED" if basket_items else "IDLE",
                        "user_confirmed": False,
                        "confirmed_basket": None,
                        "confirmed_amount_paise": None,
                        "confirmation_timestamp": None
                    }).eq("purchase_intent_id", intent_id).is_("razorpay_order_id", "null").in_("purchase_state", ["IDLE", "PRODUCT_SELECTED", "RECOMMENDATION_SHOWN", "PURCHASE_PENDING", "USER_CONFIRMED", "PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"]).execute()
                    
                    if res and res.data and len(res.data) == 1:
                        mutation_success = True

                if not mutation_success:
                    new_intent_id = f"pi_{uuid.uuid4().hex[:12]}"
                    intent_id = new_intent_id
                    ctx["purchase_intent_id"] = intent_id
                    
                    supabase.table("purchase_intents").insert({
                        "purchase_intent_id": intent_id,
                        "conversation_id": state.get("session_id"),
                        "customer_id": state.get("customer_id"),
                        "merchant_id": "merchant_mxx_001",
                        "purchase_state": "PRODUCT_SELECTED" if basket_items else "IDLE",
                        "basket": ctx["basket_items"],
                        "amount_paise": total_amount,
                        "user_confirmed": False
                    }).execute()
            except Exception as e:
                logger.error("Failed to persist purchase intent: %s", e)
                # Rollback: don't mutate the agent's context if DB persistence fails
                continue

        state_update["scout_result"] = {
            "intent_staged": True,
            "product_context": ctx
        }
        existing_ctx = ctx
    state_update["scout_end"] = time.time()
    return state_update
