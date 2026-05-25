#!/usr/bin/env python3
# Changed: add a runtime smoke gate for submit-package HF offline parity.
# Why: static package checks must be paired with an import-time check of solver local_files_only policy.

from __future__ import annotations

import argparse
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

# Changed: make direct script execution import sibling tools modules from repo root.
# Why: `python tools/eval/runtime_smoke_submit_package.py` sets sys.path to tools/eval.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.eval.check_submit_package import check_submit_package, detect_model_artifact


# Changed: report model-load status separately from package/runtime parity.
# Why: model artifacts may be absent in CI or local recovery worktrees, so load can be NOT_RUN.
@dataclass
class SmokeResult:
    ok: bool
    messages: list[str]


# Changed: force an offline HF env only inside this smoke process.
# Why: the gate must prove solver honors HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE without mutating the caller shell.
@contextmanager
def _offline_hf_env(package_dir: Path):
    saved = {
        name: os.environ.get(name)
        for name in ("HF_HOME", "HF_HUB_CACHE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
    }
    cache_dir = saved["HF_HUB_CACHE"] or saved["HF_HOME"] or str(package_dir / ".hf_cache")
    os.environ["HF_HOME"] = saved["HF_HOME"] or cache_dir
    os.environ["HF_HUB_CACHE"] = saved["HF_HUB_CACHE"] or cache_dir
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# Changed: import solver from the package under test instead of the current repo path.
# Why: runtime smoke must validate the candidate submit directory, not an installed/stale module.
@contextmanager
def _package_import_path(package_dir: Path):
    package_path = str(package_dir)
    old_path = list(sys.path)
    old_modules = {
        name: sys.modules.get(name)
        for name in ("src", "src.solver")
    }
    for name in ("src.solver", "src"):
        sys.modules.pop(name, None)
    sys.path.insert(0, package_path)
    try:
        yield
    finally:
        sys.path[:] = old_path
        for name in ("src.solver", "src"):
            sys.modules.pop(name, None)
        for name, module in old_modules.items():
            if module is not None:
                sys.modules[name] = module


# Changed: isolate solver import so no Solver() construction happens during default smoke.
# Why: model-load smoke is optional because artifact presence is environment-dependent.
def _import_solver(package_dir: Path) -> ModuleType:
    with _package_import_path(package_dir):
        return importlib.import_module("src.solver")


# Changed: add a bounded evaluator-like testcase for optional first-forward smoke.
# Why: predict_one() must be exercised without printing or depending on real evaluator data.
def _first_forward_testcase() -> dict[str, object]:
    return {
        "id": "runtime_smoke_first_forward",
        "steps": [
            {
                "input": {
                    "method": {"name": "StartSession", "args": {}},
                    "invoking_id": {"name": "SMUID", "uid": "0xFF"},
                },
                "output": {"status": "SUCCESS", "status_codes": "SUCCESS"},
            }
        ],
    }


# Changed: keep exception reporting status-only for optional runtime stages.
# Why: model/runtime errors can include environment-specific paths; smoke output should not expose payloads.
def _stage_exception_message(stage: str, action: str, exc: Exception) -> str:
    return f"{stage}_FAIL: {action} raised {type(exc).__name__}"


# Changed: display artifact paths relative to the package under test.
# Why: smoke output should identify merged-vs-LoRA mode without printing environment-specific absolute paths.
def _artifact_display_path(package_dir: Path, artifact_path: Path | None) -> str:
    if artifact_path is None:
        return "<none>"
    try:
        return str(artifact_path.relative_to(package_dir))
    except ValueError:
        return artifact_path.name


# Changed: validate runtime offline parity through solver's own policy helpers.
# Why: this catches cases where static strings exist but local_files_only resolves incorrectly.
def run_runtime_smoke(
    package_dir: Path, load_model: bool = False, first_forward: bool = False
) -> SmokeResult:
    package_dir = package_dir.resolve()
    messages: list[str] = []
    # Changed: first-forward implies model-load before predict_one() is called.
    # Why: archive runtime smoke treats first-forward as a stronger model availability check.
    model_load = load_model or first_forward

    package_errors = check_submit_package(package_dir)
    if package_errors:
        return SmokeResult(False, [f"CHECK_FAIL: {error}" for error in package_errors])
    artifact = detect_model_artifact(package_dir)
    messages.append("CHECK_OK: static HF offline/artifact readiness")
    messages.append(
        f"ARTIFACT_OK: {artifact.kind} at {_artifact_display_path(package_dir, artifact.path)}"
    )

    with _offline_hf_env(package_dir):
        solver = _import_solver(package_dir)
        local_files_only = solver._hf_local_files_only(package_dir)
        if local_files_only is not True:
            return SmokeResult(False, ["RUNTIME_FAIL: solver local_files_only is not true under offline env"])
        load_kwargs = solver._hf_load_kwargs(package_dir)
        if load_kwargs.get("local_files_only") is not True:
            return SmokeResult(False, ["RUNTIME_FAIL: _hf_load_kwargs missing local_files_only=True"])
        messages.append("RUNTIME_OK: solver resolves local_files_only=True under offline env")

        if model_load and not first_forward:
            # Changed: accept both explicit model-load and implied first-forward construction checks.
            # Why: first-forward cannot be meaningful unless Solver() construction succeeds first.
            try:
                solver.Solver()
            except Exception as exc:
                return SmokeResult(
                    False,
                    messages + [_stage_exception_message("MODEL_LOAD", "Solver construction", exc)],
                )
            messages.append("MODEL_LOAD_OK: Solver constructed")
        else:
            if first_forward:
                messages.append("MODEL_LOAD_DEFERRED: first-forward will exercise model load")
            else:
                messages.append(
                    "MODEL_LOAD_NOT_RUN: set OPAL_RUNTIME_SMOKE_LOAD_MODEL=1 when artifacts are present"
                )

        if first_forward:
            # Changed: use one predict_one() call for first-forward instead of preconstructing Solver().
            # Why: avoiding a duplicate model load reduces OOM risk during server package gates.
            try:
                prediction = solver.predict_one(_first_forward_testcase())
            except Exception as exc:
                return SmokeResult(
                    False,
                    messages + [_stage_exception_message("FIRST_FORWARD", "predict_one", exc)],
                )
            if prediction not in {"pass", "fail"}:
                return SmokeResult(
                    False,
                    messages + ["FIRST_FORWARD_FAIL: predict_one returned non-pass/fail result"],
                )
            messages.append("MODEL_LOAD_OK: implied by first-forward")
            messages.append(f"FIRST_FORWARD_OK: predict_one returned {prediction}")
        else:
            messages.append(
                "FIRST_FORWARD_NOT_RUN: set --first-forward when artifacts are present"
            )

    return SmokeResult(True, messages)


# Changed: provide a small CLI gate for package builders and unit tests.
# Why: operators need a no-submit smoke command that fails on env parity regressions.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Runtime smoke submit package HF offline parity.")
    parser.add_argument("package_dir", nargs="?", default=".", help="Submit package directory.")
    # Changed: keep compatibility with older archive commands that used --package-dir.
    # Why: server gate scripts should not fail just because they use the named path option.
    parser.add_argument(
        "--package-dir",
        dest="package_dir_option",
        help="Submit package directory; overrides the positional package_dir when provided.",
    )
    # Changed: accept archive-compatible CLI flags while preserving the old --load-model alias.
    # Why: recovery packages may call the smoke command with historical option names.
    parser.add_argument(
        "--model-load",
        "--load-model",
        dest="load_model",
        action="store_true",
        help="Instantiate Solver; requires local merged model or base model plus LoRA adapter artifacts.",
    )
    parser.add_argument(
        "--first-forward",
        action="store_true",
        help="Call predict_one() with a minimal evaluator-like testcase; implies --model-load.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Accepted for archive compatibility; this smoke always forces offline HF env.",
    )
    args = parser.parse_args(argv)

    # Changed: first-forward implies model-load at the CLI boundary as well as inside runtime smoke.
    # Why: callers should see the same behavior whether they use main() or run_runtime_smoke().
    load_model = (
        args.load_model
        or args.first_forward
        or os.environ.get("OPAL_RUNTIME_SMOKE_LOAD_MODEL") == "1"
    )
    # Changed: resolve package path after parsing both positional and named forms.
    # Why: --package-dir must be a strict alias without changing the smoke logic.
    package_dir = Path(args.package_dir_option or args.package_dir)
    result = run_runtime_smoke(package_dir, load_model=load_model, first_forward=args.first_forward)
    status = "OK" if result.ok else "FAIL"
    print(f"{status}: runtime smoke submit package")
    for message in result.messages:
        print(f"  - {message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
