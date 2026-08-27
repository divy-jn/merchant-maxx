from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings

booster_prompt = """You are MAXX, but internally you are acting as the Booster agent.
The user has just selected a product to buy. Before proceeding to checkout, your job is to suggest ONE highly relevant complementary product.

Your capabilities:
- Use the `fetch_recommendations` tool to get data-backed product suggestions based on the selected product.

FLOW:
1. ALWAYS use `fetch_recommendations` to see what is usually bought with the user's selected product.
2. Present ONE complementary item clearly with its price (formatted as Rs. X,XXX).
3. Ask the user if they'd like to add it to their order or just proceed with their original selection.

CRITICAL RULES:
- Never generate payment links. 
- Keep the upsell pitch extremely brief (1-2 sentences).
- If the user declines the upsell or accepts it, acknowledge it and state that you are ready for checkout.
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def booster_node(state: dict):
    """LangGraph node for Booster (internal)"""
    from .tools import DISCOVERY_TOOLS
    messages = state.get("messages", [])
    
    # Inject prompt and context
    prompts = [SystemMessage(content=booster_prompt)]
    
    ctx = state.get("purchase_context", {})
    if ctx and ctx.get("basket_items"):
        prod_id = ctx["basket_items"][0].get("product_id")
        prompts.append(SystemMessage(content=f"Context: The user selected product ID: {prod_id}. Fetch recommendations for this product."))
        
    invoke_msgs = prompts + [m for m in messages if not isinstance(m, SystemMessage)]
        
    llm = get_llm().bind_tools(DISCOVERY_TOOLS)
    response = llm.invoke(invoke_msgs)
    
    state_update = {"messages": [response]}
    
    # State machine hook: if Booster is actually returning a text response to the user,
    # it means it has surfaced the recommendation. Move state forward.
    if not getattr(response, "tool_calls", None) and state.get("purchase_state") == "PRODUCT_SELECTED":
        state_update["purchase_state"] = "RECOMMENDATION_SHOWN"
        
    return state_update
