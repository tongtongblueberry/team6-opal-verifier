#!/usr/bin/env python3
"""Convert public20 train/val splits to TRL prompt-completion SFT JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


# Changed: define a public20-to-TRL data contract independent of custom trainers.
# Why: TRL SFTTrainer should receive prompt/completion rows and own the loss path.
VALID_LABELS = {"pass", "fail"}
DEFAULT_INPUT_TRAIN_NAME = "train.jsonl"
DEFAULT_INPUT_VAL_NAME = "val.jsonl"
DEFAULT_OUTPUT_TRAIN_NAME = "train.jsonl"
DEFAULT_OUTPUT_VALIDATION_NAME = "validation.jsonl"
DEFAULT_PROMPT_SUFFIX = "\n"
KST = timezone(timedelta(hours=9), name="KST")


@dataclass(frozen=True)
class ConvertedSplitSummary:
    source_path: str
    output_path: str
    source_split: str
    output_split: str
    row_count: int
    label_counts: dict[str, int]


def fail(message: str, exit_code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare public20 train/val splits for TRL SFTTrainer prompt-completion SFT."
    )
    parser.add_argument(
        "--split-dir",
        required=True,
        help="Directory containing public20 split train.jsonl and val.jsonl.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for converted TRL JSONL files.")
    parser.add_argument("--input-train-name", default=DEFAULT_INPUT_TRAIN_NAME)
    parser.add_argument("--input-val-name", default=DEFAULT_INPUT_VAL_NAME)
    parser.add_argument("--output-train-name", default=DEFAULT_OUTPUT_TRAIN_NAME)
    parser.add_argument("--output-validation-name", default=DEFAULT_OUTPUT_VALIDATION_NAME)
    parser.add_argument(
        "--prompt-suffix",
        default=DEFAULT_PROMPT_SUFFIX,
        help="Suffix appended after the full trajectory prompt before the completion.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing converted files.")
    return parser.parse_args(argv)


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    if not path.exists():
        fail(f"Missing input JSONL: {path}")
    if not path.is_file():
        fail(f"Input path is not a file: {path}")
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
                fail(f"JSONL row at {path}:{line_number} is not an object")
            yield line_number, value


def normalize_label(value: Any, path: Path, line_number: int) -> str:
    if not isinstance(value, str):
        fail(f"Row {path}:{line_number} has non-string label")
    label = value.strip().lower()
    if label not in VALID_LABELS:
        fail(f"Row {path}:{line_number} has unsupported label {value!r}")
    return label


def normalize_split(value: Any, path: Path, line_number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"Row {path}:{line_number} has missing split")
    split = value.strip().lower()
    if split == "validation":
        split = "val"
    if split == "test":
        fail(f"Row {path}:{line_number} attempts to create a public20 test split")
    return split


def normalize_input(value: Any, path: Path, line_number: int) -> str:
    if not isinstance(value, str):
        fail(f"Row {path}:{line_number} has non-string input")
    if not value:
        fail(f"Row {path}:{line_number} has empty input")
    return value


def normalize_sample_id(value: Any, path: Path, line_number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"Row {path}:{line_number} has missing sample_id")
    return value.strip()


def convert_public20_row(
    row: dict[str, Any],
    path: Path,
    line_number: int,
    expected_source_split: str,
    prompt_suffix: str,
) -> dict[str, Any]:
    # Changed: keep the trajectory and answer in separate fields.
    # Why: TRL prompt-completion processing can mask prompt tokens for completion-only loss.
    input_text = normalize_input(row.get("input"), path, line_number)
    label = normalize_label(row.get("label"), path, line_number)
    sample_id = normalize_sample_id(row.get("sample_id"), path, line_number)
    source_split = normalize_split(row.get("split"), path, line_number)
    if source_split != expected_source_split:
        fail(
            f"Row {path}:{line_number} has split {source_split!r}; expected {expected_source_split!r}"
        )
    return {
        "prompt": f"{input_text}{prompt_suffix}",
        "completion": label,
        "sample_id": sample_id,
        "source_split": source_split,
        "source_line": line_number,
    }


def convert_split_file(
    source_path: Path,
    output_path: Path,
    source_split: str,
    output_split: str,
    prompt_suffix: str,
) -> ConvertedSplitSummary:
    rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    seen_sample_ids: set[str] = set()

    for line_number, row in read_jsonl(source_path):
        converted = convert_public20_row(row, source_path, line_number, source_split, prompt_suffix)
        sample_id = converted["sample_id"]
        if sample_id in seen_sample_ids:
            fail(f"Duplicate sample_id {sample_id!r} in {source_path}")
        seen_sample_ids.add(sample_id)
        label_counts[converted["completion"]] += 1
        rows.append(converted)

    if not rows:
        fail(f"No rows found in {source_path}")

    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    return ConvertedSplitSummary(
        source_path=str(source_path),
        output_path=str(output_path),
        source_split=source_split,
        output_split=output_split,
        row_count=len(rows),
        label_counts=dict(sorted(label_counts.items())),
    )


def build_report(
    split_dir: Path,
    output_dir: Path,
    summaries: list[ConvertedSplitSummary],
    prompt_suffix: str,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(KST).isoformat(),
        "adapter": "public20_trl_sft_prompt_completion",
        "training_core": "trl.SFTTrainer",
        "custom_training_loop": False,
        "dataset_format": "standard_prompt_completion",
        "completion_only_loss_intent": {
            "trl_sft_config": {"completion_only_loss": True},
            "reason": "prompt/completion columns let TRL mask prompt tokens and train on completion tokens.",
        },
        "split_dir": str(split_dir),
        "output_dir": str(output_dir),
        "prompt_suffix": prompt_suffix,
        "outputs": [summary.__dict__ for summary in summaries],
        "public20_test_split_created": False,
    }


def markdown_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# public20 TRL SFT 데이터셋 변환 리포트",
        "",
        "- 학습 core: `trl.SFTTrainer`",
        "- 데이터 형식: standard prompt-completion JSONL",
        "- loss 의도: `SFTConfig(completion_only_loss=True)`",
        "- custom training loop 사용: `false`",
        "- public20 test split 생성: `false`",
        "",
        "## Outputs",
        "",
        "| split | rows | pass | fail | path |",
        "|---|---:|---:|---:|---|",
    ]
    for output in report["outputs"]:
        labels = output["label_counts"]
        lines.append(
            "| {split} | {rows} | {pass_count} | {fail_count} | `{path}` |".format(
                split=output["output_split"],
                rows=output["row_count"],
                pass_count=labels.get("pass", 0),
                fail_count=labels.get("fail", 0),
                path=output["output_path"],
            )
        )
    lines.append("")
    return lines


def convert_dataset(args: argparse.Namespace) -> dict[str, Any]:
    split_dir = Path(args.split_dir)
    output_dir = Path(args.output_dir)
    if not split_dir.exists() or not split_dir.is_dir():
        fail(f"--split-dir is not a directory: {split_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    train_output = output_dir / args.output_train_name
    validation_output = output_dir / args.output_validation_name
    report_json = output_dir / "public20_trl_sft_dataset_report.json"
    report_md = output_dir / "public20_trl_sft_dataset_report.md"
    protected_outputs = [train_output, validation_output, report_json, report_md]
    if not args.overwrite:
        existing = [path for path in protected_outputs if path.exists()]
        if existing:
            fail(f"Refusing to overwrite existing output(s): {', '.join(str(path) for path in existing)}")

    summaries = [
        convert_split_file(
            split_dir / args.input_train_name,
            train_output,
            "train",
            "train",
            args.prompt_suffix,
        ),
        convert_split_file(
            split_dir / args.input_val_name,
            validation_output,
            "val",
            "validation",
            args.prompt_suffix,
        ),
    ]
    report = build_report(split_dir, output_dir, summaries, args.prompt_suffix)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_md.write_text("\n".join(markdown_report_lines(report)), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = convert_dataset(args)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
