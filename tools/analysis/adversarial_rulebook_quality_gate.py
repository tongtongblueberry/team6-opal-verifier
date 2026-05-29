# Changed: add a rule-book-grounded adversarial qualitative gate for generated candidates.
# Why: incremental gen3 exports must be filtered by docs/legacy_spec_rules.md evidence, not only structural parser/dedup checks.
"""Adversarial qualitative gate for Self-Instruct Opal candidates.

This tool is offline data-quality tooling. It is not a runtime solver and must
not be imported by inference code. It rejects candidates unless the final
command-response pair, cited rule-book source span, and scheduled generation
target are mutually consistent.
"""

from __future__ import annotations

import argparse
import collections
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
    normalize_candidate,
    write_jsonl,
)


Json = Dict[str, Any]
REPORT_SCHEMA_VERSION = "self_instruct.adversarial_rulebook_quality_gate.v1"
DEFAULT_RULEBOOK_PATH = ROOT / "docs" / "legacy_spec_rules.md"
STATUS_TOKENS = (
    "SUCCESS",
    "NOT_AUTHORIZED",
    "INVALID_PARAMETER",
    "FAIL",
    "SP_BUSY",
    "SP_FROZEN",
    "NO_SESSIONS_AVAILABLE",
    "AUTHORITY_LOCKED_OUT",
)
FORBIDDEN_ID_PATTERNS = (
    "H0001",
    "H0002",
    "H0003",
    "H-test",
    "SP001",
    "Session1",
)


class AdversarialRulebookGateError(ValueError):
    """Raised when the adversarial gate cannot load or write its artifacts."""


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise AdversarialRulebookGateError(f"line_{line_number}_not_object")
            yield line_number, payload


def _write_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _status_values(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value.strip().upper()] if value.strip() else []
    if isinstance(value, Mapping):
        for key in ("status_codes", "status", "name", "Name", "result"):
            if key in value:
                return _status_values(value[key])
        return []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        values: List[str] = []
        for item in value:
            values.extend(_status_values(item))
        return values
    return []


def _record_method(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_payload = record.get("input")
    if not isinstance(input_payload, Mapping):
        return ""
    method = input_payload.get("method")
    if isinstance(method, Mapping):
        return str(method.get("name") or "").strip()
    if isinstance(method, str):
        return method.strip()
    command = input_payload.get("command")
    return command.strip() if isinstance(command, str) else ""


def _final_statuses(candidate: Mapping[str, Any]) -> List[str]:
    records = candidate.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)) or not records:
        return []
    final_record = records[-1]
    output = final_record.get("output") if isinstance(final_record, Mapping) else None
    if not isinstance(output, Mapping):
        return []
    statuses = _status_values(output.get("status_codes"))
    if not statuses:
        statuses = _status_values(output.get("status"))
    return statuses


def _final_method(candidate: Mapping[str, Any]) -> str:
    records = candidate.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)) or not records:
        return ""
    return _record_method(records[-1])


def _records_text(candidate: Mapping[str, Any]) -> str:
    return json.dumps(candidate.get("records", []), ensure_ascii=False, sort_keys=True)


def _has_authenticated_start_session(candidate: Mapping[str, Any]) -> bool:
    records = candidate.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        return False
    for record in records:
        if _record_method(record) != "StartSession" or not isinstance(record, Mapping):
            continue
        text = json.dumps(record.get("input"), ensure_ascii=False, sort_keys=True)
        if "HostChallenge" in text or "HostSigningAuthority" in text:
            return True
    return False


def _load_generation_targets(path: Optional[Path]) -> Dict[str, Json]:
    if path is None or not path.is_file():
        return {}
    targets: Dict[str, Json] = {}
    for _line_number, row in _iter_jsonl(path):
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            continue
        candidate_targets = row.get("candidate_targets")
        if isinstance(candidate_targets, Sequence) and not isinstance(candidate_targets, (bytes, bytearray, str)) and candidate_targets:
            first = candidate_targets[0]
            if isinstance(first, Mapping):
                targets[request_id] = dict(first)
    return targets


def _request_id(candidate: Mapping[str, Any]) -> Optional[str]:
    provenance = candidate.get("generation_provenance")
    if isinstance(provenance, Mapping) and isinstance(provenance.get("raw_output_request_id"), str):
        return provenance["raw_output_request_id"]
    sample_id = candidate.get("sample_id")
    if isinstance(sample_id, str):
        match = re.match(r"(self-instruct-gen-\d+)-cand-\d+", sample_id)
        if match:
            return match.group(1)
    return None


def _source_span_lines(span: str, rulebook_lines: Sequence[str]) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    match = re.fullmatch(r"docs/legacy_spec_rules\.md:(\d+)-(\d+)", span.strip())
    if match is None:
        return None, None, None, "source_span_not_docs_legacy_line_range"
    start_line = int(match.group(1))
    end_line = int(match.group(2))
    if start_line < 1 or end_line < start_line or end_line > len(rulebook_lines):
        return None, start_line, end_line, "source_span_out_of_range"
    text = "\n".join(f"{line_no}: {rulebook_lines[line_no - 1]}" for line_no in range(start_line, end_line + 1))
    return text, start_line, end_line, None


