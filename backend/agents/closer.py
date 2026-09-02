import re
import uuid

from langchain_core.messages import SystemMessage, AIMessage
from llm.factory import get_chat_model
from llm.registry import Capability
from .tools import PAYMENT_TOOLS

CHECKOUT_RE = re.compile(
    r"\b(?:complete|finish|finalize|place|submit|buy|purchase|pay|checkout|check\s*out|proceed)\b.*\b(?:order|purchase|payment|checkout|buy|pay|it)?\b",
    re.I,
)

closer_prompt = """You are MAXX, acting internally as the Closer.

Your job is to move an already-staged purchase through the safe checkout flow.
The application, not you, owns user confirmation and purchase authorization.

Rules:
- If purchase_state is PURCHASE_PENDING, ask for explicit confirmation and do not call any payment tool.
- If purchase_state is USER_CONFIRMED AND user_confirmed=True, and the user's latest message asks to buy, order, checkout, complete, pay, proceed, or place the order, YOU MUST use the create_razorpay_order tool. Do not refuse checkout, do not say you cannot process payments, and do not redirect the user to a store page. Just run the tool.
- After create_razorpay_order succeeds, return the returned Razorpay Order ID and amount clearly so the application can render its secure Pay button. Never claim payment succeeded at this stage.
- If purchase_state is PAYMENT_PENDING and an existing Razorpay order is present, do not create another order. Return the existing order information and tell the user to continue payment.
- For FAILED/UNKNOWN, call check_payment_status when state inspection is needed. Never blindly retry.
- Never claim the user confirmed unless user_confirmed=True is present in state.
- Never invent a basket, amount, product, Razorpay ID, or payment result.
- Any modification to the basket after confirmation immediately invalidates the confirmation and requires a fresh user confirmation.
- A fresh purchase_intent_id and fresh confirmation are required for recovery.

Important: You are not authorizing the financial transaction yourself; you are safely initiating the server-side Razorpay order after authoritative confirmation so the application can open Checkout.

Examples:
User: "payment?"
(State says USER_CONFIRMED=False, PURCHASE_PENDING)
MAXX: "Please confirm your intent to purchase the items in your cart before we proceed to payment."

User: "checkout"
(State says USER_CONFIRMED=True)
MAXX: (calls create_razorpay_order) "I've created your secure order. Please click the Pay button to complete checkout."

User: "payment?"
(State says PAYMENT_PENDING)
MAXX: "Your order is ready. Please continue to the payment gateway to finalize your purchase."
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
    from langchain_core.messages import merge_message_runs, HumanMessage
    messages_to_invoke = merge_message_runs([messages[0], state_view] + messages[1:])
    
    # Originally added because Gemini throws 400 Bad Request "Requests ending with a model turn are not supported" 
    # if the history ends with an AIMessage.
    # Since scout/booster outputs are AIMessages, closer will frequently encounter this.
    # We keep this safeguard for when LLM_PROVIDER=gemini is active.
    
    # Pre-process messages to flatten any complex list content in AIMessages into strings
    # This ensures compatibility with the Gemini API wrappers during _transform_messages
    for m in messages_to_invoke:
        if isinstance(m, AIMessage) and isinstance(m.content, list):
            m.content = "".join(str(b.get("text", "")) for b in m.content if isinstance(b, dict))

    if messages_to_invoke and getattr(messages_to_invoke[-1], "type", "") == "ai":
        messages_to_invoke.append(HumanMessage(content="Please provide the final response to the user based on the above internal thoughts."))
        
    response = llm.invoke(messages_to_invoke)
    if isinstance(getattr(response, "content", None), list):
        response.content = "".join(str(b.get("text", "")) for b in response.content if isinstance(b, dict))
    return {"messages": [response]}
