# Changed: add public20-only train/val split builder for model validation.
# Why: public20 may be used for local model training validation, but must not create a test split or feed synthetic generation.
"""Build deterministic public20 train/val splits for model validation.

This tool is limited to public20-only model validation artifacts. Public20
labels are local evaluation references here, not Self-Instruct generation
inputs, synthetic judge labels, or generated synthetic manifest targets.
The hidden leaderboard remains the test set.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


Json = Dict[str, Any]
SPLIT_SCHEMA_VERSION = "public20_train_val_split.v1"
DEFAULT_SEEDS = (11, 29, 47)
EXPECTED_PUBLIC20_ROWS = 20
# Changed: make the active public20 model-validation split 10 train / 10 val.
# Why: the prior 16/4 split is archive-only, and the current criterion requires 5 val rows per label.
DEFAULT_VAL_PER_LABEL = 5


class Public20SplitError(ValueError):
    """Raised when public20 split inputs are malformed."""


def _read_jsonl(path: Path) -> List[Json]:
    rows: List[Json] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    value = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise Public20SplitError(f"{path}:{line_number}:invalid_json:{exc.msg}") from exc
                if not isinstance(value, dict):
                    raise Public20SplitError(f"{path}:{line_number}:row_not_object")
                rows.append(value)
    except OSError as exc:
        raise Public20SplitError(f"{path}:{exc}") from exc
    return rows


def _required_string(row: Mapping[str, Any], field: str, *, row_name: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise Public20SplitError(f"{row_name}:{field}_missing")
    return value.strip()


def _load_public20_inputs(path: Path) -> Dict[str, Json]:
    rows = _read_jsonl(path)
    by_id: Dict[str, Json] = {}
    for index, row in enumerate(rows, start=1):
        sample_id = _required_string(row, "sample_id", row_name=f"input_row_{index}")
        input_text = _required_string(row, "input", row_name=f"input_row_{index}")
        if sample_id in by_id:
            raise Public20SplitError(f"duplicate_input_sample_id:{sample_id}")
        by_id[sample_id] = {
            "sample_id": sample_id,
            "input": input_text,
            "source": row.get("source"),
        }
    return by_id


def _normalize_label(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"pass", "fail"}:
        raise Public20SplitError(f"unsupported_label:{value}")
    return normalized


def _load_public20_labels(path: Path) -> Dict[str, str]:
    rows = _read_jsonl(path)
    labels: Dict[str, str] = {}
    for index, row in enumerate(rows, start=1):
        sample_id = _required_string(row, "sample_id", row_name=f"label_row_{index}")
        label = _normalize_label(_required_string(row, "label", row_name=f"label_row_{index}"))
        if sample_id in labels:
            raise Public20SplitError(f"duplicate_label_sample_id:{sample_id}")
        labels[sample_id] = label
    return labels


def _validate_public20_alignment(inputs: Mapping[str, Json], labels: Mapping[str, str]) -> None:
    input_ids = set(inputs)
    label_ids = set(labels)
    missing_labels = sorted(input_ids - label_ids)
    missing_inputs = sorted(label_ids - input_ids)
    if missing_labels or missing_inputs:
        raise Public20SplitError(
            "input_label_sample_id_mismatch:"
            f"missing_labels={missing_labels}:missing_inputs={missing_inputs}"
        )
    if len(inputs) != EXPECTED_PUBLIC20_ROWS:
        raise Public20SplitError(f"unexpected_public20_input_count:{len(inputs)}")
    if len(labels) != EXPECTED_PUBLIC20_ROWS:
        raise Public20SplitError(f"unexpected_public20_label_count:{len(labels)}")
    counts = Counter(labels.values())
    if counts.get("pass", 0) < DEFAULT_VAL_PER_LABEL or counts.get("fail", 0) < DEFAULT_VAL_PER_LABEL:
        raise Public20SplitError(f"insufficient_label_counts:{dict(counts)}")


def load_public20(input_path: Path, labels_path: Path) -> Tuple[Dict[str, Json], Dict[str, str]]:
    inputs = _load_public20_inputs(input_path)
    labels = _load_public20_labels(labels_path)
    _validate_public20_alignment(inputs, labels)
    return inputs, labels


# Changed: select validation rows by label with a deterministic seed.
# Why: each split needs pass=5/fail=5 validation rows and no public20 test split.
# Changed: build split rows with only input and labels on disk.
# Why: public20-derived model-validation artifacts must keep the same two-column shape.
def build_split(
    inputs: Mapping[str, Json],
    labels: Mapping[str, str],
    *,
    seed: int,
    val_per_label: int = DEFAULT_VAL_PER_LABEL,
) -> Json:
    by_label: Dict[str, List[str]] = defaultdict(list)
    for sample_id, label in labels.items():
        by_label[label].append(sample_id)

    rng = random.Random(seed)
    val_ids: List[str] = []
    for label in ("pass", "fail"):
        sample_ids = sorted(by_label[label])
        rng.shuffle(sample_ids)
        if len(sample_ids) < val_per_label:
            raise Public20SplitError(f"insufficient_{label}_rows_for_val:{len(sample_ids)}")
        val_ids.extend(sample_ids[:val_per_label])

    val_set = set(val_ids)
    train_ids = sorted(sample_id for sample_id in inputs if sample_id not in val_set)
    val_ids_sorted = sorted(val_ids)

    def make_row(sample_id: str) -> Json:
        return {
            "input": inputs[sample_id]["input"],
            "labels": labels[sample_id],
        }

    train_rows = [make_row(sample_id) for sample_id in train_ids]
    val_rows = [make_row(sample_id) for sample_id in val_ids_sorted]
    report = build_report(
        seed=seed,
        train_rows=train_rows,
        val_rows=val_rows,
        labels=labels,
        train_ids=train_ids,
        val_ids=val_ids_sorted,
    )
    return {"train_rows": train_rows, "val_rows": val_rows, "report": report}


def _label_counts(rows: Iterable[Mapping[str, Any]]) -> Json:
    counts = Counter(str(row.get("labels", "")).lower() for row in rows)
    return {label: counts[label] for label in sorted(counts)}


def build_report(
    *,
    seed: int,
    train_rows: Sequence[Mapping[str, Any]],
    val_rows: Sequence[Mapping[str, Any]],
    labels: Mapping[str, str],
    train_ids: Sequence[str],
    val_ids: Sequence[str],
) -> Json:
    # Changed: keep sample IDs in reports only, not JSONL rows.
    # Why: users compare the data files to public20 input/labels columns.
    sample_ids = [*train_ids, *val_ids]
    return {
        "schema_version": SPLIT_SCHEMA_VERSION,
        "seed": seed,
        "purpose": "public20_model_validation_only",
        "hidden_test": "leaderboard",
        "public20_test_split_created": False,
        "warning": (
            "public20 labels are local model-validation references only; do not use these rows "
            "for synthetic generation prompts, synthetic judge prompts, or generated synthetic manifests"
        ),
        "row_counts": {
            "total": len(sample_ids),
            "train": len(train_rows),
            "val": len(val_rows),
            "test": 0,
        },
        "label_counts": {
            "all": {label: Counter(labels.values())[label] for label in sorted(set(labels.values()))},
            "train": _label_counts(train_rows),
            "val": _label_counts(val_rows),
        },
        "sample_ids": {
            "train": [str(sample_id) for sample_id in train_ids],
            "val": [str(sample_id) for sample_id in val_ids],
            "test": [],
        },
        "input_label_sample_id_match": True,
    }


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_report_md(report: Mapping[str, Any]) -> str:
    label_counts = report["label_counts"]
    sample_ids = report["sample_ids"]
    return "\n".join(
        [
            "# Public20 Train/Val Split Report",
            "",
            f"- schema_version: `{report['schema_version']}`",
            f"- seed: `{report['seed']}`",
            "- purpose: `public20_model_validation_only`",
            "- hidden_test: `leaderboard`",
            "- public20_test_split_created: `false`",
            "",
            "## Warning",
            "",
            str(report["warning"]),
            "",
            "## Row Counts",
            "",
            f"- train: `{report['row_counts']['train']}`",
            f"- val: `{report['row_counts']['val']}`",
            f"- test: `{report['row_counts']['test']}`",
            "",
            "## Label Counts",
            "",
            f"- all: `{json.dumps(label_counts['all'], ensure_ascii=False, sort_keys=True)}`",
            f"- train: `{json.dumps(label_counts['train'], ensure_ascii=False, sort_keys=True)}`",
            f"- val: `{json.dumps(label_counts['val'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Sample IDs",
            "",
            f"- train: `{', '.join(sample_ids['train'])}`",
            f"- val: `{', '.join(sample_ids['val'])}`",
            "- test: ``",
            "",
            "이 artifact는 public20-only 모델 후보 검증 전용이다. synthetic generation, synthetic judge, generated synthetic manifest target으로 사용하지 않는다.",
            "",
        ]
    )


def write_split(output_root: Path, seed: int, split: Mapping[str, Any]) -> Path:
    split_dir = output_root / f"split_seed_{seed}"
    _write_jsonl(split_dir / "train.jsonl", split["train_rows"])
    _write_jsonl(split_dir / "val.jsonl", split["val_rows"])
    _write_json(split_dir / "split_report.json", split["report"])
    (split_dir / "split_report.md").write_text(render_report_md(split["report"]), encoding="utf-8")
    return split_dir


def render_root_readme(seeds: Sequence[int]) -> str:
    return "\n".join(
        [
            "# Public20 Model Validation Splits",
            "",
            "이 디렉터리는 public20-only 모델 후보 검증용 deterministic train/val split artifact다.",
            "",
            "- public20 labels는 local model-validation reference로만 사용한다.",
            "- synthetic generation prompt, synthetic judge prompt, generated synthetic manifest target으로 사용하지 않는다.",
            "- public20 `test` split은 만들지 않는다. test는 leaderboard hidden 평가다.",
            # Changed: document the active 10/10 split contract in generated run README files.
            # Why: consumers must not use the old public20_splits 16/4 artifacts as active validation inputs.
            "- 기본 split은 각 seed마다 `10 train / 10 val`이며 train과 val은 각각 `pass 5 / fail 5`다.",
            "",
            f"- generated seeds: `{', '.join(str(seed) for seed in seeds)}`",
            "",
        ]
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=Path("data/local/public20/public20_input.jsonl"))
    parser.add_argument("--labels-jsonl", type=Path, default=Path("data/local/public20/public20_labels.local.jsonl"))
    # Changed: write active split artifacts under public20_10_10_splits by default.
    # Why: runs/model_validation/public20_splits contains archive-only 16/4 artifacts.
    parser.add_argument("--output-root", type=Path, default=Path("runs/model_validation/public20_10_10_splits"))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--val-per-label", type=int, default=DEFAULT_VAL_PER_LABEL)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        inputs, labels = load_public20(args.input_jsonl, args.labels_jsonl)
        # Changed: keep the CLI flag explicit but guard public20 runs to the active 5-per-label criterion.
        # Why: public20 has 20 rows total and the current validation contract is exactly 10 train / 10 val.
        if args.val_per_label != DEFAULT_VAL_PER_LABEL:
            raise Public20SplitError("val_per_label_must_remain_5_for_public20_10_10_gate")
        generated: List[str] = []
        for seed in args.seeds:
            split = build_split(inputs, labels, seed=seed, val_per_label=args.val_per_label)
            split_dir = write_split(args.output_root, seed, split)
            generated.append(str(split_dir))
        args.output_root.mkdir(parents=True, exist_ok=True)
        (args.output_root / "README.md").write_text(render_root_readme(args.seeds), encoding="utf-8")
    except Public20SplitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"generated": generated}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
