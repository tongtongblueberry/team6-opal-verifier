# Changed: cover supervised manifest loading for labeled trajectory payloads.
# Why: records+label examples and score-only artifacts need regression tests.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import build_supervised_manifest as builder


# Changed: write JSON fixtures through the same file loader used by the CLI.
# Why: the regression is in raw record discovery, not only manifest materialization.
def _write_json(temp_dir: str, name: str, payload: object) -> Path:
    path = Path(temp_dir) / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# Changed: verify trajectory examples remain single supervised units.
# Why: flattening records steps corrupts labels and loses full trajectory context.
class BuildSupervisedManifestTests(unittest.TestCase):
    def test_records_label_parent_yields_one_raw_record_with_records_input(self) -> None:
        case = {
            "sample_id": "traj-1",
            "source": "synthetic_trajectory",
            "records": [
                {"step": 0, "event": "start", "status": "accepted"},
                {"step": 1, "event": "finish", "status": "failed"},
            ],
            "label": "pass",
            "ifd_score": 0.91,
            "metrics": {"loss": 0.2},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_json(temp_dir, "trajectory.json", case)
            raw_records = builder.load_json_records(path)

        self.assertEqual(1, len(raw_records))
        self.assertEqual(case, raw_records[0].data)

        records, excluded_counts, rejections, _, _ = builder.build_manifest_records(raw_records, include_blocklisted=False)

        self.assertEqual(1, len(records))
        self.assertEqual(0, sum(excluded_counts.values()))
        self.assertEqual([], rejections)
        self.assertEqual("pass", records[0].label)
        self.assertEqual(builder.stable_json({"records": case["records"]}), records[0].input_text)
        self.assertIn('"status":"failed"', records[0].input_text)
        self.assertNotIn("ifd_score", records[0].input_text)
        self.assertNotIn("metrics", records[0].input_text)

    def test_records_internal_steps_are_not_flattened(self) -> None:
        payload = [
            {
                "sample_id": "case-a",
                "records": [{"step": 0, "request": "alpha request", "label": "fail"}],
                "label": "pass",
            },
            {
                "sample_id": "case-b",
                "records": [{"step": 0, "request": "beta request", "label": "pass"}],
                "label": "fail",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_json(temp_dir, "trajectories.json", payload)
            raw_records = builder.load_json_records(path)

        self.assertEqual(["case-a", "case-b"], [raw.data.get("sample_id") for raw in raw_records])
        self.assertTrue(all(isinstance(raw.data.get("records"), list) for raw in raw_records))

        records, _, _, _, _ = builder.build_manifest_records(raw_records, include_blocklisted=False)

        self.assertEqual(["case-a", "case-b"], [record.sample_id for record in records])
        self.assertEqual(["pass", "fail"], [record.label for record in records])
        self.assertTrue(all('"records":' in record.input_text for record in records))

    def test_ifd_score_only_auxiliary_row_is_excluded(self) -> None:
        raw_records = [
            builder.RawRecord(
                path="ifd_scores.json",
                row=0,
                data={"sample_id": "score-row", "source": "synthetic", "label": "pass", "ifd_score": 0.87},
            )
        ]

        records, excluded_counts, rejections, _, _ = builder.build_manifest_records(raw_records, include_blocklisted=False)

        self.assertEqual([], records)
        self.assertEqual(1, excluded_counts["auxiliary_record"])
        self.assertEqual(1, len(rejections))
        self.assertEqual("auxiliary_record", rejections[0].reason)
        self.assertIn("ifd_score", rejections[0].detail)

    def test_same_records_input_with_conflicting_labels_is_excluded(self) -> None:
        records_payload = [{"index": 0, "input": "same trajectory", "output": "ok"}]
        raw_records = [
            builder.RawRecord(path="conflicts.jsonl", row=0, data={"sample_id": "conflict-pass", "records": records_payload, "label": "pass"}),
            builder.RawRecord(path="conflicts.jsonl", row=1, data={"sample_id": "conflict-fail", "records": records_payload, "label": "fail"}),
        ]

        records, excluded_counts, rejections, _, _ = builder.build_manifest_records(raw_records, include_blocklisted=False)

        self.assertEqual([], records)
        self.assertEqual(2, excluded_counts["label_conflict"])
        self.assertEqual(1, len(rejections))
        self.assertEqual("label_conflict", rejections[0].reason)
        self.assertIn("input_hash_no_label", rejections[0].detail)

    def test_manifest_row_contains_p0_semantic_fields(self) -> None:
        raw_records = [
            builder.RawRecord(
                path="semantic.jsonl",
                row=0,
                data={"sample_id": "semantic", "source": "synthetic", "records": [{"input": "a", "output": "b"}], "label": "pass"},
            )
        ]

        records, excluded_counts, _, _, _ = builder.build_manifest_records(raw_records, include_blocklisted=False)
        row = builder.manifest_row(records[0], "train")

        self.assertEqual(0, sum(excluded_counts.values()))
        self.assertEqual("full_trajectory", row["parse_status"])
        self.assertFalse(row["metadata_only"])
        self.assertEqual(builder.prompt_schema_hash(), row["prompt_schema_hash"])
        self.assertEqual(builder.input_hash_no_label(records[0].input_text), row["input_hash_no_label"])
        self.assertEqual(builder.token_count(records[0].input_text), row["input_token_count"])
        self.assertEqual(builder.family_component_for_record(records[0].source, records[0].template_id), row["family_component"])


if __name__ == "__main__":
    unittest.main()
