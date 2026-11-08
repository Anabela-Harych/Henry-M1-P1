import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from evals import runner
from evals.runner import base_result, summarize
from src.llm.config import LLMConfig
from src.llm.errors import LLMConfigurationError, ProviderCallError
from src.llm.models import ProviderOutput


class EvalScoresTest(unittest.TestCase):
    def test_failed_cases_count_in_global_and_category_scores(self):
        # Una salida inválida cuenta en el total, y un JSON válido puede clasificar mal.
        cases = [
            {"id": "1", "expected_category": "billing"},
            {"id": "2", "expected_category": "billing"},
            {"id": "3", "expected_category": "technical"},
        ]
        rows = [base_result(case, None, "openai", Path("v1.yaml")) for case in cases]
        rows[0].update(status="success", contract_valid=True, category_correct=True)
        rows[1].update(status="invalid_contract")
        rows[2].update(status="success", contract_valid=True, predicted_category="account")

        scores = {row["category"]: row for row in summarize(rows)}
        self.assertEqual(scores[None]["score_category_accuracy"], 0.3333)
        self.assertEqual(scores[None]["contract_valid_rate"], 0.6667)
        self.assertEqual(scores["billing"]["score_category_accuracy"], 0.5)
        self.assertEqual(scores["technical"]["score_category_accuracy"], 0.0)

    def test_exit_code_distinguishes_no_responses_from_invalid_responses(self):
        # Conserva el reporte y falla solo cuando el modelo no devolvió ninguna respuesta.
        for status, exit_code in (
            ("configuration_error", 1),
            ("provider_error", 1),
            ("invalid_contract", 0),
        ):
            with self.subTest(status=status), TemporaryDirectory() as directory:
                config = LLMConfig(
                    "openai", "test-model", "test-key", "v1", "test",
                    usage_log_path=Path(directory) / "usage.jsonl",
                )
                provider = Mock()
                provider.generate.return_value = ProviderOutput("Invalid JSON")
                if status == "provider_error":
                    provider.generate.side_effect = ProviderCallError(
                        "openai", "connection", "simulated"
                    )
                config_error = (
                    LLMConfigurationError("simulated") if status == "configuration_error" else None
                )
                args = [
                    "evals", "--execute", "--providers", "openai", "--prompts",
                    "prompts/v1_zero_shot.yaml", "--limit-per-category", "1",
                    "--output-dir", directory, "--delay-seconds", "0.25",
                ]
                stdout = io.StringIO()
                with (
                    patch("sys.argv", args),
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(runner, "config_for", return_value=config, side_effect=config_error),
                    patch.object(runner, "build_provider", return_value=provider),
                    patch("evals.runner.time.sleep") as sleep,
                    redirect_stdout(stdout),
                    redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(runner.main(), exit_code)
                report = Path(json.loads(stdout.getvalue())["report"])
                expected_files = {report.name, f"{report.stem}_analysis.md"}
                if status != "configuration_error":
                    expected_files.add("usage.jsonl")
                self.assertEqual({path.name for path in report.parent.iterdir()}, expected_files)
                rows = json.loads(report.read_text(encoding="utf-8"))["results"]
                self.assertEqual({row["status"] for row in rows}, {status})
                expected_pauses = 0 if status == "configuration_error" else len(rows) - 1
                self.assertEqual(sleep.call_count, expected_pauses)
