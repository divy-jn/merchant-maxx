import logging
from typing import List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from config import settings
from llm.registry import Capability

logger = logging.getLogger(__name__)

def get_chat_model(required_capabilities: List[Capability] = None) -> BaseChatModel:
    """
    Returns a direct LangChain BaseChatModel configured based on LLM_PROVIDER.
    Supports 'openai' and 'gemini' natively, without fallback.
    """
    if required_capabilities is None:
        required_capabilities = []

    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY or "dummy-key-to-bypass-init-validation",
            temperature=settings.OPENAI_TEMPERATURE,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT
        )
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY or "dummy-key-to-bypass-init-validation",
            temperature=settings.GEMINI_TEMPERATURE,
            max_retries=settings.GEMINI_MAX_RETRIES,
            timeout=settings.GEMINI_TIMEOUT
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
