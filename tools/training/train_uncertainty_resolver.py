"""Train LoRA as an "Uncertainty Resolver" for rule engine low-confidence cases.

Changed: v3 training pipeline with rule engine context in prompts.
Why: v2 trained on raw trajectories without rule engine info → 70% public, 78.8% val.
v3 adds rule engine analysis (rule_id, prediction, confidence tier) to the prompt,
so the LLM learns WHEN to agree/disagree with the rule engine.

Key differences from v2:
1. Prompt includes rule engine's decision + rule_id + confidence tier
2. Training data tagged by tier (high/low/medium confidence)
3. Evaluation separately reports per-tier accuracy
4. Specifically measures "correction rate" on low-confidence cases

Usage:
  nohup python -u tools/training/train_uncertainty_resolver.py >> /workspace/team6/uncertainty_train.log 2>&1 &
"""
import sys, json, os, math, time, gc, logging, shutil
from pathlib import Path
from collections import Counter
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/workspace/team6/uncertainty_train.log", mode="w"),
    ]
)
logger = logging.getLogger("uncertainty_resolver")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType, PeftModel

IGNORE_INDEX = -100


@dataclass
class Config:
    # Changed: default to env var RAG_MODEL for easy 4B↔9B switching.
    # Why: 9B feasibility confirmed (28-30GB train, 0.5s/case inference).
    model_name: str = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")
    lr: float = 1e-3  # Changed: 1e-3 confirmed best from sweep3
    rank: int = 16
    alpha: int = 32
    dropout: float = 0.1  # Changed: moderate dropout (0.05 too low, 0.2 too high per cycle3)
    max_length: int = 1024
    epochs: int = 20  # Changed: 20 epochs for proper training (5 was too few)
    batch_size: int = 4  # Changed: 4 safe for L40S with label smoothing
    grad_accum: int = 2  # Changed: effective bs=8
    label_smoothing: float = 0.05  # Changed: light smoothing (0.1 caused too much regularization)
    warmup_ratio: float = 0.05
    save_every_n_epochs: int = 5  # Changed: checkpoint every 5 epochs for selection
    # Changed: SCL (Supervised Contrastive Learning) loss weight.
    # Why: Gunel et al. (ICLR 2021) show SCL + CE improves few-shot by up to 10.7%.
    # Paper: "Supervised Contrastive Learning for Pre-trained Language Model Fine-tuning"
    # SCL pulls same-class representations together, pushes different-class apart.
    scl_weight: float = float(os.environ.get("SCL_WEIGHT", "0.1"))
    scl_temperature: float = 0.5  # Changed: τ=0.5 per Gunel et al. optimal for binary


class MaskedDataset(torch.utils.data.Dataset):
    """Dataset with label masking — only compute loss on assistant response tokens.

    Changed: also stores class_label (0=pass, 1=fail) for SCL loss computation.
    Why: SCL needs to know which examples share the same gold label within a batch.
    """

    def __init__(self, examples, tokenizer, max_length):
        self.data = []
        skipped = 0
        for ex in examples:
            messages = ex["messages"]
            # Changed: extract gold label for SCL loss.
            gold = ex.get("gold", messages[-1]["content"])
            class_label = 1 if gold == "fail" else 0

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
                "class_labels": torch.tensor(class_label, dtype=torch.long),
            })

        if skipped:
            logger.warning("Skipped %d examples (all tokens masked)", skipped)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        return self.data[i]


