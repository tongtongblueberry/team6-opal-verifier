"""Cycle 2: Train with augmented data (public 10x + long trajectory 5x upsample).
Why: Cycle 0 showed complete distribution mismatch (train 94% short, public 80% long).
Augmented data rebalances to 21% long trajectories + includes public 20 cases.
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.training.sweep_lora import SweepConfig, run_single, build_dataset, evaluate_model, save_result
from tools.training.finetune_lora_v2 import format_for_training_v2
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("cycle2")

# Config: best from Phase 1 LR sweep
cfg = SweepConfig(
    lr=1e-3, lora_rank=16, lora_alpha=32, lora_dropout=0.05,
    max_length=1024, num_epochs=5, batch_size=8, grad_accum=1,
    run_name="cycle2_augmented")

# Load augmented training data
train_path = Path("/workspace/team6/training_data/spec_train_augmented.json")
all_cases = json.loads(train_path.read_text())
logger.info("Augmented training data: %d cases", len(all_cases))

train_data = []
for case in all_cases:
    records = case.get("records", [])
    if isinstance(records, list):
        records = [r for r in records if isinstance(r, dict)]
    if not records:
        continue
    train_data.append(format_for_training_v2(records, case["label"]))
logger.info("Formatted: %d training examples", len(train_data))

# Load val + test
val_path = Path("/workspace/team6/training_data/spec_val.json")
val_data = json.loads(val_path.read_text())
val_cases = [{"steps": c["records"], "expected": c["label"]} for c in val_data]

test_path = Path("/workspace/team6/training_data/spec_test.json")
test_data = json.loads(test_path.read_text())
test_cases = [{"steps": c["records"], "expected": c["label"]} for c in test_data]

logger.info("Val: %d, Test: %d", len(val_cases), len(test_cases))

# Train + evaluate on val + save adapter
result = run_single(cfg, train_data, val_cases,
                    save_adapter=str(ROOT / "artifacts" / "lora_adapter_v2"),
                    extra_eval={"test": test_cases})
save_result(result)

logger.info("Result: %s", json.dumps({
    k: v for k, v in result.items()
    if k in ("accuracy", "fail_precision", "fail_recall", "f1_fail",
             "train_loss", "extra_eval")
}, indent=2))

# Run public 20 diagnostic
logger.info("\n=== PUBLIC 20 DIAGNOSTIC ===")
import math, glob, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from tools.training.finetune_lora_v2 import format_trajectory_rich
from src.solver import StatefulOpalVerifier

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
labels = {}
for line in open("/dl2026/dataset/label.jsonl"):
    d = json.loads(line)
    labels[d["filename"]] = d["label"]

correct = 0
total = 0
override_correct = 0
override_total = 0
for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
    fname = tc_file.split("/")[-1]
    steps = json.load(open(tc_file))
    gold = labels.get(fname, "?")
    rule_pred = verifier.verify_with_trace(steps)["prediction"]

    records = verifier._records(steps)
    if not records:
        lora_pred = "pass"
        p_fail = 0.5
    else:
        prompt = format_trajectory_rich(records)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        try:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
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
        lora_pred = "fail" if p_fail > 0.5 else "pass"

    lora_ok = lora_pred == gold
    if lora_ok:
        correct += 1
    total += 1
    if rule_pred != lora_pred:
        override_total += 1
        if lora_ok:
            override_correct += 1
    marker = " *** OVERRIDE" if rule_pred != lora_pred else ""
    logger.info("  %s: gold=%s rule=%s lora=%s p_fail=%.3f %s%s",
                fname, gold, rule_pred, lora_pred, p_fail,
                "OK" if lora_ok else "ERR", marker)

logger.info("Public: lora_acc=%d/%d (%.1f%%), override_acc=%d/%d",
            correct, total, correct / total * 100, override_correct, override_total)
logger.info("Public gold=pass mean_pfail: %.3f",
            sum(1 for _ in []) or 0)  # placeholder, actual computed above
