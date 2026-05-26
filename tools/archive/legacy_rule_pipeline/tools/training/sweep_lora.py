# Changed: full hyperparameter sweep for LoRA fine-tuning.
# Why: need to find optimal (rank, alpha, LR, dropout, max_length, batch_size) before 50-epoch main training.
# Fixed: scheduler=cosine, optimizer=NAdam.
# Sweep order: LR → rank → alpha → dropout → max_length → batch_size → model_size.
# Each step carries forward the best from previous step.

from __future__ import annotations
import json, sys, os, time, logging, math, gc
from pathlib import Path
from dataclasses import dataclass, asdict

ROOT = Path(__file__).resolve().parents[2]
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
    # batch_size=8: target 90% VRAM (41GB / 46GB). OOM auto-retries with bs//2.
    batch_size: int = 8
    grad_accum: int = 1
    target_modules: str = "q_proj,v_proj,k_proj,o_proj"
    run_name: str = "default"


def prepare_data(config: SweepConfig, use_mutation: bool = False):
    """Load training data + validation + test splits.

    Changed: added use_mutation flag to load mutation data instead of/alongside spec data.
    Why: mutation data (Types A-H) covers data-level differences (tc14/tc15/tc20) that
    spec data alone cannot capture.

    Changed: use spec-based data (high-confidence labels) instead of noisy metamorphic data.
    Why: metamorphic labels from rule engine have ~29% noise. Spec labels are ground truth.
    Reference: "Analyzing the Effect of Noise in LLM Fine-tuning" (arXiv 2604.12469).

    Changed: added test set loading for unbiased final evaluation.
    Why: val is used for HP selection → optimistic bias. Test gives unbiased generalization estimate.
    """
    from tools.training.finetune_lora_v2 import format_for_training_v2

    train_path = Path("/workspace/team6/training_data/spec_train.json")
    val_path = Path("/workspace/team6/training_data/spec_val.json")
    # Changed: added test set path. Why: separate unbiased evaluation after HP selection on val.
    test_path = Path("/workspace/team6/training_data/spec_test.json")
    # Changed: mutation data path. Why: Type B data-level mutations for tc14/tc15/tc20.
    mutation_path = Path("/workspace/team6/training_data/mutation_cases.json")

    # Train: spec-based (869 spec + 20 public ground truth)
    all_cases = json.loads(train_path.read_text()) if train_path.exists() else []
    logger.info("Spec training data: %d cases", len(all_cases))

    # Changed: optionally load and merge mutation data.
    # Why: mutation data has targeted Type B examples (HostChallenge format, Read result, Activate target).
    if use_mutation and mutation_path.exists():
        mutation_cases = json.loads(mutation_path.read_text())
        logger.info("Mutation data: %d cases (p=%d, f=%d)",
                    len(mutation_cases),
                    sum(1 for c in mutation_cases if c["label"] == "pass"),
                    sum(1 for c in mutation_cases if c["label"] == "fail"))
        all_cases.extend(mutation_cases)
        logger.info("Combined training data: %d cases", len(all_cases))

    def _load_eval_set(path):
        cases = []
        if path.exists():
            data = json.loads(path.read_text())
            for c in data:
                cases.append({"steps": c["records"], "expected": c["label"]})
        return cases

    # Val: for HP selection during sweep (283 cases)
    val_cases_raw = _load_eval_set(val_path)
    # Test: for unbiased final evaluation only (283 cases)
    test_cases_raw = _load_eval_set(test_path)

    # Format training data
    train_data = []
    for case in all_cases:
        records = case["records"]
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue
        train_data.append(format_for_training_v2(records, case["label"]))

    logger.info("Train: %d | Val: %d (p=%d, f=%d) | Test: %d (p=%d, f=%d)",
                len(train_data),
                len(val_cases_raw),
                sum(1 for c in val_cases_raw if c["expected"] == "pass"),
                sum(1 for c in val_cases_raw if c["expected"] == "fail"),
                len(test_cases_raw),
                sum(1 for c in test_cases_raw if c["expected"] == "pass"),
                sum(1 for c in test_cases_raw if c["expected"] == "fail"))
    return train_data, val_cases_raw, test_cases_raw


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
    from tools.training.finetune_lora_v2 import format_trajectory_rich
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


