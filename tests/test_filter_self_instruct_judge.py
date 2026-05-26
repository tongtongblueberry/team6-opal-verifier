# Changed: test Self-Instruct judge dry-run request building and external result parsing.
# Why: judge filtering must remain offline, LLM-only, and separate from runtime inference.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import filter_self_instruct_judge as judge


def _record(method: str, status: str) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": []},
    }


def _candidate(sample_id: str, label: str, records: list[dict[str, object]]) -> dict[str, object]:
    final_index = len(records) - 1
    return {
        "sample_id": sample_id,
        "instruction": "Judge whether the final response is valid.",
        "records": records,
        "label": label,
        "label_target": "final_response",
        "target": {
            "final_response_index": final_index,
            "final_response": records[-1]["output"],
        },
        "primary_evidence": {
            "record_index": final_index,
            "reason": "The final response determines the verdict.",
        },
    }


class FilterSelfInstructJudgeTests(unittest.TestCase):
    def test_cli_writes_judge_request_payload(self) -> None:
        candidate = _candidate("si-judge-1", "pass", [_record("Get", "SUCCESS")])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            candidates_path = tmp / "candidates.jsonl"
            requests_path = tmp / "requests.jsonl"
            metadata_path = tmp / "metadata.json"
            candidates_path.write_text(json.dumps(candidate) + "\n", encoding="utf-8")

            exit_code = judge.main(
                [
                    "--candidates",
                    str(candidates_path),
                    "--requests-output",
                    str(requests_path),
                    "--metadata-json",
                    str(metadata_path),
                    "--created-at-kst",
                    "2026-05-26T18:00:00+09:00",
                ]
            )

            self.assertEqual(0, exit_code)
            row = json.loads(requests_path.read_text(encoding="utf-8").splitlines()[0])
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertFalse(row["execute"])
            self.assertFalse(metadata["execute"])
            self.assertEqual("si-judge-1", row["sample_id"])
            prompt = row["payload"]["messages"][1]["content"]
            self.assertIn("is_final_response_targeted", prompt)
            self.assertIn("has_public_or_rule_leakage", prompt)
            self.assertIn("generated_label", prompt)

    def test_parses_judge_results_and_splits_accept_reject(self) -> None:
        accepted_candidate = _candidate("si-judge-ok", "pass", [_record("Get", "SUCCESS")])
        rejected_candidate = _candidate("si-judge-bad", "fail", [_record("Set", "INVALID_PARAMETER")])
        results = [
            {
                "request_id": "req-ok",
                "sample_id": "si-judge-ok",
                "judge_output": json.dumps(
                    {
                        "sample_id": "si-judge-ok",
                        "decision": "accept",
                        "is_final_response_targeted": True,
                        "is_label_plausible": True,
                        "has_intermediate_label_leak": False,
                        "has_public_or_rule_leakage": False,
                        "rationale": "Final response supports the label.",
                    }
                ),
            },
            {
                "request_id": "req-bad",
                "sample_id": "si-judge-bad",
                "decision": "accept",
                "is_final_response_targeted": True,
                "is_label_plausible": True,
                "has_intermediate_label_leak": True,
                "has_public_or_rule_leakage": False,
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            candidates_path = tmp / "candidates.jsonl"
            results_path = tmp / "judge_results.jsonl"
            accepted_path = tmp / "accepted.jsonl"
            reject_path = tmp / "rejects.jsonl"
            decisions_path = tmp / "decisions.json"
            report_path = tmp / "report.json"
            candidates_path.write_text(
                "\n".join(json.dumps(row) for row in [accepted_candidate, rejected_candidate]) + "\n",
                encoding="utf-8",
            )
            results_path.write_text("\n".join(json.dumps(row) for row in results) + "\n", encoding="utf-8")

            exit_code = judge.main(
                [
                    "--candidates",
                    str(candidates_path),
                    "--requests-output",
                    str(tmp / "requests.jsonl"),
                    "--metadata-json",
                    str(tmp / "metadata.json"),
                    "--judge-results",
                    str(results_path),
                    "--accepted-output",
                    str(accepted_path),
                    "--reject-output",
                    str(reject_path),
                    "--decisions-output",
                    str(decisions_path),
                    "--report-json",
                    str(report_path),
                ]
            )

            self.assertEqual(0, exit_code)
            accepted = [json.loads(line) for line in accepted_path.read_text(encoding="utf-8").splitlines()]
            rejected = [json.loads(line) for line in reject_path.read_text(encoding="utf-8").splitlines()]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(["si-judge-ok"], [row["sample_id"] for row in accepted])
            self.assertEqual("intermediate_label_leak", rejected[0]["reason"])
            self.assertEqual(1, report["accepted_count"])
            self.assertEqual(1, report["rejected_count"])

    def test_execute_flag_does_not_call_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            candidates_path = tmp / "candidates.jsonl"
            candidates_path.write_text(json.dumps(_candidate("si-judge-1", "pass", [_record("Get", "SUCCESS")])) + "\n", encoding="utf-8")

            exit_code = judge.main(
                [
                    "--candidates",
                    str(candidates_path),
                    "--requests-output",
                    str(tmp / "requests.jsonl"),
                    "--metadata-json",
                    str(tmp / "metadata.json"),
                    "--execute",
                ]
            )

            self.assertEqual(2, exit_code)


if __name__ == "__main__":
    unittest.main()
