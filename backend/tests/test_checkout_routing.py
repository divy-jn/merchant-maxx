from langchain_core.messages import ToolMessage, AIMessage

from agents.maxx import route_after_tools


TERMINAL_PAYMENT_TOOLS = (
    "create_razorpay_order",
    "check_payment_status",
    "reset_purchase_intent",
)


def test_payment_tools_route_to_customer_safe():
    for tool_name in TERMINAL_PAYMENT_TOOLS:
        message = ToolMessage(content="operation completed", name=tool_name, tool_call_id="call_1")
        assert route_after_tools({"messages": [message]}) == "customer_safe"


def test_fatal_tool_error_routes_to_customer_safe():
    message = ToolMessage(content="FATAL_ERROR: temporary failure", name="create_razorpay_order", tool_call_id="call_2")
    assert route_after_tools({"messages": [message]}) == "customer_safe"


def test_non_payment_tool_keeps_existing_agent_flow():
    message = AIMessage(
        content="",
        tool_calls=[
            {"name": "search_catalog", "args": {"query": "keyboard"}, "id": "call_3", "type": "tool_call"}
        ],
    )
    assert route_after_tools({"messages": [message]}) == "scout"
