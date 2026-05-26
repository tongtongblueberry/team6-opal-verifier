# Changed: add Gate A qualitative audit-pack generation for Self-Instruct candidates.
# Why: generated data must be manually or LLM-judge audited by state transition before Gate B/C or training.
"""Build Gate A qualitative audit artifacts for Self-Instruct candidates.

This is an offline data-quality tool. It is not a rule engine, not a runtime
architecture component, not a deterministic verifier, and not a solver fallback.
It must not be imported by ``src/solver.py`` or submission package inference
paths. The tool only prepares hard invariant results and an audit pack whose
state-transition verdicts are filled by a human or LLM judge.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.self_instruct_invariants import (  # noqa: E402
    InvariantResult,
    check_final_response_label_invariant,
    normalize_label,
)
from tools.datagen.self_instruct_candidate_schema import (  # noqa: E402
    CandidateSchemaError,
    normalize_candidate,
)


Json = Dict[str, Any]
GATE_A_REPORT_SCHEMA_VERSION = "self_instruct.gate_a_quality_audit.v1"
KST = timezone(timedelta(hours=9), name="KST")


def _now_kst() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def _sample_id(candidate: Mapping[str, Any], fallback: str) -> str:
    for key in ("sample_id", "candidate_id", "id"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _method_name(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_value = record.get("input")
    if not isinstance(input_value, Mapping):
        return ""
    method = input_value.get("method")
    if isinstance(method, Mapping):
        name = method.get("name") or method.get("Name")
        return name.strip() if isinstance(name, str) else ""
    if isinstance(method, str):
        return method.strip()
    return ""


def _status_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().upper()
    if isinstance(value, Mapping):
        for key in ("Name", "name", "status_codes", "status"):
            if key in value:
                return _status_text(value[key])
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        statuses = [_status_text(item) for item in value]
        statuses = [status for status in statuses if status]
        return ",".join(statuses)
    return ""


def _record_status(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    output = record.get("output")
    if not isinstance(output, Mapping):
        return ""
    status = _status_text(output.get("status_codes"))
    if not status:
        status = _status_text(output.get("status"))
    return status


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


def _records(candidate: Mapping[str, Any]) -> List[Any]:
    records = candidate.get("records")
    if isinstance(records, Sequence) and not isinstance(records, (bytes, bytearray, str)):
        return list(records)
    trajectory = candidate.get("trajectory")
    if isinstance(trajectory, Mapping):
        trajectory_records = trajectory.get("records")
        if isinstance(trajectory_records, Sequence) and not isinstance(trajectory_records, (bytes, bytearray, str)):
            return list(trajectory_records)
    return []


def _line_error(line_number: int, reason: str, details: Optional[Mapping[str, Any]] = None) -> Json:
    return {
        "line_number": line_number,
        "passed": False,
        "reason": reason,
        "details": dict(details or {}),
    }


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise ValueError(f"line {line_number}: JSON value is not an object")
            yield line_number, payload


def _invariant_row_from_result(
    *,
    line_number: int,
    sample_id: str,
    result: InvariantResult,
    schema_error: Optional[str] = None,
) -> Json:
    row = result.to_dict()
    row["line_number"] = line_number
    row["sample_id"] = sample_id
    if schema_error is not None:
        row["schema_error"] = schema_error
    return row


# Changed: run candidate schema normalization and final-response invariant precheck together.
# Why: Gate A audit packs must only sample rows whose label/evidence target the final response.
def audit_candidate_rows(rows: Iterable[Tuple[int, Mapping[str, Any]]]) -> Tuple[List[Json], List[Json]]:
    invariant_rows: List[Json] = []
    accepted_rows: List[Json] = []

    for line_number, raw_candidate in rows:
        fallback_id = f"line-{line_number}"
        raw_sample_id = _sample_id(raw_candidate, fallback_id)
        try:
            normalized = normalize_candidate(raw_candidate)
        except CandidateSchemaError as exc:
            result = check_final_response_label_invariant(raw_candidate)
            if result.passed:
                result = InvariantResult(False, f"candidate_schema:{exc}", {"sample_id": raw_sample_id})
            invariant_rows.append(
                _invariant_row_from_result(
                    line_number=line_number,
                    sample_id=raw_sample_id,
                    result=result,
                    schema_error=str(exc),
                )
            )
            continue

        result = check_final_response_label_invariant(normalized)
        normalized["line_number"] = line_number
        normalized["sample_id"] = _sample_id(normalized, fallback_id)
        invariant_rows.append(
            _invariant_row_from_result(
                line_number=line_number,
                sample_id=normalized["sample_id"],
                result=result,
            )
        )
        if result.passed:
            accepted_rows.append(normalized)

    return invariant_rows, accepted_rows


def _count_by_key(rows: Iterable[Mapping[str, Any]], key: str) -> Json:
    counts: Json = {}
    for row in rows:
        value = row.get(key)
        value_key = str(value) if value is not None else "unknown"
        counts[value_key] = counts.get(value_key, 0) + 1
    return counts


# Changed: sample after hard invariant pass, with each available label represented when possible.
# Why: Gate A must qualitatively inspect both PASS and FAIL families rather than a single majority class.
def stratified_sample(candidates: Sequence[Mapping[str, Any]], sample_size: int, seed: int) -> List[Json]:
    if sample_size <= 0 or not candidates:
        return []

    groups: Dict[str, List[Json]] = {}
    for candidate in candidates:
        label = normalize_label(candidate.get("label"))
        if label is None:
            continue
        groups.setdefault(label, []).append(dict(candidate))

    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)

    labels = sorted(label for label, group in groups.items() if group)
    selected: List[Json] = []
    target_size = min(sample_size, sum(len(groups[label]) for label in labels))

    if sample_size >= len(labels):
        for label in labels:
            if len(selected) >= target_size:
                break
            selected.append(groups[label].pop(0))

    while len(selected) < target_size:
        available_labels = [label for label in labels if groups[label]]
        if not available_labels:
            break
        label = max(available_labels, key=lambda item: (len(groups[item]), item))
        selected.append(groups[label].pop(0))

    return selected


def candidate_summary(candidate: Mapping[str, Any]) -> Json:
    records = _records(candidate)
    method_sequence = [_method_name(record) for record in records]
    status_sequence = [_record_status(record) for record in records]
    final_method = method_sequence[-1] if method_sequence else ""
    final_status = status_sequence[-1] if status_sequence else ""
    return {
        "line_number": candidate.get("line_number"),
        "sample_id": _sample_id(candidate, "unknown"),
        "label": normalize_label(candidate.get("label")),
        "record_count": len(records),
        "final_method": final_method,
        "final_status": final_status,
        "method_status_sequence": [
            {"index": index, "method": method, "status": status_sequence[index] if index < len(status_sequence) else ""}
            for index, method in enumerate(method_sequence)
        ],
    }


def _audit_targets(selected: Sequence[Mapping[str, Any]]) -> List[Json]:
    return [candidate_summary(candidate) for candidate in selected]


def build_report(
    *,
    input_path: Path,
    sample_size: int,
    seed: int,
    invariant_rows: Sequence[Mapping[str, Any]],
    accepted_rows: Sequence[Mapping[str, Any]],
    selected_rows: Sequence[Mapping[str, Any]],
) -> Json:
    failed_rows = [row for row in invariant_rows if not row.get("passed")]
    passed_rows = [row for row in invariant_rows if row.get("passed")]
    return {
        "schema_version": GATE_A_REPORT_SCHEMA_VERSION,
        "generated_at_kst": _now_kst(),
        "input": str(input_path),
        "sample_size_requested": sample_size,
        "sample_size_actual": len(selected_rows),
        "seed": seed,
        "total_candidates": len(invariant_rows),
        "hard_invariant_pass_count": len(passed_rows),
        "hard_invariant_fail_count": len(failed_rows),
        "accepted_label_distribution": _count_by_key(accepted_rows, "label"),
        "sample_label_distribution": _count_by_key(selected_rows, "label"),
        "audit_targets": _audit_targets(selected_rows),
        "invariant_failures": [
            {
                "line_number": row.get("line_number"),
                "sample_id": row.get("sample_id"),
                "reason": row.get("reason"),
                "details": row.get("details"),
                "schema_error": row.get("schema_error"),
            }
            for row in failed_rows
        ],
    }


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_report_md(report: Mapping[str, Any]) -> str:
    lines = [
        "# Gate A Self-Instruct Quality Audit Report",
        "",
        "이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.",
        "",
        f"- 생성 시각(KST): {report.get('generated_at_kst')}",
        f"- 입력 JSONL: `{report.get('input')}`",
        f"- 전체 candidate 수: {report.get('total_candidates')}",
        f"- hard invariant pass 수: {report.get('hard_invariant_pass_count')}",
        f"- hard invariant fail 수: {report.get('hard_invariant_fail_count')}",
        f"- 요청 sample 수: {report.get('sample_size_requested')}",
        f"- 실제 audit pack sample 수: {report.get('sample_size_actual')}",
        f"- seed: {report.get('seed')}",
        "",
        "## Label 분포",
        "",
        f"- Accepted pool: `{json.dumps(report.get('accepted_label_distribution', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- Audit sample: `{json.dumps(report.get('sample_label_distribution', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Hard Invariant Failures",
        "",
    ]

    failures = report.get("invariant_failures")
    if isinstance(failures, Sequence) and failures:
        for failure in failures:
            if not isinstance(failure, Mapping):
                continue
            lines.append(
                f"- line {failure.get('line_number')}, sample_id `{failure.get('sample_id')}`: `{failure.get('reason')}`"
            )
    else:
        lines.append("- 없음")

    lines.extend(["", "## Audit Pack Targets", ""])
    targets = report.get("audit_targets")
    if isinstance(targets, Sequence) and targets:
        for target in targets:
            if not isinstance(target, Mapping):
                continue
            lines.append(
                f"- line {target.get('line_number')}, sample_id `{target.get('sample_id')}`, "
                f"label `{target.get('label')}`, final `{target.get('final_method')}/{target.get('final_status')}`"
            )
    else:
        lines.append("- 없음")

    return "\n".join(lines) + "\n"


def _record_summary_rows(candidate: Mapping[str, Any]) -> List[Json]:
    rows: List[Json] = []
    for index, record in enumerate(_records(candidate)):
        rows.append(
            {
                "index": index,
                "method": _method_name(record),
                "status": _record_status(record),
                "return_value_count": _return_value_count(record),
            }
        )
    return rows


def render_audit_pack_md(report: Mapping[str, Any], selected_rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Gate A Qualitative State-Transition Audit Pack",
        "",
        "이 pack은 사람이 또는 LLM judge가 records를 처음부터 끝까지 읽고 state transition을 직접 확인하기 위한 산출물이다.",
        "자동 verdict를 확정하지 않으며, rule engine/runtime architecture/solver fallback이 아니다.",
        "",
        f"- 생성 시각(KST): {report.get('generated_at_kst')}",
        f"- 입력 JSONL: `{report.get('input')}`",
        f"- sample 수: {len(selected_rows)}",
        "",
    ]

    for order, candidate in enumerate(selected_rows, start=1):
        summary = candidate_summary(candidate)
        sequence = " -> ".join(
            f"{item['index']}:{item['method']}/{item['status']}" for item in summary["method_status_sequence"]
        )
        lines.extend(
            [
                f"## Sample {order}: {summary['sample_id']}",
                "",
                f"- sample_id: `{summary['sample_id']}`",
                f"- line_number: `{summary['line_number']}`",
                f"- label: `{summary['label']}`",
                f"- record_count: {summary['record_count']}",
                f"- final method/status: `{summary['final_method']}/{summary['final_status']}`",
                f"- method/status sequence: `{sequence}`",
                "",
                "### Record Summary",
                "",
                "| index | method | status | return_value_count |",
                "|---:|---|---|---:|",
            ]
        )
        for row in _record_summary_rows(candidate):
            lines.append(f"| {row['index']} | `{row['method']}` | `{row['status']}` | {row['return_value_count']} |")

        lines.extend(
            [
                "",
                "### state_trace",
                "",
                "### observed_state_summary",
                "",
                "### audit_decision",
                "",
                "### rationale",
                "",
            ]
        )

    return "\n".join(lines)


def build_artifacts(input_path: Path, sample_size: int, seed: int) -> Tuple[List[Json], List[Json], Json]:
    invariant_rows, accepted_rows = audit_candidate_rows(_iter_jsonl(input_path))
    selected_rows = stratified_sample(accepted_rows, sample_size=sample_size, seed=seed)
    report = build_report(
        input_path=input_path,
        sample_size=sample_size,
        seed=seed,
        invariant_rows=invariant_rows,
        accepted_rows=accepted_rows,
        selected_rows=selected_rows,
    )
    return invariant_rows, selected_rows, report


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Gate A qualitative audit artifacts for Self-Instruct candidate JSONL.")
    parser.add_argument("--accepted-jsonl", required=True, type=Path, help="Label-bearing generated candidate JSONL.")
    parser.add_argument("--sample-size", required=True, type=int, help="Total stratified sample size for the audit pack.")
    parser.add_argument("--seed", required=True, type=int, help="Random seed for deterministic stratified sampling.")
    parser.add_argument("--invariant-jsonl", required=True, type=Path, help="Output JSONL with per-candidate hard invariant results.")
    parser.add_argument("--audit-pack-md", required=True, type=Path, help="Output markdown pack for qualitative state-transition audit.")
    parser.add_argument("--audit-report-json", required=True, type=Path, help="Output JSON report for Gate A.")
    parser.add_argument("--audit-report-md", required=True, type=Path, help="Output markdown report for Gate A.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if args.sample_size < 0:
        print("audit_self_instruct_quality: sample-size must be non-negative", file=sys.stderr)
        return 2

    try:
        invariant_rows, selected_rows, report = build_artifacts(args.accepted_jsonl, args.sample_size, args.seed)
        _write_jsonl(invariant_rows, args.invariant_jsonl)
        _write_json(report, args.audit_report_json)
        args.audit_report_md.parent.mkdir(parents=True, exist_ok=True)
        args.audit_report_md.write_text(render_report_md(report), encoding="utf-8")
        args.audit_pack_md.parent.mkdir(parents=True, exist_ok=True)
        args.audit_pack_md.write_text(render_audit_pack_md(report, selected_rows), encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"audit_self_instruct_quality: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
