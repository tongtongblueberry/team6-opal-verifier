#!/usr/bin/env python3
# 목적: 학습/제출 없이 JSON/JSONL 데이터셋을 감사하고 hidden-like split 산출물을 생성한다.

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


# Changed: keep default audits inside the owned workspace, never the old shared team6 root.
# Why: data validation must not silently read another team's or legacy workspace files.
DEFAULT_INPUT_CANDIDATES = (
    Path("/workspace/sinjeongmin_opal_verifier/training_data"),
    Path("/workspace/sinjeongmin_opal_verifier/data"),
    Path("training_data"),
    Path("data"),
)
JSON_SUFFIXES = {".json", ".jsonl"}
KST = timezone(timedelta(hours=9), name="KST")

ID_KEYS = ("sample_id", "sampleid", "id", "uid", "uuid", "record_id", "example_id", "idx")
SOURCE_KEYS = ("source", "data_source", "dataset", "origin", "benchmark", "task", "domain", "category")
LABEL_KEYS = ("label", "labels", "target", "class", "y", "verdict", "expected", "gold", "answer_label")
TEXT_KEYS = (
    "prompt",
    "text",
    "input",
    "instruction",
    "question",
    "query",
    "messages",
    "conversation",
    "trajectory",
    "completion",
    "response",
    "output",
    "answer",
    "final_answer",
    "solution",
    "rationale",
)
TEMPLATE_KEYS = ("template_id", "prompt_template_id", "template_name", "template", "pattern_id", "schema_id")
MUTATION_KEYS = (
    "mutation_family",
    "mutation",
    "mutation_type",
    "family",
    "variant_family",
    "perturbation",
    "transformation",
    "generator",
)
CONTAINER_KEYS = ("records", "data", "examples", "samples", "items", "rows", "train", "validation", "valid", "test")
MESSAGE_CONTENT_KEYS = ("content", "text", "message", "value", "answer", "response")
LENGTH_BINS = (
    (0, 0, "0"),
    (1, 32, "1-32"),
    (33, 64, "33-64"),
    (65, 128, "65-128"),
    (129, 256, "129-256"),
    (257, 512, "257-512"),
    (513, 1024, "513-1024"),
    (1025, None, "1025+"),
)
LENGTH_BIN_LABELS = tuple(label for _, _, label in LENGTH_BINS)


@dataclass(frozen=True)
class RawRecord:
    path: str
    row: int
    data: Mapping[str, Any]


@dataclass(frozen=True)
class AuditRecord:
    index: int
    sample_id: str
    source: str
    label: str
    text: str
    template_id: str
    template_signature: str
    mutation_family: str
    length_bin: str
    token_count: int
    path: str
    row: int
    group_key: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit JSON/JSONL data and build a hidden-like validation split.")
    parser.add_argument("--input", action="append", default=[], help="Input file or directory. May be repeated.")
    parser.add_argument("--reference", action="append", default=[], help="Reference file or directory. May be repeated.")
    parser.add_argument("--output-dir", default="data_audit_outputs", help="Directory for default outputs.")
    parser.add_argument("--manifest-out", default=None, help="JSONL manifest path. Relative paths are under --output-dir.")
    parser.add_argument("--report-out", default=None, help="Report stem/path. Emits both JSON and MD.")
    parser.add_argument("--hidden-fraction", type=float, default=0.2, help="Fraction of groups assigned to hidden.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic group shuffle seed.")
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise ValueError(message)


def resolve_input_roots(values: Sequence[str]) -> List[Path]:
    if values:
        return [Path(value) for value in values]
    return [path for path in DEFAULT_INPUT_CANDIDATES if path.exists()]


