# Changed: add a dry-run LLM-only judge request builder and result parser.
# Why: Self-Instruct candidates need an offline judge filter without adding runtime rule engines or direct API calls.
"""Build and parse Self-Instruct judge filter artifacts.

This module does not call an LLM by default. It builds judge prompt payloads
for normalized candidates and can parse externally produced judge JSON results
into accepted/rejected candidate JSONL files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.self_instruct_candidate_schema import (  # noqa: E402
    CandidateSchemaError,
    load_candidates,
    normalize_candidates,
    write_jsonl,
)


Json = Dict[str, Any]
JUDGE_REQUEST_SCHEMA_VERSION = "self_instruct.judge_request.v1"
JUDGE_REPORT_SCHEMA_VERSION = "self_instruct.judge_filter_report.v1"
JUDGE_CONTRACT_VERSION = "opal_final_response_judge.v1"
RAW_JUDGE_TEXT_KEYS = ("judge_output", "raw_output", "llm_output", "response", "text", "content")
REQUIRED_BOOL_FIELDS = (
    "is_final_response_targeted",
    "is_label_plausible",
    "has_intermediate_label_leak",
    "has_public_or_rule_leakage",
)


class SelfInstructJudgeError(ValueError):
    """Raised when judge request/result artifacts cannot be handled safely."""


def _now_kst() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).replace(microsecond=0).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _write_json(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise SelfInstructJudgeError(f"line_{line_number}_not_object")
            yield line_number, payload


def _extract_json_from_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise SelfInstructJudgeError("judge_text_empty")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1).strip())
    decoder = json.JSONDecoder()
    for start, char in enumerate(stripped):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError:
            continue
        return payload
    raise SelfInstructJudgeError("judge_json_payload_not_found")


def _candidate_for_judge(candidate: Mapping[str, Any]) -> Json:
    return {
        "sample_id": candidate.get("sample_id"),
        "instruction": candidate.get("instruction"),
        "records": candidate.get("records"),
        "generated_label": candidate.get("label"),
        "label_target": candidate.get("label_target"),
        "target": candidate.get("target"),
        "primary_evidence": candidate.get("primary_evidence"),
    }


def _judge_system_prompt() -> str:
    return (
        "You are an offline data-quality judge for Self-Instruct Opal verifier candidates. "
        "You are not a runtime solver and you must not use rule-engine outputs or public labels."
    )


def _judge_user_prompt(candidate: Mapping[str, Any]) -> str:
    prompt_spec = {
        "task": "Judge whether this generated candidate should be accepted for later Gate A state-transition audit.",
        "candidate": _candidate_for_judge(candidate),
        "judge_questions": {
            "is_final_response_targeted": "Is the label evidence tied to records[-1].output rather than an intermediate response?",
            "is_label_plausible": "Is the generated pass/fail label plausible from the final response and trajectory state?",
            "has_intermediate_label_leak": "Does the rationale rely on an intermediate success/failure as the main label evidence?",
            "has_public_or_rule_leakage": "Does the candidate include public labels, rule ids, rule-engine text, or archived verifier outputs?",
            "decision": "accept or reject",
        },
        "accept_condition": [
            'decision == "accept"',
            "is_final_response_targeted == true",
            "is_label_plausible == true",
            "has_intermediate_label_leak == false",
            "has_public_or_rule_leakage == false",
        ],
        "required_response_json": {
            "sample_id": candidate.get("sample_id"),
            "decision": "accept|reject",
            "is_final_response_targeted": "boolean",
            "is_label_plausible": "boolean",
            "has_intermediate_label_leak": "boolean",
            "has_public_or_rule_leakage": "boolean",
            "rationale": "short reason",
        },
    }
    return json.dumps(prompt_spec, ensure_ascii=False, indent=2, sort_keys=True)


def build_judge_request(candidate: Mapping[str, Any], *, model: str, created_at_kst: str) -> Json:
    sample_id = candidate.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id:
        raise SelfInstructJudgeError("candidate_sample_id_missing")
    request_id = f"self-instruct-judge-{sample_id}"
    payload: Json = {
        "model": model,
        "messages": [
            {"role": "system", "content": _judge_system_prompt()},
            {"role": "user", "content": _judge_user_prompt(candidate)},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "judge_contract_version": JUDGE_CONTRACT_VERSION,
    }
    return {
        "schema_version": JUDGE_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "sample_id": sample_id,
        "created_at_kst": created_at_kst,
        "execute": False,
        "judge_contract_version": JUDGE_CONTRACT_VERSION,
        "payload_sha256": _sha256_json(payload),
        "payload": payload,
    }


def build_judge_requests(candidates: Sequence[Mapping[str, Any]], *, model: str, created_at_kst: Optional[str] = None) -> List[Json]:
    timestamp = created_at_kst or _now_kst()
    return [build_judge_request(candidate, model=model, created_at_kst=timestamp) for candidate in candidates]


def _judge_payload_from_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in RAW_JUDGE_TEXT_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            payload = _extract_json_from_text(value)
            if not isinstance(payload, Mapping):
                raise SelfInstructJudgeError("judge_payload_not_object")
            return payload
    return row


def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise SelfInstructJudgeError(f"{field}_not_boolean")


def normalize_judge_decision(row: Mapping[str, Any]) -> Json:
    payload = _judge_payload_from_row(row)
    decision = str(payload.get("decision", "")).strip().lower()
    if decision not in {"accept", "reject"}:
        raise SelfInstructJudgeError("decision_not_accept_or_reject")
    sample_id = payload.get("sample_id") or row.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id:
        raise SelfInstructJudgeError("sample_id_missing")
    normalized: Json = {
        "sample_id": sample_id,
        "decision": decision,
        "is_final_response_targeted": _as_bool(payload.get("is_final_response_targeted"), "is_final_response_targeted"),
        "is_label_plausible": _as_bool(payload.get("is_label_plausible"), "is_label_plausible"),
        "has_intermediate_label_leak": _as_bool(payload.get("has_intermediate_label_leak"), "has_intermediate_label_leak"),
        "has_public_or_rule_leakage": _as_bool(payload.get("has_public_or_rule_leakage"), "has_public_or_rule_leakage"),
        "rationale": payload.get("rationale") if isinstance(payload.get("rationale"), str) else "",
    }
    if isinstance(row.get("request_id"), str):
        normalized["request_id"] = row["request_id"]
    return normalized


def judge_decision_accepts(decision: Mapping[str, Any]) -> bool:
    return (
        decision.get("decision") == "accept"
        and decision.get("is_final_response_targeted") is True
        and decision.get("is_label_plausible") is True
        and decision.get("has_intermediate_label_leak") is False
        and decision.get("has_public_or_rule_leakage") is False
    )


def _reject_reason(decision: Mapping[str, Any]) -> str:
    if decision.get("decision") != "accept":
        return "judge_decision_reject"
    if decision.get("is_final_response_targeted") is not True:
        return "not_final_response_targeted"
    if decision.get("is_label_plausible") is not True:
        return "label_not_plausible"
    if decision.get("has_intermediate_label_leak") is not False:
        return "intermediate_label_leak"
    if decision.get("has_public_or_rule_leakage") is not False:
        return "public_or_rule_leakage"
    return "unknown_reject"


def apply_judge_results(
    candidates: Sequence[Mapping[str, Any]],
    result_rows: Iterable[Tuple[int, Mapping[str, Any]]],
) -> Tuple[List[Json], List[Json], List[Json]]:
    by_sample_id = {str(candidate.get("sample_id")): candidate for candidate in candidates}
    accepted: List[Json] = []
    rejected: List[Json] = []
    decisions: List[Json] = []

    for line_number, row in result_rows:
        try:
            decision = normalize_judge_decision(row)
        except (json.JSONDecodeError, SelfInstructJudgeError) as exc:
            rejected.append(
                {
                    "line_number": line_number,
                    "sample_id": row.get("sample_id"),
                    "stage": "judge_parse",
                    "reason": str(exc),
                    "raw_keys": sorted(str(key) for key in row.keys()),
                }
            )
            continue

        decisions.append(decision)
        sample_id = str(decision["sample_id"])
        candidate = by_sample_id.get(sample_id)
        if candidate is None:
            rejected.append(
                {
                    "line_number": line_number,
                    "sample_id": sample_id,
                    "stage": "judge_match",
                    "reason": "candidate_not_found",
                    "decision": decision,
                }
            )
            continue
        if judge_decision_accepts(decision):
            accepted.append(dict(candidate))
        else:
            rejected.append(
                {
                    "line_number": line_number,
                    "sample_id": sample_id,
                    "stage": "judge_decision",
                    "reason": _reject_reason(decision),
                    "decision": decision,
                }
            )
    return accepted, rejected, decisions


def build_report(
    *,
    candidates_path: Path,
    request_count: int,
    accepted: Sequence[Mapping[str, Any]],
    rejected: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> Json:
    reject_reason_counts: Json = {}
    for row in rejected:
        reason = str(row.get("reason", "unknown"))
        reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
    return {
        "schema_version": JUDGE_REPORT_SCHEMA_VERSION,
        "candidates_input": str(candidates_path),
        "request_count": request_count,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "decision_count": len(decisions),
        "reject_reason_counts": reject_reason_counts,
        "judge_contract_version": JUDGE_CONTRACT_VERSION,
    }


def build_metadata(candidates_path: Path, requests: Sequence[Mapping[str, Any]]) -> Json:
    return {
        "schema_version": JUDGE_REPORT_SCHEMA_VERSION,
        "candidates_input": str(candidates_path),
        "request_count": len(requests),
        "execute": False,
        "judge_contract_version": JUDGE_CONTRACT_VERSION,
        "request_ids": [request.get("request_id") for request in requests],
        "payload_sha256": {str(request.get("request_id")): request.get("payload_sha256") for request in requests},
        "notes": [
            "dry-run only: no LLM/API call was made",
            "judge prompt uses generated candidate fields only, not public20 labels",
            "accepted judge results still require Gate A state-transition audit",
        ],
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dry-run Self-Instruct judge payloads and parse external judge results.")
    parser.add_argument("--candidates", required=True, type=Path, help="Normalized candidate JSON/JSONL.")
    parser.add_argument("--requests-output", required=True, type=Path, help="Output judge request payload JSONL.")
    parser.add_argument("--metadata-json", required=True, type=Path, help="Output judge request metadata JSON.")
    parser.add_argument("--judge-results", type=Path, default=None, help="Optional external judge result JSONL to parse.")
    parser.add_argument("--accepted-output", type=Path, default=None, help="Accepted candidates after judge filter.")
    parser.add_argument("--reject-output", type=Path, default=None, help="Rejected judge rows JSONL.")
    parser.add_argument("--decisions-output", type=Path, default=None, help="Normalized judge decisions JSON output.")
    parser.add_argument("--report-json", type=Path, default=None, help="Judge filter summary JSON.")
    parser.add_argument("--model", default="external-llm", help="Model name recorded in the judge payload for an external runner.")
    parser.add_argument("--created-at-kst", default=None, help="Optional fixed KST timestamp for reproducible tests.")
    parser.add_argument("--execute", action="store_true", help="Reserved for future external runner integration; not implemented here.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if args.execute:
        print("filter_self_instruct_judge: --execute is not implemented; no API call was made", file=sys.stderr)
        return 2
    try:
        raw_candidates = load_candidates(args.candidates)
        candidates = normalize_candidates(raw_candidates)
        requests = build_judge_requests(candidates, model=args.model, created_at_kst=args.created_at_kst)
        _write_jsonl(requests, args.requests_output)
        args.metadata_json.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_json.write_text(
            json.dumps(build_metadata(args.candidates, requests), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if args.judge_results is not None:
            required_outputs = [args.accepted_output, args.reject_output, args.decisions_output, args.report_json]
            if any(path is None for path in required_outputs):
                raise SelfInstructJudgeError("judge_result_outputs_required")
            accepted, rejected, decisions = apply_judge_results(candidates, _iter_jsonl(args.judge_results))
            write_jsonl(accepted, args.accepted_output)
            _write_jsonl(rejected, args.reject_output)
            _write_json(decisions, args.decisions_output)
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(
                json.dumps(
                    build_report(
                        candidates_path=args.candidates,
                        request_count=len(requests),
                        accepted=accepted,
                        rejected=rejected,
                        decisions=decisions,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
    except (OSError, json.JSONDecodeError, CandidateSchemaError, SelfInstructJudgeError) as exc:
        print(f"filter_self_instruct_judge: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
