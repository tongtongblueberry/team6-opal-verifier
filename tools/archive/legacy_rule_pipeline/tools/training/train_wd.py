"""4B mutation LoRA with weight decay + label smoothing.
Key changes vs mutation_4b (85% best):
  - weight_decay=0.05 (was 0.0) — L2 regularization for overfitting prevention
  - label_smoothing_factor=0.1 — soften targets to prevent overconfident logits
  - Uses 470 mutation cases (more data)
  - 5 epochs (proven sweet spot, 15ep caused catastrophic overfitting)
"""
import os, sys, json, math, time, gc, glob, logging
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
sys.path.insert(0, "/workspace/team6/team6-opal-verifier")

from tools.training.finetune_lora_v2 import format_for_training_v2, format_trajectory_rich
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("train_wd")

# --- Config ---
MUTATION_DATA = "/workspace/team6/training_data/mutation_cases.json"
ADAPTER_OUT = "/workspace/team6/adapters/mutation_wd"
BASE_MODEL = "Qwen/Qwen3.5-4B"
NUM_EPOCHS = 5
BATCH_SIZE = 2
GRAD_ACCUM = 4
LR = 1e-3
WEIGHT_DECAY = 0.05       # Changed: was 0.0
LABEL_SMOOTHING = 0.1     # Changed: was 0.0
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.1
MAX_SEQ_LEN = 2048
WARMUP_RATIO = 0.05
MAX_GRAD_NORM = 1.0       # Explicit (same as default)

# --- Data ---
data = json.load(open(MUTATION_DATA))
logger.info("Loaded %d mutation cases", len(data))

train_data = []
for case in data:
    records = case.get("records", [])
    if isinstance(records, list):
        records = [r for r in records if isinstance(r, dict)]
    if not records:
        continue
    train_data.append(format_for_training_v2(records, case["label"]))
logger.info("Formatted: %d training examples", len(train_data))

# --- Tokenizer ---
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

IGNORE_INDEX = -100


class MutationDataset(torch.utils.data.Dataset):
    def __init__(self):
        self.examples = []
        for item in train_data:
            try:
                full = tokenizer.apply_chat_template(
                    item["messages"], tokenize=False,
                    add_generation_prompt=False, enable_thinking=False)
                prompt = tokenizer.apply_chat_template(
                    item["messages"][:-1], tokenize=False,
                    add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                full = tokenizer.apply_chat_template(
                    item["messages"], tokenize=False,
                    add_generation_prompt=False)
                prompt = tokenizer.apply_chat_template(
                    item["messages"][:-1], tokenize=False,
                    add_generation_prompt=True)
            full_enc = tokenizer(full, truncation=True, max_length=MAX_SEQ_LEN,
                                 padding="max_length", return_tensors="pt")
            prompt_enc = tokenizer(prompt, truncation=True, max_length=MAX_SEQ_LEN,
                                   return_tensors="pt")
            ids = full_enc["input_ids"].squeeze()
            mask = full_enc["attention_mask"].squeeze()
            labels = ids.clone()
            plen = prompt_enc["input_ids"].shape[1]
            if plen < MAX_SEQ_LEN:
                labels[:plen] = IGNORE_INDEX
            labels[mask == 0] = IGNORE_INDEX
            if (labels != IGNORE_INDEX).sum() > 0:
                self.examples.append({
                    "input_ids": ids,
                    "attention_mask": mask,
                    "labels": labels,
                })

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, i):
        return self.examples[i]


dataset = MutationDataset()
logger.info("Dataset: %d examples", len(dataset))

# --- Model ---
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16,
    device_map="auto", trust_remote_code=True)
lora_cfg = LoraConfig(
    task_type=TaskType.CAUSAL_LM, r=LORA_R, lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"])
model = get_peft_model(model, lora_cfg)
model.gradient_checkpointing_enable()
model.enable_input_require_grads()
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
logger.info("Trainable params: %d", trainable)

# --- Training ---
args = TrainingArguments(
    output_dir=f"{ADAPTER_OUT}/checkpoints",
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    weight_decay=WEIGHT_DECAY,                # Changed: L2 regularization
    label_smoothing_factor=LABEL_SMOOTHING,    # Changed: soften targets
    max_grad_norm=MAX_GRAD_NORM,               # Explicit gradient clipping
    warmup_ratio=WARMUP_RATIO,
    lr_scheduler_type="cosine",
    optim="adamw_torch",
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=2,
    fp16=True,
    gradient_checkpointing=True,
    report_to="none",
)

trainer = Trainer(model=model, args=args, train_dataset=dataset)
t0 = time.time()
result = trainer.train()
elapsed = time.time() - t0
logger.info("Training done: %.0fs, loss=%.4f", elapsed, result.training_loss)

# --- Save ---
model.save_pretrained(f"{ADAPTER_OUT}/final")
tokenizer.save_pretrained(f"{ADAPTER_OUT}/final")

import shutil
v3 = "/workspace/team6/team6-opal-verifier/artifacts/lora_adapter_v3"
if os.path.exists(v3):
    shutil.rmtree(v3)
shutil.copytree(f"{ADAPTER_OUT}/final", v3)
logger.info("Saved adapter to %s", f"{ADAPTER_OUT}/final")

# --- Eval on public 20 ---
logger.info("=== PUBLIC 20 EVAL ===")
model.eval()
pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

from src.solver import StatefulOpalVerifier
verifier = StatefulOpalVerifier()
pub_labels = {}
for line in open("/dl2026/dataset/label.jsonl"):
    d = json.loads(line)
    pub_labels[d["filename"]] = d["label"]

correct = 0
total = 0
for f in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
    fname = os.path.basename(f)
    steps = json.load(open(f))
    gold = pub_labels.get(fname, "?")
    if gold == "?":
        continue
    records = verifier._records(steps)
    if not records:
        continue
    total += 1
    prompt = format_trajectory_rich(records)
    messages = [
        {"role": "system", "content": (
            "You are a TCG/Opal SSD protocol compliance verifier. "
            "Given a command-response trajectory with session state, "
            "determine if the final response is consistent with the "
            "specification. Answer exactly: pass or fail")},
        {"role": "user", "content": prompt},
    ]
    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_SEQ_LEN)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits[0, -1, :]
    p_l = logits[pass_id].item()
    f_l = logits[fail_id].item()
    mx = max(p_l, f_l)
    p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
    pred = "fail" if p_fail > 0.5 else "pass"
    if pred == gold:
        correct += 1
    else:
        logger.info("ERR %s: gold=%s pred=%s p_fail=%.3f", fname, gold, pred, p_fail)

logger.info("Public: %d/%d (%.1f%%)", correct, total, correct / max(total, 1) * 100)

del model, trainer
gc.collect()
torch.cuda.empty_cache()
logger.info("COMPLETE")
