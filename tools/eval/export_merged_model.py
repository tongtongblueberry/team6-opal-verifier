#!/usr/bin/env python3
# Changed: add a CLI for exporting a standalone merged model artifact.
# Why: Cycle 2 submit packages can use the 12GB limit by shipping merged base+LoRA weights.

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Changed: keep default paths package-relative and explicit.
# Why: the export command should create the artifact layout consumed by src/solver.py.
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADAPTER_DIR = ROOT / "artifacts" / "lora_adapter_dcv2_final"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "merged_model"
TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
TOKENIZER_MARKER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "sentencepiece.bpe.model",
)


# Changed: parse boolean-like HF offline env values without guessing unknown strings.
# Why: export should respect offline shells when HF_HUB_OFFLINE or TRANSFORMERS_OFFLINE is set.
def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in TRUE_ENV_VALUES


# Changed: build HF loading kwargs once for base, adapter, and tokenizer loads.
# Why: all export inputs must use the same cache/offline policy.
def _hf_load_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    local_files_only = (
        args.local_files_only
        or _env_flag("HF_HUB_OFFLINE")
        or _env_flag("TRANSFORMERS_OFFLINE")
    )
    kwargs: dict[str, Any] = {"local_files_only": local_files_only}
    if args.cache_dir:
        kwargs["cache_dir"] = str(Path(args.cache_dir).expanduser())
    return kwargs


# Changed: detect whether the adapter directory carries tokenizer files.
# Why: PEFT adapters sometimes save tokenizer files; otherwise the base tokenizer should be saved.
def _adapter_has_tokenizer(adapter_dir: Path) -> bool:
    return any((adapter_dir / name).exists() for name in TOKENIZER_MARKER_FILES)


# Changed: summarize artifact file sizes for the manifest and CLI output.
# Why: submit packaging needs an immediate size sanity check against the 12GB limit.
def _artifact_files(output_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(output_dir)),
                    "size_bytes": path.stat().st_size,
                }
            )
    return files


# Changed: write a small manifest next to the merged model files.
# Why: package review should be able to identify source base, adapter, shard size, and total bytes.
def _write_manifest(
    output_dir: Path,
    args: argparse.Namespace,
    files: list[dict[str, Any]],
) -> Path:
    manifest = {
        "artifact_type": "merged_model",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_model": args.base_model,
        "adapter_dir": str(Path(args.adapter_dir).expanduser()),
        "output_dir": str(output_dir),
        "safe_serialization": True,
        "max_shard_size": args.max_shard_size,
        "torch_dtype": args.torch_dtype,
        "device_map": args.device_map,
        "files": files,
        "total_size_bytes": sum(item["size_bytes"] for item in files),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


# Changed: isolate the actual merge_and_unload export behind the CLI entrypoint.
# Why: imports for torch/transformers/peft are only required when an operator intentionally runs export.
def export_merged_model(args: argparse.Namespace) -> Path:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter_dir = Path(args.adapter_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not (adapter_dir / "adapter_config.json").exists():
        raise FileNotFoundError(f"adapter_config.json not found: {adapter_dir}")
    output_has_files = output_dir.exists() and any(output_dir.iterdir())
    if output_has_files and not args.overwrite:
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    if output_has_files and args.overwrite:
        # Changed: remove stale shards before re-exporting into the same target directory.
        # Why: repeated Cycle 2 exports must not leave obsolete weight files in the package manifest.
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dtype_by_name = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    hf_load_kwargs = _hf_load_kwargs(args)
    tokenizer_source = str(adapter_dir) if _adapter_has_tokenizer(adapter_dir) else args.base_model

    # Changed: load tokenizer before model merge and save it into the standalone artifact.
    # Why: src/solver.py loads AutoTokenizer directly from artifacts/merged_model.
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_source,
        trust_remote_code=args.trust_remote_code,
        **hf_load_kwargs,
    )

    # Changed: load base + LoRA adapter, then materialize merged weights with merge_and_unload().
    # Why: runtime merged_model loading must not require PeftModel.from_pretrained().
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=dtype_by_name[args.torch_dtype],
        device_map=args.device_map,
        trust_remote_code=args.trust_remote_code,
        **hf_load_kwargs,
    )
    peft_model = PeftModel.from_pretrained(
        base_model,
        str(adapter_dir),
        **hf_load_kwargs,
    )
    merged_model = peft_model.merge_and_unload()

    # Changed: save merged weights with safetensors and configurable sharding.
    # Why: submit package size can be controlled while avoiding pickle-based model files.
    merged_model.save_pretrained(
        output_dir,
        safe_serialization=True,
        max_shard_size=args.max_shard_size,
    )
    tokenizer.save_pretrained(output_dir)

    files = _artifact_files(output_dir)
    manifest_path = _write_manifest(output_dir, args, files)
    total_size = sum(item["size_bytes"] for item in files)
    print(f"merged_model_dir={output_dir}")
    print(f"manifest={manifest_path}")
    print(f"total_size_bytes={total_size}")
    print(f"total_size_gib={total_size / (1024 ** 3):.3f}")
    return output_dir


# Changed: provide an operator-facing CLI without doing work at import time.
# Why: unit checks can py_compile this file; real export only happens when main() is executed.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export base+LoRA as artifacts/merged_model.")
    parser.add_argument("--base-model", default=os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B"))
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-shard-size", default="4GB")
    parser.add_argument("--torch-dtype", choices=("float16", "bfloat16", "float32"), default="float16")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-trust-remote-code", dest="trust_remote_code", action="store_false")
    parser.set_defaults(trust_remote_code=True)
    args = parser.parse_args(argv)

    export_merged_model(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
