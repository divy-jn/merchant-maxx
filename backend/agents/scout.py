from langchain_core.messages import SystemMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from config import settings
from .tools import SCOUT_TOOLS
import uuid

scout_prompt = """You are MAXX, the AI shopping assistant for Merchant Maxx.
Help customers discover products and build a purchase intent.

Rules:
1. Discovery: Use search_catalog and get_product_details to find products. If asked to compare, retrieve multiple products and compare them.
2. Selection & Quantity: If the user explicitly chooses a product (e.g. "I'll take the Lenovo one", "Give me two of those"), call stage_purchase_intent with the exact product_id and the requested quantity (default 1).
3. Ambiguity: If the user says "I'll buy it" but multiple products were discussed, DO NOT guess. Ask "Which one would you like?".
4. Confirmation Safety: Do not mistake casual interest ("looks good", "nice") for a purchase decision. Only stage intent when the user explicitly expresses intent to buy.
5. Never authorize payment, and never generate payment links. Keep responses concise and friendly.
"""

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])


def scout_node(state: dict):
    """Discovery only. Staging is persisted, but it never authorizes payment."""
    import time
    state_update = {"scout_start": time.time()}
    messages = list(state.get("messages", []))
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=scout_prompt))
    response = get_llm().bind_tools(SCOUT_TOOLS).invoke(messages)
    state_update["messages"] = [response]

    for tc in getattr(response, "tool_calls", []) or []:
        if tc["name"] != "stage_purchase_intent":
            continue
        product_id = tc["args"].get("product_id")
        if not product_id:
            continue
        # Never trust the model for the authoritative price.
        from utils.supabase_client import supabase
        product = None
        if supabase:
            try:
                result = (supabase.table("products").select("product_id,price_paise,active,inventory_qty")
                          .eq("product_id", product_id).eq("merchant_id", "merchant_mxx_001")
                          .maybe_single().execute())
                product = getattr(result, "data", None) if result else None
            except Exception as e:
                print(f"Error fetching product {product_id}: {e}")
                product = None
        quantity = int(tc["args"].get("quantity", 1))
        if quantity < 1:
            quantity = 1

        if not product or not product.get("active") or (product.get("inventory_qty") or 0) < quantity:
            continue
        intent_id = f"pi_{uuid.uuid4().hex[:12]}"
        
        # Server-side authoritative amount calculation
        unit_price = int(product["price_paise"])
        amount = unit_price * quantity
        
        ctx = {
            "purchase_intent_id": intent_id,
            "basket_items": [{"product_id": product_id, "quantity": quantity}],
            "amount_paise": amount,
            "intent_description": f"Purchase intent for {quantity}x {product_id}"
        }
        if supabase:
            supabase.table("purchase_intents").insert({
                "purchase_intent_id": intent_id,
                "conversation_id": state.get("session_id"),
                "customer_id": state.get("customer_id"),
                "merchant_id": "merchant_mxx_001",
                "purchase_state": "PRODUCT_SELECTED",
                "basket": ctx["basket_items"],
                "subtotal_paise": amount,
                "discount_paise": 0,
                "tax_paise": 0,
                "amount_paise": amount,
                "user_confirmed": False
            }).execute()
        state_update["scout_result"] = {
            "intent_staged": True,
            "product_context": ctx
        }
        break
    state_update["scout_end"] = time.time()
    return state_update
