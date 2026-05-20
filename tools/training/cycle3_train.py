"""Cycle 3: Label smoothing (0.1) + higher dropout (0.2) to reduce overconfidence.
Why: Cycle 2 showed p_fail > 0.97 on misclassified pass cases.
Model is overconfident on long trajectories with Activate patterns.
Label smoothing prevents extreme logit values, dropout adds regularization.
"""
import sys, json, math, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("cycle3")

from tools.training.finetune_lora_v2 import format_for_training_v2, format_trajectory_rich
from src.solver import StatefulOpalVerifier
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType
import gc, time

# Config
LR = 1e-3
RANK = 16
ALPHA = 32
DROPOUT = 0.2  # Changed: increased from 0.05. Why: reduce overconfidence on OOD patterns.
MAX_LEN = 1024
EPOCHS = 5
BATCH = 8
LABEL_SMOOTHING = 0.1  # Changed: added label smoothing. Why: prevent extreme logit values.

# Load augmented data
train_path = Path("/workspace/team6/training_data/spec_train_augmented.json")
all_cases = json.loads(train_path.read_text())
logger.info("Training data: %d cases", len(all_cases))

train_data = []
for case in all_cases:
    records = case.get("records", [])
    if isinstance(records, list):
        records = [r for r in records if isinstance(r, dict)]
    if not records:
        continue
    train_data.append(format_for_training_v2(records, case["label"]))

# Build dataset
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-4B", trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

IGNORE_INDEX = -100

class MaskedDS(torch.utils.data.Dataset):
    def __init__(self):
        self.examples = []
        for item in train_data:
            try:
                full = tokenizer.apply_chat_template(
                    item["messages"], tokenize=False, add_generation_prompt=False, enable_thinking=False)
            except TypeError:
                full = tokenizer.apply_chat_template(
                    item["messages"], tokenize=False, add_generation_prompt=False)
            try:
                prompt = tokenizer.apply_chat_template(
                    item["messages"][:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                prompt = tokenizer.apply_chat_template(
                    item["messages"][:-1], tokenize=False, add_generation_prompt=True)
            full_enc = tokenizer(full, truncation=True, max_length=MAX_LEN, padding="max_length", return_tensors="pt")
            prompt_enc = tokenizer(prompt, truncation=True, max_length=MAX_LEN, return_tensors="pt")
            ids = full_enc["input_ids"].squeeze()
            mask = full_enc["attention_mask"].squeeze()
            labels = ids.clone()
            plen = prompt_enc["input_ids"].shape[1]
            if plen < MAX_LEN:
                labels[:plen] = IGNORE_INDEX
            labels[mask == 0] = IGNORE_INDEX
            self.examples.append({"input_ids": ids, "attention_mask": mask, "labels": labels})
    def __len__(self): return len(self.examples)
    def __getitem__(self, i): return self.examples[i]

logger.info("Building dataset...")
dataset = MaskedDS()
logger.info("Dataset: %d examples", len(dataset))

# Model
logger.info("Loading model...")
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-4B", torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
lora_cfg = LoraConfig(
    task_type=TaskType.CAUSAL_LM, r=RANK, lora_alpha=ALPHA,
    lora_dropout=DROPOUT, target_modules=["q_proj", "v_proj", "k_proj", "o_proj"])
model = get_peft_model(model, lora_cfg)
model.gradient_checkpointing_enable()
model.enable_input_require_grads()
logger.info("Trainable params: %d", sum(p.numel() for p in model.parameters() if p.requires_grad))

# Train with label smoothing
training_args = TrainingArguments(
    output_dir="/workspace/team6/sweep_runs/cycle3",
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH,
    learning_rate=LR,
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    optim="adamw_torch",
    logging_steps=50,
    save_strategy="no",
    fp16=True,
    gradient_checkpointing=True,
    report_to="none",
    label_smoothing_factor=LABEL_SMOOTHING,  # Changed: 0.1 label smoothing
)

trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
t0 = time.time()
result = trainer.train()
logger.info("Train done: %.0fs, loss=%.4f", time.time() - t0, result.training_loss)

# Save adapter
adapter_path = str(ROOT / "artifacts" / "lora_adapter_v2")
model.save_pretrained(adapter_path)
tokenizer.save_pretrained(adapter_path)
logger.info("SAVED adapter to %s", adapter_path)

# Evaluate on val
logger.info("=== VAL EVALUATION ===")
val_data = json.loads(open("/workspace/team6/training_data/spec_val.json").read())
verifier = StatefulOpalVerifier()
SYSTEM_PROMPT = ("You are a TCG/Opal SSD protocol compliance verifier. "
                 "Given a command-response trajectory with session state, "
                 "determine if the final response is consistent with the specification. "
                 "Answer exactly: pass or fail")

model.eval()
tp = fp = fn = tn = 0
for case in val_data:
    records = case.get("records", [])
    gold = case["label"]
    if not records: continue
    prompt = format_trajectory_rich(records)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    try:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_LEN)
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
    if gold == "fail" and pred == "fail": tp += 1
    elif gold == "pass" and pred == "fail": fp += 1
    elif gold == "fail" and pred == "pass": fn += 1
    else: tn += 1

total = tp + fp + fn + tn
logger.info("Val: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f | tp=%d fp=%d fn=%d tn=%d",
            (tp+tn)/total*100, tp/(tp+fp) if tp+fp else 0, tp/(tp+fn) if tp+fn else 0,
            2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0, tp, fp, fn, tn)

# Public diagnostic
logger.info("=== PUBLIC 20 DIAGNOSTIC ===")
pub_labels = {}
for line in open("/dl2026/dataset/label.jsonl"):
    d = json.loads(line)
    pub_labels[d["filename"]] = d["label"]

correct = 0
total_pub = 0
for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
    fname = tc_file.split("/")[-1]
    steps = json.load(open(tc_file))
    gold = pub_labels.get(fname, "?")
    records = verifier._records(steps)
    if not records:
        lora_pred, p_fail = "pass", 0.5
    else:
        prompt = format_trajectory_rich(records)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        try:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_LEN)
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
    ok = lora_pred == gold
    if ok: correct += 1
    total_pub += 1
    logger.info("  %s: gold=%s lora=%s p_fail=%.3f %s", fname, gold, lora_pred, p_fail, "OK" if ok else "ERR")

logger.info("Public: %d/%d (%.1f%%)", correct, total_pub, correct/total_pub*100)

# Cleanup
del model, trainer, dataset
gc.collect()
torch.cuda.empty_cache()
