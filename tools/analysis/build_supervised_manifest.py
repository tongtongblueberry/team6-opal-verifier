#!/usr/bin/env python3
# 변경: raw artifact pool에서 clean pass/fail supervised manifest와 감사 보고서를 만드는 stdlib-only 도구를 추가한다.
# 이유: checkpoint/cache/rule-context 오염과 label 불명확 데이터를 제외하고 leakage-free split 산출물을 만들기 위해서다.

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
from typing import Any, DefaultDict, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple


FORMAT_VERSION = "supervised_manifest.v1"
# Changed: keep the prompt schema identity independent of row contents.
# Why: downstream validation and threshold artifacts need one stable renderer contract hash.
PROMPT_SCHEMA_VERSION = "manifest_chat_input_label.v1"
PROMPT_RENDERER_CONTRACT = {
    "version": PROMPT_SCHEMA_VERSION,
    "builder": "tools.analysis.build_supervised_manifest",
    "renderer": "tools.training.train_manifest_lora.build_messages",
    "message_contract": [
        {"role": "user", "content_field": "input", "normalization": "verbatim_manifest_value"},
        {"role": "assistant", "content_field": "label", "allowed_values": ["fail", "pass"]},
    ],
    "generation_prompt": False,
    "prompt_schema_hash_field": "prompt_schema_hash",
    "prompt_schema_hash_excluded_from_prompt": True,
}
JSON_SUFFIXES = {".json", ".jsonl"}
KST = timezone(timedelta(hours=9), name="KST")

BLOCKLIST_TERMS = ("ckpt", "embedding", "cache", "checkpoint", "intermediate")
ID_KEYS = ("sample_id", "sampleid", "id", "uid", "uuid", "record_id", "example_id", "idx")
# 변경: public/eval holdout signature를 build 단계에도 추가한다.
# 이유: supervised manifest에 들어가기 전 public 20/leaderboard 계열 raw row를 제외해야 하기 때문이다.
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
PUBLIC_HOLDOUT_METADATA_KEYS = ID_KEYS + (
    "source",
    "source_name",
    "data_source",
    "dataset",
    "origin",
    "benchmark",
    "task",
    "domain",
    "category",
    "split",
    "subset",
    "partition",
    "_container_key",
)
# 변경: LLM-only data contract 때문에 validator와 builder의 rule-context 탐지를 맞춘다.
RULE_CONTEXT_TERMS = (
    "rule context",
    "rule_context",
    "rule-context",
    "rule_engine",
    "rule-engine",
    "rule engine analysis",
    "rule engine's analysis",
    "the rule engine predicted",
    "rule engine predicted",
    "rule_id",
    "rule id",
    "StatefulOpalVerifier",
    "rule trace",
    "rule output",
    "rule_output",
    "rule result",
    "rule_result",
    "rule based",
    "rule-based",
    "deterministic verifier",
    "verifier trace",
    "verifier_trace",
    "protocol rules above",
    "rules above",
    "tcg rule summary",
)

