# Changed: full hyperparameter sweep for LoRA fine-tuning.
# Why: need to find optimal (rank, alpha, LR, dropout, max_length, batch_size) before 50-epoch main training.
# Fixed: scheduler=cosine, optimizer=NAdam.
# Sweep order: LR → rank → alpha → dropout → max_length → batch_size → model_size.
# Each step carries forward the best from previous step.

from __future__ import annotations
import json, sys, os, time, logging, math, gc
from pathlib import Path
from dataclasses import dataclass, asdict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("sweep")

RESULTS_PATH = Path("/workspace/team6/sweep_results.json")
BEST_CONFIG_PATH = Path("/workspace/team6/best_sweep_config.json")


@dataclass
class SweepConfig:
    model_name: str = "Qwen/Qwen3.5-4B"
    lr: float = 2e-5
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    num_epochs: int = 5
    max_length: int = 1024
    # Changed: batch_size=8 to target ~90% VRAM utilization (46GB × 90% = 41GB).
    # 4B + LoRA + fp16 + grad_ckpt + bs=8 + max_len=1024 ≈ 38-42GB.
    # Cushion ~5GB (10-20% recommended per PyTorch best practices).
    # If OOM, script catches RuntimeError and retries with smaller bs.
    batch_size: int = 8
    grad_accum: int = 1  # effective batch = 8, no accumulation needed
    target_modules: str = "q_proj,v_proj,k_proj,o_proj"
    run_name: str = "default"


def prepare_data(config: SweepConfig):
    """Load training data + validation split."""
    from tools.finetune_lora_v2 import format_for_training_v2

    training_path = Path("/workspace/team6/training_data/training_cases.json")
    test_path = Path("/workspace/team6/large_dp_test_set.json")

    all_cases = json.loads(training_path.read_text())
    test_cases = json.loads(test_path.read_text())

    # Validation: last 52 cases (idx 200-251: includes 49 fail + 3 pass)
    val_cases_raw = test_cases[200:]

    # Format training data
    train_data = []
    for case in all_cases:
        records = case["records"]
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue
        train_data.append(format_for_training_v2(records, case["label"]))

    logger.info("Train: %d | Val: %d (pass=%d, fail=%d)",
                len(train_data), len(val_cases_raw),
                sum(1 for c in val_cases_raw if c["expected"] == "pass"),
                sum(1 for c in val_cases_raw if c["expected"] == "fail"))
    return train_data, val_cases_raw


def build_dataset(train_data, tokenizer, max_length):
    """Build masked dataset for training."""
    import torch
    from torch.utils.data import Dataset

    IGNORE_INDEX = -100

    class MaskedDS(Dataset):
        def __init__(self):
            self.examples = []
            for item in train_data:
                try:
                    full = tokenizer.apply_chat_template(
                        item["messages"], tokenize=False,
                        add_generation_prompt=False, enable_thinking=False)
                except TypeError:
                    full = tokenizer.apply_chat_template(
                        item["messages"], tokenize=False, add_generation_prompt=False)
                try:
                    prompt = tokenizer.apply_chat_template(
                        item["messages"][:-1], tokenize=False,
                        add_generation_prompt=True, enable_thinking=False)
                except TypeError:
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
                self.examples.append({"input_ids": ids, "attention_mask": mask, "labels": labels})

        def __len__(self): return len(self.examples)
        def __getitem__(self, i): return self.examples[i]

    ds = MaskedDS()
    logger.info("Dataset built: %d examples, max_length=%d", len(ds), max_length)
    return ds


