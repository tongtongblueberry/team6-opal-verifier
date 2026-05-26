#!/usr/bin/env python3
"""Evaluate a standalone full/selective fine-tuned model on manifest rows.

This evaluator is intentionally separate from the LoRA adapter evaluator. It
loads a full Hugging Face model directory or base model path directly and keeps
the prompt contract aligned with tools.training.train_manifest_full.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# Added: make repo-root imports work when this file is executed as a script.
# Why: the evaluator must reuse train_manifest_full prompt contract without
# depending on installation state.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.training import train_manifest_full


KST = timezone(timedelta(hours=9), name="KST")
VALID_LABELS = {"pass", "fail"}
VALID_EVAL_SPLITS = {"train", "val", "validation", "calibration"}
ECE_BIN_COUNT = 10


@dataclass(frozen=True)
class CandidateScore:
    logit: float
    token_id: int


@dataclass(frozen=True)
class ModelBundle:
    tokenizer: Any
    model: Any
    torch: Any
    input_device: Any
    dtype_name: str
    load_mode: str
    auto_device_map_error: Optional[str]


def fail(message: str, exit_code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a full fine-tuned model directly from a manifest JSONL."
    )
    parser.add_argument("--manifest", required=True, help="Manifest JSONL containing train/val rows or val rows.")
    parser.add_argument("--model-path", required=True, help="Full fine-tuned model directory or base model path.")
    parser.add_argument(
        "--split",
        action="append",
        default=None,
        help="Split to evaluate, default val. May be repeated or comma-separated.",
    )
    parser.add_argument("--threshold", type=float, default=0.5, help="Predict fail when p_fail >= threshold.")
    parser.add_argument("--max-seq-len", type=int, default=2048, help="Maximum prompt token length.")
    parser.add_argument("--batch-size", type=int, default=1, help="Evaluation batch size.")
    parser.add_argument("--output-json", required=True, help="Output JSON report path.")
    parser.add_argument("--output-md", required=True, help="Output Korean Markdown report path.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit after split filtering.")
    parser.add_argument(
        "--torch-dtype",
        choices=("auto", "float16", "bfloat16", "float32"),
        default="auto",
        help="Torch dtype for model loading.",
    )
    parser.add_argument(
        "--device-map",
        default="auto",
        help="device_map passed to transformers. Use 'none' to load then move to cuda if available.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifest/split/report wiring without loading model dependencies.",
    )
    return parser.parse_args()


def parse_splits(values: Optional[Sequence[str]]) -> list[str]:
    raw_values = list(values) if values else ["val"]
    splits: list[str] = []
    for value in raw_values:
        for part in value.split(","):
            split = part.strip().lower()
            if not split:
                continue
            if split == "validation":
                split = "val"
            if split not in VALID_EVAL_SPLITS:
                fail(f"Unsupported --split {split!r}; expected one of {sorted(VALID_EVAL_SPLITS)}")
            if split not in splits:
                splits.append(split)
    if not splits:
        fail("At least one non-empty --split value is required")
    return splits


def validate_args(args: argparse.Namespace) -> list[str]:
    selected_splits = parse_splits(args.split)
    if not 0.0 <= args.threshold <= 1.0:
        fail("--threshold must be between 0.0 and 1.0")
    if args.max_seq_len <= 0:
        fail("--max-seq-len must be positive")
    if args.batch_size <= 0:
        fail("--batch-size must be positive")
    if args.limit is not None and args.limit <= 0:
        fail("--limit must be positive when provided")
    return selected_splits


# Added: load all manifest rows instead of train_manifest_full.load_manifest.
# Why: the trainer intentionally drops non-train rows, but the evaluator must
# select val rows while preserving the same row validation and prompt fields.
def load_manifest(path: Path) -> tuple[list[train_manifest_full.ManifestRow], dict[str, Any]]:
    train_manifest_full.ensure_not_public_path(path, "manifest")
    if not path.exists():
        fail(f"Manifest not found: {path}")
    if not path.is_file():
        fail(f"Manifest path is not a file: {path}")

    rows: list[train_manifest_full.ManifestRow] = []
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for line_number, raw in train_manifest_full.read_jsonl(path):
        violation_key = train_manifest_full.row_public_path_violation(raw)
        if violation_key:
            fail(
                f"Manifest line {line_number} references forbidden public path in {violation_key}: "
                f"{train_manifest_full.FORBIDDEN_PUBLIC_PATH}"
            )
        policy_violation = train_manifest_full.row_policy_violation(raw)
        if policy_violation:
            fail(f"Manifest line {line_number} violates LLM-only data policy: {policy_violation}")

        input_text = raw.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            fail(f"Manifest line {line_number} is missing non-empty string field 'input'")
        label = train_manifest_full.normalize_label(raw.get("label"), line_number)
        split = train_manifest_full.normalize_split(raw.get("split"))
        source_value = raw.get("source", "unknown")
        source = source_value if isinstance(source_value, str) and source_value else "unknown"
        sample_id = str(raw.get("sample_id", f"line-{line_number}"))

        split_counts[split] += 1
        label_counts[label] += 1
        source_counts[source] += 1
        rows.append(
            train_manifest_full.ManifestRow(
                sample_id=sample_id,
                input_text=input_text,
                label=label,
                split=split,
                source=source,
                row_index=line_number,
            )
        )

    if not rows:
        fail("Manifest has no rows")
    return rows, {
        "manifest_path": str(path),
        "total_rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "source_counts_top20": dict(source_counts.most_common(20)),
    }


def select_rows(
    rows: Sequence[train_manifest_full.ManifestRow],
    selected_splits: Sequence[str],
    limit: Optional[int],
) -> tuple[list[train_manifest_full.ManifestRow], int]:
    # Added: keep the pre-limit count next to selected rows.
    # Why: validation reports need to distinguish split filtering from --limit.
    selected = [row for row in rows if row.split in selected_splits]
    if not selected:
        fail(f"No rows found for requested split(s): {', '.join(selected_splits)}")
    selected_before_limit = len(selected)
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        fail("No rows selected after applying --limit")
    return selected, selected_before_limit


def selection_summary(
    rows: Sequence[train_manifest_full.ManifestRow],
    selected_before_limit: int,
) -> dict[str, Any]:
    split_counts: Counter[str] = Counter(row.split for row in rows)
    label_counts: Counter[str] = Counter(row.label for row in rows)
    return {
        "selected_rows_before_limit": selected_before_limit,
        "selected_rows_after_limit": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
    }


# Added: explicitly expose the trainer prompt contract for tests and reports.
# Why: full-model validation must score the same user=input, assistant=label
# chat shape used by full fine-tuning.
def build_prompt_messages(row: train_manifest_full.ManifestRow) -> list[dict[str, str]]:
    messages = train_manifest_full.build_messages(row)
    return messages[:-1]


def apply_prompt_template(tokenizer: Any, row: train_manifest_full.ManifestRow) -> str:
    return train_manifest_full.apply_chat_template(tokenizer, build_prompt_messages(row), answer_included=False)


def import_runtime_dependencies() -> tuple[Any, Any, Any]:
    try:
        import torch
    except ImportError as exc:
        fail(f"Missing dependency 'torch'. Install torch to run full-model evaluation. Import error: {exc}")
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        fail(f"Missing dependency 'transformers'. Install transformers to load the model. Import error: {exc}")
    return torch, AutoTokenizer, AutoModelForCausalLM


def choose_dtype(torch: Any, dtype_name: str) -> tuple[Any, str]:
    if dtype_name == "float16":
        return torch.float16, "float16"
    if dtype_name == "bfloat16":
        return torch.bfloat16, "bfloat16"
    if dtype_name == "float32":
        return torch.float32, "float32"
    if torch.cuda.is_available():
        if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
            return torch.bfloat16, "bfloat16"
        return torch.float16, "float16"
    return torch.float32, "float32"


def load_tokenizer(auto_tokenizer: Any, model_path: str) -> Any:
    tokenizer = auto_tokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        if tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
        elif tokenizer.unk_token is not None:
            tokenizer.pad_token = tokenizer.unk_token
        else:
            fail("Tokenizer has no pad/eos/unk token available for batch padding")
    return tokenizer


def first_parameter_device(model: Any) -> Any:
    try:
        return model.device
    except AttributeError:
        pass
    try:
        return next(model.parameters()).device
    except StopIteration:
        fail("Loaded model has no parameters")
    return None


def load_model_bundle(model_path: str, torch_dtype: str, device_map: str) -> ModelBundle:
    torch, auto_tokenizer, auto_model = import_runtime_dependencies()
    tokenizer = load_tokenizer(auto_tokenizer, model_path)
    dtype, dtype_name = choose_dtype(torch, torch_dtype)

    load_mode = f"device_map_{device_map}"
    auto_error: Optional[str] = None
    model_kwargs: dict[str, Any] = {"trust_remote_code": True, "torch_dtype": dtype}
    if device_map != "none":
        model_kwargs["device_map"] = device_map
    try:
        model = auto_model.from_pretrained(model_path, **model_kwargs)
    except Exception as exc:
        auto_error = str(exc)
        load_mode = "single_device_fallback"
        model = auto_model.from_pretrained(model_path, trust_remote_code=True, torch_dtype=dtype)
        if torch.cuda.is_available():
            model = model.to("cuda")

    model.eval()
    input_device = first_parameter_device(model)
    return ModelBundle(
        tokenizer=tokenizer,
        model=model,
        torch=torch,
        input_device=input_device,
        dtype_name=dtype_name,
        load_mode=load_mode,
        auto_device_map_error=auto_error,
    )


def ensure_list_of_token_lists(value: Any) -> list[list[int]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and (not value or isinstance(value[0], int)):
        return [[int(item) for item in value]]
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [[int(item) for item in row] for row in value]
    fail("Tokenizer returned input_ids in an unsupported shape")


def candidate_label_token_ids(tokenizer: Any, label: str) -> list[int]:
    try:
        encoded = tokenizer(label, add_special_tokens=False)
    except TypeError:
        encoded = tokenizer(label)
    input_ids = encoded.get("input_ids") if isinstance(encoded, dict) else getattr(encoded, "input_ids", None)
    if input_ids is None:
        fail(f"Tokenizer did not return input_ids for label {label!r}")
    token_ids = ensure_list_of_token_lists(input_ids)[0]
    if not token_ids:
        fail(f"Tokenizer returned no tokens for label {label!r}")
    return token_ids


def build_label_token_report(tokenizer: Any) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for label in ("pass", "fail"):
        token_ids = candidate_label_token_ids(tokenizer, label)
        report[label] = {"token_ids": token_ids, "first_token_id": token_ids[0]}
    if report["pass"]["first_token_id"] == report["fail"]["first_token_id"]:
        fail("Tokenizer maps pass/fail to the same first token ID; cannot compare next-token logits")
    return report


def batched(
    rows: Sequence[train_manifest_full.ManifestRow],
    batch_size: int,
) -> Iterable[list[train_manifest_full.ManifestRow]]:
    for start in range(0, len(rows), batch_size):
        yield list(rows[start : start + batch_size])


# Added: score full-model prompts by the first generated pass/fail token.
# Why: public20 validation needs deterministic class scores without generation
# length effects or LoRA adapter-specific loading.
def score_next_token_batch(
    bundle: ModelBundle,
    rows: Sequence[train_manifest_full.ManifestRow],
    label_token_report: dict[str, dict[str, Any]],
    max_seq_len: int,
) -> list[dict[str, CandidateScore]]:
    tokenizer = bundle.tokenizer
    torch = bundle.torch
    prompt_texts = [apply_prompt_template(tokenizer, row) for row in rows]
    encoded = tokenizer(
        prompt_texts,
        truncation=True,
        max_length=max_seq_len,
        padding=True,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"].to(bundle.input_device)
    attention_mask = encoded["attention_mask"].to(bundle.input_device)

    with torch.inference_mode():
        outputs = bundle.model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits

    pass_token_id = int(label_token_report["pass"]["first_token_id"])
    fail_token_id = int(label_token_report["fail"]["first_token_id"])
    vocab_size = int(logits.shape[-1])
    if pass_token_id >= vocab_size or fail_token_id >= vocab_size:
        fail(
            "Label first-token ID exceeds model vocabulary size: "
            f"pass={pass_token_id}, fail={fail_token_id}, vocab={vocab_size}"
        )

    scores: list[dict[str, CandidateScore]] = []
    sequence_width = int(input_ids.shape[1])
    padding_side = getattr(tokenizer, "padding_side", "right")
    for index, row in enumerate(rows):
        seq_len = int(attention_mask[index].sum().item())
        if seq_len <= 0:
            fail(f"Manifest line {row.row_index} produced an empty prompt after tokenization")
        next_token_position = sequence_width - 1 if padding_side == "left" else seq_len - 1
        next_token_logits = logits[index, next_token_position, :]
        scores.append(
            {
                "pass": CandidateScore(logit=float(next_token_logits[pass_token_id].item()), token_id=pass_token_id),
                "fail": CandidateScore(logit=float(next_token_logits[fail_token_id].item()), token_id=fail_token_id),
            }
        )
    return scores


def binary_logprob(pass_score: float, fail_score: float) -> tuple[float, float, float]:
    max_score = max(pass_score, fail_score)
    pass_exp = math.exp(pass_score - max_score)
    fail_exp = math.exp(fail_score - max_score)
    denom = pass_exp + fail_exp
    p_pass = pass_exp / denom
    p_fail = fail_exp / denom
    return math.log(p_pass), math.log(p_fail), p_fail


def prediction_at_threshold(p_fail: float, threshold: float) -> str:
    return "fail" if p_fail >= threshold else "pass"


def evaluate_rows(
    rows: Sequence[train_manifest_full.ManifestRow],
    bundle: Any,
    label_token_report: dict[str, dict[str, Any]],
    threshold: float,
    max_seq_len: int,
    batch_size: int,
) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for batch_rows in batched(rows, batch_size):
        batch_scores = score_next_token_batch(bundle, batch_rows, label_token_report, max_seq_len)
        for row, candidate_scores in zip(batch_rows, batch_scores):
            pass_score = candidate_scores["pass"]
            fail_score = candidate_scores["fail"]
            logprob_pass, logprob_fail, p_fail = binary_logprob(pass_score.logit, fail_score.logit)
            prediction = prediction_at_threshold(p_fail, threshold)
            predictions.append(
                {
                    "line_number": row.row_index,
                    "sample_id": row.sample_id,
                    "split": row.split,
                    "source": row.source,
                    "gold": row.label,
                    "prediction": prediction,
                    "correct": prediction == row.label,
                    "p_fail": p_fail,
                    "binary_logprob_pass": logprob_pass,
                    "binary_logprob_fail": logprob_fail,
                    "logit_pass_first_token": pass_score.logit,
                    "logit_fail_first_token": fail_score.logit,
                    "logit_margin_fail_minus_pass": fail_score.logit - pass_score.logit,
                    "pass_first_token_id": pass_score.token_id,
                    "fail_first_token_id": fail_score.token_id,
                }
            )
    return predictions


def divide_or_none(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def f1_or_none(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None or not precision + recall:
        return None
    return 2 * precision * recall / (precision + recall)


def compute_metric_block(predictions: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    tp = tn = fp = fn = 0
    for item in predictions:
        prediction = prediction_at_threshold(float(item["p_fail"]), threshold)
        if item["gold"] == "fail" and prediction == "fail":
            tp += 1
        elif item["gold"] == "pass" and prediction == "pass":
            tn += 1
        elif item["gold"] == "pass" and prediction == "fail":
            fp += 1
        elif item["gold"] == "fail" and prediction == "pass":
            fn += 1
    n = len(predictions)
    precision_fail = divide_or_none(tp, tp + fp)
    recall_fail = divide_or_none(tp, tp + fn)
    f1_fail = f1_or_none(precision_fail, recall_fail)
    precision_pass = divide_or_none(tn, tn + fn)
    recall_pass = divide_or_none(tn, tn + fp)
    f1_pass = f1_or_none(precision_pass, recall_pass)
    macro_f1 = (f1_fail + f1_pass) / 2 if f1_fail is not None and f1_pass is not None else None
    return {
        "n": n,
        "threshold": threshold,
        "accuracy": (tp + tn) / n if n else 0.0,
        "precision_fail": precision_fail,
        "recall_fail": recall_fail,
        "f1_fail": f1_fail,
        "precision_pass": precision_pass,
        "recall_pass": recall_pass,
        "f1_pass": f1_pass,
        "macro_f1": macro_f1,
        "confusion_matrix": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
    }


def compute_metrics(predictions: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    by_split: dict[str, Any] = {}
    for split in sorted({str(item["split"]) for item in predictions}):
        by_split[split] = compute_metric_block(
            [item for item in predictions if item["split"] == split],
            threshold,
        )
    return {"overall": compute_metric_block(predictions, threshold), "by_split": by_split}


def base_report(
    args: argparse.Namespace,
    selected_splits: Sequence[str],
    manifest_summary: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "created_at_kst": datetime.now(KST).isoformat(),
        "mode": "dry_run" if args.dry_run else "eval",
        "manifest": manifest_summary,
        "selection": selection,
        "arguments": {
            "model_path": args.model_path,
            "split": list(selected_splits),
            "threshold": args.threshold,
            "max_seq_len": args.max_seq_len,
            "batch_size": args.batch_size,
            "limit": args.limit,
            "torch_dtype": args.torch_dtype,
            "device_map": args.device_map,
            "output_json": args.output_json,
            "output_md": args.output_md,
        },
        "environment": {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "policy": {
            "manifest_only": True,
            "gold_label_field": "label",
            "prompt_contract": "tools.training.train_manifest_full.build_messages",
            "model_load": "full_model_direct",
            "no_lora_adapter": True,
            "no_solver_import": True,
            "no_rule_engine_import": True,
            "no_leaderboard_submission": True,
            "public20_labels_local_only_for_model_validation": True,
        },
    }


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_percent(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def markdown_table_cell(value: Any) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return " ".join(text.splitlines())


def metric_table_lines(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "| 구간 | n | Accuracy | Macro F1 | Fail Recall | Pass Recall | Fail F1 | Pass F1 | TP | TN | FP | FN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rows = [("overall", metrics["overall"])] + [
        (split, block) for split, block in sorted(metrics.get("by_split", {}).items())
    ]
    for name, block in rows:
        confusion = block["confusion_matrix"]
        lines.append(
            f"| {markdown_table_cell(name)} | {block['n']} | {format_percent(block['accuracy'])} | "
            f"{format_percent(block['macro_f1'])} | {format_percent(block['recall_fail'])} | "
            f"{format_percent(block['recall_pass'])} | {format_percent(block['f1_fail'])} | "
            f"{format_percent(block['f1_pass'])} | {confusion['TP']} | {confusion['TN']} | "
            f"{confusion['FP']} | {confusion['FN']} |"
        )
    return lines


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    args = report["arguments"]
    lines = [
        "# Full FT 모델 Validation 리포트",
        "",
        f"- 생성 시각(KST): {report['created_at_kst']}",
        f"- mode: `{report['mode']}`",
        f"- manifest: `{report['manifest']['manifest_path']}`",
        f"- model path: `{args['model_path']}`",
        f"- split: `{args['split']}`",
        f"- threshold: `{args['threshold']}`",
        f"- max seq len: `{args['max_seq_len']}`",
        f"- batch size: `{args['batch_size']}`",
        f"- limit: `{args['limit']}`",
        "",
        "## Manifest",
        "",
        f"- total rows: {report['manifest']['total_rows']}",
        f"- manifest split counts: `{report['manifest']['split_counts']}`",
        f"- manifest label counts: `{report['manifest']['label_counts']}`",
        f"- selected rows before limit: {report['selection']['selected_rows_before_limit']}",
        f"- selected rows after limit: {report['selection']['selected_rows_after_limit']}",
        f"- selected split counts: `{report['selection']['split_counts']}`",
        f"- selected label counts: `{report['selection']['label_counts']}`",
        "",
    ]
    if report["mode"] == "dry_run":
        lines.extend(
            [
                "## Dry Run",
                "",
                "- 모델은 로드하지 않았다.",
                "- manifest gate, split 선택, prompt contract 검증만 수행했다.",
            ]
        )
    else:
        model = report["model"]
        lines.extend(
            [
                "## 모델 로드",
                "",
                f"- dtype: `{model['dtype']}`",
                f"- load mode: `{model['load_mode']}`",
                f"- input device: `{model['input_device']}`",
                f"- device_map fallback error: `{model['auto_device_map_error']}`",
                f"- label token ids: `{model['label_token_ids']}`",
                "",
                "## Metric",
                "",
            ]
        )
        lines.extend(metric_table_lines(report["metrics"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    selected_splits = validate_args(args)
    rows, manifest_summary = load_manifest(Path(args.manifest))
    selected_rows, selected_before_limit = select_rows(rows, selected_splits, args.limit)
    selection = selection_summary(selected_rows, selected_before_limit)
    report = base_report(args, selected_splits, manifest_summary, selection)

    if args.dry_run:
        report["model"] = None
        report["metrics"] = None
        report["predictions"] = []
        report["dry_run"] = {"model_loaded": False}
        write_json_report(Path(args.output_json), report)
        write_markdown_report(Path(args.output_md), report)
        return 0

    bundle = load_model_bundle(args.model_path, args.torch_dtype, args.device_map)
    label_token_report = build_label_token_report(bundle.tokenizer)
    predictions = evaluate_rows(
        selected_rows,
        bundle,
        label_token_report,
        threshold=args.threshold,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
    )
    report["model"] = {
        "dtype": bundle.dtype_name,
        "load_mode": bundle.load_mode,
        "input_device": str(bundle.input_device),
        "auto_device_map_error": bundle.auto_device_map_error,
        "label_token_ids": label_token_report,
    }
    report["metrics"] = compute_metrics(predictions, args.threshold)
    report["predictions"] = predictions
    write_json_report(Path(args.output_json), report)
    write_markdown_report(Path(args.output_md), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
