#!/usr/bin/env python3
# Changed: add a stdlib-only hard gate validator for canonical supervised manifests.
# Why: cycle 7 requires manifest validation to block training when data contract gates fail.

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


KST = timezone(timedelta(hours=9), name="KST")
REQUIRED_FIELDS = (
    "sample_id",
    "input",
    "label",
    "source",
    "label_source",
    "template_id",
    "mutation_family",
    "length_bin",
    "format_version",
    "content_hash",
    "group_id",
    "split",
    "path",
    "row",
)
VALID_LABELS = ("pass", "fail")
UNKNOWN_LABELS = {"", "unknown", "unk", "none", "null", "n/a", "na", "unlabeled"}
ARTIFACT_TERMS = ("ckpt", "embedding", "cache", "checkpoint", "intermediate")
# Changed: add public/eval holdout signatures for manifest metadata scanning.
# Why: public 20 and eval/holdout rows must never enter supervised LLM-only training.
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
# Changed: define which manifest fields are metadata for leakage scanning.
# Why: source/path/sample_id and extra provenance fields should be gated without scanning problem input for public words.
MANIFEST_METADATA_SCAN_EXCLUDED_FIELDS = {"input", "label", "row", "length_bin", "content_hash", "_manifest_line"}
MANIFEST_SCAN_MATCH_LIMIT = 10
# Changed: expand rule-context signatures to cover metadata-only rule-engine traces.
# Why: LLM-only data gates must fail even when rule outputs are stored outside the input text.
RULE_CONTEXT_PATTERNS = (
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
    "statefulopalverifier",
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
REFERENCE_TEXT_KEYS = (
    "input",
    "text",
    "prompt",
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
REFERENCE_LEGACY_TEXT_KEYS = ("records", "steps")
REFERENCE_ID_KEYS = ("sample_id", "sampleid", "id", "uid", "uuid", "record_id", "example_id", "idx")
REFERENCE_LABEL_KEYS = (
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
REFERENCE_PROVENANCE_KEYS = (
    "source",
    "source_name",
    "data_source",
    "dataset",
    "origin",
    "template_id",
    "mutation_family",
    "content_hash",
    "group_id",
    "split",
    "path",
    "row",
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


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a canonical supervised manifest with hard gates.")
    parser.add_argument("--manifest", required=True, help="Canonical supervised manifest JSONL path.")
    parser.add_argument("--reference", default=None, help="Optional reference JSON/JSONL path or directory for length JSD.")
    parser.add_argument("--report-out", required=True, help="Report stem/path. Emits both JSON and Korean Markdown.")
    parser.add_argument("--min-template-entropy", type=float, default=0.75)
    parser.add_argument("--max-top-template-share", type=float, default=0.20)
    parser.add_argument("--max-length-jsd", type=float, default=0.08)
    parser.add_argument(
        "--min-char-mean-ratio",
        type=float,
        default=0.60,
        help="Minimum manifest/reference input char-length mean ratio when reference text is available.",
    )
    parser.add_argument(
        "--min-char-median-ratio",
        type=float,
        default=0.60,
        help="Minimum manifest/reference input char-length median ratio when reference text is available.",
    )
    parser.add_argument(
        "--max-min-record-count-gap",
        type=int,
        default=1,
        help="Maximum allowed manifest_min_record_count - reference_min_record_count gap when both are available.",
    )
    return parser.parse_args(argv)


def report_paths(report_out: str) -> Tuple[Path, Path]:
    base = Path(report_out)
    if base.suffix == ".json":
        return base, base.with_suffix(".md")
    if base.suffix == ".md":
        return base.with_suffix(".json"), base
    return base.with_suffix(".json"), base.with_suffix(".md")


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def label_kind(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip()
    if normalized in VALID_LABELS:
        return "valid"
    if normalized.lower() in UNKNOWN_LABELS:
        return "unknown"
    return "invalid"


def as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    # Changed: serialize structured reference text with the same compact JSON form used by the builder.
    # Why: reference length bins must be identical in build length-balancing and validate hard gates.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


# Changed: collect input-shape statistics separately from manifest construction.
# Why: data gates need to detect char-length drift and missing shortest trajectories without importing solver/rulebase code.
def new_shape_values() -> Dict[str, List[int]]:
    return {"char_lengths": [], "token_counts": [], "record_counts": []}


def infer_record_count(value: Any) -> Optional[int]:
    decoded = value
    if isinstance(decoded, str):
        stripped = decoded.strip()
        if not stripped or stripped[0] not in "[{":
            return None
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return None

    if isinstance(decoded, dict):
        for key in ("records", "steps"):
            child = decoded.get(key)
            if isinstance(child, list):
                return len(child)
        return None
    if isinstance(decoded, list):
        return len(decoded)
    return None


def add_shape_value(shape_values: Dict[str, List[int]], value: Any) -> None:
    if value is None:
        return
    text = as_text(value)
    if not text:
        return
    shape_values["char_lengths"].append(len(text))
    shape_values["token_counts"].append(token_count(text))
    record_count = infer_record_count(value)
    if record_count is not None:
        shape_values["record_counts"].append(record_count)


def median_from_sorted(values: Sequence[int]) -> float:
    count = len(values)
    middle = count // 2
    if count % 2:
        return float(values[middle])
    return (values[middle - 1] + values[middle]) / 2.0


def summarize_numeric(values: Sequence[int]) -> Dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": round(median_from_sorted(ordered), 6),
        "mean": round(sum(ordered) / len(ordered), 6),
        "max": ordered[-1],
    }


def summarize_shape_values(shape_values: Mapping[str, Sequence[int]]) -> Dict[str, Dict[str, Any]]:
    return {
        "char_lengths": summarize_numeric(shape_values.get("char_lengths", [])),
        "token_counts": summarize_numeric(shape_values.get("token_counts", [])),
        "record_counts": summarize_numeric(shape_values.get("record_counts", [])),
    }


def empty_shape_summary() -> Dict[str, Dict[str, Any]]:
    return summarize_shape_values(new_shape_values())


def stat_ratio(left: Any, right: Any) -> Optional[float]:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)) or right <= 0:
        return None
    return round(left / right, 6)


def stat_gap(left: Any, right: Any) -> Optional[int]:
    if not isinstance(left, int) or not isinstance(right, int):
        return None
    return left - right


def add_optional_reference_gate(
    gates: Dict[str, Dict[str, Any]],
    name: str,
    value: Any,
    threshold: Any,
    passed: bool,
    detail: Any,
) -> None:
    if value is None:
        gates[name] = {
            "value": None,
            "threshold": threshold,
            "passed": True,
            "skipped": True,
            "detail": detail,
        }
        return
    add_gate(gates, name, value, threshold, passed, detail)


def load_manifest(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    if not path.exists():
        return records, [{"line": None, "error": f"manifest path does not exist: {path}"}]
    if not path.is_file():
        return records, [{"line": None, "error": f"manifest path is not a file: {path}"}]

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_number, "error": f"invalid JSONL: {exc}"})
                continue
            if not isinstance(payload, dict):
                errors.append({"line": line_number, "error": "record is not a JSON object"})
                continue
            payload["_manifest_line"] = line_number
            records.append(payload)

    return records, errors


def collect_reference_files(path: Path) -> List[Path]:
    if not path.exists():
        raise ValueError(f"reference path does not exist: {path}")
    if path.is_dir():
        files = sorted(child for child in path.rglob("*") if child.is_file() and child.suffix.lower() in {".json", ".jsonl"})
    elif path.is_file() and path.suffix.lower() in {".json", ".jsonl"}:
        files = [path]
    else:
        raise ValueError(f"reference must be a .json/.jsonl file or directory: {path}")
    if not files:
        raise ValueError(f"reference contains no .json/.jsonl files: {path}")
    return files


def iter_reference_objects(payload: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(payload, dict):
        yielded_container = False
        for key in ("records", "data", "examples", "samples", "items", "rows", "train", "validation", "valid", "test"):
            value = payload.get(key)
            if isinstance(value, (list, dict)):
                yielded_container = True
                if isinstance(value, list):
                    for item in value:
                        yield from iter_reference_objects(item)
                else:
                    yield from iter_reference_objects(value)
        if not yielded_container:
            if payload and all(isinstance(value, (dict, list)) for value in payload.values()):
                for value in payload.values():
                    yield from iter_reference_objects(value)
                return
            yield payload
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_reference_objects(item)


# Changed: separate reference examples from auxiliary score/report payloads.
# Why: reference gates must fail on malformed eligible corpus records without treating unrelated artifacts as corpus rows.
def lower_key_set(record: Mapping[str, Any]) -> set:
    return {str(key).lower() for key in record}


def value_for_key(record: Mapping[str, Any], key: str) -> Any:
    lowered = {str(original).lower(): original for original in record}
    original = lowered.get(key.lower())
    if original is None:
        return None
    return record[original]


def has_length_source_key(record: Mapping[str, Any]) -> bool:
    keys = lower_key_set(record)
    if "length_bin" in keys:
        return True
    if any(key.lower() in keys for key in REFERENCE_TEXT_KEYS):
        return True
    for key in REFERENCE_LEGACY_TEXT_KEYS:
        if key.lower() not in keys:
            continue
        value = value_for_key(record, key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and value:
            return True
    return False


# Changed: prioritize auxiliary score/report artifacts before schema-like identity labels.
# Why: score rows can carry sample_id/label/source but still lack any length source for reference balancing.
def classify_reference_record(record: Mapping[str, Any], auxiliary_path_reason: Optional[str] = None) -> Tuple[bool, str]:
    keys = lower_key_set(record)
    if has_length_source_key(record):
        return True, "length_source_present"

    auxiliary_hits = sorted(keys & set(REFERENCE_AUXILIARY_KEYS))
    if auxiliary_hits:
        return False, "auxiliary_record_keys:" + ",".join(auxiliary_hits[:5])
    if auxiliary_path_reason:
        return False, auxiliary_path_reason

    label_like = keys & set(REFERENCE_LABEL_KEYS)
    identity_like = keys & (set(REFERENCE_ID_KEYS) | set(REFERENCE_PROVENANCE_KEYS))
    example_hits = sorted(keys & (set(REFERENCE_ID_KEYS) | set(REFERENCE_LABEL_KEYS) | set(REFERENCE_PROVENANCE_KEYS)))

    if label_like and identity_like:
        return True, "example_schema_keys"
    if len(example_hits) >= 3:
        return True, "example_schema_keys"
    return False, "no_reference_example_fields"


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
        "file_reason_counts": counter_to_dict(summary.get("file_reason_counts", Counter())),
        "record_reason_counts": counter_to_dict(summary.get("record_reason_counts", Counter())),
        "file_examples": list(summary.get("file_examples", [])),
        "record_examples": list(summary.get("record_examples", [])),
    }


def extract_reference_text_value(record: Mapping[str, Any]) -> Any:
    for key in REFERENCE_TEXT_KEYS:
        value = value_for_key(record, key)
        if value is not None:
            return value
    for key in REFERENCE_LEGACY_TEXT_KEYS:
        value = value_for_key(record, key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, (list, dict)) and value:
            return value
    return None


def extract_length_bin(record: Mapping[str, Any]) -> Optional[str]:
    # Changed: prefer text-derived reference length over stored length_bin, matching build_supervised_manifest.py.
    # Why: stale length_bin fields and structured JSON spacing previously made build and validate disagree on length JSD.
    text_value = extract_reference_text_value(record)
    if text_value is not None:
        count = token_count(as_text(text_value))
        if count == 0:
            return "0"
        if count <= 32:
            return "1-32"
        if count <= 64:
            return "33-64"
        if count <= 128:
            return "65-128"
        if count <= 256:
            return "129-256"
        if count <= 512:
            return "257-512"
        if count <= 1024:
            return "513-1024"
        return "1025+"

    value = value_for_key(record, "length_bin")
    if not is_blank(value):
        return str(value)
    if text_value is None:
        return None


# Changed: support manifest-like references while skipping auxiliary score/report files explicitly.
# Why: length JSD must use eligible corpus rows, and auxiliary artifacts must not hide eligible parse/schema failures.
def load_reference_length_counts(path: Path) -> Tuple[Counter, List[Dict[str, Any]], int, Dict[str, Any], Dict[str, Dict[str, Any]]]:
    counts: Counter = Counter()
    errors: List[Dict[str, Any]] = []
    eligible_records = 0
    skipped = new_reference_skip_summary()
    reference_shape_values = new_shape_values()

    # Changed: pass path-level auxiliary context into per-record eligibility.
    # Why: auxiliary score/report files without length sources should be skipped, not reported as malformed references.
    def consume_record(
        file_path: Path,
        record: Mapping[str, Any],
        line_number: Optional[int],
        record_index: int,
        auxiliary_path_reason: Optional[str] = None,
    ) -> bool:
        nonlocal eligible_records
        eligible, reason = classify_reference_record(record, auxiliary_path_reason=auxiliary_path_reason)
        if not eligible:
            add_reference_skip(skipped, "record", file_path, reason, line=line_number, record_index=record_index)
            return False

        eligible_records += 1
        # Changed: collect reference input shape stats from the same eligible records used for length JSD.
        # Why: char-length and shortest-trajectory gates must compare against the actual reference validation corpus.
        text_value = extract_reference_text_value(record)
        add_shape_value(reference_shape_values, text_value)
        bin_label = extract_length_bin(record)
        if bin_label is None:
            errors.append(
                {
                    "path": str(file_path),
                    "line": line_number,
                    "record_index": record_index,
                    "error": "eligible reference record missing length_bin/input/text",
                    "eligibility": reason,
                }
            )
        else:
            counts[bin_label] += 1
        return True

    for file_path in collect_reference_files(path):
        file_eligible_records = 0
        file_seen_records = 0
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
                        if consume_record(file_path, record, line_number, file_seen_records, auxiliary_path_reason):
                            file_eligible_records += 1
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
                if consume_record(file_path, record, None, file_seen_records, auxiliary_path_reason):
                    file_eligible_records += 1

        if pending_parse_errors:
            if file_eligible_records > 0 or auxiliary_path_reason is None:
                errors.extend(pending_parse_errors)
            else:
                add_reference_skip(
                    skipped,
                    "file",
                    file_path,
                    f"invalid_jsonl_auxiliary_file:{auxiliary_path_reason}",
                    detail=f"parse_errors={len(pending_parse_errors)}",
                )
        if file_seen_records == 0:
            reason = auxiliary_path_reason or "no_reference_objects"
            add_reference_skip(skipped, "file", file_path, reason, detail="records_seen=0")
        elif file_eligible_records == 0:
            reason = auxiliary_path_reason or "no_eligible_reference_records"
            add_reference_skip(skipped, "file", file_path, reason, detail=f"records_seen={file_seen_records}")

    return counts, errors, eligible_records, skipped, summarize_shape_values(reference_shape_values)


def normalized_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0 or len(counter) <= 1:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        probability = count / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(len(counter))


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


def add_gate(gates: Dict[str, Dict[str, Any]], name: str, value: Any, threshold: Any, passed: bool, detail: Any = None) -> None:
    status = {"value": value, "threshold": threshold, "passed": bool(passed)}
    if detail is not None:
        status["detail"] = detail
    gates[name] = status


def counter_to_dict(counter: Counter) -> Dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter, key=lambda item: str(item))}


