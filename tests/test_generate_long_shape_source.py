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

    def test_max_enriched_tokens_caps_bin_overflow_with_dense_char_fill(self) -> None:
        # 변경: v4.1 bin-aware enrichment가 513-1024 bin overflow를 막는지 고정한다.
        # 이유: char median을 올리면서도 length JSD gate를 회복해야 하기 때문이다.
        case = _get_success_case()
        before_tokens = source.token_count_for_steps(case["steps"])
        before_chars = source.char_count_for_steps(case["steps"])
        max_tokens = before_tokens + 8

        enriched = source.enrich_get_success_payloads(
            case,
            min_tokens=max_tokens,
            min_chars=before_chars + 700,
            field_cycles=12,
            value_repeat=8,
            max_tokens=max_tokens,
        )

        after_tokens = source.token_count_for_steps(enriched["steps"])
        after_chars = source.char_count_for_steps(enriched["steps"])
        self.assertLessEqual(after_tokens, max_tokens)
        self.assertGreater(after_chars, before_chars)
        self.assertEqual(source.token_bin(after_tokens), source.token_bin(max_tokens))

    def test_enrich_subset_rejects_min_tokens_above_max_tokens(self) -> None:
        # 변경: 불가능한 token 목표 조합을 조기에 실패시킨다.
        # 이유: v4.1 command 실수로 cap보다 높은 minimum을 주면 조용히 왜곡된 데이터를 만들 수 있다.
        with self.assertRaisesRegex(ValueError, "min-enriched-tokens"):
            source.enrich_subset(
                [_get_success_case()],
                fraction=1.0,
                min_tokens=513,
                min_chars=0,
                max_tokens=512,
            )

    def test_token_only_selection_does_not_enrich_char_only_candidate(self) -> None:
        # 변경: token-bin matching 후보 선별과 char-density 후보 선별을 분리한다.
        # 이유: char 보강만 필요한 row까지 257-token bin으로 끌어올리는 v4 실패 원인을 막기 위해서다.
        case = _get_success_case()
        before_chars = source.char_count_for_steps(case["steps"])
        enriched = source.enrich_subset(
            [case],
            fraction=1.0,
            min_tokens=0,
            min_chars=before_chars + 500,
            field_cycles=6,
            value_repeat=3,
            selection_mode="token-only",
        )

        self.assertEqual(before_chars, source.char_count_for_steps(enriched[0]["steps"]))

    def test_dense_char_fill_subset_increases_chars_without_token_growth(self) -> None:
        # 변경: dense no-whitespace fill이 token-bin을 움직이지 않고 char 길이만 올리는지 고정한다.
        # 이유: v4.1 strict gate는 length JSD와 char median ratio를 동시에 만족해야 하기 때문이다.
        case = _get_success_case()
        before_tokens = source.token_count_for_steps(case["steps"])
        before_chars = source.char_count_for_steps(case["steps"])
        enriched = source.dense_char_fill_subset(
            [case],
            fraction=1.0,
            min_chars=before_chars + 600,
            field_cycles=8,
            value_repeat=4,
            max_tokens=before_tokens,
        )

        self.assertEqual(before_tokens, source.token_count_for_steps(enriched[0]["steps"]))
        self.assertGreaterEqual(source.char_count_for_steps(enriched[0]["steps"]), before_chars + 600)


if __name__ == "__main__":
    unittest.main()
