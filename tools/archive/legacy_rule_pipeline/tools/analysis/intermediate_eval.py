# Changed: add a server-side intermediate evaluation report for the verifier loop.
# Why: public train/dev labels should be used to diagnose parser/rule coverage before leaderboard submission.

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    # Changed: make direct `python tools/intermediate_eval.py` execution work on the server.
    # Why: Python otherwise searches from tools/ and cannot import the submission `src` package.
    sys.path.insert(0, str(ROOT))

from src.solver import _invoking_name, _method_name, _status_name, StatefulOpalVerifier


Json = dict[str, Any]


@dataclass
class CaseSummary:
    # Changed: store only public-eval diagnostics, not private/leaderboard-derived labels.
    # Why: this keeps train/dev analysis separate from leaderboard/test data.
    case_id: str
    label: str
    prediction: str
    correct: bool
    steps: int
    final_method: str
    final_invoking: str
    final_status: str
    receptive_field: list[str]
    rule_ids: list[str]
    state_reads: list[str]
    state_writes: list[str]
    spec_ref_candidates: list[str]
    spec_hits: list[str]


def case_number(path: Path) -> int:
    return int(path.stem.removeprefix("tc").split("_")[0])


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_labels(path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            labels[record["filename"]] = str(record["label"]).strip().lower()
    return labels


def load_dataset(root: Path) -> list[Json]:
    testcase_dir = root / "testcases"
    return [
        {"id": path.name, "steps": load_json(path)}
        for path in sorted(testcase_dir.glob("tc*.json"), key=case_number)
    ]


def event_signature(step: Json) -> str:
    # Changed: compact each command/response into a readable evidence field.
    # Why: this approximates the rule engine's effective receptive field for human review.
    command = step.get("input", {}) if isinstance(step, dict) else {}
    output = step.get("output", {}) if isinstance(step, dict) else {}
    method = _method_name(command)
    invoking = _invoking_name(command)
    status = _status_name(output)
    return f"{method or '?'}({invoking or '?'}) -> {status or '?'}"


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def build_spec_index(spec_root: Path | None) -> list[tuple[str, str]]:
    # Changed: make guidebook lookup optional and lightweight.
    # Why: default eval should stay fast, but server runs can attach concrete chunk candidates.
    if spec_root is None or not spec_root.exists():
        return []
    index: list[tuple[str, str]] = []
    for path in spec_root.rglob("*.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        index.append((str(path.relative_to(spec_root)), text))
    return index


def resolve_spec_hits(candidates: list[str], spec_index: list[tuple[str, str]], limit: int) -> list[str]:
    if not candidates or not spec_index or limit <= 0:
        return []
    terms = unique(
        [
            token.lower()
            for candidate in candidates
            for token in candidate.replace("_", " ").split()
            if len(token) >= 4
        ]
    )
    scored: list[tuple[int, str]] = []
    for path, text in spec_index:
        score = sum(1 for term in terms if term in text)
        if score:
            scored.append((score, path))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, path in scored[:limit]]


def summarize_case(
    item: Json,
    label: str,
    prediction: str,
    trace: list[Json],
    window: int,
    spec_index: list[tuple[str, str]],
    spec_hits: int,
) -> CaseSummary:
    steps = item["steps"]
    final = steps[-1] if steps else {}
    command = final.get("input", {}) if isinstance(final, dict) else {}
    output = final.get("output", {}) if isinstance(final, dict) else {}
    receptive_steps = steps[max(0, len(steps) - window) :] if isinstance(steps, list) else []
    rule_ids = unique([str(event.get("rule_id", "")) for event in trace])
    state_reads = unique([read for event in trace for read in event.get("state_reads", [])])
    state_writes = unique([write for event in trace for write in event.get("state_writes", [])])
    spec_ref_candidates = unique(
        [query for event in trace for query in event.get("spec_ref_candidates", [])]
    )
    return CaseSummary(
        case_id=item["id"],
        label=label,
        prediction=prediction,
        correct=label == prediction,
        steps=len(steps) if isinstance(steps, list) else 0,
        final_method=_method_name(command),
        final_invoking=_invoking_name(command),
        final_status=_status_name(output),
        receptive_field=[event_signature(step) for step in receptive_steps],
        rule_ids=rule_ids,
        state_reads=state_reads,
        state_writes=state_writes,
        spec_ref_candidates=spec_ref_candidates,
        spec_hits=resolve_spec_hits(spec_ref_candidates, spec_index, spec_hits),
    )


def write_markdown(path: Path, summaries: list[CaseSummary], score: float, dataset_root: Path) -> None:
    # Changed: produce a durable Korean report on the server for review.
    # Why: the user asked to inspect intermediate evaluation before leaderboard submission.
    mismatches = [item for item in summaries if not item.correct]
    by_method: dict[str, list[CaseSummary]] = defaultdict(list)
    for item in summaries:
        by_method[item.final_method or "?"].append(item)

    lines: list[str] = []
    lines.append("# 중간평가 보고서")
    lines.append("")
    lines.append(f"- Dataset root: `{dataset_root}`")
    lines.append("- Split policy: public labeled data only. Leaderboard/private test data not used.")
    lines.append(f"- Total cases: {len(summaries)}")
    lines.append(f"- Score: `{score:.2f}`")
    lines.append(f"- Correct: `{len(summaries) - len(mismatches)}`")
    lines.append(f"- Mismatch: `{len(mismatches)}`")
    lines.append("")
    lines.append("## Final Method Breakdown")
    lines.append("")
    lines.append("| Final method | Correct | Total | Accuracy |")
    lines.append("|---|---:|---:|---:|")
    for method, items in sorted(by_method.items()):
        correct = sum(1 for item in items if item.correct)
        accuracy = 100.0 * correct / len(items)
        lines.append(f"| `{method}` | {correct} | {len(items)} | {accuracy:.2f} |")
    lines.append("")
    lines.append("## Mismatches")
    lines.append("")
    if not mismatches:
        lines.append("No public mismatches.")
    else:
        lines.append("| Case | Label | Prediction | Final | Status | Rules | State | Spec hits |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for item in mismatches:
            final = f"{item.final_method} / {item.final_invoking}"
            rules = "<br>".join(f"`{rule}`" for rule in item.rule_ids[-4:])
            state = "reads: " + ", ".join(item.state_reads[-4:]) + "<br>writes: " + ", ".join(
                item.state_writes[-4:]
            )
            spec = "<br>".join(f"`{hit}`" for hit in item.spec_hits[:3]) or "<br>".join(
                f"`{query}`" for query in item.spec_ref_candidates[-3:]
            )
            lines.append(
                f"| `{item.case_id}` | `{item.label}` | `{item.prediction}` | "
                f"`{final}` | `{item.final_status}` | {rules} | {state} | {spec} |"
            )
    lines.append("")
    lines.append("## All Cases")
    lines.append("")
    lines.append("| Case | Label | Prediction | Correct | Final | Status | Steps |")
    lines.append("|---|---|---|---:|---|---|---:|")
    for item in summaries:
        final = f"{item.final_method} / {item.final_invoking}"
        lines.append(
            f"| `{item.case_id}` | `{item.label}` | `{item.prediction}` | "
            f"{int(item.correct)} | `{final}` | `{item.final_status}` | {item.steps} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_brief(summaries: list[CaseSummary], score: float) -> None:
    # Changed: make the default output concise enough for fast iteration.
    # Why: long markdown reports should be opt-in, not part of every tuning loop.
    mismatches = [item for item in summaries if not item.correct]
    by_method: dict[str, list[CaseSummary]] = defaultdict(list)
    for item in summaries:
        by_method[item.final_method or "?"].append(item)

    print(f"score={score:.2f}")
    print(f"correct={len(summaries) - len(mismatches)}/{len(summaries)}")
    print(f"mismatch={len(mismatches)}")
    print("methods=" + ", ".join(
        f"{method}:{sum(1 for item in items if item.correct)}/{len(items)}"
        for method, items in sorted(by_method.items())
    ))
    for item in mismatches:
        final = f"{item.final_method}/{item.final_invoking}".strip("/")
        rules = ",".join(item.rule_ids[-3:])
        reads = ",".join(item.state_reads[-4:])
        writes = ",".join(item.state_writes[-4:])
        refs = ",".join(item.spec_hits[:2] or item.spec_ref_candidates[-2:])
        print(
            f"mismatch {item.case_id}: label={item.label} pred={item.prediction} "
            f"final={final} status={item.final_status} rules=[{rules}] "
            f"reads=[{reads}] writes=[{writes}] refs=[{refs}]"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--label-path", type=Path, default=None)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--jsonl-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    parser.add_argument("--spec-root", type=Path, default=None)
    parser.add_argument("--spec-hits", type=int, default=0)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset_root)
    label_path = args.label_path or args.dataset_root / "label.jsonl"
    labels = load_labels(label_path)
    verifier = StatefulOpalVerifier()
    spec_index = build_spec_index(args.spec_root)

    summaries: list[CaseSummary] = []
    for item in dataset:
        if item["id"] not in labels:
            continue
        result = verifier.verify_with_trace(item["steps"])
        summaries.append(
            summarize_case(
                item,
                labels[item["id"]],
                str(result["prediction"]),
                list(result.get("trace", [])),
                args.window,
                spec_index,
                args.spec_hits,
            )
        )
    correct = sum(1 for item in summaries if item.correct)
    score = 100.0 * correct / len(summaries) if summaries else 0.0

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(
                {
                    "dataset_root": str(args.dataset_root),
                    "score": score,
                    "total": len(summaries),
                    "correct": correct,
                    "mismatch": len(summaries) - correct,
                    "cases": [asdict(item) for item in summaries],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.jsonl_out is not None:
        args.jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        args.jsonl_out.write_text(
            "".join(json.dumps(asdict(item), ensure_ascii=False) + "\n" for item in summaries),
            encoding="utf-8",
        )
    if args.md_out is not None:
        write_markdown(args.md_out, summaries, score, args.dataset_root)

    print_brief(summaries, score)
    if args.json_out is not None:
        print(f"json={args.json_out}")
    if args.jsonl_out is not None:
        print(f"jsonl={args.jsonl_out}")
    if args.md_out is not None:
        print(f"markdown={args.md_out}")


if __name__ == "__main__":
    main()
