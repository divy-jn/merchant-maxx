from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import PAYMENT_TOOLS

# Closer is INTERNAL — responses shown as MAXX
closer_prompt = """You are MAXX, but internally you are acting as the Closer agent.
Your job is to finalize the checkout process.

FLOW:
1. You are called when the user has selected a product and possibly seen an upsell.
2. If the user hasn't confirmed yet, explicitly ask: "Would you like me to generate an order for you to complete the purchase?"
3. Once the user replies "yes", "sure", or "go ahead", you MUST call the `confirm_and_pay` tool to signal their confirmation.
4. After confirmation is staged, call the `create_razorpay_order` tool to generate the actual Razorpay order.

IF PAYMENT FAILED / UNKNOWN:
- If the user wants to retry a failed payment, you MUST call the `reset_purchase_intent` tool first.
- Only after `reset_purchase_intent` succeeds can you call `create_razorpay_order` again.

CRITICAL RULES:
- NEVER call `create_razorpay_order` directly if `confirm_and_pay` hasn't been called.
- The `create_razorpay_order` tool will automatically use the staged product.
- Keep responses warm and reassuring.
"""

def get_llm():
    return ChatGoogleGenerativeAI(model=settings.LLM_MODEL, google_api_key=settings.LLM_API_KEY)

def closer_node(state: dict):
    """LangGraph node for Closer (internal — user sees MAXX)"""
    messages = state.get("messages", [])
    if not messages:
        messages = [SystemMessage(content=closer_prompt)]
    elif not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=closer_prompt))
        
    llm = get_llm().bind_tools(PAYMENT_TOOLS)
    response = llm.invoke(messages)
    
    # Intercept tool calls to update state securely
    state_update = {"messages": [response]}
    
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "confirm_and_pay":
                state_update["user_confirmed"] = True
                state_update["purchase_state"] = "USER_CONFIRMED"
            elif tc["name"] == "create_razorpay_order":
                state_update["purchase_state"] = "ORDER_CREATED"
            elif tc["name"] == "reset_purchase_intent":
                import uuid
                ctx = state.get("purchase_context", {})
                if ctx:
                    ctx["purchase_intent_id"] = f"pi_{uuid.uuid4().hex[:8]}"
                    state_update["purchase_context"] = ctx
                state_update["purchase_state"] = "USER_CONFIRMED"
                
    return state_update
