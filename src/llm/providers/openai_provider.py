from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError

from src.llm.config import LLMConfig
from src.llm.errors import ProviderCallError
from src.llm.models import ProviderOutput


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
NON_RETRYABLE_QUOTA_CODES = {
    "billing_hard_limit_exceeded",
    "insufficient_quota",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
}


def _retry_after_seconds(error: APIStatusError) -> float | None:
    raw_value = error.response.headers.get("retry-after")
    if not raw_value:
        return None
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw_value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class OpenAIProvider:
    def __init__(self, config: LLMConfig, *, base_url: str | None = None) -> None:
        self._config = config
        # Retries are handled once by LLMClient so the total attempt limit is clear.
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=base_url,
            timeout=config.timeout_seconds,
            max_retries=0,
        )

    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str,
        response_schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int,
    ) -> ProviderOutput:
        provider = self._config.provider
        provider_name = "Groq" if provider == "groq" else "OpenAI"
        text_config: dict[str, Any] = {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": response_schema,
            },
        }
        request_options: dict[str, Any] = {}
        if provider == "openai":
            text_config["verbosity"] = "low"
        elif provider == "groq" and self._config.model == "openai/gpt-oss-20b":
            request_options["reasoning"] = {"effort": "low"}
        try:
            response = self._client.responses.create(
                model=self._config.model,
                instructions=system_instruction,
                input=prompt,
                max_output_tokens=max_output_tokens,
                text=text_config,
                **request_options,
            )
        except APITimeoutError as error:
            raise ProviderCallError(
                provider, "timeout", f"{provider_name} agotó el tiempo de espera.", retryable=True
            ) from error
        except APIConnectionError as error:
            raise ProviderCallError(
                provider, "connection", f"No se pudo conectar con {provider_name}.", retryable=True
            ) from error
        except APIStatusError as error:
            status_code = error.status_code
            error_code = str(getattr(error, "code", "") or "").lower()
            retryable = status_code in RETRYABLE_STATUS_CODES and (
                error_code not in NON_RETRYABLE_QUOTA_CODES
            )
            kind = "rate_limit" if status_code == 429 else "provider_status"
            raise ProviderCallError(
                provider,
                kind,
                f"{provider_name} devolvió un error HTTP {status_code}.",
                retryable=retryable,
                status_code=status_code,
                retry_after_seconds=_retry_after_seconds(error),
            ) from error
        except OpenAIError as error:
            raise ProviderCallError(
                provider, "provider_error", f"{provider_name} no pudo completar la solicitud."
            ) from error

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        incomplete_details = getattr(response, "incomplete_details", None)
        finish_reason = getattr(incomplete_details, "reason", None)
        if finish_reason is None and getattr(response, "status", None) != "completed":
            finish_reason = getattr(response, "status", None)
        return ProviderOutput(
            text=response.output_text or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_id=getattr(response, "id", None),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
        )
