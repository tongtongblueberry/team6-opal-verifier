# Changed: cover runtime smoke behavior under forced HF offline env.
# Why: Job 401/403 class failures need a unit gate that checks local_files_only resolution.

from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools.eval.runtime_smoke_submit_package import main, run_runtime_smoke


# Changed: create fake LoRA artifact files for static package readiness.
# Why: runtime smoke default tests should not depend on real adapter weights.
def _write_fake_lora_artifact(package_dir: Path) -> None:
    adapter_dir = package_dir / "artifacts" / "lora_adapter_dcv2_final"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"fake")


# Changed: create fake merged-model artifact files for static package readiness.
# Why: first-forward smoke must cover merged artifact control flow without real model files.
def _write_fake_merged_model_artifact(package_dir: Path) -> None:
    model_dir = package_dir / "artifacts" / "merged_model"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"fake")
    (model_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")


# Changed: build a minimal importable submit package with fake artifact markers.
# Why: default smoke must validate env parity while leaving model load as NOT_RUN.
def _make_package(root: Path, artifact: str = "lora") -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory()
    package_dir = Path(temp_dir.name)
    (package_dir / "src").mkdir()
    shutil.copy2(root / "setup.sh", package_dir / "setup.sh")
    shutil.copy2(root / "src" / "solver.py", package_dir / "src" / "solver.py")
    shutil.copy2(root / "src" / "__init__.py", package_dir / "src" / "__init__.py")
    # Changed: add a fake artifact marker so static readiness can pass without real weights.
    # Why: default smoke intentionally skips model load and only checks runtime policy.
    if artifact == "merged":
        _write_fake_merged_model_artifact(package_dir)
    else:
        _write_fake_lora_artifact(package_dir)
    return temp_dir


# Changed: build a fake submit package that passes static HF checks without real artifacts.
# Why: model-load and first-forward tests must validate smoke control flow, not external model files.
def _make_fake_package(
    first_forward_result: str = "pass", artifact: str = "merged"
) -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory()
    package_dir = Path(temp_dir.name)
    src_dir = package_dir / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "setup.sh").write_text(
        textwrap.dedent(
            """\
            export HF_HOME="${HF_HOME:-$PWD/.hf_cache}"
            export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME}"
            export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
            export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
            """
        ),
        encoding="utf-8",
    )
    (src_dir / "solver.py").write_text(
        textwrap.dedent(
            f"""\
            import os
            from pathlib import Path


            def _hf_local_files_only(root: Path | None = None) -> bool:
                return (
                    os.environ.get("HF_HUB_OFFLINE") == "1"
                    and os.environ.get("TRANSFORMERS_OFFLINE") == "1"
                )


            def _hf_load_kwargs(root: Path | None = None) -> dict[str, bool]:
                return {{"local_files_only": _hf_local_files_only(root)}}


            def _resolve_merged_model_path(root: Path):
                env_path = os.environ.get("OPAL_MERGED_MODEL_DIR")
                if env_path:
                    return Path(env_path), "OPAL_MERGED_MODEL_DIR"
                return root / "artifacts" / "merged_model", "repo-local"


            def _static_loader_markers() -> None:
                hf_load_kwargs = _hf_load_kwargs(Path("."))
                AutoTokenizer.from_pretrained("tokenizer", **hf_load_kwargs)
                AutoModelForCausalLM.from_pretrained("base", **hf_load_kwargs)
                PeftModel.from_pretrained("adapter", **hf_load_kwargs)


            class Solver:
                def __init__(self) -> None:
                    count = int(os.environ.get("FAKE_SOLVER_CONSTRUCTED", "0"))
                    os.environ["FAKE_SOLVER_CONSTRUCTED"] = str(count + 1)


            def predict_one(testcase):
                # Changed: make fake predict_one mirror the real entrypoint's lazy model construction.
                # Why: first-forward smoke now relies on predict_one() to prove model-load readiness once.
                Solver()
                os.environ["FAKE_FIRST_FORWARD_ID"] = str(testcase.get("id"))
                os.environ["FAKE_FIRST_FORWARD_HAS_STEPS"] = str(bool(testcase.get("steps")))
                return {first_forward_result!r}
            """
        ),
        encoding="utf-8",
    )
    # Changed: let fake packages exercise either merged-model or LoRA artifact recognition.
    # Why: static checker should pass both families without loading real model bytes.
    if artifact == "lora":
        _write_fake_lora_artifact(package_dir)
    else:
        _write_fake_merged_model_artifact(package_dir)
    return temp_dir


# Changed: isolate fake solver environment counters between tests.
# Why: fake package assertions should not leak state into other runtime smoke cases.
def _clear_fake_solver_env() -> None:
    for name in (
        "FAKE_SOLVER_CONSTRUCTED",
        "FAKE_FIRST_FORWARD_ID",
        "FAKE_FIRST_FORWARD_HAS_STEPS",
    ):
        os.environ.pop(name, None)


