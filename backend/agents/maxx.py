from typing import TypedDict, Sequence, Annotated, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import operator

from .scout import scout_node
from .closer import closer_node
from .tools import ALL_TOOLS, DISCOVERY_TOOLS, PAYMENT_TOOLS

# Define the State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

def should_use_tools(state: AgentState) -> Literal["tools", "__end__"]:
    """Check if the last message has tool calls"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

def route_after_tools(state: AgentState) -> Literal["scout", "closer"]:
    """After tool execution, decide which agent should handle the result.
    If the tool was a payment tool, route to Closer. Otherwise back to Scout."""
    # Look at the tool call that was just executed
    for msg in reversed(state["messages"]):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_name = msg.tool_calls[0]["name"]
            if tool_name == "create_payment_link_for_product":
                return "closer"
            return "scout"
    return "scout"

# Build the Graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("scout", scout_node)
workflow.add_node("closer", closer_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

# Entry point: always start with Scout (discovery)
workflow.set_entry_point("scout")

# Scout → tools or end
workflow.add_conditional_edges("scout", should_use_tools, {"tools": "tools", END: END})

# Closer → tools or end
workflow.add_conditional_edges("closer", should_use_tools, {"tools": "tools", END: END})

# After tools execute, route back to the right agent
workflow.add_conditional_edges("tools", route_after_tools, {"scout": "scout", "closer": "closer"})

# Compile graph
maxx_app = workflow.compile()
