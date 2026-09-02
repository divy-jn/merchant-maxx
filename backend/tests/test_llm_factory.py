import pytest
from llm.factory import get_chat_model
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

def test_get_chat_model_openai(monkeypatch):
    monkeypatch.setattr("config.settings.LLM_PROVIDER", "openai")
    monkeypatch.setattr("config.settings.OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("config.settings.OPENAI_MODEL", "gpt-4o-mini")
    
    model = get_chat_model()
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4o-mini"
    # OpenAI api_key is stored in a SecretStr, so accessing it directly might require get_secret_value() 
    # but asserting type and model name is sufficient to prove provider selection worked.

def test_get_chat_model_gemini(monkeypatch):
    monkeypatch.setattr("config.settings.LLM_PROVIDER", "gemini")
    monkeypatch.setattr("config.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("config.settings.GEMINI_MODEL", "gemini-3.7-flash")
    
    model = get_chat_model()
    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model == "gemini-3.7-flash"

def test_get_chat_model_invalid_provider(monkeypatch):
    monkeypatch.setattr("config.settings.LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER: anthropic"):
        get_chat_model()
