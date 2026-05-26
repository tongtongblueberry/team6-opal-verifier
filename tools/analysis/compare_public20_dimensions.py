# Changed: add Gate B profile comparison for public20 and generated candidates.
# Why: generated Self-Instruct data must be compared against public20 dimensions before manifest/model-path gates.
"""Compare public20 and generated candidate profile reports for Gate B.

This is an offline data-quality report tool. It does not import runtime,
solver, rule-engine, or submission code.

Public20 labels are accepted only as an optional aggregate JSON file for local
Gate B distribution comparison. Row-level public labels must not be supplied to
generation prompts, judge prompts, supervised manifests, or model training.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


Json = Dict[str, Any]
REPORT_SCHEMA_VERSION = "self_instruct.gate_b_dimension_comparison.v1"
NUMERIC_PROFILE_FIELDS = (
    "record_count",
    "method_sequence_length",
    "input_json_chars",
    "total_return_value_count",
    "final_return_value_count",
)
PROFILE_WARNING_FIELDS = ("schema_warnings", "raw_format_profile_warnings", "warnings")
UNKNOWN_TEXTS = {"", "UNKNOWN", "UNK", "N/A", "NA", "NONE", "NULL"}


class DimensionComparisonError(ValueError):
    """Raised when a Gate B comparison input is malformed."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DimensionComparisonError(f"{path}: invalid_json:{exc.msg}") from exc
    except OSError as exc:
        raise DimensionComparisonError(f"{path}: {exc}") from exc


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DimensionComparisonError(f"{field_name}_not_object")
    return value


def _profiles(report: Mapping[str, Any], field_name: str) -> List[Mapping[str, Any]]:
    raw_profiles = report.get("profiles")
    if not isinstance(raw_profiles, Sequence) or isinstance(raw_profiles, (bytes, bytearray, str)):
        raise DimensionComparisonError(f"{field_name}.profiles_not_list")
    profiles: List[Mapping[str, Any]] = []
    for index, profile in enumerate(raw_profiles):
        if not isinstance(profile, Mapping):
            raise DimensionComparisonError(f"{field_name}.profiles[{index}]_not_object")
        profiles.append(profile)
    return profiles


def _numeric_values(profiles: Sequence[Mapping[str, Any]], field: str) -> List[float]:
    values: List[float] = []
    for profile in profiles:
        value = profile.get(field)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _stats(values: Sequence[float]) -> Json:
    if not values:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": min(values),
        "mean": mean(values),
        "max": max(values),
    }


def _as_counter_dict(values: Iterable[Any]) -> Json:
    counter: Counter[str] = Counter()
    for value in values:
        if value is None:
            key = ""
        else:
            key = str(value)
        counter[key] += 1
    return {key: counter[key] for key in sorted(counter)}


def _sequence_values(profile: Mapping[str, Any], field: str, fallback_field: str) -> List[Any]:
    value = profile.get(field)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return list(value)
    return [profile.get(fallback_field)]


