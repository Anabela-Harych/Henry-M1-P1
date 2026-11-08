import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.llm.client import LLMClient
from src.llm.config import LLMConfig
from src.llm.factory import build_provider
from src.service import SupportService


class ProviderIntegrationTest(unittest.TestCase):
    def test_providers_return_the_same_contract_and_usage(self):
        # Comprueba el mismo contrato y consumo normalizado en los tres proveedores.
        payload = {
            "answer": "Revisá el acceso a tu cuenta.",
            "confidence": 0.8,
            "category": "account",
            "actions": [],
        }
        text = json.dumps(payload)
        with (
            patch("src.llm.providers.openai_provider.OpenAI") as openai,
            patch("src.llm.providers.gemini_provider.genai.Client") as gemini,
            patch("src.llm.client.append_usage_event"),
        ):
            openai_request = openai.return_value.responses.create
            openai_request.return_value = SimpleNamespace(
                output_text=text, status="completed",
                usage=SimpleNamespace(input_tokens=20, output_tokens=10),
            )
            groq_client = Mock()
            groq_request = groq_client.responses.create
            groq_request.return_value = openai_request.return_value
            openai.side_effect = [openai.return_value, groq_client]
            gemini_request = gemini.return_value.models.generate_content
            gemini_request.return_value = SimpleNamespace(
                text=text,
                usage_metadata=SimpleNamespace(
                    prompt_token_count=20, candidates_token_count=7, thoughts_token_count=3
                ),
            )
            providers = (
                ("openai", "test-model", openai_request),
                ("gemini", "test-model", gemini_request),
                ("groq", "openai/gpt-oss-20b", groq_request),
            )
            for provider, model, request in providers:
                with self.subTest(provider=provider):
                    config = LLMConfig(provider, model, "test-key", "v1", "test")
                    service = SupportService(LLMClient(config, build_provider(config)))
                    response, usage = service.respond("No puedo acceder a mi cuenta")

                    request.assert_called_once()
                    self.assertEqual(response.model_dump(), payload)
                    self.assertEqual((usage.input_tokens, usage.output_tokens), (20, 10))
                    self.assertEqual(usage.provider, provider)

            self.assertEqual(openai.call_args.kwargs["base_url"], "https://api.groq.com/openai/v1")
            self.assertTrue(groq_request.call_args.kwargs["text"]["format"]["strict"])
            self.assertNotIn("verbosity", groq_request.call_args.kwargs["text"])
