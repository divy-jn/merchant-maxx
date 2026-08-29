import logging
from typing import List, Optional
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.language_models.chat_models import BaseChatModel

from config import settings
from llm.registry import get_model_config, find_models_with_capabilities, Capability, ModelConfig

logger = logging.getLogger(__name__)

def _instantiate_model(cfg: ModelConfig) -> ChatLiteLLM:
    """Helper to instantiate a ChatLiteLLM based on ModelConfig and environment."""
    api_key = None
    api_base = None

    if cfg.provider.lower() == "ollama":
        api_key = settings.OLLAMA_API_KEY
        api_base = settings.OLLAMA_BASE_URL
    elif cfg.provider.lower() == "gemini":
        api_key = settings.LLM_API_KEY
    
    # We pass custom api_base if defined, else litellm handles it
    kwargs = {
        "model": cfg.litellm_model_name,
        "temperature": 0.0,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
        # LiteLLM needs custom_llm_provider for some custom bases if it's not a known prefix
        # but the prefix "ollama/" usually hints litellm.
        if cfg.provider.lower() == "ollama" and api_base:
            kwargs["custom_llm_provider"] = "openai" # Often ollama cloud exposes openai-compatible endpoints

    return ChatLiteLLM(**kwargs)

def get_chat_model(required_capabilities: List[Capability] = None) -> BaseChatModel:
    """
    Returns a LangChain BaseChatModel configured with fallbacks,
    adhering to the environment-driven primary and fallback providers.
    """
    if required_capabilities is None:
        required_capabilities = []

    # 1. Evaluate Primary Model
    primary_provider = settings.LLM_PRIMARY_PROVIDER
    primary_model_name = settings.LLM_PRIMARY_MODEL
    
    primary_cfg = get_model_config(primary_provider, primary_model_name)
    if not primary_cfg:
        # If specific model isn't found, find any model in the provider with capabilities
        matches = find_models_with_capabilities(primary_provider, required_capabilities)
        if matches:
            primary_cfg = matches[0]

    # Check free/paid constraint
    if primary_cfg and not primary_cfg.is_free and not settings.ALLOW_PAID_LLM:
        logger.warning(f"Primary model {primary_cfg.model} is paid, but ALLOW_PAID_LLM is false. Skipping.")
        primary_cfg = None

    # Verify capabilities
    if primary_cfg and not all(cap in primary_cfg.capabilities for cap in required_capabilities):
        logger.warning(f"Primary model {primary_cfg.model} lacks capabilities {required_capabilities}. Skipping.")
        primary_cfg = None

    # 2. Evaluate Fallbacks
    fallbacks = []
    fallback_providers = [p.strip() for p in settings.LLM_FALLBACK_PROVIDERS.split(",") if p.strip()]
    
    for fb_provider in fallback_providers:
        matches = find_models_with_capabilities(fb_provider, required_capabilities)
        for fb_cfg in matches:
            if not fb_cfg.is_free and not settings.ALLOW_PAID_LLM:
                continue
            fallbacks.append(fb_cfg)
            break # Just take the first valid model from this fallback provider

    if not primary_cfg and not fallbacks:
        raise ValueError(f"No suitable model found for capabilities: {required_capabilities}")

    # If primary is invalid, promote first fallback
    if not primary_cfg:
        primary_cfg = fallbacks.pop(0)

    # Instantiate
    primary_llm = _instantiate_model(primary_cfg)
    
    if fallbacks:
        fallback_llms = [_instantiate_model(cfg) for cfg in fallbacks]
        return primary_llm.with_fallbacks(fallback_llms)
    
    return primary_llm
