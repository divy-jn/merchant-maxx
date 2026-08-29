from langchain_core.messages import SystemMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from config import settings
from .tools import SCOUT_TOOLS
import uuid

scout_prompt = """You are MAXX, the AI shopping assistant for Merchant Maxx.
Help customers discover products and build a purchase intent.

Use search_catalog and get_product_details for discovery. If the user explicitly chooses a product,
call stage_purchase_intent with the exact product_id and the displayed price in paise. Never authorize payment.
Do not generate payment links. Keep responses concise and friendly.
"""

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])


def scout_node(state: dict):
    """Discovery only. Staging is persisted, but it never authorizes payment."""
    messages = list(state.get("messages", []))
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=scout_prompt))
    response = get_llm().bind_tools(SCOUT_TOOLS).invoke(messages)
    state_update = {"messages": [response]}

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
        if not product or not product.get("active") or (product.get("inventory_qty") or 0) < 1:
            continue
        intent_id = f"pi_{uuid.uuid4().hex[:12]}"
        amount = int(product["price_paise"])
        ctx = {
            "purchase_intent_id": intent_id,
            "basket_items": [{"product_id": product_id, "quantity": 1}],
            "amount_paise": amount,
            "intent_description": f"Purchase intent for {product_id}"
        }
        if supabase:
            supabase.table("purchase_intents").insert({
                "purchase_intent_id": intent_id,
                "conversation_id": state.get("session_id"),
                "customer_id": state.get("customer_id"),
                "merchant_id": "merchant_mxx_001",
                "purchase_state": "PURCHASE_PENDING",
                "basket": ctx["basket_items"],
                "subtotal_paise": amount,
                "discount_paise": 0,
                "tax_paise": 0,
                "amount_paise": amount,
                "user_confirmed": False
            }).execute()
        state_update["purchase_state"] = "PURCHASE_PENDING"
        state_update["purchase_context"] = ctx
        state_update["user_confirmed"] = False
        break
    return state_update