def _expected_status_tokens(*texts: str) -> List[str]:
    found: List[str] = []
    for text in texts:
        upper = text.upper()
        for token in STATUS_TOKENS:
            if token in upper and token not in found:
                found.append(token)
    return found


def _status_matches_expected(final_statuses: Sequence[str], expected_tokens: Sequence[str]) -> bool:
    final_set = {status.upper() for status in final_statuses}
    for expected in expected_tokens:
        if expected in final_set:
            return True
    return False


def _domain_present(candidate: Mapping[str, Any], domain: str) -> bool:
    text = _records_text(candidate).lower()
    needle = domain.lower()
    # Changed: accept both explicit names and common table/key prefixes.
    # Why: generated records may carry K_AES_256_Range1_Key or Locking_Range1 rather than only bare domain names.
    if needle in text:
        return True
    aliases = {
        "Locking": ("locking_range", "range1", "globalrange", "readlocked", "writelocked"),
        "MBRControl": ("mbrcontrol", "mbr", "doneonreset"),
        "LockingInfo": ("lockinginfo", "locking info"),
        "Authority": ("authority", "hostsigningauthority", "admins", "sid", "user1"),
        "K_AES_256": ("k_aes_256", "genkey", "range1_key"),
        "C_PIN": ("c_pin", "hostchallenge", "pin"),
        "SP": ("sp", "lockingsp", "adminsp", "spsessionid"),
    }
    return any(alias.lower() in text for alias in aliases.get(domain, ()))


