from typing import Any, Protocol

from src.llm.models import ProviderOutput


class LLMProvider(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str,
        response_schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int,
    ) -> ProviderOutput:
        """Generate text and return provider usage metadata when available."""
