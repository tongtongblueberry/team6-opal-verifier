# Changed: generate large-scale training data using rule engine as oracle.
# Why: project.pdf allows artifacts/ with trained models (≤12GB).
# Rule engine correctly labels public 20/20 and metamorphic 1891/1891.
# Use rule engine to label synthetic + public + metamorphic cases → train embedding classifier.
#
# Buckmann & Hill (2024): accuracy scales with training data size.
# 10 samples/class → GPT-4 level. 100 samples/class → surpasses GPT-4.
# With 1000+ samples we expect even better performance.

from __future__ import annotations
import json, sys, pickle
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Json = dict[str, Any]


def main() -> None:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    from src.solver import StatefulOpalVerifier
    from tools.metamorphic_eval import build_synthetic_cases, load_public_cases

    dataset_root = Path("/dl2026/dataset")
    output_dir = Path("/workspace/team6/training_data")
    output_dir.mkdir(parents=True, exist_ok=True)

    verifier = StatefulOpalVerifier()

    # ── Source 1: Public 20 labeled cases ─────────────────────────────────
    logger.info("Loading public cases...")
    labels: dict[str, str] = {}
    label_path = dataset_root / "label.jsonl"
    with label_path.open() as f:
        for line in f:
            rec = json.loads(line.strip())
            labels[rec["filename"]] = str(rec["label"]).strip().lower()

    public_cases = []
    testcase_dir = dataset_root / "testcases"
    for path in sorted(testcase_dir.glob("tc*.json")):
        if path.name not in labels:
            continue
        with path.open() as f:
            steps = json.load(f)
        if isinstance(steps, dict) and "records" in steps:
            steps = steps["records"]
        records = [item for item in steps if isinstance(item, dict)]
        if records:
            public_cases.append({
                "records": records,
                "label": labels[path.name],
                "source": f"public:{path.name}",
            })
    logger.info("Public cases: %d (pass=%d, fail=%d)",
                len(public_cases),
                sum(1 for c in public_cases if c["label"] == "pass"),
                sum(1 for c in public_cases if c["label"] == "fail"))

    # ── Source 2: Metamorphic/synthetic cases (rule engine labeled) ────────
    logger.info("Generating metamorphic cases...")
    public = load_public_cases(dataset_root)
    synthetic = build_synthetic_cases(public)
    logger.info("Metamorphic cases generated: %d", len(synthetic))

    metamorphic_cases = []
    for case in synthetic:
        result = verifier.verify_with_trace(case.steps)
        pred = result["prediction"]
        # Use rule engine prediction as label (oracle)
        records = verifier._records(case.steps)
        if records:
            metamorphic_cases.append({
                "records": records,
                "label": pred,
                "source": f"metamorphic:{case.name}",
            })
    logger.info("Metamorphic cases labeled: %d (pass=%d, fail=%d)",
                len(metamorphic_cases),
                sum(1 for c in metamorphic_cases if c["label"] == "pass"),
                sum(1 for c in metamorphic_cases if c["label"] == "fail"))

    # ── Source 3: DEFAULT_PASS synthetic cases ────────────────────────────
    # These are cases the rule engine can't confidently label.
    # Include them as "pass" (rule engine's default) — the embedding classifier
    # can learn a different boundary if it has enough other examples.
    dp_path = Path("/workspace/team6/large_dp_test_set.json")
    dp_cases = []
    if dp_path.exists():
        dp_data = json.loads(dp_path.read_text())
        for case in dp_data:
            records = verifier._records(case["steps"])
            if records:
                dp_cases.append({
                    "records": records,
                    "label": case["expected"],  # use our synthetic label
                    "source": f"default_pass:{case.get('description', '?')[:30]}",
                })
        logger.info("DEFAULT_PASS cases: %d", len(dp_cases))

    # ── Combine all ──────────────────────────────────────────────────────
    all_cases = public_cases + metamorphic_cases + dp_cases
    logger.info("Total training cases: %d", len(all_cases))
    logger.info("  pass: %d, fail: %d",
                sum(1 for c in all_cases if c["label"] == "pass"),
                sum(1 for c in all_cases if c["label"] == "fail"))

    # Save training data
    out_path = output_dir / "training_cases.json"
    # Save records as serializable format
    serializable = []
    for case in all_cases:
        serializable.append({
            "records": case["records"],
            "label": case["label"],
            "source": case["source"],
        })
    out_path.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")
    logger.info("Saved to %s (%d cases, %.1f MB)",
                out_path, len(serializable), out_path.stat().st_size / 1e6)

    # Summary
    print(f"\n=== TRAINING DATA SUMMARY ===")
    print(f"Public: {len(public_cases)}")
    print(f"Metamorphic: {len(metamorphic_cases)}")
    print(f"DEFAULT_PASS: {len(dp_cases)}")
    print(f"Total: {len(all_cases)}")
    print(f"Pass: {sum(1 for c in all_cases if c['label'] == 'pass')}")
    print(f"Fail: {sum(1 for c in all_cases if c['label'] == 'fail')}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
