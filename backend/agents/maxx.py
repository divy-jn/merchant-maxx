from typing import TypedDict, Sequence, Annotated, Literal, List, Dict, Any
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from .scout import scout_node
from .booster import booster_node
from .closer import closer_node
from .campaigner import campaigner_node
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


def route_next_node(state: AgentState):
    p_state = state.get("purchase_state", "IDLE")
    last = state.get("messages", [])[-1] if state.get("messages") else None
    if p_state in {"PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"}:
        return "closer"
    if last is not None and getattr(last, "tool_calls", None):
        return "tools"
    if p_state == "PRODUCT_SELECTED":
        return "booster"
    if p_state in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "GUARDIAN_APPROVED", "ORDER_CREATED", "PAYMENT_PENDING"}:
        return "closer"
    if isinstance(last, HumanMessage):
        text = str(last.content).lower()
        if any(k in text for k in ("campaign", "marketing", "campaign performance")):
            return "campaigner"
        return "scout"
    return END


def route_after_tools(state: AgentState):
    last_ai = next((m for m in reversed(state.get("messages", [])) if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)), None)
    if not last_ai:
        return "scout"
    names = {tc["name"] for tc in last_ai.tool_calls}
    if "stage_purchase_intent" in names:
        return "closer"
    if "search_catalog" in names or "get_product_details" in names:
        return "scout"
    if "fetch_recommendations" in names:
        return "booster"
    if "analyze_campaign_opportunities" in names:
        return "campaigner"
    if {"create_razorpay_order", "check_payment_status", "reset_purchase_intent"} & names:
        return "closer"
    return "closer"

workflow = StateGraph(AgentState)
workflow.add_node("scout", scout_node)
workflow.add_node("booster", booster_node)
workflow.add_node("closer", closer_node)
workflow.add_node("campaigner", campaigner_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

workflow.set_conditional_entry_point(route_next_node, {
    "scout": "scout", "booster": "booster", "closer": "closer",
    "campaigner": "campaigner", "tools": "tools", END: END,
})
for node in ("scout", "booster", "closer", "campaigner"):
    workflow.add_conditional_edges(node, route_next_node, {
        "tools": "tools", "scout": "scout", "booster": "booster",
        "closer": "closer", "campaigner": "campaigner", END: END,
    })
workflow.add_conditional_edges("tools", route_after_tools, {
    "scout": "scout", "booster": "booster", "closer": "closer", "campaigner": "campaigner",
})

# MemorySaver preserves conversational graph state within the process. Supabase purchase_intents is authoritative for money state.
maxx_app = workflow.compile(checkpointer=MemorySaver())
