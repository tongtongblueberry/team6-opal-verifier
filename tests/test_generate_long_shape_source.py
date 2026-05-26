# Added: cover v4 shape-source options without building a full manifest.
# Why: remaining v3 risks are missing 1-record trajectories and low strict char median ratio.

from __future__ import annotations

from collections import Counter
import json
import tempfile
import unittest
from pathlib import Path

from tools.datagen import generate_long_shape_source as source


def _get_success_case() -> dict[str, object]:
    return {
        "steps": [
            {
                "input": {
                    "method": {"name": "Get"},
                    "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "ShapeProbe"},
                    "args": {"required": {"Cellblock": [{"startColumn": 3}, {"endColumn": 3}]}, "optional": {}},
                },
                "output": {"return_values": [{"3": "shape_value"}], "status_codes": "SUCCESS"},
            }
        ],
        "label": "pass",
        "spec_rule": "unit-shape",
        "description": "unit shape case",
    }


class GenerateLongShapeSourceTests(unittest.TestCase):
    def test_single_record_family_writes_balanced_one_record_rows(self) -> None:
        cases = source.build_single_record_family(per_label=3)

        self.assertEqual({"fail": 3, "pass": 3}, dict(Counter(case["label"] for case in cases)))
        self.assertTrue(all(len(case["steps"]) == 1 for case in cases))

        with tempfile.TemporaryDirectory() as temp_name:
            output_path = Path(temp_name) / "single.jsonl"
            source.write_jsonl(cases, output_path=output_path, source_name="long_shape_v4_unit")
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(6, len(rows))
        self.assertEqual({"long_shape_v4_unit"}, {row["source"] for row in rows})
        self.assertTrue(all(len(row["records"]) == 1 for row in rows))
        self.assertIn("single-record", rows[0]["description"])

        summary = source.build_summary(
            cases,
            output_path=Path("single.jsonl"),
            target_lengths=[1],
            enrich_fraction=0.0,
            single_record_per_label=3,
            source_name="long_shape_v4_unit",
        )
        self.assertEqual(1, summary["record_count"]["min"])
        self.assertEqual(6, summary["single_record_total"])

    def test_char_enrichment_options_increase_compact_input_length(self) -> None:
        case = _get_success_case()
        before = source.char_count_for_steps(case["steps"])

        default_strength = source.enrich_get_success_payloads(
            case,
            min_tokens=0,
            min_chars=before + 600,
            field_cycles=1,
            value_repeat=1,
        )
        boosted = source.enrich_get_success_payloads(
            case,
            min_tokens=0,
            min_chars=before + 600,
            field_cycles=6,
            value_repeat=4,
        )

        default_chars = source.char_count_for_steps(default_strength["steps"])
        boosted_chars = source.char_count_for_steps(boosted["steps"])
        self.assertGreater(default_chars, before)
        self.assertGreater(boosted_chars, default_chars)
        self.assertGreaterEqual(boosted_chars, before + 600)

    def test_enrich_subset_uses_char_threshold_for_candidate_selection(self) -> None:
        case = _get_success_case()
        before = source.char_count_for_steps(case["steps"])
        enriched = source.enrich_subset(
            [case],
            fraction=1.0,
            min_tokens=0,
            min_chars=before + 500,
            field_cycles=6,
            value_repeat=3,
        )

        self.assertGreater(source.char_count_for_steps(enriched[0]["steps"]), before)


if __name__ == "__main__":
    unittest.main()
