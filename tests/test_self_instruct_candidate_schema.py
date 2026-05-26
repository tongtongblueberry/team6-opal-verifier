# Changed: cover label-bearing Self-Instruct candidate normalization separately from public seed normalization.
# Why: generated candidates need label/invariant gates, but public20 seeds must remain input-only.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.datagen import self_instruct_candidate_schema as schema


def _record(method: str, status: str, return_values: list[object] | None = None) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": [] if return_values is None else return_values},
    }


def _candidate(sample_id: str, label: str, records: list[dict[str, object]]) -> dict[str, object]:
    final_index = len(records) - 1
    return {
        "sample_id": sample_id,
        "instruction": "Judge only the final response.",
        "records": records,
        "label": label,
        "label_target": "final_response",
        "target": {
            "final_response_index": final_index,
            "final_response": records[final_index]["output"],
        },
        "primary_evidence": {
            "record_index": final_index,
            "reason": "The final response determines the label.",
        },
        "source": "self_instruct_candidate",
    }


class SelfInstructCandidateSchemaTests(unittest.TestCase):
    def test_normalizes_pass_candidate_and_applies_invariant(self) -> None:
        candidate = _candidate(
            "candidate-pass",
            "PASS",
            [
                _record("StartSession", "SUCCESS"),
                _record("Get", "SUCCESS", [{"3": "value"}]),
            ],
        )

        normalized = schema.normalize_candidate(candidate)

        self.assertEqual("self_instruct.candidate.v1", normalized["schema_version"])
        self.assertEqual("candidate-pass", normalized["sample_id"])
        self.assertEqual("pass", normalized["label"])
        self.assertEqual("final_response", normalized["label_target"])
        self.assertEqual(1, normalized["target"]["final_response_index"])
        self.assertEqual(candidate["records"][1]["output"], normalized["target"]["final_response"])
        self.assertEqual(1, normalized["primary_evidence"]["record_index"])

    def test_normalizes_fail_candidate_from_trajectory_container(self) -> None:
        records = [
            _record("StartSession", "SUCCESS"),
            _record("Set", "FAIL"),
        ]
        final_response = records[-1]["output"]
        candidate = {
            "candidate_id": "candidate-fail",
            "instruction": "Judge the last response only.",
            "trajectory": {"records": records},
            "label": "Fail",
            "label_target": "final_response",
            "target": {
                "final_response_index": 1,
                "final_response": final_response,
            },
            "primary_evidence": {"record_index": 1, "reason": "The final Set response fails."},
        }

        normalized = schema.normalize_candidate(candidate)

        self.assertEqual("candidate-fail", normalized["sample_id"])
        self.assertEqual("fail", normalized["label"])
        self.assertEqual(final_response, normalized["target"]["final_response"])
        self.assertEqual("The final Set response fails.", normalized["primary_evidence"]["reason"])

    def test_rejects_bad_final_label(self) -> None:
        candidate = _candidate(
            "bad-final-label",
            "fail",
            [
                _record("Set", "FAIL"),
                _record("EndSession", "SUCCESS"),
            ],
        )

        with self.assertRaisesRegex(schema.CandidateSchemaError, "intermediate_failure_before_final_endsession_success"):
            schema.normalize_candidate(candidate)

    def test_rejects_missing_primary_evidence(self) -> None:
        candidate = _candidate("missing-evidence", "pass", [_record("Get", "SUCCESS")])
        candidate.pop("primary_evidence")

        with self.assertRaisesRegex(schema.CandidateSchemaError, "primary_evidence_missing"):
            schema.normalize_candidate(candidate)

    def test_cli_writes_normalized_jsonl_and_profile_json(self) -> None:
        candidate = _candidate("candidate-cli", "pass", [_record("Get", "SUCCESS")])
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "input.jsonl"
            output_path = tmp / "normalized.jsonl"
            profile_path = tmp / "profile.json"
            input_path.write_text(json.dumps(candidate) + "\n", encoding="utf-8")

            exit_code = schema.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--profile-output",
                    str(profile_path),
                ]
            )

            self.assertEqual(0, exit_code)
            normalized_rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(normalized_rows))
            self.assertEqual("candidate-cli", normalized_rows[0]["sample_id"])
            self.assertEqual("pass", normalized_rows[0]["label"])
            self.assertEqual({"pass": 1}, profile["label_counts"])
            self.assertEqual(1, profile["count"])


if __name__ == "__main__":
    unittest.main()
