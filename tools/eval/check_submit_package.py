#!/usr/bin/env python3
# Changed: add a submit-package readiness gate for HF offline/cache parity.
# Why: Job 401/403 failed before model inference because package runtime env and solver loads diverged.

from __future__ import annotations

import argparse
import re
from pathlib import Path


# Changed: keep required HF env names explicit for static setup.sh checks.
# Why: evaluator shells must define the same cache/offline variables the solver reads.
REQUIRED_HF_ENV_NAMES = (
    "HF_HOME",
    "HF_HUB_CACHE",
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
)

# Changed: require each artifact loader to consume the shared HF local/offline kwargs.
# Why: tokenizer, base model, and LoRA adapter must all honor local_files_only together.
LOAD_CALL_MARKERS = (
    "AutoTokenizer.from_pretrained",
    "AutoModelForCausalLM.from_pretrained",
    "PeftModel.from_pretrained",
)


# Changed: read only source files needed for package readiness checks.
# Why: the checker must not inspect credentials, datasets, or raw evaluator IO.
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Changed: inspect a bounded source window around each loader call.
# Why: simple static gating is enough to catch missing local_files_only propagation.
def _source_window(source: str, marker: str, width: int = 700) -> str:
    index = source.find(marker)
    if index < 0:
        return ""
    return source[index : index + width]


# Changed: make setup.sh HF env parity a hard package gate.
# Why: evaluator cache/offline defaults must be present before runtime imports solver.
def _check_setup_env(setup_source: str) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_HF_ENV_NAMES:
        if name not in setup_source:
            errors.append(f"setup.sh missing {name}")
        elif not re.search(rf"\bexport\s+{re.escape(name)}\b", setup_source):
            errors.append(f"setup.sh defines {name} without exporting it")
    return errors


# Changed: make solver local/offline policy a hard package gate.
# Why: solver must not rely on network-capable Hugging Face defaults in offline evaluation.
def _check_solver_hf_policy(solver_source: str) -> list[str]:
    errors: list[str] = []
    for marker in ("_hf_local_files_only", "_hf_load_kwargs", "local_files_only"):
        if marker not in solver_source:
            errors.append(f"src/solver.py missing {marker}")
    for env_name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if env_name not in solver_source:
            errors.append(f"src/solver.py does not read {env_name}")
    for marker in LOAD_CALL_MARKERS:
        window = _source_window(solver_source, marker)
        if not window:
            errors.append(f"src/solver.py missing loader call {marker}")
        elif "hf_load_kwargs" not in window and "local_files_only" not in window:
            errors.append(f"{marker} does not receive HF local/offline kwargs")
    return errors


# Changed: expose a reusable package check for tests and runtime smoke.
# Why: both static readiness and runtime smoke should enforce the same gate.
def check_submit_package(package_dir: Path) -> list[str]:
    package_dir = package_dir.resolve()
    errors: list[str] = []

    setup_path = package_dir / "setup.sh"
    solver_path = package_dir / "src" / "solver.py"
    if not setup_path.exists():
        errors.append("missing setup.sh")
    if not solver_path.exists():
        errors.append("missing src/solver.py")
    if errors:
        return errors

    errors.extend(_check_setup_env(_read_text(setup_path)))
    errors.extend(_check_solver_hf_policy(_read_text(solver_path)))
    return errors


# Changed: keep CLI output to pass/fail status without dumping source contents.
# Why: package checks must not print credentials or raw evaluator artifacts.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check submit package HF offline readiness.")
    parser.add_argument("package_dir", nargs="?", default=".", help="Submit package directory.")
    args = parser.parse_args(argv)

    errors = check_submit_package(Path(args.package_dir))
    if errors:
        print("FAIL: submit package HF offline readiness")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: submit package HF offline readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
