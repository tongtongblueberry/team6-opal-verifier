# Changed: cover public20 input/labels dataset conversion.
# Why: persisted SFT files must match public20 while TRL mapping happens in memory.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.training import prepare_public20_sft_dataset as prepare


class PreparePublic20SftDatasetTests(unittest.TestCase):
    def _write_spec_rules(self, path: Path, long_condition: bool = False) -> None:
        condition = (
            "Set invoked with duplicate Locking range columns and a repeated ReadLocked value; "
            "the duplicated column makes the method invalid before any authorization state can change."
            if long_condition
            else "Including the same column multiple times in a single Set method invocation"
        )
        path.write_text(
            "\n".join(
                [
                    "# Test Spec Rules",
                    "",
                    "## CATEGORY 4: SET METHOD RULES (core/5.3.3.7.*, 5.3.4.2.6)",
                    "",
                    "### RULE 22: Same column multiple times in Set causes INVALID_PARAMETER",
                    "- SPEC: 5.3.4.2.6",
                    f"- CONDITION: {condition}",
                    "- EXPECTED_STATUS: INVALID_PARAMETER",
                    "- IF_VIOLATED: fail - duplicate columns should be rejected",
                    "- EXAMPLE_TRAJECTORY: Set on Locking range with ReadLocked=True, ReadLocked=False in same invocation",
                    "",
                    "### RULE 70: Random Count must be <= 32",
                    "- SPEC: opal/4.2.9.1",
                    "- CONDITION: Random method Count parameter > 32",
                    "- EXPECTED_STATUS: INVALID_PARAMETER",
                    "- IF_VIOLATED: fail - Count too large",
                    "- EXAMPLE_TRAJECTORY: Invoke Random with Count=64; should return INVALID_PARAMETER",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_converts_train_val_to_input_labels_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            split_dir = temp_dir / "split_seed_11"
            output_dir = temp_dir / "trl_sft"
            split_dir.mkdir()
            train_input = '{"records":[{"index":1,"input":{"command":"A"},"output":{"result":"ok"}}]}'
            val_input = '{"records":[{"index":1,"input":{"command":"B"},"output":{"result":"bad"}}]}'
            (split_dir / "train.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "tc1",
                        "input": train_input,
                        "label": "pass",
                        "split": "train",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (split_dir / "val.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "tc2",
                        "input": val_input,
                        "label": "FAIL",
                        "split": "val",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            report = prepare.convert_dataset(
                prepare.parse_args(
                    [
                        "--split-dir",
                        str(split_dir),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            )

            train_rows = [
                json.loads(line)
                for line in (output_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            validation_rows = [
                json.loads(line)
                for line in (output_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual("public20_trl_sft_input_labels", report["adapter"])
        self.assertFalse(report["custom_training_loop"])
        self.assertFalse(report["public20_test_split_created"])
        self.assertEqual({"input", "labels"}, set(train_rows[0]))
        self.assertEqual(train_input + "\n", train_rows[0]["input"])
        self.assertEqual("pass", train_rows[0]["labels"])
        self.assertEqual({"input", "labels"}, set(validation_rows[0]))
        self.assertEqual(val_input + "\n", validation_rows[0]["input"])
        self.assertEqual("fail", validation_rows[0]["labels"])
        self.assertNotIn("label", train_rows[0])

    def test_retrieved_spec_context_preserves_schema_and_source_spans(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            split_dir = temp_dir / "split_seed_11"
            output_dir = temp_dir / "trl_sft"
            spec_path = temp_dir / "legacy_spec_rules.md"
            split_dir.mkdir()
            self._write_spec_rules(spec_path)
            train_input = '{"records":[{"input":{"method":"Set","columns":["ReadLocked","ReadLocked"]},"output":{"status":"INVALID_PARAMETER"}}]}'
            val_input = '{"records":[{"input":{"method":"Random","Count":64},"output":{"status":"INVALID_PARAMETER"}}]}'
            (split_dir / "train.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "tc1",
                        "input": train_input,
                        "label": "pass",
                        "split": "train",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (split_dir / "val.jsonl").write_text(
                json.dumps(
                    {
                        "sample_id": "tc2",
                        "input": val_input,
                        "label": "fail",
                        "split": "val",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            report = prepare.convert_dataset(
                prepare.parse_args(
                    [
                        "--split-dir",
                        str(split_dir),
                        "--output-dir",
                        str(output_dir),
                        "--retrieved-spec-rules-md",
                        str(spec_path),
                        "--retrieved-spec-top-k",
                        "1",
                        "--retrieved-spec-max-context-chars",
                        "900",
                    ]
                )
            )
            train_row = json.loads((output_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual("public20_trl_sft_input_labels", report["adapter"])
        self.assertTrue(report["retrieved_spec_context"]["enabled"])
        self.assertEqual({"input", "labels"}, set(train_row))
        self.assertIn("Retrieved spec context:", train_row["input"])
        self.assertIn("RULE 22", train_row["input"])
        self.assertIn(str(spec_path), train_row["input"])
        self.assertEqual("pass", train_row["labels"])
        self.assertNotIn("label", train_row)

    def test_retrieved_spec_context_does_not_depend_on_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            spec_path = Path(temp_name) / "legacy_spec_rules.md"
            self._write_spec_rules(spec_path)
            cards = prepare.load_spec_rule_cards(spec_path)
            base_row = {
                "sample_id": "tc-same",
                "input": '{"records":[{"input":{"method":"Set","column":"ReadLocked"},"output":{"status":"INVALID_PARAMETER"}}]}',
                "split": "train",
            }
            pass_row = dict(base_row, label="pass")
            fail_row = dict(base_row, label="fail")

            converted_pass = prepare.convert_public20_row(
                pass_row,
                Path("train.jsonl"),
                1,
                "train",
                "\n",
                cards,
                1,
                900,
            )
            converted_fail = prepare.convert_public20_row(
                fail_row,
                Path("train.jsonl"),
                1,
                "train",
                "\n",
                cards,
                1,
                900,
            )

        self.assertEqual(converted_pass["input"], converted_fail["input"])
        self.assertEqual("pass", converted_pass["labels"])
        self.assertEqual("fail", converted_fail["labels"])

    def test_retrieved_spec_context_respects_max_context_chars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            spec_path = Path(temp_name) / "legacy_spec_rules.md"
            self._write_spec_rules(spec_path, long_condition=True)
            cards = prepare.load_spec_rule_cards(spec_path)
            row = {
                "sample_id": "tc-max",
                "input": '{"records":[{"input":{"method":"Set","columns":["ReadLocked","ReadLocked"]},"output":{"status":"INVALID_PARAMETER"}}]}',
                "label": "pass",
                "split": "train",
            }

            converted = prepare.convert_public20_row(
                row,
                Path("train.jsonl"),
                1,
                "train",
                "\n",
                cards,
                2,
                260,
            )

        self.assertIn("Retrieved spec context:", converted["input"])
        self.assertLessEqual(converted["_retrieved_spec_context_char_count"], 260)

    def test_rejects_public20_test_split(self) -> None:
        row = {
            "sample_id": "tc-test",
            "input": '{"records":[]}',
            "label": "pass",
            "split": "test",
        }

        with self.assertRaises(SystemExit):
            prepare.convert_public20_row(row, Path("val.jsonl"), 1, "val", "\n")


if __name__ == "__main__":
    unittest.main()
