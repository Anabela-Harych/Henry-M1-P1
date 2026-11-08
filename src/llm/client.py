import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

from src.llm.config import LLMConfig
from src.llm.errors import EmptyQueryError, InvalidStructuredResponse, ProviderCallError
from src.llm.models import GenerationResult, ProviderOutput
from src.llm.pricing import estimate_cost_usd, price_rates_for
from src.llm.providers.base import LLMProvider
from src.llm.telemetry import append_usage_event, redact_ticket


MAX_RETRY_DELAY_SECONDS = 8.0
ResponseT = TypeVar("ResponseT")


class LLMClient:
    def __init__(self, config: LLMConfig, provider: LLMProvider) -> None:
        self._config = config
        self._provider = provider
        self._rates = price_rates_for(config.provider, config.model)

    def generate(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any],
        schema_name: str,
        parse_response: Callable[[ProviderOutput], ResponseT],
        category_of: Callable[[ResponseT], str] | None = None,
        system_instruction: str | None = None,
        prompt_id: str | None = None,
        retry_invalid_response: bool = True,
    ) -> tuple[ResponseT, GenerationResult]:
        if not prompt.strip():
            raise EmptyQueryError("La consulta no puede estar vacía.")

        started_at = time.perf_counter()
        attempts = 0
        last_output: ProviderOutput | None = None
        input_tokens: int | None = 0
        output_tokens: int | None = 0
        failure: InvalidStructuredResponse | ProviderCallError | None = None
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
            except ProviderCallError as error:
                if self._should_retry(error, attempts):
                    time.sleep(self._retry_delay(error, attempts))
                    continue
                failure = error
                break

            last_output = provider_output
            input_tokens = (
                input_tokens + provider_output.input_tokens
                if input_tokens is not None and provider_output.input_tokens is not None
                else None
            )
            output_tokens = (
                output_tokens + provider_output.output_tokens
                if output_tokens is not None and provider_output.output_tokens is not None
                else None
            )
            try:
                response = parse_response(provider_output)
            except InvalidStructuredResponse as error:
                if retry_invalid_response and attempts <= self._config.max_retries:
                    retry_invalid_response = False
                    continue
                failure = error
            break

        if last_output is None:
            input_tokens = output_tokens = None
        estimated_cost = estimate_cost_usd(input_tokens, output_tokens, self._rates)
        applied_rates = self._rates if estimated_cost is not None else None
        result = GenerationResult(
            provider=self._config.provider,
            model=self._config.model,
            prompt_id=prompt_id or self._config.prompt_id,
            text=last_output.text if last_output else "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(
                input_tokens + output_tokens
                if input_tokens is not None and output_tokens is not None
                else None
            ),
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            attempts=attempts,
            estimated_cost_usd=estimated_cost,
            cost_basis=applied_rates.source if applied_rates else None,
            request_id=last_output.request_id if last_output else None,
            finish_reason=last_output.finish_reason if last_output else None,
            input_usd_per_million=applied_rates.input_usd_per_million if applied_rates else None,
            output_usd_per_million=applied_rates.output_usd_per_million if applied_rates else None,
        )
        category = category_of(response) if failure is None and category_of is not None else None
        self._record_usage(result, failure, query=prompt, category=category)
        if failure is not None:
            failure.generation = result
            raise failure
        return response, result

    def _record_usage(
        self,
        result: GenerationResult,
        failure: InvalidStructuredResponse | ProviderCallError | None,
        *,
        query: str,
        category: str | None,
    ) -> None:
        status: dict[str, Any] = {"status": "success"}
        if isinstance(failure, InvalidStructuredResponse):
            status = {
                "status": "invalid_contract",
                "error_type": "invalid_structured_response",
                "validation_issues": failure.issues,
            }
        elif isinstance(failure, ProviderCallError):
            status = {
                "status": "error",
                "error_type": failure.kind,
                "status_code": failure.status_code,
            }
        append_usage_event(
            self._config.usage_log_path,
            {
                "provider": result.provider,
                "model": result.model,
                "prompt_id": result.prompt_id,
                **status,
                "text": redact_ticket(query, self._config.api_key),
                "category": category,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "latency_ms": result.latency_ms,
                "latency_s": result.latency_ms / 1000,
                "attempts": result.attempts,
                "estimated_cost_usd": result.estimated_cost_usd,
                "cost_basis": result.cost_basis,
                "input_usd_per_million": result.input_usd_per_million,
                "output_usd_per_million": result.output_usd_per_million,
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
