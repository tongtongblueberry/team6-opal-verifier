# Changed: add RAG-aware evaluation script that uses the Solver class (with RAG fallback).
# Why: intermediate_eval.py uses StatefulOpalVerifier directly, bypassing RAG.
# This script uses the full Solver pipeline to measure the hybrid solver's accuracy.

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def load_dataset(root: Path) -> list[dict[str, Any]]:
    testcase_dir = root / "testcases"
    cases = []
    for path in sorted(testcase_dir.glob("tc*.json"), key=lambda p: int(p.stem.removeprefix("tc").split("_")[0])):
        with path.open("r", encoding="utf-8") as f:
            cases.append({"id": path.name, "steps": json.load(f)})
    return cases


def load_labels(path: Path) -> dict[str, str]:
    labels = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            labels[rec["filename"]] = str(rec["label"]).strip().lower()
    return labels


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--label-path", type=Path, default=None)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset_root)
    label_path = args.label_path or args.dataset_root / "label.jsonl"
    labels = load_labels(label_path)

    # Changed: use Solver class (not StatefulOpalVerifier) to trigger RAG path.
    # Why: Solver.predict() runs verify_with_trace → checks confidence → calls RAG if needed.
    from src.solver import Solver
    print("Initializing Solver (loading model + building BM25 index)...")
    t0 = time.time()
    solver = Solver()
    init_time = time.time() - t0
    print(f"Solver init: {init_time:.1f}s, rag_solver={'available' if solver.rag_solver else 'None'}")

    # Filter to labeled cases
    labeled = [item for item in dataset if item["id"] in labels]
    print(f"Evaluating {len(labeled)} labeled cases...")

    t0 = time.time()
    predictions = solver.predict(labeled)
    eval_time = time.time() - t0

    # Compute metrics
    correct = 0
    tp = fp = fn = tn = 0
    mismatches = []
    for item in labeled:
        cid = item["id"]
        pred = predictions.get(cid, "pass")
        gold = labels[cid]
        if pred == gold:
            correct += 1
        else:
            mismatches.append((cid, gold, pred))
        if gold == "fail" and pred == "fail":
            tp += 1
        elif gold == "pass" and pred == "fail":
            fp += 1
        elif gold == "fail" and pred == "pass":
            fn += 1
        else:
            tn += 1

    n = len(labeled)
    accuracy = 100.0 * correct / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print(f"\n=== RAG Hybrid Solver Evaluation ===")
    print(f"accuracy={accuracy:.2f} ({correct}/{n})")
    print(f"precision(fail)={precision:.4f}")
    print(f"recall(fail)={recall:.4f}")
    print(f"f1(fail)={f1:.4f}")
    print(f"tp={tp} fp={fp} fn={fn} tn={tn}")
    print(f"init_time={init_time:.1f}s eval_time={eval_time:.1f}s total={init_time+eval_time:.1f}s")
    if mismatches:
        print(f"\nMismatches ({len(mismatches)}):")
        for cid, gold, pred in mismatches:
            print(f"  {cid}: gold={gold} pred={pred}")
    print(f"\nrag_solver={'available' if solver.rag_solver else 'None'}")


if __name__ == "__main__":
    main()
