"""Conformal Prediction calibration for LoRA-rule engine deferral.

Changed: implements training-free conformal prediction to decide when to trust
the LoRA model vs. the rule engine.
Why: manual thresholds (0.15/0.90) are arbitrary. Conformal prediction provides
statistically valid prediction sets with guaranteed coverage.

Paper: "No Need for 'Learning' to Defer?" (arXiv 2509.12573)
Key idea: use conformal prediction sets to identify when the LLM is confident
enough to override the rule engine.

Pipeline:
1. Run LoRA model on calibration set (val data) → collect p_fail scores
2. Compute nonconformity scores per class
3. At inference: check if prediction set contains one class → confident → use LLM
4. If prediction set contains both classes → uncertain → keep rule engine

Usage: python tools/eval/conformal_calibration.py
  (Run after training to calibrate thresholds, before submission)
"""
import sys, json, math, logging, os
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("conformal")


def compute_conformal_thresholds(cal_scores, alpha=0.10):
    """Compute conformal prediction thresholds from calibration scores.

    Changed: implements split conformal prediction for binary classification.
    Why: provides (1-alpha) coverage guarantee — the true label is in the
    prediction set with probability >= 1-alpha.

    Args:
        cal_scores: list of (p_fail, gold_label) tuples from calibration set
        alpha: significance level (0.10 = 90% coverage)

    Returns:
        dict with 'pass_threshold' and 'fail_threshold' — if p_fail is between
        these thresholds, the prediction set contains both classes (uncertain).
    """
    # Nonconformity scores: how "wrong" is the model for each class?
    # For class "fail" (label=1): score = 1 - p_fail (lower p_fail = more wrong)
    # For class "pass" (label=0): score = p_fail (higher p_fail = more wrong)
    pass_scores = []  # nonconformity scores for gold="pass" examples
    fail_scores = []  # nonconformity scores for gold="fail" examples

    for p_fail, gold in cal_scores:
        if gold == "fail":
            fail_scores.append(1.0 - p_fail)  # how much the model "misses" fail
        else:
            pass_scores.append(p_fail)  # how much the model "misses" pass

    if not pass_scores or not fail_scores:
        logger.warning("Not enough calibration data for both classes")
        return {"pass_threshold": 0.5, "fail_threshold": 0.5}

    pass_scores = np.array(sorted(pass_scores))
    fail_scores = np.array(sorted(fail_scores))

    # Quantile for (1-alpha) coverage
    # Changed: use ceil((n+1)(1-alpha))/n quantile per Vovk et al.
    n_pass = len(pass_scores)
    n_fail = len(fail_scores)

    q_pass_idx = min(int(np.ceil((n_pass + 1) * (1 - alpha))), n_pass) - 1
    q_fail_idx = min(int(np.ceil((n_fail + 1) * (1 - alpha))), n_fail) - 1

    q_pass = pass_scores[q_pass_idx]  # threshold for "pass" class
    q_fail = fail_scores[q_fail_idx]  # threshold for "fail" class

    # Interpretation:
    # - Include "pass" in prediction set if p_fail <= q_pass
    # - Include "fail" in prediction set if (1-p_fail) <= q_fail, i.e., p_fail >= 1-q_fail
    # - Both included if: (1-q_fail) <= p_fail <= q_pass → UNCERTAIN
    # - Only "pass" if: p_fail <= 1-q_fail → CONFIDENT PASS
    # - Only "fail" if: p_fail >= q_pass → CONFIDENT FAIL

    pass_threshold = 1.0 - q_fail  # below this → confident pass
    fail_threshold = q_pass  # above this → confident fail

    return {
        "pass_threshold": float(pass_threshold),
        "fail_threshold": float(fail_threshold),
        "q_pass": float(q_pass),
        "q_fail": float(q_fail),
        "alpha": alpha,
        "n_pass": n_pass,
        "n_fail": n_fail,
    }


