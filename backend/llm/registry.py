from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel

class Capability(str, Enum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"

class ModelConfig(BaseModel):
    provider: str
    model: str
    priority: int = 99
    is_free: bool = True
    capabilities: List[Capability] = []
    litellm_model_name: str 
    required_env: str = ""

# Hardcoded registry of known models
MODEL_REGISTRY: List[ModelConfig] = [
    # GEMINI MODELS
    ModelConfig(
        provider="gemini",
        model="gemini-3.7-flash",
        priority=1,
        is_free=True,
        capabilities=[Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT],
        litellm_model_name="gemini/gemini-3.7-flash",
        required_env="LLM_API_KEY"
    ),
    ModelConfig(
        provider="gemini",
        model="gemini-3.6-flash",
        priority=2,
        is_free=True,
        capabilities=[Capability.TOOL_CALLING, Capability.VISION],
        litellm_model_name="gemini/gemini-3.6-flash",
        required_env="LLM_API_KEY"
    ),
    ModelConfig(
        provider="gemini",
        model="gemini-3.5-flash",
        priority=3,
        is_free=True,
        capabilities=[Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT],
        litellm_model_name="gemini/gemini-3.5-flash",
        required_env="LLM_API_KEY"
    ),
    # OPENROUTER MODELS
    ModelConfig(
        provider="openrouter",
        model="nemotron-3-ultra-550b-a55b:free",
        priority=4,
        is_free=True,
        capabilities=[Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT],
        litellm_model_name="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
        required_env="OPENROUTER_API_KEY"
    ),
]

def get_model_config(provider: str, model: str = None) -> Optional[ModelConfig]:
    for cfg in MODEL_REGISTRY:
        if cfg.provider.lower() == provider.lower():
            if model is None or cfg.model.lower() == model.lower():
                return cfg
    return None

def find_models_with_capabilities(provider: str, capabilities: List[Capability]) -> List[ModelConfig]:
    matches = []
    for cfg in MODEL_REGISTRY:
        if cfg.provider.lower() == provider.lower():
            if all(cap in cfg.capabilities for cap in capabilities):
                matches.append(cfg)
    return matches
