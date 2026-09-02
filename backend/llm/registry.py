from enum import Enum

class Capability(str, Enum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
