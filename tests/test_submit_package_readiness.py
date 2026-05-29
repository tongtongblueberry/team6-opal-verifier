# Changed: cover submit-package readiness checks for HF offline/cache parity.
# Why: setup.sh and solver.py regressions should fail before evaluator submission.

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.eval.check_submit_package import check_submit_package


# Changed: create a tiny fake LoRA artifact marker set for package checks.
# Why: readiness unit tests must validate packaging rules without real model weights.
def _write_fake_lora_artifact(package_dir: Path, name: str = "lora_adapter_dcv2_final") -> None:
    adapter_dir = package_dir / "artifacts" / name
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"fake")


# Changed: create a tiny fake merged-model artifact marker set for package checks.
# Why: checker support for standalone artifacts should be testable without loading a model.
def _write_fake_merged_model_artifact(package_dir: Path) -> None:
    model_dir = package_dir / "artifacts" / "merged_model"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"fake")
    (model_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")


# Changed: build a minimal package fixture from the current worktree files.
# Why: readiness checks should run without model artifacts, datasets, or submit commands.
def _make_package(root: Path, artifact: str | None = "lora") -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory()
    package_dir = Path(temp_dir.name)
    (package_dir / "src").mkdir()
    shutil.copy2(root / "setup.sh", package_dir / "setup.sh")
    # Changed: copy official dependency metadata into package fixtures.
    # Why: project.pdf requires pyproject.toml and uv.lock in submitted directories.
    shutil.copy2(root / "pyproject.toml", package_dir / "pyproject.toml")
    shutil.copy2(root / "uv.lock", package_dir / "uv.lock")
    shutil.copy2(root / "src" / "solver.py", package_dir / "src" / "solver.py")
    shutil.copy2(root / "src" / "__init__.py", package_dir / "src" / "__init__.py")
    # Changed: optionally add fake artifact markers after copying source files.
    # Why: tests need to cover both accepted package families and the missing-artifact failure.
    if artifact == "lora":
        _write_fake_lora_artifact(package_dir)
    elif artifact == "merged":
        _write_fake_merged_model_artifact(package_dir)
    return temp_dir


# Changed: test the checker as a package-level gate.
# Why: missing HF env defaults or local_files_only propagation must block readiness.
class SubmitPackageReadinessTest(unittest.TestCase):
    def test_current_package_files_pass_hf_offline_readiness(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            errors = check_submit_package(Path(temp_name))
        self.assertEqual([], errors)

    def test_merged_model_artifact_passes_readiness(self) -> None:
        # Changed: cover standalone merged artifact readiness.
        # Why: Cycle 2 packages may omit LoRA adapters when artifacts/merged_model is complete.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root, artifact="merged") as temp_name:
            errors = check_submit_package(Path(temp_name))
        self.assertEqual([], errors)

    def test_alternate_final_lora_artifact_passes_readiness(self) -> None:
        # Changed: cover artifacts/lora_adapter_final as a valid LoRA package layout.
        # Why: server-side packages may use the alternate final adapter directory name.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root, artifact=None) as temp_name:
            _write_fake_lora_artifact(Path(temp_name), name="lora_adapter_final")
            errors = check_submit_package(Path(temp_name))
        self.assertEqual([], errors)

    def test_missing_model_artifact_fails_readiness(self) -> None:
        # Changed: require either merged model or LoRA adapter artifact.
        # Why: static readiness should not pass a package that cannot load an LLM.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root, artifact=None) as temp_name:
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("missing model artifact" in error for error in errors), errors)

    def test_missing_dependency_metadata_fails_readiness(self) -> None:
        # Changed: cover pyproject.toml/uv.lock as hard submit requirements.
        # Why: server submission uses those files before model inference starts.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            package_dir = Path(temp_name)
            (package_dir / "pyproject.toml").unlink()
            (package_dir / "uv.lock").unlink()
            errors = check_submit_package(package_dir)
        self.assertTrue(any("missing pyproject.toml" in error for error in errors), errors)
        self.assertTrue(any("missing uv.lock" in error for error in errors), errors)

    def test_incomplete_merged_model_takes_precedence_and_fails(self) -> None:
        # Changed: incomplete merged_model blocks readiness even when LoRA exists.
        # Why: solver.py will prefer artifacts/merged_model/config.json over the adapter path.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root, artifact="lora") as temp_name:
            merged_dir = Path(temp_name) / "artifacts" / "merged_model"
            merged_dir.mkdir(parents=True)
            (merged_dir / "config.json").write_text("{}", encoding="utf-8")
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("merged model weight" in error for error in errors), errors)

    def test_index_only_merged_model_fails_readiness(self) -> None:
        # Changed: reject shard-index metadata without the referenced weight shards.
        # Why: static readiness must catch packages that would fail AutoModel loading at runtime.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root, artifact=None) as temp_name:
            merged_dir = Path(temp_name) / "artifacts" / "merged_model"
            merged_dir.mkdir(parents=True)
            (merged_dir / "config.json").write_text("{}", encoding="utf-8")
            (merged_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")
            (merged_dir / "model.safetensors.index.json").write_text(
                '{"weight_map": {"model.layers.0.weight": "model-00001-of-00002.safetensors"}}',
                encoding="utf-8",
            )
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("missing merged model weight shard" in error for error in errors), errors)
        self.assertTrue(any("references missing shards" in error for error in errors), errors)

    def test_missing_offline_setup_env_fails_readiness(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            setup_path = Path(temp_name) / "setup.sh"
            setup_path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("HF_HOME" in error for error in errors), errors)

    def test_rule_engine_marker_fails_readiness(self) -> None:
        # Changed: cover the no-rule scan on executable Python tokens.
        # Why: deterministic rule-engine architecture must fail before packaging.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            solver_path = Path(temp_name) / "src" / "solver.py"
            solver_path.write_text(
                solver_path.read_text(encoding="utf-8")
                + "\ndef _init_rule_engine():\n    return None\n",
                encoding="utf-8",
            )
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("_init_rule_engine" in error for error in errors), errors)

    def test_rule_engine_marker_in_helper_source_fails_readiness(self) -> None:
        # Changed: cover forbidden markers in every packaged src/*.py file.
        # Why: legacy helper solvers must not bypass the LLM-only package gate.
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            helper_path = Path(temp_name) / "src" / "lora_solver.py"
            helper_path.write_text(
                "def legacy_helper():\n    rule_id = 'OLD_RULE'\n    return rule_id\n",
                encoding="utf-8",
            )
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("lora_solver.py" in error and "rule_id" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