def supervised_contrastive_loss(hidden_states, attention_mask, class_labels, temperature=0.5):
    """Compute SCL loss on last-token hidden states.

    Changed: implements Gunel et al. (ICLR 2021) supervised contrastive loss.
    Why: pulls same-class representations together, pushes different-class apart.
    This improves binary classification especially with limited data.

    Args:
        hidden_states: (batch, seq_len, hidden_dim) from model output
        attention_mask: (batch, seq_len)
        class_labels: (batch,) — 0 for pass, 1 for fail
        temperature: τ for scaling similarities
    Returns:
        scalar SCL loss
    """
    batch_size = hidden_states.size(0)
    if batch_size < 2:
        return torch.tensor(0.0, device=hidden_states.device)

    # Changed: extract last non-padding token's hidden state as the representation.
    # Why: in causal LM, the last token position aggregates all prior context.
    seq_lengths = attention_mask.sum(dim=1) - 1  # (batch,)
    reps = hidden_states[torch.arange(batch_size), seq_lengths]  # (batch, hidden_dim)

    # L2 normalize
    reps = torch.nn.functional.normalize(reps, p=2, dim=1)

    # Pairwise cosine similarities / temperature
    sim_matrix = torch.matmul(reps, reps.T) / temperature  # (batch, batch)

    # Mask: same class = positive pair, different class = negative
    labels_eq = class_labels.unsqueeze(0) == class_labels.unsqueeze(1)  # (batch, batch)
    eye_mask = ~torch.eye(batch_size, dtype=torch.bool, device=hidden_states.device)

    # For numerical stability
    sim_max, _ = sim_matrix.max(dim=1, keepdim=True)
    sim_matrix = sim_matrix - sim_max.detach()

    # Compute log-sum-exp over all negatives + current positive
    exp_sim = torch.exp(sim_matrix) * eye_mask.float()
    log_sum_exp = torch.log(exp_sim.sum(dim=1, keepdim=True) + 1e-8)

    # Positive pair log similarities
    positive_mask = labels_eq & eye_mask
    n_positives = positive_mask.sum(dim=1)

    # Avoid division by zero for examples with no positive pairs
    has_positives = n_positives > 0
    if not has_positives.any():
        return torch.tensor(0.0, device=hidden_states.device)

    # SCL loss: -1/|P(i)| * Σ_{p∈P(i)} (sim(i,p)/τ - log_sum_exp)
    log_prob = sim_matrix - log_sum_exp
    scl_per_example = -(log_prob * positive_mask.float()).sum(dim=1)
    scl_per_example = scl_per_example / n_positives.clamp(min=1).float()

    return scl_per_example[has_positives].mean()


class SCLTrainer(Trainer):
    """Custom Trainer that adds SCL loss to standard CE loss.

    Changed: adds supervised contrastive learning loss.
    Why: Paper 5 (Gunel et al. ICLR 2021) shows +10.7% with 20 examples for binary classification.
    L_total = (1 - scl_weight) * L_CE + scl_weight * L_SCL
    """

    def __init__(self, scl_weight=0.1, scl_temperature=0.5, **kwargs):
        super().__init__(**kwargs)
        self.scl_weight = scl_weight
        self.scl_temperature = scl_temperature

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        class_labels = inputs.pop("class_labels", None)

        # Standard forward pass
        outputs = model(**inputs)
        ce_loss = outputs.loss

        # Changed: compute SCL loss if class labels available and weight > 0.
        if self.scl_weight > 0 and class_labels is not None:
            hidden_states = outputs.get("hidden_states", None)
            if hidden_states is None:
                # Need to re-run with output_hidden_states=True
                with torch.no_grad():
                    hs_outputs = model(**inputs, output_hidden_states=True)
                hidden_states = hs_outputs.hidden_states[-1]  # last layer

            scl_loss = supervised_contrastive_loss(
                hidden_states, inputs["attention_mask"],
                class_labels, self.scl_temperature)

            total_loss = (1 - self.scl_weight) * ce_loss + self.scl_weight * scl_loss
        else:
            total_loss = ce_loss

        return (total_loss, outputs) if return_outputs else total_loss


