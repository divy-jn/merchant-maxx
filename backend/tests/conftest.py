import importlib.util
import sys
import os

# Ensure test environment is set before any other imports
os.environ.setdefault("APP_ENV", "test")
from unittest.mock import MagicMock

# Mock Pinecone to prevent API key errors during import
sys.modules['pinecone'] = MagicMock()
sys.modules['pinecone'].Pinecone = MagicMock()

# Make payment_state importable without going through agents/__init__.py
_state_path = os.path.join(os.path.dirname(__file__), "..", "agents", "payment_state.py")
_spec = importlib.util.spec_from_file_location("agents.payment_state", _state_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["agents.payment_state"] = _mod
_spec.loader.exec_module(_mod)

import pytest

@pytest.fixture(autouse=True)
def guard_real_llm_calls(monkeypatch):
    """
    Globally blocks all real Gemini API calls during testing unless explicitly enabled.
    This guarantees zero API quota is consumed by normal pytest runs.
    """
    if os.environ.get("RUN_LIVE_LLM_TESTS") == "true":
        yield
        return

    def block_call(*args, **kwargs):
        raise RuntimeError(
            "Real LLM network call attempted in normal test suite. "
            "Set RUN_LIVE_LLM_TESTS=true to allow this, or mock the LLM locally."
        )

    # Block generate and stream calls in ChatGoogleGenerativeAI
    monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI._generate", block_call)
    monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI._agenerate", block_call)
    
    # Block generate and stream calls in ChatOpenAI
    monkeypatch.setattr("langchain_openai.ChatOpenAI._generate", block_call)
    monkeypatch.setattr("langchain_openai.ChatOpenAI._agenerate", block_call)
    
    yield
