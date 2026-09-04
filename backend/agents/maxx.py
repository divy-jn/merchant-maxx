from typing import TypedDict, Sequence, Annotated, List, Dict, Any
import operator
import re
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from .scout import scout_node
from .booster import booster_node
from .closer import closer_node
from .campaigner import campaigner_node
from .merger import merger_node
from .tools import ALL_TOOLS

class PurchaseContext(TypedDict, total=False):
    purchase_intent_id: str
    basket_items: List[Dict[str, Any]]
    amount_paise: int
    intent_description: str

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    customer_id: str
    purchase_state: str
    purchase_context: PurchaseContext
    user_confirmed: bool
    scout_result: dict
    booster_result: dict
    scout_start: float
    scout_end: float
    booster_start: float
    booster_end: float
    merger_start: float


_INTERNAL_ID_PATTERNS = (
    re.compile(r"\s*\((?:ID|Product ID)\s*:\s*item_[A-Za-z0-9_-]+\)\s*", re.IGNORECASE),
    re.compile(r"\s*\[(?:Rec ID|Recommendation ID)\s*:\s*rec_[A-Za-z0-9_-]+\]\s*", re.IGNORECASE),
    re.compile(r"\b(?:ID|Product ID|item_id|product_id|Rec ID|Recommendation ID)\s*[:=]\s*(?:item_|rec_)[A-Za-z0-9_-]+\b", re.IGNORECASE),
    re.compile(r"\bitem_[A-Za-z0-9_-]+\b", re.IGNORECASE),
    re.compile(r"\brec_[A-Za-z0-9_-]+\b", re.IGNORECASE),
    re.compile(r"\b(?:pi|ord|oi)_[A-Za-z0-9_-]+\b", re.IGNORECASE),
)


def sanitize_customer_text(text: str) -> str:
    """Remove internal catalog, recommendation, purchase-intent, and local-order identifiers from customer-visible text."""
    sanitized = str(text or "")
    for pattern in _INTERNAL_ID_PATTERNS:
        sanitized = pattern.sub(" ", sanitized)
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    sanitized = re.sub(r"\n[ \t]+", "\n", sanitized)
    return sanitized.strip()


def route_next_node(state: AgentState):
    p_state = state.get("purchase_state", "IDLE")
    last = state.get("messages", [])[-1] if state.get("messages") else None

    if p_state in {"PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"}:
        return "closer"

    if last is not None and getattr(last, "tool_calls", None):
        return "tools"

    if p_state in {"USER_CONFIRMED", "GUARDIAN_APPROVED", "ORDER_CREATED", "PAYMENT_PENDING", "PAYMENT_SUCCESS"}:
        if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
            return "customer_safe"
        return "closer"

    ctx = state.get("purchase_context")
    if p_state == "PRODUCT_SELECTED" and ctx and ctx.get("basket_items"):
        return ["scout", "booster"]

    if isinstance(last, HumanMessage):
        text = str(last.content).lower().strip()
        if p_state == "IDLE" and text in {"hi", "hello", "hey", "greetings"}:
            return "scout"
        if any(k in text for k in ("campaign", "marketing", "campaign performance")):
            return "campaigner"
        return "scout"

    if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
        return "customer_safe"

    return "customer_safe"


def route_after_merger(state: AgentState):
    """Specific routing after Merger has synced parallel results."""
    p_state = state.get("purchase_state", "IDLE")
    messages = state.get("messages", [])
    has_ai_text = False
    for m in reversed(messages):
        if getattr(m, "type", "") == "tool":
            break
        if getattr(m, "type", "") == "ai":
            if getattr(m, "tool_calls", None):
                return "tools"
            if getattr(m, "content", ""):
                has_ai_text = True
    if has_ai_text:
        return "customer_safe"

    if p_state in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "GUARDIAN_APPROVED", "ORDER_CREATED", "PAYMENT_PENDING"}:
        return "closer"
    return "customer_safe"


def route_after_tools(state: AgentState):
    messages = state.get("messages", [])
    if not messages:
        return "customer_safe"

    # Payment/order tools are terminal for this turn. They already performed the
    # authoritative side effect and return customer-safe status text. Routing
    # them back through Closer would see the same checkout user message again and
    # can issue the same tool call a second time.
    last_tool = messages[-1]
    if getattr(last_tool, "type", "") == "tool":
        tool_name = getattr(last_tool, "name", "") or ""
        if tool_name in {"create_razorpay_order", "check_payment_status", "reset_purchase_intent"}:
            return "customer_safe"
        if "FATAL_ERROR" in str(last_tool.content):
            return "customer_safe"

    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)), None)
    if not last_ai:
        return "scout"
    names = {tc["name"] for tc in last_ai.tool_calls}
    if "stage_purchase_intent" in names:
        return "booster"
    if "search_catalog" in names or "get_product_details" in names:
        return "scout"
    if "fetch_recommendations" in names:
        return "booster"
    if "analyze_campaign_opportunities" in names:
        return "campaigner"
    if {"create_razorpay_order", "check_payment_status", "reset_purchase_intent"} & names:
        return "customer_safe"
    return "closer"


def customer_safe_node(state: AgentState):
    """Final customer-visible boundary. Sanitize tool/AI response before END."""
    messages = list(state.get("messages", []))
    if not messages:
        return {"messages": [AIMessage(content="How can I help?")]}

    last = messages[-1]
    if isinstance(last, AIMessage):
        cleaned = sanitize_customer_text(getattr(last, "content", ""))
        return {"messages": [AIMessage(content=cleaned or "How can I help?")]}

    if getattr(last, "type", "") == "tool":
        content = getattr(last, "content", "")
        if "FATAL_ERROR" in content:
            content = content.replace("FATAL_ERROR:", "").replace("FATAL_ERROR", "").strip()
        cleaned = sanitize_customer_text(content)
        return {"messages": [AIMessage(content=cleaned or "Your request has been processed.")]}

    return {"messages": [AIMessage(content="How can I help?")]}


workflow = StateGraph(AgentState)
workflow.add_node("scout", scout_node)
workflow.add_node("booster", booster_node)
workflow.add_node("merger", merger_node)
workflow.add_node("closer", closer_node)
workflow.add_node("campaigner", campaigner_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_node("customer_safe", customer_safe_node)

workflow.set_conditional_entry_point(route_next_node, {
    "scout": "scout", "booster": "booster", "closer": "closer",
    "campaigner": "campaigner", "tools": "tools", "customer_safe": "customer_safe", END: END,
})

workflow.add_edge("scout", "merger")
workflow.add_edge("booster", "merger")

workflow.add_conditional_edges("merger", route_after_merger, {
    "tools": "tools", "closer": "closer", "customer_safe": "customer_safe", END: END,
})

for node in ("closer", "campaigner"):
    workflow.add_conditional_edges(node, route_next_node, {
        "tools": "tools", "scout": "scout", "booster": "booster",
        "closer": "closer", "campaigner": "campaigner", "customer_safe": "customer_safe", END: END,
    })

workflow.add_conditional_edges("tools", route_after_tools, {
    "scout": "scout", "booster": "booster", "closer": "closer", "campaigner": "campaigner",
    "customer_safe": "customer_safe", END: END
})
workflow.add_edge("customer_safe", END)

maxx_app = workflow.compile(checkpointer=MemorySaver())
