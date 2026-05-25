# Changed: cover src.solver merged-model selection without loading real model weights.
# Why: Cycle 2 support must prove OPAL_MERGED_MODEL_DIR uses AutoModel/AutoTokenizer directly.

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src import solver


# Changed: provide tiny fake tokenizer/model classes for Solver() construction.
# Why: tests should verify loader control flow without importing real transformers weights.
class _FakeTokenizer:
    pad_token = None
    eos_token = "<eos>"

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        return [1 if text == "pass" else 2]


# Changed: record direct tokenizer/model loads from the merged artifact path.
# Why: assertions should confirm merged_model does not use the LoRA adapter path.
class _FakeAutoTokenizer:
    loaded: list[tuple[str, dict]] = []

    @classmethod
    def from_pretrained(cls, path: str, **kwargs):
        cls.loaded.append((path, kwargs))
        return _FakeTokenizer()


class _FakeModel:
    device = "cpu"

    def eval(self) -> None:
        self.eval_called = True


class _FakeAutoModelForCausalLM:
    loaded: list[tuple[str, dict]] = []

    @classmethod
    def from_pretrained(cls, path: str, **kwargs):
        cls.loaded.append((path, kwargs))
        return _FakeModel()


# Changed: validate merged artifact resolution and fail-closed env behavior.
# Why: solver.py should not silently fall back to LoRA when merged model is configured.
class SolverMergedModelPathTest(unittest.TestCase):
    def setUp(self) -> None:
        # Changed: clear fake loader records before each test.
        # Why: assertions should only reflect the current Solver() construction.
        _FakeAutoTokenizer.loaded.clear()
        _FakeAutoModelForCausalLM.loaded.clear()

    def test_solver_loads_env_merged_model_directly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            merged_dir = Path(temp_name)
            (merged_dir / "config.json").write_text("{}", encoding="utf-8")

            fake_torch = types.SimpleNamespace(float16="float16")
            fake_transformers = types.SimpleNamespace(
                AutoTokenizer=_FakeAutoTokenizer,
                AutoModelForCausalLM=_FakeAutoModelForCausalLM,
            )
            env = {
                "OPAL_MERGED_MODEL_DIR": str(merged_dir),
                "OPAL_LOCAL_FILES_ONLY": "1",
            }
            with patch.dict(os.environ, env, clear=False), patch.dict(
                sys.modules,
                {
                    "torch": fake_torch,
                    "transformers": fake_transformers,
                },
            ):
                instance = solver.Solver()

        self.assertEqual("merged_model", instance._artifact_mode)
        self.assertEqual(str(merged_dir), _FakeAutoTokenizer.loaded[0][0])
        self.assertEqual(str(merged_dir), _FakeAutoModelForCausalLM.loaded[0][0])
        self.assertTrue(_FakeAutoTokenizer.loaded[0][1]["local_files_only"])
        self.assertTrue(_FakeAutoModelForCausalLM.loaded[0][1]["local_files_only"])

    def test_invalid_env_merged_model_does_not_fall_back_to_lora(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            env = {"OPAL_MERGED_MODEL_DIR": str(Path(temp_name) / "missing_config")}
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(RuntimeError, "OPAL_MERGED_MODEL_DIR"):
                    solver.Solver()


if __name__ == "__main__":
    unittest.main()
