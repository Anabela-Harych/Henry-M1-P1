import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src.llm.errors import LLMConfigurationError
from src.llm.prompt_loader import load_prompt


SUPPORTED_PROVIDERS = ("openai", "gemini", "groq")
DEFAULT_MAX_OUTPUT_TOKENS = 256
DEFAULT_USAGE_LOG_PATH = Path("data/metrics.jsonl")


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str = field(repr=False)
    prompt_id: str
    system_instruction: str
    timeout_seconds: float = 30.0
    gemini_thinking_level: str = "minimal"
    max_retries: int = 1
    retry_base_delay_seconds: float = 0.5
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    usage_log_path: Path = DEFAULT_USAGE_LOG_PATH


def normalize_provider(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "google":
        normalized = "gemini"
    if normalized not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise LLMConfigurationError(
            f"Proveedor '{value}' no soportado. Opciones: {supported}."
        )
    return normalized


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} debe ser un número.") from error
    if value < minimum:
        raise LLMConfigurationError(f"{name} debe ser mayor o igual a {minimum}.")
    return value


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} debe ser un número entero.") from error
    if not minimum <= value <= maximum:
        raise LLMConfigurationError(
            f"{name} debe estar entre {minimum} y {maximum}."
        )
    return value


def _configured_models() -> dict[str, str]:
    models: dict[str, str] = {}
    for slot in ("A", "B"):
        provider = os.getenv(f"MODEL_{slot}_PROVIDER", "").strip()
        model = os.getenv(f"MODEL_{slot}_NAME", "").strip()
        if provider and model:
            models[normalize_provider(provider)] = model

    # Provider-specific names support the existing .env configuration as well.
    for provider, env_name in (
        ("openai", "OPENAI_MODEL"),
        ("gemini", "GEMINI_MODEL"),
        ("gemini", "GOOGLE_MODEL"),
        ("groq", "GROQ_MODEL"),
    ):
        model = os.getenv(env_name, "").strip()
        if model:
            models[provider] = model
    return models


def _api_key_for(provider: str) -> str:
    names = {
        "openai": ("OPENAI_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "groq": ("GROQ_API_KEY",),
    }[provider]

    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    expected = " o ".join(names)
    raise LLMConfigurationError(
        f"Falta la clave API para {provider}. Configurá {expected} en .env."
    )


def load_config(
    *,
    provider_override: str | None = None,
    model_override: str | None = None,
    prompt_path_override: str | Path | None = None,
    timeout_override: float | None = None,
    retries_override: int | None = None,
    max_output_tokens_override: int | None = None,
) -> LLMConfig:
    load_dotenv(override=False)

    configured_default = (
        os.getenv("LLM_PROVIDER", "").strip()
        or os.getenv("MODEL_A_PROVIDER", "").strip()
        or "openai"
    )
    provider = normalize_provider(provider_override or configured_default)
    model = (model_override or _configured_models().get(provider, "")).strip()
    if not model:
        raise LLMConfigurationError(
            f"Falta el modelo para {provider}. Configurá {provider.upper()}_MODEL "
            f"o un par MODEL_A/MODEL_B en .env."
        )

    timeout = (
        timeout_override
        if timeout_override is not None
        else _env_float("LLM_TIMEOUT_SECONDS", 30.0, minimum=1.0)
    )
    if timeout < 1.0 or timeout > 300.0:
        raise LLMConfigurationError("El timeout debe estar entre 1 y 300 segundos.")

    gemini_thinking_level = os.getenv("GEMINI_THINKING_LEVEL", "minimal").strip().lower()
    if gemini_thinking_level not in {"minimal", "low", "medium", "high"}:
        raise LLMConfigurationError(
            "GEMINI_THINKING_LEVEL debe ser minimal, low, medium o high."
        )

    retries = (
        retries_override
        if retries_override is not None
        else _env_int("LLM_MAX_RETRIES", 1, minimum=0, maximum=5)
    )
    if not 0 <= retries <= 5:
        raise LLMConfigurationError("Los reintentos deben estar entre 0 y 5.")

    output_limit = (
        max_output_tokens_override
        if max_output_tokens_override is not None
        else _env_int("LLM_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS, minimum=1, maximum=8192)
    )
    if not 1 <= output_limit <= 8192:
        raise LLMConfigurationError("Los tokens de salida deben estar entre 1 y 8192.")

    prompt_path = Path(
        prompt_path_override
        or os.getenv("LLM_PROMPT_PATH", "prompts/v1_1_scope.yaml").strip()
    )
    prompt = load_prompt(prompt_path)

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=_api_key_for(provider),
        prompt_id=prompt.prompt_id,
        system_instruction=prompt.system_instruction,
        timeout_seconds=timeout,
        gemini_thinking_level=gemini_thinking_level,
        max_retries=retries,
        retry_base_delay_seconds=_env_float(
            "LLM_RETRY_BASE_DELAY_SECONDS", 0.5, minimum=0.0
        ),
        max_output_tokens=output_limit,
        usage_log_path=Path(
            os.getenv("LLM_USAGE_LOG_PATH", "").strip() or DEFAULT_USAGE_LOG_PATH
        ),
    )
