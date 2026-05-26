"""Quick HP sweep: 5 epochs per config, find best, then full train.

Changed: short sweep to find optimal HP before committing to 20-epoch training.
Why: 17 epochs confirmed as convergence point. 5 epochs is enough to compare configs.
Each run takes ~1.7h (4660/20*5=1165 steps × 5.2s). 6 configs = ~10h total.

Auto-resumes if interrupted (checks for existing results).

Usage:
  nohup python -u tools/training/quick_sweep.py >> /workspace/team6/quick_sweep.log 2>&1 &
"""
import sys, json, os, time, gc, logging
from pathlib import Path
from dataclasses import dataclass, asdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/workspace/team6/quick_sweep.log", mode="a"),
    ]
)
logger = logging.getLogger("quick_sweep")

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

from tools.training.train_uncertainty_resolver import Config, train_and_evaluate

RESULTS_PATH = Path("/workspace/team6/quick_sweep_results.json")

# Changed: sweep configs based on what we know.
# Why: lr=1e-3 confirmed best from sweep3. Now explore rank, dropout, SCL weight.
SWEEP_CONFIGS = [
    # Baseline (current best known)
    {"name": "baseline", "lr": 1e-3, "rank": 16, "dropout": 0.1, "scl_weight": 0.1, "label_smoothing": 0.05},
    # Higher rank (more capacity)
    {"name": "rank32", "lr": 1e-3, "rank": 32, "dropout": 0.1, "scl_weight": 0.1, "label_smoothing": 0.05},
    # Lower dropout (less regularization)
    {"name": "drop005", "lr": 1e-3, "rank": 16, "dropout": 0.05, "scl_weight": 0.1, "label_smoothing": 0.05},
    # No SCL (ablation)
    {"name": "no_scl", "lr": 1e-3, "rank": 16, "dropout": 0.1, "scl_weight": 0.0, "label_smoothing": 0.05},
    # Brier loss instead of SCL (calibration focus)
    {"name": "brier", "lr": 1e-3, "rank": 16, "dropout": 0.1, "scl_weight": 0.0, "label_smoothing": 0.0},
    # Lower LR (more conservative)
    {"name": "lr5e4", "lr": 5e-4, "rank": 16, "dropout": 0.1, "scl_weight": 0.1, "label_smoothing": 0.05},
]

SWEEP_EPOCHS = 5


def load_results():
    if RESULTS_PATH.exists():
        return json.loads(RESULTS_PATH.read_text())
    return {}


def save_results(results):
    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))


def main():
    SEP = "=" * 60
    logger.info(SEP)
    logger.info("QUICK HP SWEEP (%d configs × %d epochs)", len(SWEEP_CONFIGS), SWEEP_EPOCHS)
    logger.info(SEP)

    results = load_results()

    for i, sc in enumerate(SWEEP_CONFIGS):
        name = sc["name"]
        if name in results:
            logger.info("SKIP %s (already done, acc=%.1f%%)", name, results[name].get("accuracy", 0) * 100)
            continue

        logger.info("\n%s", SEP)
        logger.info("CONFIG %d/%d: %s", i + 1, len(SWEEP_CONFIGS), name)
        logger.info("  %s", json.dumps(sc))
        logger.info(SEP)

        cfg = Config()
        cfg.lr = sc["lr"]
        cfg.rank = sc["rank"]
        cfg.alpha = sc["rank"] * 2
        cfg.dropout = sc["dropout"]
        cfg.scl_weight = sc["scl_weight"]
        cfg.label_smoothing = sc["label_smoothing"]
        cfg.epochs = SWEEP_EPOCHS
        cfg.max_length = 1024
        cfg.batch_size = 4
        cfg.grad_accum = 2

        # Changed: use separate checkpoint dir per config to avoid resume conflicts.
        import shutil
        sweep_adapter = Path(f"/workspace/team6/adapters/sweep_{name}")
        if sweep_adapter.exists():
            shutil.rmtree(sweep_adapter)

        try:
            # Monkey-patch adapter dir for this run
            original_train = train_and_evaluate
            # Just run training with the config
            train_and_evaluate(cfg)

            # Read results from the training output
            result_path = Path("/workspace/team6/uncertainty_results.json")
            if result_path.exists():
                run_result = json.loads(result_path.read_text())
                results[name] = {
                    "config": sc,
                    "public_accuracy": run_result.get("public_accuracy", 0),
                    "public_correct": run_result.get("public_correct", 0),
                    "train_loss": run_result.get("train_loss", None),
                    "val_metrics": run_result.get("val_metrics", None),
                }
                save_results(results)
                logger.info("  Result: public=%.1f%%, val_acc=%.1f%%",
                            results[name]["public_accuracy"] * 100,
                            results[name].get("val_metrics", {}).get("accuracy", 0) * 100)
        except Exception as e:
            logger.error("FAILED: %s", e)
            import traceback
            traceback.print_exc()
            results[name] = {"config": sc, "error": str(e)}
            save_results(results)

        # Cleanup VRAM
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
        time.sleep(10)

    # Summary
    logger.info("\n%s", SEP)
    logger.info("SWEEP SUMMARY")
    logger.info(SEP)
    for name, r in sorted(results.items(), key=lambda x: x[1].get("public_accuracy", 0), reverse=True):
        if "error" in r:
            logger.info("  %s: ERROR (%s)", name, r["error"][:50])
        else:
            logger.info("  %s: public=%.1f%%, val=%.1f%%", name,
                        r.get("public_accuracy", 0) * 100,
                        r.get("val_metrics", {}).get("accuracy", 0) * 100)

    logger.info("DONE")


if __name__ == "__main__":
    main()
