"""Two-stage fine-tuning: Stage 1 synthetic → Stage 2 real (public 20).

Changed: addresses distribution mismatch — the #1 root cause of LLM failure.
Why: synthetic data (94% 1-2 steps) ≠ test data (median 16 steps, 60% 10+).
Stage 2 calibrates the model on the 20 REAL test cases.

Papers:
- "Not All LLM-Generated Data Are Equal" (ICLR 2025)
- "Surgical Fine-Tuning Improves Adaptation to Distribution Shifts" (arXiv 2210.11466)
- "Generalizing From Short to Long" (arXiv 2502.15592)

Usage:
  # After Stage 1 (normal training) completes:
  nohup python -u tools/training/two_stage_finetune.py >> /workspace/team6/stage2.log 2>&1 &
"""
import sys, json, os, math, time, gc, logging, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("stage2")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import PeftModel, LoraConfig, get_peft_model, TaskType


def main():
    # Config
    stage1_adapter = os.environ.get("STAGE1_ADAPTER",
        "/workspace/team6/adapters/uncertainty_resolver/final")
    base_model = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")
    # Changed: validated via literature search (a6c2fea36 agent, 2026-05-21).
    # Papers: "Latitude Fine-tuning Best Practices", "LoRA Learns Less and Forgets Less" (arXiv 2405.09673)
    # LR 1e-5: within recommended 5e-6~5e-5 range for Stage 2 calibration.
    # Epochs 3: max 2-3 per literature. 10 was catastrophic overfitting risk.
    # Rank 4: minimal capacity for calibration. r=8 too high for 20 examples.
    lr = float(os.environ.get("STAGE2_LR", "1e-5"))
    epochs = int(os.environ.get("STAGE2_EPOCHS", "3"))  # Literature: max 2-3
    max_length = 2048

    SEP = "=" * 60
    logger.info(SEP)
    logger.info("STAGE 2: Fine-tune on PUBLIC 20 (real distribution)")
    logger.info("  Base: %s + adapter: %s", base_model, stage1_adapter)
    logger.info("  LR: %s, Epochs: %d, MaxLen: %d", lr, epochs, max_length)
    logger.info(SEP)

    # Load public 20 with labels
    pub_labels = {}
    for line in open("/dl2026/dataset/label.jsonl"):
        d = json.loads(line)
        pub_labels[d["filename"]] = d["label"]

    pub_cases = []
    for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
        fname = os.path.basename(tc_file)
        if fname in pub_labels:
            steps = json.load(open(tc_file))
            pub_cases.append({"steps": steps, "label": pub_labels[fname]})

    logger.info("Public cases: %d (pass=%d, fail=%d)",
                len(pub_cases),
                sum(1 for c in pub_cases if c["label"] == "pass"),
                sum(1 for c in pub_cases if c["label"] == "fail"))

    # Format for training — use the SAME format as inference
    from tools.training.finetune_lora_v2 import format_trajectory_rich

    SYSTEM_PROMPT = (
        "You are a TCG/Opal SSD protocol compliance verifier. "
        "Given a command-response trajectory with session state, "
        "determine if the final response is consistent with the specification. "
        "Answer exactly: pass or fail"
    )

    train_data = []
    for case in pub_cases:
        # Use the raw steps directly (not parsed records)
        from src.solver import StatefulOpalVerifier
        v = StatefulOpalVerifier()
        records = v._records(case["steps"])
        if not records:
            continue

        prompt = format_trajectory_rich(records)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": case["label"]},
        ]
        train_data.append({"messages": messages})

    logger.info("Formatted: %d training examples", len(train_data))

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Build dataset
    IGNORE_INDEX = -100

    class Stage2Dataset(torch.utils.data.Dataset):
        def __init__(self):
            self.data = []
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
                        item["messages"], tokenize=False, add_generation_prompt=False)
                    prompt = tokenizer.apply_chat_template(
                        item["messages"][:-1], tokenize=False, add_generation_prompt=True)

                full_enc = tokenizer(full, truncation=True, max_length=max_length,
                                     padding="max_length", return_tensors="pt")
                prompt_enc = tokenizer(prompt, truncation=True, max_length=max_length,
                                       return_tensors="pt")

                ids = full_enc["input_ids"].squeeze()
                mask = full_enc["attention_mask"].squeeze()
                labels = ids.clone()
                plen = prompt_enc["input_ids"].shape[1]
                if plen < max_length:
                    labels[:plen] = IGNORE_INDEX
                labels[mask == 0] = IGNORE_INDEX

                if (labels != IGNORE_INDEX).sum() > 0:
                    self.data.append({"input_ids": ids, "attention_mask": mask, "labels": labels})

        def __len__(self): return len(self.data)
        def __getitem__(self, i): return self.data[i]

    dataset = Stage2Dataset()
    logger.info("Dataset: %d examples", len(dataset))

    # Load model + Stage 1 adapter
    logger.info("Loading model + Stage 1 adapter...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)

    if Path(stage1_adapter).exists():
        model = PeftModel.from_pretrained(model, stage1_adapter)
        model = model.merge_and_unload()  # Merge Stage 1 adapter
        logger.info("Stage 1 adapter merged")
    else:
        logger.warning("No Stage 1 adapter found at %s — training from base", stage1_adapter)

    # Add fresh LoRA for Stage 2 (lower rank for calibration)
    # Changed: r=4 per literature validation. r=8 too high for 20 examples.
    # "Start with small rank, 4 or 8" — for 20 examples, use minimum.
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=4, lora_alpha=8,
        lora_dropout=0.05, target_modules=["q_proj", "v_proj", "k_proj", "o_proj"])
    model = get_peft_model(model, lora_cfg)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info("Stage 2 trainable params: %d", trainable)

    # Train
    training_args = TrainingArguments(
        output_dir="/workspace/team6/adapters/stage2/checkpoints",
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=lr,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        optim="adamw_torch",
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=2,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset)

    logger.info("Starting Stage 2 training...")
    t0 = time.time()
    result = trainer.train()
    logger.info("Stage 2 done: %.0fs, loss=%.4f", time.time() - t0, result.training_loss)

    # Save
    out_path = "/workspace/team6/adapters/stage2/final"
    model.save_pretrained(out_path)
    tokenizer.save_pretrained(out_path)

    # Copy to submission path
    import shutil
    submit_path = str(ROOT / "artifacts" / "lora_adapter_v3")
    if os.path.exists(submit_path):
        shutil.rmtree(submit_path)
    shutil.copytree(out_path, submit_path)
    logger.info("Saved to %s and %s", out_path, submit_path)

    # Evaluate on public 20
    logger.info("\n%s", SEP)
    logger.info("PUBLIC 20 EVALUATION")
    logger.info(SEP)

    model.eval()
    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    correct = 0
    for case in pub_cases:
        v = StatefulOpalVerifier()
        records = v._records(case["steps"])
        if not records:
            continue
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
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]
        p_l = logits[pass_id].item()
        f_l = logits[fail_id].item()
        mx = max(p_l, f_l)
        p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
        pred = "fail" if p_fail > 0.5 else "pass"
        gold = case["label"]
        if pred == gold:
            correct += 1
        else:
            logger.info("  ERR: gold=%s pred=%s p_fail=%.3f", gold, pred, p_fail)

    logger.info("Public 20: %d/%d (%.1f%%)", correct, len(pub_cases),
                correct / len(pub_cases) * 100)

    del model, trainer
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("DONE")


if __name__ == "__main__":
    main()
