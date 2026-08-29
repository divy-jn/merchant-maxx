from langchain_core.messages import SystemMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from config import settings
from .tools import PAYMENT_TOOLS

closer_prompt = """You are MAXX, acting internally as the Closer.

Your job is to move an already-staged purchase through the safe checkout flow.
The application, not you, owns user confirmation and purchase authorization.

Rules:
- If purchase_state is PURCHASE_PENDING, ask for explicit confirmation and do not call any payment tool.
- If purchase_state is USER_CONFIRMED, the application may allow Guardian validation and order creation.
- Never claim the user confirmed unless user_confirmed=True is present in state.
- Never invent a basket, amount, product, Razorpay ID, or payment result.
- For FAILED/UNKNOWN, call check_payment_status when state inspection is needed. Never blindly retry.
- A fresh purchase_intent_id and fresh confirmation are required for recovery.
"""

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])

def closer_node(state: dict):
    messages = list(state.get("messages", []))
    messages.insert(0, SystemMessage(content=closer_prompt))
    state_view = SystemMessage(content=(
        f"Authoritative purchase state={state.get('purchase_state', 'IDLE')}; "
        f"user_confirmed={state.get('user_confirmed', False)}; "
        f"purchase_intent_id={(state.get('purchase_context') or {}).get('purchase_intent_id', '')}."
    ))
    llm = get_llm().bind_tools(PAYMENT_TOOLS)
    response = llm.invoke([messages[0], state_view] + messages[1:])
    return {"messages": [response]}
