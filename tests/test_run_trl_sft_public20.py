# Changed: test the TRL SFT launcher without importing TRL or loading models.
# Why: local verification must cover completion-only intent while server agents handle dependencies.

from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from collections import UserDict
from contextlib import redirect_stderr
from pathlib import Path

from tools.training import run_trl_sft_public20 as runner


# Changed: add tiny parameter/model fakes for full-FT verification tests.
# Why: local tests must verify trainable-count logic without importing torch or TRL.
class _FakeParameter:
    def __init__(self, count: int, requires_grad: bool) -> None:
        self._count = count
        self.requires_grad = requires_grad

    def numel(self) -> int:
        return self._count


class _FakeModel:
    def __init__(self, parameters: list[_FakeParameter]) -> None:
        self._parameters = parameters

    def parameters(self) -> list[_FakeParameter]:
        return self._parameters


# Changed: add a tiny tokenizer fake for max_length truncation preflight tests.
# Why: local tests must cover tokenizer-driven completion-label survival without importing transformers.
class _WhitespaceTokenizer:
    def __call__(self, text: str, *, add_special_tokens: bool = False) -> dict[str, list[int]]:
        del add_special_tokens
        return {"input_ids": list(range(len(text.split())))}


# Changed: add a Mapping-but-not-dict tokenizer fake for real AutoTokenizer outputs.
# Why: transformers BatchEncoding should pass preflight instead of failing the input_ids check.
class _MappingTokenizer:
    def __call__(self, text: str, *, add_special_tokens: bool = False) -> UserDict[str, list[int]]:
        del add_special_tokens
        return UserDict({"input_ids": list(range(len(text.split())))})


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "output_dir": "runs/model_validation/public20_trl_sft/adapters/seed11",
        "packing": False,
        "learning_rate": 1e-4,
        "num_train_epochs": 5.0,
        "per_device_train_batch_size": 1,
        "per_device_eval_batch_size": 1,
        "gradient_accumulation_steps": 8,
        "logging_steps": 1,
        "save_strategy": "epoch",
        "save_steps": 10,
        "eval_steps": 10,
        "seed": 42,
        "report_to": "none",
        "gradient_checkpointing": True,
        "eval_strategy": "epoch",
        # Changed: mirror the runner's audited public20 max-length default.
        # Why: CLI/default metadata tests must fail if the default drifts back to 4096.
        "max_length": runner.DEFAULT_MAX_LENGTH,
        "bf16": False,
        "fp16": False,
        # Changed: mirror the runner's QLoRA CLI defaults in the test namespace.
        # Why: config-builder unit tests should exercise the same default argument shape as parse_args().
        "use_peft": False,
        "use_4bit_quantization": False,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_compute_dtype": "bfloat16",
        "bnb_4bit_quant_storage_dtype": "uint8",
        "bnb_4bit_use_double_quant": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class RunTrlSftPublic20Tests(unittest.TestCase):
    def test_sft_config_kwargs_force_completion_only_loss(self) -> None:
        kwargs = runner.build_sft_config_kwargs(_args(), runner.dry_run_supported_fields())

        self.assertTrue(kwargs["completion_only_loss"])
        self.assertFalse(kwargs["packing"])
        self.assertEqual("epoch", kwargs["eval_strategy"])
        self.assertEqual(8192, kwargs["max_length"])
        self.assertNotIn("data_collator", kwargs)
        self.assertNotIn("formatting_func", kwargs)

    def test_cli_default_and_plan_metadata_use_8192_preflight_policy(self) -> None:
        # Changed: lock CLI default and plan metadata to the corrected public20 max-length policy.
        # Why: queue launchers that omit --max-length must inherit the safe 8192 budget.
        args = runner.parse_args(
            [
                "--dataset-dir",
                "dataset",
                "--model-name-or-path",
                "model",
                "--output-dir",
                "output",
            ]
        )
        summary = runner.DatasetSummary(
            dataset_dir="dataset",
            train_path="dataset/train.jsonl",
            validation_path="dataset/validation.jsonl",
            train_rows=10,
            validation_rows=10,
            train_label_counts={"fail": 5, "pass": 5},
            validation_label_counts={"fail": 5, "pass": 5},
        )
        config_kwargs = runner.build_sft_config_kwargs(args, runner.dry_run_supported_fields())
        report = runner.build_plan_report(args, summary, config_kwargs, dependency_report=None)

        self.assertEqual(8192, args.max_length)
        self.assertEqual(8192, report["sft_config_kwargs"]["max_length"])
        self.assertEqual(8192, report["max_length_policy"]["default_max_length"])
        self.assertEqual(8192, report["max_length_policy"]["configured_max_length"])
        self.assertTrue(report["max_length_policy"]["completion_label_preflight_required"])

    def test_qlora_requires_peft(self) -> None:
        # Changed: lock QLoRA to the PEFT adapter path.
        # Why: verified QLoRA evidence is quantized-base LoRA, not quantized full fine-tuning.
        with self.assertRaises(SystemExit) as raised:
            runner._validate_quantization_args(_args(use_4bit_quantization=True, use_peft=False))
        self.assertEqual(2, raised.exception.code)

    def test_qlora_dry_run_uses_model_init_kwargs(self) -> None:
        # Changed: verify QLoRA dry-run config shape without importing torch/transformers.
        # Why: TRL SFTConfig.model_init_kwargs is the reviewed path for model loading kwargs.
        kwargs = runner.build_sft_config_kwargs(
            _args(use_4bit_quantization=True, use_peft=True),
            runner.dry_run_supported_fields(),
        )
        model_init_kwargs = kwargs["model_init_kwargs"]
        quantization_config = model_init_kwargs["quantization_config"]
        self.assertEqual("trl.get_kbit_device_map()", model_init_kwargs["device_map"])
        self.assertEqual("transformers.BitsAndBytesConfig", quantization_config["class"])
        self.assertTrue(quantization_config["load_in_4bit"])
        self.assertEqual("nf4", quantization_config["bnb_4bit_quant_type"])

    def test_missing_completion_only_support_fails_fast(self) -> None:
        supported = runner.dry_run_supported_fields() - {"completion_only_loss"}

        with self.assertRaises(SystemExit):
            runner.build_sft_config_kwargs(_args(), supported)

    def test_validates_converted_dataset_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            dataset_dir = Path(temp_name)
            (dataset_dir / "train.jsonl").write_text(
                json.dumps({"input": '{"records":[]}\n', "labels": "pass"})
                + "\n",
                encoding="utf-8",
            )
            (dataset_dir / "validation.jsonl").write_text(
                json.dumps({"input": '{"records":[]}\n', "labels": "fail"})
                + "\n",
                encoding="utf-8",
            )

            summary = runner.validate_converted_dataset(
                dataset_dir,
                "train.jsonl",
                "validation.jsonl",
            )

        self.assertEqual(1, summary.train_rows)
        self.assertEqual(1, summary.validation_rows)
        self.assertEqual({"pass": 1}, summary.train_label_counts)
        self.assertEqual({"fail": 1}, summary.validation_label_counts)

    def test_preflight_fails_when_validation_completion_label_is_truncated(self) -> None:
        # Changed: fail fast when max_length leaves zero shifted valid completion labels.
        # Why: this is the eval_loss NaN failure mode observed on long public20 validation rows.
        with tempfile.TemporaryDirectory() as temp_name:
            dataset_dir = Path(temp_name)
            (dataset_dir / "train.jsonl").write_text(
                json.dumps({"input": "short prompt ", "labels": "pass"})
                + "\n",
                encoding="utf-8",
            )
            (dataset_dir / "validation.jsonl").write_text(
                json.dumps({"input": "tok " * 4096, "labels": "fail"})
                + "\n",
                encoding="utf-8",
            )
            summary = runner.validate_converted_dataset(dataset_dir, "train.jsonl", "validation.jsonl")
            stderr = io.StringIO()

            with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                runner.preflight_completion_label_truncation(_WhitespaceTokenizer(), summary, max_length=4096)

        message = stderr.getvalue()
        self.assertEqual(2, raised.exception.code)
        self.assertIn("split=validation", message)
        self.assertIn("row_index=0", message)
        self.assertIn("max_length=4096", message)
        self.assertIn("prompt_token_length=4096", message)
        self.assertIn("completion_token_length=1", message)
        self.assertIn("shifted_valid_completion_label_count=0", message)
        self.assertIn("truncation check", message)

    def test_preflight_passes_public20_like_row_at_8192(self) -> None:
        # Changed: verify the audited 8192 budget preserves at least one completion label.
        # Why: public20-like long prompt rows should pass only when completion tokens survive truncation.
        with tempfile.TemporaryDirectory() as temp_name:
            dataset_dir = Path(temp_name)
            long_prompt = "tok " * 4096
            (dataset_dir / "train.jsonl").write_text(
                json.dumps({"input": long_prompt, "labels": "pass"})
                + "\n",
                encoding="utf-8",
            )
            (dataset_dir / "validation.jsonl").write_text(
                json.dumps({"input": long_prompt, "labels": "fail"})
                + "\n",
                encoding="utf-8",
            )
            summary = runner.validate_converted_dataset(dataset_dir, "train.jsonl", "validation.jsonl")

            report = runner.preflight_completion_label_truncation(
                _WhitespaceTokenizer(),
                summary,
                max_length=8192,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(2, report["checked_rows"])
        self.assertEqual(1, report["min_shifted_valid_completion_label_count"])
        self.assertEqual(4096, report["splits"]["train"]["max_prompt_token_length"])
        self.assertFalse(report["chat_template_used"])
        self.assertFalse(report["completion_prefix_matching_used"])

    def test_preflight_accepts_mapping_tokenizer_output(self) -> None:
        # Changed: cover BatchEncoding-like Mapping outputs from real HF tokenizers.
        # Why: corrected queue preflight runs against AutoTokenizer, not only dict-returning fakes.
        stats = runner.completion_label_preflight_stats(
            _MappingTokenizer(),
            {"input": "one two", "labels": "pass"},
            max_length=8192,
        )

        self.assertEqual(2, stats["prompt_token_length"])
        self.assertEqual(1, stats["completion_token_length"])
        self.assertEqual(1, stats["shifted_valid_completion_label_count"])

    def test_full_ft_requires_all_parameters_trainable(self) -> None:
        model = _FakeModel([
            _FakeParameter(7, True),
            _FakeParameter(3, False),
        ])

        with self.assertRaises(SystemExit):
            runner.verify_training_mode(model, use_peft=False)

    def test_full_ft_records_trainable_parameter_count(self) -> None:
        model = _FakeModel([
            _FakeParameter(7, True),
            _FakeParameter(3, True),
        ])

        summary = runner.verify_training_mode(model, use_peft=False)

        self.assertEqual(10, summary["total_parameters"])
        self.assertEqual(10, summary["trainable_parameters"])
        self.assertEqual(0, summary["frozen_parameters"])
        self.assertTrue(summary["fully_trainable"])


if __name__ == "__main__":
    unittest.main()
