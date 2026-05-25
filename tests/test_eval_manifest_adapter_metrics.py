import math
import unittest
from contextlib import redirect_stderr
from io import StringIO

from tools.eval import eval_manifest_adapter as eval_adapter


class EvalManifestAdapterMetricTests(unittest.TestCase):
    def test_compute_metrics_adds_macro_balanced_brier_and_ece(self) -> None:
        predictions = [
            {"gold": "pass", "split": "calibration", "p_fail": 0.1, "prediction": "fail"},
            {"gold": "pass", "split": "calibration", "p_fail": 0.6, "prediction": "pass"},
            {"gold": "fail", "split": "calibration", "p_fail": 0.8, "prediction": "pass"},
            {"gold": "fail", "split": "calibration", "p_fail": 0.4, "prediction": "fail"},
        ]

        metrics = eval_adapter.compute_metrics(predictions, threshold=0.5)
        overall = metrics["overall"]

        self.assertEqual(overall["confusion_matrix"], {"TP": 1, "TN": 1, "FP": 1, "FN": 1})
        self.assertTrue(math.isclose(overall["accuracy"], 0.5))
        self.assertTrue(math.isclose(overall["precision_fail"], 0.5))
        self.assertTrue(math.isclose(overall["recall_fail"], 0.5))
        self.assertTrue(math.isclose(overall["f1_fail"], 0.5))
        self.assertTrue(math.isclose(overall["macro_f1"], 0.5))
        self.assertTrue(math.isclose(overall["balanced_accuracy"], 0.5))
        self.assertTrue(math.isclose(overall["brier_score"], 0.1925))
        self.assertIsNotNone(overall["ece"])
        self.assertGreaterEqual(overall["ece"], 0.0)
        self.assertLessEqual(overall["ece"], 1.0)

    def test_metrics_recompute_predictions_from_threshold(self) -> None:
        predictions = [
            {"gold": "pass", "split": "hidden", "p_fail": 0.2, "prediction": "fail"},
            {"gold": "fail", "split": "hidden", "p_fail": 0.7, "prediction": "pass"},
        ]

        metrics = eval_adapter.compute_metrics(predictions, threshold=0.5)

        self.assertEqual(metrics["overall"]["confusion_matrix"], {"TP": 1, "TN": 1, "FP": 0, "FN": 0})
        self.assertTrue(math.isclose(metrics["overall"]["accuracy"], 1.0))

    def test_threshold_sweep_records_metrics_and_best_entries(self) -> None:
        predictions = [
            {"gold": "pass", "split": "calibration", "p_fail": 0.2},
            {"gold": "pass", "split": "calibration", "p_fail": 0.45},
            {"gold": "fail", "split": "calibration", "p_fail": 0.55},
            {"gold": "fail", "split": "calibration", "p_fail": 0.8},
        ]

        sweep = eval_adapter.build_threshold_sweep_report(predictions, [0.3, 0.5, 0.7])

        self.assertTrue(sweep["enabled"])
        self.assertEqual(len(sweep["metrics_by_threshold"]), 3)
        self.assertEqual(sweep["best_accuracy"], {"threshold": 0.5, "value": 1.0})
        self.assertEqual(sweep["best_fail_f1"], {"threshold": 0.5, "value": 1.0})

    def test_threshold_sweep_adds_selective_risk_coverage_from_p_fail(self) -> None:
        # Changed: assert threshold sweep risk coverage is computed from p_fail scores.
        # Why: the report must reuse one inference pass without solver or model imports.
        predictions = [
            {"gold": "pass", "split": "hidden", "p_fail": 0.9, "prediction": "pass"},
            {"gold": "fail", "split": "hidden", "p_fail": 0.8, "prediction": "pass"},
            {"gold": "fail", "split": "hidden", "p_fail": 0.6, "prediction": "pass"},
            {"gold": "pass", "split": "hidden", "p_fail": 0.4, "prediction": "fail"},
        ]

        sweep = eval_adapter.build_threshold_sweep_report(predictions, [0.5])
        risk_coverage = sweep["metrics_by_threshold"][0]["risk_coverage"]
        summary = sweep["risk_coverage_summary"]

        self.assertEqual(risk_coverage["selected_n"], 3)
        self.assertTrue(math.isclose(risk_coverage["coverage"], 0.75))
        self.assertTrue(math.isclose(risk_coverage["risk_error_rate"], 1 / 3))
        self.assertTrue(math.isclose(risk_coverage["false_positive_rate"], 0.5))
        self.assertTrue(math.isclose(risk_coverage["false_positives_per_100"], 50.0))
        self.assertTrue(math.isclose(risk_coverage["fail_coverage"], 1.0))
        self.assertTrue(math.isclose(summary["aurc"], (1.0 + 0.5 + (1 / 3) + 0.5) / 4))
        self.assertTrue(math.isclose(summary["max_coverage_at_zero_error"], 0.0))

    def test_parse_threshold_sweep_deduplicates_and_validates(self) -> None:
        self.assertEqual(eval_adapter.parse_threshold_sweep("0.30, 0.35, 0.30"), [0.3, 0.35])

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                eval_adapter.parse_threshold_sweep("0.20,bad")


if __name__ == "__main__":
    unittest.main()
