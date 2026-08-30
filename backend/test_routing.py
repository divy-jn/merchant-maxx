import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from litellm import exceptions as litellm_exceptions
import httpx

from llm.registry import Capability
from llm.factory import get_chat_model
from config import settings

@pytest.fixture(autouse=True)
def setup_env():
    settings.ALLOW_PAID_LLM = False
    settings.LLM_API_KEY = "test_gemini"
    settings.OPENROUTER_API_KEY = "test_openrouter"

def _mock_completion_success(*args, **kwargs):
    model = kwargs.get("model")
    from litellm.utils import ModelResponse, Message, Choices
    msg = Message(content=f"Success from {model}", role="assistant")
    choice = Choices(message=msg, index=0, finish_reason="stop")
    return ModelResponse(id="test", choices=[choice], model=model)

def _mock_completion_429(*args, **kwargs):
    req = httpx.Request("POST", "http://test")
    res = httpx.Response(429, request=req)
    model = kwargs.get("model", "test")
    raise litellm_exceptions.RateLimitError(message="Rate limited", response=res, llm_provider="test", model=model)

def _mock_completion_401(*args, **kwargs):
    req = httpx.Request("POST", "http://test")
    res = httpx.Response(401, request=req)
    model = kwargs.get("model", "test")
    raise litellm_exceptions.AuthenticationError(message="Auth failed", response=res, llm_provider="test", model=model)


@patch("langchain_litellm.ChatLiteLLM._generate")
def test_1_37_success(mock_generate):
    """Test 1: 3.7 success -> only 3.7 invoked"""
    # Langchain invokes _generate internally.
    # Actually, ChatLiteLLM overrides `_generate`. Let's mock completion directly via litellm since ChatLiteLLM uses it.
    pass

@patch("litellm.completion")
def test_1_37_success_via_litellm(mock_completion):
    mock_completion.side_effect = _mock_completion_success
    
    model = get_chat_model([Capability.TOOL_CALLING])
    # LangChain ChatModels return AIMessage
    res = model.invoke([HumanMessage(content="Hello")])
    
    assert "gemini-3.7-flash" in res.content
    assert mock_completion.call_count == 1
    assert mock_completion.call_args[1]["model"] == "gemini/gemini-3.7-flash"

@patch("litellm.completion")
def test_2_37_429_36_success(mock_completion):
    def side_effect(*args, **kwargs):
        if kwargs.get("model") == "gemini/gemini-3.7-flash":
            return _mock_completion_429(*args, **kwargs)
        return _mock_completion_success(*args, **kwargs)
        
    mock_completion.side_effect = side_effect
    
    model = get_chat_model([Capability.TOOL_CALLING])
    res = model.invoke([HumanMessage(content="Hello")])
    
    assert "gemini-3.6-flash" in res.content
    assert mock_completion.call_count == 2
    assert mock_completion.call_args_list[0][1]["model"] == "gemini/gemini-3.7-flash"
    assert mock_completion.call_args_list[1][1]["model"] == "gemini/gemini-3.6-flash"

@patch("litellm.completion")
def test_3_37_36_429_35_success(mock_completion):
    def side_effect(*args, **kwargs):
        if kwargs.get("model") in ["gemini/gemini-3.7-flash", "gemini/gemini-3.6-flash"]:
            return _mock_completion_429(*args, **kwargs)
        return _mock_completion_success(*args, **kwargs)
        
    mock_completion.side_effect = side_effect
    
    model = get_chat_model([Capability.TOOL_CALLING])
    res = model.invoke([HumanMessage(content="Hello")])
    
    assert "gemini-3.5-flash" in res.content
    assert mock_completion.call_count == 3
    assert mock_completion.call_args_list[2][1]["model"] == "gemini/gemini-3.5-flash"

@patch("litellm.completion")
def test_4_all_429_except_nemotron(mock_completion):
    def side_effect(*args, **kwargs):
        if kwargs.get("model") != "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free":
            return _mock_completion_429(*args, **kwargs)
        return _mock_completion_success(*args, **kwargs)
        
    mock_completion.side_effect = side_effect
    
    model = get_chat_model([Capability.TOOL_CALLING])
    res = model.invoke([HumanMessage(content="Hello")])
    
    assert "nemotron" in res.content
    assert mock_completion.call_count == 4
    assert mock_completion.call_args_list[3][1]["model"] == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"

@patch("litellm.completion")
def test_5_all_fail(mock_completion):
    mock_completion.side_effect = _mock_completion_429
    
    model = get_chat_model([Capability.TOOL_CALLING])
    
    with pytest.raises(litellm_exceptions.RateLimitError):
        model.invoke([HumanMessage(content="Hello")])
        
    assert mock_completion.call_count == 4

@patch("litellm.completion")
def test_6_no_permanent_demotion(mock_completion):
    # Request 1
    def side_effect_req1(*args, **kwargs):
        if kwargs.get("model") == "gemini/gemini-3.7-flash":
            return _mock_completion_429(*args, **kwargs)
        return _mock_completion_success(*args, **kwargs)
        
    mock_completion.side_effect = side_effect_req1
    
    model = get_chat_model([Capability.TOOL_CALLING])
    res1 = model.invoke([HumanMessage(content="Hello")])
    assert "gemini-3.6-flash" in res1.content
    
    # Request 2
    mock_completion.reset_mock()
    mock_completion.side_effect = _mock_completion_success
    
    res2 = model.invoke([HumanMessage(content="Hello again")])
    assert "gemini-3.7-flash" in res2.content
    assert mock_completion.call_count == 1
    assert mock_completion.call_args_list[0][1]["model"] == "gemini/gemini-3.7-flash"

@patch("litellm.completion")
def test_7_no_retry_storm(mock_completion):
    def side_effect(*args, **kwargs):
        if kwargs.get("model") == "gemini/gemini-3.7-flash":
            return _mock_completion_429(*args, **kwargs)
        return _mock_completion_success(*args, **kwargs)
        
    mock_completion.side_effect = side_effect
    
    model = get_chat_model([Capability.TOOL_CALLING])
    model.invoke([HumanMessage(content="Hello")])
    
    # Check that 3.7 was only called ONCE
    calls_for_37 = [call for call in mock_completion.call_args_list if call[1]["model"] == "gemini/gemini-3.7-flash"]
    assert len(calls_for_37) == 1

@patch("litellm.completion")
def test_8_paid_model_blocked(mock_completion):
    mock_completion.side_effect = _mock_completion_success
    
    # Manually inject a paid model into registry dynamically for test
    from llm.registry import ModelConfig, MODEL_REGISTRY
    paid_model = ModelConfig(
        provider="openai",
        model="gpt-4o",
        priority=0, # Highest priority
        is_free=False,
        capabilities=[Capability.TOOL_CALLING],
        litellm_model_name="openai/gpt-4o"
    )
    MODEL_REGISTRY.append(paid_model)
    
    try:
        model = get_chat_model([Capability.TOOL_CALLING])
        res = model.invoke([HumanMessage(content="Hello")])
        
        # Should not be GPT-4o because ALLOW_PAID_LLM is False
        assert "gemini-3.7-flash" in res.content
    finally:
        # Cleanup
        MODEL_REGISTRY.remove(paid_model)

