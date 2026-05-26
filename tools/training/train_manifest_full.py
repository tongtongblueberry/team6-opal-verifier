#!/usr/bin/env python3
"""Data Contract v2 manifest-only full/selective fine-tuning trainer.

This trainer is intentionally separate from solver and verifier code. It reads
only the provided manifest JSONL, keeps non-train splits out of training, and
writes a standalone Hugging Face model artifact under the requested run root.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import platform
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


IGNORE_INDEX = -100
VALID_LABELS = {"pass", "fail"}
VALID_TRAIN_MODES = {"full", "last-n-layers", "lm-head-only"}
VALID_TORCH_DTYPES = {"float16", "bfloat16", "float32"}
FORBIDDEN_PUBLIC_PATH = "/dl2026/dataset"
KST = timezone(timedelta(hours=9), name="KST")
PUBLIC_HOLDOUT_PATTERNS = (
    "public",
    "public20",
    "public 20",
    "public_20",
    "public-20",
    "eval",
    "evaluation",
    "eval holdout",
    "eval_holdout",
    "eval-holdout",
    "holdout",
    "leaderboard",
)
RULE_CONTEXT_PATTERNS = (
    "rule context",
    "rule_context",
    "rule-context",
    "rule_engine",
    "rule-engine",
    "rule engine analysis",
    "rule engine predicted",
    "rule_id",
    "rule id",
    "statefulopalverifier",
    "rule trace",
    "rule output",
    "rule_output",
    "rule result",
    "rule_result",
    "deterministic verifier",
    "verifier trace",
    "verifier_trace",
    "protocol rules above",
    "rules above",
    "tcg rule summary",
)
METADATA_SCAN_EXCLUDED_FIELDS = {"input", "label", "row", "length_bin", "content_hash"}

logger = logging.getLogger("train_manifest_full")


@dataclass(frozen=True)
class ManifestRow:
    sample_id: str
    input_text: str
    label: str
    split: str
    source: str
    row_index: int


@dataclass(frozen=True)
class RunPaths:
    run_root: Path
    model_root: Path
    checkpoint_dir: Path
    final_dir: Path
    artifact_dir: Path
    report_json: Path
    report_md: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a full or selective LLM checkpoint from a Data Contract v2 JSONL manifest."
    )
    parser.add_argument("--manifest", required=True, help="Path to Data Contract v2 JSONL manifest.")
    parser.add_argument("--run-root", required=True, help="Run root for checkpoints, final model, and reports.")
    parser.add_argument("--model-name", required=True, help="Model artifact name under run_root/models.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--train-mode", choices=sorted(VALID_TRAIN_MODES), default="last-n-layers")
    parser.add_argument("--last-n-layers", type=int, default=4)
    parser.add_argument("--unfreeze-embeddings", action="store_true")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--torch-dtype", choices=sorted(VALID_TORCH_DTYPES), default="float16")
    parser.add_argument("--device-map", default="auto", help="Use 'none' to avoid passing device_map to from_pretrained.")
    parser.add_argument("--optim", default="adamw_torch")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint if present.")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest, tokenization, and freeze plan only.")
    parser.add_argument("--dry-run-load-model", action="store_true", help="In dry-run, also load model for exact trainable params.")
    parser.add_argument("--dry-run-samples", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save-total-limit", type=int, default=3)
    parser.add_argument("--save-strategy", choices=("epoch", "steps"), default="epoch")
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument(
        "--no-gradient-checkpointing",
        dest="gradient_checkpointing",
        action="store_false",
        help="Disable gradient checkpointing.",
    )
    parser.set_defaults(gradient_checkpointing=True)
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def fail(message: str, exit_code: int = 2) -> None:
    logger.error(message)
    raise SystemExit(exit_code)


def ensure_not_public_path(path: Path, label: str) -> None:
    path_text = str(path.expanduser())
    if FORBIDDEN_PUBLIC_PATH in path_text:
        fail(f"{label} must not be under forbidden public path: {FORBIDDEN_PUBLIC_PATH}")


def build_paths(run_root: Path, model_name: str) -> RunPaths:
    if not model_name or model_name in {".", ".."}:
        fail("--model-name must be a non-empty directory name")
    if "/" in model_name or "\\" in model_name:
        fail("--model-name must not contain path separators")

    model_root = run_root / "models" / model_name
    artifact_dir = run_root / "artifacts"
    return RunPaths(
        run_root=run_root,
        model_root=model_root,
        checkpoint_dir=model_root / "checkpoints",
        final_dir=model_root / "final",
        artifact_dir=artifact_dir,
        report_json=artifact_dir / f"{model_name}.train_report.json",
        report_md=artifact_dir / f"{model_name}.train_report.md",
    )


def read_jsonl(path: Path) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                fail(f"Invalid JSONL at line {index}: {exc}")
            if not isinstance(value, dict):
                fail(f"Manifest line {index} is not a JSON object")
            yield index, value


def normalize_label(value: Any, line_number: int) -> str:
    if not isinstance(value, str):
        fail(f"Manifest line {line_number} has non-string label")
    label = value.strip().lower()
    if label not in VALID_LABELS:
        fail(f"Manifest line {line_number} has unsupported label: {value!r}")
    return label


def normalize_split(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return "unspecified"


def row_public_path_violation(row: Dict[str, Any]) -> Optional[str]:
    for key in ("path", "source_path", "dataset_path", "file", "filename"):
        value = row.get(key)
        if isinstance(value, str) and FORBIDDEN_PUBLIC_PATH in value:
            return key
    return None


def scan_text_forms(value: Any) -> Tuple[str, str, str, set]:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    text = text.lower()
    spaced = re.sub(r"[^a-z0-9]+", " ", text).strip()
    compact = re.sub(r"[^a-z0-9]+", "", text)
    return text, spaced, compact, set(spaced.split())


def match_pattern(value: Any, patterns: Sequence[str]) -> Optional[str]:
    text, spaced, compact, tokens = scan_text_forms(value)
    for pattern in patterns:
        lowered = pattern.lower()
        lowered_spaced = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        lowered_compact = re.sub(r"[^a-z0-9]+", "", lowered)
        if " " not in lowered_spaced and lowered_spaced:
            if lowered_spaced in tokens or lowered_compact == compact:
                return pattern
            continue
        if lowered in text or lowered_spaced in spaced or lowered_compact in compact:
            return pattern
    return None


def row_policy_violation(row: Dict[str, Any]) -> Optional[str]:
    # Added: repeat the manifest leakage gate in this standalone trainer.
    # Why: full FT must remain LLM-only even when run outside the validator.
    for key, value in row.items():
        key_text = str(key)
        if key_text not in METADATA_SCAN_EXCLUDED_FIELDS:
            public_match = match_pattern(key_text, PUBLIC_HOLDOUT_PATTERNS) or match_pattern(value, PUBLIC_HOLDOUT_PATTERNS)
            if public_match:
                return f"public/eval holdout marker in {key_text}: {public_match}"
            rule_match = match_pattern(key_text, RULE_CONTEXT_PATTERNS) or match_pattern(value, RULE_CONTEXT_PATTERNS)
            if rule_match:
                return f"rule-context marker in metadata {key_text}: {rule_match}"
        if key_text == "input":
            rule_match = match_pattern(value, RULE_CONTEXT_PATTERNS)
            if rule_match:
                return f"rule-context marker in input: {rule_match}"
    return None


def load_manifest(path: Path) -> Tuple[List[ManifestRow], Dict[str, Any]]:
    ensure_not_public_path(path, "manifest")
    if not path.exists():
        fail(f"Manifest not found: {path}")
    if not path.is_file():
        fail(f"Manifest path is not a file: {path}")

    rows: List[ManifestRow] = []
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    train_label_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    skipped_non_train = 0

    for line_number, raw in read_jsonl(path):
        violation_key = row_public_path_violation(raw)
        if violation_key:
            fail(
                f"Manifest line {line_number} references forbidden public path in {violation_key}: "
                f"{FORBIDDEN_PUBLIC_PATH}"
            )
        policy_violation = row_policy_violation(raw)
        if policy_violation:
            fail(f"Manifest line {line_number} violates LLM-only data policy: {policy_violation}")

        input_text = raw.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            fail(f"Manifest line {line_number} is missing non-empty string field 'input'")

        label = normalize_label(raw.get("label"), line_number)
        split = normalize_split(raw.get("split"))
        source = raw.get("source", "unknown")
        source_text = source if isinstance(source, str) and source else "unknown"
        sample_id = raw.get("sample_id", f"line-{line_number}")
        sample_id_text = str(sample_id)

        split_counts[split] += 1
        label_counts[label] += 1
        source_counts[source_text] += 1

        if split != "train":
            skipped_non_train += 1
            continue

        train_label_counts[label] += 1
        rows.append(
            ManifestRow(
                sample_id=sample_id_text,
                input_text=input_text,
                label=label,
                split=split,
                source=source_text,
                row_index=line_number,
            )
        )

    if not rows:
        fail("No train rows found in manifest")

    summary = {
        "manifest_path": str(path),
        "total_rows": sum(split_counts.values()),
        "train_rows": len(rows),
        "skipped_non_train_rows": skipped_non_train,
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "train_label_counts": dict(sorted(train_label_counts.items())),
        "source_counts_top20": dict(source_counts.most_common(20)),
    }
    return rows, summary


def build_messages(row: ManifestRow) -> List[Dict[str, str]]:
    return [
        {"role": "user", "content": row.input_text},
        {"role": "assistant", "content": row.label},
    ]


def apply_chat_template(tokenizer: Any, messages: Sequence[Dict[str, str]], answer_included: bool) -> str:
    kwargs = {
        "tokenize": False,
        "add_generation_prompt": not answer_included,
    }
    try:
        return tokenizer.apply_chat_template(messages, enable_thinking=False, **kwargs)
    except TypeError:
        return tokenizer.apply_chat_template(messages, **kwargs)
    except Exception:
        if answer_included:
            prompt = messages[0]["content"]
            answer = messages[-1]["content"]
            return f"User: {prompt}\nAssistant: {answer}"
        return f"User: {messages[0]['content']}\nAssistant:"


def encode_example(tokenizer: Any, row: ManifestRow, max_seq_len: int) -> Optional[Dict[str, Any]]:
    messages = build_messages(row)
    full_text = apply_chat_template(tokenizer, messages, answer_included=True)
    prompt_text = apply_chat_template(tokenizer, messages[:-1], answer_included=False)

    full_encoded = tokenizer(
        full_text,
        truncation=True,
        max_length=max_seq_len,
        padding="max_length",
        return_tensors="pt",
    )
    prompt_encoded = tokenizer(
        prompt_text,
        truncation=True,
        max_length=max_seq_len,
        return_tensors="pt",
    )

    input_ids = full_encoded["input_ids"].squeeze(0)
    attention_mask = full_encoded["attention_mask"].squeeze(0)
    labels = input_ids.clone()
    prompt_len = int(prompt_encoded["input_ids"].shape[1])
    if prompt_len < max_seq_len:
        labels[:prompt_len] = IGNORE_INDEX
    else:
        labels[:] = IGNORE_INDEX
    labels[attention_mask == 0] = IGNORE_INDEX

    if int((labels != IGNORE_INDEX).sum().item()) == 0:
        return None
    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
    }


class ManifestFullDataset:
    """Torch Dataset wrapper without importing torch until real training starts."""

    def __init__(self, rows: Sequence[ManifestRow], tokenizer: Any, max_seq_len: int):
        self.examples: List[Dict[str, Any]] = []
        self.skipped = 0
        for row in rows:
            encoded = encode_example(tokenizer, row, max_seq_len)
            if encoded is None:
                self.skipped += 1
                continue
            self.examples.append(encoded)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        return self.examples[index]


def load_tokenizer(base_model: str) -> Any:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


class FallbackTokenizer:
    """Tiny CPU-only tokenizer for local dry-run when model files are unavailable."""

    pad_token = "<pad>"
    eos_token = "</s>"

    def apply_chat_template(
        self,
        messages: Sequence[Dict[str, str]],
        tokenize: bool = False,
        add_generation_prompt: bool = False,
        **_: Any,
    ) -> str:
        parts = []
        for message in messages:
            parts.append(f"{message['role']}: {message['content']}")
        if add_generation_prompt:
            parts.append("assistant:")
        text = "\n".join(parts)
        if tokenize:
            return self(text)["input_ids"]
        return text

    def __call__(
        self,
        text: str,
        truncation: bool = True,
        max_length: int = 2048,
        padding: Any = "max_length",
        return_tensors: Optional[str] = "pt",
    ) -> Dict[str, Any]:
        tokens = text.split()
        ids = [abs(hash(token)) % 32000 + 1 for token in tokens]
        if truncation:
            ids = ids[:max_length]
        attention = [1] * len(ids)
        if padding == "max_length" and len(ids) < max_length:
            pad_len = max_length - len(ids)
            ids.extend([0] * pad_len)
            attention.extend([0] * pad_len)
        if return_tensors is None:
            return {"input_ids": ids, "attention_mask": attention}
        import torch

        result = {
            "input_ids": torch.tensor([ids], dtype=torch.long),
            "attention_mask": torch.tensor([attention], dtype=torch.long),
        }
        if return_tensors != "pt":
            raise ValueError("FallbackTokenizer only supports return_tensors='pt'")
        return result


def flatten_token_ids(value: Any) -> List[int]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [int(item) for item in value[0]]
    if isinstance(value, list):
        return [int(item) for item in value]
    return []


def dry_answer_token_count(tokenizer: Any, row: ManifestRow, max_seq_len: int) -> int:
    messages = build_messages(row)
    full_text = apply_chat_template(tokenizer, messages, answer_included=True)
    prompt_text = apply_chat_template(tokenizer, messages[:-1], answer_included=False)
    full_encoded = tokenizer(
        full_text,
        truncation=True,
        max_length=max_seq_len,
        padding=False,
        return_tensors=None,
    )
    prompt_encoded = tokenizer(
        prompt_text,
        truncation=True,
        max_length=max_seq_len,
        padding=False,
        return_tensors=None,
    )
    full_ids = flatten_token_ids(full_encoded.get("input_ids"))
    prompt_ids = flatten_token_ids(prompt_encoded.get("input_ids"))
    return max(0, len(full_ids) - min(len(prompt_ids), max_seq_len))


def get_module_by_path(model: Any, path: str) -> Optional[Any]:
    current = model
    for part in path.split("."):
        if not hasattr(current, part):
            return None
        current = getattr(current, part)
    return current


def resolve_decoder_layers(model: Any) -> Tuple[str, Sequence[Any]]:
    candidates = (
        "model.layers",
        "model.decoder.layers",
        "decoder.layers",
        "transformer.h",
        "gpt_neox.layers",
    )
    for path in candidates:
        module = get_module_by_path(model, path)
        if module is not None and hasattr(module, "__len__") and hasattr(module, "__getitem__") and len(module) > 0:
            return path, module
    fail("Could not locate decoder layers for --train-mode last-n-layers")


def set_module_trainable(module: Any, trainable: bool) -> int:
    count = 0
    for param in module.parameters():
        param.requires_grad = trainable
        count += int(param.numel())
    return count


def unfreeze_named_module(model: Any, path: str) -> Optional[int]:
    module = get_module_by_path(model, path)
    if module is None:
        return None
    return set_module_trainable(module, True)


def count_parameters(model: Any) -> Tuple[int, int]:
    total = 0
    trainable = 0
    for param in model.parameters():
        total += int(param.numel())
        if param.requires_grad:
            trainable += int(param.numel())
    return total, trainable


def planned_freeze_summary(args: argparse.Namespace) -> Dict[str, Any]:
    # Added: dry-run can verify the intended training surface without loading a 4B model.
    # Why: full FT may OOM, so the first gate must be cheap and resumable.
    if args.train_mode == "full":
        trainable_scope = "all model parameters"
    elif args.train_mode == "last-n-layers":
        trainable_scope = f"last {args.last_n_layers} decoder layers, lm_head, final norm"
        if args.unfreeze_embeddings:
            trainable_scope += ", embeddings"
    else:
        trainable_scope = "lm_head only"
    return {
        "train_mode": args.train_mode,
        "last_n_layers": args.last_n_layers if args.train_mode == "last-n-layers" else None,
        "unfreeze_embeddings": bool(args.unfreeze_embeddings),
        "trainable_scope": trainable_scope,
        "exact_parameter_counts": False,
    }


def apply_train_mode(model: Any, args: argparse.Namespace) -> Dict[str, Any]:
    total_before, _ = count_parameters(model)
    for param in model.parameters():
        param.requires_grad = args.train_mode == "full"

    trainable_modules: List[str] = []
    module_param_counts: Dict[str, int] = {}

    if args.train_mode == "full":
        trainable_modules.append("<all>")
    elif args.train_mode == "last-n-layers":
        layer_path, layers = resolve_decoder_layers(model)
        layer_count = len(layers)
        selected_count = min(args.last_n_layers, layer_count)
        start_index = layer_count - selected_count
        for index in range(start_index, layer_count):
            module_path = f"{layer_path}.{index}"
            module_param_counts[module_path] = set_module_trainable(layers[index], True)
            trainable_modules.append(module_path)
        for module_path in ("model.norm", "transformer.ln_f", "lm_head"):
            param_count = unfreeze_named_module(model, module_path)
            if param_count is not None:
                module_param_counts[module_path] = param_count
                trainable_modules.append(module_path)
        if args.unfreeze_embeddings:
            for module_path in ("model.embed_tokens", "transformer.wte"):
                param_count = unfreeze_named_module(model, module_path)
                if param_count is not None:
                    module_param_counts[module_path] = param_count
                    trainable_modules.append(module_path)
    elif args.train_mode == "lm-head-only":
        param_count = unfreeze_named_module(model, "lm_head")
        if param_count is None:
            fail("Could not locate lm_head for --train-mode lm-head-only")
        module_param_counts["lm_head"] = param_count
        trainable_modules.append("lm_head")

    total_after, trainable_after = count_parameters(model)
    return {
        "train_mode": args.train_mode,
        "total_params": total_after,
        "trainable_params": trainable_after,
        "trainable_ratio": trainable_after / total_after if total_after else None,
        "total_params_before_freeze": total_before,
        "trainable_modules": trainable_modules,
        "module_param_counts": module_param_counts,
        "exact_parameter_counts": True,
    }


def torch_dtype_from_arg(value: str) -> Any:
    import torch

    if value == "float16":
        return torch.float16
    if value == "bfloat16":
        return torch.bfloat16
    if value == "float32":
        return torch.float32
    fail(f"Unsupported torch dtype: {value}")


def load_model_for_training(args: argparse.Namespace) -> Any:
    import torch
    from transformers import AutoModelForCausalLM

    load_kwargs: Dict[str, Any] = {
        "torch_dtype": torch_dtype_from_arg(args.torch_dtype),
        "trust_remote_code": True,
    }
    if args.device_map != "none":
        load_kwargs["device_map"] = args.device_map

    model = AutoModelForCausalLM.from_pretrained(args.base_model, **load_kwargs)
    if args.device_map == "none" and torch.cuda.is_available():
        model = model.to("cuda")
    if hasattr(model, "config"):
        model.config.use_cache = False
    return model


def latest_checkpoint(checkpoint_dir: Path) -> Optional[Path]:
    pattern = str(checkpoint_dir / "checkpoint-*")
    checkpoints = []
    for path_text in glob.glob(pattern):
        match = re.search(r"checkpoint-(\d+)$", path_text)
        step = int(match.group(1)) if match else -1
        checkpoints.append((step, Path(path_text)))
    if not checkpoints:
        return None
    checkpoints.sort(key=lambda item: item[0])
    return checkpoints[-1][1]


def write_report(paths: RunPaths, report: Dict[str, Any]) -> None:
    paths.artifact_dir.mkdir(parents=True, exist_ok=True)
    paths.report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    freeze_plan = report.get("parameter_freeze_plan", {})
    lines = [
        "# Data Contract v2 Full/Selective FT 학습 리포트",
        "",
        f"- 생성 시각(KST): {report['created_at_kst']}",
        f"- manifest: `{report['manifest']['manifest_path']}`",
        f"- final model: `{report['paths']['final_dir']}`",
        f"- mode: `{report['mode']}`",
        f"- train mode: `{freeze_plan.get('train_mode')}`",
        f"- total rows: {report['manifest']['total_rows']}",
        f"- train rows: {report['manifest']['train_rows']}",
        f"- non-train rows kept out: {report['manifest']['skipped_non_train_rows']}",
        f"- split counts: `{report['manifest']['split_counts']}`",
        f"- train label counts: `{report['manifest']['train_label_counts']}`",
        f"- dry-run tokenizer fallback: `{report.get('dry_run', {}).get('tokenizer_fallback', False)}`",
        f"- trainable params: `{freeze_plan.get('trainable_params')}`",
        f"- trainable ratio: `{freeze_plan.get('trainable_ratio')}`",
    ]
    if "training" in report:
        training = report["training"]
        lines.extend(
            [
                f"- resume checkpoint: `{training.get('resume_checkpoint')}`",
                f"- final loss: `{training.get('training_loss')}`",
                f"- elapsed seconds: `{training.get('elapsed_seconds')}`",
            ]
        )
    paths.report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def base_report(args: argparse.Namespace, paths: RunPaths, manifest_summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "created_at_kst": datetime.now(KST).isoformat(),
        "mode": "dry_run" if args.dry_run else "train",
        "manifest": manifest_summary,
        "paths": {key: str(value) for key, value in asdict(paths).items()},
        "hyperparameters": {
            "base_model": args.base_model,
            "train_mode": args.train_mode,
            "last_n_layers": args.last_n_layers,
            "unfreeze_embeddings": args.unfreeze_embeddings,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "grad_accum": args.grad_accum,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "label_smoothing": args.label_smoothing,
            "max_seq_len": args.max_seq_len,
            "warmup_ratio": args.warmup_ratio,
            "torch_dtype": args.torch_dtype,
            "device_map": args.device_map,
            "optim": args.optim,
            "gradient_checkpointing": args.gradient_checkpointing,
            "seed": args.seed,
        },
        "environment": {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "policy": {
            "manifest_only": True,
            "train_split_only": True,
            "no_solver_import": True,
            "no_rule_engine_import": True,
            "no_public_eval_files": True,
            "forbidden_public_path": FORBIDDEN_PUBLIC_PATH,
            "standalone_model_save": True,
            "safe_serialization": True,
        },
        "artifact_constraints": {
            "submission_limit_gb": 12,
            "intended_save_dtype": args.torch_dtype,
            "float32_risk": args.torch_dtype == "float32",
        },
    }


def run_dry_run(
    args: argparse.Namespace,
    paths: RunPaths,
    rows: Sequence[ManifestRow],
    report: Dict[str, Any],
) -> int:
    sample_rows = list(rows[: max(1, args.dry_run_samples)])
    fallback = False
    tokenizer_error = None
    try:
        tokenizer = load_tokenizer(args.base_model)
    except Exception as exc:
        fallback = True
        tokenizer_error = repr(exc)
        logger.warning("Tokenizer load failed in dry-run; using CPU fallback tokenizer: %s", exc)
        tokenizer = FallbackTokenizer()

    answer_token_counts = []
    skipped = 0
    for row in sample_rows:
        answer_tokens = dry_answer_token_count(tokenizer, row, args.max_seq_len)
        if answer_tokens <= 0:
            skipped += 1
            continue
        answer_token_counts.append(answer_tokens)

    if not answer_token_counts:
        fail("Dry-run produced zero tokenized answer examples", exit_code=1)

    freeze_plan = planned_freeze_summary(args)
    if args.dry_run_load_model:
        model = load_model_for_training(args)
        freeze_plan = apply_train_mode(model, args)

    report["parameter_freeze_plan"] = freeze_plan
    report["dry_run"] = {
        "sample_rows": len(sample_rows),
        "tokenized_examples": len(answer_token_counts),
        "skipped_examples": skipped,
        "answer_token_counts": answer_token_counts,
        "tokenizer_fallback": fallback,
        "tokenizer_error": tokenizer_error,
        "model_loaded_for_freeze_plan": bool(args.dry_run_load_model),
    }
    write_report(paths, report)
    logger.info("Dry-run OK: tokenized_examples=%d report=%s", len(answer_token_counts), paths.report_json)
    return 0


def run_training(
    args: argparse.Namespace,
    paths: RunPaths,
    rows: Sequence[ManifestRow],
    report: Dict[str, Any],
) -> int:
    from transformers import Trainer, TrainingArguments, set_seed

    paths.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    paths.final_dir.mkdir(parents=True, exist_ok=True)
    paths.artifact_dir.mkdir(parents=True, exist_ok=True)

    set_seed(args.seed)
    tokenizer = load_tokenizer(args.base_model)
    dataset = ManifestFullDataset(rows, tokenizer, args.max_seq_len)
    if len(dataset) == 0:
        fail("Tokenization produced zero training examples", exit_code=1)

    model = load_model_for_training(args)
    freeze_plan = apply_train_mode(model, args)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()

    training_args = TrainingArguments(
        output_dir=str(paths.checkpoint_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
        label_smoothing_factor=args.label_smoothing,
        max_grad_norm=1.0,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type="cosine",
        optim=args.optim,
        logging_steps=args.logging_steps,
        save_strategy=args.save_strategy,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        fp16=args.torch_dtype == "float16",
        bf16=args.torch_dtype == "bfloat16",
        gradient_checkpointing=args.gradient_checkpointing,
        save_safetensors=True,
        report_to="none",
        dataloader_pin_memory=True,
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    resume_checkpoint = latest_checkpoint(paths.checkpoint_dir) if args.resume else None
    if args.resume and resume_checkpoint is None:
        logger.warning("No checkpoint found under %s; starting from scratch", paths.checkpoint_dir)
    elif resume_checkpoint is not None:
        logger.info("Resuming from checkpoint: %s", resume_checkpoint)

    start = time.time()
    result = trainer.train(resume_from_checkpoint=str(resume_checkpoint) if resume_checkpoint else None)
    elapsed = time.time() - start

    # Added: save a standalone safetensors model so package size can use the 12GB budget.
    # Why: adapter-only artifacts do not test the full/partial FT hypothesis.
    model.save_pretrained(str(paths.final_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(paths.final_dir))

    report["parameter_freeze_plan"] = freeze_plan
    report["training"] = {
        "dataset_examples": len(dataset),
        "skipped_examples": dataset.skipped,
        "resume_checkpoint": str(resume_checkpoint) if resume_checkpoint else None,
        "training_loss": float(result.training_loss) if result.training_loss is not None else None,
        "elapsed_seconds": elapsed,
    }
    write_report(paths, report)
    logger.info("Training complete: final=%s report=%s", paths.final_dir, paths.report_json)
    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.train_mode not in VALID_TRAIN_MODES:
        fail(f"--train-mode must be one of: {', '.join(sorted(VALID_TRAIN_MODES))}")
    if args.last_n_layers < 1:
        fail("--last-n-layers must be >= 1")
    if args.batch_size < 1:
        fail("--batch-size must be >= 1")
    if args.grad_accum < 1:
        fail("--grad-accum must be >= 1")
    if args.max_seq_len < 8:
        fail("--max-seq-len must be >= 8")
    if args.epochs <= 0:
        fail("--epochs must be > 0")
    if args.lr <= 0:
        fail("--lr must be > 0")
    if args.weight_decay < 0:
        fail("--weight-decay must be >= 0")
    if not 0 <= args.label_smoothing < 1:
        fail("--label-smoothing must be in [0, 1)")
    if not 0 <= args.warmup_ratio < 1:
        fail("--warmup-ratio must be in [0, 1)")
    if args.torch_dtype not in VALID_TORCH_DTYPES:
        fail(f"--torch-dtype must be one of: {', '.join(sorted(VALID_TORCH_DTYPES))}")
    if args.save_steps < 1:
        fail("--save-steps must be >= 1")
    if args.save_total_limit < 1:
        fail("--save-total-limit must be >= 1")
    if args.logging_steps < 1:
        fail("--logging-steps must be >= 1")


def main() -> int:
    configure_logging()
    args = parse_args()
    validate_args(args)

    manifest_path = Path(args.manifest).expanduser().resolve()
    run_root = Path(args.run_root).expanduser().resolve()
    paths = build_paths(run_root, args.model_name)
    ensure_not_public_path(run_root, "run-root")

    rows, manifest_summary = load_manifest(manifest_path)
    report = base_report(args, paths, manifest_summary)
    logger.info(
        "Loaded manifest rows: total=%d train=%d splits=%s",
        manifest_summary["total_rows"],
        manifest_summary["train_rows"],
        manifest_summary["split_counts"],
    )

    if args.dry_run:
        return run_dry_run(args, paths, rows, report)
    return run_training(args, paths, rows, report)


if __name__ == "__main__":
    raise SystemExit(main())
