import random
import time
from typing import Any

from src.llm.config import LLMConfig
from src.llm.errors import ProviderCallError
from src.llm.models import GenerationResult
from src.llm.pricing import estimate_cost_usd
from src.llm.providers.base import LLMProvider
from src.llm.telemetry import append_usage_event


MAX_RETRY_DELAY_SECONDS = 8.0


class LLMClient:
    def __init__(self, config: LLMConfig, provider: LLMProvider) -> None:
        self._config = config
        self._provider = provider

    def generate(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any],
        schema_name: str,
        system_instruction: str | None = None,
        prompt_id: str | None = None,
    ) -> GenerationResult:
        if not prompt.strip():
            raise ValueError("La consulta no puede estar vacía.")

        started_at = time.perf_counter()
        attempts = 0
        while True:
            attempts += 1
            try:
                provider_output = self._provider.generate(
                    prompt,
                    system_instruction=system_instruction or self._config.system_instruction,
                    response_schema=response_schema,
                    schema_name=schema_name,
                    max_output_tokens=self._config.max_output_tokens,
                )
                latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                total_tokens = (
                    provider_output.input_tokens + provider_output.output_tokens
                    if provider_output.input_tokens is not None
                    and provider_output.output_tokens is not None
                    else None
                )
                estimated_cost, cost_basis = estimate_cost_usd(
                    self._config.provider,
                    self._config.model,
                    provider_output.input_tokens,
                    provider_output.output_tokens,
                )
                result = GenerationResult(
                    provider=self._config.provider,
                    model=self._config.model,
                    prompt_id=prompt_id or self._config.prompt_id,
                    text=provider_output.text,
                    input_tokens=provider_output.input_tokens,
                    output_tokens=provider_output.output_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    attempts=attempts,
                    estimated_cost_usd=estimated_cost,
                    cost_basis=cost_basis,
                    request_id=provider_output.request_id,
                    finish_reason=provider_output.finish_reason,
                )
                append_usage_event(
                    self._config.usage_log_path,
                    {
                        "provider": result.provider,
                        "model": result.model,
                        "prompt_id": result.prompt_id,
                        "status": "success",
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "total_tokens": result.total_tokens,
                        "latency_ms": result.latency_ms,
                        "attempts": result.attempts,
                        "estimated_cost_usd": result.estimated_cost_usd,
                        "cost_basis": result.cost_basis,
                        "request_id": result.request_id,
                        "finish_reason": result.finish_reason,
                    },
                )
                return result
            except ProviderCallError as error:
                if not self._should_retry(error, attempts):
                    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                    append_usage_event(
                        self._config.usage_log_path,
                        {
                            "provider": self._config.provider,
                            "model": self._config.model,
                            "prompt_id": prompt_id or self._config.prompt_id,
                            "status": "error",
                            "error_type": error.kind,
                            "status_code": error.status_code,
                            "latency_ms": latency_ms,
                            "attempts": attempts,
                            "estimated_cost_usd": None,
                            "cost_basis": None,
                        },
                    )
                    raise
                time.sleep(self._retry_delay(error, attempts))

    def record_contract_failure(
        self,
        result: GenerationResult,
        issues: list[dict[str, str]],
    ) -> None:
        append_usage_event(
            self._config.usage_log_path,
            {
                "provider": result.provider,
                "model": result.model,
                "prompt_id": result.prompt_id,
                "status": "invalid_contract",
                "error_type": "invalid_structured_response",
                "validation_issues": issues,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "estimated_cost_usd": result.estimated_cost_usd,
                "cost_basis": result.cost_basis,
                "request_id": result.request_id,
                "finish_reason": result.finish_reason,
            },
        )

    def _should_retry(self, error: ProviderCallError, attempts: int) -> bool:
        if not error.retryable or attempts > self._config.max_retries:
            return False
        if (
            error.retry_after_seconds is not None
            and error.retry_after_seconds > MAX_RETRY_DELAY_SECONDS
        ):
            return False
        return True

    def _retry_delay(self, error: ProviderCallError, attempts: int) -> float:
        exponential = min(
            self._config.retry_base_delay_seconds * (2 ** (attempts - 1)),
            MAX_RETRY_DELAY_SECONDS,
        )
        if error.retry_after_seconds is not None:
            exponential = max(exponential, error.retry_after_seconds)
        jitter = random.uniform(0.0, min(0.25, self._config.retry_base_delay_seconds))
        return min(exponential + jitter, MAX_RETRY_DELAY_SECONDS)
