from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.eval import select_manifest_sweep_candidate as selector


# Changed: cover threshold-aware post-processing without importing model, rule, or solver code.
# Why: candidate selection must be reproducible from archived manifest sweep JSON artifacts only.
class SelectManifestSweepCandidateTests(unittest.TestCase):
    def metric_block(
        self,
        *,
        accuracy: float,
        precision_fail: float,
        recall_fail: float,
        brier_score: float,
        ece: float,
    ) -> dict[str, object]:
        return {
            "n": 20,
            "threshold": 0.0,
            "accuracy": accuracy,
            "precision_fail": precision_fail,
            "recall_fail": recall_fail,
            "f1_fail": 0.0,
            "precision_pass": 0.0,
            "recall_pass": 0.0,
            "f1_pass": 0.0,
            "macro_f1": 0.0,
            "balanced_accuracy": 0.0,
            "brier_score": brier_score,
            "ece": ece,
            "ece_bins": 10,
            "confusion_matrix": {"TP": 0, "TN": 0, "FP": 0, "FN": 0},
            "mean_p_fail_by_gold": {"pass": 0.2, "fail": 0.8},
        }

    def threshold_entry(
        self,
        threshold: float,
        *,
        accuracy: float,
        precision_fail: float,
        recall_fail: float,
        brier_score: float,
        ece: float,
        hidden_accuracy: float | None = None,
        hidden_precision_fail: float | None = None,
        hidden_recall_fail: float | None = None,
        hidden_brier_score: float | None = None,
        hidden_ece: float | None = None,
    ) -> dict[str, object]:
        # Changed: fixture entries now separate calibration selection metrics from hidden validation metrics.
        # Why: default selector behavior must be tested as calibration-first with hidden preserved only for review.
        calibration = self.metric_block(
            accuracy=accuracy,
            precision_fail=precision_fail,
            recall_fail=recall_fail,
            brier_score=brier_score,
            ece=ece,
        )
        hidden = self.metric_block(
            accuracy=hidden_accuracy if hidden_accuracy is not None else accuracy,
            precision_fail=hidden_precision_fail if hidden_precision_fail is not None else precision_fail,
            recall_fail=hidden_recall_fail if hidden_recall_fail is not None else recall_fail,
            brier_score=hidden_brier_score if hidden_brier_score is not None else brier_score,
            ece=hidden_ece if hidden_ece is not None else ece,
        )
        calibration["threshold"] = threshold
        hidden["threshold"] = threshold
        overall = dict(calibration)
        return {
            "threshold": threshold,
            "metrics": {
                "overall": overall,
                "by_split": {
                    "calibration": calibration,
                    "hidden": hidden,
                },
            },
        }

    def write_eval_report(self, path: Path, entries: list[dict[str, object]]) -> None:
        path.write_text(
            json.dumps(
                {
                    "metrics": None,
                    "threshold_sweep": {
                        "enabled": True,
                        "thresholds": [entry["threshold"] for entry in entries],
                        "metrics_by_threshold": entries,
                    },
                }
            ),
            encoding="utf-8",
        )

    def write_sweep_report(self, path: Path, eval_paths: dict[str, Path]) -> None:
        path.write_text(
            json.dumps(
                {
                    "created_at_kst": "2026-05-26T00:00:00+09:00",
                    "manifest": "manifest.jsonl",
                    "run_root": str(path.parent.parent),
                    "best": {"name": "base_threshold_best"},
                    "results": [
                        {
                            "status": "completed",
                            "config": {"name": name, "lora_r": 16},
                            "paths": {
                                "adapter_final": f"adapters/{name}/final",
                                "eval_json": str(eval_path),
                            },
                            "eval_summary": {
                                "threshold_sweep": {
                                    "metrics_by_threshold": [
                                        self.threshold_entry(
                                            0.5,
                                            accuracy=0.1,
                                            precision_fail=0.1,
                                            recall_fail=0.1,
                                            brier_score=0.9,
                                            ece=0.9,
                                        )
                                    ]
                                }
                            },
                        }
                        for name, eval_path in eval_paths.items()
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_selects_best_calibration_threshold_from_eval_json_not_summary_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            first_eval = artifacts / "first.eval_manifest.json"
            second_eval = artifacts / "second.eval_manifest.json"
            self.write_eval_report(
                first_eval,
                [
                    self.threshold_entry(
                        0.5,
                        accuracy=0.99,
                        precision_fail=0.80,
                        recall_fail=0.90,
                        brier_score=0.20,
                        ece=0.10,
                    ),
                    self.threshold_entry(
                        0.7,
                        accuracy=0.94,
                        precision_fail=0.92,
                        recall_fail=0.82,
                        brier_score=0.11,
                        ece=0.04,
                        hidden_accuracy=0.70,
                        hidden_precision_fail=0.99,
                        hidden_recall_fail=0.99,
                        hidden_brier_score=0.30,
                        hidden_ece=0.20,
                    ),
                ],
            )
            self.write_eval_report(
                second_eval,
                [
                    self.threshold_entry(
                        0.6,
                        accuracy=0.93,
                        precision_fail=0.95,
                        recall_fail=0.81,
                        brier_score=0.09,
                        ece=0.03,
                        hidden_accuracy=0.99,
                        hidden_precision_fail=0.99,
                        hidden_recall_fail=0.99,
                        hidden_brier_score=0.05,
                        hidden_ece=0.01,
                    )
                ],
            )
            sweep_json = artifacts / "manifest_lora_sweep_results.json"
            self.write_sweep_report(sweep_json, {"first": first_eval, "second": second_eval})

            report = selector.build_selection_report(sweep_json, selector.SelectionOptions())

        self.assertEqual(report["base_threshold_best"], {"name": "base_threshold_best"})
        # Changed: assert default selection paths are calibration-based.
        # Why: a higher hidden score must not override the calibration-first winner.
        self.assertEqual(report["selection"]["split"], "calibration")
        self.assertEqual(report["selection"]["selection_metric"], "metrics.by_split.calibration.accuracy")
        self.assertEqual(report["best"]["config_name"], "first")
        self.assertEqual(report["best"]["threshold"], 0.7)
        self.assertEqual(report["best"]["selection_metric_value"], 0.94)
        self.assertEqual(report["best"]["calibration"]["calibration"]["brier_score"], 0.11)
        self.assertEqual(report["best"]["calibration"]["calibration"]["ece"], 0.04)

    def test_preserves_hidden_metrics_as_no_peek_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            eval_json = artifacts / "candidate.eval_manifest.json"
            self.write_eval_report(
                eval_json,
                [
                    self.threshold_entry(
                        0.55,
                        accuracy=0.91,
                        precision_fail=0.93,
                        recall_fail=0.84,
                        brier_score=0.12,
                        ece=0.05,
                        hidden_accuracy=0.77,
                        hidden_precision_fail=0.88,
                        hidden_recall_fail=0.79,
                        hidden_brier_score=0.22,
                        hidden_ece=0.09,
                    )
                ],
            )
            sweep_json = artifacts / "manifest_lora_sweep_results.json"
            self.write_sweep_report(sweep_json, {"candidate": eval_json})

            report = selector.build_selection_report(sweep_json, selector.SelectionOptions())

        # Changed: verify hidden metrics are copied into the validation block, not the selection block.
        # Why: hidden scores must stay inspectable without affecting calibration-first ranking.
        no_peek = report["best"]["no_peek_validation"]
        self.assertEqual(no_peek["split"], "hidden")
        self.assertEqual(no_peek["metrics"]["accuracy"], 0.77)
        self.assertEqual(no_peek["metrics"]["precision_fail"], 0.88)
        self.assertEqual(no_peek["summary"]["brier_score"], 0.22)
        self.assertEqual(report["best"]["metrics"]["calibration"]["accuracy"], 0.91)

    def test_reports_no_best_when_constraints_are_not_satisfied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            eval_json = artifacts / "low_precision.eval_manifest.json"
            self.write_eval_report(
                eval_json,
                [
                    self.threshold_entry(
                        0.5,
                        accuracy=0.99,
                        precision_fail=0.50,
                        recall_fail=0.99,
                        brier_score=0.12,
                        ece=0.06,
                    )
                ],
            )
            sweep_json = artifacts / "manifest_lora_sweep_results.json"
            self.write_sweep_report(sweep_json, {"low_precision": eval_json})

            report = selector.build_selection_report(sweep_json, selector.SelectionOptions())

        self.assertIsNone(report["best"])
        self.assertEqual(report["counts"]["constraint_satisfying_thresholds"], 0)
        self.assertEqual(report["best_relaxed"]["config_name"], "low_precision")
        self.assertFalse(report["best_relaxed"]["constraints_satisfied"])

    def test_markdown_report_summarizes_best_candidate(self) -> None:
        report = {
            "created_at_kst": "2026-05-26T00:00:00+09:00",
            "input": {"sweep_json": "artifacts/manifest_lora_sweep_results.json"},
            "selection": {
                # Changed: markdown fixture follows the calibration-first report default.
                # Why: formatter coverage should reflect the default selector contract.
                "split": "calibration",
                "selection_metric": "metrics.by_split.calibration.accuracy",
                "selection_direction": "max",
                "precision_metric": "metrics.by_split.calibration.precision_fail",
                "recall_metric": "metrics.by_split.calibration.recall_fail",
                "min_fail_precision": 0.9,
                "min_fail_recall": 0.8,
            },
            "counts": {"candidate_thresholds": 1, "constraint_satisfying_thresholds": 1},
            "base_threshold_best": {"name": "base"},
            "best": {
                "config_name": "chosen",
                "threshold": 0.65,
                "selection_metric_value": 0.91,
                "precision_metric_value": 0.92,
                "recall_metric_value": 0.83,
                "eval_json": "chosen.eval_manifest.json",
                "calibration": {"calibration": {"brier_score": 0.08, "ece": 0.02}},
                # Changed: markdown fixture includes the hidden no-peek validation block.
                # Why: formatter should keep hidden metrics separate from calibration selection output.
                "no_peek_validation": {
                    "split": "hidden",
                    "metrics": {
                        "accuracy": 0.71,
                        "precision_fail": 0.81,
                        "recall_fail": 0.72,
                        "brier_score": 0.18,
                        "ece": 0.06,
                    },
                },
            },
            "top_candidates": [
                {
                    "config_name": "chosen",
                    "threshold": 0.65,
                    "selection_metric_value": 0.91,
                    "precision_metric_value": 0.92,
                    "recall_metric_value": 0.83,
                    "eval_json": "chosen.eval_manifest.json",
                    "calibration": {"calibration": {"brier_score": 0.08, "ece": 0.02}},
                }
            ],
            "skipped_results": [],
        }

        markdown = selector.format_markdown_report(report)

        self.assertIn("# Threshold-aware Manifest Sweep Candidate", markdown)
        self.assertIn("`chosen`", markdown)
        self.assertIn("0.650000", markdown)
        self.assertIn("0.080000", markdown)
        self.assertIn("## No-peek Validation", markdown)
        self.assertIn("0.710000", markdown)


if __name__ == "__main__":
    unittest.main()
