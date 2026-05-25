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

    def test_resolve_repo_local_merged_model_path(self) -> None:
        # Changed: cover repo-local artifacts/merged_model detection independent of env overrides.
        # Why: packaged merged artifacts should be selected before any LoRA adapter scanning.
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            merged_dir = root / "artifacts" / "merged_model"
            merged_dir.mkdir(parents=True)
            (merged_dir / "config.json").write_text("{}", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                resolved, source = solver._resolve_merged_model_path(root)

        self.assertEqual(merged_dir, resolved)
        self.assertEqual("repo-local artifacts/merged_model", source)

    def test_solver_repo_local_merged_model_skips_lora_loader(self) -> None:
        # Changed: assert Solver stops after a repo-local merged artifact is selected.
        # Why: merged packages must not silently compose or prefer a LoRA adapter at runtime.
        with tempfile.TemporaryDirectory() as temp_name:
            merged_dir = Path(temp_name)
            (merged_dir / "config.json").write_text("{}", encoding="utf-8")
            loads: list[str] = []

            def fake_load_merged(instance, path: str) -> None:
                loads.append(path)
                instance.model = object()
                instance.tokenizer = object()
                instance._pass_id = 1
                instance._fail_id = 2
                instance._available = True

            with patch.object(
                solver,
                "_resolve_merged_model_path",
                return_value=(merged_dir, "repo-local artifacts/merged_model"),
            ), patch.object(
                solver.Solver,
                "_load_merged_model",
                fake_load_merged,
            ), patch.object(
                solver.Solver,
                "_load_model",
            ) as load_lora:
                instance = solver.Solver()

        self.assertEqual("merged_model", instance._artifact_mode)
        self.assertEqual([str(merged_dir)], loads)
        load_lora.assert_not_called()

    def test_solver_falls_back_to_env_lora_when_no_merged_model(self) -> None:
        # Changed: cover LoRA fallback after merged model resolution returns no artifact.
        # Why: legacy adapter packages remain valid while Cycle 2 merged packages are prepared.
        with tempfile.TemporaryDirectory() as temp_name:
            adapter_dir = Path(temp_name) / "adapter"
            adapter_dir.mkdir()
            (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
            loads: list[tuple[str, str]] = []

            def fake_load_lora(instance, adapter_path: str, base_model: str) -> None:
                loads.append((adapter_path, base_model))
                instance.model = object()
                instance.tokenizer = object()
                instance._pass_id = 1
                instance._fail_id = 2
                instance._available = True

            env = {"OPAL_LORA_ADAPTER": str(adapter_dir), "RAG_MODEL": "Qwen/Qwen3.5-4B"}
            with patch.dict(os.environ, env, clear=False), patch.object(
                solver,
                "_resolve_merged_model_path",
                return_value=(None, ""),
            ), patch.object(
                solver.Solver,
                "_load_model",
                fake_load_lora,
            ):
                instance = solver.Solver()

        self.assertEqual("lora_adapter", instance._artifact_mode)
        self.assertEqual([(str(adapter_dir), "Qwen/Qwen3.5-4B")], loads)


if __name__ == "__main__":
    unittest.main()
