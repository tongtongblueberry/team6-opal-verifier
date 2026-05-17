# Changed: add Metamorphic Coverage-style diagnostics for solver traces.
# Why: pass-rate-only metamorphic evaluation saturated, so we need differential coverage signals.

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Changed: support direct server execution without package installation.
    # Why: diagnostics run from the repository checkout on the course server.
    sys.path.insert(0, str(ROOT))

from src.solver import StatefulOpalVerifier, _compact, _invoking_name, _method_name, _object_kind, _status_name
from tools.metamorphic_eval import SyntheticCase, build_synthetic_cases, load_public_cases


Json = dict[str, Any]


@dataclass
class PairCoverage:
    # Changed: store one source/follow-up differential coverage record.
    # Why: MC evaluates metamorphic tests by pair-level coverage differences.
    name: str
    source: str
    relation: str
    expected: str
    prediction: str
    correct: bool
    source_coverage_size: int
    followup_coverage_size: int
    union_coverage_size: int
    mc_size: int
    mc_ratio: float
    union_features: list[str]
    differential_features: list[str]


def trailing_index(name: str) -> int | None:
    match = re.search(r":(\d+)$", name)
    if match is None:
        return None
    return int(match.group(1))


def relation_name(name: str) -> str:
    parts = name.split(":")
    if len(parts) < 2:
        return name
    return parts[1]


def source_steps_for_case(case: SyntheticCase, public: dict[str, list[Json]]) -> list[Json]:
    # Changed: reconstruct the source input paired with a synthetic follow-up input.
    # Why: MC requires comparing the original source execution with its transformed follow-up.
    steps = public.get(case.source, [])
    if not steps:
        return []
    index = trailing_index(case.name)
    if index is None or index >= len(steps):
        return steps
    if len(case.steps) == 1:
        return [steps[index]]
    return steps[: index + 1]


def final_feature_tokens(steps: list[Json], prediction: str) -> set[str]:
    if not steps:
        return {"parse:empty"}
    final = steps[-1]
    command = final.get("input", {}) if isinstance(final, dict) else {}
    output = final.get("output", {}) if isinstance(final, dict) else {}
    method = _compact(_method_name(command)) or "unknown"
    invoking = _compact(_invoking_name(command)) or "unknown"
    kind = _object_kind(command) or "unknown"
    status = _status_name(output) or "unknown"
    return {
        f"final_method:{method}",
        f"final_invoking:{invoking}",
        f"final_object_kind:{kind}",
        f"final_status:{status}",
        f"prediction:{prediction}",
    }


def coverage_tokens(verifier: StatefulOpalVerifier, steps: list[Json]) -> tuple[set[str], str]:
    # Changed: map solver trace events to protocol coverage units.
    # Why: the paper uses code coverage; this project needs rule/state/spec coverage instead.
    result = verifier.verify_with_trace(steps)
    prediction = str(result.get("prediction", ""))
    trace = list(result.get("trace", []))
    tokens = final_feature_tokens(steps, prediction)
    previous_rule = ""
    for event in trace:
        rule = str(event.get("rule_id", ""))
        if rule:
            tokens.add(f"rule:{rule}")
            if previous_rule:
                tokens.add(f"rule_transition:{previous_rule}->{rule}")
            previous_rule = rule
        for read in event.get("state_reads", []):
            tokens.add(f"read:{read}")
            if rule:
                tokens.add(f"rule_read:{rule}:{read}")
        for write in event.get("state_writes", []):
            tokens.add(f"write:{write}")
            if rule:
                tokens.add(f"rule_write:{rule}:{write}")
        for spec_query in event.get("spec_ref_candidates", []):
            tokens.add(f"spec_query:{_compact(spec_query)}")
    return tokens, prediction


