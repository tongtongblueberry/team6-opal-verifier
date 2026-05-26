# Changed: cover pass/fail generation metric logic without model inference.
# Why: heavy generation belongs to server execution, not local unit tests.

from __future__ import annotations

import math
import unittest

from tools.eval import eval_trl_sft_public20_generation as generation_eval


class EvalTrlSftPublic20GenerationTests(unittest.TestCase):
    def test_normalizes_first_generated_pass_fail_token(self) -> None:
        self.assertEqual("pass", generation_eval.normalize_generated_label(" pass\n"))
        self.assertEqual("fail", generation_eval.normalize_generated_label("FAIL."))
        self.assertIsNone(generation_eval.normalize_generated_label("unknown"))

    def test_compute_generation_metrics_tracks_invalid_outputs(self) -> None:
        predictions = [
            {"gold": "fail", "prediction": "fail"},
            {"gold": "pass", "prediction": "pass"},
            {"gold": "pass", "prediction": "fail"},
            {"gold": "fail", "prediction": None},
        ]

        metrics = generation_eval.compute_generation_metrics(predictions)

        self.assertEqual(metrics["confusion_matrix"], {"TP": 1, "TN": 1, "FP": 1, "FN": 0, "INVALID": 1})
        self.assertTrue(math.isclose(metrics["accuracy"], 0.5))
        self.assertTrue(math.isclose(metrics["precision_fail"], 0.5))
        self.assertTrue(math.isclose(metrics["recall_fail"], 0.5))


if __name__ == "__main__":
    unittest.main()
