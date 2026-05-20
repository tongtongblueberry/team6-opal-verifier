"""Cycle 0: Baseline diagnostic - measure all metrics on public 20 + val 283."""
import json, sys, math, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from tools.training.finetune_lora_v2 import format_trajectory_rich
from src.solver import StatefulOpalVerifier

# Load model
print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(str(ROOT / "artifacts" / "lora_adapter_v2"), trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-4B", torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
model = PeftModel.from_pretrained(model, str(ROOT / "artifacts" / "lora_adapter_v2"))
model.eval()

SYSTEM_PROMPT = ("You are a TCG/Opal SSD protocol compliance verifier. "
                 "Given a command-response trajectory with session state, "
                 "determine if the final response is consistent with the specification. "
                 "Answer exactly: pass or fail")

verifier = StatefulOpalVerifier()


def get_logits(steps):
    records = verifier._records(steps)
    if not records:
        return None, None, "pass"
    prompt = format_trajectory_rich(records)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
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
    pass_ids = tokenizer.encode("pass", add_special_tokens=False)
    fail_ids = tokenizer.encode("fail", add_special_tokens=False)
    p_l = logits[pass_ids[0]].item()
    f_l = logits[fail_ids[0]].item()
    mx = max(p_l, f_l)
    p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
    pred = "fail" if p_fail > 0.5 else "pass"
    return p_fail, f_l - p_l, pred


# === Public 20 cases ===
print("\n=== PUBLIC 20 CASES ===")
labels = {}
for line in open("/dl2026/dataset/label.jsonl"):
    d = json.loads(line)
    labels[d["filename"]] = d["label"]

pub_results = []
for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
    fname = tc_file.split("/")[-1]
    steps = json.load(open(tc_file))
    gold = labels.get(fname, "?")

    rule_result = verifier.verify_with_trace(steps)
    rule_pred = rule_result["prediction"]

    p_fail, logit_diff, lora_pred = get_logits(steps)

    correct_rule = rule_pred == gold
    correct_lora = lora_pred == gold

    pub_results.append({
        "case": fname, "gold": gold, "rule": rule_pred, "lora": lora_pred,
        "p_fail": p_fail, "logit_diff": logit_diff,
        "rule_correct": correct_rule, "lora_correct": correct_lora
    })

    marker = ""
    if rule_pred != lora_pred:
        marker = " *** OVERRIDE"
    r_ok = "OK" if correct_rule else "ERR"
    l_ok = "OK" if correct_lora else "ERR"
    pf_str = f"{p_fail:.3f}" if p_fail is not None else "N/A"
    print(f"  {fname}: gold={gold} rule={rule_pred}({r_ok}) "
          f"lora={lora_pred}({l_ok}) p_fail={pf_str}{marker}")

rule_acc = sum(1 for r in pub_results if r["rule_correct"]) / len(pub_results)
lora_acc = sum(1 for r in pub_results if r["lora_correct"]) / len(pub_results)
print(f"\nPublic: rule_acc={rule_acc:.1%}, lora_acc={lora_acc:.1%}")

# Confidence analysis
p_fails = [r["p_fail"] for r in pub_results if r["p_fail"] is not None]
print(f"p_fail stats: min={min(p_fails):.3f} max={max(p_fails):.3f} mean={sum(p_fails)/len(p_fails):.3f}")

pub_pass = [r for r in pub_results if r["gold"] == "pass" and r["p_fail"] is not None]
pub_fail = [r for r in pub_results if r["gold"] == "fail" and r["p_fail"] is not None]
print(f"  gold=pass ({len(pub_pass)}): p_fail values = {[round(r['p_fail'],3) for r in pub_pass]}")
print(f"  gold=fail ({len(pub_fail)}): p_fail values = {[round(r['p_fail'],3) for r in pub_fail]}")

# ECE
bins_correct = [0] * 10
bins_count = [0] * 10
for r in pub_results:
    if r["p_fail"] is None:
        continue
    conf = max(r["p_fail"], 1 - r["p_fail"])
    b = min(int(conf * 10), 9)
    bins_count[b] += 1
    bins_correct[b] += 1 if r["lora_correct"] else 0
ece = sum(
    abs(bins_correct[i] / bins_count[i] - (i + 0.5) / 10) * bins_count[i]
    for i in range(10) if bins_count[i] > 0
) / len(pub_results)
print(f"ECE (public): {ece:.3f}")

# Entropy
entropies = []
for r in pub_results:
    if r["p_fail"] is None:
        continue
    p = r["p_fail"]
    if 0 < p < 1:
        ent = -(p * math.log(p) + (1 - p) * math.log(1 - p))
    else:
        ent = 0
    entropies.append(ent)
print(f"Entropy stats: min={min(entropies):.3f} max={max(entropies):.3f} "
      f"mean={sum(entropies)/len(entropies):.3f}")

# === Val 283 cases ===
print("\n=== VAL 283 CASES ===")
val_path = "/workspace/team6/training_data/spec_val.json"
val_data = json.loads(open(val_path).read())
val_results = []
for i, case in enumerate(val_data):
    records = case.get("records", [])
    gold = case["label"]
    if not records:
        continue
    p_fail, logit_diff, lora_pred = get_logits(records)
    val_results.append({"gold": gold, "lora": lora_pred, "p_fail": p_fail,
                        "correct": lora_pred == gold})

val_acc = sum(1 for r in val_results if r["correct"]) / len(val_results)
val_pfails = [r["p_fail"] for r in val_results if r["p_fail"] is not None]
print(f"Val: acc={val_acc:.1%} ({sum(1 for r in val_results if r['correct'])}/{len(val_results)})")
print(f"p_fail stats: min={min(val_pfails):.3f} max={max(val_pfails):.3f} "
      f"mean={sum(val_pfails)/len(val_pfails):.3f}")

val_pass = [r["p_fail"] for r in val_results if r["gold"] == "pass" and r["p_fail"] is not None]
val_fail = [r["p_fail"] for r in val_results if r["gold"] == "fail" and r["p_fail"] is not None]
print(f"  gold=pass ({len(val_pass)}): mean_pfail={sum(val_pass)/len(val_pass):.3f} (should be low)")
print(f"  gold=fail ({len(val_fail)}): mean_pfail={sum(val_fail)/len(val_fail):.3f} (should be high)")

# === METRICS SUMMARY ===
print("\n=== METRICS SUMMARY ===")
print(f"M1 Val-Public Gap: val={val_acc:.1%} pub={lora_acc:.1%} gap={val_acc-lora_acc:.1%}")
print(f"M2 ECE (public): {ece:.3f}")
print(f"M3 Mean Entropy (public): {sum(entropies)/len(entropies):.3f}")
overrides = sum(1 for r in pub_results if r["rule"] != r["lora"])
override_correct = sum(1 for r in pub_results if r["rule"] != r["lora"] and r["lora_correct"])
print(f"M4 Override accuracy: {override_correct}/{overrides}")
print(f"M5 Confidence: pass_mean={sum(r['p_fail'] for r in pub_pass)/len(pub_pass):.3f} "
      f"fail_mean={sum(r['p_fail'] for r in pub_fail)/len(pub_fail):.3f}")
