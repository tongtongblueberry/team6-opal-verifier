# Changed: cover LoRA CLI/report validation without loading model dependencies.
# Why: Cycle 3 sweep jobs must fail fast before using GPU time.

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.training.train_manifest_lora import base_report, build_paths, parse_args, validate_args


# Changed: provide a complete argparse namespace for validation-only tests.
# Why: these tests should not depend on manifest files, Transformers, or PEFT.
def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "base_model": "Qwen/Qwen3.5-4B",
        "dry_run": False,
        "batch_size": 1,
        "grad_accum": 8,
        "max_seq_len": 2048,
        "epochs": 5,
        "lr": 1e-3,
        "weight_decay": 0.05,
        "label_smoothing": 0.1,
        "warmup_ratio": 0.05,
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.1,
        "target_modules": "q_proj,k_proj,v_proj,o_proj",
        "seed": 42,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


# Changed: verify the new LoRA CLI keeps prior defaults and report fields stable.
# Why: existing r16 baseline commands should remain behaviorally identical.
class TrainManifestLoraCliTest(unittest.TestCase):
    def test_lora_cli_defaults_match_existing_config(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "train_manifest_lora.py",
                "--manifest",
                "manifest.jsonl",
                "--run-root",
                "runs",
                "--adapter-name",
                "baseline",
            ],
        ):
            args = parse_args()

        validate_args(args)

        self.assertEqual(16, args.lora_r)
        self.assertEqual(32, args.lora_alpha)
        self.assertEqual(0.1, args.lora_dropout)
        self.assertEqual(["q_proj", "k_proj", "v_proj", "o_proj"], args.target_modules)

    def test_custom_lora_cli_values_are_normalized_and_reported(self) -> None:
        args = _args(
            lora_r=64,
            lora_alpha=128,
            lora_dropout=0.05,
            target_modules=" q_proj, v_proj , up_proj ",
        )

        validate_args(args)

        self.assertEqual(["q_proj", "v_proj", "up_proj"], args.target_modules)
        with tempfile.TemporaryDirectory() as temp_name:
            paths = build_paths(Path(temp_name), "r64")
            report = base_report(args, paths, {"total_rows": 0})

        hyperparameters = report["hyperparameters"]
        self.assertEqual(64, hyperparameters["lora_r"])
        self.assertEqual(128, hyperparameters["lora_alpha"])
        self.assertEqual(0.05, hyperparameters["lora_dropout"])
        self.assertEqual(["q_proj", "v_proj", "up_proj"], hyperparameters["target_modules"])

    def test_invalid_lora_values_fail_validation(self) -> None:
        invalid_cases = (
            {"lora_r": 0},
            {"lora_alpha": 0},
            {"lora_dropout": 1.0},
            {"lora_dropout": -0.1},
            {"target_modules": ""},
            {"target_modules": "q_proj,,v_proj"},
        )

        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                with mock.patch("tools.training.train_manifest_lora.logger.error"):
                    with self.assertRaises(SystemExit):
                        validate_args(_args(**overrides))


if __name__ == "__main__":
    unittest.main()
