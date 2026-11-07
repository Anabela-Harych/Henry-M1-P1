from pydantic import ValidationError

from src.llm.client import LLMClient
from src.llm.errors import InvalidStructuredResponse
from src.llm.models import GenerationResult
from src.schemas import SupportResponse


class SupportService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def respond(self, query: str) -> tuple[SupportResponse, GenerationResult]:
        generation = self._llm_client.generate(
            query,
            response_schema=SupportResponse.model_json_schema(),
            schema_name="nubbix_support_response",
        )
        try:
            response = SupportResponse.model_validate_json(generation.text)
        except ValidationError as error:
            issues = [
                {
                    "field": ".".join(str(part) for part in item["loc"]) or "$",
                    "issue": item["type"],
                }
                for item in error.errors(include_input=False)[:8]
            ]
            if generation.finish_reason:
                issues.append(
                    {"field": "$", "issue": f"finish_reason:{generation.finish_reason}"}
                )
            self._llm_client.record_contract_failure(generation, issues)
            raise InvalidStructuredResponse(
                "El proveedor devolvió una respuesta que no cumple el contrato.",
                issues,
            ) from error
        return response, generation
