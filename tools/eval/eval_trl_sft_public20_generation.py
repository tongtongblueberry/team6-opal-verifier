#!/usr/bin/env python3
"""Separate pass/fail generation metric adapter for TRL public20 SFT outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Changed: keep generation metrics separate from TRL trainer eval_loss.
# Why: eval_loss is official Trainer output, while pass/fail accuracy is a task adapter.
VALID_LABELS = {"pass", "fail"}
KST = timezone(timedelta(hours=9), name="KST")

# Changed: recognize PEFT adapter and tokenizer artifacts explicitly.
# Why: adapter-dir eval can be loaded directly, while --adapter-path must compose base model + LoRA adapter.
ADAPTER_CONFIG_FILE = "adapter_config.json"
TOKENIZER_MARKER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
)


@dataclass(frozen=True)
class EvalRow:
    sample_id: str
    prompt: str
    gold: str
    line_number: int


def fail(message: str, exit_code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate pass/fail labels from a TRL SFT model and score converted public20 JSONL."
    )
    parser.add_argument("--dataset-jsonl", required=True, help="Converted validation JSONL with prompt/completion.")
    parser.add_argument("--model-name-or-path", required=True, help="Model path/name for generation.")
    parser.add_argument("--adapter-path", default=None, help="Optional PEFT adapter path.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset only; no model load.")
    return parser.parse_args(argv)


def read_eval_rows(path: Path, limit: int | None = None) -> list[EvalRow]:
    if not path.exists():
        fail(f"Missing dataset JSONL: {path}")
    rows: list[EvalRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                fail(f"Invalid JSONL at {path}:{line_number}: {exc}")
            if not isinstance(value, dict):
                fail(f"Row {path}:{line_number} is not an object")
            prompt = value.get("prompt")
            completion = value.get("completion")
            sample_id = value.get("sample_id", f"line-{line_number}")
            if not isinstance(prompt, str) or not prompt:
                fail(f"Row {path}:{line_number} has missing prompt")
            if not isinstance(completion, str) or completion not in VALID_LABELS:
                fail(f"Row {path}:{line_number} has invalid completion {completion!r}")
            if not isinstance(sample_id, str):
                fail(f"Row {path}:{line_number} has non-string sample_id")
            rows.append(EvalRow(sample_id=sample_id, prompt=prompt, gold=completion, line_number=line_number))
            if limit is not None and len(rows) >= limit:
                break
    if not rows:
        fail(f"No rows selected from {path}")
    return rows


def normalize_generated_label(text: str) -> str | None:
    first_token = re.search(r"[A-Za-z]+", text.strip().lower())
    if first_token is None:
        return None
    value = first_token.group(0)
    if value in VALID_LABELS:
        return value
    return None


def compute_generation_metrics(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    confusion = {"TP": 0, "TN": 0, "FP": 0, "FN": 0, "INVALID": 0}
    for prediction in predictions:
        gold = prediction["gold"]
        predicted = prediction["prediction"]
        if predicted not in VALID_LABELS:
            confusion["INVALID"] += 1
        elif gold == "fail" and predicted == "fail":
            confusion["TP"] += 1
        elif gold == "pass" and predicted == "pass":
            confusion["TN"] += 1
        elif gold == "pass" and predicted == "fail":
            confusion["FP"] += 1
        elif gold == "fail" and predicted == "pass":
            confusion["FN"] += 1

    total = len(predictions)
    correct = confusion["TP"] + confusion["TN"]
    accuracy = correct / total if total else None

    def safe_div(numerator: float, denominator: float) -> float | None:
        if denominator == 0:
            return None
        return numerator / denominator

    # Changed: compute recall from all gold rows, including invalid generations.
    # Why: an invalid answer is still a missed pass/fail classification for the gold class.
    gold_fail = sum(1 for prediction in predictions if prediction["gold"] == "fail")
    gold_pass = sum(1 for prediction in predictions if prediction["gold"] == "pass")
    precision_fail = safe_div(confusion["TP"], confusion["TP"] + confusion["FP"])
    recall_fail = safe_div(confusion["TP"], gold_fail)
    precision_pass = safe_div(confusion["TN"], confusion["TN"] + confusion["FN"])
    recall_pass = safe_div(confusion["TN"], gold_pass)

    def f1(precision: float | None, recall: float | None) -> float | None:
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)

    f1_fail = f1(precision_fail, recall_fail)
    f1_pass = f1(precision_pass, recall_pass)
    macro_values = [value for value in (f1_fail, f1_pass) if value is not None]
    return {
        "n": total,
        "accuracy": accuracy,
        "confusion_matrix": confusion,
        "precision_fail": precision_fail,
        "recall_fail": recall_fail,
        "f1_fail": f1_fail,
        "precision_pass": precision_pass,
        "recall_pass": recall_pass,
        "f1_pass": f1_pass,
        "macro_f1": sum(macro_values) / len(macro_values) if macro_values else None,
    }


def is_local_adapter_dir(path_text: str) -> bool:
    path = Path(path_text).expanduser()
    return path.is_dir() and (path / ADAPTER_CONFIG_FILE).is_file()


# Changed: choose tokenizer source from the adapter when the adapter saved tokenizer files.
# Why: TRL/PEFT adapter directories may carry the tokenizer state used by direct adapter-dir loading.
def adapter_has_tokenizer(path_text: str) -> bool:
    path = Path(path_text).expanduser()
    return path.is_dir() and any((path / filename).is_file() for filename in TOKENIZER_MARKER_FILES)


def tokenizer_source_for(model_name_or_path: str, adapter_path: str | None) -> str:
    if adapter_path and adapter_has_tokenizer(adapter_path):
        return adapter_path
    return model_name_or_path


# Changed: reject local double-adapter CLI usage before model loading.
# Why: --adapter-path semantics require --model-name-or-path to identify the base model, not another adapter dir.
def validate_model_adapter_args(model_name_or_path: str, adapter_path: str | None) -> None:
    if not adapter_path:
        return
    adapter = Path(adapter_path).expanduser()
    if adapter.is_absolute() and not adapter.exists():
        fail(f"--adapter-path does not exist: {adapter_path}")
    if adapter.exists() and not (adapter / ADAPTER_CONFIG_FILE).is_file():
        fail(f"--adapter-path local directory must contain {ADAPTER_CONFIG_FILE}: {adapter_path}")
    if is_local_adapter_dir(model_name_or_path):
        fail(
            "--adapter-path expects --model-name-or-path to be the base model. "
            "For direct adapter-dir loading, omit --adapter-path and pass the adapter dir as --model-name-or-path."
        )


# Changed: prefer Transformers' PEFT adapter integration for adapter-path composition.
# Why: official Transformers loading uses base AutoModelForCausalLM plus load_adapter(), matching direct adapter-dir semantics.
def load_adapter_into_model(model: Any, adapter_path: str) -> Any:
    if hasattr(model, "load_adapter"):
        try:
            model.load_adapter(adapter_path)
        except ImportError as exc:
            fail(f"--adapter-path requires peft for Transformers adapter loading: {exc}", exit_code=3)
        if hasattr(model, "set_adapter"):
            model.set_adapter("default")
        return model

    try:
        from peft import PeftModel  # type: ignore
    except ImportError as exc:
        fail(f"--adapter-path requires peft: {exc}", exit_code=3)
    return PeftModel.from_pretrained(model, adapter_path)


def load_model_and_tokenizer(
    auto_tokenizer: Any,
    auto_model: Any,
    model_name_or_path: str,
    adapter_path: str | None,
) -> tuple[Any, Any]:
    validate_model_adapter_args(model_name_or_path, adapter_path)
    tokenizer = auto_tokenizer.from_pretrained(tokenizer_source_for(model_name_or_path, adapter_path))
    if tokenizer.pad_token_id is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token

    model = auto_model.from_pretrained(model_name_or_path)
    if adapter_path:
        model = load_adapter_into_model(model, adapter_path)
    model.eval()
    return tokenizer, model


def generate_predictions(args: argparse.Namespace, rows: list[EvalRow]) -> list[dict[str, Any]]:
    # Changed: defer heavyweight model imports until real generation.
    # Why: local tests and dry-runs must not download or load models.
    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except ImportError as exc:
        fail(f"Generation evaluation requires torch and transformers: {exc}", exit_code=3)

    tokenizer, model = load_model_and_tokenizer(
        AutoTokenizer,
        AutoModelForCausalLM,
        args.model_name_or_path,
        args.adapter_path,
    )

    predictions: list[dict[str, Any]] = []
    with torch.no_grad():
        for start in range(0, len(rows), args.batch_size):
            batch = rows[start : start + args.batch_size]
            prompts = [row.prompt for row in batch]
            encoded = tokenizer(prompts, return_tensors="pt", padding=True)
            encoded = {key: value.to(model.device) for key, value in encoded.items()}
            output_ids = model.generate(**encoded, max_new_tokens=args.max_new_tokens, do_sample=False)
            # Changed: slice generated tokens after the padded model input length.
            # Why: batched decoder-only generation appends new tokens after the full input tensor width.
            prompt_width = encoded["input_ids"].shape[1]
            for row, generated_ids in zip(batch, output_ids):
                new_tokens = generated_ids[int(prompt_width) :]
                generated_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
                predicted = normalize_generated_label(generated_text)
                predictions.append(
                    {
                        "sample_id": row.sample_id,
                        "gold": row.gold,
                        "prediction": predicted,
                        "raw_generation": generated_text,
                    }
                )
    return predictions


def write_reports(report: dict[str, Any], output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = report["metrics"]
    lines = [
        "# public20 TRL SFT pass/fail generation metric",
        "",
        "- trainer eval_loss와 분리된 task metric adapter 결과다.",
        f"- rows: `{metrics['n']}`",
        f"- accuracy: `{metrics['accuracy']}`",
        f"- macro_f1: `{metrics['macro_f1']}`",
        f"- confusion: `{metrics['confusion_matrix']}`",
        "",
    ]
    output_md.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.batch_size <= 0:
        fail("--batch-size must be positive")
    if args.max_new_tokens <= 0:
        fail("--max-new-tokens must be positive")
    if args.limit is not None and args.limit <= 0:
        fail("--limit must be positive when provided")

    rows = read_eval_rows(Path(args.dataset_jsonl), limit=args.limit)
    if args.dry_run:
        predictions = [
            {
                "sample_id": row.sample_id,
                "gold": row.gold,
                "prediction": None,
                "raw_generation": None,
            }
            for row in rows
        ]
    else:
        predictions = generate_predictions(args, rows)

    report = {
        "created_at": datetime.now(KST).isoformat(),
        "metric_adapter": "public20_trl_sft_generation",
        "official_trainer_eval_loss": False,
        "dry_run": bool(args.dry_run),
        "model_name_or_path": args.model_name_or_path,
        "adapter_path": args.adapter_path,
        "metrics": compute_generation_metrics(predictions),
        "predictions": predictions,
    }
    write_reports(report, Path(args.output_json), Path(args.output_md))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
