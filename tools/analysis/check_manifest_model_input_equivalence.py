#!/usr/bin/env python3
# Changed: add Gate C manifest/model-input equivalence checks for Self-Instruct candidates.
# Why: synthetic examples must stay full-trajectory inputs from candidate normalization through trainer loading.
"""Gate C checks for candidate, manifest, and trainer-loader input equivalence.

This is an offline data-quality gate. It does not import runtime solver code,
rule engines, model weights, tokenizers, public20 labels, or LLM/API clients.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis import build_supervised_manifest as manifest_builder  # noqa: E402
from tools.datagen.self_instruct_candidate_schema import (  # noqa: E402
    CandidateSchemaError,
    normalize_candidate,
)
from tools.training import train_manifest_lora  # noqa: E402


Json = Dict[str, Any]
SCHEMA_VERSION = "gate_c_manifest_model_input_equivalence.v1"
HASH_FIELDS = ("content_hash", "input_hash_no_label", "prompt_schema_hash")


@dataclass(frozen=True)
class GateIssue:
    severity: str
    sample_id: str
    reason: str
    detail: str

    def to_dict(self) -> Json:
        return {
            "severity": self.severity,
            "sample_id": self.sample_id,
            "reason": self.reason,
            "detail": self.detail,
        }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-jsonl", required=True, type=Path)
    parser.add_argument("--manifest-jsonl", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser.parse_args(argv)


def read_jsonl(path: Path) -> List[Json]:
    rows: List[Json] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, Mapping):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(dict(value))
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def index_by_sample_id(rows: Iterable[Mapping[str, Any]], row_type: str) -> Tuple[Dict[str, Json], List[GateIssue]]:
    indexed: Dict[str, Json] = {}
    issues: List[GateIssue] = []
    for index, row in enumerate(rows, start=1):
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            issues.append(GateIssue("fail", f"{row_type}:{index}", "sample_id_missing", "row has no non-empty sample_id"))
            continue
        sample_id_text = sample_id.strip()
        if sample_id_text in indexed:
            issues.append(GateIssue("fail", sample_id_text, f"duplicate_{row_type}_sample_id", "sample_id appears more than once"))
            continue
        indexed[sample_id_text] = dict(row)
    return indexed, issues


def normalize_candidate_rows(rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Json], List[GateIssue]]:
    normalized_rows: List[Json] = []
    issues: List[GateIssue] = []
    for index, row in enumerate(rows, start=1):
        sample_hint = row.get("sample_id") if isinstance(row.get("sample_id"), str) else f"candidate:{index}"
        try:
            normalized_rows.append(normalize_candidate(row))
        except CandidateSchemaError as exc:
            issues.append(GateIssue("fail", str(sample_hint), "candidate_schema_invalid", str(exc)))
    return normalized_rows, issues


def manifest_records_payload(input_text: str) -> Optional[Any]:
    try:
        parsed = json.loads(input_text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, Mapping) and isinstance(parsed.get("records"), list):
        return parsed.get("records")
    return None


def expected_manifest_input(candidate: Mapping[str, Any]) -> str:
    return manifest_builder.stable_json({"records": candidate["records"]})


def validate_manifest_row(candidate: Mapping[str, Any], manifest_row: Mapping[str, Any]) -> Tuple[Json, List[GateIssue]]:
    sample_id = str(candidate["sample_id"])
    row_report: Json = {
        "sample_id": sample_id,
        "split": manifest_row.get("split", "train"),
        "label": manifest_row.get("label"),
        "checks": {},
        "warnings": [],
    }
    issues: List[GateIssue] = []

    input_text = manifest_row.get("input")
    if not isinstance(input_text, str) or not input_text.strip():
        issues.append(GateIssue("fail", sample_id, "manifest_input_missing", "manifest row has no non-empty input field"))
        return row_report, issues

    candidate_label = candidate.get("label")
    manifest_label = manifest_row.get("label")
    label_match = manifest_label == candidate_label
    row_report["checks"]["label_match"] = label_match
    if not label_match:
        issues.append(
            GateIssue("fail", sample_id, "label_mismatch", f"candidate={candidate_label!r} manifest={manifest_label!r}")
        )

    expected_input = expected_manifest_input(candidate)
    parsed_records = manifest_records_payload(input_text)
    full_records_match = parsed_records == candidate.get("records")
    canonical_input_match = input_text == expected_input
    row_report["checks"]["full_records_match"] = full_records_match
    row_report["checks"]["canonical_builder_input_match"] = canonical_input_match
    row_report["input_char_count"] = len(input_text)
    row_report["candidate_record_count"] = len(candidate["records"])

    if not full_records_match:
        issues.append(
            GateIssue(
                "fail",
                sample_id,
                "full_trajectory_input_missing",
                "manifest input does not parse to top-level {'records': candidate.records}; possible step flattening",
            )
        )
    elif not canonical_input_match:
        warning = "manifest input contains full records but is not build_supervised_manifest canonical stable_json"
        row_report["warnings"].append({"reason": "non_canonical_manifest_input", "detail": warning})

    expected_hashes = {
        "content_hash": manifest_builder.content_hash(input_text, str(manifest_label)),
        "input_hash_no_label": manifest_builder.input_hash_no_label(input_text),
        "prompt_schema_hash": manifest_builder.prompt_schema_hash(),
    }
    row_report["expected_hashes"] = expected_hashes
    row_report["manifest_hashes"] = {field: manifest_row.get(field) for field in HASH_FIELDS}
    for field, expected_value in expected_hashes.items():
        actual_value = manifest_row.get(field)
        hash_match = actual_value == expected_value
        row_report["checks"][f"{field}_match"] = hash_match
        if not hash_match:
            issues.append(
                GateIssue(
                    "fail",
                    sample_id,
                    f"{field}_mismatch",
                    f"expected={expected_value} actual={actual_value!r}",
                )
            )

    prompt_schema_version = manifest_row.get("prompt_schema_version")
    if prompt_schema_version != manifest_builder.PROMPT_SCHEMA_VERSION:
        issues.append(
            GateIssue(
                "fail",
                sample_id,
                "prompt_schema_version_mismatch",
                f"expected={manifest_builder.PROMPT_SCHEMA_VERSION!r} actual={prompt_schema_version!r}",
            )
        )
    row_report["checks"]["prompt_schema_version_match"] = prompt_schema_version == manifest_builder.PROMPT_SCHEMA_VERSION

    return row_report, issues


def trainer_loader_report(manifest_path: Path, manifest_by_sample_id: Mapping[str, Mapping[str, Any]]) -> Tuple[Json, List[GateIssue]]:
    report: Json = {
        "loader": "tools.training.train_manifest_lora.load_manifest",
        "loaded": False,
        "warnings": [
            {
                "reason": "prompt_renderer_scope",
                "detail": "Gate C checks trainer build_messages only. eval/submission solver prompt renderers are not imported here.",
            },
            {
                "reason": "first_forward_not_executed",
                "detail": "No tokenizer/model is loaded in this tool; heavy first-forward smoke belongs to package/runtime gates.",
            },
        ],
    }
    issues: List[GateIssue] = []
    try:
        loader_rows, loader_summary = train_manifest_lora.load_manifest(manifest_path)
    except SystemExit as exc:
        report["loader_error"] = str(exc)
        issues.append(GateIssue("fail", "__loader__", "trainer_loader_failed", str(exc)))
        return report, issues

    report["loaded"] = True
    report["summary"] = loader_summary
    train_manifest_ids = {
        sample_id
        for sample_id, row in manifest_by_sample_id.items()
        if str(row.get("split", "train")).strip().lower() == "train"
    }
    loader_ids = {row.sample_id for row in loader_rows}
    report["train_manifest_sample_ids"] = sorted(train_manifest_ids)
    report["loader_sample_ids"] = sorted(loader_ids)
    report["row_count_match"] = len(loader_ids) == len(train_manifest_ids) == len(loader_rows)
    report["sample_id_set_match"] = loader_ids == train_manifest_ids

    missing_from_loader = sorted(train_manifest_ids - loader_ids)
    extra_from_loader = sorted(loader_ids - train_manifest_ids)
    if missing_from_loader:
        issues.append(GateIssue("fail", "__loader__", "train_rows_missing_from_loader", ",".join(missing_from_loader)))
    if extra_from_loader:
        issues.append(GateIssue("fail", "__loader__", "loader_extra_train_rows", ",".join(extra_from_loader)))

    loader_row_reports: List[Json] = []
    for loader_row in loader_rows:
        manifest_row = manifest_by_sample_id.get(loader_row.sample_id)
        if manifest_row is None:
            continue
        messages = train_manifest_lora.build_messages(loader_row)
        user_content = messages[0].get("content") if messages else None
        assistant_content = messages[-1].get("content") if messages else None
        input_match = loader_row.input_text == manifest_row.get("input") == user_content
        label_match = loader_row.label == manifest_row.get("label") == assistant_content
        loader_row_reports.append(
            {
                "sample_id": loader_row.sample_id,
                "row_index": loader_row.row_index,
                "input_text_match": input_match,
                "label_match": label_match,
                "message_roles": [message.get("role") for message in messages],
            }
        )
        if not input_match:
            issues.append(GateIssue("fail", loader_row.sample_id, "trainer_input_text_mismatch", "loader/build_messages input differs from manifest input"))
        if not label_match:
            issues.append(GateIssue("fail", loader_row.sample_id, "trainer_label_mismatch", "loader/build_messages label differs from manifest label"))

    report["rows"] = loader_row_reports
    return report, issues


def build_report(candidates_path: Path, manifest_path: Path) -> Json:
    raw_candidates = read_jsonl(candidates_path)
    manifest_rows = read_jsonl(manifest_path)
    normalized_candidates, candidate_issues = normalize_candidate_rows(raw_candidates)
    candidate_by_sample_id, candidate_index_issues = index_by_sample_id(normalized_candidates, "candidate")
    manifest_by_sample_id, manifest_index_issues = index_by_sample_id(manifest_rows, "manifest")

    issues: List[GateIssue] = []
    issues.extend(candidate_issues)
    issues.extend(candidate_index_issues)
    issues.extend(manifest_index_issues)

    candidate_ids = set(candidate_by_sample_id)
    manifest_ids = set(manifest_by_sample_id)
    for sample_id in sorted(candidate_ids - manifest_ids):
        issues.append(GateIssue("fail", sample_id, "candidate_missing_from_manifest", "candidate sample_id not found in manifest"))
    for sample_id in sorted(manifest_ids - candidate_ids):
        issues.append(GateIssue("fail", sample_id, "manifest_missing_from_candidates", "manifest sample_id not found in candidates"))

    row_reports: List[Json] = []
    for sample_id in sorted(candidate_ids & manifest_ids):
        row_report, row_issues = validate_manifest_row(candidate_by_sample_id[sample_id], manifest_by_sample_id[sample_id])
        row_reports.append(row_report)
        issues.extend(row_issues)

    loader_report, loader_issues = trainer_loader_report(manifest_path, manifest_by_sample_id)
    issues.extend(loader_issues)

    issue_counts = Counter(issue.reason for issue in issues)
    failure_count = sum(1 for issue in issues if issue.severity == "fail")
    report: Json = {
        "schema_version": SCHEMA_VERSION,
        "candidates_jsonl": str(candidates_path),
        "manifest_jsonl": str(manifest_path),
        "overall_pass": failure_count == 0,
        "candidate_count": len(raw_candidates),
        "normalized_candidate_count": len(normalized_candidates),
        "manifest_count": len(manifest_rows),
        "matched_count": len(candidate_ids & manifest_ids),
        "issues": [issue.to_dict() for issue in issues],
        "issue_counts": dict(sorted(issue_counts.items())),
        "row_reports": row_reports,
        "trainer_loader": loader_report,
        "warnings": [
            {
                "reason": "eval_solver_prompt_mismatch_possible",
                "detail": "trainer/eval manifest paths should use raw manifest input; submission solver prompt format must be audited separately without importing runtime solver here.",
            }
        ],
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Gate C Manifest/Model Input Equivalence",
        "",
        f"- candidates: `{report['candidates_jsonl']}`",
        f"- manifest: `{report['manifest_jsonl']}`",
        f"- overall_pass: `{report['overall_pass']}`",
        f"- candidate_count: `{report['candidate_count']}`",
        f"- manifest_count: `{report['manifest_count']}`",
        f"- matched_count: `{report['matched_count']}`",
        "",
        "## Issues",
    ]
    issues = report.get("issues", [])
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(f"- `{issue['severity']}` `{issue['sample_id']}` `{issue['reason']}`: {issue['detail']}")

    lines.extend(["", "## Trainer Loader", ""])
    loader = report.get("trainer_loader", {})
    lines.append(f"- loaded: `{loader.get('loaded')}`")
    summary = loader.get("summary")
    if isinstance(summary, Mapping):
        lines.append(f"- total_rows: `{summary.get('total_rows')}`")
        lines.append(f"- train_rows: `{summary.get('train_rows')}`")
        lines.append(f"- skipped_non_train_rows: `{summary.get('skipped_non_train_rows')}`")
    lines.append(f"- sample_id_set_match: `{loader.get('sample_id_set_match')}`")
    lines.append(f"- row_count_match: `{loader.get('row_count_match')}`")

    lines.extend(["", "## Warnings", ""])
    for warning in report.get("warnings", []):
        lines.append(f"- `{warning['reason']}`: {warning['detail']}")
    for warning in loader.get("warnings", []):
        lines.append(f"- `{warning['reason']}`: {warning['detail']}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    report = build_report(args.candidates_jsonl, args.manifest_jsonl)
    if args.output_json:
        write_json(args.output_json, report)
    if args.output_md:
        write_text(args.output_md, render_markdown(report))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
