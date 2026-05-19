# Changed: compute rule/state/spec coverage from solver traces.
# Why: guidebook-based improvements need a measurable coverage gap detector.

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    # Changed: support direct server execution from tools/.
    # Why: these diagnostics run outside package-installed contexts.
    sys.path.insert(0, str(ROOT))

from src.solver import RULE_SPEC_QUERIES, StatefulOpalVerifier, _invoking_name, _method_name, _status_name
from tools.eval.metamorphic_eval import build_synthetic_cases, load_public_cases


Json = dict[str, Any]
COVERAGE_COLUMNS = [
    "parser",
    "object_identity",
    "precondition",
    "state_effect",
    "status_invariant",
    "payload_invariant",
    "spec_backed",
    "tested",
]
LOW_CONFIDENCE_RULES = {"DEFAULT_PASS", "PARSE_FINAL_COMMAND", "UNEXPECTED_ERROR_STATUS"}
APPLICABLE_COLUMNS: dict[str, set[str]] = {
    "Properties": {"parser", "object_identity", "status_invariant", "payload_invariant", "spec_backed", "tested"},
    "StartSession": {
        "parser",
        "object_identity",
        "precondition",
        "state_effect",
        "status_invariant",
        "payload_invariant",
        "spec_backed",
        "tested",
    },
    "EndSession": {"parser", "precondition", "state_effect", "status_invariant", "payload_invariant", "spec_backed", "tested"},
    "Get": {"parser", "object_identity", "precondition", "status_invariant", "payload_invariant", "spec_backed", "tested"},
    "Set": {
        "parser",
        "object_identity",
        "precondition",
        "state_effect",
        "status_invariant",
        "payload_invariant",
        "spec_backed",
        "tested",
    },
    "Activate": {
        "parser",
        "object_identity",
        "precondition",
        "state_effect",
        "status_invariant",
        "payload_invariant",
        "spec_backed",
        "tested",
    },
    "GenKey": {
        "parser",
        "object_identity",
        "precondition",
        "state_effect",
        "status_invariant",
        "payload_invariant",
        "spec_backed",
        "tested",
    },
    "Read": {"parser", "state_effect", "status_invariant", "payload_invariant", "spec_backed", "tested"},
    "Write": {"parser", "state_effect", "status_invariant", "payload_invariant", "spec_backed", "tested"},
}


def case_number(path: Path) -> int:
    return int(path.stem.removeprefix("tc").split("_")[0])


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset(root: Path) -> list[Json]:
    return [
        {"id": path.name, "steps": load_json(path)}
        for path in sorted((root / "testcases").glob("tc*.json"), key=case_number)
    ]


def load_synthetic_dataset(root: Path) -> list[Json]:
    # Changed: include rule-specific synthetic cases in coverage diagnostics when requested.
    # Why: public-only coverage can report false gaps for rules already covered by metamorphic tests.
    public = load_public_cases(root)
    return [
        {
            "id": f"synthetic:{case.name}",
            "steps": case.steps,
            "label": case.expected,
            "synthetic_reason": case.reason,
        }
        for case in build_synthetic_cases(public)
    ]


