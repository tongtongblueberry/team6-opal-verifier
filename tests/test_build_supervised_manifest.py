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

    def test_spec_grounding_metadata_stays_out_of_manifest_input(self) -> None:
        # Changed: assert spec-grounding metadata does not become model input text.
        # Why: generation must be spec-grounded while Gate C keeps the trainer input records-only.
        raw_records = [
            builder.RawRecord(
                path="grounded_candidate.jsonl",
                row=0,
                data={
                    "sample_id": "grounded",
                    "source": "self_instruct_candidate",
                    "records": [{"input": {"method": {"name": "Get"}}, "output": {"status_codes": "SUCCESS"}}],
                    "label": "pass",
                    "spec_grounding": [
                        {
                            "rule_ref": "RULE 01",
                            "source_path": "docs/legacy_spec_rules.md",
                            "source_span": "docs/legacy_spec_rules.md:10-15",
                            "condition": "A method is processed completely and without error by the TPer",
                            "expected_status": "SUCCESS (0x00)",
                        }
                    ],
                },
            )
        ]

        records, excluded_counts, rejections, _, _ = builder.build_manifest_records(raw_records, include_blocklisted=False)

        self.assertEqual(1, len(records))
        self.assertEqual(0, sum(excluded_counts.values()))
        self.assertEqual([], rejections)
        self.assertIn('"records":', records[0].input_text)
        self.assertNotIn("spec_grounding", records[0].input_text)
        self.assertNotIn("legacy_spec_rules", records[0].input_text)

    def test_record_count_preserving_length_selector_uses_reference_mean(self) -> None:
        # Changed: cover the optional record_count-aware length selector.
        # Why: token length-bin balancing alone can drop the wrong high-depth group when JSD ties.
        def manifest_record(sample_id: str, label: str, record_count: int, length_bin: str, group_id: str) -> builder.ManifestRecord:
            input_text = builder.stable_json({"records": [{"index": index, "payload": sample_id} for index in range(record_count)]})
            return builder.ManifestRecord(
                index=record_count,
                sample_id=sample_id,
                input_text=input_text,
                label=label,
                source="unit_test",
                label_source="label",
                template_id=f"tmpl-{sample_id}",
                mutation_family="record-count-selector",
                length_bin=length_bin,
                input_token_count=builder.token_count(input_text),
                content_hash=builder.content_hash(input_text, label),
                input_hash_no_label=builder.input_hash_no_label(input_text),
                parse_status="full_trajectory",
                metadata_only=False,
                prompt_schema_version=builder.PROMPT_SCHEMA_VERSION,
                prompt_schema_hash=builder.prompt_schema_hash(),
                family_component="unit_test::record-count-selector",
                group_id=group_id,
                path="unit.jsonl",
                row=record_count,
                blocklisted=False,
                blocklist_matches=(),
            )

        records = [
            manifest_record("short", "pass", 1, "1-32", "group-short"),
            manifest_record("middle", "fail", 10, "257-512", "group-middle"),
            manifest_record("drop-lower-depth", "pass", 20, "513-1024", "group-z"),
            manifest_record("keep-higher-depth", "fail", 30, "513-1024", "group-a"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            reference_path = Path(temp_dir) / "reference.jsonl"
            reference_rows = [
                {"sample_id": "ref-1", "length_bin": "1-32", "record_count": 1},
                {"sample_id": "ref-2", "length_bin": "257-512", "record_count": 10},
                {"sample_id": "ref-3", "length_bin": "513-1024", "record_count": 31},
            ]
            reference_path.write_text("".join(json.dumps(row) + "\n" for row in reference_rows), encoding="utf-8")
            args = type(
                "Args",
                (),
                {
                    "length_balance_reference": str(reference_path),
                    "length_balance_target_jsd": 0.001,
                    "length_balance_max_drop_fraction": 0.25,
                    "preserve_record_count_distribution": True,
                    "min_template_entropy": 0.0,
                    "max_top_template_share": 1.0,
                },
            )()

            outcome = builder.select_length_balanced_records(records, args)

        selected_ids = {record.sample_id for record in outcome.records}
        self.assertEqual({"short", "middle", "keep-higher-depth"}, selected_ids)
        self.assertTrue(outcome.report["record_count_preservation"]["applied"])
        self.assertEqual("record_count_preserving_target_reached", outcome.report["reason"])
        self.assertEqual(0.0, outcome.report["after"]["jsd"])


if __name__ == "__main__":
    unittest.main()
