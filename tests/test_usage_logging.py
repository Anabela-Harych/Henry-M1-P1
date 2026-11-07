import json
import unittest
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
        config = LLMConfig(
            provider="openai",
            model="test-model",
            api_key="test-key",
            prompt_id="test-prompt",
            system_instruction="test-instruction",
            usage_log_path=self.log_path,
        )
        self.provider = Mock(spec=LLMProvider)
        self.service = SupportService(LLMClient(config, self.provider))

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
        with patch("src.llm.client.time.sleep"):
            response, _ = self.service.respond("Duplicate charge")

        event = self.read_event()
        self.assertEqual(response.category, "billing")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["attempts"], 2)
        self.assertEqual(event["total_tokens"], 30)

    def test_invalid_response_logs_its_usage_once(self):
        self.provider.generate.return_value = ProviderOutput(
            "Invalid JSON", input_tokens=20, output_tokens=10
        )
        with patch("src.llm.client.estimate_cost_usd", return_value=(0.001, "test")):
            with self.assertRaises(InvalidStructuredResponse):
                self.service.respond("Duplicate charge")

        event = self.read_event()
        self.assertEqual(event["status"], "invalid_contract")
        self.assertEqual(event["total_tokens"], 30)
        self.assertEqual(event["estimated_cost_usd"], 0.001)
        self.assertGreaterEqual(event["latency_ms"], 0)

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