SOURCE_KEYS = ("source", "source_name", "data_source", "dataset", "origin", "benchmark", "task", "domain", "category")
LABEL_KEYS = (
    "label",
    "status",
    "expected",
    "answer",
    "output",
    "result",
    "verdict",
    "target",
    "class",
    "y",
    "outcome",
    "pass_fail",
    "passed",
    "expected_label",
    "gold",
    "answer_label",
)
LOWER_LABEL_KEYS = {key.lower() for key in LABEL_KEYS}
INPUT_KEYS = (
    "input",
    "prompt",
    "text",
    "instruction",
    "question",
    "query",
    "problem",
    "case",
    "payload",
    "messages",
    "conversation",
    "trajectory",
    "request",
    "user_input",
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
GROUP_KEYS = ("group_id", "group", "group_key", "case_group", "problem_id", "template_group")
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
REFERENCE_AUXILIARY_KEYS = (
    "score",
    "scores",
    "ifd_score",
    "loss",
    "probability",
    "confidence",
    "metric",
    "metrics",
    "accuracy",
    "auc",
    "counts",
    "gate_status",
    "overall_gate_passed",
    "violations",
    "duplicate_groups",
    "rejection_examples",
)
# Changed: define score/report-only keys that are not supervised training inputs.
# Why: manifest rows must not be synthesized from IFD/metrics artifacts without example content.
TRAINING_AUXILIARY_KEYS = {key.lower() for key in REFERENCE_AUXILIARY_KEYS} | {
    "length",
    "length_bin",
    "num_records",
}
TRAINING_METADATA_KEYS = (
    {key.lower() for key in ID_KEYS}
    | {key.lower() for key in SOURCE_KEYS}
    | {key.lower() for key in LABEL_KEYS}
    | {key.lower() for key in TEMPLATE_KEYS}
    | {key.lower() for key in MUTATION_KEYS}
    | {key.lower() for key in GROUP_KEYS}
    | {"content_hash", "path", "row", "split"}
)
REFERENCE_AUXILIARY_PATH_TERMS = (
    "score",
    "scores",
    "ifd",
    "metric",
    "metrics",
    "report",
    "summary",
    "stats",
    "analysis",
    "audit",
    "cache",
    "embedding",
    "checkpoint",
    "ckpt",
    "dedup",
    "rejection",
)
REFERENCE_SKIP_EXAMPLE_LIMIT = 50


@dataclass(frozen=True)
class RawRecord:
    path: str
    row: int
    data: Mapping[str, Any]


@dataclass(frozen=True)
class ManifestRecord:
    index: int
    sample_id: str
    input_text: str
    label: str
    source: str
    label_source: str
    template_id: str
    mutation_family: str
    length_bin: str
    input_token_count: int
    content_hash: str
    input_hash_no_label: str
    parse_status: str
    metadata_only: bool
    prompt_schema_version: str
    prompt_schema_hash: str
    family_component: str
    group_id: str
    path: str
    row: int
    blocklisted: bool
    blocklist_matches: Tuple[str, ...]


@dataclass(frozen=True)
class Rejection:
    reason: str
    path: str
    row: Optional[int]
    sample_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DiscoveryResult:
    json_files: List[Path]
    skipped_files: List[Dict[str, str]]


@dataclass(frozen=True)
class ReferenceLoadResult:
    length_counts: Counter
    errors: List[Dict[str, Any]]
    eligible_records: int
    skipped: Mapping[str, Any]


@dataclass(frozen=True)
class LengthBalanceOutcome:
    records: List[ManifestRecord]
    report: Dict[str, Any]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a clean pass/fail supervised manifest from raw JSON artifacts.")
    parser.add_argument("--input", action="append", nargs="+", required=True, help="Input JSON/JSONL file or directory.")
    parser.add_argument("--output", required=True, help="Output manifest JSONL path.")
    parser.add_argument("--report-out", required=True, help="Report stem/path. Emits JSON and Korean MD.")
    parser.add_argument("--hidden-fraction", type=float, default=0.2, help="Fraction of groups assigned to hidden.")
    parser.add_argument("--calibration-fraction", type=float, default=0.1, help="Fraction of groups assigned to calibration.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic group shuffle seed.")
    parser.add_argument("--min-template-entropy", type=float, default=0.75, help="Minimum normalized template entropy gate.")
    parser.add_argument("--max-top-template-share", type=float, default=0.20, help="Maximum top template share gate.")
    parser.add_argument(
        "--include-blocklisted",
        action="store_true",
        help="Include records from blocklisted file/source names while still reporting them.",
    )
    # 변경: optional reference-based length selector controls를 추가한다.
    # 이유: 기본 빌드는 유지하면서 요청 시 split 전 후보의 length distribution을 reference eligible corpus에 맞추기 위해서다.
    parser.add_argument("--length-balance-reference", default=None, help="Optional reference JSON/JSONL file or directory for length balancing.")
    parser.add_argument("--length-balance-target-jsd", type=float, default=0.08, help="Target maximum length-bin JSD when length balancing is enabled.")
    parser.add_argument(
        "--length-balance-max-drop-fraction",
        type=float,
        default=0.2,
        help="Maximum fraction of deduped records the length balancer may drop by group.",
    )
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise ValueError(message)


def flatten_inputs(values: Sequence[Sequence[str]]) -> List[Path]:
    paths: List[Path] = []
    for group in values:
        for value in group:
            paths.append(Path(value))
    return paths


def validate_args(args: argparse.Namespace) -> None:
    if not 0.0 <= args.hidden_fraction <= 1.0:
        fail("--hidden-fraction must be between 0 and 1")
    if not 0.0 <= args.calibration_fraction <= 1.0:
        fail("--calibration-fraction must be between 0 and 1")
    if args.hidden_fraction + args.calibration_fraction > 1.0:
        fail("--hidden-fraction plus --calibration-fraction must be <= 1")
    if not 0.0 <= args.min_template_entropy <= 1.0:
        fail("--min-template-entropy must be between 0 and 1")
    if not 0.0 <= args.max_top_template_share <= 1.0:
        fail("--max-top-template-share must be between 0 and 1")
    if args.length_balance_target_jsd < 0.0:
        fail("--length-balance-target-jsd must be >= 0")
    if not 0.0 <= args.length_balance_max_drop_fraction <= 1.0:
        fail("--length-balance-max-drop-fraction must be between 0 and 1")


# 변경: 디렉터리/파일 입력을 JSON 계열과 skip 대상 파일로 분리한다.
# 이유: raw artifact pool 안의 npz/checkpoint 같은 비JSON 산출물을 실패가 아니라 명시적 skip으로 보고하기 위해서다.
def discover_json_files(paths: Sequence[Path]) -> DiscoveryResult:
    json_files: List[Path] = []
    skipped_files: List[Dict[str, str]] = []

    for path in paths:
        if not path.exists():
            fail(f"input path does not exist: {path}")
        if path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                if child.suffix.lower() in JSON_SUFFIXES:
                    json_files.append(child)
                else:
                    skipped_files.append({"path": str(child), "reason": "non_json"})
        elif path.is_file() and path.suffix.lower() in JSON_SUFFIXES:
            json_files.append(path)
        elif path.is_file():
            skipped_files.append({"path": str(path), "reason": "non_json"})
        else:
            skipped_files.append({"path": str(path), "reason": "not_file"})

    deduped: List[Path] = []
    seen = set()
    for file_path in json_files:
        key = str(file_path.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(file_path)
    return DiscoveryResult(json_files=sorted(deduped), skipped_files=skipped_files)


def load_raw_records(paths: Sequence[Path]) -> List[RawRecord]:
    raw_records: List[RawRecord] = []
    for file_path in paths:
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

    # Changed: preserve {"records": [...], "label": ...} as one trajectory example.
    # Why: the records list is the training input unit, not a container to flatten into steps.
    if is_labeled_records_trajectory(payload):
        yield payload
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
    known = (
        set(ID_KEYS)
        | set(SOURCE_KEYS)
        | set(LABEL_KEYS)
        | set(INPUT_KEYS)
        | set(TEMPLATE_KEYS)
        | set(MUTATION_KEYS)
        | set(GROUP_KEYS)
    )
    return bool(keys & known)


# Changed: add top-level trajectory helpers for raw manifest units.
# Why: only the parent records+label object should control loading and input extraction.
def top_level_value_for_key(record: Mapping[str, Any], wanted_key: str) -> Tuple[bool, Any]:
    lowered = {str(key).lower(): key for key in record}
    original_key = lowered.get(wanted_key.lower())
    if original_key is None:
        return False, None
    return True, record[original_key]


def is_labeled_records_trajectory(record: Mapping[str, Any]) -> bool:
    has_records, records_value = top_level_value_for_key(record, "records")
    has_label, label_value = top_level_value_for_key(record, "label")
    return (
        has_records
        and has_label
        and isinstance(records_value, (list, dict))
        and normalize_label(label_value) is not None
    )


def records_trajectory_input_text(record: Mapping[str, Any]) -> Optional[str]:
    if not is_labeled_records_trajectory(record):
        return None
    _, records_value = top_level_value_for_key(record, "records")
    return stable_json({"records": records_value})


# Changed: identify score/report rows that have no example payload.
# Why: label plus ifd_score/metrics metadata alone must not become fallback JSON training input.
def auxiliary_training_row_reason(record: Mapping[str, Any]) -> Optional[str]:
    keys = {str(key).lower() for key in record}
    auxiliary_hits = sorted(keys & TRAINING_AUXILIARY_KEYS)
    if not auxiliary_hits:
        return None
    if is_labeled_records_trajectory(record):
        return None
    if keys & {key.lower() for key in INPUT_KEYS}:
        return None

    unexpected_payload_keys = sorted(keys - TRAINING_AUXILIARY_KEYS - TRAINING_METADATA_KEYS)
    if unexpected_payload_keys:
        return None
    return "auxiliary_record_keys:" + ",".join(auxiliary_hits[:5])


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def scalar_to_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        return text if text else None
    return None


def value_to_text(value: Any) -> str:
    scalar = scalar_to_text(value)
    if scalar is not None:
        return scalar
    return stable_json(value)


def stable_id(prefix: str, text: str, size: int = 12) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:size]
    return f"{prefix}_{digest}"


def identifier_from_value(prefix: str, value: Any) -> Optional[str]:
    text = value_to_text(value).strip()
    if not text:
        return None
    safe = re.sub(r"[^A-Za-z0-9_.:-]+", "_", text).strip("_")
    if 1 <= len(safe) <= 96:
        return safe
    return stable_id(prefix, text)


def path_to_string(parts: Sequence[Any]) -> str:
    rendered: List[str] = []
    for part in parts:
        if isinstance(part, int):
            if rendered:
                rendered[-1] = f"{rendered[-1]}[{part}]"
            else:
                rendered.append(f"[{part}]")
        else:
            rendered.append(str(part))
    return ".".join(rendered)


def find_key_matches(value: Any, keys: Sequence[str], path: Tuple[Any, ...] = ()) -> Iterator[Tuple[Tuple[Any, ...], Any]]:
    wanted = {key.lower(): index for index, key in enumerate(keys)}
    if isinstance(value, Mapping):
        lowered = {str(key).lower(): key for key in value}
        ordered_keys = sorted(
            (lowered[key] for key in wanted if key in lowered),
            key=lambda original: wanted[str(original).lower()],
        )
        for key in ordered_keys:
            yield path + (key,), value[key]
        for key, child in value.items():
            if isinstance(child, (Mapping, list)):
                yield from find_key_matches(child, keys, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (Mapping, list)):
                yield from find_key_matches(child, keys, path + (index,))


def first_scalar_value(record: Mapping[str, Any], keys: Sequence[str]) -> Optional[Any]:
    matches = list(find_key_matches(record, keys))
    if not matches:
        return None
    matches.sort(key=lambda item: (len(item[0]), key_priority(item[0][-1], keys), path_to_string(item[0])))
    for _, value in matches:
        if scalar_to_text(value) is not None:
            return value
    return matches[0][1]


def key_priority(key: Any, keys: Sequence[str]) -> int:
    lowered = str(key).lower()
    for index, candidate in enumerate(keys):
        if lowered == candidate.lower():
            return index
    return len(keys)


def normalize_label(value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return None
    scalar = scalar_to_text(value)
    if scalar is None:
        return None

    normalized = scalar.strip().lower()
    normalized = re.sub(r"^[^a-z]+|[^a-z]+$", "", normalized)
    if normalized in {"pass", "passed"}:
        return "pass"
    if normalized in {"fail", "failed"}:
        return "fail"
    return None


# 변경: label/status/expected/answer/output/result 계열을 우선순위와 위치 정보까지 함께 탐색한다.
# 이유: pass/fail로 확정되는 record만 allowlist에 포함하고, label provenance를 manifest에 남기기 위해서다.
def extract_label(record: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    matches = list(find_key_matches(record, LABEL_KEYS))
    matches.sort(key=lambda item: (len(item[0]), key_priority(item[0][-1], LABEL_KEYS), path_to_string(item[0])))
    for path, value in matches:
        normalized = normalize_label(value)
        if normalized is not None:
            return normalized, path_to_string(path)
    return None, None


def collect_text_parts(value: Any, key_hint: str = "") -> List[str]:
    scalar = scalar_to_text(value)
    if scalar is not None:
        return [scalar]

    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            parts.extend(collect_text_parts(item, key_hint))
        return parts

    if isinstance(value, Mapping):
        lowered = {str(key).lower(): key for key in value}
        parts: List[str] = []

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

        for input_key in INPUT_KEYS:
            original_key = lowered.get(input_key)
            if original_key is not None:
                parts.extend(collect_text_parts(value[original_key], input_key))
        if parts:
            return parts

        return [stable_json(value)]

    return [value_to_text(value)]


def strip_label_like_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: Dict[str, Any] = {}
        for key, child in value.items():
            if str(key).lower() in LOWER_LABEL_KEYS:
                continue
            cleaned[str(key)] = strip_label_like_keys(child)
        return cleaned
    if isinstance(value, list):
        return [strip_label_like_keys(item) for item in value]
    return value


def extract_input_text(record: Mapping[str, Any], label_source: Optional[str]) -> Optional[str]:
    # Changed: use the full top-level records JSON for labeled trajectory examples.
    # Why: individual step fields must not replace the complete trajectory unit.
    trajectory_text = records_trajectory_input_text(record)
    if trajectory_text is not None:
        return trajectory_text

    parts: List[str] = []
    for path, value in find_key_matches(record, INPUT_KEYS):
        if label_source is not None and path_to_string(path) == label_source:
            continue
        parts.extend(collect_text_parts(value, str(path[-1])))

    text = "\n".join(part for part in parts if part).strip()
    if text:
        return text

    fallback = strip_label_like_keys(record)
    fallback_text = stable_json(fallback).strip()
    if fallback_text and fallback_text not in {"{}", "[]", "null"}:
        return fallback_text
    return None


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
    return LENGTH_BINS[-1][2]


# 변경: reference eligible corpus와 candidate length distribution 비교 유틸을 추가한다.
# 이유: build 단계에서 optional selector가 validate와 같은 length-bin 기준을 사용해야 하기 때문이다.
def value_for_key(record: Mapping[str, Any], key: str) -> Any:
    lowered = {str(original).lower(): original for original in record}
    original = lowered.get(key.lower())
    if original is None:
        return None
    return record[original]


def extract_reference_text_value(record: Mapping[str, Any]) -> Any:
    for key in INPUT_KEYS:
        value = value_for_key(record, key)
        if value is not None:
            return value
    for key in ("records", "steps"):
        value = value_for_key(record, key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, (list, dict)) and value:
            return value
    return None


def extract_reference_length_bin(record: Mapping[str, Any]) -> Optional[str]:
    # 변경: reference text가 있으면 저장된 length_bin보다 텍스트 기반 재계산을 우선한다.
    # 이유: validate가 텍스트 기준으로 reference length distribution을 산출하므로 build balancer의 목표분포를 맞추기 위해서다.
    text_value = extract_reference_text_value(record)
    if text_value is not None:
        return length_bin(token_count(value_to_text(text_value)))

    value = value_for_key(record, "length_bin")
    if scalar_to_text(value) is not None:
        return str(value).strip()
    return None


def lower_key_set(record: Mapping[str, Any]) -> set:
    return {str(key).lower() for key in record}


def has_reference_length_source(record: Mapping[str, Any]) -> bool:
    keys = lower_key_set(record)
    if "length_bin" in keys:
        return True
    if keys & {key.lower() for key in INPUT_KEYS}:
        return True
    for key in ("records", "steps"):
        value = value_for_key(record, key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and value:
            return True
    return False


# 변경: auxiliary score/report record를 schema-like identity/label record보다 먼저 판정한다.
# 이유: sample_id/label/source가 있어도 length source가 없으면 reference length balancing의 eligible corpus가 아니기 때문이다.
def classify_reference_record(record: Mapping[str, Any], auxiliary_path_reason: Optional[str] = None) -> Tuple[bool, str]:
    keys = lower_key_set(record)
    if has_reference_length_source(record):
        return True, "length_source_present"

    auxiliary_hits = sorted(keys & set(REFERENCE_AUXILIARY_KEYS))
    if auxiliary_hits:
        return False, "auxiliary_record_keys:" + ",".join(auxiliary_hits[:5])
    if auxiliary_path_reason:
        return False, auxiliary_path_reason

    label_like = keys & {key.lower() for key in LABEL_KEYS}
    identity_like = keys & ({key.lower() for key in ID_KEYS} | {key.lower() for key in SOURCE_KEYS} | {key.lower() for key in TEMPLATE_KEYS} | {key.lower() for key in MUTATION_KEYS} | {key.lower() for key in GROUP_KEYS} | {"content_hash", "split", "path", "row"})
    example_hits = sorted(keys & ({key.lower() for key in ID_KEYS} | {key.lower() for key in LABEL_KEYS} | {key.lower() for key in SOURCE_KEYS} | {key.lower() for key in TEMPLATE_KEYS} | {key.lower() for key in MUTATION_KEYS} | {key.lower() for key in GROUP_KEYS} | {"content_hash", "split", "path", "row"}))

    if label_like and identity_like:
        return True, "example_schema_keys"
    if len(example_hits) >= 3:
        return True, "example_schema_keys"
    return False, "no_reference_example_fields"


def collect_reference_files(path: Path) -> List[Path]:
    if not path.exists():
        fail(f"length balance reference path does not exist: {path}")
    if path.is_dir():
        files = sorted(child for child in path.rglob("*") if child.is_file() and child.suffix.lower() in JSON_SUFFIXES)
    elif path.is_file() and path.suffix.lower() in JSON_SUFFIXES:
        files = [path]
    else:
        fail(f"length balance reference must be a .json/.jsonl file or directory: {path}")
    if not files:
        fail(f"length balance reference contains no .json/.jsonl files: {path}")
    return files


def iter_reference_objects(payload: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from iter_reference_objects(item)
        return
    if not isinstance(payload, dict):
        return

    lowered = {str(key).lower(): key for key in payload}
    yielded_container = False
    for container_key in CONTAINER_KEYS:
        original_key = lowered.get(container_key)
        if original_key is None:
            continue
        value = payload[original_key]
        if isinstance(value, (list, dict)):
            yielded_container = True
            yield from iter_reference_objects(value)
    if yielded_container:
        return

    if payload and all(isinstance(value, (dict, list)) for value in payload.values()):
        for value in payload.values():
            yield from iter_reference_objects(value)
        return
    yield payload


def reference_path_auxiliary_reason(path: Path) -> Optional[str]:
    stem = path.stem.lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", stem) if token}
    for term in REFERENCE_AUXILIARY_PATH_TERMS:
        if term in tokens or term in stem:
            return f"auxiliary_path:{term}"
    return None


def new_reference_skip_summary() -> Dict[str, Any]:
    return {
        "file_count": 0,
        "record_count": 0,
        "file_reason_counts": Counter(),
        "record_reason_counts": Counter(),
        "file_examples": [],
        "record_examples": [],
    }


def add_reference_skip(
    summary: Dict[str, Any],
    kind: str,
    path: Path,
    reason: str,
    line: Optional[int] = None,
    record_index: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    if kind == "file":
        summary["file_count"] += 1
        summary["file_reason_counts"][reason] += 1
        examples = summary["file_examples"]
    else:
        summary["record_count"] += 1
        summary["record_reason_counts"][reason] += 1
        examples = summary["record_examples"]

    if len(examples) >= REFERENCE_SKIP_EXAMPLE_LIMIT:
        return
    item: Dict[str, Any] = {"path": str(path), "reason": reason}
    if line is not None:
        item["line"] = line
    if record_index is not None:
        item["record_index"] = record_index
    if detail:
        item["detail"] = detail
    examples.append(item)


def finalize_reference_skip_summary(summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "file_count": int(summary.get("file_count", 0)),
        "record_count": int(summary.get("record_count", 0)),
        "file_reason_counts": counter_to_sorted_dict(summary.get("file_reason_counts", Counter())),
        "record_reason_counts": counter_to_sorted_dict(summary.get("record_reason_counts", Counter())),
        "file_examples": list(summary.get("file_examples", [])),
        "record_examples": list(summary.get("record_examples", [])),
    }


def load_length_balance_reference(path: Path) -> ReferenceLoadResult:
    counts: Counter = Counter()
    errors: List[Dict[str, Any]] = []
    skipped = new_reference_skip_summary()
    eligible_records = 0

    for file_path in collect_reference_files(path):
        file_seen_records = 0
        file_eligible_records = 0
        pending_parse_errors: List[Dict[str, Any]] = []
        auxiliary_path_reason = reference_path_auxiliary_reason(file_path)

        if file_path.suffix.lower() == ".jsonl":
            with file_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        pending_parse_errors.append({"path": str(file_path), "line": line_number, "error": f"invalid JSONL: {exc}"})
                        continue
                    for record in iter_reference_objects(payload):
                        file_seen_records += 1
                        # 변경: path-level auxiliary context를 record classifier에 전달한다.
                        # 이유: auxiliary path의 identity-only rows를 malformed eligible reference로 세지 않기 위해서다.
                        eligible, reason = classify_reference_record(record, auxiliary_path_reason=auxiliary_path_reason)
                        if not eligible:
                            add_reference_skip(skipped, "record", file_path, reason, line=line_number, record_index=file_seen_records)
                            continue
                        eligible_records += 1
                        file_eligible_records += 1
                        bin_label = extract_reference_length_bin(record)
                        if bin_label is None:
                            errors.append({"path": str(file_path), "line": line_number, "record_index": file_seen_records, "error": "eligible reference record missing length_bin/input/text", "eligibility": reason})
                        else:
                            counts[bin_label] += 1
        else:
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except json.JSONDecodeError as exc:
                if auxiliary_path_reason:
                    add_reference_skip(skipped, "file", file_path, f"invalid_json_auxiliary_file:{auxiliary_path_reason}", detail=str(exc))
                else:
                    errors.append({"path": str(file_path), "line": None, "error": f"invalid JSON: {exc}"})
                continue
            for record in iter_reference_objects(payload):
                file_seen_records += 1
                # 변경: path-level auxiliary context를 record classifier에 전달한다.
                # 이유: auxiliary path의 identity-only rows를 malformed eligible reference로 세지 않기 위해서다.
                eligible, reason = classify_reference_record(record, auxiliary_path_reason=auxiliary_path_reason)
                if not eligible:
                    add_reference_skip(skipped, "record", file_path, reason, record_index=file_seen_records)
                    continue
                eligible_records += 1
                file_eligible_records += 1
                bin_label = extract_reference_length_bin(record)
                if bin_label is None:
                    errors.append({"path": str(file_path), "line": None, "record_index": file_seen_records, "error": "eligible reference record missing length_bin/input/text", "eligibility": reason})
                else:
                    counts[bin_label] += 1

        if pending_parse_errors:
            if file_eligible_records > 0 or auxiliary_path_reason is None:
                errors.extend(pending_parse_errors)
            else:
                add_reference_skip(skipped, "file", file_path, f"invalid_jsonl_auxiliary_file:{auxiliary_path_reason}", detail=f"parse_errors={len(pending_parse_errors)}")
        if file_seen_records == 0:
            reason = auxiliary_path_reason or "no_reference_objects"
            add_reference_skip(skipped, "file", file_path, reason, detail="records_seen=0")
        elif file_eligible_records == 0:
            reason = auxiliary_path_reason or "no_eligible_reference_records"
            add_reference_skip(skipped, "file", file_path, reason, detail=f"records_seen={file_seen_records}")

    return ReferenceLoadResult(
        length_counts=counts,
        errors=errors,
        eligible_records=eligible_records,
        skipped=finalize_reference_skip_summary(skipped),
    )


def distribution(counter: Counter, labels: Sequence[str]) -> List[float]:
    total = sum(counter.get(label, 0) for label in labels)
    if total <= 0:
        return [0.0 for _ in labels]
    return [counter.get(label, 0) / total for label in labels]


def kl_divergence(left: Sequence[float], right: Sequence[float]) -> float:
    total = 0.0
    for left_value, right_value in zip(left, right):
        if left_value == 0.0:
            continue
        if right_value == 0.0:
            return math.inf
        total += left_value * math.log(left_value / right_value)
    return total


def jensen_shannon_divergence(left_counter: Counter, right_counter: Counter) -> Optional[float]:
    labels = sorted(set(left_counter) | set(right_counter))
    if not labels or not left_counter or not right_counter:
        return None
    left = distribution(left_counter, labels)
    right = distribution(right_counter, labels)
    midpoint = [(left_value + right_value) / 2.0 for left_value, right_value in zip(left, right)]
    return 0.5 * kl_divergence(left, midpoint) + 0.5 * kl_divergence(right, midpoint)


def normalized_input_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def content_hash(input_text: str, label: str) -> str:
    normalized = normalized_input_for_hash(input_text)
    payload = f"{normalized}\x1f{label}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Changed: expose input-only semantic hashes for conflict and split audits.
# Why: content_hash includes the label and cannot detect pass/fail conflict for identical inputs.
def input_hash_no_label(input_text: str) -> str:
    normalized = normalized_input_for_hash(input_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# Changed: compute a single manifest prompt schema hash from the renderer contract.
# Why: row input size/content changes must not create many prompt schema identities.
def prompt_schema_hash() -> str:
    return hashlib.sha256(stable_json(PROMPT_RENDERER_CONTRACT).encode("utf-8")).hexdigest()


# Changed: derive a stable semantic component from source and template.
# Why: mutation_family is often base, so downstream coverage audits need a more useful component key.
def family_component_for_record(source: str, template_id: str) -> str:
    basis = "\x1f".join((source, template_id))
    return stable_id("family", basis, size=16)


def blocklist_matches(path: str, source: str) -> Tuple[str, ...]:
    haystack = f"{path}\n{source}".lower()
    return tuple(term for term in BLOCKLIST_TERMS if term in haystack)


# 변경: public/rule signature 매칭을 token/공백/compact 형태로 통일한다.
# 이유: source/path/sample_id 메타데이터가 snake/kebab/camel 형식으로 섞여도 같은 gate가 적용되어야 하기 때문이다.
def scan_text_forms(value: Any) -> Tuple[str, str, str, set]:
    text = value_to_text(value).lower()
    spaced = re.sub(r"[^a-z0-9]+", " ", text).strip()
    compact = re.sub(r"[^a-z0-9]+", "", text)
    tokens = set(spaced.split())
    return text, spaced, compact, tokens


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


# 변경: raw row의 public/eval holdout provenance를 manifest 생성 전에 탐지한다.
# 이유: public 20/leaderboard 데이터는 build에서 제외되어야 하며 validate에만 의존하면 raw metadata가 유실될 수 있기 때문이다.
def public_holdout_matches(raw: RawRecord, source: str, sample_id: str) -> Tuple[str, ...]:
    matches: List[str] = []
    for location, value in (("path", raw.path), ("source", source), ("sample_id", sample_id)):
        matched = match_pattern(value, PUBLIC_HOLDOUT_PATTERNS)
        if matched:
            matches.append(f"{location}:{matched}")
    for key_path, value in find_key_matches(raw.data, PUBLIC_HOLDOUT_METADATA_KEYS):
        matched_key = match_pattern(path_to_string(key_path), PUBLIC_HOLDOUT_PATTERNS)
        matched_value = match_pattern(value, PUBLIC_HOLDOUT_PATTERNS)
        if matched_key:
            matches.append(f"{path_to_string(key_path)}:{matched_key}")
        if matched_value:
            matches.append(f"{path_to_string(key_path)}:{matched_value}")
        if len(matches) >= 10:
            break
    return tuple(dict.fromkeys(matches))


def rule_context_matches(record: Mapping[str, Any]) -> Tuple[str, ...]:
    raw = stable_json(record).lower()
    spaced = re.sub(r"[^a-z0-9]+", " ", raw)
    compact = re.sub(r"[^a-z0-9]+", "", raw)

    matches: List[str] = []
    for term in RULE_CONTEXT_TERMS:
        lowered = term.lower()
        lowered_spaced = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        lowered_compact = re.sub(r"[^a-z0-9]+", "", lowered)
        if lowered in raw or lowered_spaced in spaced or lowered_compact in compact:
            matches.append(term)
    return tuple(matches)


def source_for_record(raw: RawRecord) -> str:
    source_value = first_scalar_value(raw.data, SOURCE_KEYS)
    source = scalar_to_text(source_value)
    if source:
        return source
    return Path(raw.path).stem or "unknown"


def sample_id_for_record(raw: RawRecord, input_text: Optional[str], label: Optional[str]) -> str:
    value = first_scalar_value(raw.data, ID_KEYS)
    sample_id = scalar_to_text(value)
    if sample_id:
        return sample_id
    basis = f"{raw.path}\x1f{raw.row}\x1f{input_text or ''}\x1f{label or ''}"
    return stable_id("sample", basis, size=16)


def template_id_for_record(record: Mapping[str, Any], input_text: str) -> str:
    value = first_scalar_value(record, TEMPLATE_KEYS)
    if value is not None:
        identifier = identifier_from_value("tmpl", value)
        if identifier:
            return identifier
    return stable_id("tmpl", normalize_template_text(input_text))


def mutation_family_for_record(record: Mapping[str, Any]) -> str:
    value = first_scalar_value(record, MUTATION_KEYS)
    if value is None:
        return "base"
    return identifier_from_value("mut", value) or "base"


def group_id_for_record(record: Mapping[str, Any], source: str, template_id: str, mutation_family: str) -> str:
    value = first_scalar_value(record, GROUP_KEYS)
    if value is not None:
        identifier = identifier_from_value("grp", value)
        if identifier:
            return identifier
    basis = "\x1f".join((source, template_id, mutation_family))
    return stable_id("grp", basis, size=16)


# 변경: filtering과 row materialization을 한 경로에서 수행한다.
# 이유: exclusion reason, blocklisted inclusion 표시, label provenance, content hash가 같은 판정 기준을 공유해야 하기 때문이다.
def build_manifest_records(
    raw_records: Sequence[RawRecord],
    include_blocklisted: bool,
) -> Tuple[List[ManifestRecord], Counter, List[Rejection], List[Dict[str, Any]], Counter]:
    candidates: List[ManifestRecord] = []
    excluded_counts: Counter = Counter()
    rejection_examples: List[Rejection] = []
    blocklisted_included_counts: Counter = Counter()

    for index, raw in enumerate(raw_records):
        source = source_for_record(raw)
        sample_hint = sample_id_for_record(raw, None, None)

        # 변경: public/eval holdout provenance를 clean 후보 생성 전에 차단한다.
        # 이유: public 20/leaderboard row는 LLM supervised 학습 데이터로 직접 쓰면 안 되기 때문이다.
        public_matches = public_holdout_matches(raw, source, sample_hint)
        if public_matches:
            excluded_counts["public_holdout"] += 1
            append_rejection(
                rejection_examples,
                Rejection("public_holdout", raw.path, raw.row, sample_hint, ", ".join(public_matches)),
            )
            continue

        rule_matches = rule_context_matches(raw.data)
        if rule_matches:
            excluded_counts["rule_context"] += 1
            append_rejection(
                rejection_examples,
                Rejection("rule_context", raw.path, raw.row, sample_hint, ", ".join(rule_matches)),
            )
            continue

        block_matches = blocklist_matches(raw.path, source)
        if block_matches and not include_blocklisted:
            excluded_counts["blocklisted"] += 1
            append_rejection(
                rejection_examples,
                Rejection("blocklisted", raw.path, raw.row, sample_hint, ", ".join(block_matches)),
            )
            continue

        # Changed: drop score/report-only rows before fallback input materialization.
        # Why: auxiliary IFD/metrics metadata must not become supervised training text.
        auxiliary_reason = auxiliary_training_row_reason(raw.data)
        if auxiliary_reason is not None:
            excluded_counts["auxiliary_record"] += 1
            append_rejection(
                rejection_examples,
                Rejection("auxiliary_record", raw.path, raw.row, sample_hint, auxiliary_reason),
            )
            continue

        label, label_source = extract_label(raw.data)
        if label is None or label_source is None:
            excluded_counts["unknown_label"] += 1
            append_rejection(
                rejection_examples,
                Rejection("unknown_label", raw.path, raw.row, sample_hint, "no pass/fail label candidate"),
            )
            continue

        input_text = extract_input_text(raw.data, label_source)
        sample_id = sample_id_for_record(raw, input_text, label)
        if input_text is None:
            excluded_counts["missing_input"] += 1
            append_rejection(
                rejection_examples,
                Rejection("missing_input", raw.path, raw.row, sample_id, "no input/prompt/text-like content"),
            )
            continue

        template_id = template_id_for_record(raw.data, input_text)
        mutation_family = mutation_family_for_record(raw.data)
        group_id = group_id_for_record(raw.data, source, template_id, mutation_family)
        input_tokens = token_count(input_text)
        digest = content_hash(input_text, label)
        input_digest = input_hash_no_label(input_text)
        prompt_digest = prompt_schema_hash()
        family_component = family_component_for_record(source, template_id)
        if block_matches:
            for term in block_matches:
                blocklisted_included_counts[term] += 1

        candidates.append(
            ManifestRecord(
                index=index,
                sample_id=sample_id,
                input_text=input_text,
                label=label,
                source=source,
                label_source=label_source,
                template_id=template_id,
                mutation_family=mutation_family,
                length_bin=length_bin(input_tokens),
                input_token_count=input_tokens,
                content_hash=digest,
                input_hash_no_label=input_digest,
                parse_status="full_trajectory",
                metadata_only=False,
                prompt_schema_version=PROMPT_SCHEMA_VERSION,
                prompt_schema_hash=prompt_digest,
                family_component=family_component,
                group_id=group_id,
                path=raw.path,
                row=raw.row,
                blocklisted=bool(block_matches),
                blocklist_matches=block_matches,
            )
        )

    candidates, label_conflict_groups = remove_input_label_conflicts(candidates)
    label_conflict_count = sum(group["count"] for group in label_conflict_groups)
    if label_conflict_count:
        excluded_counts["label_conflict"] += label_conflict_count
        for group in label_conflict_groups[:50]:
            append_rejection(
                rejection_examples,
                Rejection(
                    "label_conflict",
                    group["paths"][0],
                    group["rows"][0],
                    group["sample_ids"][0],
                    f"input_hash_no_label={group['input_hash_no_label']} labels={','.join(group['labels'])} count={group['count']}",
                ),
            )

    deduped, duplicate_groups = deduplicate_records(candidates)
    duplicate_count = sum(group["duplicate_count"] for group in duplicate_groups)
    if duplicate_count:
        excluded_counts["duplicate"] += duplicate_count
        for group in duplicate_groups[:50]:
            append_rejection(
                rejection_examples,
                Rejection(
                    "duplicate",
                    group["kept_path"],
                    group["kept_row"],
                    group["kept_sample_id"],
                    f"content_hash={group['content_hash']} duplicate_count={group['duplicate_count']}",
                ),
            )

    return deduped, excluded_counts, rejection_examples, duplicate_groups, blocklisted_included_counts


def append_rejection(rejections: List[Rejection], rejection: Rejection, limit: int = 100) -> None:
    if len(rejections) < limit:
        rejections.append(rejection)


def deduplicate_records(records: Sequence[ManifestRecord]) -> Tuple[List[ManifestRecord], List[Dict[str, Any]]]:
    groups: DefaultDict[str, List[ManifestRecord]] = defaultdict(list)
    for record in records:
        groups[record.content_hash].append(record)

    deduped: List[ManifestRecord] = []
    duplicate_groups: List[Dict[str, Any]] = []
    for record in records:
        members = groups[record.content_hash]
        if members[0] is record:
            deduped.append(record)

    for digest, members in sorted(groups.items(), key=lambda item: item[0]):
        if len(members) <= 1:
            continue
        kept = members[0]
        duplicate_groups.append(
            {
                "content_hash": digest,
                "count": len(members),
                "duplicate_count": len(members) - 1,
                "label": kept.label,
                "kept_sample_id": kept.sample_id,
                "kept_path": kept.path,
                "kept_row": kept.row,
                "sample_ids": [member.sample_id for member in members[:20]],
                "paths": sorted({member.path for member in members}),
                "rows": [member.row for member in members[:20]],
            }
        )
    return deduped, duplicate_groups


# Changed: quarantine all rows whose identical input has conflicting labels.
# Why: label-including content_hash cannot catch pass/fail conflicts for the same trajectory.
def remove_input_label_conflicts(records: Sequence[ManifestRecord]) -> Tuple[List[ManifestRecord], List[Dict[str, Any]]]:
    groups: DefaultDict[str, List[ManifestRecord]] = defaultdict(list)
    for record in records:
        groups[record.input_hash_no_label].append(record)

    conflict_hashes = {
        digest
        for digest, members in groups.items()
        if len({member.label for member in members}) > 1
    }
    kept = [record for record in records if record.input_hash_no_label not in conflict_hashes]

    conflict_groups: List[Dict[str, Any]] = []
    for digest in sorted(conflict_hashes):
        members = groups[digest]
        conflict_groups.append(
            {
                "input_hash_no_label": digest,
                "count": len(members),
                "labels": sorted({member.label for member in members}),
                "sample_ids": [member.sample_id for member in members[:20]],
                "paths": sorted({member.path for member in members}),
                "rows": [member.row for member in members[:20]],
            }
        )
    return kept, conflict_groups


def split_count(total: int, fraction: float) -> int:
    if total <= 0 or fraction <= 0.0:
        return 0
    if fraction >= 1.0:
        return total
    count = int(round(total * fraction))
    return max(1, min(total, count))


# 변경: split은 record가 아니라 group_id 목록을 셔플한 뒤 배정한다.
# 이유: 같은 group_id가 train/hidden/calibration에 동시에 들어가는 leakage를 구조적으로 막기 위해서다.
def assign_splits(
    records: Sequence[ManifestRecord],
    hidden_fraction: float,
    calibration_fraction: float,
    seed: int,
) -> Dict[str, str]:
    groups = sorted({record.group_id for record in records})
    rng = random.Random(seed)
    rng.shuffle(groups)

    total = len(groups)
    hidden_count = split_count(total, hidden_fraction)
    calibration_count = split_count(total, calibration_fraction)

    while hidden_count + calibration_count > total:
        if calibration_count >= hidden_count and calibration_count > 0:
            calibration_count -= 1
        elif hidden_count > 0:
            hidden_count -= 1
        else:
            break

    if hidden_fraction + calibration_fraction < 1.0 and total > 1 and hidden_count + calibration_count >= total:
        if calibration_count > 0 and calibration_fraction <= hidden_fraction:
            calibration_count -= 1
        elif hidden_count > 0:
            hidden_count -= 1

    hidden_groups = set(groups[:hidden_count])
    calibration_groups = set(groups[hidden_count : hidden_count + calibration_count])
    split_by_group: Dict[str, str] = {}
    for group in groups:
        if group in hidden_groups:
            split_by_group[group] = "hidden"
        elif group in calibration_groups:
            split_by_group[group] = "calibration"
        else:
            split_by_group[group] = "train"
    return split_by_group


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


def top_share(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return max(counter.values()) / total


# 변경: dedup 후 split 전 group-preserving length selector를 추가한다.
# 이유: length distribution 보정이 split leakage를 만들지 않고 기존 label/template gates를 깨지 않게 하기 위해서다.
def rounded_metric(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 6)


def length_counts_for_records(records: Sequence[ManifestRecord]) -> Counter:
    return Counter(record.length_bin for record in records)


def group_count_for_records(records: Sequence[ManifestRecord]) -> int:
    return len({record.group_id for record in records})


def length_balance_safety_issue(records: Sequence[ManifestRecord], args: argparse.Namespace) -> Optional[str]:
    if not records:
        return "no_records_remaining"
    label_counts = Counter(record.label for record in records)
    missing_labels = [label for label in ("pass", "fail") if label_counts.get(label, 0) == 0]
    if missing_labels:
        return "label_count_zero:" + ",".join(missing_labels)
    template_counts = Counter(record.template_id for record in records)
    entropy = normalized_entropy(template_counts)
    if entropy < args.min_template_entropy:
        return f"template_entropy_below_min:{round(entropy, 6)}"
    share = top_share(template_counts)
    if share > args.max_top_template_share:
        return f"top_template_share_above_max:{round(share, 6)}"
    return None


def length_balance_disabled_report(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "enabled": False,
        "applied": False,
        "target_reached": None,
        "reason": "disabled",
        "config": {
            "reference": args.length_balance_reference,
            "target_jsd": args.length_balance_target_jsd,
            "max_drop_fraction": args.length_balance_max_drop_fraction,
        },
        "reference": None,
        "before": None,
        "after": None,
        "dropped_group_count": 0,
        "dropped_record_count": 0,
        "dropped_groups": [],
    }


def select_length_balanced_records(records: Sequence[ManifestRecord], args: argparse.Namespace) -> LengthBalanceOutcome:
    if not args.length_balance_reference:
        return LengthBalanceOutcome(records=list(records), report=length_balance_disabled_report(args))

    original_records = list(records)
    reference_path = Path(args.length_balance_reference)
    try:
        reference = load_length_balance_reference(reference_path)
        reference_error = None
    except ValueError as exc:
        reference = ReferenceLoadResult(Counter(), [{"path": str(reference_path), "line": None, "error": str(exc)}], 0, finalize_reference_skip_summary(new_reference_skip_summary()))
        reference_error = str(exc)

    before_counts = length_counts_for_records(original_records)
    before_jsd = jensen_shannon_divergence(before_counts, reference.length_counts)
    max_drop_records = int(math.floor(len(original_records) * args.length_balance_max_drop_fraction))
    base_report: Dict[str, Any] = {
        "enabled": True,
        "applied": False,
        "target_reached": False,
        "reason": "",
        "config": {
            "reference": str(reference_path),
            "target_jsd": args.length_balance_target_jsd,
            "max_drop_fraction": args.length_balance_max_drop_fraction,
            "max_drop_records": max_drop_records,
        },
        "reference": {
            "eligible_records": reference.eligible_records,
            "length_bins": counter_to_sorted_dict(reference.length_counts),
            "error_count": len(reference.errors),
            "errors": reference.errors[:50],
            "skipped": reference.skipped,
            "load_error": reference_error,
        },
        "before": {
            "record_count": len(original_records),
            "group_count": group_count_for_records(original_records),
            "length_bins": {label: before_counts.get(label, 0) for _, _, label in LENGTH_BINS},
            "jsd": rounded_metric(before_jsd),
        },
        "after": {
            "record_count": len(original_records),
            "group_count": group_count_for_records(original_records),
            "length_bins": {label: before_counts.get(label, 0) for _, _, label in LENGTH_BINS},
            "jsd": rounded_metric(before_jsd),
        },
        "dropped_group_count": 0,
        "dropped_record_count": 0,
        "dropped_groups": [],
        "candidate_rejected_reason_counts": {},
        "best_attempt": None,
    }

    if reference.errors:
        base_report["reason"] = "reference_errors"
        return LengthBalanceOutcome(records=original_records, report=base_report)
    if reference.eligible_records <= 0:
        base_report["reason"] = "reference_has_no_eligible_records"
        return LengthBalanceOutcome(records=original_records, report=base_report)
    if before_jsd is None:
        base_report["reason"] = "length_jsd_unavailable"
        return LengthBalanceOutcome(records=original_records, report=base_report)
    if before_jsd <= args.length_balance_target_jsd:
        base_report["target_reached"] = True
        base_report["reason"] = "already_within_target"
        return LengthBalanceOutcome(records=original_records, report=base_report)

    initial_issue = length_balance_safety_issue(original_records, args)
    if initial_issue:
        base_report["reason"] = "initial_candidates_unsafe:" + initial_issue
        return LengthBalanceOutcome(records=original_records, report=base_report)
    if max_drop_records <= 0:
        base_report["reason"] = "max_drop_fraction_allows_no_records"
        return LengthBalanceOutcome(records=original_records, report=base_report)

    records_by_group: DefaultDict[str, List[ManifestRecord]] = defaultdict(list)
    for record in original_records:
        records_by_group[record.group_id].append(record)

    current_records = original_records
    current_jsd = before_jsd
    dropped_groups: List[str] = []
    dropped_records = 0
    rejected_reasons: Counter = Counter()

    while current_jsd > args.length_balance_target_jsd and dropped_records < max_drop_records:
        current_group_set = {record.group_id for record in current_records}
        best_group: Optional[str] = None
        best_records: Optional[List[ManifestRecord]] = None
        best_jsd: Optional[float] = None

        for group_id in sorted(current_group_set):
            group_records = records_by_group[group_id]
            next_dropped_records = dropped_records + len(group_records)
            if next_dropped_records > max_drop_records:
                rejected_reasons["max_drop_records"] += 1
                continue

            candidate_records = [record for record in current_records if record.group_id != group_id]
            issue = length_balance_safety_issue(candidate_records, args)
            if issue:
                rejected_reasons[issue] += 1
                continue

            candidate_jsd = jensen_shannon_divergence(length_counts_for_records(candidate_records), reference.length_counts)
            if candidate_jsd is None:
                rejected_reasons["candidate_jsd_unavailable"] += 1
                continue
            if candidate_jsd >= current_jsd - 1e-12:
                rejected_reasons["no_jsd_improvement"] += 1
                continue
            if best_jsd is None or candidate_jsd < best_jsd - 1e-12 or (abs(candidate_jsd - best_jsd) <= 1e-12 and group_id < (best_group or group_id)):
                best_group = group_id
                best_records = candidate_records
                best_jsd = candidate_jsd

        if best_group is None or best_records is None or best_jsd is None:
            break

        dropped_groups.append(best_group)
        dropped_records += len(records_by_group[best_group])
        current_records = best_records
        current_jsd = best_jsd

    target_reached = current_jsd <= args.length_balance_target_jsd
    base_report["candidate_rejected_reason_counts"] = counter_to_sorted_dict(rejected_reasons)
    base_report["best_attempt"] = {
        "record_count": len(current_records),
        "group_count": group_count_for_records(current_records),
        "jsd": rounded_metric(current_jsd),
        "dropped_group_count": len(dropped_groups),
        "dropped_record_count": dropped_records,
        "dropped_groups": dropped_groups[:50],
    }

    if not target_reached:
        base_report["reason"] = "target_not_reached_within_constraints"
        return LengthBalanceOutcome(records=original_records, report=base_report)

    after_counts = length_counts_for_records(current_records)
    base_report["applied"] = True
    base_report["target_reached"] = True
    base_report["reason"] = "target_reached"
    base_report["after"] = {
        "record_count": len(current_records),
        "group_count": group_count_for_records(current_records),
        "length_bins": {label: after_counts.get(label, 0) for _, _, label in LENGTH_BINS},
        "jsd": rounded_metric(current_jsd),
    }
    base_report["dropped_group_count"] = len(dropped_groups)
    base_report["dropped_record_count"] = dropped_records
    base_report["dropped_groups"] = dropped_groups[:50]
    return LengthBalanceOutcome(records=current_records, report=base_report)


def leakage_groups(records: Sequence[ManifestRecord], split_by_group: Mapping[str, str]) -> List[str]:
    groups: DefaultDict[str, set] = defaultdict(set)
    for record in records:
        groups[record.group_id].add(split_by_group[record.group_id])
    return sorted(group for group, splits in groups.items() if len(splits) > 1)


def counter_to_sorted_dict(counter: Counter) -> Dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter)}


def rejection_to_dict(rejection: Rejection) -> Dict[str, Any]:
    return {
        "reason": rejection.reason,
        "path": rejection.path,
        "row": rejection.row,
        "sample_id": rejection.sample_id,
        "detail": rejection.detail,
    }


def manifest_row(record: ManifestRecord, split: str) -> Dict[str, Any]:
    return {
        "sample_id": record.sample_id,
        "input": record.input_text,
        "label": record.label,
        "source": record.source,
        "label_source": record.label_source,
        "template_id": record.template_id,
        "mutation_family": record.mutation_family,
        "length_bin": record.length_bin,
        "input_token_count": record.input_token_count,
        "format_version": FORMAT_VERSION,
        "content_hash": record.content_hash,
        "input_hash_no_label": record.input_hash_no_label,
        "parse_status": record.parse_status,
        "metadata_only": record.metadata_only,
        "prompt_schema_version": record.prompt_schema_version,
        "prompt_schema_hash": record.prompt_schema_hash,
        "family_component": record.family_component,
        "group_id": record.group_id,
        "split": split,
        "path": record.path,
        "row": record.row,
    }


def report_paths(requested: str) -> Tuple[Path, Path]:
    base = Path(requested)
    if base.suffix == ".json":
        return base, base.with_suffix(".md")
    if base.suffix == ".md":
        return base.with_suffix(".json"), base
    return base.with_suffix(".json"), base.with_suffix(".md")


def build_report(
    records: Sequence[ManifestRecord],
    raw_record_count: int,
    excluded_counts: Counter,
    rejection_examples: Sequence[Rejection],
    duplicate_groups: Sequence[Mapping[str, Any]],
    blocklisted_included_counts: Counter,
    discovery: DiscoveryResult,
    input_paths: Sequence[Path],
    output_path: Path,
    report_json_path: Path,
    report_md_path: Path,
    split_by_group: Mapping[str, str],
    length_balance_report: Mapping[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    label_counts = Counter(record.label for record in records)
    source_counts = Counter(record.source for record in records)
    template_counts = Counter(record.template_id for record in records)
    length_counts = Counter(record.length_bin for record in records)
    record_split_counts = Counter(split_by_group[record.group_id] for record in records)
    group_split_counts = Counter(split_by_group.values())
    leakage = leakage_groups(records, split_by_group)
    entropy = normalized_entropy(template_counts)
    share = top_share(template_counts)
    manifest_duplicate_count = sum(count - 1 for count in Counter(record.content_hash for record in records).values() if count > 1)
    selected_public_holdout_hits: List[Dict[str, Any]] = []
    selected_rule_context_hits: List[Dict[str, Any]] = []

    # 변경: 최종 선택 row에도 LLM-only 누수 gate를 한 번 더 건다.
    # 이유: raw 필터가 놓친 public/rule provenance가 있으면 build report와 exit code가 즉시 실패해야 하기 때문이다.
    for record in records:
        public_matches: List[str] = []
        for field_name, value in (("sample_id", record.sample_id), ("source", record.source), ("path", record.path)):
            matched = match_pattern(value, PUBLIC_HOLDOUT_PATTERNS)
            if matched:
                public_matches.append(f"{field_name}:{matched}")
        if public_matches:
            selected_public_holdout_hits.append({"sample_id": record.sample_id, "matches": public_matches[:10]})

        rule_matches = rule_context_matches(
            {
                "sample_id": record.sample_id,
                "input": record.input_text,
                "source": record.source,
                "path": record.path,
                "label_source": record.label_source,
            }
        )
        if rule_matches:
            selected_rule_context_hits.append({"sample_id": record.sample_id, "matches": list(rule_matches[:10])})

    gate_status: Dict[str, Dict[str, Any]] = {
        "selected_records_gt_0": {
            "value": len(records),
            "threshold": "> 0",
            "passed": len(records) > 0,
        },
        "group_leakage_0": {
            "value": len(leakage),
            "threshold": 0,
            "passed": len(leakage) == 0,
        },
        "manifest_exact_duplicate_0": {
            "value": manifest_duplicate_count,
            "threshold": 0,
            "passed": manifest_duplicate_count == 0,
        },
        "template_entropy_gte_min": {
            "value": round(entropy, 6),
            "threshold": args.min_template_entropy,
            "passed": entropy >= args.min_template_entropy,
        },
        "top_template_share_lte_max": {
            "value": round(share, 6),
            "threshold": args.max_top_template_share,
            "passed": share <= args.max_top_template_share,
        },
        "public_holdout_selected_0": {
            "value": len(selected_public_holdout_hits),
            "threshold": 0,
            "passed": len(selected_public_holdout_hits) == 0,
        },
        "rule_context_selected_0": {
            "value": len(selected_rule_context_hits),
            "threshold": 0,
            "passed": len(selected_rule_context_hits) == 0,
        },
    }
    # 변경: length balance 결과를 build hard gate에 연결한다.
    # 이유: 선택 실패나 reference 오류가 report overall status에서 드러나야 하기 때문이다.
    if length_balance_report.get("enabled"):
        reference_info = length_balance_report.get("reference") or {}
        after_info = length_balance_report.get("after") or {}
        after_jsd = after_info.get("jsd")
        gate_status["length_balance_reference_errors_0"] = {
            "value": reference_info.get("error_count"),
            "threshold": 0,
            "passed": reference_info.get("error_count") == 0,
        }
        gate_status["length_balance_reference_records_gt_0"] = {
            "value": reference_info.get("eligible_records"),
            "threshold": "> 0",
            "passed": int(reference_info.get("eligible_records") or 0) > 0,
        }
        gate_status["length_balance_jsd_lte_target"] = {
            "value": after_jsd,
            "threshold": args.length_balance_target_jsd,
            "passed": after_jsd is not None and after_jsd <= args.length_balance_target_jsd,
        }

    return {
        "generated_at_kst": datetime.now(KST).isoformat(),
        "format_version": FORMAT_VERSION,
        "config": {
            "input_paths": [str(path) for path in input_paths],
            "output": str(output_path),
            "report_json_out": str(report_json_path),
            "report_md_out": str(report_md_path),
            "hidden_fraction": args.hidden_fraction,
            "calibration_fraction": args.calibration_fraction,
            "seed": args.seed,
            "min_template_entropy": args.min_template_entropy,
            "max_top_template_share": args.max_top_template_share,
            "include_blocklisted": args.include_blocklisted,
            "length_balance_reference": args.length_balance_reference,
            "length_balance_target_jsd": args.length_balance_target_jsd,
            "length_balance_max_drop_fraction": args.length_balance_max_drop_fraction,
        },
        "files": {
            "json_files_loaded": [str(path) for path in discovery.json_files],
            "json_file_count": len(discovery.json_files),
            "skipped_files": discovery.skipped_files,
            "skipped_file_counts": counter_to_sorted_dict(Counter(item["reason"] for item in discovery.skipped_files)),
        },
        "counts": {
            "raw_records": raw_record_count,
            "selected_records": len(records),
            "excluded_records": sum(excluded_counts.values()),
            "excluded_by_reason": counter_to_sorted_dict(excluded_counts),
            "label_counts": counter_to_sorted_dict(label_counts),
            "source_counts": counter_to_sorted_dict(source_counts),
            "split_record_counts": counter_to_sorted_dict(record_split_counts),
            "split_group_counts": counter_to_sorted_dict(group_split_counts),
            "group_count": len(split_by_group),
            "blocklisted_included_records": sum(1 for record in records if record.blocklisted),
            "blocklisted_included_by_term": counter_to_sorted_dict(blocklisted_included_counts),
        },
        "metrics": {
            "normalized_template_entropy": round(entropy, 6),
            "top_template_share": round(share, 6),
            "top_template_count": max(template_counts.values()) if template_counts else 0,
            "template_counts": counter_to_sorted_dict(template_counts),
            "length_bins": {label: length_counts.get(label, 0) for _, _, label in LENGTH_BINS},
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_record_count": sum(int(group.get("duplicate_count", 0)) for group in duplicate_groups),
            "duplicate_groups": list(duplicate_groups),
            "group_leakage_count": len(leakage),
            "group_leakage_keys": leakage[:50],
        },
        "gate_status": gate_status,
        "overall_gate_passed": all(status["passed"] for status in gate_status.values()),
        "selected_gate_violations": {
            "public_holdout_hits": selected_public_holdout_hits[:50],
            "rule_context_hits": selected_rule_context_hits[:50],
        },
        "rejection_examples": [rejection_to_dict(rejection) for rejection in rejection_examples],
        "length_balance": dict(length_balance_report),
    }


def write_outputs(
    records: Sequence[ManifestRecord],
    split_by_group: Mapping[str, str],
    report: Mapping[str, Any],
    output_path: Path,
    report_json_path: Path,
    report_md_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            row = manifest_row(record, split_by_group[record.group_id])
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    with report_json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    with report_md_path.open("w", encoding="utf-8") as handle:
        handle.write(render_markdown(report))


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    metrics = report["metrics"]
    gates = report["gate_status"]
    files = report["files"]
    lines = [
        "# Clean Supervised Manifest 보고서",
        "",
        f"- 생성 시각(KST): {report['generated_at_kst']}",
        f"- 전체 게이트: {'통과' if report['overall_gate_passed'] else '실패'}",
        f"- JSON 로드 파일 수: {files['json_file_count']}",
        f"- 비JSON/기타 skip 파일 수: {sum(files['skipped_file_counts'].values())}",
        f"- 원본/선택/제외 record 수: {counts['raw_records']} / {counts['selected_records']} / {counts['excluded_records']}",
        f"- group 수: {counts['group_count']}",
        f"- blocklisted 포함 record 수: {counts['blocklisted_included_records']}",
        "",
        "## 게이트 상태",
        "",
        "| 항목 | 기준 | 값 | 상태 |",
        "| --- | --- | --- | --- |",
    ]

    for name, status in gates.items():
        state = "통과" if status["passed"] else "실패"
        lines.append(f"| `{name}` | {status['threshold']} | {status['value']} | {state} |")

    lines.extend(
        [
            "",
            "## 핵심 지표",
            "",
            f"- normalized template entropy: {metrics['normalized_template_entropy']}",
            f"- top template share: {metrics['top_template_share']}",
            f"- top template count: {metrics['top_template_count']}",
            f"- duplicate group/record 수: {metrics['duplicate_group_count']} / {metrics['duplicate_record_count']}",
            f"- group leakage 수: {metrics['group_leakage_count']}",
            "",
            "## 제외 사유",
            "",
        ]
    )
    lines.extend(render_counter_lines(counts["excluded_by_reason"]))
    lines.extend(["", "## Label Counts", ""])
    lines.extend(render_counter_lines(counts["label_counts"]))
    lines.extend(["", "## Split Record Counts", ""])
    lines.extend(render_counter_lines(counts["split_record_counts"]))
    lines.extend(["", "## Split Group Counts", ""])
    lines.extend(render_counter_lines(counts["split_group_counts"]))
    lines.extend(["", "## Length Bins", ""])
    lines.extend(render_counter_lines(metrics["length_bins"]))
    lines.extend(["", "## Blocklisted Included By Term", ""])
    lines.extend(render_counter_lines(counts["blocklisted_included_by_term"]))

    length_balance = report.get("length_balance", {})
    if length_balance.get("enabled"):
        before = length_balance.get("before") or {}
        after = length_balance.get("after") or {}
        reference = length_balance.get("reference") or {}
        skipped = reference.get("skipped") or {}
        # 변경: length balance 설정/결과를 Markdown 감사 보고서에 노출한다.
        # 이유: dropped group/record와 reference eligible/skip 현황을 재현 가능하게 남기기 위해서다.
        lines.extend(
            [
                "",
                "## Length Balance",
                "",
                f"- applied: {length_balance.get('applied')}",
                f"- reason: {length_balance.get('reason')}",
                f"- before/after JSD: {before.get('jsd')} / {after.get('jsd')}",
                f"- dropped groups/records: {length_balance.get('dropped_group_count')} / {length_balance.get('dropped_record_count')}",
                f"- reference eligible records: {reference.get('eligible_records')}",
                f"- reference skipped files/records: {skipped.get('file_count', 0)} / {skipped.get('record_count', 0)}",
                f"- reference errors: {reference.get('error_count')}",
            ]
        )
        for value in skipped.get("file_examples", [])[:10]:
            lines.append(f"- skipped file `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")
        for value in skipped.get("record_examples", [])[:10]:
            lines.append(f"- skipped record `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")

    duplicate_groups = metrics["duplicate_groups"]
    if duplicate_groups:
        lines.extend(["", "## Duplicate Groups", ""])
        for group in duplicate_groups[:20]:
            lines.append(
                f"- hash=`{group['content_hash']}`, count={group['count']}, "
                f"kept=`{group['kept_sample_id']}`, paths={group['paths']}"
            )

    selected_gate_violations = report.get("selected_gate_violations", {})
    if selected_gate_violations.get("public_holdout_hits") or selected_gate_violations.get("rule_context_hits"):
        # 변경: 선택 row의 LLM-only hard gate 위반을 Markdown에도 기록한다.
        # 이유: public/rule 누수가 발생하면 KST 아카이브에서 즉시 추적할 수 있어야 하기 때문이다.
        lines.extend(["", "## Selected Gate Violations", ""])
        for key in ("public_holdout_hits", "rule_context_hits"):
            for item in selected_gate_violations.get(key, [])[:20]:
                lines.append(f"- {key}: `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")

    rejection_examples = report["rejection_examples"]
    if rejection_examples:
        lines.extend(["", "## Exclusion Examples", ""])
        for item in rejection_examples[:20]:
            lines.append(
                f"- reason=`{item['reason']}`, path=`{item['path']}`, row={item['row']}, "
                f"sample_id=`{item['sample_id']}`, detail={item['detail']}"
            )

    return "\n".join(lines) + "\n"


def render_counter_lines(counter: Mapping[str, int]) -> List[str]:
    if not counter:
        return ["- 없음"]
    return [f"- `{key}`: {value}" for key, value in counter.items()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    validate_args(args)

    input_paths = flatten_inputs(args.input)
    discovery = discover_json_files(input_paths)
    raw_records = load_raw_records(discovery.json_files)
    records, excluded_counts, rejections, duplicate_groups, blocklisted_included_counts = build_manifest_records(
        raw_records,
        include_blocklisted=args.include_blocklisted,
    )
    # 변경: deduped clean candidates 이후, split 이전에 optional group-preserving length balancing을 수행한다.
    # 이유: group_id 단위 선택만 split으로 전달해 leakage 없는 분포 보정을 보장하기 위해서다.
    length_balance_outcome = select_length_balanced_records(records, args)
    records = length_balance_outcome.records
    split_by_group = assign_splits(records, args.hidden_fraction, args.calibration_fraction, args.seed)

    output_path = Path(args.output)
    report_json_path, report_md_path = report_paths(args.report_out)
    report = build_report(
        records=records,
        raw_record_count=len(raw_records),
        excluded_counts=excluded_counts,
        rejection_examples=rejections,
        duplicate_groups=duplicate_groups,
        blocklisted_included_counts=blocklisted_included_counts,
        discovery=discovery,
        input_paths=input_paths,
        output_path=output_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        split_by_group=split_by_group,
        length_balance_report=length_balance_outcome.report,
        args=args,
    )
    write_outputs(records, split_by_group, report, output_path, report_json_path, report_md_path)

    print(f"manifest: {output_path}")
    print(f"report_json: {report_json_path}")
    print(f"report_md: {report_md_path}")
    print(f"selected_records: {len(records)}")
    print(f"overall_gate_passed: {report['overall_gate_passed']}")
    # 변경: build hard gate 실패를 process exit code로 전달한다.
    # 이유: nohup 파이프라인이 report JSON을 따로 파싱하지 않아도 실패 run을 성공으로 오판하지 않게 하기 위해서다.
    return 0 if report["overall_gate_passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"build_supervised_manifest: error: {exc}", file=sys.stderr)
        raise SystemExit(2)
