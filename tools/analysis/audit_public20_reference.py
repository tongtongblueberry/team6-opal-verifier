# Changed: add a public20-only qualitative audit pack builder.
# Why: public20 is an input-structure reference, not a generated candidate pool with exposed training labels.
"""Build a qualitative state-transition audit pack for public20 reference rows.

This is an offline data-quality artifact generator. It is not a rule engine,
not a runtime verifier, and not a solver fallback. The tool prepares a
label-free audit pack so a human or LLM judge can inspect public20 trajectory
shape and state-transition requirements without leaking local-only labels into
generation prompts or training manifests.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.self_instruct_seed_schema import (  # noqa: E402
    SeedSchemaError,
    normalize_seed,
    profile_seed,
)


Json = Dict[str, Any]
PUBLIC20_AUDIT_SCHEMA_VERSION = "self_instruct.public20_reference_audit.v1"
KST = timezone(timedelta(hours=9), name="KST")


def _now_kst() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


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


def _status_texts(value: Any) -> Tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped.upper(),) if stripped else ()
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


def _method_name(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_value = record.get("input")
    if isinstance(input_value, Mapping):
        command = input_value.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        method = input_value.get("method")
        if isinstance(method, Mapping):
            name = method.get("name") or method.get("Name")
            return name.strip() if isinstance(name, str) else ""
        if isinstance(method, str):
            return method.strip()
    command = record.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()
    method = record.get("method")
    if isinstance(method, Mapping):
        name = method.get("name") or method.get("Name")
        return name.strip() if isinstance(name, str) else ""
    if isinstance(method, str):
        return method.strip()
    return ""


def _input_status(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_value = record.get("input")
    if isinstance(input_value, Mapping):
        statuses = _status_texts(input_value.get("status_codes"))
        if not statuses:
            statuses = _status_texts(input_value.get("status"))
        return ",".join(statuses)
    return ""


def _output_status(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    output = record.get("output")
    if isinstance(output, Mapping):
        statuses = _status_texts(output.get("status_codes"))
        if not statuses:
            statuses = _status_texts(output.get("status"))
        if not statuses:
            statuses = _status_texts(output.get("result"))
        if not statuses:
            args = output.get("args")
            if isinstance(args, Mapping):
                statuses = _status_texts(args.get("result"))
        return ",".join(statuses)
    statuses = _status_texts(record.get("status_codes"))
    if not statuses:
        statuses = _status_texts(record.get("status"))
    return ",".join(statuses)


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


def _invoking_name(record: Any) -> str:
    if not isinstance(record, Mapping):
        return ""
    input_value = record.get("input")
    if not isinstance(input_value, Mapping):
        return ""
    invoking_id = input_value.get("invoking_id")
    if isinstance(invoking_id, Mapping):
        name = invoking_id.get("name") or invoking_id.get("Name")
        return name.strip() if isinstance(name, str) else ""
    return ""


# Changed: summarize public20 rows without consulting or exposing row-level labels.
# Why: public20 audit pack is for state-transition shape inspection only.
def record_summary_rows(seed: Mapping[str, Any]) -> List[Json]:
    records = seed.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        raise SeedSchemaError("records_not_list")
    rows: List[Json] = []
    for index, record in enumerate(records):
        rows.append(
            {
                "index": index,
                "source_index": record.get("index") if isinstance(record, Mapping) else None,
                "method": _method_name(record),
                "invoking_name": _invoking_name(record),
                "input_status": _input_status(record),
                "output_status": _output_status(record),
                "return_value_count": _return_value_count(record),
            }
        )
    return rows


def public20_summary(seed: Mapping[str, Any], line_number: Optional[int] = None) -> Json:
    profile = profile_seed(seed)
    sequence = [
        {"index": index, "method": method, "status": profile["status_sequence"][index]}
        for index, method in enumerate(profile["method_sequence"])
    ]
    return {
        "line_number": line_number,
        "sample_id": seed.get("sample_id"),
        "record_count": profile["record_count"],
        "input_json_chars": profile["input_json_chars"],
        "length_bin": profile["length_bin"],
        "final_method": profile["final_method"],
        "final_status": profile["final_status"],
        "method_status_sequence": sequence,
        "record_summaries": record_summary_rows(seed),
    }


def load_public20_rows(path: Path) -> List[Json]:
    rows: List[Json] = []
    for line_number, row in _iter_jsonl(path):
        try:
            normalized = normalize_seed(row)
        except SeedSchemaError:
            normalized = dict(row)
            normalized["profile"] = profile_seed(normalized)
        normalized["line_number"] = line_number
        rows.append(normalized)
    return rows


def select_rows(rows: Sequence[Mapping[str, Any]], sample_size: Optional[int], seed: int) -> List[Json]:
    copied = [dict(row) for row in rows]
    if sample_size is None or sample_size >= len(copied):
        return copied
    if sample_size <= 0:
        return []
    rng = random.Random(seed)
    rng.shuffle(copied)
    return sorted(copied[:sample_size], key=lambda row: str(row.get("sample_id", "")))


def load_profile_report(path: Optional[Path]) -> Optional[Json]:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("profile JSON root is not an object")
    return dict(payload)


def load_local_label_aggregate(path: Optional[Path], expected_sample_ids: Sequence[str]) -> Json:
    if path is None:
        return {
            "available": False,
            "policy": "local-only labels were not provided; no row-level labels are present in the audit pack.",
        }

    counts: Json = {}
    label_sample_ids: List[str] = []
    for _, row in _iter_jsonl(path):
        sample_id = row.get("sample_id")
        if isinstance(sample_id, str):
            label_sample_ids.append(sample_id)
        label = row.get("label")
        key = label.lower().strip() if isinstance(label, str) and label.strip() else "unknown"
        counts[key] = counts.get(key, 0) + 1

    expected_set = set(expected_sample_ids)
    label_set = set(label_sample_ids)
    return {
        "available": True,
        "policy": "local-only aggregate for reference/evaluation only; never use row labels in generation prompts, judge prompts, or training manifests.",
        "label_distribution": counts,
        "row_count": len(label_sample_ids),
        "sample_id_match": expected_set == label_set,
        "missing_input_ids": sorted(expected_set - label_set),
        "extra_label_ids": sorted(label_set - expected_set),
    }


def build_report(
    *,
    normalized_jsonl: Path,
    profile_json: Optional[Path],
    labels_local_jsonl: Optional[Path],
    sample_size: Optional[int],
    seed: int,
    rows: Sequence[Mapping[str, Any]],
    selected_rows: Sequence[Mapping[str, Any]],
) -> Json:
    sample_ids = [str(row.get("sample_id")) for row in rows if isinstance(row.get("sample_id"), str)]
    profile_report = load_profile_report(profile_json)
    label_aggregate = load_local_label_aggregate(labels_local_jsonl, sample_ids)
    return {
        "schema_version": PUBLIC20_AUDIT_SCHEMA_VERSION,
        "generated_at_kst": _now_kst(),
        "normalized_jsonl": str(normalized_jsonl),
        "profile_json": str(profile_json) if profile_json is not None else None,
        "labels_local_jsonl": str(labels_local_jsonl) if labels_local_jsonl is not None else None,
        "policy": {
            "public20_role": "input-structure reference and local evaluation reference",
            "audit_pack_row_labels": "omitted",
            "generation_prompt_use": "forbidden",
            "judge_prompt_label_use": "forbidden",
            "training_manifest_use": "forbidden",
            "runtime_solver_use": "forbidden",
        },
        "sample_size_requested": sample_size if sample_size is not None else len(rows),
        "sample_size_actual": len(selected_rows),
        "seed": seed,
        "total_public20_rows": len(rows),
        "profile_summary": {
            "count": profile_report.get("count") if isinstance(profile_report, Mapping) else len(rows),
            "final_method_counts": profile_report.get("final_method_counts") if isinstance(profile_report, Mapping) else {},
            "final_status_counts": profile_report.get("final_status_counts") if isinstance(profile_report, Mapping) else {},
        },
        "labels_local_only_summary": label_aggregate,
        "audit_targets": [public20_summary(row, line_number=row.get("line_number")) for row in selected_rows],
    }


def render_report_md(report: Mapping[str, Any]) -> str:
    label_summary = report.get("labels_local_only_summary")
    profile_summary = report.get("profile_summary")
    lines = [
        "# Public20 Reference Qualitative Audit Report",
        "",
        "이 문서는 public20을 실제 입력 구조 reference로 검수하기 위한 offline 데이터 품질 산출물이다.",
        "rule engine, runtime verifier, solver fallback이 아니며 LLM-only architecture에 포함되지 않는다.",
        "",
        f"- 생성 시각(KST): {report.get('generated_at_kst')}",
        f"- normalized JSONL: `{report.get('normalized_jsonl')}`",
        f"- profile JSON: `{report.get('profile_json')}`",
        f"- 전체 public20 row 수: {report.get('total_public20_rows')}",
        f"- audit pack sample 수: {report.get('sample_size_actual')}",
        "",
        "## 사용 금지 정책",
        "",
        "- local-only label은 aggregate reference/evaluation summary에만 사용한다.",
        "- generation prompt, judge prompt, training manifest에는 public20 row-level label을 넣지 않는다.",
        "- audit pack에는 sample별 label을 노출하지 않는다.",
        "",
        "## Profile Summary",
        "",
        f"- count: `{profile_summary.get('count') if isinstance(profile_summary, Mapping) else None}`",
        f"- final_method_counts: `{json.dumps(profile_summary.get('final_method_counts', {}) if isinstance(profile_summary, Mapping) else {}, ensure_ascii=False, sort_keys=True)}`",
        f"- final_status_counts: `{json.dumps(profile_summary.get('final_status_counts', {}) if isinstance(profile_summary, Mapping) else {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Local-Only Label Aggregate",
        "",
        f"`{json.dumps(label_summary, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Audit Targets",
        "",
    ]

    targets = report.get("audit_targets")
    if isinstance(targets, Sequence) and targets:
        for target in targets:
            if not isinstance(target, Mapping):
                continue
            lines.append(
                f"- sample_id `{target.get('sample_id')}`, records `{target.get('record_count')}`, "
                f"final `{target.get('final_method')}/{target.get('final_status')}`"
            )
    else:
        lines.append("- 없음")

    return "\n".join(lines) + "\n"


def render_audit_pack_md(report: Mapping[str, Any]) -> str:
    lines = [
        "# Public20 Reference Qualitative State-Transition Audit Pack",
        "",
        "이 pack은 public20 trajectory를 실제 입력 구조 reference로 읽고 state transition을 직접 확인하기 위한 산출물이다.",
        "정답 정보는 이 파일에 포함하지 않는다.",
        "자동 판정기가 아니며 rule engine/runtime verifier/solver fallback이 아니다.",
        "",
        f"- 생성 시각(KST): {report.get('generated_at_kst')}",
        f"- normalized JSONL: `{report.get('normalized_jsonl')}`",
        f"- sample 수: {report.get('sample_size_actual')}",
        "",
    ]

    targets = report.get("audit_targets")
    if not isinstance(targets, Sequence):
        targets = []

    for order, target in enumerate(targets, start=1):
        if not isinstance(target, Mapping):
            continue
        sequence_value = target.get("method_status_sequence")
        sequence = ""
        if isinstance(sequence_value, Sequence):
            sequence = " -> ".join(
                f"{item.get('index')}:{item.get('method')}/{item.get('status')}"
                for item in sequence_value
                if isinstance(item, Mapping)
            )
        lines.extend(
            [
                f"## Sample {order}: {target.get('sample_id')}",
                "",
                f"- sample_id: `{target.get('sample_id')}`",
                f"- line_number: `{target.get('line_number')}`",
                f"- record_count: {target.get('record_count')}",
                f"- final method/status: `{target.get('final_method')}/{target.get('final_status')}`",
                f"- method/status sequence: `{sequence}`",
                "",
                "### Record Summary",
                "",
                "| index | source_index | invoking_name | method | input_status | output_status | return_value_count |",
                "|---:|---:|---|---|---|---|---:|",
            ]
        )
        summaries = target.get("record_summaries")
        if isinstance(summaries, Sequence):
            for row in summaries:
                if not isinstance(row, Mapping):
                    continue
                source_index = row.get("source_index")
                lines.append(
                    f"| {row.get('index')} | {'' if source_index is None else source_index} | "
                    f"`{row.get('invoking_name')}` | `{row.get('method')}` | "
                    f"`{row.get('input_status')}` | `{row.get('output_status')}` | "
                    f"{row.get('return_value_count')} |"
                )

        lines.extend(
            [
                "",
                "### state_trace",
                "",
                "### observed_state_summary",
                "",
                "### shape_notes",
                "",
                "### audit_decision",
                "",
                "### rationale",
                "",
            ]
        )

    return "\n".join(lines)


def write_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_artifacts(
    *,
    normalized_jsonl: Path,
    profile_json: Optional[Path],
    labels_local_jsonl: Optional[Path],
    sample_size: Optional[int],
    seed: int,
) -> Json:
    rows = load_public20_rows(normalized_jsonl)
    selected_rows = select_rows(rows, sample_size, seed)
    return build_report(
        normalized_jsonl=normalized_jsonl,
        profile_json=profile_json,
        labels_local_jsonl=labels_local_jsonl,
        sample_size=sample_size,
        seed=seed,
        rows=rows,
        selected_rows=selected_rows,
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public20 qualitative reference audit artifacts.")
    parser.add_argument("--normalized-jsonl", required=True, type=Path, help="Input-only normalized public20 JSONL.")
    parser.add_argument("--profile-json", type=Path, help="public20 profile JSON from Gate B.")
    parser.add_argument("--labels-local-jsonl", type=Path, help="Local-only labels for aggregate reporting only.")
    parser.add_argument("--sample-size", type=int, help="Optional number of public20 rows to include; default is all rows.")
    parser.add_argument("--seed", default=0, type=int, help="Random seed used only when sample-size is smaller than the row count.")
    parser.add_argument("--audit-pack-md", required=True, type=Path, help="Output label-free qualitative audit pack.")
    parser.add_argument("--audit-report-json", required=True, type=Path, help="Output public20 audit report JSON.")
    parser.add_argument("--audit-report-md", required=True, type=Path, help="Output public20 audit report markdown.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if args.sample_size is not None and args.sample_size < 0:
        print("audit_public20_reference: sample-size must be non-negative", file=sys.stderr)
        return 2

    try:
        report = build_artifacts(
            normalized_jsonl=args.normalized_jsonl,
            profile_json=args.profile_json,
            labels_local_jsonl=args.labels_local_jsonl,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        write_json(report, args.audit_report_json)
        args.audit_report_md.parent.mkdir(parents=True, exist_ok=True)
        args.audit_report_md.write_text(render_report_md(report), encoding="utf-8")
        args.audit_pack_md.parent.mkdir(parents=True, exist_ok=True)
        args.audit_pack_md.write_text(render_audit_pack_md(report), encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError, SeedSchemaError) as exc:
        print(f"audit_public20_reference: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
