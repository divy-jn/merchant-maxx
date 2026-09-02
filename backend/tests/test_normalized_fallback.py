import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from llm.factory import get_chat_model
from litellm.exceptions import BadRequestError

def test_normalization_genuine_400():
    # If the LLM throws a genuine 400 Bad Request, it should NOT be caught by the fallback, 
    # meaning get_chat_model().invoke(...) should raise the BadRequestError to the application.
    llm = get_chat_model()
    
    with patch("langchain_litellm.ChatLiteLLM._generate") as mock_generate:
        # Mocking genuine 400
        mock_generate.side_effect = BadRequestError(
            message='GeminiException BadRequestError - {"error": {"code": 400, "message": "Requests ending with a model turn are not supported.", "status": "INVALID_ARGUMENT"}}',
            model="gemini-3.6-flash",
            llm_provider="gemini"
        )
        
        with pytest.raises(BadRequestError):
            llm.invoke([HumanMessage(content="hi")])

def test_normalization_fake_429():
    # If the LLM throws a 429 disguised as a 400, it SHOULD be caught by the fallback, 
    # and since we mocked the first one, it will fall back to the next model (which we can mock to succeed).
    llm = get_chat_model()
    
    with patch("langchain_litellm.ChatLiteLLM._generate") as mock_generate:
        # First call fails with disguised 429
        # Second call (Gemini fallback) succeeds
        def side_effect(*args, **kwargs):
            if mock_generate.call_count == 1:
                raise BadRequestError(
                    message="Client error '429 Too Many Requests' - Quota exceeded",
                    model="gemini-3.6-flash",
                    llm_provider="gemini"
                )
            # Succeed on fallback
            from langchain_core.outputs import ChatResult, ChatGeneration
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Fallback success!"))])
            
        mock_generate.side_effect = side_effect
        
        response = llm.invoke([HumanMessage(content="hi")])
        assert response.content == "Fallback success!"
        assert mock_generate.call_count == 2 # Proves fallback occurred
