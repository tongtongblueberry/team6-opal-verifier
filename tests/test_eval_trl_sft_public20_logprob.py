# Changed: cover TRL public20 conditional logprob evaluator without loading a real model.
# Why: this lane must diagnose label likelihoods locally while server workers handle heavy inference.

from __future__ import annotations

import json
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from tools.eval import eval_trl_sft_public20_generation as generation_eval
from tools.eval import eval_trl_sft_public20_logprob as logprob_eval


class FakeTokenizer:
    pad_token_id = 0
    padding_side = "right"

    def __call__(
        self,
        text: str,
        add_special_tokens: bool = False,
        return_offsets_mapping: bool = False,
    ) -> dict[str, object]:
        del add_special_tokens
        input_ids = [ord(character) for character in text]
        result: dict[str, object] = {"input_ids": input_ids}
        if return_offsets_mapping:
            result["offset_mapping"] = [(index, index + 1) for index in range(len(text))]
        return result


class EvalTrlSftPublic20LogprobTests(unittest.TestCase):
    def test_candidate_features_mask_prompt_with_ignore_index(self) -> None:
        row = generation_eval.EvalRow(sample_id="tc1", prompt="abc\n", gold="pass", line_number=1)

        features = logprob_eval.build_candidate_features(FakeTokenizer(), row, "fail", max_length=128)

        self.assertEqual([ord(character) for character in "abc\nfail"], features.input_ids)
        self.assertEqual(
            [logprob_eval.IGNORE_INDEX] * len("abc\n") + [ord(character) for character in "fail"],
            features.labels,
        )
        self.assertEqual(len("abc\n"), features.prompt_token_count)
        self.assertEqual(len("fail"), features.candidate_token_count)

    def test_padding_sets_pad_labels_to_ignore_index(self) -> None:
        first = logprob_eval.CandidateFeatures(
            sample_id="tc1",
            gold="pass",
            candidate_label="pass",
            input_ids=[10, 20],
            labels=[logprob_eval.IGNORE_INDEX, 20],
            prompt_token_count=1,
            candidate_token_count=1,
            total_token_count=2,
        )
        second = logprob_eval.CandidateFeatures(
            sample_id="tc1",
            gold="pass",
            candidate_label="fail",
            input_ids=[10, 30, 40],
            labels=[logprob_eval.IGNORE_INDEX, 30, 40],
            prompt_token_count=1,
            candidate_token_count=2,
            total_token_count=3,
        )

        padded = logprob_eval.pad_candidate_features([first, second], pad_token_id=0, padding_side="right")

        self.assertEqual(len(padded["input_ids"][0]), len(padded["input_ids"][1]))
        self.assertEqual(logprob_eval.IGNORE_INDEX, padded["labels"][0][-1])
        self.assertEqual(0, padded["attention_mask"][0][-1])

    def test_candidate_score_reports_nll_and_mean_logprob(self) -> None:
        score = logprob_eval.candidate_score_from_sum(sum_logprob=-2.5, token_count=5)

        self.assertTrue(math.isclose(score.nll, 2.5))
        self.assertTrue(math.isclose(score.mean_logprob, -0.5))

    def test_evaluate_rows_predicts_higher_mean_logprob_label(self) -> None:
        rows = [generation_eval.EvalRow(sample_id="tc1", prompt="input\n", gold="fail", line_number=3)]

        def fake_score_candidate_batch(torch, model, tokenizer, features):
            del torch, model, tokenizer
            self.assertEqual(["pass", "fail"], [feature.candidate_label for feature in features])
            return [
                logprob_eval.CandidateScore(nll=4.0, sum_logprob=-4.0, mean_logprob=-1.0, token_count=4),
                logprob_eval.CandidateScore(nll=2.0, sum_logprob=-2.0, mean_logprob=-0.5, token_count=4),
            ]

        with mock.patch.object(logprob_eval, "score_candidate_batch", fake_score_candidate_batch):
            predictions = logprob_eval.evaluate_rows(
                rows,
                tokenizer=FakeTokenizer(),
                model=object(),
                torch=object(),
                batch_size=1,
                max_length=128,
            )

        self.assertEqual("fail", predictions[0]["prediction"])
        self.assertTrue(predictions[0]["correct"])
        self.assertGreater(predictions[0]["mean_logprob_margin_fail_minus_pass"], 0)

    def test_load_logprob_model_reuses_generation_helper(self) -> None:
        with mock.patch.object(
            generation_eval,
            "load_model_and_tokenizer",
            return_value=("tokenizer", "model"),
        ) as load_helper:
            tokenizer, model = logprob_eval.load_logprob_model_and_tokenizer(
                auto_tokenizer=object(),
                auto_model=object(),
                model_name_or_path="adapter-or-full-model",
                adapter_path=None,
            )

        self.assertEqual("tokenizer", tokenizer)
        self.assertEqual("model", model)
        load_helper.assert_called_once()

    def test_direct_adapter_without_tokenizer_uses_base_tokenizer_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            adapter_dir = Path(temp_name) / "adapter"
            adapter_dir.mkdir()
            (adapter_dir / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": "base-model"}),
                encoding="utf-8",
            )

            source = generation_eval.tokenizer_source_for(str(adapter_dir), adapter_path=None)

        self.assertEqual("base-model", source)

    def test_dry_run_writes_report_without_model_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            dataset = temp_dir / "validation.jsonl"
            output_json = temp_dir / "logprob.json"
            output_md = temp_dir / "logprob.md"
            dataset.write_text(
                json.dumps({"prompt": "input\n", "completion": "pass", "sample_id": "tc1"}) + "\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                exit_code = logprob_eval.main(
                    [
                        "--dataset-jsonl",
                        str(dataset),
                        "--model-name-or-path",
                        "dummy-model",
                        "--output-json",
                        str(output_json),
                        "--output-md",
                        str(output_md),
                        "--dry-run",
                    ]
                )

            report = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        self.assertTrue(report["dry_run"])
        self.assertEqual("public20_trl_sft_logprob", report["metric_adapter"])
        self.assertEqual(1, report["dataset"]["selected_rows"])
        self.assertIn("labels=-100", markdown)


if __name__ == "__main__":
    unittest.main()
