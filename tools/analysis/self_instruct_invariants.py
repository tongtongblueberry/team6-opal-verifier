# Changed: add a Self-Instruct final-response invariant checker.
# Why: generated labels must be gated before training when they target the final response.
"""Data-quality gates for Self-Instruct candidate records.

This module is intentionally stdlib-only and intentionally outside runtime
inference. It is not a rule engine, not a deterministic verifier, and not a
solver fallback. Its only job is to reject malformed Self-Instruct training
candidates whose label/evidence target does not point at the last response.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# Changed: keep status compatibility deliberately narrow.
# Why: this gate checks label/target consistency without encoding protocol rules.
SUCCESS_COMPATIBLE_STATUSES = frozenset({"SUCCESS", "OK", "PASS", "PASSED"})
FAILURE_COMPATIBLE_STATUSES = frozenset({"FAIL", "FAILED", "FAILURE", "ERROR", "EXCEPTION"})


# Changed: expose a small result object for tests and JSONL audit output.
# Why: callers need stable pass/fail, reason, and machine-readable details.
@dataclass(frozen=True)
class InvariantResult:
    passed: bool
    reason: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "details": self.details,
        }


# Changed: normalize public labels without accepting unrelated values.
# Why: PASS/FAIL and pass/fail should be equivalent, but other labels are data errors.
def normalize_label(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"pass", "fail"}:
        return normalized
    return None


# Changed: extract common status representations used by local data artifacts.
# Why: the checker must remain a structural gate across candidate JSON variants.
def _status_texts(value: Any) -> Tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
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


def _normalized_statuses(output: Any) -> Tuple[str, ...]:
    if not isinstance(output, Mapping):
        return ()
    texts = _status_texts(output.get("status_codes"))
    if not texts:
        texts = _status_texts(output.get("status"))
    return tuple(text.upper() for text in texts)


def _has_success_compatible_status(output: Any) -> bool:
    return any(status in SUCCESS_COMPATIBLE_STATUSES for status in _normalized_statuses(output))


def _has_failure_compatible_status(output: Any) -> bool:
    return any(status in FAILURE_COMPATIBLE_STATUSES for status in _normalized_statuses(output))


# Changed: read method names only for audit details and EndSession-specific diagnostics.
# Why: method inspection must not become protocol validation or rule-engine behavior.
def _method_name(record: Any) -> Optional[str]:
    if not isinstance(record, Mapping):
        return None
    input_value = record.get("input")
    if not isinstance(input_value, Mapping):
        return None
    method = input_value.get("method")
    if isinstance(method, Mapping):
        name = method.get("name") or method.get("Name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    if isinstance(method, str) and method.strip():
        return method.strip()
    return None


def _record_output(record: Any) -> Any:
    if isinstance(record, Mapping):
        return record.get("output")
    return None


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


def _base_details(candidate: Mapping[str, Any], final_index: Optional[int] = None) -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    sample_id = candidate.get("sample_id") or candidate.get("id")
    if sample_id is not None:
        details["sample_id"] = sample_id
    if final_index is not None:
        details["final_response_index"] = final_index
    return details


def _failure(reason: str, details: Mapping[str, Any]) -> InvariantResult:
    return InvariantResult(False, reason, dict(details))


def _record_indices_with_failure_status(records: Sequence[Any]) -> List[int]:
    indices: List[int] = []
    for index, record in enumerate(records):
        if _has_failure_compatible_status(_record_output(record)):
            indices.append(index)
    return indices


def _candidate_evidence_steps(candidate: Mapping[str, Any]) -> Iterable[Tuple[str, Any]]:
    if "evidence_step" in candidate:
        yield "evidence_step", candidate.get("evidence_step")
    primary_evidence = candidate.get("primary_evidence")
    if isinstance(primary_evidence, Mapping) and "evidence_step" in primary_evidence:
        yield "primary_evidence.evidence_step", primary_evidence.get("evidence_step")


# Changed: implement the public invariant API expected by regression tests.
# Why: accepted Self-Instruct rows must label the last response, not an intermediate event.
def check_final_response_label_invariant(candidate: Mapping[str, Any]) -> InvariantResult:
    if not isinstance(candidate, Mapping):
        return _failure("candidate_not_mapping", {"actual_type": type(candidate).__name__})

    records = candidate.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        return _failure("records_not_list", _base_details(candidate))
    if len(records) == 0:
        return _failure("records_empty", _base_details(candidate))

    final_index = len(records) - 1
    last_record = records[final_index]
    last_output = _record_output(last_record)
    final_method = _method_name(last_record)
    final_statuses = _normalized_statuses(last_output)
    details = _base_details(candidate, final_index)
    details.update(
        {
            "record_count": len(records),
            "final_method": final_method,
            "final_statuses": list(final_statuses),
        }
    )
    # Changed: make final method/status presence a hard structural gate.
    # Why: downstream label checks are meaningless if the last response cannot be identified.
    if final_method is None:
        return _failure("final_method_missing", details)
    if not final_statuses:
        return _failure("final_status_missing", details)

    target = candidate.get("target")
    if not isinstance(target, Mapping):
        return _failure("target_missing", details)

    target_index = _as_index(target.get("final_response_index"))
    if target_index != final_index:
        target_details = dict(details)
        target_details["expected_final_response_index"] = final_index
        target_details["actual_final_response_index"] = target_index
        return _failure("target_index_not_last_record", target_details)

    if target.get("final_response") != last_output:
        target_details = dict(details)
        target_details["target_final_response_matches_last_output"] = False
        return _failure("target_response_not_last_record_output", target_details)

    target_method = target.get("final_method")
    if target_method is not None and str(target_method).strip() != str(final_method or "").strip():
        method_details = dict(details)
        method_details["expected_final_method"] = final_method
        method_details["actual_final_method"] = target_method
        return _failure("target_method_not_last_record", method_details)

    label = normalize_label(candidate.get("label"))
    if label is None:
        label_details = dict(details)
        label_details["actual_label"] = candidate.get("label")
        return _failure("invalid_label", label_details)
    details["label"] = label

    label_target = candidate.get("label_target")
    if not isinstance(label_target, str) or label_target.strip().lower() != "final_response":
        label_target_details = dict(details)
        label_target_details["actual_label_target"] = label_target
        return _failure("label_target_not_final_response", label_target_details)

    primary_evidence = candidate.get("primary_evidence")
    if not isinstance(primary_evidence, Mapping):
        return _failure("primary_evidence_missing", details)

    primary_evidence_index = _as_index(primary_evidence.get("record_index"))
    if primary_evidence_index is None:
        evidence_details = dict(details)
        evidence_details["primary_evidence_index"] = primary_evidence.get("record_index")
        return _failure("primary_evidence_index_missing", evidence_details)

    if primary_evidence_index != final_index:
        evidence_details = dict(details)
        evidence_details["primary_evidence_index"] = primary_evidence_index
        return _failure("primary_evidence_not_final_response", evidence_details)

    for evidence_step_name, evidence_step_value in _candidate_evidence_steps(candidate):
        evidence_step_index = _as_index(evidence_step_value)
        if evidence_step_index != final_index:
            evidence_step_details = dict(details)
            evidence_step_details["evidence_step_field"] = evidence_step_name
            evidence_step_details["expected_evidence_step"] = final_index
            evidence_step_details["actual_evidence_step"] = evidence_step_value
            return _failure("evidence_step_not_final_response", evidence_step_details)

    failure_status_indices = _record_indices_with_failure_status(records)
    if label == "pass" and failure_status_indices:
        pass_details = dict(details)
        pass_details["failure_compatible_record_indices"] = failure_status_indices
        return _failure("pass_label_contains_failure_compatible_status", pass_details)

    if label == "fail" and _has_success_compatible_status(last_output):
        fail_details = dict(details)
        fail_details["success_compatible_final_status"] = True
        fail_details["failure_compatible_record_indices"] = failure_status_indices
        if final_method and final_method.strip().lower() == "endsession" and any(index < final_index for index in failure_status_indices):
            return _failure("intermediate_failure_before_final_endsession_success", fail_details)
        return _failure("fail_label_final_response_success_compatible", fail_details)

    return InvariantResult(True, "ok", details)


# Changed: provide optional JSONL auditing without adding non-stdlib dependencies.
# Why: data workers can gate candidate files before manifest construction.
def audit_jsonl_records(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    audited: List[Dict[str, Any]] = []
    for line_number, record in enumerate(records, start=1):
        result = check_final_response_label_invariant(record)
        item = result.to_dict()
        item["line_number"] = line_number
        sample_id = record.get("sample_id") or record.get("id")
        if sample_id is not None:
            item["sample_id"] = sample_id
        audited.append(item)
    return audited


def _iter_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise ValueError(f"line {line_number}: JSON value is not an object")
            yield payload


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Self-Instruct final-response invariants for JSONL candidates.")
    parser.add_argument("input_jsonl", type=Path, help="Path to a JSONL file containing Self-Instruct candidates.")
    parser.add_argument("--output-jsonl", type=Path, default=None, help="Optional path for per-record audit JSONL output.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        audit_rows = audit_jsonl_records(_iter_jsonl(args.input_jsonl))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"self_instruct_invariants: {exc}", file=sys.stderr)
        return 2

    failed_count = sum(1 for row in audit_rows if not row["passed"])
    output_handle = None
    try:
        if args.output_jsonl is not None:
            args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
            output_handle = args.output_jsonl.open("w", encoding="utf-8")
        for row in audit_rows:
            line = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if output_handle is None:
                print(line)
            else:
                output_handle.write(line + "\n")
    finally:
        if output_handle is not None:
            output_handle.close()

    summary = {
        "input_jsonl": str(args.input_jsonl),
        "total_records": len(audit_rows),
        "failed_records": failed_count,
        "passed_records": len(audit_rows) - failed_count,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