def coefficient_of_variation(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = statistics.fmean(values)
    if mean == 0:
        return 0.0
    return statistics.pstdev(values) / mean


def summarize_pairs(pairs: list[PairCoverage]) -> Json:
    groups: dict[str, list[PairCoverage]] = {}
    for pair in pairs:
        groups.setdefault(pair.relation, []).append(pair)

    group_summary: dict[str, Json] = {}
    for relation, items in sorted(groups.items()):
        mc_values = [float(item.mc_size) for item in items]
        union_values = [float(item.union_coverage_size) for item in items]
        group_summary[relation] = {
            "pairs": len(items),
            "mean_mc_size": statistics.fmean(mc_values) if mc_values else 0.0,
            "mean_union_coverage_size": statistics.fmean(union_values) if union_values else 0.0,
            "zero_mc_pairs": sum(1 for item in items if item.mc_size == 0),
            "correct": sum(1 for item in items if item.correct),
        }

    all_mc = [float(pair.mc_size) for pair in pairs]
    all_union = [float(pair.union_coverage_size) for pair in pairs]
    group_mc_means = [float(item["mean_mc_size"]) for item in group_summary.values()]
    group_union_means = [float(item["mean_union_coverage_size"]) for item in group_summary.values()]
    total_union = set()
    total_mc = set()
    for pair in pairs:
        total_mc.update(pair.differential_features)
        total_union.update(pair.union_features)

    low_mc_relations = sorted(
        group_summary.items(),
        key=lambda item: (float(item[1]["mean_mc_size"]), -int(item[1]["pairs"]), item[0]),
    )[:10]
    high_mc_relations = sorted(
        group_summary.items(),
        key=lambda item: (-float(item[1]["mean_mc_size"]), item[0]),
    )[:10]

    return {
        "pairs": len(pairs),
        "correct": sum(1 for pair in pairs if pair.correct),
        "mean_pair_mc_size": statistics.fmean(all_mc) if all_mc else 0.0,
        "median_pair_mc_size": statistics.median(all_mc) if all_mc else 0.0,
        "max_pair_mc_size": max(all_mc) if all_mc else 0.0,
        "mean_pair_union_coverage_size": statistics.fmean(all_union) if all_union else 0.0,
        "zero_mc_pairs": sum(1 for pair in pairs if pair.mc_size == 0),
        "mc_cv_by_relation": coefficient_of_variation(group_mc_means),
        "coverage_cv_by_relation": coefficient_of_variation(group_union_means),
        "unique_mc_features": len(total_mc),
        "unique_differential_features": len(total_union),
        "low_mc_relations": [
            {"relation": relation, **summary}
            for relation, summary in low_mc_relations
        ],
        "high_mc_relations": [
            {"relation": relation, **summary}
            for relation, summary in high_mc_relations
        ],
        "relations": group_summary,
    }


def build_pair_coverage(public: dict[str, list[Json]], synthetic: list[SyntheticCase]) -> list[PairCoverage]:
    verifier = StatefulOpalVerifier()
    pairs: list[PairCoverage] = []
    for case in synthetic:
        source_steps = source_steps_for_case(case, public)
        if not source_steps:
            continue
        source_cov, _ = coverage_tokens(verifier, source_steps)
        followup_cov, prediction = coverage_tokens(verifier, case.steps)
        union_cov = source_cov | followup_cov
        mc = source_cov ^ followup_cov
        pairs.append(
            PairCoverage(
                name=case.name,
                source=case.source,
                relation=relation_name(case.name),
                expected=case.expected,
                prediction=prediction,
                correct=prediction == case.expected,
                source_coverage_size=len(source_cov),
                followup_coverage_size=len(followup_cov),
                union_coverage_size=len(union_cov),
                mc_size=len(mc),
                mc_ratio=(len(mc) / len(union_cov)) if union_cov else 0.0,
                union_features=sorted(union_cov),
                differential_features=sorted(mc),
            )
        )
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--out", type=Path, default=Path("reports/metamorphic_coverage.json"))
    parser.add_argument("--jsonl-out", type=Path, default=None)
    args = parser.parse_args()

    public = load_public_cases(args.dataset_root)
    synthetic = build_synthetic_cases(public)
    pairs = build_pair_coverage(public, synthetic)
    summary = summarize_pairs(pairs)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.jsonl_out is not None:
        args.jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        args.jsonl_out.write_text(
            "".join(json.dumps(asdict(pair), ensure_ascii=False) + "\n" for pair in pairs),
            encoding="utf-8",
        )

    print(f"pairs={summary['pairs']}")
    print(f"correct={summary['correct']}/{summary['pairs']}")
    print(f"mean_pair_mc_size={summary['mean_pair_mc_size']:.2f}")
    print(f"zero_mc_pairs={summary['zero_mc_pairs']}")
    print(f"mc_cv_by_relation={summary['mc_cv_by_relation']:.2f}")
    print(f"coverage_cv_by_relation={summary['coverage_cv_by_relation']:.2f}")
    print(f"out={args.out}")


if __name__ == "__main__":
    main()
