#!/usr/bin/env python3
"""Data Contract v2 manifest-only LoRA trainer.

This script intentionally reads only the provided JSONL manifest. It does not
import solver, verifier, public evaluation labels, or leaderboard data.
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
FORBIDDEN_PUBLIC_PATH = "/dl2026/dataset"
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]
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

logger = logging.getLogger("train_manifest_lora")


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
    adapter_root: Path
    checkpoint_dir: Path
    final_dir: Path
    artifact_dir: Path
    report_json: Path
    report_md: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train an LLM-only LoRA adapter from a Data Contract v2 JSONL manifest."
    )
    parser.add_argument("--manifest", required=True, help="Path to Data Contract v2 JSONL manifest.")
    parser.add_argument("--run-root", required=True, help="Run root for adapters and artifacts.")
    parser.add_argument("--adapter-name", required=True, help="Adapter name under run_root/adapters.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--epochs", type=float, default=5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.05)
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--resume", action="store_true", help="Resume from the latest checkpoint if present.")
    parser.add_argument("--dry-run", action="store_true", help="Load manifest and tokenize a small sample only.")
    parser.add_argument("--dry-run-samples", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save-total-limit", type=int, default=3)
    parser.add_argument("--logging-steps", type=int, default=10)
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


def build_paths(run_root: Path, adapter_name: str) -> RunPaths:
    if not adapter_name or adapter_name in {".", ".."}:
        fail("--adapter-name must be a non-empty directory name")
    if "/" in adapter_name or "\\" in adapter_name:
        fail("--adapter-name must not contain path separators")

    adapter_root = run_root / "adapters" / adapter_name
    artifact_dir = run_root / "artifacts"
    return RunPaths(
        run_root=run_root,
        adapter_root=adapter_root,
        checkpoint_dir=adapter_root / "checkpoints",
        final_dir=adapter_root / "final",
        artifact_dir=artifact_dir,
        report_json=artifact_dir / f"{adapter_name}.train_report.json",
        report_md=artifact_dir / f"{adapter_name}.train_report.md",
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
    # Changed: repeat the LLM-only manifest leakage gate inside the trainer.
    # Why: training must fail closed even if a caller bypasses the Data Contract validator.
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

    # Changed: only parse manifest rows so training cannot pull public/eval data from side files.
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
    # Changed: user content is exactly manifest input and answer is exactly pass/fail.
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


class ManifestLoraDataset:
    """Torch Dataset wrapper without importing torch until training/dry-run time."""

    def __init__(self, rows: Sequence[ManifestRow], tokenizer: Any, max_seq_len: int):
        import torch

        self._torch_dataset_base = torch.utils.data.Dataset
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

    lines = [
        "# Data Contract v2 LoRA 학습 리포트",
        "",
        f"- 생성 시각(KST): {report['created_at_kst']}",
        f"- manifest: `{report['manifest']['manifest_path']}`",
        f"- adapter: `{report['paths']['final_dir']}`",
        f"- mode: `{report['mode']}`",
        f"- total rows: {report['manifest']['total_rows']}",
        f"- train rows: {report['manifest']['train_rows']}",
        f"- non-train rows kept out: {report['manifest']['skipped_non_train_rows']}",
        f"- split counts: `{report['manifest']['split_counts']}`",
        f"- train label counts: `{report['manifest']['train_label_counts']}`",
        f"- dry-run tokenizer fallback: `{report.get('dry_run', {}).get('tokenizer_fallback', False)}`",
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
        # Changed: all run records use KST timestamps.
        # Why: project cycle records and nohup logs are compared in KST.
        "created_at_kst": datetime.now(KST).isoformat(),
        "mode": "dry_run" if args.dry_run else "train",
        "manifest": manifest_summary,
        "paths": {key: str(value) for key, value in asdict(paths).items()},
        "hyperparameters": {
            "base_model": args.base_model,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "grad_accum": args.grad_accum,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "label_smoothing": args.label_smoothing,
            "max_seq_len": args.max_seq_len,
            "warmup_ratio": args.warmup_ratio,
            "target_modules": TARGET_MODULES,
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
        },
    }


class FallbackTokenizer:
    """Tiny CPU-only tokenizer for local dry-run when Transformers/model files are unavailable."""

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
        padding: str = "max_length",
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
    # Changed: dry-run tokenizes without torch tensors so local validation stays CPU-safe.
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

    report["dry_run"] = {
        "sample_rows": len(sample_rows),
        "tokenized_examples": len(answer_token_counts),
        "skipped_examples": skipped,
        "answer_token_counts": answer_token_counts,
        "tokenizer_fallback": fallback,
        "tokenizer_error": tokenizer_error,
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
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, Trainer, TrainingArguments, set_seed

    paths.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    paths.final_dir.mkdir(parents=True, exist_ok=True)
    paths.artifact_dir.mkdir(parents=True, exist_ok=True)

    set_seed(args.seed)
    tokenizer = load_tokenizer(args.base_model)
    dataset = ManifestLoraDataset(rows, tokenizer, args.max_seq_len)
    if len(dataset) == 0:
        fail("Tokenization produced zero training examples", exit_code=1)

    # Changed: model is loaded only after manifest validation/tokenization passes.
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    if hasattr(model, "config"):
        model.config.use_cache = False

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=TARGET_MODULES,
    )
    model = get_peft_model(model, lora_config)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    trainable_params = sum(param.numel() for param in model.parameters() if param.requires_grad)
    total_params = sum(param.numel() for param in model.parameters())

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
        optim="adamw_torch",
        logging_steps=args.logging_steps,
        save_strategy="epoch",
        save_total_limit=args.save_total_limit,
        fp16=True,
        gradient_checkpointing=True,
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

    # Changed: final adapter is written only under the provided run root.
    start = time.time()
    result = trainer.train(resume_from_checkpoint=str(resume_checkpoint) if resume_checkpoint else None)
    elapsed = time.time() - start

    model.save_pretrained(str(paths.final_dir))
    tokenizer.save_pretrained(str(paths.final_dir))

    report["training"] = {
        "dataset_examples": len(dataset),
        "skipped_examples": dataset.skipped,
        "trainable_params": trainable_params,
        "total_params": total_params,
        "trainable_ratio": trainable_params / total_params if total_params else None,
        "resume_checkpoint": str(resume_checkpoint) if resume_checkpoint else None,
        "training_loss": float(result.training_loss) if result.training_loss is not None else None,
        "elapsed_seconds": elapsed,
    }
    write_report(paths, report)
    logger.info("Training complete: final=%s report=%s", paths.final_dir, paths.report_json)
    return 0


def validate_args(args: argparse.Namespace) -> None:
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


def main() -> int:
    configure_logging()
    args = parse_args()
    validate_args(args)

    manifest_path = Path(args.manifest).expanduser().resolve()
    run_root = Path(args.run_root).expanduser().resolve()
    paths = build_paths(run_root, args.adapter_name)
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