def evaluate_model(model, tokenizer, eval_cases, max_length, device):
    """Evaluate model on cases, return per-tier metrics."""
    model.eval()
    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    results = []
    for case in eval_cases:
        messages = case["messages"][:2]  # system + user only
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]

        p_logit = logits[pass_id].item()
        f_logit = logits[fail_id].item()
        mx = max(p_logit, f_logit)
        p_fail = math.exp(f_logit - mx) / (math.exp(p_logit - mx) + math.exp(f_logit - mx))
        pred = "fail" if p_fail > 0.5 else "pass"

        gold = case.get("gold", case["messages"][-1]["content"])
        tier = case.get("tier", "unknown")
        rule_pred = case.get("rule_pred", "unknown")

        results.append({
            "pred": pred, "gold": gold, "p_fail": p_fail,
            "tier": tier, "rule_pred": rule_pred,
            "correct": pred == gold,
            "corrects_rule": rule_pred != gold and pred == gold,  # LLM fixes rule error
            "breaks_rule": rule_pred == gold and pred != gold,    # LLM breaks correct rule
        })

    # Aggregate metrics
    total = len(results)
    correct = sum(r["correct"] for r in results)
    tp = sum(1 for r in results if r["gold"] == "fail" and r["pred"] == "fail")
    fp = sum(1 for r in results if r["gold"] == "pass" and r["pred"] == "fail")
    fn = sum(1 for r in results if r["gold"] == "fail" and r["pred"] == "pass")
    tn = sum(1 for r in results if r["gold"] == "pass" and r["pred"] == "pass")

    metrics = {
        "accuracy": correct / total if total else 0,
        "fail_precision": tp / (tp + fp) if (tp + fp) else 0,
        "fail_recall": tp / (tp + fn) if (tp + fn) else 0,
        "f1_fail": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0,
        "total": total,
        "corrections": sum(r["corrects_rule"] for r in results),
        "breaks": sum(r["breaks_rule"] for r in results),
    }

    # Per-tier metrics
    for tier in ["high", "medium", "low"]:
        tier_results = [r for r in results if r["tier"] == tier]
        if tier_results:
            t_correct = sum(r["correct"] for r in tier_results)
            metrics[f"{tier}_accuracy"] = t_correct / len(tier_results)
            metrics[f"{tier}_corrections"] = sum(r["corrects_rule"] for r in tier_results)
            metrics[f"{tier}_breaks"] = sum(r["breaks_rule"] for r in tier_results)
            metrics[f"{tier}_total"] = len(tier_results)

    return metrics, results


