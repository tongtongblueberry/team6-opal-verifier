# Changed: evaluate LoRA-finetuned model on test sets.
# Why: need to measure if LoRA fine-tuning improves fail recall over zero-shot baseline.
# Evaluates on: (1) public 20 cases, (2) 252 synthetic DEFAULT_PASS cases.

from __future__ import annotations
import json, sys, os, time, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_lora_model(base_model: str, adapter_path: str):
    """Load base model + LoRA adapter for inference."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    logger.info("Loading tokenizer from %s...", adapter_path)
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info("Loading base model %s...", base_model)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    logger.info("Loading LoRA adapter from %s...", adapter_path)
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return model, tokenizer


def _get_format_fn(version: str):
    """Return the appropriate format function for the given version."""
    if version == "v2":
        from tools.finetune_lora_v2 import format_trajectory_rich
        return format_trajectory_rich, (
            "You are a TCG/Opal SSD protocol compliance verifier. "
            "Given a command-response trajectory with session state, "
            "determine if the final response is consistent with the specification. "
            "Answer exactly: pass or fail"
        )
    else:
        from src.embedding_classifier import format_trajectory_for_embedding
        def fmt_v1(records):
            prompt = format_trajectory_for_embedding(records)
            prompt = prompt.rstrip("(").rstrip()
            if prompt.endswith("Answer:"):
                prompt = prompt[:-len("Answer:")].rstrip()
            return prompt
        return fmt_v1, (
            "You are a TCG/Opal protocol compliance checker. Given a command-response "
            "trajectory, determine if the final response is consistent with the "
            "specification. Answer with exactly one word: pass or fail"
        )


# Changed: support v1/v2 format selection via global variable.
_FORMAT_VERSION = "v1"
_MAX_LENGTH = 512


def predict_single(model, tokenizer, records: list, max_new_tokens: int = 32) -> str:
    """Predict pass/fail for a single trajectory using the LoRA model."""
    import torch

    fmt_fn, sys_prompt = _get_format_fn(_FORMAT_VERSION)
    prompt = fmt_fn(records)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=_MAX_LENGTH)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.pad_token_id,
        )

    # Decode only the generated tokens (not the prompt)
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip().lower()

    # Extract pass/fail from the answer
    if "fail" in answer:
        return "fail"
    elif "pass" in answer:
        return "pass"
    else:
        logger.warning("Ambiguous answer: %r → defaulting to pass", answer)
        return "pass"


def predict_logit(model, tokenizer, records: list) -> tuple[str, float, float]:
    """Predict pass/fail using logit scoring (faster than generation)."""
    import torch

    fmt_fn, sys_prompt = _get_format_fn(_FORMAT_VERSION)
    prompt = fmt_fn(records)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=_MAX_LENGTH)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits[0, -1, :]  # last token logits

    # Get logits for "pass" and "fail" tokens
    pass_ids = tokenizer.encode("pass", add_special_tokens=False)
    fail_ids = tokenizer.encode("fail", add_special_tokens=False)

    pass_logit = logits[pass_ids[0]].item()
    fail_logit = logits[fail_ids[0]].item()

    # Softmax
    import math
    max_l = max(pass_logit, fail_logit)
    p_pass = math.exp(pass_logit - max_l) / (math.exp(pass_logit - max_l) + math.exp(fail_logit - max_l))
    p_fail = 1.0 - p_pass

    pred = "fail" if p_fail > 0.5 else "pass"
    return pred, p_pass, p_fail


def eval_public(model, tokenizer, dataset_root: Path, mode: str = "generate"):
    """Evaluate on public 20 labeled cases."""
    labels = {}
    label_path = dataset_root / "label.jsonl"
    with label_path.open() as f:
        for line in f:
            rec = json.loads(line.strip())
            labels[rec["filename"]] = str(rec["label"]).strip().lower()

    testcase_dir = dataset_root / "testcases"
    results = []
    for path in sorted(testcase_dir.glob("tc*.json")):
        if path.name not in labels:
            continue
        with path.open() as f:
            steps = json.load(f)
        if isinstance(steps, dict) and "records" in steps:
            steps = steps["records"]
        records = [item for item in steps if isinstance(item, dict)]
        if not records:
            continue

        gold = labels[path.name]
        t0 = time.time()
        if mode == "generate":
            pred = predict_single(model, tokenizer, records)
            results.append({"file": path.name, "gold": gold, "pred": pred, "time": time.time() - t0})
        else:
            pred, p_pass, p_fail = predict_logit(model, tokenizer, records)
            results.append({"file": path.name, "gold": gold, "pred": pred,
                           "p_pass": p_pass, "p_fail": p_fail, "time": time.time() - t0})

    return results


def eval_synthetic(model, tokenizer, test_path: Path, mode: str = "generate", limit: int = 0):
    """Evaluate on synthetic DEFAULT_PASS test set."""
    cases = json.loads(test_path.read_text())
    if limit > 0:
        cases = cases[:limit]

    from src.solver import StatefulOpalVerifier
    verifier = StatefulOpalVerifier()

    results = []
    for i, case in enumerate(cases):
        steps = case["steps"]
        records = verifier._records(steps)
        if not records:
            continue

        gold = case["expected"]
        t0 = time.time()
        if mode == "generate":
            pred = predict_single(model, tokenizer, records)
            results.append({"idx": i, "gold": gold, "pred": pred, "time": time.time() - t0})
        else:
            pred, p_pass, p_fail = predict_logit(model, tokenizer, records)
            results.append({"idx": i, "gold": gold, "pred": pred,
                           "p_pass": p_pass, "p_fail": p_fail, "time": time.time() - t0})

        if (i + 1) % 50 == 0:
            correct = sum(1 for r in results if r["gold"] == r["pred"])
            logger.info("Progress: %d/%d, acc=%.1f%%", i + 1, len(cases), 100 * correct / len(results))

    return results


def print_metrics(results: list, dataset_name: str):
    """Print classification metrics."""
    tp = sum(1 for r in results if r["gold"] == "fail" and r["pred"] == "fail")
    fp = sum(1 for r in results if r["gold"] == "pass" and r["pred"] == "fail")
    fn = sum(1 for r in results if r["gold"] == "fail" and r["pred"] == "pass")
    tn = sum(1 for r in results if r["gold"] == "pass" and r["pred"] == "pass")

    total = len(results)
    correct = tp + tn
    acc = correct / total if total > 0 else 0

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    total_time = sum(r["time"] for r in results)

    print(f"\n=== {dataset_name} ===")
    print(f"accuracy={acc*100:.2f}% ({correct}/{total})")
    print(f"precision(fail)={prec:.4f} recall(fail)={rec:.4f} f1(fail)={f1:.4f}")
    print(f"tp={tp} fp={fp} fn={fn} tn={tn}")
    print(f"time={total_time:.1f}s ({total_time/total:.1f}s/case)")

    # Print mismatches
    mismatches = [r for r in results if r["gold"] != r["pred"]]
    if mismatches:
        print(f"\nMismatches ({len(mismatches)}):")
        for r in mismatches[:20]:
            key = r.get("file", f"idx={r.get('idx', '?')}")
            extra = ""
            if "p_fail" in r:
                extra = f" p_fail={r['p_fail']:.4f}"
            print(f"  {key}: gold={r['gold']} pred={r['pred']}{extra}")


def main():
    global _FORMAT_VERSION, _MAX_LENGTH
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-0.8B")
    parser.add_argument("--adapter-path", default=str(ROOT / "artifacts" / "lora_adapter"))
    parser.add_argument("--dataset-root", default="/dl2026/dataset")
    parser.add_argument("--synthetic-path", default="/workspace/team6/large_dp_test_set.json")
    parser.add_argument("--mode", choices=["generate", "logit"], default="generate")
    parser.add_argument("--synthetic-limit", type=int, default=0,
                       help="Limit synthetic cases (0=all)")
    parser.add_argument("--skip-public", action="store_true")
    parser.add_argument("--skip-synthetic", action="store_true")
    # Changed: add format version and max_length args for v2 support.
    parser.add_argument("--format", choices=["v1", "v2"], default="v1",
                       help="Trajectory format version")
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()

    _FORMAT_VERSION = args.format
    _MAX_LENGTH = args.max_length
    logger.info("Format: %s, max_length: %d", _FORMAT_VERSION, _MAX_LENGTH)

    model, tokenizer = load_lora_model(args.base_model, args.adapter_path)

    if not args.skip_public:
        ds_root = Path(args.dataset_root)
        if ds_root.exists():
            logger.info("Evaluating on public dataset...")
            results = eval_public(model, tokenizer, ds_root, mode=args.mode)
            print_metrics(results, f"PUBLIC ({args.mode} mode)")

    if not args.skip_synthetic:
        syn_path = Path(args.synthetic_path)
        if syn_path.exists():
            logger.info("Evaluating on synthetic test set...")
            results = eval_synthetic(model, tokenizer, syn_path, mode=args.mode,
                                    limit=args.synthetic_limit)
            print_metrics(results, f"SYNTHETIC ({args.mode} mode)")


if __name__ == "__main__":
    main()
