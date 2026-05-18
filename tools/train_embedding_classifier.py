# Changed: extract embeddings from LLM and train ridge regression classifier.
# Why: Buckmann & Hill (2024) showed embedding + ridge = GPT-4 level with 10-shot.
# We have 2163 training cases → expect even better performance.
# Save trained classifier to artifacts/ for submission.

from __future__ import annotations
import json, sys, os, pickle, time, logging
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    model_name = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")

    training_path = Path("/workspace/team6/training_data/training_cases.json")
    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading training data from %s", training_path)
    cases = json.loads(training_path.read_text())
    logger.info("Training cases: %d (pass=%d, fail=%d)",
                len(cases),
                sum(1 for c in cases if c["label"] == "pass"),
                sum(1 for c in cases if c["label"] == "fail"))

    # Load model for embedding extraction
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from src.embedding_classifier import format_trajectory_for_embedding

    logger.info("Loading model %s...", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
        output_hidden_states=True,
    )
    model.eval()
    hidden_dim = model.config.hidden_size
    logger.info("Model loaded. hidden_dim=%d", hidden_dim)

    # Extract embeddings
    embeddings = []
    labels = []
    t0 = time.time()

    for i, case in enumerate(cases):
        records = case["records"]
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue

        prompt = format_trajectory_for_embedding(records)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)

        # Penultimate layer, last token
        last_hidden = outputs.hidden_states[-1]
        emb = last_hidden[0, -1, :].cpu().float().numpy()
        embeddings.append(emb)
        labels.append(1 if case["label"] == "fail" else 0)

        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(cases) - i - 1)
            logger.info("  %d/%d embeddings (%.0fs elapsed, ETA %.0fs)",
                        i + 1, len(cases), elapsed, eta)

    X = np.stack(embeddings)
    y = np.array(labels)
    logger.info("Embeddings: shape=%s, labels: pass=%d fail=%d",
                X.shape, (y == 0).sum(), (y == 1).sum())

    # Save embeddings for reuse
    emb_path = Path("/workspace/team6/training_data/embeddings.npz")
    np.savez_compressed(str(emb_path), X=X, y=y)
    logger.info("Embeddings saved to %s (%.1f MB)", emb_path, emb_path.stat().st_size / 1e6)

    # Train ridge regression classifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score

    logger.info("Training ridge regression...")
    clf = LogisticRegression(
        penalty="l2",
        C=1.0,
        solver="lbfgs",
        max_iter=1000,
        class_weight="balanced",  # handle class imbalance
    )
    clf.fit(X, y)

    # Cross-validation
    cv_scores = cross_val_score(clf, X, y, cv=10, scoring="accuracy")
    logger.info("CV accuracy: %.3f ± %.3f", cv_scores.mean(), cv_scores.std())

    from sklearn.metrics import classification_report
    y_pred = clf.predict(X)
    print("\n=== Training Set Classification Report ===")
    print(classification_report(y, y_pred, target_names=["pass", "fail"]))

    # Save classifier
    clf_path = artifacts_dir / "embedding_classifier.pkl"
    with clf_path.open("wb") as f:
        pickle.dump({
            "classifier": clf,
            "model_name": model_name,
            "hidden_dim": hidden_dim,
            "n_train": len(y),
            "cv_accuracy": float(cv_scores.mean()),
        }, f)
    logger.info("Classifier saved to %s (%.1f KB)", clf_path, clf_path.stat().st_size / 1e3)

    print(f"\n=== TRAINING COMPLETE ===")
    print(f"Model: {model_name}")
    print(f"Training cases: {len(y)} (pass={int((y==0).sum())}, fail={int((y==1).sum())})")
    print(f"CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
    print(f"Classifier: {clf_path}")
    print(f"Total time: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