def train_and_evaluate(cfg: Config):
    """Full training + evaluation pipeline."""
    SEP = "=" * 60

    # Load data
    logger.info(SEP)
    logger.info("UNCERTAINTY RESOLVER TRAINING v3")
    logger.info(SEP)

    data_dir = Path("/workspace/team6/training_data")
    train_path = data_dir / "uncertainty_train.json"
    val_path = data_dir / "uncertainty_val.json"
    test_path = data_dir / "uncertainty_test.json"

    if not train_path.exists():
        logger.error("Training data not found. Run generate_uncertainty_data.py first.")
        return

    train_data = json.loads(train_path.read_text())
    val_data = json.loads(val_path.read_text()) if val_path.exists() else []
    test_data = json.loads(test_path.read_text()) if test_path.exists() else []

    logger.info("Data: train=%d val=%d test=%d", len(train_data), len(val_data), len(test_data))

    # Load tokenizer + model
    logger.info("Loading %s...", cfg.model_name)
    tokenizer = AutoTokenizer.from_pretrained(cfg.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Changed: support max_memory to cap VRAM usage when sharing GPU.
    # Why: server is shared; other processes may use GPU simultaneously.
    max_mem_gb = int(os.environ.get("MAX_MEMORY_GB", "0"))
    load_kwargs = dict(torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
    if max_mem_gb > 0:
        load_kwargs["max_memory"] = {0: f"{max_mem_gb}GiB", "cpu": "30GiB"}
        logger.info("VRAM cap: %d GiB", max_mem_gb)
    model = AutoModelForCausalLM.from_pretrained(cfg.model_name, **load_kwargs)

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=cfg.rank, lora_alpha=cfg.alpha,
        lora_dropout=cfg.dropout,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"])
    model = get_peft_model(model, lora_cfg)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info("Trainable params: %d (%.3f%%)", trainable,
                trainable / sum(p.numel() for p in model.parameters()) * 100)

    # Build dataset
    dataset = MaskedDataset(train_data, tokenizer, cfg.max_length)
    logger.info("Dataset: %d examples", len(dataset))

    # Training
    adapter_dir = Path("/workspace/team6/adapters/uncertainty_resolver")
    adapter_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(adapter_dir / "checkpoints"),
        num_train_epochs=cfg.epochs,
        per_device_train_batch_size=cfg.batch_size,
        gradient_accumulation_steps=cfg.grad_accum,
        learning_rate=cfg.lr,
        warmup_ratio=cfg.warmup_ratio,
        lr_scheduler_type="cosine",
        optim="adamw_torch",
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=4,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
        label_smoothing_factor=cfg.label_smoothing,
    )

    # Changed: use SCLTrainer if scl_weight > 0, else standard Trainer.
    # Why: SCL loss adds supervised contrastive learning (Gunel et al. ICLR 2021).
    if cfg.scl_weight > 0:
        trainer = SCLTrainer(
            scl_weight=cfg.scl_weight, scl_temperature=cfg.scl_temperature,
            model=model, args=training_args, train_dataset=dataset)
        logger.info("Using SCLTrainer (weight=%.2f, temp=%.2f)", cfg.scl_weight, cfg.scl_temperature)
    else:
        trainer = Trainer(model=model, args=training_args, train_dataset=dataset)

    logger.info("Starting training: %d epochs, lr=%s, rank=%d, bs=%d*%d=%d",
                cfg.epochs, cfg.lr, cfg.rank, cfg.batch_size, cfg.grad_accum,
                cfg.batch_size * cfg.grad_accum)

    t0 = time.time()
    try:
        result = trainer.train()
        logger.info("Training done: %.0fs, loss=%.4f", time.time() - t0, result.training_loss)
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            logger.error("OOM during training. Try reducing batch_size or max_length.")
            # Changed: retry with smaller batch on OOM
            torch.cuda.empty_cache()
            gc.collect()
            cfg.batch_size = max(1, cfg.batch_size // 2)
            cfg.grad_accum *= 2
            logger.info("Retrying with bs=%d gacc=%d", cfg.batch_size, cfg.grad_accum)
            training_args.per_device_train_batch_size = cfg.batch_size
            training_args.gradient_accumulation_steps = cfg.grad_accum
            if cfg.scl_weight > 0:
                trainer = SCLTrainer(
                    scl_weight=cfg.scl_weight, scl_temperature=cfg.scl_temperature,
                    model=model, args=training_args, train_dataset=dataset)
            else:
                trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
            result = trainer.train()
            logger.info("Training done (retry): %.0fs, loss=%.4f",
                        time.time() - t0, result.training_loss)
        else:
            raise

    # Save final adapter
    final_adapter = str(adapter_dir / "final")
    model.save_pretrained(final_adapter)
    tokenizer.save_pretrained(final_adapter)
    logger.info("Saved final adapter to %s", final_adapter)

    # Copy to submission path
    submit_adapter = str(ROOT / "artifacts" / "lora_adapter_v3")
    if os.path.exists(submit_adapter):
        shutil.rmtree(submit_adapter)
    shutil.copytree(final_adapter, submit_adapter)
    logger.info("Copied to submission path: %s", submit_adapter)

    # Evaluate on val
    device = next(model.parameters()).device
    logger.info("\n%s", SEP)
    logger.info("VALIDATION EVALUATION")
    logger.info(SEP)

    if val_data:
        val_metrics, val_results = evaluate_model(model, tokenizer, val_data,
                                                   cfg.max_length, device)
        logger.info("Val overall: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f",
                    val_metrics["accuracy"] * 100, val_metrics["fail_precision"],
                    val_metrics["fail_recall"], val_metrics["f1_fail"])
        logger.info("Val corrections: %d, breaks: %d (net=%+d)",
                    val_metrics["corrections"], val_metrics["breaks"],
                    val_metrics["corrections"] - val_metrics["breaks"])
        for tier in ["high", "medium", "low"]:
            if f"{tier}_accuracy" in val_metrics:
                logger.info("  %s tier: acc=%.1f%% corrections=%d breaks=%d (n=%d)",
                            tier, val_metrics[f"{tier}_accuracy"] * 100,
                            val_metrics[f"{tier}_corrections"],
                            val_metrics[f"{tier}_breaks"],
                            val_metrics[f"{tier}_total"])

    # Evaluate on test
    if test_data:
        logger.info("\n%s", SEP)
        logger.info("TEST EVALUATION")
        logger.info(SEP)
        test_metrics, test_results = evaluate_model(model, tokenizer, test_data,
                                                     cfg.max_length, device)
        logger.info("Test overall: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f",
                    test_metrics["accuracy"] * 100, test_metrics["fail_precision"],
                    test_metrics["fail_recall"], test_metrics["f1_fail"])
        logger.info("Test corrections: %d, breaks: %d (net=%+d)",
                    test_metrics["corrections"], test_metrics["breaks"],
                    test_metrics["corrections"] - test_metrics["breaks"])

    # Public 20 evaluation
    logger.info("\n%s", SEP)
    logger.info("PUBLIC 20 EVALUATION")
    logger.info(SEP)

    pub_labels = {}
    label_file = Path("/dl2026/dataset/label.jsonl")
    if label_file.exists():
        for line in open(label_file):
            d = json.loads(line)
            pub_labels[d["filename"]] = d["label"]

    from src.solver import StatefulOpalVerifier
    verifier = StatefulOpalVerifier()
    from tools.training.generate_uncertainty_data import get_rule_analysis, format_with_rule_context, SYSTEM_PROMPT_V3
    import glob as glob_mod

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    correct = 0
    total_pub = 0
    for tc_file in sorted(glob_mod.glob("/dl2026/dataset/testcases/tc*.json")):
        fname = os.path.basename(tc_file)
        steps = json.load(open(tc_file))
        gold = pub_labels.get(fname, "?")
        rule_result = verifier.verify_with_trace(steps)
        rule_pred = rule_result["prediction"]
        records = verifier._records(steps)

        analysis = get_rule_analysis(verifier, steps)
        prompt = format_with_rule_context(records, analysis) if records else ""

        if not prompt:
            lora_pred, p_fail = "pass", 0.5
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_V3},
                {"role": "user", "content": prompt},
            ]
            try:
                text = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                text = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=cfg.max_length)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = model(**inputs).logits[0, -1, :]
            p_l = logits[pass_id].item()
            f_l = logits[fail_id].item()
            mx = max(p_l, f_l)
            p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
            lora_pred = "fail" if p_fail > 0.5 else "pass"

        ok = lora_pred == gold
        if ok:
            correct += 1
        total_pub += 1
        override = " OVERRIDE" if rule_pred != lora_pred else ""
        logger.info("  %s: gold=%s rule=%s lora=%s p_fail=%.3f %s%s",
                    fname, gold, rule_pred, lora_pred, p_fail,
                    "OK" if ok else "ERR", override)

    logger.info("Public: %d/%d (%.1f%%)", correct, total_pub,
                correct / total_pub * 100 if total_pub else 0)

    # Save all results
    all_results = {
        "config": {k: v for k, v in cfg.__dict__.items()},
        "train_loss": result.training_loss if hasattr(result, 'training_loss') else None,
        "val_metrics": val_metrics if val_data else None,
        "test_metrics": test_metrics if test_data else None,
        "public_accuracy": correct / total_pub if total_pub else 0,
        "public_correct": correct,
        "public_total": total_pub,
    }
    json.dump(all_results, open("/workspace/team6/uncertainty_results.json", "w"),
              indent=2, default=str)
    logger.info("\nResults saved to /workspace/team6/uncertainty_results.json")

    # Cleanup
    del model, trainer, dataset
    gc.collect()
    torch.cuda.empty_cache()

    logger.info("DONE")


if __name__ == "__main__":
    cfg = Config()
    # Allow env overrides
    cfg.lr = float(os.environ.get("LR", str(cfg.lr)))
    cfg.rank = int(os.environ.get("RANK", str(cfg.rank)))
    cfg.epochs = int(os.environ.get("EPOCHS", str(cfg.epochs)))
    cfg.model_name = os.environ.get("MODEL", cfg.model_name)

    train_and_evaluate(cfg)