def load_labels(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    labels: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                labels[record["filename"]] = str(record["label"]).strip().lower()
    return labels


def load_spec_index(path: Path | None) -> list[Json]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def spec_hit_count(queries: list[str], spec_index: list[Json]) -> int:
    if not queries or not spec_index:
        return 0
    query_terms = {
        token.lower()
        for query in queries
        for token in query.replace("_", " ").split()
        if len(token) >= 4
    }
    hits = 0
    for record in spec_index:
        haystack = " ".join(
            [
                str(record.get("section_title", "")),
                " ".join(record.get("methods", [])),
                " ".join(record.get("objects", [])),
                " ".join(record.get("fields", [])),
                str(record.get("text_preview", "")),
            ]
        ).lower()
        if any(term in haystack for term in query_terms):
            hits += 1
    return hits


def final_info(steps: list[Json]) -> tuple[str, str, str]:
    final = steps[-1] if steps else {}
    command = final.get("input", {}) if isinstance(final, dict) else {}
    output = final.get("output", {}) if isinstance(final, dict) else {}
    return _method_name(command) or "?", _invoking_name(command) or "?", _status_name(output) or "?"


def categories_for_trace(trace: list[Json], spec_hits: int) -> set[str]:
    categories = {"parser", "tested"}
    rule_ids = {str(item.get("rule_id", "")) for item in trace}
    reads = {read for item in trace for read in item.get("state_reads", [])}
    writes = {write for item in trace for write in item.get("state_writes", [])}
    if any("invoking" in read for read in reads):
        categories.add("object_identity")
    # Changed: count known-field value checks as precondition coverage.
    # Why: they validate method arguments before considering a success payload.
    if (
        "PRECONDITION_EXPECTED_ERROR" in rule_ids
        or "KNOWN_FIELD_INVALID_VALUE" in rule_ids
        or "AUTHORITY_DISABLED_STARTSESSION" in rule_ids
        or "STARTSESSION_FINAL" in rule_ids
    ):
        categories.add("precondition")
    if writes:
        categories.add("state_effect")
    # Changed: count known-field status rules as status-invariant coverage.
    # Why: these rules explain formerly low-confidence non-success finals.
    if any(
        rule in rule_ids
        for rule in {
            "UNEXPECTED_ERROR_STATUS",
            "PRECONDITION_EXPECTED_ERROR",
            "KNOWN_FIELD_EXPECTED_SUCCESS",
            "KNOWN_FIELD_INVALID_VALUE",
            "AUTHORITY_DISABLED_STARTSESSION",
            "PROPERTIES_PAYLOAD",
            "STARTSESSION_FINAL",
            "ACTIVATE_TARGET",
            "READ_PAYLOAD",
            "WRITE_RESPONSE",
            "LOCKING_DATA_ACCESS",
            "SET_PAYLOAD",
            "GET_PAYLOAD",
            "GENKEY_PAYLOAD",
            "ENDSESSION_PAYLOAD",
        }
    ):
        categories.add("status_invariant")
    if any(
        rule in rule_ids
        for rule in {
            "READ_PAYLOAD",
            "GET_PAYLOAD",
            "PROPERTIES_PAYLOAD",
            "STARTSESSION_FINAL",
            "SET_PAYLOAD",
            "ENDSESSION_PAYLOAD",
            "ACTIVATE_PAYLOAD",
            "WRITE_RESPONSE",
            "LOCKING_DATA_ACCESS",
            "GENKEY_PAYLOAD",
        }
    ):
        categories.add("payload_invariant")
    if spec_hits:
        categories.add("spec_backed")
    return categories


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--label-path", type=Path, default=None)
    parser.add_argument("--spec-index", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("reports/rule_coverage.json"))
    parser.add_argument("--include-synthetic", action="store_true")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset_root)
    if args.include_synthetic:
        dataset.extend(load_synthetic_dataset(args.dataset_root))
    labels = load_labels(args.label_path or args.dataset_root / "label.jsonl")
    spec_index = load_spec_index(args.spec_index)
    verifier = StatefulOpalVerifier()

    matrix: dict[str, dict[str, bool]] = defaultdict(lambda: {key: False for key in COVERAGE_COLUMNS})
    cases: list[Json] = []
    low_confidence: list[Json] = []
    correct = 0

    for item in dataset:
        method, invoking, status = final_info(item["steps"])
        result = verifier.verify_with_trace(item["steps"])
        prediction = str(result["prediction"])
        label = str(item.get("label") or labels.get(item["id"], ""))
        if label and prediction == label:
            correct += 1
        trace = list(result.get("trace", []))
        queries = [query for event in trace for query in event.get("spec_ref_candidates", [])]
        hits = spec_hit_count(queries, spec_index)
        categories = categories_for_trace(trace, hits)
        for category in categories:
            matrix[method][category] = True
        rule_ids = [str(event.get("rule_id", "")) for event in trace]
        case = {
            "id": item["id"],
            "label": label,
            "prediction": prediction,
            "correct": (prediction == label) if label else None,
            "final_method": method,
            "final_invoking": invoking,
            "final_status": status,
            "rule_ids": rule_ids,
            "spec_hits": hits,
            "state_reads": sorted({read for event in trace for read in event.get("state_reads", [])}),
            "state_writes": sorted({write for event in trace for write in event.get("state_writes", [])}),
        }
        cases.append(case)
        if not hits or (rule_ids and rule_ids[-1] in LOW_CONFIDENCE_RULES) or not case["state_reads"]:
            low_confidence.append(case)

    total = len([case for case in cases if case["label"]])
    score = 100.0 * correct / total if total else None
    missing = {}
    for method, columns in sorted(matrix.items()):
        applicable = APPLICABLE_COLUMNS.get(method, set(COVERAGE_COLUMNS))
        missing[method] = [column for column in COVERAGE_COLUMNS if column in applicable and not columns[column]]
    output = {
        "score": score,
        "total_labeled": total,
        "correct": correct,
        "matrix": {method: dict(columns) for method, columns in sorted(matrix.items())},
        "missing": missing,
        "low_confidence": low_confidence,
        "cases": cases,
        "rule_spec_queries": RULE_SPEC_QUERIES,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"score={score:.2f}" if score is not None else "score=NA")
    print(f"methods={len(matrix)}")
    print(f"low_confidence={len(low_confidence)}")
    for method, gaps in missing.items():
        print(f"missing {method}: {','.join(gaps) if gaps else 'none'}")
    print(f"out={args.out}")


if __name__ == "__main__":
    main()
