#!/usr/bin/env python3
"""Convert public20 train/val splits to input/labels SFT JSONL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


# Changed: define a public20-shaped persisted data contract independent of custom trainers.
# Why: JSONL artifacts should expose only input/labels while loaders adapt them for TRL in memory.
VALID_LABELS = {"pass", "fail"}
OUTPUT_COLUMNS = ("input", "labels")
DEFAULT_INPUT_TRAIN_NAME = "train.jsonl"
DEFAULT_INPUT_VAL_NAME = "val.jsonl"
DEFAULT_OUTPUT_TRAIN_NAME = "train.jsonl"
DEFAULT_OUTPUT_VALIDATION_NAME = "validation.jsonl"
DEFAULT_PROMPT_SUFFIX = "\n"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_RULES_PATH = ROOT / "docs" / "legacy_spec_rules.md"
DEFAULT_RETRIEVED_SPEC_MAX_CONTEXT_CHARS = 4096
KST = timezone(timedelta(hours=9), name="KST")


@dataclass(frozen=True)
class ConvertedSplitSummary:
    source_path: str
    output_path: str
    source_split: str
    output_split: str
    row_count: int
    label_counts: dict[str, int]
    retrieved_spec_context_enabled: bool = False
    retrieved_spec_context_char_min: int | None = None
    retrieved_spec_context_char_max: int | None = None


# Changed: represent docs/legacy_spec_rules.md sections as source-span cards for prompt augmentation.
# Why: retrieval-context SFT should add offline spec snippets to training inputs without adding a rule engine.
@dataclass(frozen=True)
class SpecRuleCard:
    rule_ref: str
    title: str
    category: str
    source_path: str
    source_start_line: int
    source_end_line: int
    source_span: str
    spec_section: str
    condition: str
    expected_status: str
    if_violated: str
    example_trajectory: str | None = None

    def search_text(self) -> str:
        return " ".join(
            part
            for part in (
                self.rule_ref,
                self.title,
                self.category,
                self.spec_section,
                self.condition,
                self.expected_status,
                self.if_violated,
                self.example_trajectory,
            )
            if part
        )

    def metadata(self, score: int, matched_terms: Sequence[str]) -> dict[str, Any]:
        return {
            "rule_ref": self.rule_ref,
            "title": self.title,
            "source_path": self.source_path,
            "source_span": self.source_span,
            "score": score,
            "matched_terms": list(matched_terms),
        }


def fail(message: str, exit_code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare public20 train/val splits as input/labels JSONL for TRL SFTTrainer."
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
        help="Suffix appended after the full trajectory input before the label.",
    )
    parser.add_argument(
        "--retrieved-spec-rules-md",
        default=None,
        help=(
            "Optional legacy spec rules markdown for input-only retrieval context. "
            "Defaults to docs/legacy_spec_rules.md when --retrieved-spec-top-k is positive."
        ),
    )
    parser.add_argument(
        "--retrieved-spec-top-k",
        type=int,
        default=0,
        help="Number of lexical spec snippets to append to each input. Zero disables retrieval context.",
    )
    parser.add_argument(
        "--retrieved-spec-max-context-chars",
        type=int,
        default=DEFAULT_RETRIEVED_SPEC_MAX_CONTEXT_CHARS,
        help="Maximum characters for the Retrieved spec context section in each input.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing converted files.")
    return parser.parse_args(argv)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


# Changed: parse rule-card fields and line ranges directly from markdown.
# Why: public20 retrieval augmentation needs source-span snippets, not runtime rule decisions.
def load_spec_rule_cards(path: Path) -> list[SpecRuleCard]:
    if not path.exists():
        fail(f"Missing spec rules markdown: {path}")
    if not path.is_file():
        fail(f"Spec rules path is not a file: {path}")

    source_path = display_path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    cards: list[SpecRuleCard] = []
    category = ""
    current: dict[str, Any] | None = None
    current_fields: dict[str, str] = {}
    last_content_line: int | None = None

    def flush(end_line: int | None) -> None:
        nonlocal current, current_fields, last_content_line
        if current is None:
            return
        required = ("SPEC", "CONDITION", "EXPECTED_STATUS", "IF_VIOLATED")
        missing = [field for field in required if field not in current_fields]
        if missing:
            fail(f"Spec rule {current.get('rule_ref')} missing field(s): {', '.join(missing)}")
        source_start_line = int(current["source_start_line"])
        source_end_line = int(end_line or source_start_line)
        cards.append(
            SpecRuleCard(
                rule_ref=str(current["rule_ref"]),
                title=str(current["title"]),
                category=str(current["category"]),
                source_path=source_path,
                source_start_line=source_start_line,
                source_end_line=source_end_line,
                source_span=f"{source_path}:{source_start_line}-{source_end_line}",
                spec_section=current_fields["SPEC"],
                condition=current_fields["CONDITION"],
                expected_status=current_fields["EXPECTED_STATUS"],
                if_violated=current_fields["IF_VIOLATED"],
                example_trajectory=current_fields.get("EXAMPLE_TRAJECTORY"),
            )
        )
        current = None
        current_fields = {}
        last_content_line = None

    for line_number, line in enumerate(lines, start=1):
        category_match = re.match(r"^##\s+(CATEGORY\s+\d+:.+)$", line)
        if category_match:
            category = category_match.group(1).strip()
            continue

        rule_match = re.match(r"^###\s+(RULE\s+\d+):\s*(.+)$", line)
        if rule_match:
            flush(last_content_line)
            current = {
                "rule_ref": rule_match.group(1).strip(),
                "title": rule_match.group(2).strip(),
                "category": category,
                "source_start_line": line_number,
            }
            last_content_line = line_number
            continue

        if current is None or not line.startswith("- "):
            continue
        key, separator, value = line[2:].partition(":")
        if not separator:
            continue
        current_fields[key.strip()] = value.strip()
        last_content_line = line_number

    flush(last_content_line)
    if not cards:
        fail(f"No rule cards parsed from spec rules markdown: {path}")
    return cards


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


def normalize_split(value: Any, path: Path, line_number: int, fallback: str | None = None) -> str:
    # Changed: allow file-name implied splits for two-column public20-shaped inputs.
    # Why: source JSONL rows may no longer carry a split metadata field.
    if value is None and fallback is not None:
        return fallback
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


def normalize_sample_id(value: Any, path: Path, line_number: int, fallback: str | None = None) -> str:
    # Changed: allow line-number fallback IDs for duplicate checks only.
    # Why: persisted rows should not need sample_id metadata.
    if value is None and fallback is not None:
        return fallback
    if not isinstance(value, str) or not value.strip():
        fail(f"Row {path}:{line_number} has missing sample_id")
    return value.strip()


# Changed: rank spec cards by lexical overlap with the trajectory input only.
# Why: the retrieval lane may expose relevant spec text but must not read labels or emit rule decisions.
def tokenize_for_retrieval(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_]+", text)
        if len(token) > 1
    ]


def retrieve_spec_context(
    input_text: str,
    cards: Sequence[SpecRuleCard],
    top_k: int,
) -> list[tuple[SpecRuleCard, int, list[str]]]:
    if top_k < 0:
        fail("--retrieved-spec-top-k must be non-negative")
    if top_k == 0:
        return []
    if not cards:
        fail("Retrieved spec context requested but no spec rule cards are available")

    query_counts = Counter(tokenize_for_retrieval(input_text))
    ranked: list[tuple[int, int, SpecRuleCard, list[str]]] = []
    for card in cards:
        card_terms = set(tokenize_for_retrieval(card.search_text()))
        matched_terms = sorted(term for term in query_counts if term in card_terms)
        score = sum(query_counts[term] for term in matched_terms)
        ranked.append((-score, card.source_start_line, card, matched_terms))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [(card, -negative_score, matched_terms) for negative_score, _, card, matched_terms in ranked[:top_k]]


def truncate_field(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    suffix = " [truncated]"
    if max_chars <= len(suffix):
        return value[:max_chars]
    return value[: max_chars - len(suffix)].rstrip() + suffix


def render_spec_card_snippet(card: SpecRuleCard, max_chars: int) -> str:
    lines = [
        f"- [{card.source_span}] {card.rule_ref}: {card.title}",
        f"  SPEC: {card.spec_section}",
        f"  CONDITION: {card.condition}",
        f"  EXPECTED_STATUS: {card.expected_status}",
        f"  IF_VIOLATED: {card.if_violated}",
    ]
    if card.example_trajectory:
        lines.append(f"  EXAMPLE_TRAJECTORY: {card.example_trajectory}")
    snippet = "\n".join(lines)
    if len(snippet) <= max_chars:
        return snippet

    compact_lines = [
        f"- [{card.source_span}] {card.rule_ref}: {card.title}",
        f"  SPEC: {card.spec_section}",
        f"  CONDITION: {card.condition}",
        f"  EXPECTED_STATUS: {card.expected_status}",
    ]
    compact = "\n".join(compact_lines)
    if len(compact) <= max_chars:
        return compact

    fixed_prefix = "\n".join(compact_lines[:2] + ["  CONDITION: "])
    fixed_suffix = f"\n  EXPECTED_STATUS: {card.expected_status}"
    condition_budget = max_chars - len(fixed_prefix) - len(fixed_suffix)
    if condition_budget <= 0:
        return truncate_field(compact_lines[0], max_chars)
    return fixed_prefix + truncate_field(card.condition, condition_budget) + fixed_suffix


def build_retrieved_spec_context_section(
    retrieved: Sequence[tuple[SpecRuleCard, int, list[str]]],
    max_context_chars: int,
) -> tuple[str, list[dict[str, Any]], bool]:
    if max_context_chars <= 0:
        fail("--retrieved-spec-max-context-chars must be positive")
    if not retrieved:
        return "", [], False

    header = "Retrieved spec context:"
    context = header
    metadata: list[dict[str, Any]] = []
    truncated = False
    for card, score, matched_terms in retrieved:
        separator = "\n" if context == header else "\n\n"
        remaining = max_context_chars - len(context) - len(separator)
        if remaining <= 0:
            truncated = True
            break
        snippet = render_spec_card_snippet(card, remaining)
        if len(snippet) > remaining:
            snippet = truncate_field(snippet, remaining)
            truncated = True
        context += separator + snippet
        metadata.append(card.metadata(score, matched_terms))
        if len(snippet) == remaining:
            truncated = True
            break

    if len(context) > max_context_chars:
        context = context[:max_context_chars]
        truncated = True
    return context, metadata, truncated


def append_retrieved_spec_context(
    input_text: str,
    cards: Sequence[SpecRuleCard],
    top_k: int,
    max_context_chars: int,
) -> tuple[str, list[dict[str, Any]], int, bool]:
    retrieved = retrieve_spec_context(input_text, cards, top_k)
    section, metadata, truncated = build_retrieved_spec_context_section(retrieved, max_context_chars)
    if not section:
        return input_text, [], 0, False
    separator = "\n\n" if not input_text.endswith("\n") else "\n"
    return f"{input_text}{separator}{section}", metadata, len(section), truncated


def convert_public20_row(
    row: dict[str, Any],
    path: Path,
    line_number: int,
    expected_source_split: str,
    prompt_suffix: str,
    spec_rule_cards: Sequence[SpecRuleCard] | None = None,
    retrieved_spec_top_k: int = 0,
    retrieved_spec_max_context_chars: int = DEFAULT_RETRIEVED_SPEC_MAX_CONTEXT_CHARS,
) -> dict[str, Any]:
    # Changed: keep only input and labels in the persisted row.
    # Why: TRL prompt/completion names and provenance stay out of the public20-shaped JSONL.
    input_text = normalize_input(row.get("input"), path, line_number)
    # Changed: accept labels from either source split form while writing only labels.
    # Why: old split inputs used label; corrected public20-shaped splits use labels.
    label = normalize_label(row.get("labels", row.get("label")), path, line_number)
    source_split = normalize_split(row.get("split"), path, line_number, fallback=expected_source_split)
    if source_split != expected_source_split:
        fail(
            f"Row {path}:{line_number} has split {source_split!r}; expected {expected_source_split!r}"
        )
    prompt_text = input_text
    retrieved_metadata: list[dict[str, Any]] = []
    retrieved_context_char_count = 0
    retrieved_context_truncated = False
    if retrieved_spec_top_k:
        prompt_text, retrieved_metadata, retrieved_context_char_count, retrieved_context_truncated = append_retrieved_spec_context(
            input_text,
            spec_rule_cards or [],
            retrieved_spec_top_k,
            retrieved_spec_max_context_chars,
        )
    del retrieved_metadata, retrieved_context_truncated
    return {
        "input": f"{prompt_text}{prompt_suffix}",
        "labels": label,
        "_retrieved_spec_context_char_count": retrieved_context_char_count,
    }


def convert_split_file(
    source_path: Path,
    output_path: Path,
    source_split: str,
    output_split: str,
    prompt_suffix: str,
    spec_rule_cards: Sequence[SpecRuleCard] | None = None,
    retrieved_spec_top_k: int = 0,
    retrieved_spec_max_context_chars: int = DEFAULT_RETRIEVED_SPEC_MAX_CONTEXT_CHARS,
) -> ConvertedSplitSummary:
    rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    seen_sample_ids: set[str] = set()
    retrieved_context_char_counts: list[int] = []

    for line_number, row in read_jsonl(source_path):
        # Changed: validate duplicate IDs from source only, then drop them from output rows.
        # Why: the written training JSONL must contain exactly input and labels.
        sample_id = normalize_sample_id(
            row.get("sample_id"),
            source_path,
            line_number,
            fallback=f"{source_split}:{line_number}",
        )
        converted = convert_public20_row(
            row,
            source_path,
            line_number,
            source_split,
            prompt_suffix,
            spec_rule_cards,
            retrieved_spec_top_k,
            retrieved_spec_max_context_chars,
        )
        if sample_id in seen_sample_ids:
            fail(f"Duplicate sample_id {sample_id!r} in {source_path}")
        seen_sample_ids.add(sample_id)
        label_counts[converted["labels"]] += 1
        if retrieved_spec_top_k:
            retrieved_context_char_counts.append(int(converted["_retrieved_spec_context_char_count"]))
        rows.append({key: converted[key] for key in OUTPUT_COLUMNS})

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
        retrieved_spec_context_enabled=bool(retrieved_spec_top_k),
        retrieved_spec_context_char_min=min(retrieved_context_char_counts) if retrieved_context_char_counts else None,
        retrieved_spec_context_char_max=max(retrieved_context_char_counts) if retrieved_context_char_counts else None,
    )


def build_report(
    split_dir: Path,
    output_dir: Path,
    summaries: list[ConvertedSplitSummary],
    prompt_suffix: str,
    retrieved_spec_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(KST).isoformat(),
        # Changed: report persisted and trainer-facing schemas separately.
        # Why: files stay public20-shaped; only the loader maps them for TRL.
        "adapter": "public20_trl_sft_input_labels",
        "training_core": "trl.SFTTrainer",
        "custom_training_loop": False,
        "dataset_format": "public20_input_labels",
        "completion_only_loss_intent": {
            "trl_sft_config": {"completion_only_loss": True},
            "reason": "loader maps input/labels to prompt/completion in memory so TRL can mask prompt tokens.",
        },
        "output_columns": list(OUTPUT_COLUMNS),
        "split_dir": str(split_dir),
        "output_dir": str(output_dir),
        "prompt_suffix": prompt_suffix,
        "retrieved_spec_context": retrieved_spec_report,
        "outputs": [summary.__dict__ for summary in summaries],
        "public20_test_split_created": False,
    }


def markdown_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# public20 TRL SFT 데이터셋 변환 리포트",
        "",
        "- 학습 core: `trl.SFTTrainer`",
        "- 데이터 형식: public20 input/labels JSONL",
        "- loss 의도: `SFTConfig(completion_only_loss=True)`",
        "- custom training loop 사용: `false`",
        "- public20 test split 생성: `false`",
        f"- retrieved spec context 사용: `{str(report['retrieved_spec_context']['enabled']).lower()}`",
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


def build_retrieval_inputs(args: argparse.Namespace) -> tuple[list[SpecRuleCard], dict[str, Any]]:
    if args.retrieved_spec_top_k < 0:
        fail("--retrieved-spec-top-k must be non-negative")
    if args.retrieved_spec_max_context_chars <= 0:
        fail("--retrieved-spec-max-context-chars must be positive")
    if args.retrieved_spec_top_k == 0:
        return [], {
            "enabled": False,
            "source_path": None,
            "top_k": 0,
            "max_context_chars": args.retrieved_spec_max_context_chars,
            "rule_card_count": 0,
            "label_used_for_retrieval": False,
            "runtime_rule_engine": False,
        }

    spec_rules_path = Path(args.retrieved_spec_rules_md) if args.retrieved_spec_rules_md else DEFAULT_SPEC_RULES_PATH
    cards = load_spec_rule_cards(spec_rules_path)
    return cards, {
        "enabled": True,
        "source_path": display_path(spec_rules_path),
        "top_k": args.retrieved_spec_top_k,
        "max_context_chars": args.retrieved_spec_max_context_chars,
        "rule_card_count": len(cards),
        "label_used_for_retrieval": False,
        "runtime_rule_engine": False,
        "retrieval_method": "deterministic lexical overlap over input text only",
    }


def convert_dataset(args: argparse.Namespace) -> dict[str, Any]:
    split_dir = Path(args.split_dir)
    output_dir = Path(args.output_dir)
    if not split_dir.exists() or not split_dir.is_dir():
        fail(f"--split-dir is not a directory: {split_dir}")
    spec_rule_cards, retrieved_spec_report = build_retrieval_inputs(args)

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
            spec_rule_cards,
            args.retrieved_spec_top_k,
            args.retrieved_spec_max_context_chars,
        ),
        convert_split_file(
            split_dir / args.input_val_name,
            validation_output,
            "val",
            "validation",
            args.prompt_suffix,
            spec_rule_cards,
            args.retrieved_spec_top_k,
            args.retrieved_spec_max_context_chars,
        ),
    ]
    report = build_report(split_dir, output_dir, summaries, args.prompt_suffix, retrieved_spec_report)
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
