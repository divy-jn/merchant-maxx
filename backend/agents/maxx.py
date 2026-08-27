from typing import TypedDict, Sequence, Annotated, Literal, List, Dict, Optional, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import operator

from .scout import scout_node
from .booster import booster_node
from .closer import closer_node
from .campaigner import campaigner_node
from .tools import ALL_TOOLS

# Define the State
class PurchaseContext(TypedDict):
    purchase_intent_id: str
    basket_items: List[Dict[str, Any]] # e.g. [{"product_id": "...", "quantity": 1}]
    amount_paise: int
    intent_description: str

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    customer_id: str
    purchase_state: Literal[
        "IDLE", 
        "PRODUCT_SELECTED", 
        "RECOMMENDATION_SHOWN",
        "USER_CONFIRMED", 
        "GUARDIAN_APPROVED", 
        "ORDER_CREATED", 
        "PAYMENT_PENDING", 
        "PAYMENT_SUCCESS", 
        "PAYMENT_FAILED", 
        "PAYMENT_UNKNOWN",
        "RECOVERY_PENDING"
    ]
    purchase_context: PurchaseContext
    user_confirmed: bool

def route_next_node(state: AgentState) -> Literal["tools", "scout", "booster", "closer", "campaigner", "__end__"]:
    p_state = state.get("purchase_state", "IDLE")
    last_message = state["messages"][-1] if state["messages"] else None
    
    # 1. Recovery explicitly takes precedence
    if p_state in ["PAYMENT_FAILED", "PAYMENT_UNKNOWN", "RECOVERY_PENDING"]:
        return "closer"
        
    # 2. If tools were called, route to tools
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
        
    # 3. State machine routing
    if p_state == "IDLE":
        # Check if the user is asking about campaigns (simple heuristic)
        if last_message and isinstance(last_message, HumanMessage):
            content = str(last_message.content).lower()
            if "campaign" in content or "marketing" in content or "discount" in content:
                return "campaigner"
        return "scout"
    elif p_state == "PRODUCT_SELECTED":
        return "booster"
    elif p_state in ["RECOMMENDATION_SHOWN", "USER_CONFIRMED", "GUARDIAN_APPROVED", "ORDER_CREATED", "PAYMENT_PENDING"]:
        return "closer"
    
    return END

def route_after_tools(state: AgentState) -> Literal["scout", "booster", "closer", "campaigner"]:
    """After tools run, return to the agent that called them or progress state"""
    # Find the last AIMessage with tool calls
    last_ai_msg = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai_msg = msg
            break
            
    if not last_ai_msg:
        return "scout"
        
    tool_names = [tc["name"] for tc in last_ai_msg.tool_calls]
    
    # Tool specific state transitions
    if "search_products" in tool_names:
        return "booster"  # Scout just searched, progress to Booster
        
    if "fetch_recommendations" in tool_names:
        return "booster"
        
    if "create_razorpay_order" in tool_names or "create_payment_link_for_product" in tool_names:
        return "closer"
        
    if "check_payment_status" in tool_names:
        return "closer"
        
    if "get_campaign_performance" in tool_names or "get_customer_metrics" in tool_names:
        return "campaigner"
        
    # Default fallback based on state
    p_state = state.get("purchase_state", "IDLE")
    if p_state in ["IDLE"]:
        return "scout"
    if p_state == "PRODUCT_SELECTED":
        return "booster"
        
    return "closer"

# Build the Graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("scout", scout_node)
workflow.add_node("booster", booster_node)
workflow.add_node("closer", closer_node)
workflow.add_node("campaigner", campaigner_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

# Entry point depends on state
workflow.set_conditional_entry_point(
    route_next_node,
    {
        "scout": "scout",
        "booster": "booster",
        "closer": "closer",
        "campaigner": "campaigner",
        "tools": "tools",
        END: END
    }
)

# Agent -> tools or end
for node in ["scout", "booster", "closer", "campaigner"]:
    workflow.add_conditional_edges(
        node, 
        route_next_node, 
        {"tools": "tools", END: END, "booster": "booster", "closer": "closer", "scout": "scout"}
    )

# Tools -> right agent
workflow.add_conditional_edges(
    "tools", 
    route_after_tools, 
    {"scout": "scout", "booster": "booster", "closer": "closer", "campaigner": "campaigner"}
)

# Compile graph
maxx_app = workflow.compile()