def duplicate_summary(hash_to_records: Mapping[str, Sequence[Mapping[str, Any]]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for content_hash, records in sorted(hash_to_records.items()):
        if len(records) <= 1:
            continue
        groups.append(
            {
                "content_hash": content_hash,
                "count": len(records),
                "sample_ids": [record.get("sample_id") for record in records[:10]],
                "lines": [record.get("_manifest_line") for record in records[:10]],
            }
        )
    return groups


def leakage_summary(group_to_splits: Mapping[str, Iterable[str]], group_to_records: Mapping[str, Sequence[Mapping[str, Any]]]) -> List[Dict[str, Any]]:
    leaks: List[Dict[str, Any]] = []
    for group_id, split_values in sorted(group_to_splits.items()):
        splits = sorted(split_values)
        if len(splits) <= 1:
            continue
        records = group_to_records.get(group_id, [])
        leaks.append(
            {
                "group_id": group_id,
                "splits": splits,
                "sample_ids": [record.get("sample_id") for record in records[:10]],
                "lines": [record.get("_manifest_line") for record in records[:10]],
            }
        )
    return leaks


def contains_artifact(value: Any) -> bool:
    text = as_text(value).lower()
    return any(term in text for term in ARTIFACT_TERMS)


# Changed: centralize normalized text forms for manifest gate scanners.
# Why: public/eval and rule-context markers appear with mixed separators in source/path/sample_id metadata.
def scan_text_forms(value: Any) -> Tuple[str, str, str, set]:
    text = as_text(value).lower()
    spaced = " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())
    compact = "".join(ch for ch in text if ch.isalnum())
    tokens = set(spaced.split())
    return text, spaced, compact, tokens


# Changed: return the matched marker instead of only a boolean.
# Why: violation reports need to show why a manifest row failed the LLM-only data gate.
def match_pattern(value: Any, patterns: Sequence[str]) -> Optional[str]:
    text, spaced, compact, tokens = scan_text_forms(value)
    for pattern in patterns:
        lowered = pattern.lower()
        lowered_spaced = " ".join("".join(ch if ch.isalnum() else " " for ch in lowered).split())
        lowered_compact = "".join(ch for ch in lowered if ch.isalnum())
        if " " not in lowered_spaced and lowered_spaced:
            if lowered_spaced in tokens or lowered_compact == compact:
                return pattern
            continue
        if lowered in text or lowered_spaced in spaced or lowered_compact in compact:
            return pattern
    return None


# Changed: scan every manifest metadata field except payload/label/hash fields.
# Why: public holdout and rule-engine provenance can be present in extra metadata keys not listed in REQUIRED_FIELDS.
def iter_manifest_metadata_items(record: Mapping[str, Any]) -> Iterator[Tuple[str, Any]]:
    for key, value in record.items():
        field_name = str(key)
        if field_name in MANIFEST_METADATA_SCAN_EXCLUDED_FIELDS:
            continue
        yield field_name, value


def shortened_text(value: Any, limit: int = 200) -> str:
    text = as_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# Changed: add explicit public/eval holdout manifest metadata detection.
# Why: source/path/sample_id leakage must hard-fail before any training or leaderboard submission.
def public_holdout_metadata_matches(record: Mapping[str, Any]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for field_name, value in iter_manifest_metadata_items(record):
        field_match = match_pattern(field_name, PUBLIC_HOLDOUT_PATTERNS)
        value_match = match_pattern(value, PUBLIC_HOLDOUT_PATTERNS)
        if field_match:
            matches.append({"field": field_name, "matched": field_match, "location": "metadata_key"})
        if value_match:
            matches.append(
                {
                    "field": field_name,
                    "matched": value_match,
                    "location": "metadata_value",
                    "value": shortened_text(value),
                }
            )
        if len(matches) >= MANIFEST_SCAN_MATCH_LIMIT:
            break
    return matches


def contains_rule_context(value: Any) -> bool:
    return match_pattern(value, RULE_CONTEXT_PATTERNS) is not None


# Changed: scan both input text and manifest metadata for rule-context traces.
# Why: rule-engine outputs in metadata still violate the LLM-only data contract.
def rule_context_manifest_matches(record: Mapping[str, Any]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    fields: List[Tuple[str, Any, bool]] = []
    if "input" in record:
        fields.append(("input", record.get("input"), False))
    fields.extend((field_name, value, True) for field_name, value in iter_manifest_metadata_items(record))

    for field_name, value, scan_key in fields:
        if scan_key:
            field_match = match_pattern(field_name, RULE_CONTEXT_PATTERNS)
            if field_match:
                matches.append({"field": field_name, "matched": field_match, "location": "metadata_key"})
        value_match = match_pattern(value, RULE_CONTEXT_PATTERNS)
        if value_match:
            matches.append(
                {
                    "field": field_name,
                    "matched": value_match,
                    "location": "input_value" if field_name == "input" else "metadata_value",
                    "value": shortened_text(value),
                }
            )
        if len(matches) >= MANIFEST_SCAN_MATCH_LIMIT:
            break
    return matches


def manifest_violation_summary(record: Mapping[str, Any], matches: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "line": record.get("_manifest_line"),
        "sample_id": record.get("sample_id"),
        "matches": list(matches[:MANIFEST_SCAN_MATCH_LIMIT]),
    }


def split_label_issues(split_label_counts: Mapping[str, Counter], label_counts: Counter) -> Dict[str, Any]:
    split_names = sorted(split_label_counts)
    possible_labels = [label for label in VALID_LABELS if label_counts.get(label, 0) >= len(split_names) and split_names]
    missing: List[Dict[str, str]] = []
    for split in split_names:
        counts = split_label_counts[split]
        for label in possible_labels:
            if counts.get(label, 0) == 0:
                missing.append({"split": split, "label": label})
    return {
        "possible_labels": possible_labels,
        "missing": missing,
        "split_count": len(split_names),
    }


# Changed: centralize all hard gate calculations from the canonical manifest rows.
# Why: exit code and reports must use the same contract without hidden side effects.
def build_report(
    records: Sequence[Mapping[str, Any]],
    parse_errors: Sequence[Mapping[str, Any]],
    manifest_path: Path,
    reference_path: Optional[Path],
    reference_length_counts: Counter,
    reference_errors: Sequence[Mapping[str, Any]],
    reference_skipped: Mapping[str, Any],
    reference_record_count: int,
    reference_shape_summary: Mapping[str, Mapping[str, Any]],
    report_json_path: Path,
    report_md_path: Path,
    min_template_entropy: float,
    max_top_template_share: float,
    max_length_jsd: float,
    min_char_mean_ratio: float,
    min_char_median_ratio: float,
    max_min_record_count_gap: int,
) -> Dict[str, Any]:
    missing_required: List[Dict[str, Any]] = []
    unknown_labels: List[Dict[str, Any]] = []
    invalid_labels: List[Dict[str, Any]] = []
    artifact_hits: List[Dict[str, Any]] = []
    public_holdout_hits: List[Dict[str, Any]] = []
    rule_context_hits: List[Dict[str, Any]] = []
    rule_context_text_hits: List[Dict[str, Any]] = []
    label_counts: Counter = Counter()
    source_counts: Counter = Counter()
    template_counts: Counter = Counter()
    length_counts: Counter = Counter()
    split_counts: Counter = Counter()
    split_label_counts: DefaultDict[str, Counter] = defaultdict(Counter)
    hash_to_records: DefaultDict[str, List[Mapping[str, Any]]] = defaultdict(list)
    group_to_splits: DefaultDict[str, set] = defaultdict(set)
    group_to_records: DefaultDict[str, List[Mapping[str, Any]]] = defaultdict(list)
    manifest_shape_values = new_shape_values()

    for record in records:
        line = record.get("_manifest_line")
        missing = [field for field in REQUIRED_FIELDS if field not in record or is_blank(record.get(field))]
        if missing:
            missing_required.append({"line": line, "sample_id": record.get("sample_id"), "missing_fields": missing})

        kind = label_kind(record.get("label"))
        if kind == "valid":
            label = str(record.get("label")).strip()
            label_counts[label] += 1
            split = str(record.get("split")) if not is_blank(record.get("split")) else ""
            if split:
                split_label_counts[split][label] += 1
        elif kind == "unknown":
            unknown_labels.append({"line": line, "sample_id": record.get("sample_id"), "label": record.get("label")})
        else:
            invalid_labels.append({"line": line, "sample_id": record.get("sample_id"), "label": record.get("label")})

        if not is_blank(record.get("source")):
            source_counts[str(record.get("source"))] += 1
        if not is_blank(record.get("template_id")):
            template_counts[str(record.get("template_id"))] += 1
        if not is_blank(record.get("length_bin")):
            length_counts[str(record.get("length_bin"))] += 1
        if not is_blank(record.get("split")):
            split_counts[str(record.get("split"))] += 1
        if not is_blank(record.get("content_hash")):
            hash_to_records[str(record.get("content_hash"))].append(record)
        if not is_blank(record.get("group_id")):
            group_id = str(record.get("group_id"))
            if not is_blank(record.get("split")):
                group_to_splits[group_id].add(str(record.get("split")))
            group_to_records[group_id].append(record)
        # Changed: collect manifest input shape stats during the existing row scan.
        # Why: this keeps shape gates data-only and avoids another pass with different filtering semantics.
        add_shape_value(manifest_shape_values, record.get("input"))

        source = record.get("source")
        path = record.get("path")
        if contains_artifact(source) or contains_artifact(path):
            artifact_hits.append({"line": line, "sample_id": record.get("sample_id"), "source": source, "path": path})
        # Changed: hard-fail public/eval holdout traces in manifest metadata.
        # Why: public 20/eval holdout rows must be excluded before supervised training.
        public_matches = public_holdout_metadata_matches(record)
        if public_matches:
            public_holdout_hits.append(manifest_violation_summary(record, public_matches))
        # Changed: hard-fail rule-context traces in both input and metadata.
        # Why: metadata-only rule-engine outputs are still non-LLM-only supervision.
        rule_matches = rule_context_manifest_matches(record)
        if rule_matches:
            rule_context_hits.append(manifest_violation_summary(record, rule_matches))
        if "input" in record and contains_rule_context(record.get("input")):
            rule_context_text_hits.append({"line": line, "sample_id": record.get("sample_id")})

    total_records = len(records)
    valid_label_records = sum(label_counts.values())
    labeled_coverage = valid_label_records / total_records if total_records else 0.0
    duplicate_groups = duplicate_summary(hash_to_records)
    duplicate_record_count = sum(group["count"] for group in duplicate_groups)
    leakage_groups = leakage_summary(group_to_splits, group_to_records)
    template_entropy = normalized_entropy(template_counts)
    top_template_count = max(template_counts.values()) if template_counts else 0
    top_template_share = top_template_count / total_records if total_records else 0.0
    split_issue_data = split_label_issues(split_label_counts, label_counts)
    length_jsd = jensen_shannon_divergence(length_counts, reference_length_counts) if reference_path else None
    reference_skip_report = finalize_reference_skip_summary(reference_skipped)
    manifest_shape_summary = summarize_shape_values(manifest_shape_values)
    manifest_char_stats = manifest_shape_summary["char_lengths"]
    reference_char_stats = reference_shape_summary.get("char_lengths", {})
    manifest_record_stats = manifest_shape_summary["record_counts"]
    reference_record_stats = reference_shape_summary.get("record_counts", {})
    char_mean_ratio = stat_ratio(manifest_char_stats.get("mean"), reference_char_stats.get("mean"))
    char_median_ratio = stat_ratio(manifest_char_stats.get("median"), reference_char_stats.get("median"))
    min_record_count_gap = stat_gap(manifest_record_stats.get("min"), reference_record_stats.get("min"))
    record_gap_detail = {
        "manifest_min_record_count": manifest_record_stats.get("min"),
        "reference_min_record_count": reference_record_stats.get("min"),
        "message": "reference와 manifest의 최단 trajectory record_count 차이를 비교했습니다.",
    }
    if reference_record_stats.get("min") == 1 and isinstance(manifest_record_stats.get("min"), int) and manifest_record_stats.get("min") >= 2:
        record_gap_detail["message"] = (
            "reference에는 1-record shortest case가 있지만 manifest 최단 record_count가 "
            f"{manifest_record_stats.get('min')}라서 shortest case coverage가 부족할 수 있습니다."
        )

    gates: Dict[str, Dict[str, Any]] = {}
    add_gate(gates, "manifest_jsonl_parse_errors_0", len(parse_errors), 0, len(parse_errors) == 0)
    add_gate(gates, "manifest_records_gt_0", total_records, ">0", total_records > 0)
    add_gate(gates, "required_fields_present", len(missing_required), 0, len(missing_required) == 0)
    add_gate(gates, "labeled_coverage_100pct", round(labeled_coverage, 6), 1.0, labeled_coverage == 1.0)
    # Changed: count every non-pass/fail label in the label vocabulary gate.
    # Why: unknown labels are reported separately, but they still violate the canonical label set.
    non_pass_fail_labels = len(unknown_labels) + len(invalid_labels)
    add_gate(gates, "unknown_label_0", len(unknown_labels), 0, len(unknown_labels) == 0)
    add_gate(gates, "labels_only_pass_fail", non_pass_fail_labels, 0, non_pass_fail_labels == 0)
    add_gate(gates, "exact_duplicate_content_hash_0", len(duplicate_groups), 0, len(duplicate_groups) == 0)
    add_gate(gates, "group_leakage_0", len(leakage_groups), 0, len(leakage_groups) == 0)
    add_gate(gates, "template_entropy_gte_threshold", round(template_entropy, 6), min_template_entropy, template_entropy >= min_template_entropy)
    add_gate(gates, "top_template_share_lte_threshold", round(top_template_share, 6), max_top_template_share, top_template_share <= max_top_template_share)
    add_gate(
        gates,
        "split_label_counts_nonzero_where_possible",
        len(split_issue_data["missing"]),
        0,
        len(split_issue_data["missing"]) == 0,
        split_issue_data,
    )
    add_gate(gates, "artifact_exclusion", len(artifact_hits), 0, len(artifact_hits) == 0)
    add_gate(gates, "public_holdout_metadata_absent", len(public_holdout_hits), 0, len(public_holdout_hits) == 0)
    add_gate(gates, "rule_context_text_absent", len(rule_context_text_hits), 0, len(rule_context_text_hits) == 0)
    add_gate(gates, "rule_context_metadata_or_input_absent", len(rule_context_hits), 0, len(rule_context_hits) == 0)

    if reference_path:
        # Changed: reference parse gate now covers eligible corpus records only.
        # Why: auxiliary files are reported separately instead of weakening eligible corpus validation.
        add_gate(
            gates,
            "reference_parse_errors_0",
            len(reference_errors),
            0,
            len(reference_errors) == 0,
            {
                "skipped_auxiliary_files": reference_skip_report["file_count"],
                "skipped_auxiliary_records": reference_skip_report["record_count"],
            },
        )
        add_gate(gates, "reference_records_gt_0", reference_record_count, ">0", reference_record_count > 0)
        add_gate(
            gates,
            "length_jsd_lte_threshold",
            None if length_jsd is None else round(length_jsd, 6),
            max_length_jsd,
            length_jsd is not None and length_jsd <= max_length_jsd,
        )
        # Changed: add optional reference shape gates for char length and shortest trajectory coverage.
        # Why: length-bin JSD can pass even when raw chars are short or 1-record cases are absent.
        add_optional_reference_gate(
            gates,
            "char_length_mean_ratio_gte_threshold",
            char_mean_ratio,
            min_char_mean_ratio,
            char_mean_ratio is not None and char_mean_ratio >= min_char_mean_ratio,
            {
                "manifest_mean_chars": manifest_char_stats.get("mean"),
                "reference_mean_chars": reference_char_stats.get("mean"),
                "message": "manifest/reference input char length mean ratio입니다.",
            },
        )
        add_optional_reference_gate(
            gates,
            "char_length_median_ratio_gte_threshold",
            char_median_ratio,
            min_char_median_ratio,
            char_median_ratio is not None and char_median_ratio >= min_char_median_ratio,
            {
                "manifest_median_chars": manifest_char_stats.get("median"),
                "reference_median_chars": reference_char_stats.get("median"),
                "message": "manifest/reference input char length median ratio입니다.",
            },
        )
        add_optional_reference_gate(
            gates,
            "min_record_count_gap_lte_threshold",
            min_record_count_gap,
            max_min_record_count_gap,
            min_record_count_gap is not None and min_record_count_gap <= max_min_record_count_gap,
            record_gap_detail,
        )
    else:
        gates["length_jsd_lte_threshold"] = {
            "value": None,
            "threshold": max_length_jsd,
            "passed": False,
            "skipped": True,
            "detail": "reference가 없어서 actual length JSD를 계산하지 못했습니다.",
        }
        add_optional_reference_gate(
            gates,
            "char_length_mean_ratio_gte_threshold",
            None,
            min_char_mean_ratio,
            True,
            "reference가 없어서 char length mean ratio를 계산하지 않았습니다.",
        )
        add_optional_reference_gate(
            gates,
            "char_length_median_ratio_gte_threshold",
            None,
            min_char_median_ratio,
            True,
            "reference가 없어서 char length median ratio를 계산하지 않았습니다.",
        )
        add_optional_reference_gate(
            gates,
            "min_record_count_gap_lte_threshold",
            None,
            max_min_record_count_gap,
            True,
            "reference가 없어서 min record_count gap을 계산하지 않았습니다.",
        )

    overall_passed = all(status.get("passed") is True for status in gates.values())
    return {
        "generated_at_kst": datetime.now(KST).isoformat(),
        "overall_gate_passed": overall_passed,
        "config": {
            "manifest": str(manifest_path),
            "reference": None if reference_path is None else str(reference_path),
            "report_json_out": str(report_json_path),
            "report_md_out": str(report_md_path),
            "min_template_entropy": min_template_entropy,
            "max_top_template_share": max_top_template_share,
            "max_length_jsd": max_length_jsd,
            "min_char_mean_ratio": min_char_mean_ratio,
            "min_char_median_ratio": min_char_median_ratio,
            "max_min_record_count_gap": max_min_record_count_gap,
        },
        "counts": {
            "records": total_records,
            "valid_label_records": valid_label_records,
            "unknown_label_records": len(unknown_labels),
            "invalid_label_records": len(invalid_labels),
            "reference_records": reference_record_count,
            "reference_skipped_files": reference_skip_report["file_count"],
            "reference_skipped_records": reference_skip_report["record_count"],
            "split_counts": counter_to_dict(split_counts),
        },
        "metrics": {
            "labeled_coverage": round(labeled_coverage, 6),
            "label_counts": {label: label_counts.get(label, 0) for label in VALID_LABELS},
            "source_counts": counter_to_dict(source_counts),
            "template_counts": counter_to_dict(template_counts),
            "length_bins": counter_to_dict(length_counts),
            "reference_length_bins": counter_to_dict(reference_length_counts),
            "split_label_counts": {split: counter_to_dict(counter) for split, counter in sorted(split_label_counts.items())},
            "char_length_stats": manifest_char_stats,
            "reference_char_length_stats": reference_char_stats,
            "token_count_stats": manifest_shape_summary["token_counts"],
            "reference_token_count_stats": reference_shape_summary.get("token_counts", {}),
            "record_count_stats": manifest_record_stats,
            "reference_record_count_stats": reference_record_stats,
            "char_length_mean_ratio": char_mean_ratio,
            "char_length_median_ratio": char_median_ratio,
            "min_record_count_gap": min_record_count_gap,
            "normalized_template_entropy": round(template_entropy, 6),
            "top_template_share": round(top_template_share, 6),
            "top_template_count": top_template_count,
            "length_jsd": None if length_jsd is None else round(length_jsd, 6),
            "duplicate_content_hash_group_count": len(duplicate_groups),
            "duplicate_content_hash_record_count": duplicate_record_count,
            "group_leakage_count": len(leakage_groups),
        },
        "gate_status": gates,
        "violations": {
            "parse_errors": list(parse_errors)[:50],
            "missing_required": missing_required[:50],
            "unknown_labels": unknown_labels[:50],
            "invalid_labels": invalid_labels[:50],
            "duplicate_content_hash_groups": duplicate_groups[:50],
            "group_leakage": leakage_groups[:50],
            "artifact_hits": artifact_hits[:50],
            "public_holdout_hits": public_holdout_hits[:50],
            "rule_context_hits": rule_context_hits[:50],
            "rule_context_text_hits": rule_context_text_hits[:50],
            "reference_errors": list(reference_errors)[:50],
        },
        "reference_skipped": reference_skip_report,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    metrics = report["metrics"]
    gates = report["gate_status"]
    lines = [
        "# Supervised Manifest 검증 보고서",
        "",
        f"- 생성 시각(KST): {report['generated_at_kst']}",
        f"- 전체 hard gate: {'통과' if report['overall_gate_passed'] else '실패'}",
        f"- manifest: `{report['config']['manifest']}`",
        f"- reference: `{report['config']['reference']}`",
        f"- 레코드 수: {counts['records']}",
        f"- labeled coverage: {metrics['labeled_coverage']}",
        f"- unknown label records: {counts['unknown_label_records']}",
        f"- invalid label records: {counts['invalid_label_records']}",
        "",
        "## Hard Gates",
        "",
        "| 게이트 | 기준 | 값 | 상태 |",
        "| --- | ---: | ---: | --- |",
    ]

    for name, status in gates.items():
        if status.get("skipped"):
            state = "건너뜀" if status.get("passed") else "실패(건너뜀)"
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
            f"- normalized template entropy: {metrics['normalized_template_entropy']}",
            f"- top template share: {metrics['top_template_share']} ({metrics['top_template_count']} records)",
            f"- length JSD: {metrics['length_jsd']}",
            f"- char length mean ratio: {metrics['char_length_mean_ratio']}",
            f"- char length median ratio: {metrics['char_length_median_ratio']}",
            f"- min record_count gap: {metrics['min_record_count_gap']}",
            f"- manifest char stats: {metrics['char_length_stats']}",
            f"- reference char stats: {metrics['reference_char_length_stats']}",
            f"- manifest record_count stats: {metrics['record_count_stats']}",
            f"- reference record_count stats: {metrics['reference_record_count_stats']}",
            f"- duplicate content_hash groups: {metrics['duplicate_content_hash_group_count']}",
            f"- group leakage groups: {metrics['group_leakage_count']}",
            "",
            "## Label Counts",
            "",
        ]
    )
    lines.extend(render_counter(metrics["label_counts"]))
    lines.extend(["", "## Split Label Counts", ""])
    for split, split_counts in metrics["split_label_counts"].items():
        lines.append(f"- `{split}`: {split_counts}")
    if not metrics["split_label_counts"]:
        lines.append("- 없음")

    reference_skipped = report.get("reference_skipped", {})
    if reference_skipped.get("file_count", 0) or reference_skipped.get("record_count", 0):
        lines.extend(
            [
                "",
                "## Reference Auxiliary Skip",
                "",
                f"- skipped files: {reference_skipped.get('file_count', 0)}",
                f"- skipped records: {reference_skipped.get('record_count', 0)}",
                f"- file reasons: {reference_skipped.get('file_reason_counts', {})}",
                f"- record reasons: {reference_skipped.get('record_reason_counts', {})}",
            ]
        )
        for value in reference_skipped.get("file_examples", [])[:20]:
            lines.append(f"- file `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")
        for value in reference_skipped.get("record_examples", [])[:20]:
            lines.append(f"- record `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")

    violations = report["violations"]
    # Changed: surface new LLM-only leakage gates in the Markdown report.
    # Why: public/eval holdout and metadata rule-context failures must be auditable from archived reports.
    for key, title in (
        ("missing_required", "필수 필드 위반"),
        ("duplicate_content_hash_groups", "중복 content_hash"),
        ("group_leakage", "Group Leakage"),
        ("artifact_hits", "Artifact 포함"),
        ("public_holdout_hits", "Public/Eval Holdout 메타데이터 포함"),
        ("rule_context_hits", "Rule Context 메타데이터/Input 포함"),
        ("reference_errors", "Reference 오류"),
    ):
        values = violations.get(key, [])
        if values:
            lines.extend(["", f"## {title}", ""])
            for value in values[:20]:
                lines.append(f"- `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")

    return "\n".join(lines) + "\n"


def render_counter(counter: Mapping[str, int]) -> List[str]:
    if not counter:
        return ["- 없음"]
    return [f"- `{key}`: {value}" for key, value in counter.items()]


def write_reports(report: Mapping[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(render_markdown(report))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest)
    reference_path = Path(args.reference) if args.reference else None
    report_json_path, report_md_path = report_paths(args.report_out)

    records, parse_errors = load_manifest(manifest_path)
    reference_length_counts: Counter = Counter()
    reference_errors: List[Dict[str, Any]] = []
    reference_skipped: Dict[str, Any] = new_reference_skip_summary()
    reference_record_count = 0
    reference_shape_summary = empty_shape_summary()
    if reference_path:
        try:
            # Changed: load reference corpus with eligible/auxiliary accounting.
            # Why: validation should fail only on malformed eligible corpus records while reporting skipped artifacts.
            (
                reference_length_counts,
                reference_errors,
                reference_record_count,
                reference_skipped,
                reference_shape_summary,
            ) = load_reference_length_counts(reference_path)
        except ValueError as exc:
            reference_errors = [{"path": str(reference_path), "line": None, "error": str(exc)}]

    report = build_report(
        records=records,
        parse_errors=parse_errors,
        manifest_path=manifest_path,
        reference_path=reference_path,
        reference_length_counts=reference_length_counts,
        reference_errors=reference_errors,
        reference_skipped=reference_skipped,
        reference_record_count=reference_record_count,
        reference_shape_summary=reference_shape_summary,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        min_template_entropy=args.min_template_entropy,
        max_top_template_share=args.max_top_template_share,
        max_length_jsd=args.max_length_jsd,
        min_char_mean_ratio=args.min_char_mean_ratio,
        min_char_median_ratio=args.min_char_median_ratio,
        max_min_record_count_gap=args.max_min_record_count_gap,
    )
    write_reports(report, report_json_path, report_md_path)

    print(f"report_json: {report_json_path}")
    print(f"report_md: {report_md_path}")
    print(f"overall_gate_passed: {report['overall_gate_passed']}")
    return 0 if report["overall_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
