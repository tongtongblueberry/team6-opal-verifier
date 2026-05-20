"""Generate training data focused on rule engine uncertainty cases.

Changed: creates training data where rule engine is uncertain (UNEXPECTED_ERROR_STATUS, DEFAULT_PASS).
Why: these are the ~57/200 cases the rule engine gets wrong. LLM should learn to resolve these.

Pipeline:
1. Run rule engine on ALL training cases → get (prediction, rule_id) per case
2. Tag each case with rule_id confidence tier
3. For UNCERTAIN cases: the gold label teaches the LLM to correct the rule engine
4. Include rule engine analysis in the prompt (neuro-symbolic approach)

Output: /workspace/team6/training_data/uncertainty_train.json
"""
import sys, json, logging, glob, os
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("gen_uncertainty")

from src.solver import StatefulOpalVerifier
from tools.training.finetune_lora_v2 import format_trajectory_rich

# Changed: confidence tiers for rule engine decisions.
# Why: UNEXPECTED_ERROR_STATUS and DEFAULT_PASS are low confidence → LLM should override.
HIGH_CONFIDENCE_RULES = {
    "PARSE_FINAL_COMMAND", "PROPERTIES_TARGET", "PROPERTIES_PAYLOAD",
    "STARTSESSION_FINAL", "PRECONDITION_EXPECTED_ERROR", "KNOWN_FIELD_INVALID_VALUE",
    "LOCKING_DATA_ACCESS", "ACTIVATE_TARGET",
}
LOW_CONFIDENCE_RULES = {
    "UNEXPECTED_ERROR_STATUS", "DEFAULT_PASS", "KNOWN_FIELD_EXPECTED_SUCCESS",
}
# Everything else is MEDIUM confidence


def get_rule_analysis(verifier, steps):
    """Run rule engine and extract detailed analysis."""
    result = verifier.verify_with_trace(steps)
    prediction = result["prediction"]
    trace = result.get("trace", [])

    # Extract final rule_id
    rule_id = "UNKNOWN"
    rule_detail = ""
    if trace:
        last = trace[-1]
        rule_id = last.get("rule_id", "UNKNOWN")
        rule_detail = last.get("detail", "")

    # Determine confidence tier
    if rule_id in HIGH_CONFIDENCE_RULES:
        tier = "high"
    elif rule_id in LOW_CONFIDENCE_RULES:
        tier = "low"
    else:
        tier = "medium"

    return {
        "prediction": prediction,
        "rule_id": rule_id,
        "rule_detail": rule_detail,
        "tier": tier,
        "trace_len": len(trace),
    }


def format_with_rule_context(records, rule_analysis):
    """Format trajectory WITH rule engine analysis for neuro-symbolic training.

    Changed: include rule engine's decision and reasoning in the prompt.
    Why: LLM can use rule engine's structured analysis as additional signal,
    especially knowing WHICH rule fired and what the rule engine saw.
    """
    base_prompt = format_trajectory_rich(records)
    if not base_prompt:
        return ""

    rule_id = rule_analysis["rule_id"]
    rule_pred = rule_analysis["prediction"]
    rule_detail = rule_analysis["rule_detail"]
    tier = rule_analysis["tier"]

    # Changed: add rule engine context block.
    # Why: TOGLL (ASE 2024) + NSVIF (arXiv 2025) show combining symbolic analysis
    # with neural models improves verification accuracy.
    context = (
        f"\n--- Rule Engine Analysis ---\n"
        f"Rule: {rule_id}\n"
        f"Prediction: {rule_pred}\n"
        f"Detail: {rule_detail}\n"
        f"Confidence: {tier}\n"
        f"---\n\n"
        f"The rule engine predicted '{rule_pred}' with {tier} confidence.\n"
        f"Given the trajectory and this analysis, is the final response "
        f"consistent with the TCG/Opal specification? Answer: "
    )

    # Replace the original question with enhanced version
    # Original ends with "Is the final response consistent...? Answer: "
    base_parts = base_prompt.rsplit("Is the final response", 1)
    if len(base_parts) == 2:
        return base_parts[0] + context
    return base_prompt + context


SYSTEM_PROMPT_V3 = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory, session state, and a rule engine's analysis, "
    "determine if the final response is consistent with the specification. "
    "The rule engine may be wrong — use your understanding of the protocol to decide. "
    "Answer exactly: pass or fail"
)


def format_for_training_v3(records, label, rule_analysis):
    """Format a single training example with rule engine context."""
    prompt = format_with_rule_context(records, rule_analysis)
    if not prompt:
        return None

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_V3},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": label},
    ]
    return {"messages": messages, "rule_id": rule_analysis["rule_id"],
            "tier": rule_analysis["tier"], "rule_pred": rule_analysis["prediction"],
            "gold": label, "agrees": rule_analysis["prediction"] == label}


