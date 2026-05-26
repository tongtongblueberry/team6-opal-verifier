# Changed: cover public20 to TRL prompt-completion dataset conversion.
# Why: SFTTrainer must see separated prompt and completion fields without importing TRL.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.training import prepare_public20_sft_dataset as prepare


class PreparePublic20SftDatasetTests(unittest.TestCase):
    def test_converts_train_val_to_prompt_completion_jsonl(self) -> None:
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

        self.assertEqual("public20_trl_sft_prompt_completion", report["adapter"])
        self.assertFalse(report["custom_training_loop"])
        self.assertFalse(report["public20_test_split_created"])
        self.assertEqual(train_input + "\n", train_rows[0]["prompt"])
        self.assertEqual("pass", train_rows[0]["completion"])
        self.assertEqual(val_input + "\n", validation_rows[0]["prompt"])
        self.assertEqual("fail", validation_rows[0]["completion"])
        self.assertNotIn("label", train_rows[0])

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
