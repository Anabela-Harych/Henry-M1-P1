import os
from dataclasses import dataclass
from math import isfinite

from src.llm.errors import LLMConfigurationError


@dataclass(frozen=True)
class PriceRates:
    input_usd_per_million: float
    output_usd_per_million: float
    source: str


# Paid Standard text rates, verified 2026-11-07. These are estimates and may
# differ by account tier, processing mode, context length, or future price changes.
# Official sources:
# https://developers.openai.com/api/docs/models/gpt-6-luna
# https://ai.google.dev/gemini-api/docs/pricing
# https://console.groq.com/docs/models
DEFAULT_RATES = {
    ("openai", "gpt-6-luna"): (0.10, 0.50),
    ("gemini", "gemini-3.6-flash"): (0.75, 3.75),
    ("groq", "openai/gpt-oss-20b"): (0.075, 0.30),
}


def _optional_price(name: str) -> float | None:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return None
    try:
        value = float(raw_value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} debe ser un precio numérico.") from error
    if not isfinite(value) or value < 0:
        raise LLMConfigurationError(f"{name} debe ser un precio finito y no negativo.")
    return value


def price_rates_for(provider: str, model: str) -> PriceRates | None:
    prefix = provider.upper()
    input_override = _optional_price(f"{prefix}_INPUT_USD_PER_MILLION_TOKENS")
    output_override = _optional_price(f"{prefix}_OUTPUT_USD_PER_MILLION_TOKENS")
    defaults = DEFAULT_RATES.get((provider, model))

    if defaults is None and (input_override is None or output_override is None):
        return None

    input_rate = input_override if input_override is not None else defaults[0]
    output_rate = output_override if output_override is not None else defaults[1]
    source = (
        "env_override"
        if input_override is not None or output_override is not None
        else "official_paid_standard_rate_card_2026-11-07"
    )
    return PriceRates(input_rate, output_rate, source)


def estimate_cost_usd(
    input_tokens: int | None,
    output_tokens: int | None,
    rates: PriceRates | None,
) -> float | None:
    if input_tokens is None or output_tokens is None or rates is None:
        return None

    cost = (
        input_tokens * rates.input_usd_per_million
        + output_tokens * rates.output_usd_per_million
    ) / 1_000_000
    return round(cost, 10)