def main():
    verifier = StatefulOpalVerifier()

    # Load all training data sources
    data_sources = []

    # 1. Spec-based training data (main source)
    spec_path = Path("/workspace/team6/training_data/spec_train_augmented.json")
    if spec_path.exists():
        cases = json.loads(spec_path.read_text())
        logger.info("Spec augmented data: %d cases", len(cases))
        data_sources.extend(cases)
    else:
        # Fallback to original
        for p in ["/workspace/team6/training_data/training_cases.json"]:
            if Path(p).exists():
                cases = json.loads(Path(p).read_text())
                logger.info("Training data from %s: %d cases", p, len(cases))
                data_sources.extend(cases)

    # 2. Public 20 cases (with labels)
    pub_labels = {}
    label_path = Path("/dl2026/dataset/label.jsonl")
    if label_path.exists():
        for line in open(label_path):
            d = json.loads(line)
            pub_labels[d["filename"]] = d["label"]

    pub_cases = []
    tc_dir = Path("/dl2026/dataset/testcases/")
    if tc_dir.exists():
        for tc_file in sorted(glob.glob(str(tc_dir / "tc*.json"))):
            fname = os.path.basename(tc_file)
            if fname in pub_labels:
                steps = json.load(open(tc_file))
                records = verifier._records(steps)
                if records:
                    pub_cases.append({
                        "records": records,
                        "label": pub_labels[fname],
                        "source": "public",
                        "filename": fname,
                    })
        logger.info("Public cases: %d", len(pub_cases))

    # Process all cases through rule engine
    all_examples = []
    rule_stats = Counter()
    tier_stats = Counter()
    agree_stats = Counter()

    # Process spec data
    for case in data_sources:
        records = case.get("records", [])
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue

        label = case["label"]
        # Changed: wrap records in the format the verifier expects
        # Why: verifier.verify_with_trace expects raw steps, not parsed records
        # But _records() was already called on the training data, so we reconstruct
        steps = [{"input": r.get("input", {}), "output": r.get("output", {})} for r in records]
        analysis = get_rule_analysis(verifier, steps)

        example = format_for_training_v3(records, label, analysis)
        if example:
            example["source"] = case.get("source", "spec")
            all_examples.append(example)
            rule_stats[analysis["rule_id"]] += 1
            tier_stats[analysis["tier"]] += 1
            agree_stats[f"{analysis['tier']}_{analysis['prediction'] == label}"] += 1

    # Process public cases (10x upsample for distribution matching)
    PUB_UPSAMPLE = 10
    for case in pub_cases:
        analysis = get_rule_analysis(verifier, [
            {"input": r.get("input", {}), "output": r.get("output", {})}
            for r in case["records"]
        ])
        example = format_for_training_v3(case["records"], case["label"], analysis)
        if example:
            example["source"] = "public"
            example["filename"] = case["filename"]
            for _ in range(PUB_UPSAMPLE):
                all_examples.append(example.copy())

    # Statistics
    logger.info("\n=== RULE DISTRIBUTION ===")
    for rule_id, count in rule_stats.most_common():
        logger.info("  %s: %d", rule_id, count)

    logger.info("\n=== TIER DISTRIBUTION ===")
    for tier, count in tier_stats.most_common():
        logger.info("  %s: %d", tier, count)

    logger.info("\n=== AGREEMENT (rule engine vs gold label) ===")
    for key, count in sorted(agree_stats.items()):
        logger.info("  %s: %d", key, count)

    # Split: train / val / test
    import random
    random.seed(42)
    random.shuffle(all_examples)

    # Keep public cases in both train and val for distribution anchoring
    public_examples = [e for e in all_examples if e.get("source") == "public"]
    spec_examples = [e for e in all_examples if e.get("source") != "public"]

    n_spec = len(spec_examples)
    n_val = min(100, n_spec // 5)
    n_test = min(100, n_spec // 5)
    n_train = n_spec - n_val - n_test

    train_data = spec_examples[:n_train] + public_examples
    val_data = spec_examples[n_train:n_train + n_val]
    test_data = spec_examples[n_train + n_val:]

    random.shuffle(train_data)

    logger.info("\n=== SPLIT ===")
    logger.info("  Train: %d (spec=%d, public=%d)", len(train_data),
                sum(1 for e in train_data if e.get("source") != "public"),
                sum(1 for e in train_data if e.get("source") == "public"))
    logger.info("  Val: %d", len(val_data))
    logger.info("  Test: %d", len(test_data))

    # Save
    out_dir = Path("/workspace/team6/training_data")
    out_dir.mkdir(exist_ok=True)

    def save_split(data, name):
        path = out_dir / f"uncertainty_{name}.json"
        json.dump(data, open(path, "w"), indent=1, default=str)
        logger.info("Saved %s: %d examples → %s", name, len(data), path)

    save_split(train_data, "train")
    save_split(val_data, "val")
    save_split(test_data, "test")

    # Also save stats for analysis
    stats = {
        "total": len(all_examples),
        "rule_distribution": dict(rule_stats),
        "tier_distribution": dict(tier_stats),
        "agreement": dict(agree_stats),
        "splits": {"train": len(train_data), "val": len(val_data), "test": len(test_data)},
    }
    json.dump(stats, open(out_dir / "uncertainty_stats.json", "w"), indent=2)
    logger.info("\nDone. Stats saved to %s", out_dir / "uncertainty_stats.json")


if __name__ == "__main__":
    main()
