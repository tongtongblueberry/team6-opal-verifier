# Changed: test Gate B public20/generated dimension comparison reports.
# Why: generated candidate profile comparison must work before real generated data exists.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import compare_public20_dimensions as compare


def _profile(
    sample_id: str,
    record_count: int,
    input_json_chars: int,
    methods: list[str],
    statuses: list[str],
    label: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "sample_id": sample_id,
        "record_count": record_count,
        "method_sequence": methods,
        "method_sequence_length": len(methods),
        "input_json_chars": input_json_chars,
        "final_method": methods[-1] if methods else "",
        "status_sequence": statuses,
        "final_status": statuses[-1] if statuses else "",
        "return_value_counts": [1 for _ in range(record_count)],
        "total_return_value_count": record_count,
        "final_return_value_count": 1 if record_count else 0,
        "length_bin": "1-32" if record_count <= 32 else "33-64",
    }
    if label is not None:
        row["label"] = label
    return row


def _report(schema_version: str, profiles: list[dict[str, object]], label_counts: dict[str, int] | None = None) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": schema_version,
        "input": "fixture.jsonl",
        "count": len(profiles),
        "profiles": profiles,
    }
    if label_counts is not None:
        report["label_counts"] = label_counts
    return report


class ComparePublic20DimensionsTests(unittest.TestCase):
    def test_builds_json_report_with_no_go_warnings(self) -> None:
        public = _report(
            "self_instruct.seed_profile.v1",
            [
                _profile("tc1", 1, 100, ["Properties"], ["SUCCESS"]),
                _profile("tc2", 3, 300, ["StartSession", "Set", "EndSession"], ["SUCCESS", "SUCCESS", "SUCCESS"]),
            ],
        )
        generated = _report(
            "self_instruct.candidate_profile.v1",
            [
                _profile("si1", 5, 500, ["StartSession", "Get", "Set", "Get", "Set"], ["SUCCESS"] * 5, "pass"),
                _profile("si2", 7, 700, ["StartSession", "UNKNOWN", "EndSession"], ["SUCCESS", "FAIL", ""], "fail"),
            ],
            {"pass": 1, "fail": 1},
        )

        result = compare.compare_profiles(public, generated)

        self.assertEqual("self_instruct.gate_b_dimension_comparison.v1", result["schema_version"])
        self.assertEqual(2, result["public"]["count"])
        self.assertEqual(2, result["generated"]["count"])
        self.assertEqual(2.0, result["public"]["numeric_stats"]["record_count"]["mean"])
        self.assertEqual(6.0, result["generated"]["numeric_stats"]["record_count"]["mean"])
        codes = {warning["code"] for warning in result["no_go_warnings"]}
        self.assertIn("record_count_mean_difference", codes)
        self.assertIn("generated_final_status_blank_count", codes)
        self.assertIn("generated_unknown_method_or_status_count", codes)

    def test_cli_writes_json_and_markdown_with_public_label_aggregate(self) -> None:
        public = _report("self_instruct.seed_profile.v1", [_profile("tc1", 1, 100, ["Get"], ["SUCCESS"])])
        generated = _report(
            "self_instruct.candidate_profile.v1",
            [_profile("si1", 1, 120, ["Get"], ["SUCCESS"], "pass")],
            {"pass": 1},
        )
        public_labels = {"label_distribution_local_eval_only": {"pass": 1, "fail": 0}}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            public_path = tmp / "public.profile.json"
            generated_path = tmp / "generated.profile.json"
            labels_path = tmp / "public_labels.aggregate.json"
            output_json = tmp / "comparison.json"
            output_md = tmp / "comparison.md"
            public_path.write_text(json.dumps(public), encoding="utf-8")
            generated_path.write_text(json.dumps(generated), encoding="utf-8")
            labels_path.write_text(json.dumps(public_labels), encoding="utf-8")

            exit_code = compare.main(
                [
                    "--public-profile",
                    str(public_path),
                    "--generated-profile",
                    str(generated_path),
                    "--public-label-distribution",
                    str(labels_path),
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                ]
            )

            self.assertEqual(0, exit_code)
            report = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            self.assertEqual({"fail": 0, "pass": 1}, report["label_distribution"]["public_local_eval_only"])
            self.assertEqual({"pass": 1}, report["label_distribution"]["generated"])
            self.assertIn("Gate B Dimension Comparison", markdown)
            self.assertIn("generation, judge, manifest, training input", markdown)

    def test_generated_label_distribution_is_optional(self) -> None:
        public = _report("self_instruct.seed_profile.v1", [_profile("tc1", 1, 100, ["Get"], ["SUCCESS"])])
        generated = _report("self_instruct.candidate_profile.v1", [_profile("si1", 1, 100, ["Get"], ["SUCCESS"])])

        result = compare.compare_profiles(public, generated)

        self.assertIsNone(result["label_distribution"]["generated"])
        self.assertIsNone(result["label_distribution"]["public_local_eval_only"])


if __name__ == "__main__":
    unittest.main()
