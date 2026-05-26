# Added: cover full-model validation logic without loading a real model.
# Why: public20 full FT validation needs reliable manifest, metric, and prompt
# gates before any GPU inference run.

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.eval import eval_manifest_full_model as full_eval
from tools.training import train_manifest_full


def _write_manifest(path: Path) -> None:
    rows = [
        {"sample_id": "train-pass", "input": '{"records":[{"output":{"status_codes":["SUCCESS"]}}]}', "label": "pass", "split": "train"},
        {"sample_id": "val-pass", "input": '{"records":[{"output":{"status_codes":["SUCCESS"]}}]}', "label": "pass", "split": "val"},
        {"sample_id": "val-fail", "input": '{"records":[{"output":{"status_codes":["FAIL"]}}]}', "label": "fail", "split": "val"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class EvalManifestFullModelTests(unittest.TestCase):
    def test_load_manifest_selects_val_without_using_train_loader_drop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            manifest = Path(temp_name) / "manifest.jsonl"
            _write_manifest(manifest)

            rows, summary = full_eval.load_manifest(manifest)
            selected, selected_before_limit = full_eval.select_rows(rows, ["val"], limit=None)

        self.assertEqual(3, summary["total_rows"])
        self.assertEqual({"train": 1, "val": 2}, summary["split_counts"])
        self.assertEqual(2, selected_before_limit)
        self.assertEqual(["val-pass", "val-fail"], [row.sample_id for row in selected])

    def test_prompt_contract_matches_train_manifest_full(self) -> None:
        row = train_manifest_full.ManifestRow(
            sample_id="val-pass",
            input_text='{"records":[]}',
            label="pass",
            split="val",
            source="unknown",
            row_index=2,
        )

        prompt_messages = full_eval.build_prompt_messages(row)
        train_messages = train_manifest_full.build_messages(row)

        self.assertEqual(prompt_messages, train_messages[:-1])
        self.assertEqual(train_messages[-1], {"role": "assistant", "content": "pass"})

    def test_compute_metrics_reports_requested_core_values(self) -> None:
        predictions = [
            {"gold": "pass", "split": "val", "p_fail": 0.1},
            {"gold": "pass", "split": "val", "p_fail": 0.8},
            {"gold": "fail", "split": "val", "p_fail": 0.9},
            {"gold": "fail", "split": "val", "p_fail": 0.2},
        ]

        metrics = full_eval.compute_metrics(predictions, threshold=0.5)
        overall = metrics["overall"]

        self.assertEqual(overall["confusion_matrix"], {"TP": 1, "TN": 1, "FP": 1, "FN": 1})
        self.assertTrue(math.isclose(overall["accuracy"], 0.5))
        self.assertTrue(math.isclose(overall["recall_fail"], 0.5))
        self.assertTrue(math.isclose(overall["recall_pass"], 0.5))
        self.assertTrue(math.isclose(overall["macro_f1"], 0.5))

    def test_evaluate_rows_aggregates_fake_logits_without_model_load(self) -> None:
        rows = [
            train_manifest_full.ManifestRow("pass-id", "input", "pass", "val", "unknown", 1),
            train_manifest_full.ManifestRow("fail-id", "input", "fail", "val", "unknown", 2),
        ]
        original = full_eval.score_next_token_batch

        def fake_score_next_token_batch(bundle, batch_rows, label_token_report, max_seq_len):
            return [
                {
                    "pass": full_eval.CandidateScore(logit=2.0, token_id=10),
                    "fail": full_eval.CandidateScore(logit=0.0, token_id=11),
                },
                {
                    "pass": full_eval.CandidateScore(logit=0.0, token_id=10),
                    "fail": full_eval.CandidateScore(logit=2.0, token_id=11),
                },
            ][: len(batch_rows)]

        try:
            full_eval.score_next_token_batch = fake_score_next_token_batch
            predictions = full_eval.evaluate_rows(
                rows,
                bundle=object(),
                label_token_report={},
                threshold=0.5,
                max_seq_len=128,
                batch_size=2,
            )
        finally:
            full_eval.score_next_token_batch = original

        self.assertEqual(["pass", "fail"], [row["prediction"] for row in predictions])
        self.assertTrue(predictions[0]["correct"])
        self.assertTrue(predictions[1]["correct"])
        self.assertLess(predictions[0]["binary_logprob_pass"], 0)
        self.assertLess(predictions[1]["binary_logprob_fail"], 0)

    def test_dry_run_writes_reports_without_model_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            manifest = temp_dir / "manifest.jsonl"
            output_json = temp_dir / "eval.json"
            output_md = temp_dir / "eval.md"
            _write_manifest(manifest)

            with mock.patch.object(
                sys,
                "argv",
                [
                    "eval_manifest_full_model.py",
                    "--manifest",
                    str(manifest),
                    "--model-path",
                    "dummy-full-model",
                    "--split",
                    "val",
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                    "--dry-run",
                ],
            ):
                exit_code = full_eval.main()

            report = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        self.assertEqual("dry_run", report["mode"])
        self.assertEqual({"val": 2}, report["selection"]["split_counts"])
        self.assertEqual([], report["predictions"])
        self.assertIn("Full FT 모델 Validation 리포트", markdown)


if __name__ == "__main__":
    unittest.main()
