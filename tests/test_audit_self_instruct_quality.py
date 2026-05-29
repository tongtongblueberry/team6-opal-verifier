# Changed: cover Gate A qualitative audit-pack generation.
# Why: generated candidate pools need invariant precheck and stratified state-transition audit artifacts.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import audit_self_instruct_quality as audit


def _record(method: str, status: str, return_values: list[object] | None = None) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": [] if return_values is None else return_values},
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
        # Changed: include official Self-Instruct provenance required before Gate A sampling.
        # Why: Gate A must audit post-parser/judge candidates, not pre-migration draft rows.
        "source_instruction_id": f"instruction-{sample_id}",
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
        "spec_grounding": _spec_grounding(),
        "generation_provenance": {
            "source_instruction_id": f"instruction-{sample_id}",
            "classification_detection_id": f"classification-{sample_id}",
            "instance_generation_request_id": f"request-{sample_id}",
            "raw_output_request_id": f"raw-{sample_id}",
        },
        "source": "self_instruct_candidate",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class GateAQualityAuditTests(unittest.TestCase):
    def test_reports_hard_invariant_failure(self) -> None:
        good = _candidate("good-pass", "pass", [_record("Get", "SUCCESS")])
        bad = _candidate(
            "bad-final-success",
            "fail",
            [
                _record("Set", "FAIL"),
                _record("EndSession", "SUCCESS"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "accepted.jsonl"
            invariant_path = tmp / "invariant.jsonl"
            pack_path = tmp / "audit_pack.md"
            report_json_path = tmp / "report.json"
            report_md_path = tmp / "report.md"
            _write_jsonl(input_path, [good, bad])

            exit_code = audit.main(
                [
                    "--accepted-jsonl",
                    str(input_path),
                    "--sample-size",
                    "2",
                    "--seed",
                    "7",
                    "--invariant-jsonl",
                    str(invariant_path),
                    "--audit-pack-md",
                    str(pack_path),
                    "--audit-report-json",
                    str(report_json_path),
                    "--audit-report-md",
                    str(report_md_path),
                ]
            )

            self.assertEqual(0, exit_code)
            report = json.loads(report_json_path.read_text(encoding="utf-8"))
            invariant_rows = [json.loads(line) for line in invariant_path.read_text(encoding="utf-8").splitlines()]
            failed_rows = [row for row in invariant_rows if not row["passed"]]
            self.assertEqual(1, report["hard_invariant_fail_count"])
            self.assertEqual(1, len(failed_rows))
            self.assertEqual("bad-final-success", failed_rows[0]["sample_id"])
            self.assertEqual("intermediate_failure_before_final_endsession_success", failed_rows[0]["reason"])

    def test_stratified_sampling_includes_each_label_when_possible(self) -> None:
        rows = [
            _candidate("pass-1", "pass", [_record("Get", "SUCCESS")]),
            _candidate("pass-2", "pass", [_record("Set", "SUCCESS")]),
            _candidate("fail-1", "fail", [_record("Set", "FAIL")]),
            _candidate("fail-2", "fail", [_record("Authenticate", "FAIL")]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "accepted.jsonl"
            _write_jsonl(input_path, rows)
            invariant_rows, selected_rows, report = audit.build_artifacts(input_path, sample_size=2, seed=13)

            self.assertEqual(4, len(invariant_rows))
            self.assertEqual(2, len(selected_rows))
            self.assertEqual({"fail": 1, "pass": 1}, report["sample_label_distribution"])
            self.assertEqual({"fail", "pass"}, {row["label"] for row in selected_rows})

    def test_audit_markdown_contains_empty_state_transition_sections(self) -> None:
        candidate = _candidate(
            "audit-target",
            "fail",
            [
                _record("StartSession", "SUCCESS"),
                _record("Set", "FAIL", [{"error": "denied"}]),
            ],
        )

        invariant_rows, accepted_rows = audit.audit_candidate_rows([(1, candidate)])
        selected_rows = audit.stratified_sample(accepted_rows, sample_size=1, seed=0)
        report = audit.build_report(
            input_path=Path("accepted.jsonl"),
            sample_size=1,
            seed=0,
            invariant_rows=invariant_rows,
            accepted_rows=accepted_rows,
            selected_rows=selected_rows,
        )
        markdown = audit.render_audit_pack_md(report, selected_rows)

        self.assertIn("### state_trace\n\n### observed_state_summary", markdown)
        self.assertIn("### audit_decision\n\n### rationale", markdown)
        self.assertIn("| index | method | status | return_value_count |", markdown)
        self.assertIn("sample_id: `audit-target`", markdown)
        self.assertIn("final `Set/FAIL`", audit.render_report_md(report))


if __name__ == "__main__":
    unittest.main()
