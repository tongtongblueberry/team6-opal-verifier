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
    build_profile_report,
    normalize_candidate,
    write_jsonl,
)


Json = Dict[str, Any]
PARSER_SCHEMA_VERSION = "self_instruct.raw_output_parser.v1"
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
                accepted.append(normalize_candidate(candidate_payload))
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