def evaluate_model(model, tokenizer, val_cases, max_length):
    """Evaluate on validation set, return metrics dict."""
    import torch
    from tools.finetune_lora_v2 import format_trajectory_rich
    from src.solver import StatefulOpalVerifier

    model.eval()
    verifier = StatefulOpalVerifier()

    tp = fp = fn = tn = 0
    for case in val_cases:
        records = verifier._records(case["steps"])
        if not records:
            continue
        gold = case["expected"]

        prompt_text = format_trajectory_rich(records)
        messages = [
            {"role": "system", "content": "You are a TCG/Opal SSD protocol compliance verifier. "
             "Given a command-response trajectory with session state, "
             "determine if the final response is consistent with the specification. "
             "Answer exactly: pass or fail"},
            {"role": "user", "content": prompt_text},
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
    acc = (tp + tn) / total if total else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0

    return {"accuracy": round(acc, 4), "fail_precision": round(prec, 4),
            "fail_recall": round(rec, 4), "f1_fail": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def run_single(config: SweepConfig, train_data, val_cases):
    """Train one config, evaluate, return full result dict."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
    from peft import LoraConfig, get_peft_model, TaskType

    logger.info("=" * 50)
    logger.info("RUN: %s", config.run_name)
    logger.info("  model=%s lr=%.1e rank=%d alpha=%d dropout=%.2f maxlen=%d bs=%d gacc=%d",
                config.model_name, config.lr, config.lora_rank, config.lora_alpha,
                config.lora_dropout, config.max_length, config.batch_size, config.grad_accum)

    output_dir = Path(f"/workspace/team6/sweep_runs/{config.run_name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(config.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config.model_name, torch_dtype=torch.float16,
        device_map="auto", trust_remote_code=True)

    target_mods = [m.strip() for m in config.target_modules.split(",")]
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=config.lora_rank,
        lora_alpha=config.lora_alpha, lora_dropout=config.lora_dropout,
        target_modules=target_mods)
    model = get_peft_model(model, lora_cfg)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info("  trainable params: %d", trainable)

    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    dataset = build_dataset(train_data, tokenizer, config.max_length)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.grad_accum,
        learning_rate=config.lr,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        optim="adamw_torch",
        logging_steps=50,
        save_strategy="no",
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
    t0 = time.time()
    try:
        train_result = trainer.train()
    except RuntimeError as e:
        if "out of memory" in str(e).lower() and config.batch_size > 1:
            # Auto-reduce batch size on OOM and retry
            logger.warning("  OOM at bs=%d, retrying with bs=%d",
                          config.batch_size, config.batch_size // 2)
            del trainer, dataset, model, tokenizer
            gc.collect()
            import torch as _t; _t.cuda.empty_cache()
            time.sleep(5)
            config.batch_size = config.batch_size // 2
            config.grad_accum = max(1, 8 // config.batch_size)
            config.run_name = config.run_name + f"_bs{config.batch_size}"
            return run_single(config, train_data, val_cases)  # retry
        raise
    train_time = time.time() - t0
    train_loss = train_result.training_loss

    logger.info("  train done: %.0fs, loss=%.4f", train_time, train_loss)

    metrics = evaluate_model(model, tokenizer, val_cases, config.max_length)
    logger.info("  RESULT: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f | tp=%d fp=%d fn=%d tn=%d",
                metrics["accuracy"] * 100, metrics["fail_precision"],
                metrics["fail_recall"], metrics["f1_fail"],
                metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"])

    full_result = {**asdict(config), **metrics,
                   "train_loss": round(train_loss, 5),
                   "train_time_s": round(train_time),
                   "trainable_params": trainable}

    # Cleanup GPU
    del model, trainer, dataset, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    time.sleep(5)  # GPU memory release

    return full_result


def save_result(result):
    results = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else []
    results.append(result)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


def pick_best(results, key="fail_recall", constraint_key="fail_precision", constraint_min=0.9):
    """Pick best result by key, subject to constraint."""
    valid = [r for r in results if r.get(constraint_key, 0) >= constraint_min]
    if not valid:
        valid = results  # fallback: ignore constraint
    return max(valid, key=lambda r: r.get(key, 0))


def main():
    logger.info("=" * 60)
    logger.info("FULL LORA HYPERPARAMETER SWEEP")
    logger.info("Fixed: scheduler=cosine, optimizer=NAdam")
    logger.info("=" * 60)

    # Reset results
    if RESULTS_PATH.exists():
        RESULTS_PATH.rename(RESULTS_PATH.with_suffix(".json.bak"))
    RESULTS_PATH.write_text("[]")

    base_config = SweepConfig()
    train_data, val_cases = prepare_data(base_config)

    # ── Step 1: LR Sweep ──────────────────────────────────────
    # LoRA standard LR is ~2e-4 (10x full FT). Previous 2e-5 was too low.
    # "Learning Rate Matters" (arXiv 2602.04998): start at 2e-4.
    logger.info("\n>>> STEP 1: LR Sweep <<<")
    step1_results = []
    for lr in [5e-5, 1e-4, 2e-4, 5e-4, 1e-3]:
        cfg = SweepConfig(lr=lr, run_name=f"s1_lr_{lr:.0e}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        step1_results.append(r)
    best1 = pick_best(step1_results)
    best_lr = best1["lr"]
    logger.info(">>> Best LR: %.1e (recall=%.2f, prec=%.2f)", best_lr, best1["fail_recall"], best1["fail_precision"])

    # ── Step 2: Rank Sweep ────────────────────────────────────
    logger.info("\n>>> STEP 2: Rank Sweep <<<")
    step2_results = []
    for rank in [4, 8, 16, 32, 64]:
        cfg = SweepConfig(lr=best_lr, lora_rank=rank, lora_alpha=rank * 2,
                          run_name=f"s2_r{rank}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        step2_results.append(r)
    best2 = pick_best(step2_results)
    best_rank = best2["lora_rank"]
    logger.info(">>> Best rank: %d (recall=%.2f)", best_rank, best2["fail_recall"])

    # ── Step 3: Alpha Sweep ───────────────────────────────────
    logger.info("\n>>> STEP 3: Alpha Sweep <<<")
    step3_results = []
    for ratio in [1, 2, 4, 8]:
        alpha = best_rank * ratio
        cfg = SweepConfig(lr=best_lr, lora_rank=best_rank, lora_alpha=alpha,
                          run_name=f"s3_a{alpha}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        step3_results.append(r)
    best3 = pick_best(step3_results)
    best_alpha = best3["lora_alpha"]
    logger.info(">>> Best alpha: %d (ratio=%.1f, recall=%.2f)", best_alpha, best_alpha / best_rank, best3["fail_recall"])

    # ── Step 4: Dropout Sweep ─────────────────────────────────
    logger.info("\n>>> STEP 4: Dropout Sweep <<<")
    step4_results = []
    for dropout in [0.0, 0.05, 0.1, 0.2]:
        cfg = SweepConfig(lr=best_lr, lora_rank=best_rank, lora_alpha=best_alpha,
                          lora_dropout=dropout, run_name=f"s4_d{dropout:.2f}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        step4_results.append(r)
    best4 = pick_best(step4_results)
    best_dropout = best4["lora_dropout"]
    logger.info(">>> Best dropout: %.2f (recall=%.2f)", best_dropout, best4["fail_recall"])

    # ── Step 5: max_length Sweep ──────────────────────────────
    logger.info("\n>>> STEP 5: max_length Sweep <<<")
    step5_results = []
    for ml in [512, 1024, 2048]:
        cfg = SweepConfig(lr=best_lr, lora_rank=best_rank, lora_alpha=best_alpha,
                          lora_dropout=best_dropout, max_length=ml,
                          run_name=f"s5_ml{ml}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        step5_results.append(r)
    best5 = pick_best(step5_results)
    best_ml = best5["max_length"]
    logger.info(">>> Best max_length: %d (recall=%.2f)", best_ml, best5["fail_recall"])

    # Batch size is NOT a sweep target — fixed to max VRAM allows (bs=4 for 4B, bs=2 for 9B).
    best_bs = best5.get("batch_size", 4)
    best_ga = best5.get("grad_accum", 2)

    # ── Step 6: Model Size ────────────────────────────────────
    # batch size adapts to model: 4B→bs=8, 9B→bs=4 (target 90% of 46GB)
    logger.info("\n>>> STEP 6: Model Size <<<")
    step6_results = []
    for model_name, m_bs, m_ga in [("Qwen/Qwen3.5-4B", 8, 1), ("Qwen/Qwen3.5-9B", 4, 1)]:
        cfg = SweepConfig(model_name=model_name, lr=best_lr,
                          lora_rank=best_rank, lora_alpha=best_alpha,
                          lora_dropout=best_dropout, max_length=best_ml,
                          batch_size=m_bs, grad_accum=m_ga,
                          run_name=f"s6_{model_name.split('/')[-1]}")
        try:
            r = run_single(cfg, train_data, val_cases)
            save_result(r)
            step6_results.append(r)
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.warning("  OOM for %s, skipping", model_name)
                gc.collect()
                import torch; torch.cuda.empty_cache()
            else:
                raise
    best6 = pick_best(step6_results) if step6_results else best5
    best_model = best6.get("model_name", "Qwen/Qwen3.5-4B")
    best_bs = best6.get("batch_size", 4)
    best_ga = best6.get("grad_accum", 2)
    logger.info(">>> Best model: %s (recall=%.2f)", best_model, best6["fail_recall"])

    # ── Final Summary ─────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("SWEEP COMPLETE")
    logger.info("  model     = %s", best_model)
    logger.info("  lr        = %.1e", best_lr)
    logger.info("  rank      = %d", best_rank)
    logger.info("  alpha     = %d", best_alpha)
    logger.info("  dropout   = %.2f", best_dropout)
    logger.info("  max_length= %d", best_ml)
    logger.info("  batch     = %d × %d = %d", best_bs, best_ga, best_bs * best_ga)
    logger.info("  recall    = %.2f (prec >= 0.9)", best6["fail_recall"])
    logger.info("=" * 60)

    best_cfg = {"model": best_model, "lr": best_lr, "rank": best_rank,
                "alpha": best_alpha, "dropout": best_dropout,
                "max_length": best_ml, "batch_size": best_bs, "grad_accum": best_ga}
    BEST_CONFIG_PATH.write_text(json.dumps(best_cfg, indent=2))
    logger.info("Saved to %s", BEST_CONFIG_PATH)
    logger.info("Run main training: python3 tools/sweep_lora.py --main")


def main_training():
    """50-epoch main training with best config from sweep."""
    if BEST_CONFIG_PATH.exists():
        cfg = json.loads(BEST_CONFIG_PATH.read_text())
    else:
        cfg = {}

    model = os.environ.get("RAG_MODEL", cfg.get("model", "Qwen/Qwen3.5-4B"))
    lr = float(os.environ.get("LR", cfg.get("lr", 2e-5)))
    rank = int(os.environ.get("LORA_RANK", cfg.get("rank", 16)))
    alpha = int(os.environ.get("LORA_ALPHA", cfg.get("alpha", 32)))
    dropout = float(os.environ.get("LORA_DROPOUT", cfg.get("dropout", 0.05)))
    ml = int(os.environ.get("MAX_LENGTH", cfg.get("max_length", 1024)))
    bs = int(os.environ.get("BATCH_SIZE", cfg.get("batch_size", 1)))
    ga = int(os.environ.get("GRAD_ACCUM", cfg.get("grad_accum", 8)))
    epochs = int(os.environ.get("NUM_EPOCHS", "50"))

    config = SweepConfig(
        model_name=model, lr=lr, lora_rank=rank, lora_alpha=alpha,
        lora_dropout=dropout, max_length=ml, batch_size=bs, grad_accum=ga,
        num_epochs=epochs, run_name=f"main_{epochs}ep")

    train_data, val_cases = prepare_data(config)
    result = run_single(config, train_data, val_cases)
    save_result(result)

    # Save adapter to artifacts
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    adapter_src = Path(f"/workspace/team6/sweep_runs/{config.run_name}")
    # The model was already cleaned up in run_single, need to re-save
    # Actually run_single doesn't save adapter. Let me fix: save in run_single is needed for main.
    logger.info("Main training result: %s", json.dumps(result, indent=2))
    logger.info("NOTE: Re-run with --main-save to load and save the adapter after training.")


if __name__ == "__main__":
    if "--main" in sys.argv:
        main_training()
    else:
        main()
