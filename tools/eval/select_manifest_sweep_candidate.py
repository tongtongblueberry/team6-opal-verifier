from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
DEFAULT_SPLIT = "hidden"
DEFAULT_STATUSES = ("completed", "skipped_completed")
TOOL_NAME = "tools/eval/select_manifest_sweep_candidate.py"


# Changed: keep this selector as a JSON-only post-processor.
# Why: threshold-aware selection must not import model runtime, rule code, or solver modules.
@dataclass(frozen=True)
class SelectionOptions:
    split: str = DEFAULT_SPLIT
    selection_metric: str | None = None
    precision_metric: str | None = None
    recall_metric: str | None = None
    min_fail_precision: float = 0.90
    min_fail_recall: float = 0.80
    selection_direction: str = "max"
    statuses: tuple[str, ...] = DEFAULT_STATUSES
    top_k: int = 10


class SelectionError(ValueError):
    pass


def fail(message: str, exit_code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select a threshold-aware candidate from manifest LoRA sweep artifacts."
    )
    parser.add_argument("--sweep-json", required=True, help="Path to manifest_lora_sweep_results.json.")
    parser.add_argument("--split", default=DEFAULT_SPLIT, help="Split used for constraints and selection.")
    parser.add_argument(
        "--selection-metric",
        default=None,
        help="Dotted metric path inside each threshold entry, or a split metric key. Default: hidden accuracy.",
    )
    parser.add_argument(
        "--selection-direction",
        choices=("max", "min"),
        default="max",
        help="Whether the selection metric is better when larger or smaller.",
    )
    parser.add_argument(
        "--precision-metric",
        default=None,
        help="Dotted metric path for fail precision, or a split metric key. Default: hidden precision_fail.",
    )
    parser.add_argument(
        "--recall-metric",
        default=None,
        help="Dotted metric path for fail recall, or a split metric key. Default: hidden recall_fail.",
    )
    parser.add_argument("--min-fail-precision", type=float, default=0.90)
    parser.add_argument("--min-fail-recall", type=float, default=0.80)
    parser.add_argument(
        "--status",
        action="append",
        dest="statuses",
        choices=DEFAULT_STATUSES,
        default=None,
        help="Sweep result status to include. Repeatable. Defaults to completed and skipped_completed.",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Number of ranked candidates to include.")
    parser.add_argument("--output-json", default=None, help="Optional JSON report path.")
    parser.add_argument("--output-md", default=None, help="Optional Markdown report path.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Format printed to stdout.",
    )
    return parser.parse_args(argv)


def validate_options(options: SelectionOptions) -> None:
    if not options.split:
        raise SelectionError("split must not be empty")
    if options.selection_direction not in {"max", "min"}:
        raise SelectionError("selection_direction must be 'max' or 'min'")
    for name, value in (
        ("min_fail_precision", options.min_fail_precision),
        ("min_fail_recall", options.min_fail_recall),
    ):
        if not 0.0 <= value <= 1.0:
            raise SelectionError(f"{name} must be between 0.0 and 1.0")
    if options.top_k < 0:
        raise SelectionError("top_k must be non-negative")
    if not options.statuses:
        raise SelectionError("at least one status must be included")


def options_from_args(args: argparse.Namespace) -> SelectionOptions:
    return SelectionOptions(
        split=args.split,
        selection_metric=args.selection_metric,
        precision_metric=args.precision_metric,
        recall_metric=args.recall_metric,
        min_fail_precision=args.min_fail_precision,
        min_fail_recall=args.min_fail_recall,
        selection_direction=args.selection_direction,
        statuses=tuple(args.statuses or DEFAULT_STATUSES),
        top_k=args.top_k,
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SelectionError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SelectionError(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SelectionError(f"JSON root must be an object: {path}")
    return data


def nested_get(data: Any, dotted_path: str) -> Any:
    current = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def metric_path(value: str | None, split: str, default_key: str) -> str:
    metric = value or default_key
    if metric.startswith("metrics."):
        return metric
    if "." in metric:
        return metric
    return f"metrics.by_split.{split}.{metric}"


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_eval_json_path(raw_path: Any, sweep_json_path: Path, sweep_report: dict[str, Any]) -> Path | None:
    if not raw_path:
        return None
    path = Path(str(raw_path)).expanduser()
    if path.is_absolute():
        return path
    candidates = [sweep_json_path.parent / path]
    run_root = sweep_report.get("run_root")
    if run_root:
        candidates.append(Path(str(run_root)).expanduser() / path)
    candidates.append(Path.cwd() / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def calibration_summary(block: Any) -> dict[str, Any]:
    if not isinstance(block, dict):
        return {
            "n": None,
            "brier_score": None,
            "ece": None,
            "ece_bins": None,
            "mean_p_fail_by_gold": None,
        }
    return {
        "n": block.get("n"),
        "brier_score": optional_float(block.get("brier_score")),
        "ece": optional_float(block.get("ece")),
        "ece_bins": block.get("ece_bins"),
        "mean_p_fail_by_gold": block.get("mean_p_fail_by_gold"),
    }


def config_name_for(result: dict[str, Any], result_index: int) -> str:
    config = result.get("config")
    if isinstance(config, dict) and config.get("name"):
        return str(config["name"])
    return f"result_{result_index}"


def threshold_entries(eval_report: dict[str, Any]) -> list[dict[str, Any]]:
    threshold_sweep = eval_report.get("threshold_sweep")
    if not isinstance(threshold_sweep, dict):
        return []
    entries = threshold_sweep.get("metrics_by_threshold")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


# Changed: turn each archived threshold_sweep entry into one selectable candidate.
# Why: base-threshold metrics must not decide a threshold-aware sweep winner.
def candidate_from_entry(
    *,
    result: dict[str, Any],
    result_index: int,
    eval_json_path: Path,
    entry: dict[str, Any],
    options: SelectionOptions,
    selection_metric_path: str,
    precision_metric_path: str,
    recall_metric_path: str,
) -> dict[str, Any] | None:
    threshold = optional_float(entry.get("threshold"))
    selection_value = optional_float(nested_get(entry, selection_metric_path))
    precision_value = optional_float(nested_get(entry, precision_metric_path))
    recall_value = optional_float(nested_get(entry, recall_metric_path))
    if threshold is None or selection_value is None:
        return None

    split_metrics = nested_get(entry, f"metrics.by_split.{options.split}")
    overall_metrics = nested_get(entry, "metrics.overall")
    if not isinstance(split_metrics, dict):
        split_metrics = {}
    if not isinstance(overall_metrics, dict):
        overall_metrics = {}

    config = result.get("config") if isinstance(result.get("config"), dict) else {}
    paths = result.get("paths") if isinstance(result.get("paths"), dict) else {}
    constraints_satisfied = (
        precision_value is not None
        and recall_value is not None
        and precision_value >= options.min_fail_precision
        and recall_value >= options.min_fail_recall
    )
    return {
        "result_index": result_index,
        "config_name": config_name_for(result, result_index),
        "config": config,
        "status": result.get("status"),
        "adapter_final": paths.get("adapter_final"),
        "eval_json": str(eval_json_path),
        "threshold": threshold,
        "selection_metric_value": selection_value,
        "precision_metric_value": precision_value,
        "recall_metric_value": recall_value,
        "constraints_satisfied": constraints_satisfied,
        "calibration": {
            options.split: calibration_summary(split_metrics),
            "overall": calibration_summary(overall_metrics),
        },
        "metrics": {
            options.split: split_metrics,
            "overall": overall_metrics,
        },
    }


# Changed: reload every eval_manifest JSON instead of trusting the sweep summary cache.
# Why: manifest_lora_sweep_results.json stores only a shallow eval summary.
def collect_candidates(
    sweep_json_path: Path,
    sweep_report: dict[str, Any],
    options: SelectionOptions,
    selection_metric_path: str,
    precision_metric_path: str,
    recall_metric_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    skipped_results: list[dict[str, Any]] = []
    results = sweep_report.get("results")
    if not isinstance(results, list):
        raise SelectionError("sweep JSON missing results list")

    for result_index, result in enumerate(results):
        if not isinstance(result, dict):
            skipped_results.append({"result_index": result_index, "reason": "result is not an object"})
            continue
        status = result.get("status")
        if status not in options.statuses:
            skipped_results.append(
                {
                    "result_index": result_index,
                    "config_name": config_name_for(result, result_index),
                    "status": status,
                    "reason": "status not included",
                }
            )
            continue
        paths = result.get("paths")
        eval_json_path = resolve_eval_json_path(
            paths.get("eval_json") if isinstance(paths, dict) else None,
            sweep_json_path,
            sweep_report,
        )
        if eval_json_path is None:
            skipped_results.append(
                {
                    "result_index": result_index,
                    "config_name": config_name_for(result, result_index),
                    "status": status,
                    "reason": "missing paths.eval_json",
                }
            )
            continue
        try:
            eval_report = load_json(eval_json_path)
        except SelectionError as exc:
            skipped_results.append(
                {
                    "result_index": result_index,
                    "config_name": config_name_for(result, result_index),
                    "status": status,
                    "eval_json": str(eval_json_path),
                    "reason": str(exc),
                }
            )
            continue

        entries = threshold_entries(eval_report)
        if not entries:
            skipped_results.append(
                {
                    "result_index": result_index,
                    "config_name": config_name_for(result, result_index),
                    "status": status,
                    "eval_json": str(eval_json_path),
                    "reason": "missing threshold_sweep.metrics_by_threshold",
                }
            )
            continue
        before_count = len(candidates)
        for entry in entries:
            candidate = candidate_from_entry(
                result=result,
                result_index=result_index,
                eval_json_path=eval_json_path,
                entry=entry,
                options=options,
                selection_metric_path=selection_metric_path,
                precision_metric_path=precision_metric_path,
                recall_metric_path=recall_metric_path,
            )
            if candidate is not None:
                candidates.append(candidate)
        if len(candidates) == before_count:
            skipped_results.append(
                {
                    "result_index": result_index,
                    "config_name": config_name_for(result, result_index),
                    "status": status,
                    "eval_json": str(eval_json_path),
                    "reason": "threshold entries missing usable threshold or selection metric",
                }
            )
    return candidates, skipped_results


# Changed: use deterministic ranking with calibration metrics as late tie-breakers.
# Why: repeated runs over the same archived JSON should select the same threshold candidate.
def candidate_sort_key(candidate: dict[str, Any], direction: str) -> tuple[Any, ...]:
    score = float(candidate["selection_metric_value"])
    primary = -score if direction == "max" else score
    precision = optional_float(candidate.get("precision_metric_value"))
    recall = optional_float(candidate.get("recall_metric_value"))
    split_name = next(iter(candidate["calibration"]))
    split_calibration = candidate["calibration"].get(split_name, {})
    brier = optional_float(split_calibration.get("brier_score"))
    ece = optional_float(split_calibration.get("ece"))
    return (
        primary,
        -(precision if precision is not None else float("-inf")),
        -(recall if recall is not None else float("-inf")),
        brier if brier is not None else float("inf"),
        ece if ece is not None else float("inf"),
        str(candidate.get("config_name")),
        float(candidate.get("threshold", 0.0)),
    )


def rank_candidates(candidates: Sequence[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    return sorted(candidates, key=lambda candidate: candidate_sort_key(candidate, direction))


def slim_candidate(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "config_name": candidate["config_name"],
        "config": candidate["config"],
        "threshold": candidate["threshold"],
        "status": candidate["status"],
        "adapter_final": candidate["adapter_final"],
        "eval_json": candidate["eval_json"],
        "selection_metric_value": candidate["selection_metric_value"],
        "precision_metric_value": candidate["precision_metric_value"],
        "recall_metric_value": candidate["recall_metric_value"],
        "constraints_satisfied": candidate["constraints_satisfied"],
        "calibration": candidate["calibration"],
        "metrics": candidate["metrics"],
    }


# Changed: build a standalone report that keeps base-threshold best separate from threshold-aware best.
# Why: reviewers need to compare the old sweep winner with the hidden-split constrained threshold winner.
def build_selection_report(sweep_json_path: Path, options: SelectionOptions) -> dict[str, Any]:
    validate_options(options)
    sweep_json_path = sweep_json_path.expanduser().resolve()
    sweep_report = load_json(sweep_json_path)
    selection_metric_path = metric_path(options.selection_metric, options.split, "accuracy")
    precision_metric_path = metric_path(options.precision_metric, options.split, "precision_fail")
    recall_metric_path = metric_path(options.recall_metric, options.split, "recall_fail")
    candidates, skipped_results = collect_candidates(
        sweep_json_path,
        sweep_report,
        options,
        selection_metric_path,
        precision_metric_path,
        recall_metric_path,
    )
    ranked = rank_candidates(candidates, options.selection_direction)
    constrained = [candidate for candidate in ranked if candidate["constraints_satisfied"]]
    best = constrained[0] if constrained else None
    best_relaxed = ranked[0] if ranked else None
    top_k = options.top_k
    return {
        "created_at_kst": datetime.now(KST).isoformat(),
        "tool": TOOL_NAME,
        "input": {
            "sweep_json": str(sweep_json_path),
            "sweep_created_at_kst": sweep_report.get("created_at_kst"),
            "manifest": sweep_report.get("manifest"),
            "run_root": sweep_report.get("run_root"),
        },
        "selection": {
            "split": options.split,
            "selection_metric": selection_metric_path,
            "selection_direction": options.selection_direction,
            "precision_metric": precision_metric_path,
            "recall_metric": recall_metric_path,
            "min_fail_precision": options.min_fail_precision,
            "min_fail_recall": options.min_fail_recall,
            "statuses": list(options.statuses),
            "top_k": top_k,
        },
        "counts": {
            "results": len(sweep_report.get("results", [])) if isinstance(sweep_report.get("results"), list) else None,
            "candidate_thresholds": len(candidates),
            "constraint_satisfying_thresholds": len(constrained),
            "skipped_results": len(skipped_results),
        },
        "base_threshold_best": sweep_report.get("best"),
        "best": slim_candidate(best),
        "best_relaxed": slim_candidate(best_relaxed),
        "top_candidates": [slim_candidate(candidate) for candidate in ranked[:top_k]],
        "top_constraint_satisfying_candidates": [
            slim_candidate(candidate) for candidate in constrained[:top_k]
        ],
        "skipped_results": skipped_results,
    }


def format_float(value: Any) -> str:
    number = optional_float(value)
    return "N/A" if number is None else f"{number:.6f}"


def format_candidate_row(candidate: dict[str, Any], split: str) -> str:
    calibration = candidate["calibration"].get(split, {})
    return (
        f"| `{candidate['config_name']}` | {format_float(candidate['threshold'])} | "
        f"{format_float(candidate['selection_metric_value'])} | "
        f"{format_float(candidate['precision_metric_value'])} | "
        f"{format_float(candidate['recall_metric_value'])} | "
        f"{format_float(calibration.get('brier_score'))} | {format_float(calibration.get('ece'))} | "
        f"`{candidate['eval_json']}` |"
    )


# Changed: add a human-readable Markdown rendering for the same JSON selection report.
# Why: archive review should not require manually inspecting nested JSON.
def format_markdown_report(report: dict[str, Any]) -> str:
    selection = report["selection"]
    split = selection["split"]
    lines = [
        "# Threshold-aware Manifest Sweep Candidate",
        "",
        f"- created_at_kst: `{report['created_at_kst']}`",
        f"- sweep_json: `{report['input']['sweep_json']}`",
        f"- split: `{split}`",
        f"- selection_metric: `{selection['selection_metric']}` ({selection['selection_direction']})",
        f"- precision constraint: `{selection['precision_metric']} >= {selection['min_fail_precision']}`",
        f"- recall constraint: `{selection['recall_metric']} >= {selection['min_fail_recall']}`",
        f"- candidate thresholds: `{report['counts']['candidate_thresholds']}`",
        f"- constraint-satisfying thresholds: `{report['counts']['constraint_satisfying_thresholds']}`",
        f"- base-threshold best: `{report['base_threshold_best']}`",
        "",
        "## Best",
        "",
    ]
    if report["best"] is None:
        lines.append("- No threshold candidate satisfied both fail precision and fail recall constraints.")
    else:
        lines.extend(
            [
                "| Config | Threshold | Score | Fail Precision | Fail Recall | Brier | ECE | Eval JSON |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
                format_candidate_row(report["best"], split),
            ]
        )
    lines.extend(
        [
            "",
            "## Top Candidates",
            "",
            "| Config | Threshold | Score | Fail Precision | Fail Recall | Brier | ECE | Eval JSON |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for candidate in report["top_candidates"]:
        lines.append(format_candidate_row(candidate, split))
    if not report["top_candidates"]:
        lines.append("| N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
    if report["skipped_results"]:
        lines.extend(["", "## Skipped Results", "", "| Result | Config | Status | Reason |", "|---:|---|---|---|"])
        for item in report["skipped_results"]:
            lines.append(
                f"| {item.get('result_index')} | `{item.get('config_name', 'N/A')}` | "
                f"`{item.get('status', 'N/A')}` | {item.get('reason')} |"
            )
    return "\n".join(lines) + "\n"


def write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        options = options_from_args(args)
        report = build_selection_report(Path(args.sweep_json), options)
    except SelectionError as exc:
        fail(str(exc))

    json_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_text = format_markdown_report(report)
    if args.output_json:
        write_report(Path(args.output_json), json_text)
    if args.output_md:
        write_report(Path(args.output_md), markdown_text)
    print(json_text if args.format == "json" else markdown_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
