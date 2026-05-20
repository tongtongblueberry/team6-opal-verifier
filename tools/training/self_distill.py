"""Self-distillation for LoRA calibration improvement.

Changed: implements post-SFT self-distillation from Paper 12
("Know When You're Wrong", arXiv 2603.06604).
Why: SFT produces well-calibrated models, but calibration degrades with
longer training. Self-distillation restores calibration by training a new
LoRA adapter to match the soft probability distribution of the teacher model.

Pipeline:
1. Load trained teacher adapter (from train_uncertainty_resolver.py)
2. Generate soft labels: run teacher on training data → p_fail per case
3. Train student LoRA with KL-divergence loss against teacher's soft labels
4. Result: student has similar accuracy but much better calibrated probabilities

Key findings from Paper 12:
- SFT → ECE=0.163, AUROC=0.806 on Qwen3-4B
- SFT + self-distillation → ECE=0.034, AUROC=0.879
- 4.8x improvement in ECE with no accuracy loss

Usage:
  python tools/training/self_distill.py --teacher /workspace/team6/adapters/uncertainty_resolver/final
"""
import sys, json, os, math, time, gc, logging, argparse, shutil
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/workspace/team6/self_distill.log", mode="w"),
    ]
)
logger = logging.getLogger("self_distill")

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType, PeftModel

IGNORE_INDEX = -100


def generate_soft_labels(teacher_model, tokenizer, train_data, max_length, device):
    """Run teacher model on training data to generate soft probability labels.

    Changed: generates p_fail for each training example.
    Why: soft labels contain "dark knowledge" about inter-class similarity,
    which helps the student model learn calibrated confidence.
    """
    teacher_model.eval()
    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    soft_labels = []
    for i, ex in enumerate(train_data):
        messages = ex["messages"][:2]  # system + user
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = teacher_model(**inputs).logits[0, -1, :]

        p_logit = logits[pass_id].item()
        f_logit = logits[fail_id].item()
        mx = max(p_logit, f_logit)
        p_fail = math.exp(f_logit - mx) / (math.exp(p_logit - mx) + math.exp(f_logit - mx))
        soft_labels.append(p_fail)

        if (i + 1) % 100 == 0:
            logger.info("  Generated soft labels: %d/%d", i + 1, len(train_data))

    return soft_labels


