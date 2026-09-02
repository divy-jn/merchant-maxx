import logging
from typing import List, Optional
from langchain_litellm import ChatLiteLLM
from langchain_core.language_models.chat_models import BaseChatModel
from litellm import exceptions as litellm_exceptions

from config import settings
from llm.registry import Capability, ModelConfig, MODEL_REGISTRY

logger = logging.getLogger(__name__)

import google.genai.errors as genai_errors
import httpx

# Exceptions that allow moving to fallback
FALLBACK_EXCEPTIONS = (
    litellm_exceptions.RateLimitError,
    litellm_exceptions.Timeout,
    litellm_exceptions.APIConnectionError,
    litellm_exceptions.APIError,  # Usually covers 5xx
    litellm_exceptions.ServiceUnavailableError,
    litellm_exceptions.NotFoundError,  # 404
    litellm_exceptions.AuthenticationError, # 401/403 - we fall back, max_retries=0 prevents retry storm
    genai_errors.APIError,  # Catches native Google GenAI SDK errors (like QuotaFailure) that LiteLLM might miss
    httpx.HTTPError,  # Catches underlying transport/timeout errors
)

class NormalizedChatLiteLLM(ChatLiteLLM):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            return super()._generate(messages, stop, run_manager, **kwargs)
        except litellm_exceptions.BadRequestError as e:
            msg = getattr(e, "message", "") or str(e)
            
            # Genuine 400 errors like malformed requests should bubble up
            if "Requests ending with a model turn" in msg or "INVALID_ARGUMENT" in msg:
                raise e
                
            # If it's not a known genuine 400, or it explicitly mentions quota/rate limits, 
            # we normalize it to a RateLimitError to trigger our fallback.
            if "quota" in msg.lower() or "429" in msg or "too many requests" in msg.lower():
                raise litellm_exceptions.RateLimitError(
                    message=msg,
                    llm_provider=getattr(e, "llm_provider", "gemini"),
                    model=getattr(e, "model", self.model)
                ) from e
                
            # For any other unknown 400s, raise as is (fail the transaction)
            raise e
            
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            return await super()._agenerate(messages, stop, run_manager, **kwargs)
        except litellm_exceptions.BadRequestError as e:
            msg = getattr(e, "message", "") or str(e)
            if "Requests ending with a model turn" in msg or "INVALID_ARGUMENT" in msg:
                raise e
            if "quota" in msg.lower() or "429" in msg or "too many requests" in msg.lower():
                raise litellm_exceptions.RateLimitError(
                    message=msg,
                    llm_provider=getattr(e, "llm_provider", "gemini"),
                    model=getattr(e, "model", self.model)
                ) from e
            raise e

def _instantiate_model(cfg: ModelConfig) -> ChatLiteLLM:
    """Helper to instantiate a ChatLiteLLM based on ModelConfig and environment."""
    api_key = None
    api_base = None

    if cfg.provider.lower() == "gemini":
        api_key = settings.LLM_API_KEY
    elif cfg.provider.lower() == "openrouter":
        api_key = settings.OPENROUTER_API_KEY

    kwargs = {
        "model": cfg.litellm_model_name,
        "temperature": 0.0,
        "max_retries": 0,  # For langchain tenacity
        "num_retries": 0,  # For litellm native retries
        "timeout": 30, # Fail fast so fallback happens before Cloud Run 504
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    return NormalizedChatLiteLLM(**kwargs)

def get_chat_model(required_capabilities: List[Capability] = None) -> BaseChatModel:
    """
    Returns a LangChain BaseChatModel configured with strict prioritized fallbacks,
    adhering to the registry priorities.
    """
    if required_capabilities is None:
        required_capabilities = []

    # 1. Fetch eligible models sorted by priority
    eligible_configs = []
    
    # Sort all registry models by priority
    sorted_registry = sorted(MODEL_REGISTRY, key=lambda x: x.priority)
    
    for cfg in sorted_registry:
        # Filter free-only
        if not cfg.is_free and not settings.ALLOW_PAID_LLM:
            continue
            
        # Filter required capabilities
        if not all(cap in cfg.capabilities for cap in required_capabilities):
            continue
            
        eligible_configs.append(cfg)

    if not eligible_configs:
        raise ValueError(f"No suitable model found for capabilities: {required_capabilities}")

    # 2. Instantiate all models with max_retries=0
    llms = [_instantiate_model(cfg) for cfg in eligible_configs]
    
    primary_llm = llms[0]
    fallbacks = llms[1:]
    
    if fallbacks:
        return primary_llm.with_fallbacks(
            fallbacks,
            exceptions_to_handle=FALLBACK_EXCEPTIONS
        )
    
    return primary_llm
