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


def route_next_node(state: AgentState):
    p_state = state.get("purchase_state", "IDLE")
    last = state.get("messages", [])[-1] if state.get("messages") else None
    
    if p_state in {"PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"}:
        return "closer"
        
    if last is not None and getattr(last, "tool_calls", None):
        return "tools"
        
    if p_state in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "GUARDIAN_APPROVED", "ORDER_CREATED", "PAYMENT_PENDING", "PAYMENT_SUCCESS"}:
        if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
            return END
        return "closer"
        
    ctx = state.get("purchase_context")
    if p_state == "PRODUCT_SELECTED" and ctx and ctx.get("basket_items"):
        return ["scout", "booster"]
        
    if isinstance(last, HumanMessage):
        text = str(last.content).lower().strip()
        
        # Fast-path trivial greetings if we have no active purchase state
        if p_state == "IDLE" and text in {"hi", "hello", "hey", "greetings"}:
            return "scout"
            
        if any(k in text for k in ("campaign", "marketing", "campaign performance")):
            return "campaigner"
        return "scout"
        
    if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
        return END

    return END

def route_after_merger(state: AgentState):
    """Specific routing after Merger has synced parallel results."""
    p_state = state.get("purchase_state", "IDLE")
    
    # If Booster or Scout had tool calls, route to tools
    last = state.get("messages", [])[-1] if state.get("messages") else None
    if last is not None and getattr(last, "tool_calls", None):
        return "tools"
        
    if p_state in {"PURCHASE_PENDING", "RECOMMENDATION_SHOWN", "USER_CONFIRMED", "GUARDIAN_APPROVED", "ORDER_CREATED", "PAYMENT_PENDING"}:
        return "closer"
    return END


def route_after_tools(state: AgentState):
    messages = state.get("messages", [])
    if messages and getattr(messages[-1], "type", "") == "tool" and "FATAL_ERROR" in str(messages[-1].content):
        return END
    return route_next_node(state)

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
        return "closer"
    return "closer"

workflow = StateGraph(AgentState)
workflow.add_node("scout", scout_node)
workflow.add_node("booster", booster_node)
workflow.add_node("merger", merger_node)
workflow.add_node("closer", closer_node)
workflow.add_node("campaigner", campaigner_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

workflow.set_conditional_entry_point(route_next_node, {
    "scout": "scout", "booster": "booster", "closer": "closer",
    "campaigner": "campaigner", "tools": "tools", END: END,
})

# Fan-in to merger
workflow.add_edge("scout", "merger")
workflow.add_edge("booster", "merger")

# After merger, decide next step (often closer or END)
workflow.add_conditional_edges("merger", route_after_merger, {
    "tools": "tools", "closer": "closer", END: END,
})

# Closer and Campaigner behavior
for node in ("closer", "campaigner"):
    workflow.add_conditional_edges(node, route_next_node, {
        "tools": "tools", "scout": "scout", "booster": "booster",
        "closer": "closer", "campaigner": "campaigner", END: END,
    })

workflow.add_conditional_edges("tools", route_after_tools, {
    "scout": "scout", "booster": "booster", "closer": "closer", "campaigner": "campaigner", END: END
})

# MemorySaver preserves conversational graph state within the process. Supabase purchase_intents is authoritative for money state.
maxx_app = workflow.compile(checkpointer=MemorySaver())
