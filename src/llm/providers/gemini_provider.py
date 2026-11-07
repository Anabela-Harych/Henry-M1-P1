import httpx2
from google import genai
from google.genai import errors, types
from typing import Any

from src.llm.config import LLMConfig
from src.llm.errors import ProviderCallError
from src.llm.models import ProviderOutput


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _looks_like_quota_exhaustion(message: str) -> bool:
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in ("billing", "insufficient_quota", "quota exceeded", "daily quota")
    )


class GeminiProvider:
    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = genai.Client(
            api_key=config.api_key,
            http_options=types.HttpOptions(
                timeout=int(config.timeout_seconds * 1000),
                # Keep provider-side retries off; LLMClient owns the retry budget.
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
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
        try:
            response = self._client.models.generate_content(
                model=self._config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=self._config.gemini_thinking_level,
                    ),
                    response_mime_type="application/json",
                    response_json_schema=response_schema,
                ),
            )
        except httpx2.TimeoutException as error:
            raise ProviderCallError(
                "gemini", "timeout", "Gemini agotó el tiempo de espera.", retryable=True
            ) from error
        except httpx2.TransportError as error:
            raise ProviderCallError(
                "gemini", "connection", "No se pudo conectar con Gemini.", retryable=True
            ) from error
        except errors.APIError as error:
            status_code = getattr(error, "code", None)
            provider_message = str(getattr(error, "message", "") or "")
            retryable = (
                status_code in RETRYABLE_STATUS_CODES
                and not _looks_like_quota_exhaustion(provider_message)
            )
            kind = "rate_limit" if status_code == 429 else "provider_status"
            raise ProviderCallError(
                "gemini",
                kind,
                f"Gemini devolvió un error HTTP {status_code or 'desconocido'}.",
                retryable=retryable,
                status_code=status_code if isinstance(status_code, int) else None,
            ) from error

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None)
        candidate_tokens = getattr(usage, "candidates_token_count", None)
        thought_tokens = getattr(usage, "thoughts_token_count", 0) or 0
        output_tokens = (
            candidate_tokens + thought_tokens if candidate_tokens is not None else None
        )
        candidates = getattr(response, "candidates", None) or []
        finish_reason = getattr(candidates[0], "finish_reason", None) if candidates else None
        if finish_reason is not None:
            finish_reason = getattr(finish_reason, "name", None) or str(finish_reason)
        return ProviderOutput(
            text=response.text or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_id=getattr(response, "response_id", None),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
        )
