# Changed: add pending regression tests for the Self-Instruct final-response invariant gate.
# Why: the replacement pipeline must reject labels that target an intermediate response instead of the final response.

from __future__ import annotations

import importlib
import importlib.util
import unittest


def _load_checker_module():
    module_name = "tools.analysis.self_instruct_invariants"
    if importlib.util.find_spec(module_name) is None:
        raise unittest.SkipTest(f"{module_name} is not implemented yet")
    return importlib.import_module(module_name)


class SelfInstructFinalResponseInvariantTests(unittest.TestCase):
    def test_rejects_intermediate_failure_followed_by_successful_final_response(self) -> None:
        checker = _load_checker_module()
        candidate = {
            "schema_version": "self_instruct.candidate.v1",
            "sample_id": "intermediate-failure-final-success",
            "records": [
                {
                    "input": {"method": {"name": "Set"}},
                    "output": {"status_codes": "FAIL", "return_values": []},
                },
                {
                    "input": {"method": {"name": "EndSession"}},
                    "output": {"status_codes": "SUCCESS", "return_values": []},
                },
            ],
            "label": "fail",
            "label_target": "final_response",
            "target": {
                "final_response_index": 1,
                "final_response": {"status_codes": "SUCCESS", "return_values": []},
            },
            "primary_evidence": {
                "record_index": 0,
                "reason": "The Set response failed before the final EndSession response.",
            },
        }

        result = checker.check_final_response_label_invariant(candidate)

        self.assertFalse(result.passed)
        self.assertEqual("primary_evidence_not_final_response", result.reason)
        self.assertEqual(1, result.details["final_response_index"])
        self.assertEqual(0, result.details["primary_evidence_index"])

    def test_rejects_target_index_that_is_not_last_record(self) -> None:
        checker = _load_checker_module()
        candidate = {
            "schema_version": "self_instruct.candidate.v1",
            "sample_id": "target-not-last",
            "records": [
                {
                    "input": {"method": {"name": "Get"}},
                    "output": {"status_codes": "FAIL", "return_values": []},
                },
                {
                    "input": {"method": {"name": "EndSession"}},
                    "output": {"status_codes": "SUCCESS", "return_values": []},
                },
            ],
            "label": "fail",
            "label_target": "final_response",
            "target": {
                "final_response_index": 0,
                "final_response": {"status_codes": "FAIL", "return_values": []},
            },
            "primary_evidence": {
                "record_index": 0,
                "reason": "The target response is not the last record.",
            },
        }

        result = checker.check_final_response_label_invariant(candidate)

        self.assertFalse(result.passed)
        self.assertEqual("target_index_not_last_record", result.reason)
        self.assertEqual(1, result.details["expected_final_response_index"])
        self.assertEqual(0, result.details["actual_final_response_index"])

    def test_accepts_candidate_when_target_and_evidence_are_final_response(self) -> None:
        checker = _load_checker_module()
        final_response = {"status_codes": "NOT_AUTHORIZED", "return_values": []}
        candidate = {
            "schema_version": "self_instruct.candidate.v1",
            "sample_id": "final-targeted-fail",
            "records": [
                {
                    "input": {"method": {"name": "StartSession"}},
                    "output": {"status_codes": "SUCCESS", "return_values": []},
                },
                {
                    "input": {"method": {"name": "Set"}},
                    "output": final_response,
                },
            ],
            "label": "pass",
            "label_target": "final_response",
            "target": {
                "final_response_index": 1,
                "final_response": final_response,
            },
            "primary_evidence": {
                "record_index": 1,
                "reason": "The final Set response is the response being judged.",
            },
        }

        result = checker.check_final_response_label_invariant(candidate)

        self.assertTrue(result.passed)
        self.assertEqual("ok", result.reason)
        self.assertEqual(1, result.details["final_response_index"])


if __name__ == "__main__":
    unittest.main()