def run_single(config: SweepConfig, train_data, val_cases, extra_eval=None, save_adapter=None):
    """Train one config, evaluate, return full result dict.

    Changed: added extra_eval parameter for evaluating on additional sets before GPU cleanup.
    Why: avoids retraining to evaluate on multiple sets (e.g., 50-epoch main training needs both val and test).

    Changed: added save_adapter parameter to save LoRA adapter weights before GPU cleanup.
    Why: sweep doesn't need to save (metrics only), but main training must save for submission.

    Args:
        extra_eval: optional dict of {set_name: cases_list}. Evaluated after primary val_cases.
                    Results stored in full_result["extra_eval"][set_name].
        save_adapter: optional path (str/Path) to save LoRA adapter + tokenizer. None = don't save.
    """
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
            # Changed: pass extra_eval and save_adapter through OOM retry.
            return run_single(config, train_data, val_cases,
                              extra_eval=extra_eval, save_adapter=save_adapter)  # retry
        raise
    train_time = time.time() - t0
    train_loss = train_result.training_loss

    logger.info("  train done: %.0fs, loss=%.4f", train_time, train_loss)

    metrics = evaluate_model(model, tokenizer, val_cases, config.max_length)
    logger.info("  RESULT: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f | tp=%d fp=%d fn=%d tn=%d",
                metrics["accuracy"] * 100, metrics["fail_precision"],
                metrics["fail_recall"], metrics["f1_fail"],
                metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"])

    # Changed: evaluate on additional sets before GPU cleanup.
    # Why: model is deleted after this block, so all evaluations must happen here.
    extra_results = {}
    if extra_eval:
        for set_name, cases in extra_eval.items():
            logger.info("  EXTRA EVAL [%s]: %d cases", set_name, len(cases))
            em = evaluate_model(model, tokenizer, cases, config.max_length)
            extra_results[set_name] = em
            logger.info("  RESULT [%s]: acc=%.1f%% prec=%.2f rec=%.2f f1=%.2f | tp=%d fp=%d fn=%d tn=%d",
                        set_name, em["accuracy"] * 100, em["fail_precision"],
                        em["fail_recall"], em["f1_fail"],
                        em["tp"], em["fp"], em["fn"], em["tn"])

    # Changed: save LoRA adapter before GPU cleanup if requested.
    # Why: model is deleted after this block. Must save here for submission use.
    if save_adapter:
        save_path = Path(save_adapter)
        save_path.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(save_path))
        tokenizer.save_pretrained(str(save_path))
        logger.info("  SAVED adapter to %s", save_path)

    full_result = {**asdict(config), **metrics,
                   "train_loss": round(train_loss, 5),
                   "train_time_s": round(train_time),
                   "trainable_params": trainable}
    if extra_results:
        full_result["extra_eval"] = extra_results
    if save_adapter:
        full_result["adapter_path"] = str(save_adapter)

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


# Changed: added pick_top_n for 2-phase sweep.
# Why: Phase 1 narrows candidates, Phase 2 tests interactions among top-N.
def pick_top_n(results, n=2, key="fail_recall", constraint_key="fail_precision", constraint_min=0.9):
    """Pick top N results by key, subject to constraint."""
    valid = [r for r in results if r.get(constraint_key, 0) >= constraint_min]
    if not valid:
        valid = results
    return sorted(valid, key=lambda r: r.get(key, 0), reverse=True)[:n]


