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
# Changed: centralize the fixed Opal verifier instruction used by Qwen generation.
# Why: Self-Instruct instruction generation is an audited no-op for this task, so raw candidates must be checked against one stable final-pair instruction string.
FIXED_OPAL_VERIFIER_INSTRUCTION = (
    "Given the full Opal command-response trajectory, judge only whether the final command-response pair (cN, rN) is valid under the cited rule-book."
)


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


def _normalize_status_codes_value(value: Any) -> Any:
    # Changed: canonicalize generated Opal status fields to lists.
    # Why: Qwen sometimes emits "SUCCESS" while public-style records use status_codes as a list.
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [str(item).strip() for item in value if str(item).strip()]
    return value


def _normalize_status_codes_mapping(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    normalized = copy.deepcopy(dict(value))
    if "status_codes" in normalized:
        normalized["status_codes"] = _normalize_status_codes_value(normalized["status_codes"])
    return normalized


def _normalize_record_status_codes(records: Sequence[Any]) -> List[Any]:
    # Changed: normalize status_codes in record input/output before target comparison and export.
    # Why: final public schema should not mix string and list status representations.
    normalized_records = copy.deepcopy(list(records))
    for record in normalized_records:
        if not isinstance(record, Mapping):
            continue
        for key in ("input", "output"):
            if isinstance(record.get(key), Mapping):
                record[key] = _normalize_status_codes_mapping(record[key])
    return normalized_records


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
    target_final_response = _normalize_status_codes_mapping(target.get("final_response"))
    if target_final_response != final_response:
        raise CandidateSchemaError("target_response_not_last_record_output")

    normalized: Json = {
        "final_response_index": final_index,
        "final_response": target_final_response,
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


# Changed: require source-span grounding metadata on generated candidates.
# Why: ungrounded LLM text must not advance from raw output into judge, Gate A, or manifest staging.
def _normalize_spec_grounding(candidate: Mapping[str, Any]) -> List[Json]:
    grounding = candidate.get("spec_grounding")
    if not isinstance(grounding, Sequence) or isinstance(grounding, (bytes, bytearray, str)) or len(grounding) == 0:
        raise CandidateSchemaError("spec_grounding_missing")

    normalized: List[Json] = []
    for index, item in enumerate(grounding):
        if not isinstance(item, Mapping):
            raise CandidateSchemaError(f"spec_grounding_{index}_not_object")

        rule_ref = _required_string(item, ("rule_ref", "rule_citation", "spec_rule_ref"), f"spec_grounding_{index}_rule_ref")
        source_path = _required_string(item, ("source_path",), f"spec_grounding_{index}_source_path")
        source_span = _required_string(item, ("source_span",), f"spec_grounding_{index}_source_span")
        if "docs/legacy_spec_rules.md" not in source_path and "docs/legacy_spec_rules.md" not in source_span:
            raise CandidateSchemaError(f"spec_grounding_{index}_source_not_legacy_spec_rules")
        if ":" not in source_span or "-" not in source_span:
            raise CandidateSchemaError(f"spec_grounding_{index}_source_span_not_line_range")

        row: Json = {
            "rule_ref": rule_ref,
            "source_path": source_path,
            "source_span": source_span,
        }
        for source_key, output_key in (
            ("spec_section", "spec_section"),
            ("condition", "condition"),
            ("expected_status", "expected_status"),
            ("state_transition_notes", "state_transition_notes"),
        ):
            value = item.get(source_key)
            if isinstance(value, str) and value.strip():
                row[output_key] = value.strip()
        normalized.append(row)
    return normalized


# Changed: require generated-instruction provenance on every candidate row.
# Why: official Self-Instruct instance rows must trace back to the instruction generation and classification-detection artifacts.
def _normalize_generation_provenance(candidate: Mapping[str, Any]) -> Json:
    provenance_value = candidate.get("generation_provenance")
    if not isinstance(provenance_value, Mapping):
        provenance_value = candidate.get("provenance")
    provenance = dict(provenance_value) if isinstance(provenance_value, Mapping) else {}

    source_instruction_id = candidate.get("source_instruction_id") or provenance.get("source_instruction_id")
    if not isinstance(source_instruction_id, str) or not source_instruction_id.strip():
        raise CandidateSchemaError(
            "source_instruction_id_missing; migration: set source_instruction_id or "
            "generation_provenance.source_instruction_id from the machine_generated_instructions dry-run artifact"
        )

    normalized: Json = {
        "source_instruction_id": source_instruction_id.strip(),
        "official_instruction_artifact": provenance.get("official_instruction_artifact")
        or "machine_generated_instructions.jsonl",
        "official_instance_artifact": provenance.get("official_instance_artifact")
        or "machine_generated_instances.jsonl",
    }
    for key in (
        "classification_detection_id",
        "official_classification_artifact",
        "instance_generation_request_id",
        "raw_output_request_id",
        "provenance_migration",
        "parser_source_line",
    ):
        value = candidate.get(key) if key in candidate else provenance.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()
        elif isinstance(value, int):
            normalized[key] = value
    return normalized


# Changed: canonicalize label-bearing candidate rows and run the final-response invariant gate.
# Why: generated labels must target records[-1].output before any judge, manifest, or training step.
def normalize_candidate(candidate: Mapping[str, Any]) -> Json:
    if not isinstance(candidate, Mapping):
        raise CandidateSchemaError("candidate_not_mapping")

    sample_id = _required_string(candidate, ("sample_id", "candidate_id", "id"), "sample_id")
    instruction = _required_string(candidate, ("instruction", "task_instruction"), "instruction")
    records = _normalize_record_status_codes(_extract_records(candidate))
    final_index = len(records) - 1
    final_response = _final_output(records)

    label = normalize_label(candidate.get("label"))
    if label is None:
        raise CandidateSchemaError("invalid_label")
    generation_provenance = _normalize_generation_provenance(candidate)

    label_target = candidate.get("label_target")
    if label_target is not None and str(label_target).strip().lower() != "final_response":
        raise CandidateSchemaError("label_target_not_final_response")

    normalized: Json = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "sample_id": sample_id,
        "source_instruction_id": generation_provenance["source_instruction_id"],
        "instruction": instruction,
        "records": records,
        "label": label,
        "label_target": "final_response",
        "target": _normalize_target(candidate, final_index, final_response),
        "primary_evidence": _normalize_primary_evidence(candidate, final_index),
        "spec_grounding": _normalize_spec_grounding(candidate),
        "generation_provenance": generation_provenance,
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
    grounding = candidate.get("spec_grounding")
    if isinstance(grounding, Sequence) and not isinstance(grounding, (bytes, bytearray, str)):
        profile["spec_rule_refs"] = [
            item.get("rule_ref")
            for item in grounding
            if isinstance(item, Mapping) and isinstance(item.get("rule_ref"), str)
        ]
    profile["source_instruction_id"] = candidate.get("source_instruction_id")
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
