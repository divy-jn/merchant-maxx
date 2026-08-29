from langchain_core.messages import SystemMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from config import settings
from .tools import BOOSTER_TOOLS

booster_prompt = """You are MAXX, acting as the Booster agent.
Give at most ONE highly relevant complementary recommendation.
The relationship must come from the recommendation tool; never invent it.
Use customer history only to personalize why the recommendation may fit.
Do not authorize, create, or imply payment.
"""

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])

def booster_node(state: dict):
    messages = list(state.get("messages", []))
    context = state.get("purchase_context") or {}
    customer_id = state.get("customer_id")
    prompts = [SystemMessage(content=booster_prompt)]
    if context.get("basket_items"):
        prompts.append(SystemMessage(content=f"Selected product: {context['basket_items'][0].get('product_id')}"))
    if customer_id:
        try:
            from services.customer_context import get_customer_context
            customer = get_customer_context(customer_id)
            prompts.append(SystemMessage(content=f"Customer context (use only for personalization): {customer}"))
        except Exception:
            pass
    response = get_llm().bind_tools(BOOSTER_TOOLS).invoke(prompts + messages)
    state_update = {"messages": [response]}
    if not getattr(response, "tool_calls", None) and state.get("purchase_state") == "PRODUCT_SELECTED":
        state_update["purchase_state"] = "RECOMMENDATION_SHOWN"
    return state_update
