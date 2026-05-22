"""Evaluate all 3 mutation adapters on public 20 side-by-side."""
import os, sys, json, math, glob, gc, logging
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
sys.path.insert(0, "/workspace/team6/team6-opal-verifier")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from src.solver import StatefulOpalVerifier
from tools.training.finetune_lora_v2 import format_trajectory_rich

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("eval_3adapters")

ADAPTERS = {
    "mutation_4b":   "/workspace/team6/adapters/mutation_4b/final",
    "mutation_15ep": "/workspace/team6/adapters/mutation_15ep/final",
    "mutation_470":  "/workspace/team6/adapters/mutation_470/final",
}

# Load public 20 labels
pub_labels = {}
for line in open("/dl2026/dataset/label.jsonl"):
    d = json.loads(line)
    pub_labels[d["filename"]] = d["label"]

# Prepare test cases once
verifier = StatefulOpalVerifier()
test_cases = []
for f in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
    fname = os.path.basename(f)
    steps = json.load(open(f))
    gold = pub_labels.get(fname, "?")
    if gold == "?":
        continue
    records = verifier._records(steps)
    if not records:
        continue
    prompt = format_trajectory_rich(records)
    test_cases.append({"fname": fname, "gold": gold, "prompt": prompt})

logger.info("Prepared %d test cases", len(test_cases))

# System prompt
SYS_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory with session state, "
    "determine if the final response is consistent with the "
    "specification. Answer exactly: pass or fail"
)

# Tokenizer (shared)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-4B", trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

# Results table
all_results = {}

for adapter_name, adapter_path in ADAPTERS.items():
    if not os.path.exists(adapter_path):
        logger.warning("SKIP %s: %s not found", adapter_name, adapter_path)
        continue

    logger.info("=== Evaluating: %s ===", adapter_name)

    # Load base + adapter
    base_model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3.5-4B", torch_dtype=torch.float16,
        device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()

    results = []
    correct = 0
    for tc in test_cases:
        messages = [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": tc["prompt"]},
        ]
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False)
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]

        p_l = logits[pass_id].item()
        f_l = logits[fail_id].item()
        mx = max(p_l, f_l)
        p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
        pred = "fail" if p_fail > 0.5 else "pass"
        ok = pred == tc["gold"]
        if ok:
            correct += 1
        results.append({
            "fname": tc["fname"],
            "gold": tc["gold"],
            "pred": pred,
            "p_fail": round(p_fail, 4),
            "correct": ok,
        })

    all_results[adapter_name] = results
    logger.info("%s: %d/%d (%.1f%%)", adapter_name, correct, len(test_cases),
                correct / max(len(test_cases), 1) * 100)

    # Free memory
    del model, base_model
    gc.collect()
    torch.cuda.empty_cache()

# === Side-by-side comparison ===
logger.info("\n" + "=" * 80)
logger.info("SIDE-BY-SIDE COMPARISON")
logger.info("=" * 80)

header = f"{'TC':<12} {'Gold':<6}"
for name in ADAPTERS:
    if name in all_results:
        header += f" | {name:<20}"
logger.info(header)
logger.info("-" * len(header))

for i, tc in enumerate(test_cases):
    row = f"{tc['fname']:<12} {tc['gold']:<6}"
    for name in ADAPTERS:
        if name not in all_results:
            continue
        r = all_results[name][i]
        mark = "OK" if r["correct"] else "XX"
        row += f" | {r['pred']:<5} p_f={r['p_fail']:.3f} {mark}"
    logger.info(row)

logger.info("-" * len(header))
summary = f"{'TOTAL':<12} {'':6}"
for name in ADAPTERS:
    if name not in all_results:
        continue
    c = sum(1 for r in all_results[name] if r["correct"])
    t = len(all_results[name])
    summary += f" | {c}/{t} ({c/t*100:.0f}%)             "
logger.info(summary)

# Save detailed results
out_path = "/workspace/team6/eval_3adapters_results.json"
json.dump(all_results, open(out_path, "w"), indent=2)
logger.info("Saved to %s", out_path)
logger.info("COMPLETE")
