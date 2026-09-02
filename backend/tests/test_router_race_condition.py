import pytest
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from agents.maxx import route_after_merger

def test_route_after_merger_tool_call_preservation():
    # Simulate Scout branch finishing with a tool call
    scout_msg = AIMessage(content="", tool_calls=[{"name": "stage_purchase_intent", "args": {}, "id": "tc1"}])
    # Simulate Booster branch finishing with a normal response
    booster_msg = AIMessage(content="normal response")

    # Scenario 1: Booster finishes AFTER Scout
    state_booster_last = {
        "messages": [scout_msg, booster_msg],
        "purchase_state": "PRODUCT_SELECTED"
    }
    # It must detect the tool call in scout_msg
    assert route_after_merger(state_booster_last) == "tools"

    # Scenario 2: Booster finishes BEFORE Scout
    state_scout_last = {
        "messages": [booster_msg, scout_msg],
        "purchase_state": "PRODUCT_SELECTED"
    }
    assert route_after_merger(state_scout_last) == "tools"

def test_route_after_merger_no_phantom_execution():
    booster_msg = AIMessage(content="normal response")
    scout_msg = AIMessage(content="another normal response")

    state = {
        "messages": [booster_msg, scout_msg],
        "purchase_state": "PRODUCT_SELECTED"
    }
    # No tool calls at all
    assert route_after_merger(state) == "__end__"

def test_route_after_merger_multiple_tool_calls():
    scout_msg1 = AIMessage(content="", tool_calls=[{"name": "search_catalog", "args": {}, "id": "tc1"}])
    scout_msg2 = AIMessage(content="", tool_calls=[{"name": "get_product_details", "args": {}, "id": "tc2"}])
    booster_msg = AIMessage(content="normal response")

    state = {
        "messages": [scout_msg1, scout_msg2, booster_msg],
        "purchase_state": "PRODUCT_SELECTED"
    }
    assert route_after_merger(state) == "tools"

def test_route_after_merger_tool_already_executed():
    # If the tool call was already executed, a ToolMessage will be present AFTER the AIMessage
    scout_msg = AIMessage(content="", tool_calls=[{"name": "stage_purchase_intent", "args": {}, "id": "tc1"}])
    tool_msg = ToolMessage(content="staged", tool_call_id="tc1")
    booster_msg = AIMessage(content="normal response")

    # Sequence: Tool was executed.
    state = {
        "messages": [scout_msg, tool_msg, booster_msg],
        "purchase_state": "PURCHASE_PENDING"
    }
    # Since tool_msg is present, the scan backward hits tool_msg and stops, ignoring the unresolved tool_calls earlier.
    assert route_after_merger(state) == "closer"

