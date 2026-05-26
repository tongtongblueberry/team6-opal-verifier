# Changed: make the Self-Instruct seed schema input-only.
# Why: public20 seeds may provide trajectory shape context, but labels must not leak into generation or training rows.
"""Normalize input-only Self-Instruct seed records and compute shape profiles.

This module is a data preparation tool. It does not import deprecated v4/v4.1
generators, and it must not be used by runtime inference or submission code.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


Json = Dict[str, Any]
SEED_SCHEMA_VERSION = "self_instruct.seed.v1"
SEED_PROFILE_SCHEMA_VERSION = "self_instruct.seed_profile.v1"

FORBIDDEN_SEED_LABEL_FIELDS = frozenset(
    {
        "answer",
        "expected_answer",
        "expected_label",
        "gold",
        "gold_label",
        "label",
        "public_answer",
        "public_label",
    }
)
FORBIDDEN_SEED_RULE_FIELDS = frozenset(
    {
        "rule_engine",
        "rule_id",
        "rule_pred",
        "verifier_output",
    }
)
FORBIDDEN_SEED_TARGET_FIELDS = frozenset(
    {
        "evidence_step",
        "label_target",
        "primary_evidence",
        "target",
    }
)
FORBIDDEN_SEED_FIELDS = FORBIDDEN_SEED_LABEL_FIELDS | FORBIDDEN_SEED_RULE_FIELDS | FORBIDDEN_SEED_TARGET_FIELDS


class SeedSchemaError(ValueError):
    """Raised when an input-only seed cannot be normalized safely."""


# Changed: keep method/status extraction local to this schema tool.
# Why: public seed profiling needs dimensions, not protocol verdict logic.
def _method_name(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_value = record.get("input")
    if isinstance(input_value, Mapping):
        command = input_value.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        method = input_value.get("method")
        if isinstance(method, Mapping):
            name = method.get("name") or method.get("Name")
            return name.strip() if isinstance(name, str) else ""
        if isinstance(method, str):
            return method.strip()
    command = record.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()
    method = record.get("method")
    if isinstance(method, Mapping):
        name = method.get("name") or method.get("Name")
        return name.strip() if isinstance(name, str) else ""
    if isinstance(method, str):
        return method.strip()
    return ""


def _status_texts(value: Any) -> Tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped.upper(),) if stripped else ()
    if isinstance(value, Mapping):
        for key in ("Name", "name", "status_codes", "status"):
            if key in value:
                return _status_texts(value[key])
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        texts: List[str] = []
        for item in value:
            texts.extend(_status_texts(item))
        return tuple(texts)
    return ()


def _record_status(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    output = record.get("output")
    if isinstance(output, Mapping):
        statuses = _status_texts(output.get("status_codes"))
        if not statuses:
            statuses = _status_texts(output.get("status"))
        if not statuses:
            statuses = _status_texts(record.get("status_codes"))
        if not statuses:
            statuses = _status_texts(record.get("status"))
        if not statuses:
            statuses = _status_texts(output.get("result"))
        if not statuses:
            args = output.get("args")
            if isinstance(args, Mapping):
                statuses = _status_texts(args.get("result"))
        return statuses[0] if statuses else ""
    statuses = _status_texts(record.get("status_codes"))
    if not statuses:
        statuses = _status_texts(record.get("status"))
    return statuses[0] if statuses else ""


def _return_value_count(record: Any) -> int:
    if not isinstance(record, Mapping):
        return 0
    output = record.get("output")
    if not isinstance(output, Mapping):
        return 0
    return_values = output.get("return_values")
    if isinstance(return_values, Mapping):
        return len(return_values)
    if isinstance(return_values, Sequence) and not isinstance(return_values, (bytes, bytearray, str)):
        return len(return_values)
    return 0


def _required_string(candidate: Mapping[str, Any], keys: Sequence[str], field_name: str) -> str:
    for key in keys:
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise SeedSchemaError(f"{field_name}_missing")


def _extract_records(candidate: Mapping[str, Any]) -> List[Any]:
    records = candidate.get("records")
    if records is None:
        trajectory = candidate.get("trajectory")
        if isinstance(trajectory, Mapping):
            records = trajectory.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        raise SeedSchemaError("records_not_list")
    if len(records) == 0:
        raise SeedSchemaError("records_empty")
    return copy.deepcopy(list(records))


# Changed: support public/model raw rows whose `input` is the exact model input JSON string.
# Why: public20 must be profiled without inventing an instruction field or changing the input dimension.
def _extract_public_raw_input(candidate: Mapping[str, Any]) -> Optional[Tuple[str, List[Any]]]:
    input_text = candidate.get("input")
    if not isinstance(input_text, str):
        return None
    stripped = input_text.strip()
    if not stripped:
        raise SeedSchemaError("input_empty")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise SeedSchemaError(f"input_json_invalid:{exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise SeedSchemaError("input_json_root_not_object")
    records = payload.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        raise SeedSchemaError("records_not_list")
    if len(records) == 0:
        raise SeedSchemaError("records_empty")
    return input_text, copy.deepcopy(list(records))


def _forbidden_seed_fields(candidate: Mapping[str, Any]) -> List[str]:
    fields = sorted(key for key in candidate.keys() if str(key) in FORBIDDEN_SEED_FIELDS)
    trajectory = candidate.get("trajectory")
    if isinstance(trajectory, Mapping):
        fields.extend(sorted(f"trajectory.{key}" for key in trajectory.keys() if str(key) in FORBIDDEN_SEED_FIELDS))
    return fields


def _length_bin(record_count: int) -> str:
    if record_count <= 32:
        return "1-32"
    if record_count <= 64:
        return "33-64"
    if record_count <= 128:
        return "65-128"
    if record_count <= 256:
        return "129-256"
    return "257-512"


# Changed: canonicalize only input-side fields needed by Self-Instruct generation gates.
# Why: public20 labels and label-derived evidence must never become generation or training fields.
def normalize_seed(candidate: Mapping[str, Any], *, allow_label_fields_for_audit: bool = False) -> Json:
    if not isinstance(candidate, Mapping):
        raise SeedSchemaError("candidate_not_mapping")

    forbidden_fields = _forbidden_seed_fields(candidate)
    if forbidden_fields and not allow_label_fields_for_audit:
        raise SeedSchemaError(f"forbidden_seed_fields:{','.join(forbidden_fields)}")

    sample_id = _required_string(candidate, ("sample_id", "seed_id", "id"), "sample_id")
    raw_input = _extract_public_raw_input(candidate)
    if raw_input is None:
        instruction = _required_string(candidate, ("instruction", "task_instruction"), "instruction")
        records = _extract_records(candidate)
        input_text = None
        input_format = "canonical_instruction_records"
    else:
        input_text, records = raw_input
        instruction = None
        input_format = "public_model_raw_json_text"

    final_record = records[-1]
    if not isinstance(final_record, Mapping):
        raise SeedSchemaError("final_record_not_mapping")
    if not isinstance(final_record.get("output"), Mapping):
        raise SeedSchemaError("final_output_missing")

    normalized: Json = {
        "schema_version": SEED_SCHEMA_VERSION,
        "sample_id": sample_id,
        "records": records,
        "input_format": input_format,
        "source": candidate.get("source") if isinstance(candidate.get("source"), str) else "public20_input_only",
    }
    if instruction is not None:
        normalized["instruction"] = instruction
    if input_text is not None:
        normalized["input_text"] = input_text
    normalized["profile"] = profile_seed(normalized)
    return normalized


# Changed: expose one profile shape used by Gate B and model-path equivalence checks.
# Why: generated data must be compared against public20 with identical dimension definitions.
def profile_seed(seed: Mapping[str, Any]) -> Json:
    records = seed.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        raise SeedSchemaError("records_not_list")
    if len(records) == 0:
        raise SeedSchemaError("records_empty")

    method_sequence = [_method_name(record) for record in records]
    status_sequence = [_record_status(record) for record in records]
    input_text = seed.get("input_text")
    if isinstance(input_text, str):
        input_json = input_text
        input_format = "public_model_raw_json_text"
    else:
        input_payload: Json = {"records": list(records)}
        instruction = seed.get("instruction")
        if isinstance(instruction, str):
            input_payload["instruction"] = instruction
        input_json = json.dumps(input_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        input_format = "canonical_instruction_records" if "instruction" in input_payload else "records_only"
    return_value_counts = [_return_value_count(record) for record in records]

    return {
        "sample_id": seed.get("sample_id"),
        "input_format": input_format,
        "record_count": len(records),
        "input_json_chars": len(input_json),
        "method_sequence": method_sequence,
        "method_sequence_length": len(method_sequence),
        "status_sequence": status_sequence,
        "final_method": method_sequence[-1],
        "final_status": status_sequence[-1],
        "return_value_counts": return_value_counts,
        "total_return_value_count": sum(return_value_counts),
        "final_return_value_count": return_value_counts[-1],
        "length_bin": _length_bin(len(records)),
    }


def normalize_seeds(candidates: Iterable[Mapping[str, Any]], *, allow_label_fields_for_audit: bool = False) -> List[Json]:
    return [normalize_seed(candidate, allow_label_fields_for_audit=allow_label_fields_for_audit) for candidate in candidates]


def build_profile_report(seeds: Sequence[Mapping[str, Any]], input_path: Optional[Path] = None) -> Json:
    profiles = [profile_seed(seed) for seed in seeds]
    source_counts: Json = {}
    final_status_counts: Json = {}
    final_method_counts: Json = {}
    for seed, profile in zip(seeds, profiles):
        source = seed.get("source")
        source_key = source if isinstance(source, str) and source else "unknown"
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        final_status = profile["final_status"]
        final_method = profile["final_method"]
        final_status_counts[final_status] = final_status_counts.get(final_status, 0) + 1
        final_method_counts[final_method] = final_method_counts.get(final_method, 0) + 1
    return {
        "schema_version": SEED_PROFILE_SCHEMA_VERSION,
        "input": str(input_path) if input_path is not None else None,
        "count": len(profiles),
        "source_counts": source_counts,
        "final_method_counts": final_method_counts,
        "final_status_counts": final_status_counts,
        "profiles": profiles,
    }


def _ensure_mapping_list(values: Sequence[Any]) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise SeedSchemaError(f"item_{index}_not_object")
        rows.append(value)
    return rows


def _parse_json_or_jsonl(text: str) -> List[Mapping[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return []

    if stripped[0] in "[{":
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        else:
            if isinstance(payload, list):
                return _ensure_mapping_list(payload)
            if isinstance(payload, Mapping):
                # Changed: only collection wrapper keys are expanded here.
                # Why: a single seed also has a trajectory `records` field and must stay one row.
                for key in ("seeds", "inputs"):
                    value = payload.get(key)
                    if isinstance(value, list) and value and all(isinstance(item, Mapping) for item in value):
                        return _ensure_mapping_list(value)
                return [payload]
            raise SeedSchemaError("json_root_not_object_or_array")

    rows: List[Mapping[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise SeedSchemaError(f"line_{line_number}_not_object")
        rows.append(payload)
    return rows


def load_seed_candidates(path: Path) -> List[Mapping[str, Any]]:
    return _parse_json_or_jsonl(path.read_text(encoding="utf-8"))


def write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize input-only Self-Instruct seed JSON/JSONL and emit profile metrics.")
    parser.add_argument("--input", required=True, type=Path, help="Input JSON or JSONL seed file.")
    parser.add_argument("--output", required=True, type=Path, help="Output canonical input-only seed JSONL path.")
    parser.add_argument("--profile-output", required=True, type=Path, help="Output profile JSON path.")
    parser.add_argument(
        "--allow-label-fields-for-audit",
        action="store_true",
        help="Permit label-like source fields for audit ingestion only; labels are still omitted from output.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        candidates = load_seed_candidates(args.input)
        normalized = normalize_seeds(candidates, allow_label_fields_for_audit=args.allow_label_fields_for_audit)
        profile_report = build_profile_report(normalized, input_path=args.input)
        write_jsonl(normalized, args.output)
        args.profile_output.parent.mkdir(parents=True, exist_ok=True)
        args.profile_output.write_text(
            json.dumps(profile_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, SeedSchemaError) as exc:
        print(f"self_instruct_seed_schema: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