def collect_json_files(paths: Sequence[Path]) -> List[Path]:
    files: List[Path] = []
    for path in paths:
        if not path.exists():
            fail(f"input path does not exist: {path}")
        if path.is_dir():
            files.extend(sorted(child for child in path.rglob("*") if child.is_file() and child.suffix.lower() in JSON_SUFFIXES))
        elif path.is_file() and path.suffix.lower() in JSON_SUFFIXES:
            files.append(path)
        else:
            fail(f"expected a .json/.jsonl file or directory: {path}")

    deduped: List[Path] = []
    seen = set()
    for file_path in files:
        key = str(file_path.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(file_path)
    return sorted(deduped)


# Added to tolerate common dataset schemas without adding parser dependencies.
def load_raw_records(paths: Sequence[Path]) -> List[RawRecord]:
    files = collect_json_files(paths)
    raw_records: List[RawRecord] = []
    for file_path in files:
        if file_path.suffix.lower() == ".jsonl":
            raw_records.extend(load_jsonl_records(file_path))
        else:
            raw_records.extend(load_json_records(file_path))
    return raw_records


def load_jsonl_records(file_path: Path) -> List[RawRecord]:
    rows: List[RawRecord] = []
    logical_row = 0
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                fail(f"invalid JSONL in {file_path} line {line_number}: {exc}")
            for record in iter_json_records(payload):
                rows.append(RawRecord(path=str(file_path), row=logical_row, data=record))
                logical_row += 1
    return rows


def load_json_records(file_path: Path) -> List[RawRecord]:
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {file_path}: {exc}")
    return [RawRecord(path=str(file_path), row=row, data=record) for row, record in enumerate(iter_json_records(payload))]


def iter_json_records(payload: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from iter_json_records(item)
        return

    if not isinstance(payload, dict):
        yield {"value": payload}
        return

    lowered = {str(key).lower(): key for key in payload}
    for container_key in CONTAINER_KEYS:
        original_key = lowered.get(container_key)
        if original_key is not None and isinstance(payload[original_key], (list, dict)):
            yield from iter_json_records(payload[original_key])
            return

    if looks_record_like(payload):
        yield payload
        return

    if payload and all(isinstance(value, (dict, list)) for value in payload.values()):
        for key, value in payload.items():
            for record in iter_json_records(value):
                expanded = dict(record)
                expanded.setdefault("_container_key", key)
                yield expanded
        return

    yield payload


def looks_record_like(record: Mapping[str, Any]) -> bool:
    keys = {str(key).lower() for key in record}
    known_keys = set(ID_KEYS) | set(SOURCE_KEYS) | set(LABEL_KEYS) | set(TEXT_KEYS) | set(TEMPLATE_KEYS) | set(MUTATION_KEYS)
    return bool(keys & known_keys)


def get_value(record: Mapping[str, Any], keys: Iterable[str]) -> Any:
    lowered = {str(key).lower(): key for key in record}
    for key in keys:
        if key in record:
            return record[key]
        original_key = lowered.get(key.lower())
        if original_key is not None:
            return record[original_key]
    return None


def scalar_to_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        return text if text else None
    return None


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def value_to_text(value: Any) -> str:
    scalar = scalar_to_text(value)
    if scalar is not None:
        return scalar
    return stable_json(value)


def identifier_from_value(prefix: str, value: Any) -> Optional[str]:
    text = value_to_text(value).strip()
    if not text:
        return None
    safe = re.sub(r"[^A-Za-z0-9_.:-]+", "_", text).strip("_")
    if 1 <= len(safe) <= 80:
        return safe
    return stable_id(prefix, text)


def stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def extract_text(record: Mapping[str, Any]) -> str:
    parts: List[str] = []
    for key in TEXT_KEYS:
        value = get_value(record, (key,))
        if value is not None:
            parts.extend(collect_text_parts(value, key))
    if not parts:
        parts.append(stable_json(record))
    return "\n".join(part for part in parts if part).strip()


def collect_text_parts(value: Any, key_hint: str = "") -> List[str]:
    scalar = scalar_to_text(value)
    if scalar is not None:
        return [scalar]

    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            parts.extend(collect_text_parts(item, key_hint))
        return parts

    if isinstance(value, dict):
        lowered = {str(key).lower(): key for key in value}
        parts = []

        role = scalar_to_text(value.get("role"))
        for content_key in MESSAGE_CONTENT_KEYS:
            original_key = lowered.get(content_key)
            if original_key is None:
                continue
            content_parts = collect_text_parts(value[original_key], content_key)
            if role:
                parts.extend(f"{role}: {part}" for part in content_parts)
            else:
                parts.extend(content_parts)

        if parts:
            return parts

        for text_key in TEXT_KEYS:
            original_key = lowered.get(text_key)
            if original_key is not None:
                parts.extend(collect_text_parts(value[original_key], text_key))
        if parts:
            return parts

        return [stable_json(value)]

    return [value_to_text(value)]


def normalize_template_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"https?://\S+|www\.\S+", "<url>", normalized)
    normalized = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", normalized)
    normalized = re.sub(r"\b[0-9a-f]{16,}\b", "<hex>", normalized)
    normalized = re.sub(r"[-+]?\d+\.\d+", "<num>", normalized)
    normalized = re.sub(r"\b\d+\b", "<num>", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or "<empty>"


def token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def length_bin(count: int) -> str:
    for lower, upper, label in LENGTH_BINS:
        if count >= lower and (upper is None or count <= upper):
            return label
    return LENGTH_BIN_LABELS[-1]


def build_audit_records(raw_records: Sequence[RawRecord]) -> List[AuditRecord]:
    records: List[AuditRecord] = []
    for index, raw in enumerate(raw_records):
        text = extract_text(raw.data)
        signature = normalize_template_text(text)
        count = token_count(text)
        template_value = get_value(raw.data, TEMPLATE_KEYS)

        sample_id = scalar_to_text(get_value(raw.data, ID_KEYS)) or f"{raw.path}:{raw.row}"
        source = scalar_to_text(get_value(raw.data, SOURCE_KEYS)) or Path(raw.path).stem or "unknown"
        label = value_to_text(get_value(raw.data, LABEL_KEYS)) if get_value(raw.data, LABEL_KEYS) is not None else "unknown"
        template_id = identifier_from_value("tmpl", template_value) if template_value is not None else stable_id("tmpl", signature)
        mutation_family = identifier_from_value("mut", get_value(raw.data, MUTATION_KEYS)) or "base"
        bin_label = length_bin(count)
        group_key = "\x1f".join((template_id, source, mutation_family))

        records.append(
            AuditRecord(
                index=index,
                sample_id=sample_id,
                source=source,
                label=label,
                text=text,
                template_id=template_id,
                template_signature=signature,
                mutation_family=mutation_family,
                length_bin=bin_label,
                token_count=count,
                path=raw.path,
                row=raw.row,
                group_key=group_key,
            )
        )
    return records


# Added to make the hidden split deterministic and leakage-free at the required group level.
def assign_splits(records: Sequence[AuditRecord], hidden_fraction: float, seed: int) -> Dict[str, str]:
    if hidden_fraction < 0.0 or hidden_fraction > 1.0:
        fail("--hidden-fraction must be between 0 and 1")

    groups = sorted({record.group_key for record in records})
    rng = random.Random(seed)
    rng.shuffle(groups)

    if not groups or hidden_fraction <= 0.0:
        hidden_count = 0
    elif hidden_fraction >= 1.0:
        hidden_count = len(groups)
    else:
        hidden_count = int(round(len(groups) * hidden_fraction))
        hidden_count = max(1, hidden_count)
        if hidden_count >= len(groups) and len(groups) > 1:
            hidden_count = len(groups) - 1

    hidden_groups = set(groups[:hidden_count])
    return {group: ("hidden" if group in hidden_groups else "train") for group in groups}


def normalized_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    unique = len(counter)
    if total <= 0 or unique <= 1:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        probability = count / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(unique)


def counter_to_sorted_dict(counter: Counter) -> Dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def distribution(counter: Counter, labels: Sequence[str]) -> List[float]:
    total = sum(counter.get(label, 0) for label in labels)
    if total <= 0:
        return [0.0 for _ in labels]
    return [counter.get(label, 0) / total for label in labels]


def kl_divergence(p_dist: Sequence[float], q_dist: Sequence[float]) -> float:
    total = 0.0
    for p_value, q_value in zip(p_dist, q_dist):
        if p_value > 0.0 and q_value > 0.0:
            total += p_value * math.log(p_value / q_value, 2)
    return total


def jensen_shannon_divergence(left_counter: Counter, right_counter: Counter, labels: Sequence[str]) -> Optional[float]:
    if sum(left_counter.values()) <= 0 or sum(right_counter.values()) <= 0:
        return None
    left = distribution(left_counter, labels)
    right = distribution(right_counter, labels)
    midpoint = [(left_value + right_value) / 2 for left_value, right_value in zip(left, right)]
    return 0.5 * kl_divergence(left, midpoint) + 0.5 * kl_divergence(right, midpoint)


def duplicate_groups(records: Sequence[AuditRecord]) -> List[Dict[str, Any]]:
    groups: DefaultDict[Tuple[str, str], List[AuditRecord]] = defaultdict(list)
    for record in records:
        groups[(record.source, record.text)].append(record)

    duplicates = []
    for (source, text), members in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        if len(members) <= 1:
            continue
        duplicates.append(
            {
                "source": source,
                "text_hash": hashlib.sha1(text.encode("utf-8")).hexdigest(),
                "count": len(members),
                "sample_ids": [member.sample_id for member in members[:20]],
                "paths": sorted({member.path for member in members}),
            }
        )
    return duplicates


def leakage_groups(records: Sequence[AuditRecord], split_by_group: Mapping[str, str]) -> List[str]:
    split_sets: DefaultDict[str, set] = defaultdict(set)
    for record in records:
        split_sets[record.group_key].add(split_by_group[record.group_key])
    return sorted(group for group, splits in split_sets.items() if len(splits) > 1)


# Added to compute audit gates from the same metrics that are written to reports.
def build_report(
    records: Sequence[AuditRecord],
    reference_records: Sequence[AuditRecord],
    split_by_group: Mapping[str, str],
    input_paths: Sequence[Path],
    reference_paths: Sequence[Path],
    manifest_path: Path,
    report_json_path: Path,
    report_md_path: Path,
    hidden_fraction: float,
    seed: int,
) -> Dict[str, Any]:
    source_counts = Counter(record.source for record in records)
    label_counts = Counter(record.label for record in records)
    length_counts = Counter(record.length_bin for record in records)
    template_counts = Counter(record.template_id for record in records)
    split_counts = Counter(split_by_group[record.group_key] for record in records)
    group_split_counts = Counter(split_by_group[group] for group in split_by_group)
    duplicate_list = duplicate_groups(records)
    leakage_list = leakage_groups(records, split_by_group)

    total_records = len(records)
    top_template_count = max(template_counts.values()) if template_counts else 0
    top_template_share = top_template_count / total_records if total_records else 0.0
    template_entropy = normalized_entropy(template_counts)

    reference_length_counts = Counter(record.length_bin for record in reference_records)
    length_jsd = (
        jensen_shannon_divergence(length_counts, reference_length_counts, LENGTH_BIN_LABELS)
        if reference_paths
        else None
    )

    gate_status: Dict[str, Dict[str, Any]] = {
        "source_exact_duplicate_0": {
            "value": len(duplicate_list),
            "threshold": 0,
            "passed": len(duplicate_list) == 0,
        },
        "group_leakage_0": {
            "value": len(leakage_list),
            "threshold": 0,
            "passed": len(leakage_list) == 0,
        },
        "normalized_template_entropy_gte_0.75": {
            "value": round(template_entropy, 6),
            "threshold": 0.75,
            "passed": template_entropy >= 0.75,
        },
        "top_template_share_lte_0.20": {
            "value": round(top_template_share, 6),
            "threshold": 0.20,
            "passed": top_template_share <= 0.20,
        },
    }

    if reference_paths:
        gate_status["length_jsd_lte_0.08"] = {
            "value": None if length_jsd is None else round(length_jsd, 6),
            "threshold": 0.08,
            "passed": length_jsd is not None and length_jsd <= 0.08,
        }
    else:
        gate_status["length_jsd_lte_0.08"] = {
            "value": None,
            "threshold": 0.08,
            "passed": None,
            "skipped": True,
        }

    overall_passed = all(status["passed"] is not False for status in gate_status.values())

    generated_at = datetime.now(KST).isoformat()
    return {
        "generated_at_kst": generated_at,
        "config": {
            "hidden_fraction": hidden_fraction,
            "seed": seed,
            "input_paths": [str(path) for path in input_paths],
            "reference_paths": [str(path) for path in reference_paths],
            "manifest_out": str(manifest_path),
            "report_json_out": str(report_json_path),
            "report_md_out": str(report_md_path),
        },
        "counts": {
            "records": total_records,
            "reference_records": len(reference_records),
            "groups": len(split_by_group),
            "train_records": split_counts.get("train", 0),
            "hidden_records": split_counts.get("hidden", 0),
            "train_groups": group_split_counts.get("train", 0),
            "hidden_groups": group_split_counts.get("hidden", 0),
        },
        "metrics": {
            "source_counts": counter_to_sorted_dict(source_counts),
            "label_counts": counter_to_sorted_dict(label_counts),
            "length_bins": {label: length_counts.get(label, 0) for label in LENGTH_BIN_LABELS},
            "reference_length_bins": {label: reference_length_counts.get(label, 0) for label in LENGTH_BIN_LABELS},
            "normalized_template_entropy": round(template_entropy, 6),
            "top_template_share": round(top_template_share, 6),
            "top_template_count": top_template_count,
            "exact_duplicate_groups": duplicate_list,
            "exact_duplicate_group_count": len(duplicate_list),
            "group_leakage_count": len(leakage_list),
            "group_leakage_keys": leakage_list[:50],
            "length_jsd": None if length_jsd is None else round(length_jsd, 6),
        },
        "gate_status": gate_status,
        "overall_gate_passed": overall_passed,
    }


def manifest_row(record: AuditRecord, split: str) -> Dict[str, Any]:
    return {
        "sample_id": record.sample_id,
        "source": record.source,
        "template_id": record.template_id,
        "mutation_family": record.mutation_family,
        "length_bin": record.length_bin,
        "label": record.label,
        "split": split,
        "path": record.path,
        "row": record.row,
    }


def output_path(output_dir: Path, requested: Optional[str], default_name: str) -> Path:
    if requested is None:
        return output_dir / default_name
    path = Path(requested)
    if path.is_absolute():
        return path
    return output_dir / path


def report_paths(output_dir: Path, requested: Optional[str]) -> Tuple[Path, Path]:
    base = output_path(output_dir, requested, "data_audit_report")
    if base.suffix == ".json":
        return base, base.with_suffix(".md")
    if base.suffix == ".md":
        return base.with_suffix(".json"), base
    return base.with_suffix(".json"), base.with_suffix(".md")


# Added to emit both machine-readable and Korean human-readable audit reports.
def write_outputs(
    records: Sequence[AuditRecord],
    split_by_group: Mapping[str, str],
    report: Mapping[str, Any],
    manifest_path: Path,
    report_json_path: Path,
    report_md_path: Path,
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(manifest_row(record, split_by_group[record.group_key]), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    with report_json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    with report_md_path.open("w", encoding="utf-8") as handle:
        handle.write(render_markdown(report))


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    metrics = report["metrics"]
    gate_status = report["gate_status"]
    lines = [
        "# 데이터 감사 보고서",
        "",
        f"- 생성 시각(KST): {report['generated_at_kst']}",
        f"- 전체 게이트 통과: {'통과' if report['overall_gate_passed'] else '실패'}",
        f"- 레코드 수: {counts['records']}",
        f"- 그룹 수: {counts['groups']}",
        f"- train/hidden 레코드: {counts['train_records']} / {counts['hidden_records']}",
        f"- train/hidden 그룹: {counts['train_groups']} / {counts['hidden_groups']}",
        "",
        "## 게이트 상태",
        "",
        "| 항목 | 기준 | 값 | 상태 |",
        "| --- | --- | --- | --- |",
    ]

    for name, status in gate_status.items():
        if status.get("skipped"):
            state = "건너뜀"
        elif status.get("passed"):
            state = "통과"
        else:
            state = "실패"
        lines.append(f"| `{name}` | {status.get('threshold')} | {status.get('value')} | {state} |")

    lines.extend(
        [
            "",
            "## 핵심 지표",
            "",
            f"- source exact duplicate group 수: {metrics['exact_duplicate_group_count']}",
            f"- train/hidden group leakage 수: {metrics['group_leakage_count']}",
            f"- normalized template entropy: {metrics['normalized_template_entropy']}",
            f"- top template share: {metrics['top_template_share']}",
            f"- reference length JSD: {metrics['length_jsd']}",
            "",
            "## Source Counts",
            "",
        ]
    )
    lines.extend(render_counter_lines(metrics["source_counts"]))
    lines.extend(["", "## Label Counts", ""])
    lines.extend(render_counter_lines(metrics["label_counts"]))
    lines.extend(["", "## Length Bins", ""])
    lines.extend(render_counter_lines(metrics["length_bins"]))

    duplicate_groups_value = metrics["exact_duplicate_groups"]
    if duplicate_groups_value:
        lines.extend(["", "## Exact Duplicate Groups", ""])
        for group in duplicate_groups_value[:20]:
            lines.append(
                f"- source=`{group['source']}`, count={group['count']}, "
                f"text_hash=`{group['text_hash']}`, sample_ids={group['sample_ids']}"
            )

    return "\n".join(lines) + "\n"


def render_counter_lines(counter: Mapping[str, int]) -> List[str]:
    if not counter:
        return ["- 없음"]
    return [f"- `{key}`: {value}" for key, value in counter.items()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    input_paths = resolve_input_roots(args.input)
    reference_paths = [Path(value) for value in args.reference]

    if not input_paths:
        candidates = ", ".join(str(path) for path in DEFAULT_INPUT_CANDIDATES)
        fail(f"no --input provided and no default input candidates exist: {candidates}")

    raw_records = load_raw_records(input_paths)
    if not raw_records:
        fail("no records found in input JSON/JSONL files")

    reference_raw_records = load_raw_records(reference_paths) if reference_paths else []
    records = build_audit_records(raw_records)
    reference_records = build_audit_records(reference_raw_records)
    split_by_group = assign_splits(records, args.hidden_fraction, args.seed)

    manifest_path = output_path(output_dir, args.manifest_out, "split_manifest.jsonl")
    report_json_path, report_md_path = report_paths(output_dir, args.report_out)
    report = build_report(
        records=records,
        reference_records=reference_records,
        split_by_group=split_by_group,
        input_paths=input_paths,
        reference_paths=reference_paths,
        manifest_path=manifest_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        hidden_fraction=args.hidden_fraction,
        seed=args.seed,
    )

    write_outputs(records, split_by_group, report, manifest_path, report_json_path, report_md_path)
    print(f"manifest: {manifest_path}")
    print(f"report_json: {report_json_path}")
    print(f"report_md: {report_md_path}")
    print(f"overall_gate_passed: {report['overall_gate_passed']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"data_audit: error: {exc}", file=sys.stderr)
        raise SystemExit(2)
