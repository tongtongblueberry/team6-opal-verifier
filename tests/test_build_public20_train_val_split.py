# Changed: test deterministic public20 train/val split artifacts.
# Why: public20 model validation must train on public20 train rows, reserve only val rows, and never create a test split.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import build_public20_train_val_split as splitter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _fixture_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    inputs: list[dict[str, object]] = []
    labels: list[dict[str, object]] = []
    for index in range(1, 21):
        sample_id = f"tc{index}"
        inputs.append(
            {
                "sample_id": sample_id,
                "input": json.dumps({"records": [{"index": 1, "input": {"method": {"name": "Get"}}, "output": {"status_codes": "SUCCESS"}}]}),
                "source": "shape20_reference",
            }
        )
        labels.append(
            {
                "sample_id": sample_id,
                "label": "pass" if index <= 10 else "fail",
                "source": "local_eval_reference",
            }
        )
    return inputs, labels


class BuildPublic20TrainValSplitTests(unittest.TestCase):
    def test_build_split_has_expected_size_balance_and_no_test(self) -> None:
        inputs, labels = _fixture_rows()
        input_map = {str(row["sample_id"]): row for row in inputs}
        label_map = {str(row["sample_id"]): str(row["label"]) for row in labels}

        split = splitter.build_split(input_map, label_map, seed=11)
        report = split["report"]

        # Changed: assert the active 10/10 public20 split contract.
        # Why: the old 16/4 split is archive-only and must not pass as the default builder behavior.
        self.assertEqual(10, len(split["train_rows"]))
        self.assertEqual(10, len(split["val_rows"]))
        self.assertFalse(report["public20_test_split_created"])
        self.assertEqual(0, report["row_counts"]["test"])
        self.assertEqual([], report["sample_ids"]["test"])
        self.assertEqual({"fail": 5, "pass": 5}, report["label_counts"]["val"])
        self.assertEqual({"fail": 5, "pass": 5}, report["label_counts"]["train"])

    def test_default_output_root_is_active_10_10_path(self) -> None:
        parser = splitter.build_arg_parser()
        args = parser.parse_args([])

        # Changed: pin the CLI default output root to the active 10/10 split directory.
        # Why: runs/model_validation/public20_splits is archive-only for the old 16/4 artifacts.
        self.assertEqual(Path("runs/model_validation/public20_10_10_splits"), args.output_root)
        self.assertEqual(5, args.val_per_label)

    def test_cli_rejects_non_active_val_per_label(self) -> None:
        inputs, labels = _fixture_rows()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "public20_input.jsonl"
            labels_path = tmp / "public20_labels.local.jsonl"
            _write_jsonl(input_path, inputs)
            _write_jsonl(labels_path, labels)

            # Changed: keep --val-per-label visible while rejecting non-5 public20 runs.
            # Why: explicit CLI compatibility should not allow new 16/4 artifacts under the active contract.
            exit_code = splitter.main(
                [
                    "--input-jsonl",
                    str(input_path),
                    "--labels-jsonl",
                    str(labels_path),
                    "--output-root",
                    str(tmp / "splits"),
                    "--val-per-label",
                    "2",
                ]
            )

            self.assertEqual(2, exit_code)

    def test_split_is_deterministic_for_seed(self) -> None:
        inputs, labels = _fixture_rows()
        input_map = {str(row["sample_id"]): row for row in inputs}
        label_map = {str(row["sample_id"]): str(row["label"]) for row in labels}

        first = splitter.build_split(input_map, label_map, seed=29)
        second = splitter.build_split(input_map, label_map, seed=29)
        third = splitter.build_split(input_map, label_map, seed=47)

        self.assertEqual(first["report"]["sample_ids"]["val"], second["report"]["sample_ids"]["val"])
        self.assertNotEqual(first["report"]["sample_ids"]["val"], third["report"]["sample_ids"]["val"])

    def test_load_public20_requires_input_label_sample_id_match(self) -> None:
        inputs, labels = _fixture_rows()
        labels[-1]["sample_id"] = "missing-input"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "public20_input.jsonl"
            labels_path = tmp / "public20_labels.local.jsonl"
            _write_jsonl(input_path, inputs)
            _write_jsonl(labels_path, labels)

            with self.assertRaisesRegex(splitter.Public20SplitError, "input_label_sample_id_mismatch"):
                splitter.load_public20(input_path, labels_path)

    def test_cli_writes_three_seed_artifacts(self) -> None:
        inputs, labels = _fixture_rows()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "public20_input.jsonl"
            labels_path = tmp / "public20_labels.local.jsonl"
            output_root = tmp / "splits"
            _write_jsonl(input_path, inputs)
            _write_jsonl(labels_path, labels)

            exit_code = splitter.main(
                [
                    "--input-jsonl",
                    str(input_path),
                    "--labels-jsonl",
                    str(labels_path),
                    "--output-root",
                    str(output_root),
                    "--seeds",
                    "11",
                    "29",
                    "47",
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertTrue((output_root / "README.md").exists())
            for seed in (11, 29, 47):
                split_dir = output_root / f"split_seed_{seed}"
                self.assertTrue((split_dir / "train.jsonl").exists())
                self.assertTrue((split_dir / "val.jsonl").exists())
                self.assertTrue((split_dir / "split_report.json").exists())
                self.assertTrue((split_dir / "split_report.md").exists())
                train_rows = [json.loads(line) for line in (split_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()]
                val_rows = [json.loads(line) for line in (split_dir / "val.jsonl").read_text(encoding="utf-8").splitlines()]
                report = json.loads((split_dir / "split_report.json").read_text(encoding="utf-8"))
                # Changed: generated split JSONL now matches public20-shaped input/labels only.
                # Why: sample_id and split metadata belong in split_report, not data rows.
                self.assertEqual({"input", "labels"}, set(train_rows[0]))
                self.assertEqual({"input", "labels"}, set(val_rows[0]))
                # Changed: verify each generated seed report carries the active 10/10 counts.
                # Why: downstream training workers read split_report.json before consuming train/val rows.
                self.assertEqual(10, report["row_counts"]["train"])
                self.assertEqual(10, report["row_counts"]["val"])
                self.assertEqual(0, report["row_counts"]["test"])
                self.assertFalse(report["public20_test_split_created"])
                self.assertEqual({"fail": 5, "pass": 5}, report["label_counts"]["train"])
                self.assertEqual({"fail": 5, "pass": 5}, report["label_counts"]["val"])


if __name__ == "__main__":
    unittest.main()
