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
    import time
    booster_start = time.time()
    
    messages = list(state.get("messages", []))
    context = state.get("purchase_context") or {}
    
    if not context or not context.get("basket_items"):
        return {
            "booster_start": booster_start,
            "booster_end": time.time(),
            "booster_result": {"status": "skipped", "reason": "missing_context"}
        }

    customer_id = state.get("customer_id")
    prompts = [SystemMessage(content=booster_prompt)]
    if context.get("basket_items"):
        selected_ids = [item.get("product_id") for item in context["basket_items"]]
        prompts.append(SystemMessage(content=f"Selected products: {', '.join(selected_ids)}"))
    if customer_id:
        try:
            from services.customer_context import get_customer_context
            customer = get_customer_context(customer_id)
            prompts.append(SystemMessage(content=f"Customer context (use only for personalization): {customer}"))
        except Exception:
            pass
    try:
        from langchain_core.messages import merge_message_runs
        messages_to_invoke = merge_message_runs(prompts + messages)
        response = get_llm().bind_tools(BOOSTER_TOOLS).invoke(messages_to_invoke)
        if isinstance(getattr(response, "content", None), list):
            response.content = "".join(str(b.get("text", "")) for b in response.content if isinstance(b, dict))
        state_update = {"messages": [response], "booster_start": booster_start, "booster_result": {"status": "success"}}
        
        if not getattr(response, "tool_calls", None) and state.get("purchase_state") == "PRODUCT_SELECTED":
            # Check if recommendations were actually fetched
            has_rec = any("Data-backed recommendations:" in str(m.content) for m in messages if getattr(m, "name", None) == "fetch_recommendations")
            state_update["booster_result"]["recommendations_shown"] = has_rec
        
        state_update["booster_end"] = time.time()
        return state_update
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Booster failure: {e}")
        return {
            "booster_start": booster_start,
            "booster_end": time.time(),
            "booster_result": {"status": "unavailable"}
        }
