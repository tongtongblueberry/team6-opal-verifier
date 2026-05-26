#!/usr/bin/env python3
"""Conditional pass/fail logprob evaluator for converted TRL public20 SFT rows."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


# Changed: make repo-root imports work when this file is executed as a script.
# Why: this evaluator must reuse the existing public20 generation loading helper without requiring package installation.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.eval import eval_trl_sft_public20_generation as generation_eval


# Changed: keep logprob evaluation separate from generation decoding.
# Why: this evaluator diagnoses whether the model assigns higher conditional likelihood to pass or fail.
VALID_LABELS = generation_eval.VALID_LABELS
CANDIDATE_LABELS = ("pass", "fail")
IGNORE_INDEX = -100
KST = generation_eval.KST


@dataclass(frozen=True)
class CandidateFeatures:
    sample_id: str
    gold: str
    candidate_label: str
    input_ids: list[int]
    labels: list[int]
    prompt_token_count: int
    candidate_token_count: int
    total_token_count: int


@dataclass(frozen=True)
class CandidateScore:
    nll: float
    sum_logprob: float
    mean_logprob: float
    token_count: int


def fail(message: str, exit_code: int = 2) -> None:
    generation_eval.fail(message, exit_code=exit_code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score pass/fail candidate completions by conditional log-likelihood for TRL public20 SFT rows."
    )
    parser.add_argument("--dataset-jsonl", required=True, help="Converted validation JSONL with prompt/completion.")
    parser.add_argument("--model-name-or-path", required=True, help="Full model path/name or direct adapter directory.")
    parser.add_argument("--adapter-path", default=None, help="Optional PEFT adapter path for base-model composition.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument(
        "--max-length",
        type=int,
        default=4096,
        help="Maximum prompt+candidate token length. Rows exceeding it fail instead of silently dropping labels.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset only; no model load.")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if args.batch_size <= 0:
        fail("--batch-size must be positive")
    if args.max_length <= 1:
        fail("--max-length must be greater than 1")
    if args.limit is not None and args.limit <= 0:
        fail("--limit must be positive when provided")


def ensure_token_list(value: Any, label: str) -> list[int]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and (not value or isinstance(value[0], int)):
        return [int(item) for item in value]
    if isinstance(value, list) and value and isinstance(value[0], list):
        if len(value) != 1:
            fail(f"Tokenizer returned batched input_ids for {label!r}; expected one row")
        return [int(item) for item in value[0]]
    fail(f"Tokenizer returned input_ids for {label!r} in an unsupported shape")


def extract_input_ids(encoded: Any, label: str) -> list[int]:
    input_ids = encoded.get("input_ids") if isinstance(encoded, dict) else getattr(encoded, "input_ids", None)
    if input_ids is None:
        fail(f"Tokenizer did not return input_ids for {label!r}")
    return ensure_token_list(input_ids, label)


def extract_offsets(encoded: Any) -> list[tuple[int, int]] | None:
    offsets = encoded.get("offset_mapping") if isinstance(encoded, dict) else getattr(encoded, "offset_mapping", None)
    if offsets is None:
        return None
    if hasattr(offsets, "tolist"):
        offsets = offsets.tolist()
    if isinstance(offsets, list) and offsets and isinstance(offsets[0], list) and offsets[0] and isinstance(offsets[0][0], (list, tuple)):
        if len(offsets) != 1:
            fail("Tokenizer returned batched offset_mapping; expected one row")
        offsets = offsets[0]
    if not isinstance(offsets, list):
        fail("Tokenizer returned offset_mapping in an unsupported shape")
    result: list[tuple[int, int]] = []
    for item in offsets:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            fail("Tokenizer returned malformed offset_mapping entries")
        result.append((int(item[0]), int(item[1])))
    return result


def encode_text(tokenizer: Any, text: str, label: str) -> list[int]:
    try:
        encoded = tokenizer(text, add_special_tokens=False)
    except TypeError:
        encoded = tokenizer(text)
    return extract_input_ids(encoded, label)


def encode_text_with_offsets(tokenizer: Any, text: str, label: str) -> tuple[list[int], list[tuple[int, int]] | None]:
    try:
        encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    except (NotImplementedError, TypeError, ValueError):
        return encode_text(tokenizer, text, label), None
    return extract_input_ids(encoded, label), extract_offsets(encoded)


def labels_from_offsets(
    input_ids: Sequence[int],
    offsets: Sequence[tuple[int, int]],
    prompt: str,
    sample_id: str,
    candidate_label: str,
) -> tuple[list[int], int, int]:
    # Changed: prefer tokenizer offsets to identify completion tokens.
    # Why: prompt-only token length can be wrong if a tokenizer merges across the prompt/completion boundary.
    if len(input_ids) != len(offsets):
        fail(f"Tokenizer offset length mismatch for sample {sample_id!r}, candidate {candidate_label!r}")
    boundary = len(prompt)
    labels = [IGNORE_INDEX for _ in input_ids]
    prompt_token_count = 0
    candidate_token_count = 0
    for index, (start, end) in enumerate(offsets):
        if end <= start:
            continue
        if start < boundary < end:
            fail(
                f"Tokenizer produced a boundary-spanning token for sample {sample_id!r}, "
                f"candidate {candidate_label!r}; cannot isolate candidate completion loss"
            )
        if start >= boundary:
            labels[index] = int(input_ids[index])
            candidate_token_count += 1
        else:
            prompt_token_count += 1
    return labels, prompt_token_count, candidate_token_count


def labels_from_prompt_prefix(
    tokenizer: Any,
    prompt: str,
    input_ids: Sequence[int],
    sample_id: str,
    candidate_label: str,
) -> tuple[list[int], int, int]:
    # Changed: keep a strict fallback for tokenizers without offset mappings.
    # Why: the evaluator must still mask prompt tokens with -100 while rejecting ambiguous token boundaries.
    prompt_ids = encode_text(tokenizer, prompt, f"prompt:{sample_id}")
    if list(input_ids[: len(prompt_ids)]) != prompt_ids:
        fail(
            f"Tokenizer did not preserve prompt token prefix for sample {sample_id!r}, candidate {candidate_label!r}; "
            "use a tokenizer with offset mappings or a prompt suffix that prevents boundary merges"
        )
    labels = [IGNORE_INDEX for _ in input_ids]
    for index in range(len(prompt_ids), len(input_ids)):
        labels[index] = int(input_ids[index])
    return labels, len(prompt_ids), len(input_ids) - len(prompt_ids)


def build_candidate_features(
    tokenizer: Any,
    row: generation_eval.EvalRow,
    candidate_label: str,
    max_length: int,
) -> CandidateFeatures:
    if candidate_label not in VALID_LABELS:
        fail(f"Unsupported candidate label {candidate_label!r}")
    full_text = f"{row.prompt}{candidate_label}"
    input_ids, offsets = encode_text_with_offsets(tokenizer, full_text, f"{row.sample_id}:{candidate_label}")
    if offsets is not None:
        labels, prompt_token_count, candidate_token_count = labels_from_offsets(
            input_ids,
            offsets,
            row.prompt,
            row.sample_id,
            candidate_label,
        )
    else:
        labels, prompt_token_count, candidate_token_count = labels_from_prompt_prefix(
            tokenizer,
            row.prompt,
            input_ids,
            row.sample_id,
            candidate_label,
        )
    if len(input_ids) > max_length:
        fail(
            f"Sample {row.sample_id!r}, candidate {candidate_label!r} has {len(input_ids)} tokens, "
            f"exceeding --max-length {max_length}"
        )
    if prompt_token_count <= 0:
        fail(f"Sample {row.sample_id!r} produced an empty prompt token span")
    if candidate_token_count <= 0:
        fail(f"Sample {row.sample_id!r}, candidate {candidate_label!r} produced no candidate tokens")
    return CandidateFeatures(
        sample_id=row.sample_id,
        gold=row.gold,
        candidate_label=candidate_label,
        input_ids=[int(item) for item in input_ids],
        labels=labels,
        prompt_token_count=prompt_token_count,
        candidate_token_count=candidate_token_count,
        total_token_count=len(input_ids),
    )


def pad_candidate_features(
    features: Sequence[CandidateFeatures],
    pad_token_id: int,
    padding_side: str,
) -> dict[str, list[list[int]]]:
    # Changed: pad input_ids while keeping prompt and pad labels ignored.
    # Why: labels must match Transformers CausalLM loss semantics with -100 ignored positions.
    if not features:
        fail("No candidate features to pad")
    max_width = max(len(feature.input_ids) for feature in features)
    input_rows: list[list[int]] = []
    attention_rows: list[list[int]] = []
    label_rows: list[list[int]] = []
    for feature in features:
        pad_width = max_width - len(feature.input_ids)
        attention = [1 for _ in feature.input_ids]
        if padding_side == "left":
            input_rows.append([pad_token_id] * pad_width + feature.input_ids)
            attention_rows.append([0] * pad_width + attention)
            label_rows.append([IGNORE_INDEX] * pad_width + feature.labels)
        else:
            input_rows.append(feature.input_ids + [pad_token_id] * pad_width)
            attention_rows.append(attention + [0] * pad_width)
            label_rows.append(feature.labels + [IGNORE_INDEX] * pad_width)
    return {"input_ids": input_rows, "attention_mask": attention_rows, "labels": label_rows}


def candidate_score_from_sum(sum_logprob: float, token_count: int) -> CandidateScore:
    if token_count <= 0:
        fail("Candidate token_count must be positive")
    return CandidateScore(
        nll=-sum_logprob,
        sum_logprob=sum_logprob,
        mean_logprob=sum_logprob / token_count,
        token_count=token_count,
    )


def batched(rows: Sequence[generation_eval.EvalRow], batch_size: int) -> Iterable[list[generation_eval.EvalRow]]:
    for start in range(0, len(rows), batch_size):
        yield list(rows[start : start + batch_size])


def first_model_device(model: Any) -> Any:
    try:
        return model.device
    except AttributeError:
        pass
    try:
        return next(model.parameters()).device
    except (AttributeError, StopIteration):
        return None


def score_candidate_batch(
    torch: Any,
    model: Any,
    tokenizer: Any,
    features: Sequence[CandidateFeatures],
) -> list[CandidateScore]:
    pad_token_id = getattr(tokenizer, "pad_token_id", None)
    if pad_token_id is None:
        fail("Tokenizer has no pad_token_id for batched logprob evaluation")
    padding_side = getattr(tokenizer, "padding_side", "right")
    padded = pad_candidate_features(features, int(pad_token_id), padding_side)
    device = first_model_device(model)

    input_ids = torch.tensor(padded["input_ids"], dtype=torch.long)
    attention_mask = torch.tensor(padded["attention_mask"], dtype=torch.long)
    labels = torch.tensor(padded["labels"], dtype=torch.long)
    if device is not None:
        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)
        labels = labels.to(device)

    with torch.inference_mode():
        # Changed: call the CausalLM with labels containing -100 prompt/pad masks.
        # Why: the scorer must align with Transformers' next-token loss/ignore_index contract.
        outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        logits = outputs.logits

    shift_logits = logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    mask = shift_labels.ne(IGNORE_INDEX)
    safe_labels = shift_labels.masked_fill(~mask, 0)
    log_probs = torch.nn.functional.log_softmax(shift_logits, dim=-1)
    token_logprobs = log_probs.gather(dim=-1, index=safe_labels.unsqueeze(-1)).squeeze(-1)
    token_logprobs = token_logprobs.masked_fill(~mask, 0.0)
    sum_logprobs = token_logprobs.sum(dim=1).detach().cpu().tolist()
    token_counts = mask.sum(dim=1).detach().cpu().tolist()

    scores: list[CandidateScore] = []
    for feature, sum_logprob, token_count in zip(features, sum_logprobs, token_counts):
        count = int(token_count)
        if count != feature.candidate_token_count:
            fail(
                f"Candidate token count mismatch for sample {feature.sample_id!r}, "
                f"candidate {feature.candidate_label!r}: labels={feature.candidate_token_count}, shifted={count}"
            )
        scores.append(candidate_score_from_sum(float(sum_logprob), count))
    return scores


def prediction_from_candidate_scores(scores: dict[str, CandidateScore]) -> str:
    # Changed: compare length-normalized candidate likelihoods.
    # Why: pass/fail can tokenize to different lengths, so mean logprob is the fair decision statistic.
    if scores["fail"].mean_logprob > scores["pass"].mean_logprob:
        return "fail"
    return "pass"


def evaluate_rows(
    rows: Sequence[generation_eval.EvalRow],
    tokenizer: Any,
    model: Any,
    torch: Any,
    batch_size: int,
    max_length: int,
) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for batch_rows in batched(rows, batch_size):
        features = [
            build_candidate_features(tokenizer, row, candidate_label, max_length)
            for row in batch_rows
            for candidate_label in CANDIDATE_LABELS
        ]
        scores = score_candidate_batch(torch, model, tokenizer, features)
        grouped: dict[str, dict[str, CandidateScore]] = {row.sample_id: {} for row in batch_rows}
        feature_by_key = {(feature.sample_id, feature.candidate_label): feature for feature in features}
        for feature, score in zip(features, scores):
            grouped[feature.sample_id][feature.candidate_label] = score
        for row in batch_rows:
            candidate_scores = grouped[row.sample_id]
            prediction = prediction_from_candidate_scores(candidate_scores)
            pass_score = candidate_scores["pass"]
            fail_score = candidate_scores["fail"]
            predictions.append(
                {
                    "line_number": row.line_number,
                    "sample_id": row.sample_id,
                    "gold": row.gold,
                    "prediction": prediction,
                    "correct": prediction == row.gold,
                    "scores": {
                        label: {
                            "nll": candidate_scores[label].nll,
                            "sum_logprob": candidate_scores[label].sum_logprob,
                            "mean_logprob": candidate_scores[label].mean_logprob,
                            "token_count": candidate_scores[label].token_count,
                            "prompt_token_count": feature_by_key[(row.sample_id, label)].prompt_token_count,
                            "total_token_count": feature_by_key[(row.sample_id, label)].total_token_count,
                        }
                        for label in CANDIDATE_LABELS
                    },
                    "mean_logprob_margin_fail_minus_pass": fail_score.mean_logprob - pass_score.mean_logprob,
                    "sum_logprob_margin_fail_minus_pass": fail_score.sum_logprob - pass_score.sum_logprob,
                }
            )
    return predictions


def import_runtime_dependencies() -> tuple[Any, Any, Any]:
    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except ImportError as exc:
        fail(f"Logprob evaluation requires torch and transformers: {exc}", exit_code=3)
    return torch, AutoTokenizer, AutoModelForCausalLM


def load_logprob_model_and_tokenizer(
    auto_tokenizer: Any,
    auto_model: Any,
    model_name_or_path: str,
    adapter_path: str | None,
) -> tuple[Any, Any]:
    # Changed: route all model loading through the generation evaluator helper.
    # Why: full-model and direct/explicit LoRA adapter semantics must stay identical across public20 evaluators.
    return generation_eval.load_model_and_tokenizer(
        auto_tokenizer,
        auto_model,
        model_name_or_path,
        adapter_path,
    )


def generate_logprob_predictions(args: argparse.Namespace, rows: Sequence[generation_eval.EvalRow]) -> list[dict[str, Any]]:
    torch, auto_tokenizer, auto_model = import_runtime_dependencies()
    tokenizer, model = load_logprob_model_and_tokenizer(
        auto_tokenizer,
        auto_model,
        args.model_name_or_path,
        args.adapter_path,
    )
    return evaluate_rows(rows, tokenizer, model, torch, args.batch_size, args.max_length)


def write_reports(report: dict[str, Any], output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = report["metrics"]
    lines = [
        "# public20 TRL SFT pass/fail logprob evaluator",
        "",
        "- trainer eval_loss와 generation decoding metric을 분리한 task metric adapter 결과다.",
        "- prompt/pad token은 `labels=-100`으로 제외하고 candidate completion token만 scoring한다.",
        "- prediction 기준: `pass`/`fail` candidate mean logprob 비교.",
        f"- rows: `{metrics['n']}`",
        f"- accuracy: `{metrics['accuracy']}`",
        f"- macro_f1: `{metrics['macro_f1']}`",
        f"- confusion: `{metrics['confusion_matrix']}`",
        "",
    ]
    output_md.write_text("\n".join(lines), encoding="utf-8")


def build_report(
    args: argparse.Namespace,
    rows: Sequence[generation_eval.EvalRow],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(KST).isoformat(),
        "metric_adapter": "public20_trl_sft_logprob",
        "official_trainer_eval_loss": False,
        "dry_run": bool(args.dry_run),
        "model_name_or_path": args.model_name_or_path,
        "adapter_path": args.adapter_path,
        "scoring": {
            "candidate_labels": list(CANDIDATE_LABELS),
            "candidate_text": "raw label string without generated decoding",
            "prediction_basis": "higher candidate mean_logprob",
            "ignore_index": IGNORE_INDEX,
            "prompt_tokens_ignored": True,
            "pad_tokens_ignored": True,
            "transformers_causal_lm_labels_contract": True,
            "max_length": args.max_length,
        },
        "dataset": {
            "dataset_jsonl": args.dataset_jsonl,
            "selected_rows": len(rows),
            "limit": args.limit,
        },
        "metrics": generation_eval.compute_generation_metrics(predictions),
        "predictions": predictions,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    rows = generation_eval.read_eval_rows(Path(args.dataset_jsonl), limit=args.limit)
    if args.dry_run:
        predictions = [
            {
                "line_number": row.line_number,
                "sample_id": row.sample_id,
                "gold": row.gold,
                "prediction": None,
                "correct": None,
                "scores": None,
            }
            for row in rows
        ]
    else:
        predictions = generate_logprob_predictions(args, rows)
    report = build_report(args, rows, predictions)
    write_reports(report, Path(args.output_json), Path(args.output_md))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
