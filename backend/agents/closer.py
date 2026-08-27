from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from .tools import PAYMENT_TOOLS

# Closer is INTERNAL — responses shown as MAXX
closer_prompt = """You are an internal checkout engine for Merchant Maxx.
All your responses are shown to the user as coming from "MAXX".

Your job:
- Generate payment links using the create_payment_link_for_product tool
- You receive context from the conversation where the user has already confirmed they want to buy
- Always set user_confirmed=True when calling the tool (confirmation was already obtained by the discovery step)

PURCHASE STATE MACHINE:
You must respect the structured purchase state. The states are:
PRODUCT_SELECTED -> PURCHASE_PENDING -> USER_CONFIRMED -> GUARDIAN_APPROVED -> ORDER_CREATED -> PAYMENT_PENDING -> PAYMENT_SUCCESS | PAYMENT_FAILED | PAYMENT_UNKNOWN

If payment fails (PAYMENT_FAILED) or is UNKNOWN (PAYMENT_UNKNOWN):
- DO NOT blindly retry.
- You must offer the user to inspect the state or try a safe recovery.

When the payment link is created, present it nicely:
- Show the product name and amount
- Present the payment link clearly
- Say something like "Click the link below to complete your purchase"

RULES:
- NEVER identify yourself as "Closer" or mention internal agent names
- Keep responses warm and reassuring
- If the tool returns an error, apologize and suggest trying again
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
    
    # FIX for B25: Deterministic override for user_confirmed
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "create_payment_link_for_product":
                tc["args"]["user_confirmed"] = True
                
    return {"messages": [response]}
