from typing import TypedDict, Sequence, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import operator

from .scout import scout_node
from .closer import closer_node
from .tools import ALL_TOOLS

# Define the State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str

def router(state: AgentState) -> str:
    """Routes to the correct node based on tool calls or intent"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message has a tool call, route to the tool execution node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Check if it's the payment link tool, which closer uses
        if last_message.tool_calls[0]["name"] == "create_payment_link_for_product":
            return "tools" # execute tool
        return "tools"
    
    return END

# Build the Graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("scout", scout_node)
workflow.add_node("closer", closer_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

# For now, MAXX delegates everything to Scout first
workflow.set_entry_point("scout")

# Route from Scout
workflow.add_conditional_edges(
    "scout",
    router,
    {"tools": "tools", END: END}
)

# Route from tools back to Scout
workflow.add_edge("tools", "scout")

# Compile graph
maxx_app = workflow.compile()
