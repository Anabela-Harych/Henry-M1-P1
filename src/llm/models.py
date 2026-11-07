from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderOutput:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    finish_reason: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    provider: str
    model: str
    prompt_id: str
    text: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: float
    attempts: int
    estimated_cost_usd: float | None
    cost_basis: str | None
    request_id: str | None
    finish_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
