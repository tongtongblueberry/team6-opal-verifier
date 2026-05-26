"""Diagnose rule engine performance on public 20 cases.

Changed: outputs detailed per-case analysis including rule_id, confidence tier,
and where the rule engine agrees/disagrees with gold labels.
Why: understanding the error pattern on public cases is critical for
directing LoRA training to fix the right cases.

Output: per-case analysis + summary statistics.
"""
import argparse
import sys, json, glob, os, logging
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# Changed: 진단 결과 기본 루트를 env로 재정의 가능하게 분리.
# Why: diagnose_public 기본 출력이 이전 /workspace/team6에 쓰이지 않도록 함.
DEFAULT_RUNTIME_ROOT = Path(
    os.environ.get("OPAL_RUNTIME_ROOT", "/workspace/sinjeongmin_opal_verifier")
)
DEFAULT_OUTPUT = DEFAULT_RUNTIME_ROOT / "public_diagnosis.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("diagnose")

from src.solver import StatefulOpalVerifier

# Changed: confidence tier classification (must match solver.py).
HIGH_CONFIDENCE_RULES = {
    "PARSE_FINAL_COMMAND", "PROPERTIES_TARGET", "PROPERTIES_PAYLOAD",
    "STARTSESSION_FINAL", "PRECONDITION_EXPECTED_ERROR", "KNOWN_FIELD_INVALID_VALUE",
    "LOCKING_DATA_ACCESS", "ACTIVATE_TARGET",
}
LOW_CONFIDENCE_RULES = {
    "UNEXPECTED_ERROR_STATUS", "DEFAULT_PASS", "KNOWN_FIELD_EXPECTED_SUCCESS",
}


def get_tier(rule_id):
    if rule_id in HIGH_CONFIDENCE_RULES:
        return "HIGH"
    elif rule_id in LOW_CONFIDENCE_RULES:
        return "LOW"
    return "MEDIUM"


def main():
    parser = argparse.ArgumentParser(description="Diagnose rule engine on public cases")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="진단 JSON 출력 경로",
    )
    args = parser.parse_args()

    verifier = StatefulOpalVerifier()

    # Load public labels
    pub_labels = {}
    for line in open("/dl2026/dataset/label.jsonl"):
        d = json.loads(line)
        pub_labels[d["filename"]] = d["label"]

    logger.info("=" * 70)
    logger.info("PUBLIC 20 RULE ENGINE DIAGNOSIS")
    logger.info("=" * 70)

    results = []
    for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
        fname = os.path.basename(tc_file)
        steps = json.load(open(tc_file))
        gold = pub_labels.get(fname, "?")

        result = verifier.verify_with_trace(steps)
        pred = result["prediction"]
        trace = result.get("trace", [])

        # Extract final rule info
        rule_id = trace[-1].get("rule_id", "?") if trace else "?"
        detail = trace[-1].get("detail", "") if trace else ""
        tier = get_tier(rule_id)

        correct = pred == gold
        results.append({
            "filename": fname,
            "gold": gold,
            "pred": pred,
            "correct": correct,
            "rule_id": rule_id,
            "tier": tier,
            "detail": detail,
            "n_steps": len(verifier._records(steps)),
        })

        status = "OK" if correct else "ERR"
        logger.info("  %s: gold=%s pred=%s [%s] rule=%s tier=%s detail=%s steps=%d",
                    fname, gold, pred, status, rule_id, tier,
                    detail[:60] if detail else "-", results[-1]["n_steps"])

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    total = len(results)
    correct = sum(r["correct"] for r in results)
    logger.info("Accuracy: %d/%d (%.1f%%)", correct, total, correct / total * 100)

    # Per-tier
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        tier_results = [r for r in results if r["tier"] == tier]
        if tier_results:
            t_correct = sum(r["correct"] for r in tier_results)
            logger.info("  %s: %d/%d (%.1f%%)", tier, t_correct, len(tier_results),
                        t_correct / len(tier_results) * 100)

    # Per-rule
    logger.info("\nPer-rule breakdown:")
    rule_counter = Counter()
    rule_correct = Counter()
    for r in results:
        rule_counter[r["rule_id"]] += 1
        if r["correct"]:
            rule_correct[r["rule_id"]] += 1
    for rule_id, count in rule_counter.most_common():
        c = rule_correct[rule_id]
        logger.info("  %s: %d/%d (%.0f%%)", rule_id, c, count, c / count * 100)

    # Error analysis
    errors = [r for r in results if not r["correct"]]
    if errors:
        logger.info("\nERROR CASES:")
        for r in errors:
            logger.info("  %s: gold=%s pred=%s rule=%s tier=%s",
                        r["filename"], r["gold"], r["pred"], r["rule_id"], r["tier"])

        # Key question: how many errors are from LOW confidence rules?
        low_errors = [r for r in errors if r["tier"] == "LOW"]
        logger.info("\nLOW confidence errors (LLM should fix these): %d/%d",
                    len(low_errors), len(errors))
        for r in low_errors:
            logger.info("  %s: gold=%s pred=%s rule=%s detail=%s",
                        r["filename"], r["gold"], r["pred"], r["rule_id"], r["detail"][:80])

    # Save detailed results
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(out_path, "w"), indent=2)
    logger.info("\nSaved to %s", out_path)


if __name__ == "__main__":
    main()
