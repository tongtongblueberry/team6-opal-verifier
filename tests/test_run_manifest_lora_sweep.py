from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from tools.training import run_manifest_lora_sweep as sweep


class RunManifestLoraSweepTest(unittest.TestCase):
    def test_default_configs_cover_baseline_and_high_rank(self) -> None:
        configs = sweep.default_configs()
        names = [config.name for config in configs]
        self.assertIn("r16_lr1e3_do10_ep5", names)
        self.assertIn("r32_lr1e3_do10_ep5", names)
        self.assertIn("r64_lr1e3_do05_ep5", names)

    def test_train_command_includes_lora_cli_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            args = argparse.Namespace(
                python="python3",
                train_script="tools/training/train_manifest_lora.py",
                manifest="manifest.jsonl",
                base_model="Qwen/Qwen3.5-4B",
                resume=True,
                logging_steps=7,
            )
            config = sweep.SweepConfig(
                name="r32",
                lr=0.001,
                epochs=5,
                batch_size=2,
                grad_accum=4,
                lora_r=32,
                lora_alpha=64,
                lora_dropout=0.05,
            )
            command = sweep.build_train_command(args, config, Path(temp_name))

        self.assertIn("--lora-r", command)
        self.assertIn("32", command)
        self.assertIn("--lora-alpha", command)
        self.assertIn("64", command)
        self.assertIn("--lora-dropout", command)
        self.assertIn("0.05", command)
        self.assertIn("--resume", command)

    def test_parse_args_defaults_to_calibration_selection_metrics(self) -> None:
        # Changed: lock the runner CLI defaults to calibration split metrics.
        # Why: hidden metrics are reserved for no-peek validation reports.
        args = sweep.parse_args(["--manifest", "manifest.jsonl", "--run-root", "runs"])

        self.assertEqual(args.selection_metric, "metrics.by_split.calibration.accuracy")
        self.assertEqual(args.precision_metric, "metrics.by_split.calibration.precision_fail")
        self.assertEqual(args.recall_metric, "metrics.by_split.calibration.recall_fail")

    def test_choose_best_prefers_constraint_satisfying_result(self) -> None:
        args = argparse.Namespace(
            # Changed: choose_best fixture now uses calibration metric paths.
            # Why: runner defaults must align with calibration-first candidate selection.
            selection_metric="metrics.by_split.calibration.accuracy",
            precision_metric="metrics.by_split.calibration.precision_fail",
            recall_metric="metrics.by_split.calibration.recall_fail",
            min_fail_precision=0.90,
            min_fail_recall=0.80,
        )
        low_precision = {
            "status": "completed",
            "config": {"name": "high_acc_low_precision"},
            "paths": {"adapter_final": "a", "eval_json": "a.json"},
            "eval_summary": {
                "metrics": {
                    "by_split": {
                        "calibration": {
                            "accuracy": 0.99,
                            "precision_fail": 0.80,
                            "recall_fail": 1.00,
                        }
                    }
                }
            },
        }
        constrained = {
            "status": "completed",
            "config": {"name": "constrained"},
            "paths": {"adapter_final": "b", "eval_json": "b.json"},
            "eval_summary": {
                "metrics": {
                    "by_split": {
                        "calibration": {
                            "accuracy": 0.93,
                            "precision_fail": 0.95,
                            "recall_fail": 0.85,
                        }
                    }
                }
            },
        }

        best = sweep.choose_best([low_precision, constrained], args)

        self.assertIsNotNone(best)
        self.assertEqual("constrained", best["name"])
        self.assertTrue(best["constraints_applied"])

    def test_dry_run_writes_plan_without_process_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            exit_code = sweep.main(
                [
                    "--manifest",
                    "manifest.jsonl",
                    "--run-root",
                    temp_name,
                    "--dry-run",
                    "--limit-configs",
                    "1",
                ]
            )
            report_path = Path(temp_name) / "artifacts" / "manifest_lora_sweep_results.json"
            report_text = report_path.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        self.assertIn('"status": "planned"', report_text)
        self.assertIn("--lora-r", report_text)

    def test_completed_eval_must_match_train_hyperparameters_to_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            run_root = Path(temp_name)
            artifacts = run_root / "artifacts"
            artifacts.mkdir()
            eval_json = artifacts / "r32.eval_manifest.json"
            eval_json.write_text(
                json.dumps(
                    {
                        "arguments": {
                            "base_model": "Qwen/Qwen3.5-4B",
                            "threshold": 0.5,
                            "threshold_sweep": sweep.DEFAULT_THRESHOLD_SWEEP,
                        }
                    }
                ),
                encoding="utf-8",
            )
            train_report = artifacts / "r32.train_report.json"
            train_report.write_text(
                json.dumps(
                    {
                        "hyperparameters": {
                            "lr": 0.001,
                            "epochs": 5.0,
                            "batch_size": 2,
                            "grad_accum": 4,
                            "lora_r": 16,
                            "lora_alpha": 32,
                            "lora_dropout": 0.1,
                            "weight_decay": 0.05,
                            "label_smoothing": 0.1,
                            "max_seq_len": 2048,
                            "warmup_ratio": 0.05,
                            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
                            "seed": 42,
                        }
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                run_root=temp_name,
                base_model="Qwen/Qwen3.5-4B",
                threshold=0.5,
                threshold_sweep=sweep.DEFAULT_THRESHOLD_SWEEP,
            )
            config = sweep.SweepConfig(
                name="r32",
                lr=0.001,
                epochs=5.0,
                batch_size=2,
                grad_accum=4,
                lora_r=32,
                lora_alpha=64,
                lora_dropout=0.1,
            )

            matches, reason = sweep.completed_eval_matches_config(eval_json, config, args)

        self.assertFalse(matches)
        self.assertIn("lora_r", reason)


if __name__ == "__main__":
    unittest.main()