# Changed: verify runtime smoke does not require artifacts unless explicitly requested.
# Why: recovery worktrees should report model-load NOT_RUN instead of failing package parity.
class RuntimeSmokeSubmitPackageTest(unittest.TestCase):
    def tearDown(self) -> None:
        # Changed: clean fake solver env writes after each test.
        # Why: the fake package records construction/forward calls through process env.
        _clear_fake_solver_env()

    def test_runtime_smoke_forces_local_files_only_and_skips_model_load(self) -> None:
        root = Path(__file__).resolve().parents[1]
        saved = os.environ.get("OPAL_RUNTIME_SMOKE_LOAD_MODEL")
        os.environ.pop("OPAL_RUNTIME_SMOKE_LOAD_MODEL", None)
        try:
            with _make_package(root) as temp_name:
                result = run_runtime_smoke(Path(temp_name))
        finally:
            if saved is None:
                os.environ.pop("OPAL_RUNTIME_SMOKE_LOAD_MODEL", None)
            else:
                os.environ["OPAL_RUNTIME_SMOKE_LOAD_MODEL"] = saved

        self.assertTrue(result.ok, result.messages)
        self.assertTrue(any("RUNTIME_OK" in message for message in result.messages), result.messages)
        self.assertTrue(any("ARTIFACT_OK: lora_adapter" in message for message in result.messages), result.messages)
        self.assertTrue(any("MODEL_LOAD_NOT_RUN" in message for message in result.messages), result.messages)
        self.assertTrue(any("FIRST_FORWARD_NOT_RUN" in message for message in result.messages), result.messages)

    def test_runtime_smoke_first_forward_implies_model_load_for_merged_artifact(self) -> None:
        # Changed: cover first-forward using a fake Solver/predict_one package.
        # Why: merged-model smoke should validate control flow without real model bytes.
        with _make_fake_package(artifact="merged") as temp_name:
            result = run_runtime_smoke(Path(temp_name), first_forward=True)

        self.assertTrue(result.ok, result.messages)
        self.assertEqual("1", os.environ.get("FAKE_SOLVER_CONSTRUCTED"))
        self.assertEqual("runtime_smoke_first_forward", os.environ.get("FAKE_FIRST_FORWARD_ID"))
        self.assertEqual("True", os.environ.get("FAKE_FIRST_FORWARD_HAS_STEPS"))
        self.assertTrue(any("ARTIFACT_OK: merged_model" in message for message in result.messages), result.messages)
        self.assertTrue(any("MODEL_LOAD_OK" in message for message in result.messages), result.messages)
        self.assertTrue(any("FIRST_FORWARD_OK" in message for message in result.messages), result.messages)

    def test_runtime_smoke_rejects_non_pass_fail_first_forward_result(self) -> None:
        # Changed: assert first-forward validates predict_one() result shape.
        # Why: smoke should fail if the LLM-only entrypoint does not return pass/fail.
        with _make_fake_package(first_forward_result="maybe") as temp_name:
            result = run_runtime_smoke(Path(temp_name), first_forward=True)

        self.assertFalse(result.ok, result.messages)
        self.assertTrue(any("FIRST_FORWARD_FAIL" in message for message in result.messages), result.messages)

    def test_cli_accepts_archive_flags_and_load_model_alias(self) -> None:
        # Changed: cover --model-load/--first-forward/--offline and legacy --load-model.
        # Why: archive smoke invocations and existing callers must both parse successfully.
        with _make_fake_package() as temp_name:
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--first-forward", "--offline", temp_name])

        self.assertEqual(0, exit_code, stdout.getvalue())
        self.assertIn("MODEL_LOAD_OK", stdout.getvalue())
        self.assertIn("FIRST_FORWARD_OK", stdout.getvalue())

        _clear_fake_solver_env()
        with _make_fake_package() as temp_name:
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--model-load", temp_name])

        self.assertEqual(0, exit_code, stdout.getvalue())
        self.assertIn("MODEL_LOAD_OK", stdout.getvalue())
        self.assertIn("FIRST_FORWARD_NOT_RUN", stdout.getvalue())

        _clear_fake_solver_env()
        with _make_fake_package() as temp_name:
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--load-model", temp_name])

        self.assertEqual(0, exit_code, stdout.getvalue())
        self.assertIn("MODEL_LOAD_OK", stdout.getvalue())
        self.assertIn("FIRST_FORWARD_NOT_RUN", stdout.getvalue())

        # Changed: cover older archive invocations that pass the package with --package-dir.
        # Why: server-side recovery commands should remain compatible with recorded gate syntax.
        _clear_fake_solver_env()
        with _make_fake_package() as temp_name:
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--package-dir", temp_name, "--first-forward"])

        self.assertEqual(0, exit_code, stdout.getvalue())
        self.assertIn("MODEL_LOAD_OK", stdout.getvalue())
        self.assertIn("FIRST_FORWARD_OK", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
