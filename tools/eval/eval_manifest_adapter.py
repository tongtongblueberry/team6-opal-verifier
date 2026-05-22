#!/usr/bin/env python3
"""Evaluate a LoRA adapter from a Data Contract v2 manifest JSONL only."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# Changed: define the evaluator's manifest-only policy gates in this file.
# Why: evaluation must fail closed on direct solver/verifier/public/rule-context signals in this script and manifest.
VALID_LABELS = {"pass", "fail"}
VALID_EVAL_SPLITS = {"calibration", "hidden"}
FORBIDDEN_DATASET_PATH = "/dl2026/dataset"
KST = timezone(timedelta(hours=9), name="KST")
MIN_COMPACT_SUBSTRING_PATTERN_LEN = 6
PUBLIC_HOLDOUT_PATTERNS = (
    "public",
    "public20",
    "public 20",
    "public_20",
    "public-20",
    "eval",
    "evaluation",
    "holdout",
    "leaderboard",
)
RULE_CONTEXT_PATTERNS = (
    "rule_context",
    "rule-context",
    "rule context",
    "rulecontext",
    "rule_engine",
    "rule-engine",
    "rule engine",
    "rule_id",
    "rule id",
    "statefulopalverifier",
    "verifier_trace",
    "verifier trace",
    "rule_trace",
    "rule trace",
    "rule_output",
    "rule output",
    "rule_result",
    "rule result",
)
SOLVER_PATTERNS = (
    "src.solver",
    "src/solver",
    "src\\solver",
    "solver.py",
    "solver import",
    "solver_import",
    "solver-import",
    "solverimport",
    "solver module",
    "solver_module",
    "solver-module",
    "solvermodule",
    "import solver",
    "from solver import",
    "from src.solver import",
)
POLICY_PATTERNS = PUBLIC_HOLDOUT_PATTERNS + RULE_CONTEXT_PATTERNS + SOLVER_PATTERNS


# Changed: keep only manifest fields required by evaluation.
# Why: gold labels must come only from row label, and model prompts must be exactly row input.
@dataclass(frozen=True)
class ManifestRow:
    line_number: int
    sample_id: str
    input_text: str
    label: str
    split: str
    source: str


# Changed: store the first-token logit and token ID instead of completion totals.
# Why: pass/fail scoring now compares only the prompt's next-token logits.
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


# Changed: expose all requested CLI controls, including repeated or comma-separated splits.
# Why: the script must be runnable for calibration, hidden, or both without changing code.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a PEFT LoRA adapter using only a Data Contract v2 manifest JSONL."
    )
    parser.add_argument("--manifest", required=True, help="Path to Data Contract v2 manifest JSONL.")
    parser.add_argument("--base-model", required=True, help="Base model name or path for AutoModelForCausalLM.")
    parser.add_argument("--adapter-path", required=True, help="PEFT LoRA adapter path.")
    parser.add_argument(
        "--split",
        action="append",
        required=True,
        help="Evaluation split: calibration or hidden. May be repeated or comma-separated.",
    )
    parser.add_argument("--threshold", type=float, default=0.5, help="Predict fail when p_fail >= threshold.")
    parser.add_argument("--max-seq-len", type=int, default=2048, help="Maximum tokenized sequence length.")
    parser.add_argument("--batch-size", type=int, default=1, help="Evaluation batch size.")
    parser.add_argument("--output-json", required=True, help="Output JSON report path.")
    parser.add_argument("--output-md", required=True, help="Output Korean Markdown report path.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum rows to evaluate after split filtering.")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest gates, split, and counts without model load.")
    return parser.parse_args()


def parse_splits(values: Sequence[str]) -> list[str]:
    splits: list[str] = []
    for value in values:
        for part in value.split(","):
            split = part.strip().lower()
            if not split:
                continue
            if split not in VALID_EVAL_SPLITS:
                fail(f"Unsupported split {split!r}; expected one of {sorted(VALID_EVAL_SPLITS)}")
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


# Changed: scan raw manifest rows for public/eval/holdout/leaderboard/rule-context/solver signals.
# Why: the evaluator must stop before any contaminated row can become a prompt or gold label.
def scan_text_forms(value: Any) -> tuple[str, str, str, set[str]]:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    lowered = text.lower()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    return lowered, spaced, compact, set(spaced.split())


def match_pattern(value: Any, patterns: Sequence[str]) -> Optional[str]:
    text, spaced, compact, tokens = scan_text_forms(value)
    if FORBIDDEN_DATASET_PATH in text:
        return FORBIDDEN_DATASET_PATH
    for pattern in patterns:
        lowered = pattern.lower()
        pattern_spaced = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        pattern_compact = re.sub(r"[^a-z0-9]+", "", lowered)
        if not pattern_spaced:
            continue
        if " " not in pattern_spaced:
            if pattern_spaced in tokens or pattern_compact == compact:
                return pattern
            # Changed: allow compact substring matches only for longer markers.
            # Why: camelCase/suffix evasions should be caught without making short tokens like "eval" overbroad.
            if (
                len(pattern_compact) >= MIN_COMPACT_SUBSTRING_PATTERN_LEN
                and pattern_compact in compact
            ):
                return pattern
            continue
        if lowered in text or pattern_spaced in spaced or pattern_compact in compact:
            return pattern
    return None


def row_policy_violation(row: dict[str, Any]) -> Optional[str]:
    key_match = match_pattern(list(row.keys()), POLICY_PATTERNS)
    if key_match:
        return f"forbidden marker in row keys: {key_match}"
    for key, value in row.items():
        value_match = match_pattern(value, POLICY_PATTERNS)
        if value_match:
            return f"forbidden marker in field {key!r}: {value_match}"
    return None


def ensure_manifest_path_allowed(path: Path) -> None:
    # Changed: check provided and resolved path forms before reading the manifest.
    # Why: symlinks or relative paths must not bypass the forbidden dataset path gate.
    path_forms = [("provided", str(path)), ("resolved_non_strict", str(path.resolve(strict=False)))]
    if path.exists():
        try:
            path_forms.append(("resolved_strict", str(path.resolve(strict=True))))
        except OSError as exc:
            fail(f"Unable to resolve existing manifest path strictly: {path} ({exc})")
    forbidden = FORBIDDEN_DATASET_PATH.lower()
    for source, path_text in path_forms:
        if forbidden in path_text.lower():
            fail(
                "Manifest path references forbidden dataset path "
                f"via {source}: {FORBIDDEN_DATASET_PATH}"
            )


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                fail(f"Invalid JSONL at line {line_number}: {exc}")
            if not isinstance(value, dict):
                fail(f"Manifest line {line_number} is not a JSON object")
            yield line_number, value


def normalize_label(value: Any, line_number: int) -> str:
    if not isinstance(value, str):
        fail(f"Manifest line {line_number} has non-string label")
    label = value.strip().lower()
    if label not in VALID_LABELS:
        fail(f"Manifest line {line_number} has unsupported label: {value!r}")
    return label


def normalize_split(value: Any, line_number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"Manifest line {line_number} is missing non-empty string field 'split'")
    return value.strip().lower()


def load_manifest(path: Path) -> tuple[list[ManifestRow], dict[str, Any]]:
    ensure_manifest_path_allowed(path)
    if not path.exists():
        fail(f"Manifest not found: {path}")
    if not path.is_file():
        fail(f"Manifest path is not a file: {path}")

    rows: list[ManifestRow] = []
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for line_number, raw in read_jsonl(path):
        violation = row_policy_violation(raw)
        if violation:
            fail(f"Manifest line {line_number} violates LLM-only data policy: {violation}")

        input_text = raw.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            fail(f"Manifest line {line_number} is missing non-empty string field 'input'")
        label = normalize_label(raw.get("label"), line_number)
        split = normalize_split(raw.get("split"), line_number)
        sample_id = str(raw.get("sample_id", f"line-{line_number}"))
        source_value = raw.get("source", "unknown")
        source = source_value if isinstance(source_value, str) and source_value else "unknown"

        split_counts[split] += 1
        label_counts[label] += 1
        source_counts[source] += 1
        rows.append(
            ManifestRow(
                line_number=line_number,
                sample_id=sample_id,
                input_text=input_text,
                label=label,
                split=split,
                source=source,
            )
        )

    if not rows:
        fail("Manifest has no rows")

    summary = {
        "manifest_path": str(path),
        "total_rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "source_counts_top20": dict(source_counts.most_common(20)),
    }
    return rows, summary


def select_rows(rows: Sequence[ManifestRow], selected_splits: Sequence[str], limit: Optional[int]) -> list[ManifestRow]:
    selected = [row for row in rows if row.split in selected_splits]
    if not selected:
        fail(f"No rows found for requested split(s): {', '.join(selected_splits)}")
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        fail("No rows selected after applying --limit")
    return selected


# Changed: mirror train_manifest_lora.py prompt construction.
# Why: adapter evaluation must use user=input exactly and assistant answer equal to pass/fail.
def build_messages(input_text: str, answer: Optional[str] = None) -> list[dict[str, str]]:
    messages = [{"role": "user", "content": input_text}]
    if answer is not None:
        messages.append({"role": "assistant", "content": answer})
    return messages


def apply_chat_template(tokenizer: Any, messages: Sequence[dict[str, str]], answer_included: bool) -> str:
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


def ensure_list_of_token_lists(value: Any) -> list[list[int]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and (not value or isinstance(value[0], int)):
        return [[int(item) for item in value]]
    if isinstance(value, list):
        return [[int(item) for item in items] for items in value]
    fail("Tokenizer returned an unsupported input_ids structure")
    return []


# Changed: load model dependencies lazily for prompt-only next-token scoring.
# Why: dry-run must not require model packages, while full eval must use the same base+adapter stack as inference.
def import_runtime_dependencies() -> tuple[Any, Any, Any, Any]:
    try:
        import torch
    except ImportError as exc:
        fail(f"Missing dependency 'torch'. Install torch to run adapter evaluation. Import error: {exc}")
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        fail(f"Missing dependency 'transformers'. Install transformers to load the base model. Import error: {exc}")
    try:
        from peft import PeftModel
    except ImportError as exc:
        fail(f"Missing dependency 'peft'. Install peft to load the LoRA adapter. Import error: {exc}")
    return torch, AutoTokenizer, AutoModelForCausalLM, PeftModel


def choose_dtype(torch: Any) -> tuple[Any, str]:
    if torch.cuda.is_available():
        if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
            return torch.bfloat16, "bfloat16"
        return torch.float16, "float16"
    return torch.float32, "float32"


def load_tokenizer(auto_tokenizer: Any, base_model: str) -> Any:
    tokenizer = auto_tokenizer.from_pretrained(base_model, trust_remote_code=True)
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


def load_model_bundle(base_model: str, adapter_path: str) -> ModelBundle:
    torch, auto_tokenizer, auto_model, peft_model = import_runtime_dependencies()
    tokenizer = load_tokenizer(auto_tokenizer, base_model)
    dtype, dtype_name = choose_dtype(torch)

    load_mode = "device_map_auto"
    auto_error: Optional[str] = None
    model_kwargs = {"trust_remote_code": True, "torch_dtype": dtype}
    try:
        base = auto_model.from_pretrained(base_model, device_map="auto", **model_kwargs)
    except Exception as exc:
        auto_error = str(exc)
        load_mode = "single_device_fallback"
        base = auto_model.from_pretrained(base_model, **model_kwargs)
        if torch.cuda.is_available():
            base = base.to("cuda")

    model = peft_model.from_pretrained(base, adapter_path)
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


def batched(rows: Sequence[ManifestRow], batch_size: int) -> Iterable[list[ManifestRow]]:
    for start in range(0, len(rows), batch_size):
        yield list(rows[start : start + batch_size])


# Changed: derive the exact candidate token IDs used for next-token comparison.
# Why: reports must show which pass/fail first-token IDs were scored.
def candidate_label_token_ids(tokenizer: Any, label: str) -> list[int]:
    try:
        encoded = tokenizer(label, add_special_tokens=False)
    except TypeError:
        encoded = tokenizer(label)
    input_ids = (
        encoded.get("input_ids")
        if isinstance(encoded, dict)
        else getattr(encoded, "input_ids", None)
    )
    if input_ids is None:
        fail(f"Tokenizer did not return input_ids for label {label!r}")
    token_ids = ensure_list_of_token_lists(input_ids)[0]
    if not token_ids:
        fail(f"Tokenizer returned no tokens for label {label!r}")
    return token_ids


# Changed: keep pass/fail token metadata in a stable report shape.
# Why: first-token scoring is only auditable when the compared token IDs are persisted.
def build_label_token_report(tokenizer: Any) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for label in ("pass", "fail"):
        token_ids = candidate_label_token_ids(tokenizer, label)
        report[label] = {
            "token_ids": token_ids,
            "first_token_id": token_ids[0],
        }
    if report["pass"]["first_token_id"] == report["fail"]["first_token_id"]:
        fail("Tokenizer maps pass/fail to the same first token ID; cannot compare next-token logits")
    return report


# Changed: score pass/fail by reading prompt-only next-token logits.
# Why: candidate decisions must compare the first generated token, not summed full-completion probabilities.
def score_next_token_batch(
    bundle: ModelBundle,
    rows: Sequence[ManifestRow],
    label_token_report: dict[str, dict[str, Any]],
    max_seq_len: int,
) -> list[dict[str, CandidateScore]]:
    tokenizer = bundle.tokenizer
    torch = bundle.torch
    prompt_texts = [
        apply_chat_template(tokenizer, build_messages(row.input_text), answer_included=False)
        for row in rows
    ]
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
            fail(f"Manifest line {row.line_number} produced an empty prompt after tokenization")
        next_token_position = sequence_width - 1 if padding_side == "left" else seq_len - 1
        next_token_logits = logits[index, next_token_position, :]
        scores.append(
            {
                "pass": CandidateScore(
                    logit=float(next_token_logits[pass_token_id].item()),
                    token_id=pass_token_id,
                ),
                "fail": CandidateScore(
                    logit=float(next_token_logits[fail_token_id].item()),
                    token_id=fail_token_id,
                ),
            }
        )
    return scores


# Changed: normalize two candidate scores into a fail probability.
# Why: logits from different rows can be large, so the binary softmax must stay numerically stable.
def stable_fail_probability(pass_score: float, fail_score: float) -> float:
    max_score = max(pass_score, fail_score)
    pass_weight = math.exp(pass_score - max_score)
    fail_weight = math.exp(fail_score - max_score)
    return fail_weight / (pass_weight + fail_weight)


# Changed: emit prediction rows with next-token logits and token IDs.
# Why: full reports must make the first-token pass/fail decision auditable per row.
def evaluate_rows(
    rows: Sequence[ManifestRow],
    bundle: ModelBundle,
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
            p_fail = stable_fail_probability(pass_score.logit, fail_score.logit)
            prediction = "fail" if p_fail >= threshold else "pass"
            predictions.append(
                {
                    "line_number": row.line_number,
                    "sample_id": row.sample_id,
                    "split": row.split,
                    "gold": row.label,
                    "prediction": prediction,
                    "correct": prediction == row.label,
                    "p_fail": p_fail,
                    "logit_pass_first_token": pass_score.logit,
                    "logit_fail_first_token": fail_score.logit,
                    "pass_first_token_id": pass_score.token_id,
                    "fail_first_token_id": fail_score.token_id,
                }
            )
    return predictions


# Changed: compute fail-class metrics by split and overall from prediction rows only.
# Why: reports must be auditable without consulting any external labels or leaderboard results.
def compute_metric_block(predictions: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    tp = sum(1 for item in predictions if item["gold"] == "fail" and item["prediction"] == "fail")
    tn = sum(1 for item in predictions if item["gold"] == "pass" and item["prediction"] == "pass")
    fp = sum(1 for item in predictions if item["gold"] == "pass" and item["prediction"] == "fail")
    fn = sum(1 for item in predictions if item["gold"] == "fail" and item["prediction"] == "pass")
    n = len(predictions)
    # Changed: represent undefined fail-class metrics as None.
    # Why: zero predicted positives or zero gold positives should render as JSON null and Markdown N/A.
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    p_fail_by_gold: dict[str, list[float]] = defaultdict(list)
    for item in predictions:
        p_fail_by_gold[item["gold"]].append(float(item["p_fail"]))

    def mean_or_none(values: Sequence[float]) -> Optional[float]:
        return sum(values) / len(values) if values else None

    return {
        "n": n,
        "threshold": threshold,
        "accuracy": (tp + tn) / n if n else 0.0,
        "precision_fail": precision,
        "recall_fail": recall,
        "f1_fail": f1,
        "confusion_matrix": {
            "TP": tp,
            "TN": tn,
            "FP": fp,
            "FN": fn,
        },
        "mean_p_fail_by_gold": {
            "pass": mean_or_none(p_fail_by_gold["pass"]),
            "fail": mean_or_none(p_fail_by_gold["fail"]),
        },
    }


def compute_metrics(predictions: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    by_split: dict[str, Any] = {}
    split_names = sorted({str(item["split"]) for item in predictions})
    for split in split_names:
        split_predictions = [item for item in predictions if item["split"] == split]
        by_split[split] = compute_metric_block(split_predictions, threshold)
    return {
        "overall": compute_metric_block(predictions, threshold),
        "by_split": by_split,
    }


def selected_summary(rows: Sequence[ManifestRow], selected_before_limit: int) -> dict[str, Any]:
    split_counts: Counter[str] = Counter(row.split for row in rows)
    label_counts: Counter[str] = Counter(row.label for row in rows)
    return {
        "selected_rows_before_limit": selected_before_limit,
        "selected_rows_after_limit": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
    }


def base_report(
    args: argparse.Namespace,
    selected_splits: Sequence[str],
    manifest_summary: dict[str, Any],
    selection_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "created_at_kst": datetime.now(KST).isoformat(),
        "mode": "dry_run" if args.dry_run else "eval",
        "manifest": manifest_summary,
        "selection": selection_summary,
        "arguments": {
            "base_model": args.base_model,
            "adapter_path": args.adapter_path,
            "split": list(selected_splits),
            "threshold": args.threshold,
            "max_seq_len": args.max_seq_len,
            "batch_size": args.batch_size,
            "limit": args.limit,
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
            "prompt_field": "input",
            # Changed: name policy guarantees at this script's actual enforcement boundary.
            # Why: report wording must not overclaim repository-wide import behavior.
            "this_script_no_solver_direct_import": True,
            "this_script_no_stateful_verifier_direct_import": True,
            "manifest_gate_no_public_eval_holdout_or_leaderboard_markers": True,
            "manifest_gate_no_rule_context_markers": True,
            "manifest_gate_no_solver_markers": True,
            "forbidden_dataset_path": FORBIDDEN_DATASET_PATH,
        },
    }


# Changed: write both machine-readable JSON and Korean Markdown reports.
# Why: evaluation runs need reproducible artifacts and a human-readable KST summary.
def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_percent(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def format_float(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.6f}"


def metric_table_lines(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "| 구간 | n | Accuracy | Fail Precision | Fail Recall | Fail F1 | TP | TN | FP | FN | mean p_fail(pass) | mean p_fail(fail) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rows = [("overall", metrics["overall"])] + [
        (split, block) for split, block in sorted(metrics.get("by_split", {}).items())
    ]
    for name, block in rows:
        confusion = block["confusion_matrix"]
        means = block["mean_p_fail_by_gold"]
        lines.append(
            f"| {name} | {block['n']} | {format_percent(block['accuracy'])} | "
            f"{format_percent(block['precision_fail'])} | {format_percent(block['recall_fail'])} | "
            f"{format_percent(block['f1_fail'])} | {confusion['TP']} | {confusion['TN']} | "
            f"{confusion['FP']} | {confusion['FN']} | {format_float(means['pass'])} | "
            f"{format_float(means['fail'])} |"
        )
    return lines


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    args = report["arguments"]
    lines = [
        "# Data Contract v2 LoRA 어댑터 평가 리포트",
        "",
        f"- 생성 시각(KST): {report['created_at_kst']}",
        f"- mode: `{report['mode']}`",
        f"- manifest: `{report['manifest']['manifest_path']}`",
        f"- base model: `{args['base_model']}`",
        f"- adapter path: `{args['adapter_path']}`",
        f"- split: `{args['split']}`",
        f"- threshold: `{args['threshold']}`",
        f"- max seq len: `{args['max_seq_len']}`",
        f"- batch size: `{args['batch_size']}`",
        f"- limit: `{args['limit']}`",
        "",
        "## Manifest 검증",
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
                "## Dry Run 결과",
                "",
                "- 모델은 로드하지 않았다.",
                "- manifest gate, split 선택, row count 검증만 수행했다.",
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
                f"- device_map auto fallback error: `{model['auto_device_map_error']}`",
                f"- label token ids: `{model['label_token_ids']}`",
                "",
                "## Metric",
                "",
            ]
        )
        lines.extend(metric_table_lines(report["metrics"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Changed: keep orchestration local and side-effect scoped to requested reports.
# Why: the script must not touch any non-manifest data source or repo file outside explicit outputs.
def main() -> int:
    args = parse_args()
    selected_splits = validate_args(args)
    manifest_path = Path(args.manifest)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    rows, manifest_summary = load_manifest(manifest_path)
    selected_before_limit = sum(1 for row in rows if row.split in selected_splits)
    selected_rows = select_rows(rows, selected_splits, args.limit)
    selection = selected_summary(selected_rows, selected_before_limit)
    report = base_report(args, selected_splits, manifest_summary, selection)

    if args.dry_run:
        # Changed: keep dry-run JSON schema aligned with full evaluation reports.
        # Why: downstream consumers should not special-case missing metrics or predictions keys.
        report["model"] = None
        report["metrics"] = None
        report["predictions"] = []
        report["dry_run"] = {"model_loaded": False}
        write_json_report(output_json, report)
        write_markdown_report(output_md, report)
        return 0

    bundle = load_model_bundle(args.base_model, args.adapter_path)
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
    write_json_report(output_json, report)
    write_markdown_report(output_md, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
