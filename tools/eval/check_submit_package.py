#!/usr/bin/env python3
# Changed: add a submit-package readiness gate for HF offline/cache parity.
# Why: Job 401/403 failed before model inference because package runtime env and solver loads diverged.

from __future__ import annotations

import argparse
import io
import json
import re
import tokenize
from dataclasses import dataclass
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

# Changed: define package-local model artifact locations accepted by the submission gate.
# Why: Cycle 2 packages may contain either a standalone merged model or a LoRA adapter.
MERGED_MODEL_RELATIVE_DIR = Path("artifacts") / "merged_model"
LORA_ADAPTER_RELATIVE_DIRS = (
    Path("artifacts") / "lora_adapter_dcv2_final",
    Path("artifacts") / "lora_adapter_final",
    Path("artifacts") / "lora_adapter_v3",
    Path("artifacts") / "lora_adapter_v2",
    Path("artifacts") / "lora_adapter",
)
MERGED_MODEL_WEIGHT_PATTERNS = (
    "model*.safetensors",
    "pytorch_model*.bin",
)
MERGED_MODEL_INDEX_FILES = (
    "model.safetensors.index.json",
    "pytorch_model.bin.index.json",
)
MERGED_MODEL_TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "sentencepiece.bpe.model",
)
LORA_ADAPTER_WEIGHT_FILES = (
    "adapter_model.safetensors",
    "adapter_model.bin",
)

# Changed: scan executable Python tokens for deterministic verifier imports/calls.
# Why: no-rule policy must ignore explanatory comments while still blocking rule-engine architecture.
FORBIDDEN_RULE_ENGINE_MARKERS = (
    "_init_rule_engine",
    "StatefulOpalVerifier",
    "ProtocolState",
    "RULE_SPEC_QUERIES",
    "verify_with_trace",
    "RuleEngine",
    "USE_RULE_ENGINE",
    "rule_context",
    "rule_id",
)


# Changed: expose artifact status for both the static checker and runtime smoke.
# Why: runtime smoke should report whether it is validating a merged model or LoRA package.
@dataclass(frozen=True)
class ModelArtifactStatus:
    kind: str
    path: Path | None
    errors: tuple[str, ...]


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


# Changed: strip comments and string literals before no-rule marker scanning.
# Why: required explanatory comments can mention forbidden architecture terms without adding runtime code.
def _python_code_without_comments_or_strings(source: str) -> str:
    parts: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in {tokenize.COMMENT, tokenize.STRING}:
                continue
            parts.append(token.string)
    except tokenize.TokenError:
        return source
    return " ".join(parts)


# Changed: collect only real merged model weight files, not shard index metadata.
# Why: an index-only artifacts/merged_model directory passes static strings but cannot load at runtime.
def _merged_weight_files(merged_dir: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in MERGED_MODEL_WEIGHT_PATTERNS:
        for path in merged_dir.glob(pattern):
            if path.is_file() and not path.name.endswith(".index.json"):
                files.add(path)
    return sorted(files)


# Changed: validate shard index references when an index file is present.
# Why: a merged package with missing referenced shards should fail before evaluator runtime.
def _check_index_referenced_weights(merged_dir: Path) -> list[str]:
    errors: list[str] = []
    for index_name in MERGED_MODEL_INDEX_FILES:
        index_path = merged_dir / index_name
        if not index_path.exists():
            continue
        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"{MERGED_MODEL_RELATIVE_DIR}/{index_name} is not valid JSON")
            continue
        weight_map = index_data.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            errors.append(f"{MERGED_MODEL_RELATIVE_DIR}/{index_name} missing non-empty weight_map")
            continue
        missing = sorted(
            {
                str(relative_path)
                for relative_path in weight_map.values()
                if isinstance(relative_path, str) and not (merged_dir / relative_path).is_file()
            }
        )
        if missing:
            errors.append(
                f"{MERGED_MODEL_RELATIVE_DIR}/{index_name} references missing shards: "
                + ", ".join(missing[:5])
            )
    return errors


