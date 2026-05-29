# Changed: add Self-Instruct candidate filtering without generating new data.
# Why: official Self-Instruct filtering removes duplicates, conflicts, and near-duplicates before quality audit or training.
"""Deduplicate and filter normalized Self-Instruct Opal candidates.

This stdlib-only tool applies the filtering concepts from Self-Instruct to
Opal candidate rows: exact duplicate removal, same input with conflicting label
removal, ROUGE-L near-duplicate removal, and public20 exact/near duplicate
removal. The official Self-Instruct code filters near-duplicate instructions
with ROUGE-L < 0.7; in the Opal fixed-instruction domain, the default preserves
that official principle but applies ROUGE-L to domain-adapted trajectory text
instead of the near-constant instruction string. This is a data quality gate
only; it does not import runtime solver code or rule engines.
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
    load_candidates,
    normalize_candidate,
    write_jsonl,
)


Json = Dict[str, Any]
DEDUP_SCHEMA_VERSION = "self_instruct.candidate_dedup.v1"
DEFAULT_ROUGE_L_THRESHOLD = 0.7
DEFAULT_NEAR_DUPLICATE_MODE = "domain_text"
NEAR_DUPLICATE_MODES = ("domain_text", "trajectory_signature", "instruction")
FILTER_STAGE_BY_REASON = {
    "near_duplicate_domain_text": "domain_adapted_rouge_l",
    "near_duplicate_trajectory_signature": "domain_adapted_rouge_l",
    "near_duplicate_instruction": "legacy_instruction_level_rouge_l",
    "exact_duplicate": "trajectory_level_duplicate",
    "same_input_conflicting_label": "trajectory_level_duplicate",
    "public20_exact_duplicate": "public20_reference_overlap",
    "public20_near_duplicate": "public20_reference_overlap",
    "invalid_candidate": "schema_validation",
}


class DedupSelfInstructError(ValueError):
    """Raised when filtering input cannot be loaded safely."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _lcs_length(left: Sequence[str], right: Sequence[str]) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


