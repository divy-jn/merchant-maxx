import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

class AgentTelemetryHandler(BaseCallbackHandler):
    """Safely logs execution timings and usage metrics without exposing payloads."""
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.start_times: Dict[UUID, float] = {}
        self.run_names: Dict[UUID, str] = {}
        self.root_run_id: Optional[UUID] = None
        self.root_started_at: Optional[float] = None
        self.llm_calls = 0
        self.llm_errors = 0
        self.tool_calls = 0
        self.tool_errors = 0

    @staticmethod
    def _name(serialized: Optional[Dict[str, Any]], fallback: str) -> str:
        if not serialized:
            return fallback
        if serialized.get("name"):
            return str(serialized["name"])
        identifiers = serialized.get("id")
        if isinstance(identifiers, list) and identifiers:
            return str(identifiers[-1])
        return fallback

    def _start(self, run_id: UUID, kind: str, name: str) -> None:
        self.start_times[run_id] = time.perf_counter()
        self.run_names[run_id] = name
        logger.info("TELEMETRY_START | conv=%s | kind=%s | name=%s", self.conversation_id, kind, name)

    def _finish(self, run_id: UUID, kind: str, fallback: str) -> float:
        duration_ms = (time.perf_counter() - self.start_times.pop(run_id, time.perf_counter())) * 1000
        name = self.run_names.pop(run_id, fallback)
        logger.info("TELEMETRY_END | conv=%s | kind=%s | name=%s | duration_ms=%.2f", self.conversation_id, kind, name, duration_ms)
        return duration_ms

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        if parent_run_id is None and self.root_run_id is None:
            self.root_run_id = run_id
            self.root_started_at = time.perf_counter()
        self._start(run_id, "chain", self._name(serialized, "chain"))

    def on_chain_end(self, outputs: Dict[str, Any], *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        self._finish(run_id, "chain", "chain")
        if run_id == self.root_run_id and self.root_started_at is not None:
            total_ms = (time.perf_counter() - self.root_started_at) * 1000
            logger.info("TELEMETRY_REQUEST | conv=%s | total_ms=%.2f | llm_calls=%d | llm_errors=%d | tool_calls=%d | tool_errors=%d", self.conversation_id, total_ms, self.llm_calls, self.llm_errors, self.tool_calls, self.tool_errors)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        duration_ms = self._finish(run_id, "chain_error", "chain")
        logger.warning("TELEMETRY_CHAIN_ERROR | conv=%s | duration_ms=%.2f | error=%s", self.conversation_id, duration_ms, type(error).__name__)

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        self.llm_calls += 1
        self._start(run_id, "llm", self._name(serialized, "llm"))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        duration_ms = self._finish(run_id, "llm", "llm")
        llm_output = response.llm_output or {}
        model_name = llm_output.get("model_name", "unknown")
        token_usage = llm_output.get("token_usage", {}) or {}
        logger.info("TELEMETRY_LLM | conv=%s | model=%s | tokens_in=%s | tokens_out=%s | duration_ms=%.2f", self.conversation_id, model_name, token_usage.get("prompt_tokens", 0), token_usage.get("completion_tokens", 0), duration_ms)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        self.llm_errors += 1
        duration_ms = self._finish(run_id, "llm_error", "llm")
        logger.warning("TELEMETRY_LLM_ERROR | conv=%s | duration_ms=%.2f | error=%s", self.conversation_id, duration_ms, type(error).__name__)

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        self.tool_calls += 1
        self._start(run_id, "tool", self._name(serialized, "tool"))

    def on_tool_end(self, output: Any, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        self._finish(run_id, "tool", "tool")

    def on_tool_error(self, error: BaseException, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        self.tool_errors += 1
        duration_ms = self._finish(run_id, "tool_error", "tool")
        logger.warning("TELEMETRY_TOOL_ERROR | conv=%s | duration_ms=%.2f | error=%s", self.conversation_id, duration_ms, type(error).__name__)
