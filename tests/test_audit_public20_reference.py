# Changed: cover public20 qualitative audit-pack generation.
# Why: public20 reference audits must be label-free while preserving local-only aggregate label summaries.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import audit_public20_reference as audit


def _record(method: str, status: str, return_values: list[object] | None = None) -> dict[str, object]:
    return {
        "index": 1,
        "input": {
            "invoking_id": {"name": "Session Manager UID"},
            "method": {"name": method},
            "status_codes": "SUCCESS",
        },
        "output": {"status_codes": status, "return_values": [] if return_values is None else return_values},
    }


def _public_raw_row(sample_id: str, records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "input": json.dumps({"records": records}, ensure_ascii=False, separators=(",", ":")),
        "source": "shape20_reference",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class Public20ReferenceAuditTests(unittest.TestCase):
    def test_builds_label_free_public20_pack_with_local_aggregate(self) -> None:
        rows = [
            _public_raw_row("tc-a", [_record("Properties", "SUCCESS")]),
            _public_raw_row("tc-b", [_record("StartSession", "SUCCESS"), _record("Get", "NOT_AUTHORIZED")]),
        ]
        labels = [
            {"sample_id": "tc-a", "label": "pass", "source": "local"},
            {"sample_id": "tc-b", "label": "fail", "source": "local"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            normalized_path = tmp / "public20.normalized.jsonl"
            labels_path = tmp / "public20_labels.local.jsonl"
            profile_path = tmp / "public20.profile.json"
            pack_path = tmp / "public20_reference_audit_pack.md"
            report_json_path = tmp / "public20_reference_audit_report.json"
            report_md_path = tmp / "public20_reference_audit_report.md"
            _write_jsonl(normalized_path, rows)
            _write_jsonl(labels_path, labels)
            profile_path.write_text(
                json.dumps(
                    {
                        "count": 2,
                        "final_method_counts": {"Get": 1, "Properties": 1},
                        "final_status_counts": {"NOT_AUTHORIZED": 1, "SUCCESS": 1},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = audit.main(
                [
                    "--normalized-jsonl",
                    str(normalized_path),
                    "--profile-json",
                    str(profile_path),
                    "--labels-local-jsonl",
                    str(labels_path),
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
            pack = pack_path.read_text(encoding="utf-8")
            self.assertEqual(2, report["total_public20_rows"])
            self.assertEqual(2, report["sample_size_actual"])
            self.assertEqual({"fail": 1, "pass": 1}, report["labels_local_only_summary"]["label_distribution"])
            self.assertTrue(report["labels_local_only_summary"]["sample_id_match"])
            self.assertIn("sample_id: `tc-a`", pack)
            self.assertIn("sample_id: `tc-b`", pack)
            self.assertIn("### state_trace\n\n### observed_state_summary", pack)
            self.assertIn("### shape_notes\n\n### audit_decision", pack)
            self.assertNotIn("label:", pack.lower())
            self.assertNotIn("pass", pack.lower())
            self.assertNotIn("fail", pack.lower())

    def test_sample_size_selects_subset_without_label_lookup(self) -> None:
        rows = [
            _public_raw_row("tc-a", [_record("Properties", "SUCCESS")]),
            _public_raw_row("tc-b", [_record("Get", "SUCCESS")]),
            _public_raw_row("tc-c", [_record("Set", "NOT_AUTHORIZED")]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            normalized_path = tmp / "public20.normalized.jsonl"
            _write_jsonl(normalized_path, rows)

            report = audit.build_artifacts(
                normalized_jsonl=normalized_path,
                profile_json=None,
                labels_local_jsonl=None,
                sample_size=2,
                seed=11,
            )

            self.assertEqual(3, report["total_public20_rows"])
            self.assertEqual(2, report["sample_size_actual"])
            self.assertFalse(report["labels_local_only_summary"]["available"])
            self.assertNotIn("label", report["audit_targets"][0])

    def test_public20_summary_handles_command_status_variant(self) -> None:
        row = {
            "sample_id": "tc-read",
            "input": json.dumps(
                {
                    "records": [
                        {
                            "index": 1,
                            "input": {"command": "Read", "args": {"LBA": "80 ~ 87"}},
                            "output": {"command": "Read", "args": {"result": "Pattern 8E"}},
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "source": "shape20_reference",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            path = tmp / "public20.normalized.jsonl"
            _write_jsonl(path, [row])
            normalized = audit.load_public20_rows(path)[0]

        summary = audit.public20_summary(normalized)

        self.assertEqual("Read", summary["final_method"])
        self.assertEqual("PATTERN 8E", summary["final_status"])
        self.assertEqual("Read", summary["record_summaries"][0]["method"])
        self.assertEqual("PATTERN 8E", summary["record_summaries"][0]["output_status"])


if __name__ == "__main__":
    unittest.main()