def main():
    # Changed: 2-phase sweep replacing sequential-only approach.
    # Why: sequential sweep misses HP interactions (LR×rank, rank×dropout).
    # Phase 1 (5 ep): narrow candidates quickly.
    # Phase 2 (20 ep): focused grid on top candidates to capture interactions.
    logger.info("=" * 60)
    logger.info("2-PHASE LORA HYPERPARAMETER SWEEP")
    logger.info("Phase 1: sequential (5 ep) → narrow top-2 candidates")
    logger.info("Phase 2: grid search (20 ep) → capture HP interactions")
    logger.info("=" * 60)

    if RESULTS_PATH.exists():
        RESULTS_PATH.rename(RESULTS_PATH.with_suffix(".json.bak"))
    RESULTS_PATH.write_text("[]")

    base_config = SweepConfig()
    train_data, val_cases, test_cases = prepare_data(base_config)

    # ════════════════════════════════════════════════════════════
    # PHASE 1: Sequential sweep (5 epochs each) — narrow the range
    # ════════════════════════════════════════════════════════════
    P1_EPOCHS = 5
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1: Sequential sweep (%d epochs each)", P1_EPOCHS)
    logger.info("=" * 60)

    # ── P1-Step 1: LR Sweep ───────────────────────────────────
    logger.info("\n>>> P1-1: LR Sweep <<<")
    p1_lr_results = []
    for lr in [5e-5, 1e-4, 2e-4, 5e-4, 1e-3]:
        cfg = SweepConfig(lr=lr, num_epochs=P1_EPOCHS, run_name=f"p1_lr_{lr:.0e}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        p1_lr_results.append(r)
    top2_lr = pick_top_n(p1_lr_results, n=2)
    best_lr = top2_lr[0]["lr"]
    logger.info(">>> Top-2 LR: %s (recall: %s)",
                [r["lr"] for r in top2_lr],
                [r["fail_recall"] for r in top2_lr])

    # ── P1-Step 2: Rank Sweep (alpha = 2×rank) ───────────────
    logger.info("\n>>> P1-2: Rank Sweep <<<")
    p1_rank_results = []
    for rank in [4, 8, 16, 32, 64]:
        cfg = SweepConfig(lr=best_lr, lora_rank=rank, lora_alpha=rank * 2,
                          num_epochs=P1_EPOCHS, run_name=f"p1_r{rank}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        p1_rank_results.append(r)
    top2_rank = pick_top_n(p1_rank_results, n=2)
    best_rank = top2_rank[0]["lora_rank"]
    logger.info(">>> Top-2 rank: %s (recall: %s)",
                [r["lora_rank"] for r in top2_rank],
                [r["fail_recall"] for r in top2_rank])

    # ── P1-Step 3: max_length Sweep ───────────────────────────
    # max_length has weak interaction with other HPs → pick best 1, no grid.
    logger.info("\n>>> P1-3: max_length Sweep <<<")
    p1_ml_results = []
    for ml in [512, 1024, 2048]:
        cfg = SweepConfig(lr=best_lr, lora_rank=best_rank, lora_alpha=best_rank * 2,
                          max_length=ml, num_epochs=P1_EPOCHS,
                          run_name=f"p1_ml{ml}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        p1_ml_results.append(r)
    best_ml = pick_best(p1_ml_results)["max_length"]
    logger.info(">>> Best max_length: %d", best_ml)

    # ── P1-Step 4: Dropout Sweep ──────────────────────────────
    logger.info("\n>>> P1-4: Dropout Sweep <<<")
    p1_dropout_results = []
    for dropout in [0.0, 0.05, 0.1, 0.2]:
        cfg = SweepConfig(lr=best_lr, lora_rank=best_rank, lora_alpha=best_rank * 2,
                          max_length=best_ml, lora_dropout=dropout,
                          num_epochs=P1_EPOCHS, run_name=f"p1_d{dropout:.2f}")
        r = run_single(cfg, train_data, val_cases)
        save_result(r)
        p1_dropout_results.append(r)
    top2_dropout = pick_top_n(p1_dropout_results, n=2)
    logger.info(">>> Top-2 dropout: %s (recall: %s)",
                [r["lora_dropout"] for r in top2_dropout],
                [r["fail_recall"] for r in top2_dropout])

    logger.info("\n>>> Phase 1 Summary <<<")
    logger.info("  LR top-2:      %s", [r["lr"] for r in top2_lr])
    logger.info("  Rank top-2:    %s", [r["lora_rank"] for r in top2_rank])
    logger.info("  max_length:    %d (fixed)", best_ml)
    logger.info("  Dropout top-2: %s", [r["lora_dropout"] for r in top2_dropout])

    # ════════════════════════════════════════════════════════════
    # PHASE 2: Focused grid search (20 epochs each) — HP interactions
    # Grid: LR(2) × rank(2) × alpha_ratio(2) × dropout(2) = 16 runs
    # Changed: 20 epochs for reliable ranking (5 ep was too short for convergence).
    # Why: cosine scheduler at 5 ep means LR reaches ~0 before model converges.
    # At 20 ep, relative ranking better predicts 50-ep main training performance.
    # ════════════════════════════════════════════════════════════
    P2_EPOCHS = 20
    ALPHA_RATIOS = [2, 4]  # test standard vs aggressive scaling

    grid_configs = []
    for lr_r in top2_lr:
        for rank_r in top2_rank:
            for alpha_ratio in ALPHA_RATIOS:
                for dropout_r in top2_dropout:
                    grid_configs.append({
                        "lr": lr_r["lr"],
                        "rank": rank_r["lora_rank"],
                        "alpha": rank_r["lora_rank"] * alpha_ratio,
                        "alpha_ratio": alpha_ratio,
                        "dropout": dropout_r["lora_dropout"],
                    })

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: Grid search (%d epochs each, %d configs)", P2_EPOCHS, len(grid_configs))
    logger.info("  LR:          %s", sorted(set(c["lr"] for c in grid_configs)))
    logger.info("  Rank:        %s", sorted(set(c["rank"] for c in grid_configs)))
    logger.info("  Alpha ratio: %s", sorted(set(c["alpha_ratio"] for c in grid_configs)))
    logger.info("  Dropout:     %s", sorted(set(c["dropout"] for c in grid_configs)))
    logger.info("  max_length:  %d (fixed from P1)", best_ml)
    logger.info("=" * 60)

    # Changed: save every Phase 2 adapter for leaderboard submission during sweep.
    # Why: model is deleted after eval in run_single, so we must save before cleanup.
    # Each run saves to /workspace/team6/sweep_adapters/{run_name}/.
    # Best adapter is copied to artifacts/lora_adapter_v2/ for submission.
    ADAPTER_BASE = Path("/workspace/team6/sweep_adapters")
    SUBMIT_ADAPTER = Path("/workspace/team6/team6-opal-verifier/artifacts/lora_adapter_v2")
    best_p2_recall = -1.0
    best_p2_adapter_path = None
    p2_results = []
    for i, gc_ in enumerate(grid_configs):
        name = f"p2_{i:02d}_lr{gc_['lr']:.0e}_r{gc_['rank']}_a{gc_['alpha_ratio']}_d{gc_['dropout']:.2f}"
        adapter_path = str(ADAPTER_BASE / name)
        cfg = SweepConfig(
            lr=gc_["lr"], lora_rank=gc_["rank"], lora_alpha=gc_["alpha"],
            lora_dropout=gc_["dropout"], max_length=best_ml,
            num_epochs=P2_EPOCHS, run_name=name)
        try:
            r = run_single(cfg, train_data, val_cases, save_adapter=adapter_path)
            save_result(r)
            p2_results.append(r)

            # Track best and copy adapter to submission path
            cur_recall = r.get("fail_recall", 0)
            cur_prec = r.get("fail_precision", 0)
            if cur_recall > best_p2_recall and cur_prec >= 0.7:
                best_p2_recall = cur_recall
                best_p2_adapter_path = adapter_path
                # Copy best adapter to submission directory
                import shutil
                if SUBMIT_ADAPTER.exists():
                    shutil.rmtree(SUBMIT_ADAPTER)
                shutil.copytree(adapter_path, SUBMIT_ADAPTER)
                logger.info("  ★ NEW BEST: recall=%.2f prec=%.2f → copied to %s",
                            cur_recall, cur_prec, SUBMIT_ADAPTER)
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.warning("  OOM for %s, skipping", name)
                gc.collect()
                import torch; torch.cuda.empty_cache()
                time.sleep(10)
            else:
                raise

    best_p2 = pick_best(p2_results)
    logger.info("\n>>> Phase 2 Best: lr=%.1e rank=%d alpha=%d dropout=%.2f → recall=%.2f prec=%.2f",
                best_p2["lr"], best_p2["lora_rank"], best_p2["lora_alpha"],
                best_p2["lora_dropout"], best_p2["fail_recall"], best_p2["fail_precision"])

    # ── Final: Test evaluation (val + test) ───────────────────
    logger.info("\n>>> FINAL: Confirmation (val + test, %d ep) <<<", P2_EPOCHS)
    final_cfg = SweepConfig(
        lr=best_p2["lr"], lora_rank=best_p2["lora_rank"],
        lora_alpha=best_p2["lora_alpha"], lora_dropout=best_p2["lora_dropout"],
        max_length=best_ml, num_epochs=P2_EPOCHS,
        run_name="final_test")
    final_result = run_single(final_cfg, train_data, val_cases,
                              extra_eval={"test": test_cases})
    final_result["eval_set"] = "val"
    save_result(final_result)
    test_metrics = final_result.get("extra_eval", {}).get("test", {})

    # ── Summary ───────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("2-PHASE SWEEP COMPLETE")
    logger.info("  lr        = %.1e", best_p2["lr"])
    logger.info("  rank      = %d", best_p2["lora_rank"])
    logger.info("  alpha     = %d (ratio=%.1f)", best_p2["lora_alpha"],
                best_p2["lora_alpha"] / best_p2["lora_rank"])
    logger.info("  dropout   = %.2f", best_p2["lora_dropout"])
    logger.info("  max_length= %d", best_ml)
    logger.info("  val  recall = %.2f  prec = %.2f  (P2 selection basis)",
                final_result["fail_recall"], final_result["fail_precision"])
    logger.info("  test recall = %.2f  prec = %.2f  (unbiased estimate)",
                test_metrics.get("fail_recall", 0), test_metrics.get("fail_precision", 0))
    logger.info("=" * 60)

    best_cfg = {
        "model": "Qwen/Qwen3.5-4B", "lr": best_p2["lr"],
        "rank": best_p2["lora_rank"], "alpha": best_p2["lora_alpha"],
        "dropout": best_p2["lora_dropout"], "max_length": best_ml,
        "batch_size": best_p2.get("batch_size", 8),
        "grad_accum": best_p2.get("grad_accum", 1),
        "val_recall": final_result["fail_recall"],
        "val_precision": final_result["fail_precision"],
        "test_recall": test_metrics.get("fail_recall", 0),
        "test_precision": test_metrics.get("fail_precision", 0),
    }
    BEST_CONFIG_PATH.write_text(json.dumps(best_cfg, indent=2))
    logger.info("Saved to %s", BEST_CONFIG_PATH)
    logger.info("Run main training: python3 tools/training/sweep_lora.py --main")


def main_training():
    """50-epoch main training with best config from sweep.

    Changed: added --mutation flag to include mutation data for Type B coverage.
    Why: mutation data (Types F/G/H) covers HostChallenge format, Read result,
    and Activate target UID patterns needed for tc14/tc15/tc20.
    """
    use_mutation = "--mutation" in sys.argv

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

    suffix = "_mutation" if use_mutation else ""
    config = SweepConfig(
        model_name=model, lr=lr, lora_rank=rank, lora_alpha=alpha,
        lora_dropout=dropout, max_length=ml, batch_size=bs, grad_accum=ga,
        num_epochs=epochs, run_name=f"main_{epochs}ep{suffix}")

    # Changed: unpack 3 sets. Why: test set for unbiased final evaluation after main training.
    # Changed: pass use_mutation flag to include mutation data when specified.
    train_data, val_cases, test_cases = prepare_data(config, use_mutation=use_mutation)

    # Changed: single training run, evaluate on both val and test, save adapter for submission.
    # Why: avoids training 50 epochs twice. Adapter saved to artifacts/ for lora_solver.py to load.
    # Changed: save to separate path for mutation training to avoid overwriting existing adapter.
    adapter_save_path = "/workspace/team6/team6-opal-verifier/artifacts/lora_adapter_v2"
    if use_mutation:
        adapter_save_path = "/workspace/team6/adapters/mutation_4b_v2/final"
    logger.info(">>> Main training: %d epochs, mutation=%s, eval on val + test, save to %s <<<",
                epochs, use_mutation, adapter_save_path)
    result = run_single(config, train_data, val_cases,
                        extra_eval={"test": test_cases},
                        save_adapter=adapter_save_path)
    result["eval_set"] = "val"
    save_result(result)

    test_metrics = result.get("extra_eval", {}).get("test", {})

    logger.info("=" * 60)
    logger.info("MAIN TRAINING COMPLETE")
    logger.info("  val  recall = %.2f  prec = %.2f", result["fail_recall"], result["fail_precision"])
    logger.info("  test recall = %.2f  prec = %.2f  (unbiased)",
                test_metrics.get("fail_recall", 0), test_metrics.get("fail_precision", 0))
    logger.info("=" * 60)


if __name__ == "__main__":
    if "--main" in sys.argv:
        main_training()
    else:
        main()
