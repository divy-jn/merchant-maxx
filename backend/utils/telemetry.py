import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

class AgentTelemetryHandler(BaseCallbackHandler):
    """Safely logs execution metrics without exposing sensitive data."""
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.start_times: Dict[UUID, float] = {}

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], *, run_id: UUID, parent_run_id: Optional[UUID] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Any:
        self.start_times[run_id] = time.perf_counter()
        
    def on_llm_end(
        self, response: LLMResult, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any
    ) -> Any:
        duration_ms = (time.perf_counter() - self.start_times.pop(run_id, time.perf_counter())) * 1000
        llm_output = response.llm_output or {}
        model_name = llm_output.get("model_name", "unknown")
        token_usage = llm_output.get("token_usage", {})
        
        logger.info(
            f"TELEMETRY | conv={self.conversation_id} | model={model_name} | "
            f"tokens_in={token_usage.get('prompt_tokens', 0)} | "
            f"tokens_out={token_usage.get('completion_tokens', 0)} | "
            f"duration={duration_ms:.2f}ms"
        )

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any
    ) -> Any:
        duration_ms = (time.perf_counter() - self.start_times.pop(run_id, time.perf_counter())) * 1000
        logger.warning(
            f"TELEMETRY ERROR | conv={self.conversation_id} | duration={duration_ms:.2f}ms | error={type(error).__name__}"
        )
