"""
Task 18 — LLM Fallback Evaluation
Mock failures at each level to verify fallback cascades properly and is request-scoped.
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from litellm.exceptions import RateLimitError
from httpx import Request, Response
from llm.factory import get_chat_model

def test_per_request_fallback_cascade():
    """Verify fallback occurs per request, with no permanent demotion."""
    model = get_chat_model()
    req = Request("POST", "https://example.com")
    resp = Response(429, request=req)
    
    with patch("langchain_litellm.ChatLiteLLM.invoke") as mock_invoke:
        # Request 1: 3.7 fails (429), 3.6 succeeds
        # Request 2: 3.7 fails (429), 3.6 fails (500), 3.5 succeeds
        # Request 3: all Gemini fail, Nemotron succeeds
        
        mock_invoke.side_effect = [
            # Req 1
            RateLimitError("429 Too Many Requests", response=resp, llm_provider="gemini", model="gemini-3.7-flash"),
            MagicMock(content="Response 1 from 3.6"),
            
            # Req 2
            RateLimitError("429 Too Many Requests", response=resp, llm_provider="gemini", model="gemini-3.7-flash"),
            RateLimitError("500 Internal Error", response=Response(500, request=req), llm_provider="gemini", model="gemini-3.6-flash"),
            MagicMock(content="Response 2 from 3.5"),
            
            # Req 3
            RateLimitError("429", response=resp, llm_provider="gemini", model="gemini-3.7-flash"),
            RateLimitError("429", response=resp, llm_provider="gemini", model="gemini-3.6-flash"),
            RateLimitError("429", response=resp, llm_provider="gemini", model="gemini-3.5-flash"),
            MagicMock(content="Response 3 from Nemotron"),
        ]
        
        res1 = model.invoke([HumanMessage(content="test 1")])
        assert res1.content == "Response 1 from 3.6"
        assert mock_invoke.call_count == 2
        
        res2 = model.invoke([HumanMessage(content="test 2")])
        assert res2.content == "Response 2 from 3.5"
        assert mock_invoke.call_count == 5
        
        res3 = model.invoke([HumanMessage(content="test 3")])
        assert res3.content == "Response 3 from Nemotron"
        assert mock_invoke.call_count == 9