def _is_unknown_text(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    return value.strip().upper() in UNKNOWN_TEXTS


def _is_blank_text(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _length_bin(profile: Mapping[str, Any]) -> str:
    value = profile.get("length_bin")
    if isinstance(value, str) and value.strip():
        return value.strip()
    record_count = profile.get("record_count")
    if not isinstance(record_count, int):
        return "unknown"
    if record_count <= 32:
        return "1-32"
    if record_count <= 64:
        return "33-64"
    if record_count <= 128:
        return "65-128"
    if record_count <= 256:
        return "129-256"
    return "257-512"


def _collect_profile_warnings(report: Mapping[str, Any]) -> List[Any]:
    warnings: List[Any] = []
    for field in PROFILE_WARNING_FIELDS:
        value = report.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            warnings.extend(list(value))
        elif value:
            warnings.append(value)
    return warnings


def _label_counts_from_report(report: Mapping[str, Any], profiles: Sequence[Mapping[str, Any]]) -> Optional[Json]:
    label_counts = report.get("label_counts")
    if isinstance(label_counts, Mapping):
        return {str(key).lower(): int(value) for key, value in sorted(label_counts.items()) if isinstance(value, int)}

    counter: Counter[str] = Counter()
    for profile in profiles:
        label = profile.get("label")
        if isinstance(label, str) and label.strip():
            counter[label.strip().lower()] += 1
    if not counter:
        return None
    return {key: counter[key] for key in sorted(counter)}


def _normalize_public_label_distribution(data: Mapping[str, Any]) -> Json:
    for key in ("label_distribution_local_eval_only", "label_counts", "label_distribution"):
        value = data.get(key)
        if isinstance(value, Mapping):
            return {str(label).lower(): int(count) for label, count in sorted(value.items()) if isinstance(count, int)}
    if all(isinstance(data.get(label), int) for label in ("pass", "fail")):
        return {label: int(data[label]) for label in ("fail", "pass")}
    raise DimensionComparisonError("public_label_distribution_not_aggregate")


def _profile_summary(report: Mapping[str, Any], name: str) -> Json:
    profiles = _profiles(report, name)
    final_methods = [profile.get("final_method") for profile in profiles]
    final_statuses = [profile.get("final_status") for profile in profiles]

    unknown_method_count = 0
    unknown_status_count = 0
    for profile in profiles:
        unknown_method_count += sum(
            1 for item in _sequence_values(profile, "method_sequence", "final_method") if _is_unknown_text(item)
        )
        unknown_status_count += sum(
            1 for item in _sequence_values(profile, "status_sequence", "final_status") if _is_unknown_text(item)
        )

    numeric_stats = {field: _stats(_numeric_values(profiles, field)) for field in NUMERIC_PROFILE_FIELDS}
    label_counts = _label_counts_from_report(report, profiles)
    summary: Json = {
        "input": report.get("input"),
        "schema_version": report.get("schema_version"),
        "count": len(profiles),
        "declared_count": report.get("count"),
        "numeric_stats": numeric_stats,
        "record_count_bins": _as_counter_dict(_length_bin(profile) for profile in profiles),
        "final_method_counts": _as_counter_dict(final_methods),
        "final_status_counts": _as_counter_dict(final_statuses),
        "final_status_blank_count": sum(1 for value in final_statuses if _is_blank_text(value)),
        "final_method_blank_count": sum(1 for value in final_methods if _is_blank_text(value)),
        "unknown_method_count": unknown_method_count,
        "unknown_status_count": unknown_status_count,
        "schema_warnings": _collect_profile_warnings(report),
    }
    if label_counts is not None:
        summary["label_counts"] = label_counts
    return summary


def _mean(summary: Mapping[str, Any], field: str) -> Optional[float]:
    numeric_stats = summary.get("numeric_stats")
    if not isinstance(numeric_stats, Mapping):
        return None
    field_stats = numeric_stats.get(field)
    if not isinstance(field_stats, Mapping):
        return None
    value = field_stats.get("mean")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _add_no_go(no_go_warnings: List[Json], code: str, message: str, details: Mapping[str, Any]) -> None:
    no_go_warnings.append(
        {
            "severity": "no_go_warning",
            "code": code,
            "message": message,
            "details": dict(details),
        }
    )


def _build_comparisons(public: Mapping[str, Any], generated: Mapping[str, Any]) -> Json:
    comparisons: Json = {
        "row_count_difference": {
            "public": public["count"],
            "generated": generated["count"],
            "generated_minus_public": generated["count"] - public["count"],
        }
    }
    for field in NUMERIC_PROFILE_FIELDS:
        public_mean = _mean(public, field)
        generated_mean = _mean(generated, field)
        comparisons[f"{field}_mean_difference"] = {
            "public_mean": public_mean,
            "generated_mean": generated_mean,
            "generated_minus_public": None
            if public_mean is None or generated_mean is None
            else generated_mean - public_mean,
            "absolute_difference": None
            if public_mean is None or generated_mean is None
            else abs(generated_mean - public_mean),
        }
    return comparisons


def compare_profiles(
    public_profile: Mapping[str, Any],
    generated_profile: Mapping[str, Any],
    *,
    public_label_distribution: Optional[Mapping[str, Any]] = None,
    public_profile_path: Optional[Path] = None,
    generated_profile_path: Optional[Path] = None,
) -> Json:
    public = _profile_summary(public_profile, "public_profile")
    generated = _profile_summary(generated_profile, "generated_profile")
    comparisons = _build_comparisons(public, generated)
    no_go_warnings: List[Json] = []

    record_diff = comparisons["record_count_mean_difference"]["generated_minus_public"]
    if isinstance(record_diff, (int, float)) and abs(record_diff) > 0:
        _add_no_go(
            no_go_warnings,
            "record_count_mean_difference",
            "public20와 generated의 평균 record_count가 다르므로 Gate B에서 질적 검토가 필요하다.",
            comparisons["record_count_mean_difference"],
        )

    for side_name, summary in (("public", public), ("generated", generated)):
        if summary["final_status_blank_count"]:
            _add_no_go(
                no_go_warnings,
                f"{side_name}_final_status_blank_count",
                f"{side_name} profile에 비어 있는 final_status가 있다.",
                {"count": summary["final_status_blank_count"]},
            )
        if summary["unknown_method_count"] or summary["unknown_status_count"]:
            _add_no_go(
                no_go_warnings,
                f"{side_name}_unknown_method_or_status_count",
                f"{side_name} profile에 unknown method/status가 있다.",
                {
                    "unknown_method_count": summary["unknown_method_count"],
                    "unknown_status_count": summary["unknown_status_count"],
                },
            )
        if summary["schema_warnings"]:
            _add_no_go(
                no_go_warnings,
                f"{side_name}_schema_warnings_present",
                f"{side_name} profile에 schema warning이 있다.",
                {"count": len(summary["schema_warnings"])},
            )

    if generated["count"] == 0:
        _add_no_go(no_go_warnings, "generated_row_count_zero", "generated profile row가 0개다.", {"count": 0})

    label_distribution: Json = {
        "generated": generated.get("label_counts"),
        "public_local_eval_only": None,
        "note": "public20 labels are local aggregate only and must not enter generation, judge, manifest, or training inputs.",
    }
    if public_label_distribution is not None:
        label_distribution["public_local_eval_only"] = _normalize_public_label_distribution(public_label_distribution)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "public_profile_path": str(public_profile_path) if public_profile_path is not None else None,
        "generated_profile_path": str(generated_profile_path) if generated_profile_path is not None else None,
        "public": public,
        "generated": generated,
        "comparisons": comparisons,
        "label_distribution": label_distribution,
        "no_go_warnings": no_go_warnings,
    }


def _format_number(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _counts_text(counts: Mapping[str, Any]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def render_markdown(report: Mapping[str, Any]) -> str:
    public = _mapping(report.get("public"), "public")
    generated = _mapping(report.get("generated"), "generated")
    comparisons = _mapping(report.get("comparisons"), "comparisons")
    label_distribution = _mapping(report.get("label_distribution"), "label_distribution")
    warnings = report.get("no_go_warnings")
    warning_rows = warnings if isinstance(warnings, list) else []

    lines = [
        "# Gate B Dimension Comparison",
        "",
        "- public profile: `" + str(report.get("public_profile_path")) + "`",
        "- generated profile: `" + str(report.get("generated_profile_path")) + "`",
        "- public20 label aggregate: local eval/distribution only; generation, judge, manifest, training input 사용 금지",
        "",
        "## Row Count",
        "",
        "| side | rows | declared_count |",
        "|---|---:|---:|",
        f"| public20 | {public.get('count')} | {public.get('declared_count')} |",
        f"| generated | {generated.get('count')} | {generated.get('declared_count')} |",
        "",
        "## Numeric Stats",
        "",
        "| metric | public min/mean/max | generated min/mean/max | generated-public mean diff |",
        "|---|---|---|---:|",
    ]

    public_stats = _mapping(public.get("numeric_stats"), "public.numeric_stats")
    generated_stats = _mapping(generated.get("numeric_stats"), "generated.numeric_stats")
    for field in NUMERIC_PROFILE_FIELDS:
        p_stat = _mapping(public_stats.get(field), f"public.{field}")
        g_stat = _mapping(generated_stats.get(field), f"generated.{field}")
        diff = _mapping(comparisons.get(f"{field}_mean_difference"), f"{field}_mean_difference")
        p_text = "/".join(_format_number(p_stat.get(key)) for key in ("min", "mean", "max"))
        g_text = "/".join(_format_number(g_stat.get(key)) for key in ("min", "mean", "max"))
        lines.append(f"| {field} | {p_text} | {g_text} | {_format_number(diff.get('generated_minus_public'))} |")

    lines.extend(
        [
            "",
            "## Distribution Counts",
            "",
            "- public record_count bins: " + _counts_text(_mapping(public.get("record_count_bins"), "public.record_count_bins")),
            "- generated record_count bins: "
            + _counts_text(_mapping(generated.get("record_count_bins"), "generated.record_count_bins")),
            "- public final_method: " + _counts_text(_mapping(public.get("final_method_counts"), "public.final_method_counts")),
            "- generated final_method: "
            + _counts_text(_mapping(generated.get("final_method_counts"), "generated.final_method_counts")),
            "- public final_status: " + _counts_text(_mapping(public.get("final_status_counts"), "public.final_status_counts")),
            "- generated final_status: "
            + _counts_text(_mapping(generated.get("final_status_counts"), "generated.final_status_counts")),
            "",
            "## Label Distribution",
            "",
            "- public local aggregate: "
            + _counts_text(label_distribution.get("public_local_eval_only") or {}),
            "- generated labels: " + _counts_text(label_distribution.get("generated") or {}),
            "",
            "## No-Go Warnings",
            "",
        ]
    )

    if warning_rows:
        for warning in warning_rows:
            if isinstance(warning, Mapping):
                lines.append(f"- `{warning.get('code')}`: {warning.get('message')}")
    else:
        lines.append("- 없음")

    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare public20 and generated candidate profile dimensions for Gate B.")
    parser.add_argument("--public-profile", required=True, type=Path, help="public20 profile JSON path.")
    parser.add_argument("--generated-profile", required=True, type=Path, help="generated candidate profile JSON path.")
    parser.add_argument(
        "--public-label-distribution",
        type=Path,
        help="Optional local aggregate label distribution JSON. Row-level labels are not accepted here.",
    )
    parser.add_argument("--output-json", type=Path, help="Optional comparison report JSON path.")
    parser.add_argument("--output-md", type=Path, help="Optional comparison report Markdown path.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        public_profile = _mapping(_load_json(args.public_profile), "public_profile")
        generated_profile = _mapping(_load_json(args.generated_profile), "generated_profile")
        public_labels = None
        if args.public_label_distribution is not None:
            public_labels = _mapping(_load_json(args.public_label_distribution), "public_label_distribution")
        report = compare_profiles(
            public_profile,
            generated_profile,
            public_label_distribution=public_labels,
            public_profile_path=args.public_profile,
            generated_profile_path=args.generated_profile,
        )

        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.output_md is not None:
            args.output_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_md.write_text(render_markdown(report), encoding="utf-8")
        if args.output_json is None and args.output_md is None:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    except DimensionComparisonError as exc:
        print(f"compare_public20_dimensions: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
