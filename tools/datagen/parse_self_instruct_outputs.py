# Changed: add a parser for externally generated Self-Instruct raw outputs.
# Why: LLM responses must be normalized and rejected through the candidate schema without adding another ad-hoc generator.
"""Parse raw Self-Instruct LLM outputs into canonical Opal candidates.

This tool does not call an LLM, does not create trajectories, and does not
label data. It only reads raw JSON/JSONL or text responses already produced by
the Self-Instruct output-first generation step, parses candidate objects, then
normalizes them with ``self_instruct_candidate_schema.normalize_candidate``.
Invalid JSON, missing fields, and final-response invariant failures are written
to a reject report without copying raw response text into that report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.self_instruct_candidate_schema import (  # noqa: E402
    CandidateSchemaError,
    FIXED_OPAL_VERIFIER_INSTRUCTION,
    build_profile_report,
    normalize_candidate,
    write_jsonl,
)


Json = Dict[str, Any]
PARSER_SCHEMA_VERSION = "self_instruct.raw_output_parser.v1"
PREPARED_CANDIDATE_ARTIFACT_SCHEMA_VERSION = "self_instruct.prepare_for_finetuning_candidate.v1"
RAW_TEXT_KEYS = (
    "raw_output",
    "llm_output",
    "completion",
    "response",
    "text",
    "content",
)


class ParseSelfInstructOutputError(ValueError):
    """Raised when a raw Self-Instruct response cannot be parsed."""


def _ensure_mapping(value: Any, *, reason: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ParseSelfInstructOutputError(reason)
    return value


def _expand_payload(payload: Any) -> List[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            rows: List[Mapping[str, Any]] = []
            for index, item in enumerate(candidates):
                rows.append(_ensure_mapping(item, reason=f"candidates_{index}_not_object"))
            return rows
        candidate = payload.get("candidate")
        if isinstance(candidate, Mapping):
            return [candidate]
        return [payload]
    if isinstance(payload, list):
        rows = []
        for index, item in enumerate(payload):
            rows.append(_ensure_mapping(item, reason=f"item_{index}_not_object"))
        return rows
    raise ParseSelfInstructOutputError("parsed_payload_not_object_or_array")


def _extract_json_from_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise ParseSelfInstructOutputError("raw_text_empty")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        fenced = fence_match.group(1).strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    for start, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError:
            continue
        return payload

    raise ParseSelfInstructOutputError("json_payload_not_found")


def _candidate_payloads_from_raw_row(row: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    if isinstance(row.get("candidate"), Mapping) or isinstance(row.get("candidates"), list):
        return _expand_payload(row)
    for key in RAW_TEXT_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            return _expand_payload(_extract_json_from_text(value))
    return _expand_payload(row)


# Changed: carry request/instruction provenance from raw wrapper rows into candidate normalization.
# Why: official instance-generation raw outputs must preserve their machine_generated_instructions and is_clf_or_not lineage.
def _candidate_with_raw_provenance(candidate: Mapping[str, Any], raw_row: Mapping[str, Any], line_number: int) -> Json:
    merged: Json = dict(candidate)
    provenance = dict(merged.get("generation_provenance")) if isinstance(merged.get("generation_provenance"), Mapping) else {}
    for raw_key, provenance_key in (
        ("request_id", "raw_output_request_id"),
        ("source_instruction_id", "source_instruction_id"),
        ("classification_detection_id", "classification_detection_id"),
    ):
        value = raw_row.get(raw_key)
        if isinstance(value, str) and value.strip() and provenance_key not in provenance and provenance_key not in merged:
            provenance[provenance_key] = value.strip()
    # Changed: provide an explicit legacy migration path for old raw wrappers that predate instruction artifacts.
    # Why: backward-compatible parser tests may validate wiring, but migrated rows remain provenance-marked and are not accepted synthetic data.
    if "source_instruction_id" not in provenance and "source_instruction_id" not in merged:
        request_id = raw_row.get("request_id")
        if isinstance(request_id, str) and request_id.strip():
            provenance["source_instruction_id"] = f"legacy-migrated:{request_id.strip()}"
            provenance["provenance_migration"] = "missing source_instruction_id in raw wrapper; set from request_id for parser compatibility only"
    provenance.setdefault("official_instruction_artifact", "machine_generated_instructions.jsonl")
    provenance.setdefault("official_classification_artifact", "is_clf_or_not_<engine>_<template>.jsonl")
    provenance.setdefault("official_instance_artifact", "machine_generated_instances.jsonl")
    provenance["parser_source_line"] = line_number
    merged["generation_provenance"] = provenance
    return merged


# Changed: reject raw candidates that drift from the fixed instruction or encode empty/null instance inputs.
# Why: this Opal task does not generate new instructions, and X_t,i must be a concrete trajectory record rather than a null/empty placeholder.
def _null_paths(value: Any, prefix: Sequence[str]) -> List[str]:
    if value is None:
        return [".".join(prefix)]
    if isinstance(value, Mapping):
        paths: List[str] = []
        for key, item in value.items():
            paths.extend(_null_paths(item, [*prefix, str(key)]))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_null_paths(item, [*prefix, str(index)]))
        return paths
    return []


def _records_for_quality_gate(candidate: Mapping[str, Any]) -> Any:
    records = candidate.get("records")
    if records is None and isinstance(candidate.get("trajectory"), Mapping):
        records = candidate["trajectory"].get("records")
    return records


def _validate_fixed_instruction_and_inputs(candidate: Mapping[str, Any]) -> None:
    instruction = candidate.get("instruction") or candidate.get("task_instruction")
    if not isinstance(instruction, str) or instruction.strip() != FIXED_OPAL_VERIFIER_INSTRUCTION:
        raise CandidateSchemaError("instruction_not_fixed")

    records = _records_for_quality_gate(candidate)
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        return

    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        input_payload = record.get("input")
        if not isinstance(input_payload, Mapping):
            continue
        null_paths = _null_paths(input_payload, ["records", str(index), "input"])
        if null_paths:
            raise CandidateSchemaError(f"record_{index}_input_contains_null:{null_paths[0]}")

        method = input_payload.get("method")
        if not isinstance(method, Mapping):
            continue
        args = method.get("args")
        if not isinstance(args, Mapping):
            raise CandidateSchemaError(f"record_{index}_method_args_missing")
        if not isinstance(args.get("required"), Mapping) or not isinstance(args.get("optional"), Mapping):
            raise CandidateSchemaError(f"record_{index}_method_args_not_required_optional")
        if set(args.keys()) == set() or args == {}:
            raise CandidateSchemaError(f"record_{index}_method_args_bare_empty")

        invoking_id = input_payload.get("invoking_id")
        if isinstance(invoking_id, Mapping):
            uid = invoking_id.get("uid")
            if not isinstance(uid, str) or not uid.strip():
                raise CandidateSchemaError(f"record_{index}_invoking_id_uid_empty")


def _iter_jsonl_rows(path: Path) -> Iterable[Tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise ParseSelfInstructOutputError(f"line_{line_number}_not_object")
            yield line_number, payload


def parse_raw_output_rows(rows: Iterable[Tuple[int, Mapping[str, Any]]]) -> Tuple[List[Json], List[Json]]:
    accepted: List[Json] = []
    rejected: List[Json] = []
    for line_number, raw_row in rows:
        try:
            candidate_payloads = _candidate_payloads_from_raw_row(raw_row)
        except (json.JSONDecodeError, ParseSelfInstructOutputError) as exc:
            rejected.append(
                {
                    "line_number": line_number,
                    "candidate_index": None,
                    "stage": "parse",
                    "reason": str(exc),
                    "raw_keys": sorted(str(key) for key in raw_row.keys()),
                }
            )
            continue

        for candidate_index, candidate_payload in enumerate(candidate_payloads):
            try:
                _validate_fixed_instruction_and_inputs(candidate_payload)
                accepted.append(normalize_candidate(_candidate_with_raw_provenance(candidate_payload, raw_row, line_number)))
            except CandidateSchemaError as exc:
                rejected.append(
                    {
                        "line_number": line_number,
                        "candidate_index": candidate_index,
                        "stage": "normalize",
                        "reason": str(exc),
                        "sample_id": candidate_payload.get("sample_id")
                        or candidate_payload.get("candidate_id")
                        or candidate_payload.get("id"),
                        "raw_keys": sorted(str(key) for key in candidate_payload.keys()),
                    }
                )
    return accepted, rejected


def build_report(input_path: Path, accepted: Sequence[Mapping[str, Any]], rejected: Sequence[Mapping[str, Any]]) -> Json:
    reject_reason_counts: Json = {}
    for row in rejected:
        reason = str(row.get("reason", "unknown"))
        reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
    return {
        "schema_version": PARSER_SCHEMA_VERSION,
        "prepared_candidate_artifact_schema_version": PREPARED_CANDIDATE_ARTIFACT_SCHEMA_VERSION,
        "official_counterpart": "prepare_for_finetuning.py outputs",
        "official_stage": "candidate_preparation",
        "input": str(input_path),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "reject_reason_counts": reject_reason_counts,
    }


def write_rejects(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse raw Self-Instruct LLM output JSONL into canonical candidate JSONL.")
    parser.add_argument("--input", required=True, type=Path, help="Raw JSONL file containing candidate objects or raw LLM text fields.")
    parser.add_argument("--output", required=True, type=Path, help="Accepted canonical candidate JSONL output.")
    parser.add_argument("--reject-output", required=True, type=Path, help="Rejected rows JSONL output.")
    parser.add_argument("--report-json", required=True, type=Path, help="Parser summary JSON output.")
    parser.add_argument("--profile-output", type=Path, default=None, help="Optional accepted candidate profile JSON output.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        accepted, rejected = parse_raw_output_rows(_iter_jsonl_rows(args.input))
        write_jsonl(accepted, args.output)
        write_rejects(rejected, args.reject_output)
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(build_report(args.input, accepted, rejected), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.profile_output is not None:
            profile_report = build_profile_report(accepted, input_path=args.output)
            args.profile_output.parent.mkdir(parents=True, exist_ok=True)
            args.profile_output.write_text(
                json.dumps(profile_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (OSError, json.JSONDecodeError, ParseSelfInstructOutputError) as exc:
        print(f"parse_self_instruct_outputs: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