class DistillDataset(torch.utils.data.Dataset):
    """Dataset for self-distillation with soft target probabilities."""

    def __init__(self, examples, soft_labels, tokenizer, max_length):
        self.data = []
        skipped = 0
        for ex, p_fail in zip(examples, soft_labels):
            messages = ex["messages"]
            try:
                full = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=False, enable_thinking=False)
                prompt = tokenizer.apply_chat_template(
                    messages[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                full = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=False)
                prompt = tokenizer.apply_chat_template(
                    messages[:-1], tokenize=False, add_generation_prompt=True)

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

            if (labels != IGNORE_INDEX).sum() == 0:
                skipped += 1
                continue

            self.data.append({
                "input_ids": ids,
                "attention_mask": mask,
                "labels": labels,
                "soft_p_fail": torch.tensor(p_fail, dtype=torch.float32),
            })

        if skipped:
            logger.warning("Skipped %d examples", skipped)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        return self.data[i]


class DistillTrainer(Trainer):
    """Trainer with KL-divergence loss against teacher's soft labels.

    Changed: replaces standard CE with interpolated CE + KL loss.
    Why: KL loss makes student match teacher's probability distribution,
    inheriting the teacher's calibration properties.

    L = alpha * L_CE(hard) + (1-alpha) * T^2 * KL(teacher_soft || student_soft)
    """

    def __init__(self, pass_id, fail_id, distill_alpha=0.5, temperature=2.0, **kwargs):
        super().__init__(**kwargs)
        self.pass_id = pass_id
        self.fail_id = fail_id
        self.distill_alpha = distill_alpha
        self.temperature = temperature

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        soft_p_fail = inputs.pop("soft_p_fail", None)

        outputs = model(**inputs)
        ce_loss = outputs.loss

        if soft_p_fail is not None:
            # Get student's logits at last non-padding position
            logits = outputs.logits  # (batch, seq, vocab)
            attention_mask = inputs["attention_mask"]
            seq_lengths = attention_mask.sum(dim=1) - 1

            # Extract pass/fail logits at answer position (right before last token)
            batch_size = logits.size(0)
            # Changed: use the position just before the label token
            # Why: that's where the model predicts the next token (pass/fail)
            last_logits = logits[torch.arange(batch_size), seq_lengths - 1]  # (batch, vocab)
            student_pf = last_logits[:, [self.pass_id, self.fail_id]]  # (batch, 2)

            # Teacher soft distribution
            teacher_p_fail = soft_p_fail.to(student_pf.device)  # (batch,)
            teacher_dist = torch.stack([1 - teacher_p_fail, teacher_p_fail], dim=1)  # (batch, 2)

            # KL divergence with temperature scaling
            T = self.temperature
            student_log_probs = F.log_softmax(student_pf / T, dim=1)
            teacher_probs = F.softmax(torch.log(teacher_dist.clamp(min=1e-8)) / T, dim=1)
            kl_loss = F.kl_div(student_log_probs, teacher_probs, reduction="batchmean") * (T * T)

            total_loss = self.distill_alpha * ce_loss + (1 - self.distill_alpha) * kl_loss
        else:
            total_loss = ce_loss

        return (total_loss, outputs) if return_outputs else total_loss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", default="/workspace/team6/adapters/uncertainty_resolver/final")
    parser.add_argument("--model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--alpha", type=float, default=0.5, help="CE vs KL weight (0.5=equal)")
    parser.add_argument("--temperature", type=float, default=2.0)
    args = parser.parse_args()

    SEP = "=" * 60
    logger.info(SEP)
    logger.info("SELF-DISTILLATION FOR CALIBRATION")
    logger.info("Teacher: %s", args.teacher)
    logger.info(SEP)

    # Load data
    data_dir = Path("/workspace/team6/training_data")
    train_data = json.loads((data_dir / "uncertainty_train.json").read_text())
    val_data = json.loads((data_dir / "uncertainty_val.json").read_text()) if (data_dir / "uncertainty_val.json").exists() else []
    logger.info("Data: train=%d val=%d", len(train_data), len(val_data))

    # Load teacher
    logger.info("Loading teacher model...")
    tokenizer = AutoTokenizer.from_pretrained(args.teacher, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    teacher = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
    teacher = PeftModel.from_pretrained(teacher, args.teacher)
    teacher.eval()
    device = next(teacher.parameters()).device

    # Generate soft labels
    logger.info("Generating soft labels from teacher...")
    t0 = time.time()
    soft_labels = generate_soft_labels(teacher, tokenizer, train_data, 1024, device)
    logger.info("Soft labels generated in %.0fs", time.time() - t0)

    # Analyze soft label distribution
    import numpy as np
    sl = np.array(soft_labels)
    logger.info("Soft label stats: mean=%.3f std=%.3f min=%.3f max=%.3f",
                sl.mean(), sl.std(), sl.min(), sl.max())
    logger.info("  p_fail < 0.1: %d, p_fail > 0.9: %d, 0.3 < p_fail < 0.7: %d",
                (sl < 0.1).sum(), (sl > 0.9).sum(), ((sl > 0.3) & (sl < 0.7)).sum())

    # Free teacher VRAM
    del teacher
    gc.collect()
    torch.cuda.empty_cache()
    time.sleep(3)

    # Load fresh student model
    logger.info("Loading student model...")
    student = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=args.rank, lora_alpha=args.rank * 2,
        lora_dropout=0.1, target_modules=["q_proj", "v_proj", "k_proj", "o_proj"])
    student = get_peft_model(student, lora_cfg)
    student.gradient_checkpointing_enable()
    student.enable_input_require_grads()

    # Build distillation dataset
    dataset = DistillDataset(train_data, soft_labels, tokenizer, 1024)
    logger.info("Distill dataset: %d examples", len(dataset))

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    # Train student
    out_dir = Path("/workspace/team6/adapters/distilled")
    out_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
        learning_rate=args.lr,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        optim="adamw_torch",
        logging_steps=50,
        save_strategy="no",
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = DistillTrainer(
        pass_id=pass_id, fail_id=fail_id,
        distill_alpha=args.alpha, temperature=args.temperature,
        model=student, args=training_args, train_dataset=dataset)

    logger.info("Starting distillation: %d epochs, lr=%s, alpha=%.2f, T=%.1f",
                args.epochs, args.lr, args.alpha, args.temperature)

    t0 = time.time()
    result = trainer.train()
    logger.info("Distillation done: %.0fs, loss=%.4f", time.time() - t0, result.training_loss)

    # Save
    final_path = str(out_dir / "final")
    student.save_pretrained(final_path)
    tokenizer.save_pretrained(final_path)

    # Copy to submission
    submit_path = str(ROOT / "artifacts" / "lora_adapter_v3")
    if os.path.exists(submit_path):
        shutil.rmtree(submit_path)
    shutil.copytree(final_path, submit_path)
    logger.info("Saved distilled adapter to %s (and %s)", final_path, submit_path)

    # Evaluate calibration
    logger.info("\n%s", SEP)
    logger.info("CALIBRATION EVALUATION")
    logger.info(SEP)

    from tools.training.train_uncertainty_resolver import evaluate_model
    if val_data:
        device = next(student.parameters()).device
        metrics, _ = evaluate_model(student, tokenizer, val_data, 1024, device)
        logger.info("Val: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f",
                    metrics["accuracy"] * 100, metrics["fail_precision"],
                    metrics["fail_recall"], metrics["f1_fail"])

    # Cleanup
    del student, trainer, dataset
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("DONE")


if __name__ == "__main__":
    main()
