from __future__ import annotations

import argparse
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

    def test_choose_best_prefers_constraint_satisfying_result(self) -> None:
        args = argparse.Namespace(
            selection_metric="metrics.by_split.hidden.accuracy",
            precision_metric="metrics.by_split.hidden.precision_fail",
            recall_metric="metrics.by_split.hidden.recall_fail",
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
                        "hidden": {
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
                        "hidden": {
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


if __name__ == "__main__":
    unittest.main()
