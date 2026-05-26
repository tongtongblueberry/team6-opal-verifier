# Changed: cover pass/fail generation metric logic without model inference.
# Why: heavy generation belongs to server execution, not local unit tests.

from __future__ import annotations

import math
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

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

    # Changed: cover direct adapter-dir and explicit --adapter-path loading flow without importing HF packages.
    # Why: the regression was caused by the adapter-path branch diverging from verified PEFT/Transformers semantics.
    def test_adapter_path_loads_base_model_and_adapter_tokenizer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter_dir = Path(temp_dir) / "adapter"
            adapter_dir.mkdir()
            (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
            (adapter_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")

            class FakeTokenizer:
                pad_token_id = None
                eos_token = "<eos>"
                pad_token = None

            class FakeAutoTokenizer:
                loaded: list[str] = []

                @classmethod
                def from_pretrained(cls, path: str) -> FakeTokenizer:
                    cls.loaded.append(path)
                    return FakeTokenizer()

            class FakeModel:
                def __init__(self) -> None:
                    self.adapter_calls: list[str] = []
                    self.active_adapter: str | None = None
                    self.eval_called = False

                def load_adapter(self, path: str) -> None:
                    self.adapter_calls.append(path)

                def set_adapter(self, name: str) -> None:
                    self.active_adapter = name

                def eval(self) -> None:
                    self.eval_called = True

            class FakeAutoModel:
                loaded: list[str] = []
                model = FakeModel()

                @classmethod
                def from_pretrained(cls, path: str) -> FakeModel:
                    cls.loaded.append(path)
                    return cls.model

            tokenizer, model = generation_eval.load_model_and_tokenizer(
                FakeAutoTokenizer,
                FakeAutoModel,
                "base-model",
                str(adapter_dir),
            )

            self.assertEqual([str(adapter_dir)], FakeAutoTokenizer.loaded)
            self.assertEqual("<eos>", tokenizer.pad_token)
            self.assertEqual(["base-model"], FakeAutoModel.loaded)
            self.assertEqual([str(adapter_dir)], model.adapter_calls)
            self.assertEqual("default", model.active_adapter)
            self.assertTrue(model.eval_called)

    def test_direct_adapter_dir_omits_adapter_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter_dir = Path(temp_dir) / "adapter"
            adapter_dir.mkdir()
            (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")

            class FakeTokenizer:
                pad_token_id = 0
                eos_token = "<eos>"

            class FakeAutoTokenizer:
                loaded: list[str] = []

                @classmethod
                def from_pretrained(cls, path: str) -> FakeTokenizer:
                    cls.loaded.append(path)
                    return FakeTokenizer()

            class FakeModel:
                def __init__(self) -> None:
                    self.adapter_calls: list[str] = []
                    self.eval_called = False

                def load_adapter(self, path: str) -> None:
                    self.adapter_calls.append(path)

                def eval(self) -> None:
                    self.eval_called = True

            class FakeAutoModel:
                loaded: list[str] = []
                model = FakeModel()

                @classmethod
                def from_pretrained(cls, path: str) -> FakeModel:
                    cls.loaded.append(path)
                    return cls.model

            _, model = generation_eval.load_model_and_tokenizer(
                FakeAutoTokenizer,
                FakeAutoModel,
                str(adapter_dir),
                None,
            )

            self.assertEqual([str(adapter_dir)], FakeAutoTokenizer.loaded)
            self.assertEqual([str(adapter_dir)], FakeAutoModel.loaded)
            self.assertEqual([], model.adapter_calls)
            self.assertTrue(model.eval_called)

    def test_adapter_path_rejects_local_adapter_as_base_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_adapter_dir = Path(temp_dir) / "base-adapter"
            adapter_dir = Path(temp_dir) / "adapter"
            base_adapter_dir.mkdir()
            adapter_dir.mkdir()
            (base_adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
            (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")

            stderr = StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                generation_eval.validate_model_adapter_args(str(base_adapter_dir), str(adapter_dir))

            self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
