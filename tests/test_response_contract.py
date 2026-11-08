import json
import unittest

from pydantic import ValidationError

from src.schemas import SupportResponse


class ResponseContractTest(unittest.TestCase):
    def response_json(self, confidence: object) -> str:
        return json.dumps(
            {
                "answer": "Consultá el flujo de recuperación.",
                "confidence": confidence,
                "category": "account",
                "actions": [],
            }
        )

    def test_confidence_accepts_json_numbers_in_range(self):
        for value in (0, 0.8, 1):
            with self.subTest(value=value):
                response = SupportResponse.model_validate_json(self.response_json(value))
                self.assertEqual(response.confidence, value)

    def test_confidence_rejects_non_numbers_and_out_of_range_values(self):
        for value in (True, False, "0.8", None, -0.01, 1.01):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    SupportResponse.model_validate_json(self.response_json(value))

    def test_rejects_changes_to_the_response_contract(self):
        # Protege los cuatro campos del contrato y sus tipos.
        valid = json.loads(self.response_json(0.8))
        invalid = {
            "missing_answer": {key: value for key, value in valid.items() if key != "answer"},
            "unknown_category": dict(valid, category="unknown"),
            "actions_as_text": dict(valid, actions="Revisar la cuenta"),
            "extra_field": dict(valid, details="Campo extra"),
        }
        for case, payload in invalid.items():
            with self.subTest(case=case), self.assertRaises(ValidationError):
                SupportResponse.model_validate_json(json.dumps(payload))
