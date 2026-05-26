# Changed: test parsing externally generated Self-Instruct outputs without creating synthetic data.
# Why: raw LLM responses need schema/invariant gates before dedup, audit, manifest, or training.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.datagen import parse_self_instruct_outputs as parser


def _record(method: str, status: str) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": []},
    }


def _spec_grounding() -> list[dict[str, object]]:
    return [
        {
            "rule_ref": "RULE 01",
            "source_path": "docs/legacy_spec_rules.md",
            "source_span": "docs/legacy_spec_rules.md:10-15",
            "condition": "A method is processed completely and without error by the TPer",
            "expected_status": "SUCCESS (0x00)",
        }
    ]


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
            "final_response": records[-1]["output"],
        },
        "primary_evidence": {
            "record_index": final_index,
            "reason": "The final response determines the label.",
        },
        "spec_grounding": _spec_grounding(),
    }


class ParseSelfInstructOutputsTests(unittest.TestCase):
    def test_parses_raw_llm_output_and_writes_reject_report(self) -> None:
        valid = _candidate("si-parse-ok", "pass", [_record("Get", "SUCCESS")])
        rows = [
            {"request_id": "req-1", "raw_output": json.dumps(valid)},
            {"request_id": "req-2", "raw_output": "not json"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "raw.jsonl"
            output_path = tmp / "accepted.jsonl"
            reject_path = tmp / "rejects.jsonl"
            report_path = tmp / "report.json"
            input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            exit_code = parser.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--reject-output",
                    str(reject_path),
                    "--report-json",
                    str(report_path),
                ]
            )

            self.assertEqual(0, exit_code)
            accepted = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            rejected = [json.loads(line) for line in reject_path.read_text(encoding="utf-8").splitlines()]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(accepted))
            self.assertEqual("si-parse-ok", accepted[0]["sample_id"])
            self.assertEqual("pass", accepted[0]["label"])
            self.assertEqual(1, len(rejected))
            self.assertEqual("parse", rejected[0]["stage"])
            self.assertEqual(1, report["accepted_count"])
            self.assertEqual(1, report["rejected_count"])

    def test_rejects_final_response_invariant_violation(self) -> None:
        bad = _candidate(
            "si-bad-final",
            "fail",
            [
                _record("Set", "FAIL"),
                _record("EndSession", "SUCCESS"),
            ],
        )

        accepted, rejected = parser.parse_raw_output_rows([(1, {"raw_output": json.dumps(bad)})])

        self.assertEqual([], accepted)
        self.assertEqual(1, len(rejected))
        self.assertEqual("normalize", rejected[0]["stage"])
        self.assertEqual("intermediate_failure_before_final_endsession_success", rejected[0]["reason"])

    def test_parses_fenced_json_candidate_list(self) -> None:
        first = _candidate("si-fenced-1", "pass", [_record("Get", "SUCCESS")])
        second = _candidate("si-fenced-2", "fail", [_record("Set", "INVALID_PARAMETER")])
        text = "Here is the JSON:\n```json\n" + json.dumps({"candidates": [first, second]}) + "\n```"

        accepted, rejected = parser.parse_raw_output_rows([(3, {"llm_output": text})])

        self.assertEqual([], rejected)
        self.assertEqual(["si-fenced-1", "si-fenced-2"], [row["sample_id"] for row in accepted])


if __name__ == "__main__":
    unittest.main()
