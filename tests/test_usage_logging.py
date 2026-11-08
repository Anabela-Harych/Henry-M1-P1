import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.llm.client import LLMClient
from src.llm.config import LLMConfig
from src.llm.errors import InvalidStructuredResponse, ProviderCallError
from src.llm.models import ProviderOutput
from src.llm.providers.base import LLMProvider
from src.service import SupportService


class UsageLoggingTest(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.log_path = Path(directory) / "usage.jsonl"
        self.config = LLMConfig(
            provider="openai",
            model="test-model",
            api_key="test-key",
            prompt_id="test-prompt",
            system_instruction="test-instruction",
            usage_log_path=self.log_path,
        )
        self.provider = Mock(spec=LLMProvider)
        self.service = SupportService(LLMClient(self.config, self.provider))

    def read_event(self):
        records = self.log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(records), 1)
        return json.loads(records[0])

    def test_valid_response_after_retry_logs_one_success(self):
        self.provider.generate.side_effect = [
            ProviderCallError("openai", "connection", "simulated", retryable=True),
            ProviderOutput(
                '{"answer":"Review the invoice","confidence":0.8,"category":"billing","actions":[]}',
                input_tokens=20,
                output_tokens=10,
            ),
        ]
        query = "Duplicate charge. Contact: person@example.com. Password: secret"
        with patch("src.llm.client.time.sleep"):
            response, _ = self.service.respond(query)

        event = self.read_event()
        self.assertEqual(response.category, "billing")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["attempts"], 2)
        self.assertEqual(event["total_tokens"], 30)
        self.assertEqual(event["category"], "billing")
        self.assertEqual(event["latency_s"], event["latency_ms"] / 1000)
        self.assertEqual(event["text"], "Duplicate charge. Contact: [REDACTADO]. [REDACTADO]")
        self.assertEqual(self.provider.generate.call_args.args[0], query)

    def test_invalid_response_logs_its_usage_once(self):
        self.provider.generate.return_value = ProviderOutput(
            "Invalid JSON", input_tokens=20, output_tokens=10
        )
        with patch.dict(
            "os.environ",
            {
                "OPENAI_INPUT_USD_PER_MILLION_TOKENS": "0.25",
                "OPENAI_OUTPUT_USD_PER_MILLION_TOKENS": "0.75",
            },
        ):
            service = SupportService(
                LLMClient(replace(self.config, max_retries=3), self.provider)
            )
            with self.assertRaises(InvalidStructuredResponse) as caught:
                service.respond("Duplicate charge")

        event = self.read_event()
        self.assertEqual(event["status"], "invalid_contract")
        self.assertIsNone(event["category"])
        self.assertEqual(event["attempts"], 2)
        self.assertEqual(event["total_tokens"], 60)
        self.assertEqual(caught.exception.generation.total_tokens, 60)
        self.assertEqual(event["cost_basis"], "env_override")
        self.assertEqual(event["input_usd_per_million"], 0.25)
        self.assertEqual(event["output_usd_per_million"], 0.75)
        self.assertEqual(event["estimated_cost_usd"], 0.000025)
        reconstructed = (
            event["input_tokens"] * event["input_usd_per_million"]
            + event["output_tokens"] * event["output_usd_per_million"]
        ) / 1_000_000
        self.assertEqual(event["estimated_cost_usd"], round(reconstructed, 10))
        self.assertGreaterEqual(event["latency_ms"], 0)

    def test_invalid_then_valid_response_logs_combined_usage(self):
        self.provider.generate.side_effect = [
            ProviderOutput("Invalid JSON", input_tokens=20, output_tokens=10),
            ProviderOutput(
                '{"answer":"Review the invoice","confidence":0.8,"category":"billing","actions":[]}',
                input_tokens=21,
                output_tokens=11,
            ),
        ]
        response, generation = self.service.respond("Duplicate charge")

        self.assertEqual(response.category, "billing")
        self.assertEqual(generation.attempts, 2)
        first, second = self.provider.generate.call_args_list
        self.assertEqual(first, second)
        event = self.read_event()
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["total_tokens"], 62)

    def test_invalid_then_provider_error_keeps_reported_usage(self):
        self.provider.generate.side_effect = [
            ProviderOutput("Invalid JSON", input_tokens=20, output_tokens=10),
            ProviderCallError("openai", "authentication", "simulated"),
        ]
        with self.assertRaises(ProviderCallError):
            self.service.respond("Duplicate charge")

        event = self.read_event()
        self.assertEqual(event["status"], "error")
        self.assertEqual(event["attempts"], 2)
        self.assertEqual(event["total_tokens"], 30)

    def test_evaluation_records_first_invalid_response(self):
        self.provider.generate.return_value = ProviderOutput("Invalid JSON")
        service = SupportService(LLMClient(self.config, self.provider), retry_invalid_response=False)

        with self.assertRaises(InvalidStructuredResponse):
            service.respond("Duplicate charge")

        self.provider.generate.assert_called_once()
        event = self.read_event()
        self.assertEqual(event["status"], "invalid_contract")

    def test_provider_error_logs_one_error(self):
        self.provider.generate.side_effect = ProviderCallError(
            "openai", "authentication", "simulated"
        )
        with self.assertRaises(ProviderCallError):
            self.service.respond("Duplicate charge")

        event = self.read_event()
        self.assertEqual(event["status"], "error")
        self.assertEqual(event["error_type"], "authentication")
        self.assertIsNone(event["estimated_cost_usd"])
        self.assertIsNone(event["input_usd_per_million"])
        self.assertIsNone(event["output_usd_per_million"])
