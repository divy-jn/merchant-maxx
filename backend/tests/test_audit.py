import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from agents.maxx import maxx_app
from langgraph.errors import GraphRecursionError

def test_infinite_tool_loop_termination():
    """Phase 2: Prove that if the LLM goes crazy and infinitely requests tools, the graph terminates safely."""
    
    # We mock the scout chat model to ALWAYS return a tool call
    with patch("agents.scout.get_llm") as mock_get_llm:
        mock_inst = MagicMock()
        mock_inst.invoke.return_value = AIMessage(
            content="", 
            tool_calls=[{"name": "search_catalog", "args": {"query": "test"}, "id": "tc_1"}]
        )
        mock_inst.bind_tools.return_value = mock_inst
        mock_get_llm.return_value = mock_inst

        inputs = {
            "messages": [HumanMessage(content="Show me laptops")],
            "purchase_state": "IDLE"
        }
        config = {"configurable": {"thread_id": "test_loop"}, "recursion_limit": 10}
        
        # It should hit the recursion limit (10) and raise GraphRecursionError
        with pytest.raises(GraphRecursionError):
            maxx_app.invoke(inputs, config)

def test_llm_fallback_sequence():
    """Phase 3: Verify that fallback is request-scoped and cascades correctly without permanent demotion."""
    from llm.factory import get_chat_model
    from litellm.exceptions import RateLimitError
    from httpx import Response, Request

    # Create dummy request and response for the exception
    req = Request("POST", "https://example.com")
    resp = Response(429, request=req)

    with patch("langchain_litellm.ChatLiteLLM.invoke") as mock_invoke:
        # We need invoke to fail on first call (3.7), succeed on second (3.6)
        mock_invoke.side_effect = [
            RateLimitError("429 Too Many Requests", response=resp, llm_provider="gemini", model="gemini-3.7-flash"),
            AIMessage(content="Response from 3.6"),
            # For the second request:
            RateLimitError("429 Too Many Requests", response=resp, llm_provider="gemini", model="gemini-3.7-flash"),
            AIMessage(content="Response from 3.6 (second)")
        ]
        
        model = get_chat_model()
        
        # Act
        res = model.invoke([HumanMessage(content="Hello")])
        
        # Assert the model succeeded by falling back
        assert mock_invoke.call_count == 2
        assert res.content == "Response from 3.6"
        
        # Verify request-scoped (second request starts from primary again)
        res2 = model.invoke([HumanMessage(content="Hello again")])
        
        assert mock_invoke.call_count == 4  # It tried primary again, failed, then fallback
        assert res2.content == "Response from 3.6 (second)"

def test_merger_contradictory_results():
    """Phase 10: Verify Merger handles contradictory states safely."""
    from agents.merger import merger_node

    # Simulated state where Scout succeeded but Booster failed/returned garbage
    state = {
        "purchase_state": "IDLE",
        "scout_result": {"msg": "Purchase intent staged for prod_123. Await explicit confirmation.", "intent_staged": True},
        "booster_result": {"msg": "Recommendation service unavailable: Pinecone API Error", "status": "unavailable"}
    }
    
    new_state = merger_node(state)
    
    # The combined result should move state to PURCHASE_PENDING
    assert new_state["purchase_state"] == "PURCHASE_PENDING"
