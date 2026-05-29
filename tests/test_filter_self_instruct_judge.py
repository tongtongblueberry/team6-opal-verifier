# Changed: test Self-Instruct judge dry-run request building and external result parsing.
# Why: judge filtering must remain offline, LLM-only, and separate from runtime inference.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import filter_self_instruct_judge as judge
from tools.datagen import parse_self_instruct_outputs as parser


# Changed: load parser/judge fixtures from tests/fixtures only.
# Why: mock fixtures validate wiring without creating accepted synthetic data artifacts.
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "self_instruct_gate_wiring"
MOCK_RAW_OUTPUT_FIXTURE = FIXTURE_ROOT / "mock_raw_outputs.jsonl"
MOCK_JUDGE_BOOL_FIXTURE = FIXTURE_ROOT / "mock_judge_results_required_booleans.jsonl"


def _fixture_rows(path: Path) -> list[tuple[int, dict[str, object]]]:
    rows: list[tuple[int, dict[str, object]]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped:
            rows.append((line_number, json.loads(stripped)))
    return rows


def _record(method: str, status: str) -> dict[str, object]:
    return {
        # Changed: include concrete Opal input shape in judge candidates.
        # Why: gen3 candidates must preserve parse/export-compatible trajectory records.
        "input": {
            "method": {"name": method, "args": {"required": {"HostSessionID": "00000001"}, "optional": {}}},
            "invoking_id": {"uid": "00 00 00 06 00 00 00 01", "name": "Locking"},
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
        # Changed: include generated instruction and classification provenance in judge fixtures.
        # Why: judge payloads must audit candidates with official-stage lineage.
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
            "reason": "The final response determines the verdict.",
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


class FilterSelfInstructJudgeTests(unittest.TestCase):
    # Changed: use a judge response fixture that flips every required boolean once.
    # Why: decision=accept must still reject unless the complete required-boolean contract is satisfied.
    def test_required_boolean_fixture_accepts_only_full_contract(self) -> None:
        candidates, parser_rejected = parser.parse_raw_output_rows(_fixture_rows(MOCK_RAW_OUTPUT_FIXTURE))
        self.assertEqual([], parser_rejected)
        self.assertEqual(["fixture-spec-grounded-pass"], [row["sample_id"] for row in candidates])

        judge_rows = _fixture_rows(MOCK_JUDGE_BOOL_FIXTURE)
        violated_fields = {row["fixture_violated_field"] for _line, row in judge_rows if "fixture_violated_field" in row}
        accepted, rejected, decisions = judge.apply_judge_results(candidates, judge_rows)

        self.assertEqual(set(judge.REQUIRED_BOOL_FIELDS), violated_fields)
        self.assertEqual(["fixture-spec-grounded-pass"], [row["sample_id"] for row in accepted])
        self.assertEqual(8, len(rejected))
        self.assertEqual(9, len(decisions))
        self.assertEqual(
            {
                "intermediate_label_leak",
                "label_not_plausible",
                "manifest_loader_incompatible",
                "missing_spec_grounding",
                "not_final_response_targeted",
                "public_or_rule_leakage",
                "source_span_not_supportive",
                "state_transition_inconsistent",
            },
            {row["reason"] for row in rejected},
        )

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
            self.assertEqual("self-instruct-instruction-00000", row["source_instruction_id"])
            self.assertEqual("self-instruct-clf-00000", row["classification_detection_id"])
            prompt = row["payload"]["messages"][1]["content"]
            self.assertIn("is_final_response_targeted", prompt)
            self.assertIn("has_required_spec_grounding", prompt)
            self.assertIn("is_source_span_supported", prompt)
            self.assertIn("spec_grounding", prompt)
            self.assertIn("has_public_or_rule_leakage", prompt)
            self.assertIn("generated_label", prompt)
            self.assertIn("official_pipeline_provenance", prompt)
            self.assertIn("classification_detection_id", prompt)
            # Changed: judge prompts must carry exact source text from docs/legacy_spec_rules.md.
            # Why: adversarial qualitative checks cannot trust generator-copied condition text alone.
            self.assertIn("resolved_spec_source_spans", prompt)
            self.assertIn("SUCCESS on complete method processing", prompt)
            self.assertIn("A method is processed completely and without error by the TPer", prompt)

    def test_parses_judge_results_and_splits_accept_reject(self) -> None:
        accepted_candidate = _candidate("si-judge-ok", "pass", [_record("Get", "SUCCESS")])
        rejected_candidate = _candidate("si-judge-bad", "fail", [_record("Set", "INVALID_PARAMETER")])
        boolean_accepted_candidate = _candidate("si-judge-fail-ok", "fail", [_record("Set", "INVALID_PARAMETER")])
        results = [
            {
                "request_id": "req-ok",
                "sample_id": "si-judge-ok",
                "judge_output": json.dumps(
                    {
                        "sample_id": "si-judge-ok",
                        "decision": "accept",
                        "is_final_response_targeted": True,
                        "has_required_spec_grounding": True,
                        "is_source_span_supported": True,
                        "is_state_transition_consistent": True,
                        "is_manifest_loader_compatible": True,
                        "is_label_plausible": True,
                        "has_intermediate_label_leak": False,
                        "has_public_or_rule_leakage": False,
                        "rationale": "Final response supports the label.",
                    }
                ),
            },
            {
                "request_id": "req-fail-ok",
                "sample_id": "si-judge-fail-ok",
                "decision": "reject",
                "is_final_response_targeted": True,
                "has_required_spec_grounding": True,
                "is_source_span_supported": True,
                "is_state_transition_consistent": True,
                "is_manifest_loader_compatible": True,
                "is_label_plausible": True,
                "has_intermediate_label_leak": False,
                "has_public_or_rule_leakage": False,
            },
            {
                "request_id": "req-bad",
                "sample_id": "si-judge-bad",
                "decision": "accept",
                "is_final_response_targeted": True,
                "has_required_spec_grounding": True,
                "is_source_span_supported": True,
                "is_state_transition_consistent": True,
                "is_manifest_loader_compatible": True,
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
                "\n".join(json.dumps(row) for row in [accepted_candidate, boolean_accepted_candidate, rejected_candidate]) + "\n",
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
            self.assertEqual(["si-judge-ok", "si-judge-fail-ok"], [row["sample_id"] for row in accepted])
            self.assertEqual("intermediate_label_leak", rejected[0]["reason"])
            self.assertEqual(2, report["accepted_count"])
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
