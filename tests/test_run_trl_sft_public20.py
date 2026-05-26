# Changed: test the TRL SFT launcher without importing TRL or loading models.
# Why: local verification must cover completion-only intent while server agents handle dependencies.

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
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
        "max_length": 4096,
        "bf16": False,
        "fp16": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class RunTrlSftPublic20Tests(unittest.TestCase):
    def test_sft_config_kwargs_force_completion_only_loss(self) -> None:
        kwargs = runner.build_sft_config_kwargs(_args(), runner.dry_run_supported_fields())

        self.assertTrue(kwargs["completion_only_loss"])
        self.assertFalse(kwargs["packing"])
        self.assertEqual("epoch", kwargs["eval_strategy"])
        self.assertEqual(4096, kwargs["max_length"])
        self.assertNotIn("data_collator", kwargs)
        self.assertNotIn("formatting_func", kwargs)

    def test_missing_completion_only_support_fails_fast(self) -> None:
        supported = runner.dry_run_supported_fields() - {"completion_only_loss"}

        with self.assertRaises(SystemExit):
            runner.build_sft_config_kwargs(_args(), supported)

    def test_validates_converted_dataset_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            dataset_dir = Path(temp_name)
            (dataset_dir / "train.jsonl").write_text(
                json.dumps({"prompt": '{"records":[]}\n', "completion": "pass", "sample_id": "tc1"})
                + "\n",
                encoding="utf-8",
            )
            (dataset_dir / "validation.jsonl").write_text(
                json.dumps({"prompt": '{"records":[]}\n', "completion": "fail", "sample_id": "tc2"})
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
