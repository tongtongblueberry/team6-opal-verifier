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

    def test_bucket_metrics_group_by_source_and_length_bucket(self) -> None:
        # Changed: verify base-threshold bucket metrics for source and deterministic input length.
        # Why: coverage reports must expose weak source/length buckets without extending threshold sweep.
        short_bucket = eval_adapter.input_length_bucket("x" * 512)
        medium_bucket = eval_adapter.input_length_bucket("x" * 513)
        long_bucket = eval_adapter.input_length_bucket("x" * 1025)
        xlong_bucket = eval_adapter.input_length_bucket("x" * 2049)
        predictions = [
            {
                "gold": "pass",
                "split": "calibration",
                "source": "synthetic_a",
                "length_bucket": short_bucket,
                "p_fail": 0.1,
            },
            {
                "gold": "fail",
                "split": "calibration",
                "source": "synthetic_a",
                "length_bucket": medium_bucket,
                "p_fail": 0.8,
            },
            {
                "gold": "pass",
                "split": "hidden",
                "source": "synthetic_b",
                "length_bucket": long_bucket,
                "p_fail": 0.7,
            },
            {
                "gold": "fail",
                "split": "hidden",
                "source": "synthetic_b",
                "length_bucket": xlong_bucket,
                "p_fail": 0.4,
            },
        ]

        bucket_metrics = eval_adapter.compute_bucket_metrics(predictions, threshold=0.5)

        self.assertEqual(short_bucket, "chars_0000_0512")
        self.assertEqual(medium_bucket, "chars_0513_1024")
        self.assertEqual(long_bucket, "chars_1025_2048")
        self.assertEqual(xlong_bucket, "chars_2049_plus")
        self.assertEqual(
            bucket_metrics["by_source"]["synthetic_a"]["confusion_matrix"],
            {"TP": 1, "TN": 1, "FP": 0, "FN": 0},
        )
        self.assertEqual(
            bucket_metrics["by_source"]["synthetic_b"]["confusion_matrix"],
            {"TP": 0, "TN": 0, "FP": 1, "FN": 1},
        )
        self.assertEqual(bucket_metrics["by_length_bucket"][short_bucket]["n"], 1)
        self.assertEqual(bucket_metrics["by_length_bucket"][xlong_bucket]["confusion_matrix"]["FN"], 1)
        self.assertEqual(bucket_metrics["summary"]["source"]["worst_accuracy"]["bucket"], "synthetic_b")
        self.assertTrue(
            math.isclose(bucket_metrics["summary"]["source"]["worst_accuracy"]["accuracy"], 0.0)
        )
        markdown_lines = eval_adapter.bucket_metrics_markdown_lines(bucket_metrics)
        self.assertIn("## Bucket Metrics", markdown_lines)
        self.assertTrue(any("| source | 2 | 4 | synthetic_b | 2 | 0.00% |" in line for line in markdown_lines))

    def test_bucket_metrics_markdown_escapes_source_bucket_cells(self) -> None:
        # Changed: cover Markdown escaping for manifest-derived bucket labels.
        # Why: source names can contain Markdown table delimiters.
        bucket_metrics = {
            "threshold": 0.5,
            "summary": {
                "split": {"bucket_count": 0, "total_n": 0, "worst_accuracy": None},
                "source": {
                    "bucket_count": 1,
                    "total_n": 1,
                    "worst_accuracy": {
                        "bucket": "src|pipe\nline",
                        "n": 1,
                        "accuracy": 0.0,
                        "macro_f1": None,
                        "fail_f1": None,
                    },
                },
                "length_bucket": {"bucket_count": 0, "total_n": 0, "worst_accuracy": None},
            },
        }

        markdown_lines = eval_adapter.bucket_metrics_markdown_lines(bucket_metrics)

        self.assertTrue(any("src\\|pipe line" in line for line in markdown_lines))

    def test_evaluate_rows_preserves_source_and_length_bucket_metadata(self) -> None:
        # Changed: verify ManifestRow metadata survives the evaluate_rows cache path.
        # Why: bucket reports depend on prediction rows carrying source and length fields.
        row = eval_adapter.ManifestRow(
            line_number=7,
            sample_id="sample-7",
            input_text="x" * 513,
            label="fail",
            split="calibration",
            source="src|pipe",
        )
        original_score_next_token_batch = eval_adapter.score_next_token_batch

        def fake_score_next_token_batch(bundle, rows, label_token_report, max_seq_len):
            return [
                {
                    "pass": eval_adapter.CandidateScore(logit=0.0, token_id=1),
                    "fail": eval_adapter.CandidateScore(logit=2.0, token_id=2),
                }
                for _ in rows
            ]

        try:
            eval_adapter.score_next_token_batch = fake_score_next_token_batch
            predictions = eval_adapter.evaluate_rows(
                [row],
                bundle=object(),
                label_token_report={},
                threshold=0.5,
                max_seq_len=2048,
                batch_size=1,
            )
        finally:
            eval_adapter.score_next_token_batch = original_score_next_token_batch

        self.assertEqual(predictions[0]["source"], "src|pipe")
        self.assertEqual(predictions[0]["input_length_chars"], 513)
        self.assertEqual(predictions[0]["length_bucket"], "chars_0513_1024")
        self.assertEqual(predictions[0]["prediction"], "fail")


if __name__ == "__main__":
    unittest.main()
