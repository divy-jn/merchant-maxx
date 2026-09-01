import re
import uuid

from langchain_core.messages import SystemMessage, AIMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from .tools import PAYMENT_TOOLS

CHECKOUT_RE = re.compile(
    r"\b(?:complete|finish|finalize|place|submit|buy|purchase|pay|checkout|check\s*out|proceed)\b.*\b(?:order|purchase|payment|checkout|buy|pay)?\b",
    re.I,
)

closer_prompt = """You are MAXX, acting internally as the Closer.

Your job is to move an already-staged purchase through the safe checkout flow.
The application, not you, owns user confirmation and purchase authorization.

Rules:
- If purchase_state is PURCHASE_PENDING, ask for explicit confirmation and do not call any payment tool.
- If purchase_state is USER_CONFIRMED AND user_confirmed=True, and the user's latest message asks to buy, order, checkout, complete, pay, proceed, or place the order, the application will deterministically trigger create_razorpay_order. Do not refuse checkout and do not redirect the user to another store page.
- After create_razorpay_order succeeds, present the returned Razorpay Order ID and amount clearly so the application can render its secure Pay button. Never claim payment succeeded at this stage; the user must still complete Razorpay Checkout.
- If purchase_state is PAYMENT_PENDING and an existing Razorpay order is present, do not create another order. Return the existing order information and tell the user to continue payment.
- For FAILED/UNKNOWN, call check_payment_status when state inspection is needed. Never blindly retry.
- Never claim the user confirmed unless user_confirmed=True is present in state.
- Never invent a basket, amount, product, Razorpay ID, or payment result.
- Any modification to the basket after confirmation immediately invalidates the confirmation and requires a fresh user confirmation.
- A fresh purchase_intent_id and fresh confirmation are required for recovery.

Important: You are not authorizing the financial transaction yourself; you are safely initiating the server-side Razorpay order after authoritative confirmation so the application can open Checkout.
"""

def get_llm():
    return get_chat_model([Capability.TOOL_CALLING])

def closer_node(state: dict):
    messages = list(state.get("messages", []))
    latest_user = next((m for m in reversed(messages) if getattr(m, "type", None) == "human"), None)
    latest_text = str(latest_user.content) if latest_user is not None else ""

    # Deterministic checkout trigger: once authoritative state says the user has
    # confirmed the basket, explicit checkout language should never be turned
    # into a generic refusal by the model.
    if (
        state.get("purchase_state") == "USER_CONFIRMED"
        and state.get("user_confirmed") is True
        and CHECKOUT_RE.search(latest_text)
    ):
        tool_call = {
            "name": "create_razorpay_order",
            "args": {},
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "tool_call",
        }
        return {"messages": [AIMessage(content="", tool_calls=[tool_call])]}

    messages.insert(0, SystemMessage(content=closer_prompt))
    state_view = SystemMessage(content=(
        f"Authoritative purchase state={state.get('purchase_state', 'IDLE')}; "
        f"user_confirmed={state.get('user_confirmed', False)}; "
        f"purchase_intent_id={(state.get('purchase_context') or {}).get('purchase_intent_id', '')}."
    ))
    llm = get_llm().bind_tools(PAYMENT_TOOLS)
    response = llm.invoke([messages[0], state_view] + messages[1:])
    return {"messages": [response]}
