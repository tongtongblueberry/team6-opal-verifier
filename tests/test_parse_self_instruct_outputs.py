# Changed: test parsing externally generated Self-Instruct outputs without creating synthetic data.
# Why: raw LLM responses need schema/invariant gates before dedup, audit, manifest, or training.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.datagen import parse_self_instruct_outputs as parser


# Changed: keep raw parser fixtures under tests/fixtures instead of runs or accepted data directories.
# Why: mock raw outputs prove wiring only and must not become synthetic training artifacts.
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "self_instruct_gate_wiring"
MOCK_RAW_OUTPUT_FIXTURE = FIXTURE_ROOT / "mock_raw_outputs.jsonl"


def _record(method: str, status: str) -> dict[str, object]:
    return {
        # Changed: parser fixtures use concrete method args and invoking UID.
        # Why: raw Qwen candidates with null input fields or bare args:{} are now rejected before normalization.
        "input": {
            "method": {"name": method, "args": {"required": {"HostSessionID": "00000001"}, "optional": {}}},
            "invoking_id": {"uid": "00 00 00 06 00 00 00 01"},
            "status_codes": ["SUCCESS"],
        },
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
        # Changed: include generated instruction provenance in mock candidates.
        # Why: parser normalization now requires official-stage provenance before candidate preparation.
        "source_instruction_id": "self-instruct-instruction-00000",
        "instruction": parser.FIXED_OPAL_VERIFIER_INSTRUCTION,
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
        "generation_provenance": {
            "source_instruction_id": "self-instruct-instruction-00000",
            "classification_detection_id": "self-instruct-clf-00000",
            "official_instruction_artifact": "machine_generated_instructions.jsonl",
            "official_classification_artifact": "is_clf_or_not_audited_noop.jsonl",
            "official_instance_artifact": "machine_generated_instances.jsonl",
        },
    }


class ParseSelfInstructOutputsTests(unittest.TestCase):
    # Changed: build the parser smoke raw row with the active fixed instruction.
    # Why: stale fixture instructions must not keep old gen2 prompt contracts alive after the gen3 restart.
    def test_spec_grounded_mock_raw_fixture_passes_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "mock_raw_outputs.jsonl"
            output_path = tmp / "parser.accepted.jsonl"
            reject_path = tmp / "parser.rejects.jsonl"
            report_path = tmp / "parser.report.json"
            profile_path = tmp / "parser.profile.json"
            raw_row = {
                "request_id": "mock-fixture-raw-1",
                "raw_output": json.dumps(_candidate("fixture-spec-grounded-pass", "pass", [_record("Get", "SUCCESS")])),
            }
            input_path.write_text(json.dumps(raw_row) + "\n", encoding="utf-8")

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
                    "--profile-output",
                    str(profile_path),
                ]
            )

            self.assertEqual(0, exit_code)
            accepted = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            rejected = [json.loads(line) for line in reject_path.read_text(encoding="utf-8").splitlines()]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual([], rejected)
            self.assertEqual(1, len(accepted))
            self.assertEqual("fixture-spec-grounded-pass", accepted[0]["sample_id"])
            self.assertEqual("self_instruct.candidate.v1", accepted[0]["schema_version"])
            self.assertEqual("self-instruct-instruction-00000", accepted[0]["source_instruction_id"])
            self.assertEqual("docs/legacy_spec_rules.md:10-15", accepted[0]["spec_grounding"][0]["source_span"])
            self.assertEqual(1, report["accepted_count"])
            self.assertEqual(0, report["rejected_count"])
            self.assertEqual("candidate_preparation", report["official_stage"])

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

    def test_accepts_fail_label_with_success_final_response_when_final_targeted(self) -> None:
        candidate = _candidate(
            "si-final-success-fail",
            "fail",
            [
                _record("Set", "FAIL"),
                _record("EndSession", "SUCCESS"),
            ],
        )

        accepted, rejected = parser.parse_raw_output_rows([(1, {"raw_output": json.dumps(candidate)})])

        self.assertEqual([], rejected)
        self.assertEqual(1, len(accepted))
        self.assertEqual("si-final-success-fail", accepted[0]["sample_id"])
        self.assertEqual("fail", accepted[0]["label"])

    def test_rejects_non_fixed_instruction_and_null_input(self) -> None:
        bad_instruction = _candidate("si-bad-instruction", "pass", [_record("Get", "SUCCESS")])
        bad_instruction["instruction"] = "Generate a new task instruction."
        bad_null = _candidate("si-null-input", "pass", [_record("Get", "SUCCESS")])
        bad_null["records"][0]["input"]["invoking_id"]["uid"] = None

        accepted, rejected = parser.parse_raw_output_rows(
            [
                (1, {"raw_output": json.dumps(bad_instruction)}),
                (2, {"raw_output": json.dumps(bad_null)}),
            ]
        )

        self.assertEqual([], accepted)
        self.assertEqual(["instruction_not_fixed", "record_0_input_contains_null:records.0.input.invoking_id.uid"], [row["reason"] for row in rejected])

    def test_parses_fenced_json_candidate_list(self) -> None:
        first = _candidate("si-fenced-1", "pass", [_record("Get", "SUCCESS")])
        second = _candidate("si-fenced-2", "fail", [_record("Set", "INVALID_PARAMETER")])
        text = "Here is the JSON:\n```json\n" + json.dumps({"candidates": [first, second]}) + "\n```"

        accepted, rejected = parser.parse_raw_output_rows([(3, {"llm_output": text})])

        self.assertEqual([], rejected)
        self.assertEqual(["si-fenced-1", "si-fenced-2"], [row["sample_id"] for row in accepted])


if __name__ == "__main__":
    unittest.main()