# Changed: implement a stdlib-only ROUGE-L F1 proxy for filtering.
# Why: the official Self-Instruct threshold can be applied without adding a non-stdlib dependency.
def rouge_l_f1(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    lcs = _lcs_length(left_tokens, right_tokens)
    if lcs == 0:
        return 0.0
    precision = lcs / len(left_tokens)
    recall = lcs / len(right_tokens)
    return 2 * precision * recall / (precision + recall)


def _records_from_reference_row(row: Mapping[str, Any]) -> Any:
    records = row.get("records")
    if isinstance(records, list):
        return records
    for key in ("input", "input_text"):
        value = row.get(key)
        if not isinstance(value, str):
            continue
        payload = json.loads(value)
        if not isinstance(payload, Mapping):
            raise DedupSelfInstructError(f"{key}_json_root_not_object")
        records = payload.get("records")
        if not isinstance(records, list):
            raise DedupSelfInstructError("public20_records_not_list")
        return records
    raise DedupSelfInstructError("public20_records_missing")


def _iter_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise DedupSelfInstructError(f"line_{line_number}_not_object")
            yield payload


def load_public20_reference(path: Optional[Path]) -> List[Json]:
    if path is None:
        return []
    references: List[Json] = []
    for index, row in enumerate(_iter_jsonl(path)):
        records = _records_from_reference_row(row)
        references.append(
            {
                "sample_id": row.get("sample_id") or row.get("id") or f"public20-{index:03d}",
                "records_hash": _canonical_json(records),
                "records_text": _canonical_json(records),
            }
        )
    return references


def _candidate_exact_key(candidate: Mapping[str, Any]) -> str:
    # Changed: key exact duplicates by trajectory and label instead of fixed instruction text.
    # Why: official Self-Instruct filtering separates instruction-level ROUGE-L from trajectory-level duplicate filtering.
    return _canonical_json(
        {
            "records": candidate.get("records"),
            "label": candidate.get("label"),
        }
    )


# Changed: move default near-duplicate ROUGE-L text from fixed instruction text to Opal domain signatures.
# Why: official Self-Instruct instruction ROUGE-L would reject most Opal candidates because their task instruction is intentionally stable.
def _record_method(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_value = record.get("input")
    if not isinstance(input_value, Mapping):
        return ""
    method_value = input_value.get("method")
    if isinstance(method_value, Mapping):
        name = method_value.get("name")
        return str(name).strip() if name is not None else ""
    if method_value is not None:
        return str(method_value).strip()
    return ""


def _record_status(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    output_value = record.get("output")
    if not isinstance(output_value, Mapping):
        return ""
    for key in ("status_codes", "status", "status_code"):
        value = output_value.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _candidate_trajectory_signature(candidate: Mapping[str, Any]) -> str:
    records = candidate.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        return ""
    return " | ".join(f"{index}:{_record_method(record)}->{_record_status(record)}" for index, record in enumerate(records))


def _target_final_response(candidate: Mapping[str, Any]) -> Any:
    target = candidate.get("target")
    if isinstance(target, Mapping) and "final_response" in target:
        return target.get("final_response")
    records = candidate.get("records")
    if isinstance(records, Sequence) and not isinstance(records, (bytes, bytearray, str)) and records:
        final_record = records[-1]
        if isinstance(final_record, Mapping):
            return final_record.get("output")
    return None


def _spec_ref_rows(candidate: Mapping[str, Any]) -> List[Json]:
    grounding = candidate.get("spec_grounding")
    if not isinstance(grounding, Sequence) or isinstance(grounding, (bytes, bytearray, str)):
        return []
    rows: List[Json] = []
    for item in grounding:
        if not isinstance(item, Mapping):
            continue
        row: Json = {}
        for key in ("rule_ref", "source_span", "expected_status", "condition", "spec_section", "state_transition_notes"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                row[key] = value.strip()
        if row:
            rows.append(row)
    return rows


def _candidate_domain_signature(candidate: Mapping[str, Any]) -> str:
    return _canonical_json(
        {
            "trajectory_signature": _candidate_trajectory_signature(candidate),
            "target_final_response": _target_final_response(candidate),
            "spec_refs": _spec_ref_rows(candidate),
        }
    )


def _candidate_domain_text(candidate: Mapping[str, Any]) -> str:
    domain_payload = {
        "trajectory_signature": _candidate_trajectory_signature(candidate),
        "records": candidate.get("records"),
        "target": candidate.get("target"),
        "final_response": _target_final_response(candidate),
        "primary_evidence": candidate.get("primary_evidence"),
        "spec_refs": _spec_ref_rows(candidate),
    }
    return _canonical_json(domain_payload)


def _near_duplicate_reason(mode: str) -> str:
    if mode == "instruction":
        return "near_duplicate_instruction"
    if mode == "trajectory_signature":
        return "near_duplicate_trajectory_signature"
    return "near_duplicate_domain_text"


def _near_duplicate_text_and_signature(candidate: Mapping[str, Any], mode: str) -> Tuple[str, Optional[str]]:
    if mode == "instruction":
        return str(candidate.get("instruction", "")).strip(), None
    if mode == "trajectory_signature":
        return _candidate_trajectory_signature(candidate), None
    return _candidate_domain_text(candidate), _candidate_domain_signature(candidate)


def _filter_stage(reason: str) -> str:
    return FILTER_STAGE_BY_REASON.get(reason, "other")


def _reject(
    candidate: Mapping[str, Any],
    *,
    line_number: int,
    reason: str,
    details: Optional[Mapping[str, Any]] = None,
) -> Json:
    row: Json = {
        "line_number": line_number,
        "reason": reason,
        "filter_stage": _filter_stage(reason),
        "sample_id": candidate.get("sample_id"),
    }
    if details:
        row["details"] = dict(details)
    return row


def dedup_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    public20_references: Sequence[Mapping[str, Any]] = (),
    rouge_l_threshold: float = DEFAULT_ROUGE_L_THRESHOLD,
    near_duplicate_mode: str = DEFAULT_NEAR_DUPLICATE_MODE,
) -> Tuple[List[Json], List[Json]]:
    if near_duplicate_mode not in NEAR_DUPLICATE_MODES:
        raise DedupSelfInstructError(f"near_duplicate_mode_not_supported:{near_duplicate_mode}")
    accepted: List[Json] = []
    rejected: List[Json] = []
    seen_exact_keys: Dict[str, str] = {}
    seen_input_labels: Dict[str, str] = {}
    accepted_near_duplicate_rows: List[Tuple[str, str, Optional[str]]] = []

    for line_number, raw_candidate in enumerate(candidates, start=1):
        try:
            candidate = normalize_candidate(raw_candidate)
        except CandidateSchemaError as exc:
            rejected.append(
                {
                    "line_number": line_number,
                    "reason": "invalid_candidate",
                    "filter_stage": _filter_stage("invalid_candidate"),
                    "details": {"schema_error": str(exc)},
                    "sample_id": raw_candidate.get("sample_id") if isinstance(raw_candidate, Mapping) else None,
                }
            )
            continue

        records_hash = _canonical_json(candidate["records"])
        records_text = records_hash
        label = str(candidate["label"])
        exact_key = _candidate_exact_key(candidate)

        public20_match = next((row for row in public20_references if row.get("records_hash") == records_hash), None)
        if public20_match is not None:
            rejected.append(
                _reject(
                    candidate,
                    line_number=line_number,
                    reason="public20_exact_duplicate",
                    details={"public20_sample_id": public20_match.get("sample_id")},
                )
            )
            continue

        near_public20_match: Optional[Mapping[str, Any]] = None
        near_public20_score = 0.0
        for reference in public20_references:
            score = rouge_l_f1(records_text, str(reference.get("records_text", "")))
            if score >= rouge_l_threshold and score > near_public20_score:
                near_public20_match = reference
                near_public20_score = score
        if near_public20_match is not None:
            rejected.append(
                _reject(
                    candidate,
                    line_number=line_number,
                    reason="public20_near_duplicate",
                    details={
                        "public20_sample_id": near_public20_match.get("sample_id"),
                        "rouge_l": round(near_public20_score, 6),
                        "threshold": rouge_l_threshold,
                    },
                )
            )
            continue

        previous_label = seen_input_labels.get(records_hash)
        if previous_label is not None and previous_label != label:
            rejected.append(
                _reject(
                    candidate,
                    line_number=line_number,
                    reason="same_input_conflicting_label",
                    details={"previous_label": previous_label, "current_label": label},
                )
            )
            continue

        previous_exact_sample_id = seen_exact_keys.get(exact_key)
        if previous_exact_sample_id is not None:
            rejected.append(
                _reject(
                    candidate,
                    line_number=line_number,
                    reason="exact_duplicate",
                    details={"previous_sample_id": previous_exact_sample_id},
                )
            )
            continue

        near_duplicate_text, near_duplicate_signature = _near_duplicate_text_and_signature(candidate, near_duplicate_mode)
        near_duplicate_match: Optional[Tuple[str, float]] = None
        for previous_sample_id, previous_text, previous_signature in accepted_near_duplicate_rows:
            if near_duplicate_signature is not None and previous_signature != near_duplicate_signature:
                continue
            score = rouge_l_f1(near_duplicate_text, previous_text)
            if score >= rouge_l_threshold:
                near_duplicate_match = (previous_sample_id, score)
                break
        if near_duplicate_match is not None:
            reason = _near_duplicate_reason(near_duplicate_mode)
            details: Json = {
                "previous_sample_id": near_duplicate_match[0],
                "rouge_l": round(near_duplicate_match[1], 6),
                "threshold": rouge_l_threshold,
                "near_duplicate_mode": near_duplicate_mode,
            }
            if near_duplicate_signature is not None:
                details["domain_signature"] = near_duplicate_signature
            rejected.append(
                _reject(
                    candidate,
                    line_number=line_number,
                    reason=reason,
                    details=details,
                )
            )
            continue

        accepted.append(candidate)
        seen_exact_keys[exact_key] = str(candidate.get("sample_id"))
        seen_input_labels[records_hash] = label
        accepted_near_duplicate_rows.append((str(candidate.get("sample_id")), near_duplicate_text, near_duplicate_signature))

    return accepted, rejected


def build_report(
    input_path: Path,
    accepted: Sequence[Mapping[str, Any]],
    rejected: Sequence[Mapping[str, Any]],
    *,
    public20_reference_path: Optional[Path],
    rouge_l_threshold: float,
    near_duplicate_mode: str = DEFAULT_NEAR_DUPLICATE_MODE,
) -> Json:
    reject_reason_counts: Json = {}
    reject_filter_stage_counts: Json = {}
    for row in rejected:
        reason = str(row.get("reason", "unknown"))
        reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
        filter_stage = str(row.get("filter_stage") or _filter_stage(reason))
        reject_filter_stage_counts[filter_stage] = reject_filter_stage_counts.get(filter_stage, 0) + 1
    return {
        "schema_version": DEDUP_SCHEMA_VERSION,
        "input": str(input_path),
        "public20_reference": str(public20_reference_path) if public20_reference_path else None,
        "rouge_l_threshold": rouge_l_threshold,
        "near_duplicate_mode": near_duplicate_mode,
        "near_duplicate_mode_default": DEFAULT_NEAR_DUPLICATE_MODE,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "reject_reason_counts": reject_reason_counts,
        # Changed: report domain-adapted ROUGE-L separately from exact/conflict/public20 filters.
        # Why: Opal fixed-instruction candidates must preserve the official Self-Instruct near-duplicate principle without instruction-only collapse.
        "reject_filter_stage_counts": reject_filter_stage_counts,
    }


def write_rejects(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deduplicate and filter canonical Self-Instruct candidate JSON/JSONL.")
    parser.add_argument("--input", required=True, type=Path, help="Input candidate JSON or JSONL path.")
    parser.add_argument("--output", required=True, type=Path, help="Accepted candidate JSONL output path.")
    parser.add_argument("--reject-output", required=True, type=Path, help="Rejected rows JSONL output path.")
    parser.add_argument("--report-json", required=True, type=Path, help="Summary JSON output path.")
    parser.add_argument("--public20-reference-jsonl", type=Path, default=None, help="Optional public20 input-only or normalized JSONL reference.")
    parser.add_argument("--rouge-l-threshold", type=float, default=DEFAULT_ROUGE_L_THRESHOLD, help="Near-duplicate threshold. Default: 0.7.")
    parser.add_argument(
        "--near-duplicate-mode",
        choices=NEAR_DUPLICATE_MODES,
        default=DEFAULT_NEAR_DUPLICATE_MODE,
        help=(
            "Near-duplicate ROUGE-L comparison text. Default: domain_text. "
            "Use instruction only for legacy official-instruction-scope compatibility."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        if not 0.0 < args.rouge_l_threshold <= 1.0:
            raise DedupSelfInstructError("rouge_l_threshold_out_of_range")
        candidates = load_candidates(args.input)
        public20_references = load_public20_reference(args.public20_reference_jsonl)
        accepted, rejected = dedup_candidates(
            candidates,
            public20_references=public20_references,
            rouge_l_threshold=args.rouge_l_threshold,
            near_duplicate_mode=args.near_duplicate_mode,
        )
        write_jsonl(accepted, args.output)
        write_rejects(rejected, args.reject_output)
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(
                build_report(
                    args.input,
                    accepted,
                    rejected,
                    public20_reference_path=args.public20_reference_jsonl,
                    rouge_l_threshold=args.rouge_l_threshold,
                    near_duplicate_mode=args.near_duplicate_mode,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, CandidateSchemaError, DedupSelfInstructError) as exc:
        print(f"dedup_self_instruct_candidates: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
