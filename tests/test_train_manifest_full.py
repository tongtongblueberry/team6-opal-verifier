# Added: cover full/selective FT dry-run without loading model dependencies.
# Why: the first validation gate must be cheap and independent from GPU/network state.

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.training import train_manifest_full


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "train_mode": "last-n-layers",
        "last_n_layers": 4,
        "unfreeze_embeddings": False,
        "batch_size": 1,
        "grad_accum": 8,
        "max_seq_len": 2048,
        "epochs": 1.0,
        "lr": 2e-5,
        "weight_decay": 0.01,
        "label_smoothing": 0.05,
        "warmup_ratio": 0.03,
        "torch_dtype": "float16",
        "save_steps": 100,
        "save_total_limit": 3,
        "logging_steps": 10,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TrainManifestFullTest(unittest.TestCase):
    def test_cli_defaults_are_selective_and_submission_dtype(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "train_manifest_full.py",
                "--manifest",
                "manifest.jsonl",
                "--run-root",
                "runs",
                "--model-name",
                "partial",
            ],
        ):
            args = train_manifest_full.parse_args()

        train_manifest_full.validate_args(args)

        self.assertEqual("last-n-layers", args.train_mode)
        self.assertEqual(4, args.last_n_layers)
        self.assertEqual("float16", args.torch_dtype)
        self.assertTrue(args.gradient_checkpointing)

    def test_invalid_values_fail_before_model_load(self) -> None:
        invalid_cases = (
            {"last_n_layers": 0},
            {"batch_size": 0},
            {"grad_accum": 0},
            {"max_seq_len": 7},
            {"epochs": 0},
            {"lr": 0},
            {"weight_decay": -0.1},
            {"label_smoothing": 1.0},
            {"warmup_ratio": 1.0},
            {"torch_dtype": "int8"},
            {"save_steps": 0},
            {"save_total_limit": 0},
            {"logging_steps": 0},
        )

        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                with mock.patch("tools.training.train_manifest_full.logger.error"):
                    with self.assertRaises(SystemExit):
                        train_manifest_full.validate_args(_args(**overrides))

    def test_dry_run_uses_train_split_only_and_writes_freeze_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            manifest = temp_dir / "manifest.jsonl"
            rows = [
                {"sample_id": "train-pass", "input": '{"records":[{"input":{},"output":{}}]}', "label": "pass", "split": "train"},
                {"sample_id": "train-fail", "input": '{"records":[{"input":{},"output":{"error":"x"}}]}', "label": "fail", "split": "train"},
                {"sample_id": "hidden-pass", "input": '{"records":[{"input":{},"output":{}}]}', "label": "pass", "split": "hidden"},
            ]
            manifest.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            with mock.patch.object(
                sys,
                "argv",
                [
                    "train_manifest_full.py",
                    "--manifest",
                    str(manifest),
                    "--run-root",
                    str(temp_dir / "run"),
                    "--model-name",
                    "dry_partial",
                    "--dry-run",
                    "--dry-run-samples",
                    "2",
                    "--train-mode",
                    "last-n-layers",
                    "--last-n-layers",
                    "2",
                ],
            ):
                with mock.patch(
                    "tools.training.train_manifest_full.load_tokenizer",
                    side_effect=RuntimeError("offline"),
                ):
                    exit_code = train_manifest_full.main()

            self.assertEqual(0, exit_code)
            report_path = temp_dir / "run" / "artifacts" / "dry_partial.train_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(3, report["manifest"]["total_rows"])
        self.assertEqual(2, report["manifest"]["train_rows"])
        self.assertEqual(1, report["manifest"]["skipped_non_train_rows"])
        self.assertEqual({"fail": 1, "pass": 1}, report["manifest"]["train_label_counts"])
        self.assertEqual("last-n-layers", report["parameter_freeze_plan"]["train_mode"])
        self.assertEqual(2, report["parameter_freeze_plan"]["last_n_layers"])
        self.assertFalse(report["parameter_freeze_plan"]["exact_parameter_counts"])
        self.assertTrue(report["dry_run"]["tokenizer_fallback"])


if __name__ == "__main__":
    unittest.main()