def calibrate_from_val(val_results_path, alpha=0.10):
    """Load validation results and compute conformal thresholds."""
    results = json.loads(Path(val_results_path).read_text())

    cal_scores = []
    for r in results:
        p_fail = r.get("p_fail", 0.5)
        gold = r.get("gold", r.get("expected", "pass"))
        cal_scores.append((p_fail, gold))

    logger.info("Calibration data: %d examples (pass=%d, fail=%d)",
                len(cal_scores),
                sum(1 for _, g in cal_scores if g == "pass"),
                sum(1 for _, g in cal_scores if g == "fail"))

    thresholds = compute_conformal_thresholds(cal_scores, alpha)
    logger.info("Conformal thresholds (alpha=%.2f):", alpha)
    logger.info("  pass_threshold (below → confident pass): %.4f", thresholds["pass_threshold"])
    logger.info("  fail_threshold (above → confident fail): %.4f", thresholds["fail_threshold"])

    # Coverage analysis
    in_set = 0
    confident = 0
    for p_fail, gold in cal_scores:
        if p_fail <= thresholds["pass_threshold"]:
            pred_set = {"pass"}
        elif p_fail >= thresholds["fail_threshold"]:
            pred_set = {"fail"}
        else:
            pred_set = {"pass", "fail"}

        if gold in pred_set:
            in_set += 1
        if len(pred_set) == 1:
            confident += 1

    coverage = in_set / len(cal_scores) if cal_scores else 0
    efficiency = confident / len(cal_scores) if cal_scores else 0
    logger.info("  Coverage: %.1f%% (target: %.1f%%)", coverage * 100, (1 - alpha) * 100)
    logger.info("  Efficiency (single-class sets): %.1f%%", efficiency * 100)

    return thresholds


def apply_conformal_deferral(p_fail, rule_pred, thresholds):
    """Apply conformal prediction to decide LLM vs rule engine.

    Returns:
        (final_prediction, source) — source is 'lora' or 'rule'
    """
    pass_thresh = thresholds["pass_threshold"]
    fail_thresh = thresholds["fail_threshold"]

    if p_fail < pass_thresh:
        return "pass", "lora"
    elif p_fail > fail_thresh:
        return "fail", "lora"
    else:
        return rule_pred, "rule"  # uncertain → defer to rule engine


def main():
    """Run calibration on public 20 or validation set."""
    import glob
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    from tools.training.finetune_lora_v2 import format_trajectory_rich
    from src.solver import StatefulOpalVerifier

    logger.info("=" * 60)
    logger.info("CONFORMAL PREDICTION CALIBRATION")
    logger.info("=" * 60)

    # Try to load existing val results
    val_results_path = Path("/workspace/team6/uncertainty_results.json")
    if val_results_path.exists():
        results = json.loads(val_results_path.read_text())
        if "val_results" in results:
            thresholds = calibrate_from_val(results["val_results"])
            json.dump(thresholds, open("/workspace/team6/conformal_thresholds.json", "w"), indent=2)
            logger.info("Thresholds saved to /workspace/team6/conformal_thresholds.json")
            return thresholds

    # Otherwise, run model on public 20 to calibrate
    logger.info("No val results found. Running LoRA model on public 20 for calibration...")

    adapter_path = str(ROOT / "artifacts" / "lora_adapter_v3")
    if not Path(adapter_path).exists():
        adapter_path = str(ROOT / "artifacts" / "lora_adapter_v2")
    if not Path(adapter_path).exists():
        logger.error("No adapter found!")
        return None

    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B"),
        torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()

    verifier = StatefulOpalVerifier()
    pub_labels = {}
    for line in open("/dl2026/dataset/label.jsonl"):
        d = json.loads(line)
        pub_labels[d["filename"]] = d["label"]

    SYSTEM_PROMPT = (
        "You are a TCG/Opal SSD protocol compliance verifier. "
        "Given a command-response trajectory with session state, "
        "determine if the final response is consistent with the specification. "
        "Answer exactly: pass or fail"
    )

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    cal_scores = []
    for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
        fname = os.path.basename(tc_file)
        steps = json.load(open(tc_file))
        gold = pub_labels.get(fname, "?")
        records = verifier._records(steps)

        if not records:
            continue

        prompt = format_trajectory_rich(records)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]
        p_l = logits[pass_id].item()
        f_l = logits[fail_id].item()
        mx = max(p_l, f_l)
        p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))

        cal_scores.append((p_fail, gold))
        logger.info("  %s: gold=%s p_fail=%.4f", fname, gold, p_fail)

    # Compute thresholds for multiple alpha values
    for alpha in [0.05, 0.10, 0.15, 0.20]:
        thresholds = compute_conformal_thresholds(cal_scores, alpha)
        logger.info("\nalpha=%.2f: pass<%.4f, fail>%.4f",
                    alpha, thresholds["pass_threshold"], thresholds["fail_threshold"])

    # Save best (alpha=0.10)
    best_thresholds = compute_conformal_thresholds(cal_scores, 0.10)
    json.dump(best_thresholds, open("/workspace/team6/conformal_thresholds.json", "w"), indent=2)
    logger.info("\nSaved alpha=0.10 thresholds to /workspace/team6/conformal_thresholds.json")

    del model, tokenizer
    import gc
    gc.collect()
    torch.cuda.empty_cache()

    return best_thresholds


if __name__ == "__main__":
    main()
