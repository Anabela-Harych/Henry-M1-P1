from pydantic import ValidationError

from src.input_guard import check_query
from src.llm.client import LLMClient
from src.llm.errors import InvalidStructuredResponse
from src.llm.models import GenerationResult, ProviderOutput
from src.schemas import SupportResponse


class SupportService:
    def __init__(self, llm_client: LLMClient, *, retry_invalid_response: bool = True) -> None:
        self._llm_client = llm_client
        self._retry_invalid_response = retry_invalid_response

    def respond(self, query: str) -> tuple[SupportResponse, GenerationResult]:
        check_query(query)
        return self._llm_client.generate(
            query,
            response_schema=SupportResponse.model_json_schema(),
            schema_name="nubbix_support_response",
            parse_response=self._parse_response,
            category_of=lambda response: response.category,
            retry_invalid_response=self._retry_invalid_response,
        )

    @staticmethod
    def _parse_response(output: ProviderOutput) -> SupportResponse:
        try:
            return SupportResponse.model_validate_json(output.text)
        except ValidationError as error:
            issues = [
                {
                    "field": ".".join(str(part) for part in item["loc"]) or "$",
                    "issue": item["type"],
                }
                for item in error.errors(include_input=False)[:8]
            ]
            if output.finish_reason:
                issues.append(
                    {"field": "$", "issue": f"finish_reason:{output.finish_reason}"}
                )
            raise InvalidStructuredResponse(
                "El proveedor devolvió una respuesta que no cumple el contrato.",
                issues,
            ) from error