def _rulebook_decision(
    candidate: Mapping[str, Any],
    *,
    line_number: int,
    rulebook_lines: Sequence[str],
    generation_targets: Mapping[str, Mapping[str, Any]],
) -> Json:
    reasons: List[str] = []
    evidence: Json = {"line_number": line_number}
    try:
        normalized = normalize_candidate(candidate)
    except CandidateSchemaError as exc:
        return {
            "line_number": line_number,
            "sample_id": candidate.get("sample_id"),
            "decision": "reject",
            "reasons": [f"candidate_schema:{exc}"],
            "evidence": evidence,
        }

    sample_id = normalized["sample_id"]
    final_statuses = _final_statuses(normalized)
    final_method = _final_method(normalized)
    label = str(normalized.get("label"))
    evidence.update({"sample_id": sample_id, "label": label, "final_method": final_method, "final_statuses": final_statuses})

    if normalized.get("instruction") != (
        "Given the full Opal command-response trajectory, judge only whether the final command-response pair (cN, rN) is valid under the cited rule-book."
    ):
        reasons.append("instruction_not_gen3_final_pair_contract")

    records = normalized.get("records") if isinstance(normalized.get("records"), list) else []
    record_text = _records_text(normalized)
    for forbidden in FORBIDDEN_ID_PATTERNS:
        if forbidden in record_text:
            reasons.append(f"forbidden_placeholder_id:{forbidden}")
    if record_text.count("000065ab") > 1:
        reasons.append("repeated_placeholder_spsessionid:000065ab")

    request_id = _request_id(normalized)
    target = generation_targets.get(request_id or "")
    evidence["request_id"] = request_id
    if target:
        evidence["generation_target"] = dict(target)
        if target.get("target_label") != label:
            reasons.append(f"target_label_mismatch:{target.get('target_label')}!={label}")
        if isinstance(target.get("target_final_method"), str) and target["target_final_method"] != final_method:
            reasons.append(f"target_final_method_mismatch:{target.get('target_final_method')}!={final_method}")
        target_status = str(target.get("target_final_status") or "").upper()
        if target_status and target_status not in set(final_statuses):
            reasons.append(f"target_final_status_mismatch:{target_status}!={','.join(final_statuses)}")
        target_count = target.get("target_record_count")
        if isinstance(target_count, int) and target_count != len(records):
            reasons.append(f"target_record_count_mismatch:{target_count}!={len(records)}")
        if target.get("requires_auth_session") is True and not _has_authenticated_start_session(normalized):
            reasons.append("required_auth_session_missing_hostchallenge_or_authority")
        required_domains = target.get("required_context_domains")
        if isinstance(required_domains, Sequence) and not isinstance(required_domains, (bytes, bytearray, str)):
            missing_domains = [str(domain) for domain in required_domains if not _domain_present(normalized, str(domain))]
            if missing_domains:
                reasons.append(f"required_context_domains_missing:{','.join(missing_domains)}")

    resolved_groundings: List[Json] = []
    expected_tokens: List[str] = []
    for grounding in normalized.get("spec_grounding", []):
        if not isinstance(grounding, Mapping):
            continue
        rule_ref = str(grounding.get("rule_ref") or "")
        source_span = str(grounding.get("source_span") or "")
        source_text, start_line, end_line, error = _source_span_lines(source_span, rulebook_lines)
        resolved: Json = {
            "rule_ref": rule_ref,
            "source_span": source_span,
            "source_start_line": start_line,
            "source_end_line": end_line,
            "resolved": error is None,
        }
        if error is not None:
            resolved["resolution_error"] = error
            reasons.append(f"{rule_ref or 'unknown_rule'}:{error}")
        else:
            resolved["source_text"] = source_text
            if rule_ref and rule_ref not in source_text:
                reasons.append(f"{rule_ref}:source_span_does_not_contain_rule_header")
            tokens = _expected_status_tokens(str(grounding.get("expected_status") or ""), source_text or "")
            expected_tokens.extend(token for token in tokens if token not in expected_tokens)
        resolved_groundings.append(resolved)

    if not resolved_groundings:
        reasons.append("spec_grounding_not_resolved")
    evidence["resolved_spec_source_spans"] = resolved_groundings
    evidence["expected_status_tokens"] = expected_tokens

    status_supported = _status_matches_expected(final_statuses, expected_tokens) if expected_tokens else False
    evidence["final_status_matches_rulebook_expected_status"] = status_supported
    if expected_tokens:
        if label == "pass" and not status_supported:
            reasons.append(f"pass_final_status_not_supported_by_rulebook:{','.join(final_statuses)} not in {','.join(expected_tokens)}")
        if label == "fail" and status_supported:
            rationale_text = json.dumps(
                {
                    "primary_evidence": normalized.get("primary_evidence"),
                    "spec_grounding": normalized.get("spec_grounding"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ).lower()
            contradiction_markers = ("contradict", "violate", "missing", "omitted", "not ", "without", "unauthorized", "out of bounds")
            if not any(marker in rationale_text for marker in contradiction_markers):
                reasons.append("fail_final_status_matches_rulebook_without_specific_violation")

    decision = "accept" if not reasons else "reject"
    return {
        "line_number": line_number,
        "sample_id": sample_id,
        "decision": decision,
        "reasons": reasons,
        "evidence": evidence,
    }


def run_gate(
    *,
    candidates_path: Path,
    accepted_output: Path,
    rejected_output: Path,
    decisions_output: Path,
    report_json: Path,
    rulebook_path: Path,
    generation_requests_jsonl: Optional[Path],
) -> Json:
    rulebook_lines = rulebook_path.read_text(encoding="utf-8").splitlines()
    generation_targets = _load_generation_targets(generation_requests_jsonl)
    accepted: List[Json] = []
    rejected: List[Json] = []
    decisions: List[Json] = []

    for line_number, row in _iter_jsonl(candidates_path):
        decision = _rulebook_decision(
            row,
            line_number=line_number,
            rulebook_lines=rulebook_lines,
            generation_targets=generation_targets,
        )
        decisions.append(decision)
        if decision["decision"] == "accept":
            accepted.append(normalize_candidate(row))
        else:
            rejected.append({"candidate": row, "decision": decision})

    write_jsonl(accepted, accepted_output)
    _write_jsonl(rejected, rejected_output)
    _write_jsonl(decisions, decisions_output)
    reason_counts = collections.Counter(reason for row in decisions for reason in row.get("reasons", []))
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "candidates_input": str(candidates_path),
        "rulebook_path": str(rulebook_path),
        "generation_requests_jsonl": str(generation_requests_jsonl) if generation_requests_jsonl is not None else None,
        "candidate_count": len(decisions),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "reject_reason_counts": dict(sorted(reason_counts.items())),
        "accepted_output": str(accepted_output),
        "rejected_output": str(rejected_output),
        "decisions_output": str(decisions_output),
        "training_use": "accepted_rows_only_pending_gate_b_c",
    }
    _write_json(report, report_json)
    return report


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run adversarial docs/legacy_spec_rules.md qualitative gate.")
    parser.add_argument("--candidates", required=True, type=Path, help="Deduplicated normalized candidate JSONL.")
    parser.add_argument("--accepted-output", required=True, type=Path, help="Candidates accepted by the adversarial rule-book gate.")
    parser.add_argument("--rejected-output", required=True, type=Path, help="Rejected candidates plus decision evidence JSONL.")
    parser.add_argument("--decisions-output", required=True, type=Path, help="Per-candidate adversarial decision JSONL.")
    parser.add_argument("--report-json", required=True, type=Path, help="Summary report JSON.")
    parser.add_argument("--rulebook-md", type=Path, default=DEFAULT_RULEBOOK_PATH, help="Rule-book markdown source.")
    parser.add_argument("--generation-requests-jsonl", type=Path, default=None, help="Optional generation request JSONL with target schedule metadata.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        run_gate(
            candidates_path=args.candidates,
            accepted_output=args.accepted_output,
            rejected_output=args.rejected_output,
            decisions_output=args.decisions_output,
            report_json=args.report_json,
            rulebook_path=args.rulebook_md,
            generation_requests_jsonl=args.generation_requests_jsonl,
        )
    except (OSError, json.JSONDecodeError, CandidateSchemaError, AdversarialRulebookGateError) as exc:
        print(f"adversarial_rulebook_quality_gate: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
