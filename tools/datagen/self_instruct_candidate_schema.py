# Changed: separate label-bearing Self-Instruct candidate normalization from public seed normalization.
# Why: generated candidates need labels and final-response invariant gates, while public20 seeds must remain input-only.
"""Normalize label-bearing Self-Instruct candidate records.

This module is a data preparation tool for generated candidate JSONL. It does
not import deprecated v4/v4.1 generators, and it must not be used by runtime
inference or submission code.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.self_instruct_invariants import (  # noqa: E402
    check_final_response_label_invariant,
    normalize_label,
)
from tools.datagen.self_instruct_seed_schema import profile_seed  # noqa: E402


Json = Dict[str, Any]
CANDIDATE_SCHEMA_VERSION = "self_instruct.candidate.v1"
CANDIDATE_PROFILE_SCHEMA_VERSION = "self_instruct.candidate_profile.v1"


class CandidateSchemaError(ValueError):
    """Raised when a generated candidate cannot be normalized safely."""


def _as_index(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lstrip("-").isdigit():
            return int(stripped)
    return None


def _required_string(candidate: Mapping[str, Any], keys: Sequence[str], field_name: str) -> str:
    for key in keys:
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise CandidateSchemaError(f"{field_name}_missing")


def _extract_records(candidate: Mapping[str, Any]) -> List[Any]:
    records = candidate.get("records")
    if records is None:
        trajectory = candidate.get("trajectory")
        if isinstance(trajectory, Mapping):
            records = trajectory.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        raise CandidateSchemaError("records_not_list")
    if len(records) == 0:
        raise CandidateSchemaError("records_empty")
    return copy.deepcopy(list(records))


def _final_output(records: Sequence[Any]) -> Any:
    final_record = records[-1]
    if not isinstance(final_record, Mapping):
        raise CandidateSchemaError("final_record_not_mapping")
    final_output = final_record.get("output")
    if not isinstance(final_output, Mapping):
        raise CandidateSchemaError("final_output_missing")
    return copy.deepcopy(final_output)


def _normalize_target(candidate: Mapping[str, Any], final_index: int, final_response: Any) -> Json:
    target = candidate.get("target")
    if not isinstance(target, Mapping):
        raise CandidateSchemaError("target_missing")

    source_index = _as_index(target.get("final_response_index"))
    if source_index != final_index:
        raise CandidateSchemaError("target_index_not_last_record")
    if target.get("final_response") != final_response:
        raise CandidateSchemaError("target_response_not_last_record_output")

    normalized: Json = {
        "final_response_index": final_index,
        "final_response": final_response,
    }
    final_method = target.get("final_method")
    if isinstance(final_method, str) and final_method.strip():
        normalized["final_method"] = final_method.strip()
    return normalized


def _normalize_primary_evidence(candidate: Mapping[str, Any], final_index: int) -> Json:
    primary_evidence = candidate.get("primary_evidence")
    if not isinstance(primary_evidence, Mapping):
        raise CandidateSchemaError("primary_evidence_missing")

    evidence_index = _as_index(primary_evidence.get("record_index"))
    if evidence_index != final_index:
        raise CandidateSchemaError("primary_evidence_not_final_response")

    normalized: Json = {"record_index": final_index}
    reason = primary_evidence.get("reason")
    if isinstance(reason, str) and reason.strip():
        normalized["reason"] = reason.strip()
    return normalized


# Changed: canonicalize label-bearing candidate rows and run the final-response invariant gate.
# Why: generated labels must target records[-1].output before any judge, manifest, or training step.
def normalize_candidate(candidate: Mapping[str, Any]) -> Json:
    if not isinstance(candidate, Mapping):
        raise CandidateSchemaError("candidate_not_mapping")

    sample_id = _required_string(candidate, ("sample_id", "candidate_id", "id"), "sample_id")
    instruction = _required_string(candidate, ("instruction", "task_instruction"), "instruction")
    records = _extract_records(candidate)
    final_index = len(records) - 1
    final_response = _final_output(records)

    label = normalize_label(candidate.get("label"))
    if label is None:
        raise CandidateSchemaError("invalid_label")

    label_target = candidate.get("label_target")
    if label_target is not None and str(label_target).strip().lower() != "final_response":
        raise CandidateSchemaError("label_target_not_final_response")

    normalized: Json = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "sample_id": sample_id,
        "instruction": instruction,
        "records": records,
        "label": label,
        "label_target": "final_response",
        "target": _normalize_target(candidate, final_index, final_response),
        "primary_evidence": _normalize_primary_evidence(candidate, final_index),
        "source": candidate.get("source") if isinstance(candidate.get("source"), str) else "self_instruct_candidate",
    }

    invariant = check_final_response_label_invariant(normalized)
    if not invariant.passed:
        raise CandidateSchemaError(invariant.reason)
    return normalized


def profile_candidate(candidate: Mapping[str, Any]) -> Json:
    profile = profile_seed(candidate)
    profile["label"] = normalize_label(candidate.get("label"))
    profile["label_target"] = candidate.get("label_target")
    target = candidate.get("target")
    if isinstance(target, Mapping):
        profile["target_final_response_index"] = _as_index(target.get("final_response_index"))
    return profile


def normalize_candidates(candidates: Iterable[Mapping[str, Any]]) -> List[Json]:
    return [normalize_candidate(candidate) for candidate in candidates]


def build_profile_report(candidates: Sequence[Mapping[str, Any]], input_path: Optional[Path] = None) -> Json:
    profiles = [profile_candidate(candidate) for candidate in candidates]
    label_counts: Json = {}
    final_status_counts: Json = {}
    for profile in profiles:
        label = profile["label"]
        label_counts[label] = label_counts.get(label, 0) + 1
        final_status = profile["final_status"]
        final_status_counts[final_status] = final_status_counts.get(final_status, 0) + 1
    return {
        "schema_version": CANDIDATE_PROFILE_SCHEMA_VERSION,
        "input": str(input_path) if input_path is not None else None,
        "count": len(profiles),
        "label_counts": label_counts,
        "final_status_counts": final_status_counts,
        "profiles": profiles,
    }


def _ensure_mapping_list(values: Sequence[Any]) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise CandidateSchemaError(f"item_{index}_not_object")
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
                # Why: a single candidate also has a trajectory `records` field and must stay one row.
                for key in ("candidates",):
                    value = payload.get(key)
                    if isinstance(value, list) and value and all(isinstance(item, Mapping) for item in value):
                        return _ensure_mapping_list(value)
                return [payload]
            raise CandidateSchemaError("json_root_not_object_or_array")

    rows: List[Mapping[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise CandidateSchemaError(f"line_{line_number}_not_object")
        rows.append(payload)
    return rows


def load_candidates(path: Path) -> List[Mapping[str, Any]]:
    return _parse_json_or_jsonl(path.read_text(encoding="utf-8"))


def write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize label-bearing Self-Instruct candidate JSON/JSONL and emit profile metrics.")
    parser.add_argument("--input", required=True, type=Path, help="Input JSON or JSONL candidate file.")
    parser.add_argument("--output", required=True, type=Path, help="Output canonical candidate JSONL path.")
    parser.add_argument("--profile-output", required=True, type=Path, help="Output candidate profile JSON path.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        candidates = load_candidates(args.input)
        normalized = normalize_candidates(candidates)
        profile_report = build_profile_report(normalized, input_path=args.input)
        write_jsonl(normalized, args.output)
        args.profile_output.parent.mkdir(parents=True, exist_ok=True)
        args.profile_output.write_text(
            json.dumps(profile_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, CandidateSchemaError) as exc:
        print(f"self_instruct_candidate_schema: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
