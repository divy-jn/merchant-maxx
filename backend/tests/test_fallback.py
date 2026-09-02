import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from llm.registry import Capability
import litellm.exceptions as litellm_exceptions
import httpx
from llm.factory import get_chat_model

pytestmark = pytest.mark.asyncio

from langchain_core.runnables import Runnable

class MockLLM(Runnable):
    def __init__(self, side_effect=None, return_value=None):
        self._side_effect = side_effect
        self._return_value = return_value
        self.call_count = 0
    
    async def ainvoke(self, *args, **kwargs):
        self.call_count += 1
        if self._side_effect:
            raise self._side_effect
        return self._return_value
        
    def bind_tools(self, *args, **kwargs):
        return self
        
    def with_config(self, *args, **kwargs):
        return self
        
    def invoke(self, *args, **kwargs):
        self.call_count += 1
        if self._side_effect:
            raise self._side_effect
        return self._return_value

@patch("llm.factory._instantiate_model")
async def test_fallback_sequence_gemini_to_nemotron(mock_instantiate):
    """Test that consecutive provider errors fall back exactly 4 levels, from Gemini down to Nemotron."""
    mock_1 = MockLLM(side_effect=litellm_exceptions.RateLimitError("429 Quota Exceeded", llm_provider="google", model="gemini-3.7-flash"))
    mock_2 = MockLLM(side_effect=litellm_exceptions.Timeout("Timeout", llm_provider="google", model="gemini-3.6-flash"))
    mock_3 = MockLLM(side_effect=httpx.HTTPError("Connection closed"))
    
    mock_nemotron_res = AIMessage(content="Success from Nemotron!")
    mock_4 = MockLLM(return_value=mock_nemotron_res)
    
    mock_instantiate.side_effect = [mock_1, mock_2, mock_3, mock_4]
    
    model = get_chat_model([Capability.TOOL_CALLING])
    res = await model.ainvoke([HumanMessage(content="Hello")])
    
    assert res.content == "Success from Nemotron!"
    assert mock_1.call_count == 1
    assert mock_2.call_count == 1
    assert mock_3.call_count == 1
    assert mock_4.call_count == 1

@patch("llm.factory._instantiate_model")
async def test_fallback_early_success(mock_instantiate):
    """Test that if the primary model succeeds, fallbacks are NOT called."""
    mock_success = AIMessage(content="Success from Gemini!")
    mock_1 = MockLLM(return_value=mock_success)
    mock_2 = MockLLM()
    mock_3 = MockLLM()
    mock_4 = MockLLM()
    
    mock_instantiate.side_effect = [mock_1, mock_2, mock_3, mock_4]
    
    model = get_chat_model([Capability.TOOL_CALLING])
    res = await model.ainvoke([HumanMessage(content="Hello")])
    
    assert res.content == "Success from Gemini!"
    assert mock_1.call_count == 1
    assert mock_2.call_count == 0
    assert mock_3.call_count == 0
    assert mock_4.call_count == 0

@patch("llm.factory._instantiate_model")
async def test_fallback_does_not_catch_application_bugs(mock_instantiate):
    """Test that application bugs like AttributeError, TypeError, NameError are NOT caught by the LLM fallback."""
    for error_type in [
        AttributeError("NoneType object has no attribute 'data'"),
        TypeError("Invalid type"),
        NameError("name is not defined")
    ]:
        mock_1 = MockLLM(side_effect=error_type)
        mock_2 = MockLLM()
        mock_3 = MockLLM()
        mock_4 = MockLLM()
        
        mock_instantiate.side_effect = [mock_1, mock_2, mock_3, mock_4]
        
        model = get_chat_model([Capability.TOOL_CALLING])
        
        with pytest.raises(type(error_type)):
            await model.ainvoke([HumanMessage(content="Hello")])
        
        assert mock_1.call_count == 1
        assert mock_2.call_count == 0  # Should not fallback!
    
@patch("services.payment_resolution.supabase.table")
def test_mid_process_recovery_reuses_order(mock_table):
    """
    Test that if an LLM fails after an order is created, the next request 
    (or fallback request re-reading authoritative state) will reuse the order.
    """
    from services.payment_resolution import _recover_local_order
    
    # Mocking supabase to return an existing order
    mock_table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "order_id": "order_existing123",
        "purchase_intent_id": "pi_mock123",
        "customer_id": "cust_mock123",
        "total_paise": 50000
    }
    
    recovered_order = _recover_local_order(
        "pi_mock123",
        "order_mock123",
        "cust_mock123",
        50000,
        [],
        50000,
        0,
        0
    )
    
    assert recovered_order is not None
    assert recovered_order["order_id"] == "order_existing123"
