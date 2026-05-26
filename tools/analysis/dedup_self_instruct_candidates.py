# Changed: add Self-Instruct candidate filtering without generating new data.
# Why: official Self-Instruct filtering removes duplicates, conflicts, and near-duplicates before quality audit or training.
"""Deduplicate and filter normalized Self-Instruct Opal candidates.

This stdlib-only tool applies the filtering concepts from Self-Instruct to
Opal candidate rows: exact duplicate removal, same input with conflicting label
removal, ROUGE-L near-duplicate instruction removal, and public20 exact/near
duplicate removal. The default ROUGE-L threshold is 0.7, matching the threshold
reported by the official Self-Instruct filtering protocol. This is a data
quality gate only; it does not import runtime solver code or rule engines.
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
    return _canonical_json(
        {
            "instruction": str(candidate.get("instruction", "")).strip(),
            "records": candidate.get("records"),
            "label": candidate.get("label"),
        }
    )


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
) -> Tuple[List[Json], List[Json]]:
    accepted: List[Json] = []
    rejected: List[Json] = []
    seen_exact_keys: Dict[str, str] = {}
    seen_input_labels: Dict[str, str] = {}
    accepted_instruction_rows: List[Tuple[str, str]] = []

    for line_number, raw_candidate in enumerate(candidates, start=1):
        try:
            candidate = normalize_candidate(raw_candidate)
        except CandidateSchemaError as exc:
            rejected.append(
                {
                    "line_number": line_number,
                    "reason": "invalid_candidate",
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

        instruction = str(candidate.get("instruction", "")).strip()
        near_instruction_match: Optional[Tuple[str, str, float]] = None
        for previous_sample_id, previous_instruction in accepted_instruction_rows:
            score = rouge_l_f1(instruction, previous_instruction)
            if score >= rouge_l_threshold:
                near_instruction_match = (previous_sample_id, previous_instruction, score)
                break
        if near_instruction_match is not None:
            rejected.append(
                _reject(
                    candidate,
                    line_number=line_number,
                    reason="near_duplicate_instruction",
                    details={
                        "previous_sample_id": near_instruction_match[0],
                        "rouge_l": round(near_instruction_match[2], 6),
                        "threshold": rouge_l_threshold,
                    },
                )
            )
            continue

        accepted.append(candidate)
        seen_exact_keys[exact_key] = str(candidate.get("sample_id"))
        seen_input_labels[records_hash] = label
        accepted_instruction_rows.append((str(candidate.get("sample_id")), instruction))

    return accepted, rejected


def build_report(
    input_path: Path,
    accepted: Sequence[Mapping[str, Any]],
    rejected: Sequence[Mapping[str, Any]],
    *,
    public20_reference_path: Optional[Path],
    rouge_l_threshold: float,
) -> Json:
    reject_reason_counts: Json = {}
    for row in rejected:
        reason = str(row.get("reason", "unknown"))
        reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
    return {
        "schema_version": DEDUP_SCHEMA_VERSION,
        "input": str(input_path),
        "public20_reference": str(public20_reference_path) if public20_reference_path else None,
        "rouge_l_threshold": rouge_l_threshold,
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
    parser = argparse.ArgumentParser(description="Deduplicate and filter canonical Self-Instruct candidate JSON/JSONL.")
    parser.add_argument("--input", required=True, type=Path, help="Input candidate JSON or JSONL path.")
    parser.add_argument("--output", required=True, type=Path, help="Accepted candidate JSONL output path.")
    parser.add_argument("--reject-output", required=True, type=Path, help="Rejected rows JSONL output path.")
    parser.add_argument("--report-json", required=True, type=Path, help="Summary JSON output path.")
    parser.add_argument("--public20-reference-jsonl", type=Path, default=None, help="Optional public20 input-only or normalized JSONL reference.")
    parser.add_argument("--rouge-l-threshold", type=float, default=DEFAULT_ROUGE_L_THRESHOLD, help="Near-duplicate threshold. Default: 0.7.")
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