# Changed: detect a usable merged model by config, weights, and tokenizer files.
# Why: solver.py selects artifacts/merged_model when config.json exists, so incomplete merged packages must fail early.
def _check_merged_model_artifact(package_dir: Path) -> tuple[bool, list[str]]:
    merged_dir = package_dir / MERGED_MODEL_RELATIVE_DIR
    if not merged_dir.exists():
        return False, []
    # Changed: only treat merged_model as authoritative when config.json exists.
    # Why: solver.py ignores a stray artifacts/merged_model directory without config.json.
    if not (merged_dir / "config.json").exists():
        return False, []

    errors: list[str] = []
    # Changed: require actual weight files and validate optional shard indexes.
    # Why: index metadata without referenced shards cannot be loaded by AutoModelForCausalLM.
    if not _merged_weight_files(merged_dir):
        errors.append(f"{MERGED_MODEL_RELATIVE_DIR}/ missing merged model weight shard")
    errors.extend(_check_index_referenced_weights(merged_dir))
    if not any((merged_dir / name).exists() for name in MERGED_MODEL_TOKENIZER_FILES):
        errors.append(f"{MERGED_MODEL_RELATIVE_DIR}/ missing tokenizer file")
    return not errors, errors


# Changed: detect a usable LoRA adapter package from supported repo-local adapter names.
# Why: legacy LoRA packages remain valid when no merged model artifact is packaged.
def _check_lora_adapter_artifact(package_dir: Path) -> tuple[bool, Path | None, list[str]]:
    partial_errors: list[str] = []
    for relative_dir in LORA_ADAPTER_RELATIVE_DIRS:
        adapter_dir = package_dir / relative_dir
        if not adapter_dir.exists():
            continue
        if not (adapter_dir / "adapter_config.json").exists():
            partial_errors.append(f"{relative_dir}/ missing adapter_config.json")
            continue
        missing_weights = not any((adapter_dir / name).exists() for name in LORA_ADAPTER_WEIGHT_FILES)
        if missing_weights:
            partial_errors.append(f"{relative_dir}/ missing adapter model weights")
            continue
        return True, adapter_dir, []
    return False, None, partial_errors


# Changed: require a usable LLM artifact family to be present in the package.
# Why: readiness should pass for merged-model or LoRA packages and fail before runtime when neither exists.
def detect_model_artifact(package_dir: Path) -> ModelArtifactStatus:
    package_dir = package_dir.resolve()
    merged_dir = package_dir / MERGED_MODEL_RELATIVE_DIR
    merged_ok, merged_errors = _check_merged_model_artifact(package_dir)
    if merged_errors:
        return ModelArtifactStatus("invalid_merged_model", merged_dir, tuple(merged_errors))
    if merged_ok:
        return ModelArtifactStatus("merged_model", merged_dir, ())

    lora_ok, lora_path, lora_errors = _check_lora_adapter_artifact(package_dir)
    if lora_ok:
        return ModelArtifactStatus("lora_adapter", lora_path, ())
    if lora_errors:
        return ModelArtifactStatus("invalid_lora_adapter", lora_path, tuple(lora_errors))

    return ModelArtifactStatus(
        "missing",
        None,
        (
            "missing model artifact: include artifacts/merged_model/ with config, "
            "weights, tokenizer or a supported artifacts/lora_adapter*/ adapter",
        ),
    )


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
    for marker in ("OPAL_MERGED_MODEL_DIR", "_resolve_merged_model_path", "artifacts\" / \"merged_model"):
        if marker not in solver_source:
            errors.append(f"src/solver.py missing merged model support marker {marker}")
    return errors


# Changed: keep no-rule architecture scanning inside the package checker.
# Why: submit packages must not reintroduce deterministic rule-engine imports or calls.
def _check_no_rule_engine_path(solver_source: str) -> list[str]:
    code_source = _python_code_without_comments_or_strings(solver_source)
    errors: list[str] = []
    for marker in FORBIDDEN_RULE_ENGINE_MARKERS:
        if marker in code_source:
            errors.append(f"src/solver.py contains forbidden rule-engine marker {marker}")
    if re.search(r"\b(from|import)\b[^\n]*(spec_solver|probe_solver|llm_solver)", code_source):
        errors.append("src/solver.py imports a non-submission solver module")
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

    solver_source = _read_text(solver_path)
    errors.extend(_check_setup_env(_read_text(setup_path)))
    errors.extend(_check_solver_hf_policy(solver_source))
    errors.extend(_check_no_rule_engine_path(solver_source))
    errors.extend(detect_model_artifact(package_dir).errors)
    return errors


# Changed: keep CLI output to pass/fail status without dumping source contents.
# Why: package checks must not print credentials or raw evaluator artifacts.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check submit package HF offline and artifact readiness.")
    parser.add_argument("package_dir", nargs="?", default=".", help="Submit package directory.")
    args = parser.parse_args(argv)

    errors = check_submit_package(Path(args.package_dir))
    if errors:
        print("FAIL: submit package HF offline/artifact readiness")
        for error in errors:
            print(f"  - {error}")
        return 1

    artifact = detect_model_artifact(Path(args.package_dir))
    print(f"OK: submit package HF offline/artifact readiness ({artifact.kind})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
