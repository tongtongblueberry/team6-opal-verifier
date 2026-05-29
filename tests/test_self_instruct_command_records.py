# Changed: cover public20 command-style final records in Self-Instruct invariants.
# Why: generated data that preserves public20 COMMAND:Read/Write rows must pass structural final-response checks.

from __future__ import annotations

import unittest

from tools.analysis.self_instruct_invariants import check_final_response_label_invariant


class SelfInstructCommandRecordsTests(unittest.TestCase):
    def test_command_final_record_counts_as_final_method(self) -> None:
        record = {
            "input": {"command": "Read", "args": {"LBA": "1 ~ 2"}},
            "output": {"command": "Read", "status_codes": "SUCCESS", "args": {"result": "Pattern AA"}},
        }
        candidate = {
            "sample_id": "command-final",
            "records": [record],
            "label": "pass",
            "label_target": "final_response",
            "target": {
                "final_response_index": 0,
                "final_method": "Read",
                "final_response": record["output"],
            },
            "primary_evidence": {"record_index": 0},
        }

        result = check_final_response_label_invariant(candidate)

        self.assertTrue(result.passed, result)

    def test_command_final_record_without_status_counts_as_final_response(self) -> None:
        # Changed: public20 command rows may have command/result without status_codes.
        # Why: generated data should preserve those rows instead of adding synthetic statuses.
        record = {
            "input": {"command": "Read", "args": {"LBA": "1 ~ 2"}},
            "output": {"command": "Read", "args": {"result": "Pattern AA"}},
        }
        candidate = {
            "sample_id": "command-final-no-status",
            "records": [record],
            "label": "pass",
            "label_target": "final_response",
            "target": {
                "final_response_index": 0,
                "final_method": "Read",
                "final_response": record["output"],
            },
            "primary_evidence": {"record_index": 0},
        }

        result = check_final_response_label_invariant(candidate)

        self.assertTrue(result.passed, result)

    def test_fail_label_with_final_success_is_not_a_targeting_error(self) -> None:
        # Changed: lock the invariant to targeting, not status-derived semantics.
        # Why: public20 contains fail rows whose final response status is SUCCESS.
        record = {
            "input": {"method": {"name": "Activate"}},
            "output": {"status_codes": "SUCCESS", "return_values": []},
        }
        candidate = {
            "sample_id": "fail-final-success",
            "records": [record],
            "label": "fail",
            "label_target": "final_response",
            "target": {
                "final_response_index": 0,
                "final_method": "Activate",
                "final_response": record["output"],
            },
            "primary_evidence": {"record_index": 0},
        }

        result = check_final_response_label_invariant(candidate)

        self.assertTrue(result.passed, result)


if __name__ == "__main__":
    unittest.main()
