# Changed: add a server-side intermediate evaluation report for the verifier loop.
# Why: public train/dev labels should be used to diagnose parser/rule coverage before leaderboard submission.

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Changed: make direct `python tools/intermediate_eval.py` execution work on the server.
    # Why: Python otherwise searches from tools/ and cannot import the submission `src` package.
    sys.path.insert(0, str(ROOT))

from src.solver import _invoking_name, _method_name, _status_name, Solver


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


def summarize_case(item: Json, label: str, prediction: str, window: int) -> CaseSummary:
    steps = item["steps"]
    final = steps[-1] if steps else {}
    command = final.get("input", {}) if isinstance(final, dict) else {}
    output = final.get("output", {}) if isinstance(final, dict) else {}
    receptive_steps = steps[max(0, len(steps) - window) :] if isinstance(steps, list) else []
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
        lines.append("| Case | Label | Prediction | Final | Status | Recent receptive field |")
        lines.append("|---|---|---|---|---|---|")
        for item in mismatches:
            field = "<br>".join(f"`{event}`" for event in item.receptive_field)
            final = f"{item.final_method} / {item.final_invoking}"
            lines.append(
                f"| `{item.case_id}` | `{item.label}` | `{item.prediction}` | "
                f"`{final}` | `{item.final_status}` | {field} |"
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--label-path", type=Path, default=None)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--json-out", type=Path, default=Path("reports/intermediate_eval.json"))
    parser.add_argument("--md-out", type=Path, default=Path("reports/intermediate_eval.md"))
    args = parser.parse_args()

    dataset = load_dataset(args.dataset_root)
    label_path = args.label_path or args.dataset_root / "label.jsonl"
    labels = load_labels(label_path)
    predictions = Solver().predict(dataset)

    summaries = [
        summarize_case(item, labels[item["id"]], predictions.get(item["id"], "fail"), args.window)
        for item in dataset
        if item["id"] in labels
    ]
    correct = sum(1 for item in summaries if item.correct)
    score = 100.0 * correct / len(summaries) if summaries else 0.0

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
    write_markdown(args.md_out, summaries, score, args.dataset_root)

    print(f"score={score:.2f}")
    print(f"correct={correct}/{len(summaries)}")
    print(f"mismatch={len(summaries) - correct}")
    print(f"json={args.json_out}")
    print(f"markdown={args.md_out}")


if __name__ == "__main__":
    main()
