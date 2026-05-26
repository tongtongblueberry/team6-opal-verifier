import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import validate_manifest as validator


# Changed: add focused tests for reference shape gates.
# Why: char-length drift and missing 1-record trajectories were the remaining data risks after v3 manifest repair.
def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _trajectory(record_count: int, filler: str) -> dict[str, object]:
    return {
        "records": [
            {
                "index": index,
                "input": {"command": "Get", "path": f"/shape/{index}", "payload": filler},
                "output": {"status": "SUCCESS", "value": filler},
            }
            for index in range(record_count)
        ]
    }


def _manifest_row(index: int, label: str, record_count: int, filler: str) -> dict[str, object]:
    return {
        "_manifest_line": index + 1,
        "sample_id": f"sample-{index}",
        "input": _compact_json(_trajectory(record_count, filler)),
        "label": label,
        "source": "synthetic_shape_gate_test",
        "label_source": "unit_test",
        "template_id": f"template-{index}",
        "mutation_family": "shape_gate",
        "length_bin": "129-256",
        "format_version": "canonical.v1",
        "content_hash": f"hash-{index}",
        "group_id": f"group-{index}",
        "split": "train",
        "path": f"unit/{index}.jsonl",
        "row": index,
    }


def _write_reference(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_compact_json(row) + "\n")


def _build_report(
    temp_dir: Path,
    manifest_rows: list[dict[str, object]],
    reference_rows: list[dict[str, object]],
    min_char_mean_ratio: float = 0.60,
    min_char_median_ratio: float = 0.60,
    max_min_record_count_gap: int = 1,
) -> dict[str, object]:
    reference_path = temp_dir / "reference.jsonl"
    _write_reference(reference_path, reference_rows)
    reference_counts, reference_errors, reference_record_count, reference_skipped, reference_shape_summary = (
        validator.load_reference_length_counts(reference_path)
    )
    return validator.build_report(
        records=manifest_rows,
        parse_errors=[],
        manifest_path=temp_dir / "manifest.jsonl",
        reference_path=reference_path,
        reference_length_counts=reference_counts,
        reference_errors=reference_errors,
        reference_skipped=reference_skipped,
        reference_record_count=reference_record_count,
        reference_shape_summary=reference_shape_summary,
        report_json_path=temp_dir / "report.json",
        report_md_path=temp_dir / "report.md",
        min_template_entropy=0.0,
        max_top_template_share=1.0,
        max_length_jsd=1.0,
        min_char_mean_ratio=min_char_mean_ratio,
        min_char_median_ratio=min_char_median_ratio,
        max_min_record_count_gap=max_min_record_count_gap,
    )


class ValidateManifestShapeGateTests(unittest.TestCase):
    def test_strict_min_record_count_gap_fails_when_reference_has_one_record_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            manifest_rows = [
                _manifest_row(0, "pass", 2, "short"),
                _manifest_row(1, "fail", 2, "short"),
            ]
            reference_rows = [
                {"input": _compact_json(_trajectory(1, "reference one record"))},
                {"input": _compact_json(_trajectory(2, "reference two records"))},
            ]

            report = _build_report(
                temp_dir,
                manifest_rows,
                reference_rows,
                min_char_mean_ratio=0.0,
                min_char_median_ratio=0.0,
                max_min_record_count_gap=0,
            )

        gate = report["gate_status"]["min_record_count_gap_lte_threshold"]
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["value"], 1)
        self.assertIn("1-record shortest case", gate["detail"]["message"])
        self.assertEqual(report["metrics"]["reference_record_count_stats"]["min"], 1)
        self.assertEqual(report["metrics"]["record_count_stats"]["min"], 2)

    def test_char_length_ratio_gates_fail_and_report_reference_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            manifest_rows = [
                _manifest_row(0, "pass", 2, "x"),
                _manifest_row(1, "fail", 2, "x"),
            ]
            reference_rows = [
                {"input": _compact_json(_trajectory(2, "reference payload " * 80))},
                {"input": _compact_json(_trajectory(2, "reference payload " * 90))},
            ]

            report = _build_report(
                temp_dir,
                manifest_rows,
                reference_rows,
                min_char_mean_ratio=0.90,
                min_char_median_ratio=0.90,
                max_min_record_count_gap=1,
            )
            markdown = validator.render_markdown(report)

        mean_gate = report["gate_status"]["char_length_mean_ratio_gte_threshold"]
        median_gate = report["gate_status"]["char_length_median_ratio_gte_threshold"]
        self.assertFalse(mean_gate["passed"])
        self.assertFalse(median_gate["passed"])
        self.assertLess(report["metrics"]["char_length_mean_ratio"], 0.90)
        self.assertLess(report["metrics"]["char_length_median_ratio"], 0.90)
        self.assertGreater(report["metrics"]["reference_char_length_stats"]["mean"], report["metrics"]["char_length_stats"]["mean"])
        self.assertIn("char length mean ratio", markdown)
        self.assertIn("reference char stats", markdown)


if __name__ == "__main__":
    unittest.main()
