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
    is_free: bool = True
    capabilities: List[Capability] = []
    # If the provider needs a specific litellm alias (like ollama/gpt-oss or gemini/gemini-1.5)
    litellm_model_name: str 

# Hardcoded registry of known models
MODEL_REGISTRY: List[ModelConfig] = [
    # OLLAMA CLOUD MODELS
    ModelConfig(
        provider="ollama",
        model="gpt-oss:120b-cloud",
        is_free=True,
        capabilities=[Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT],
        litellm_model_name="ollama/gpt-oss:120b-cloud"
    ),
    # GEMINI MODELS
    ModelConfig(
        provider="gemini",
        model="gemini-3.6-flash",
        is_free=True,  # Assuming generous free tier
        capabilities=[Capability.TOOL_CALLING, Capability.VISION],
        litellm_model_name="gemini/gemini-3.6-flash"
    ),
    ModelConfig(
        provider="gemini",
        model="text-embedding-004",
        is_free=True,
        capabilities=[Capability.EMBEDDINGS],
        litellm_model_name="gemini/text-embedding-004"
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
