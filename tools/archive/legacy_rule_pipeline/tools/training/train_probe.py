"""Train hidden state probe: extract LLM features → logistic regression.

Pipeline:
1. Load frozen LLM (Qwen3.5-4B)
2. Run each training case through LLM, extract last hidden state
3. Train sklearn LogisticRegression on (hidden_state, label) pairs
4. Save probe to artifacts/probe_classifier.pkl
5. Evaluate on val + public 20

Key advantage: no fine-tuning needed. The frozen LLM's hidden states encode
protocol understanding from pre-training. Logistic regression learns the
decision boundary with as few as 20 examples.

Usage:
  nohup python -u tools/training/train_probe.py >> /workspace/team6/probe_train.log 2>&1 &
"""
import sys, json, os, time, pickle, logging, glob
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("train_probe")


def extract_all_features(probe_solver, cases, label_key="label"):
    """Extract features for all cases."""
    features = []
    labels = []
    skipped = 0

    for i, case in enumerate(cases):
        records = case.get("records", case.get("steps", []))
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            skipped += 1
            continue

        # Wrap as steps format
        steps = [{"input": r.get("input", {}), "output": r.get("output", {})} for r in records]
        feat = probe_solver.extract_features(steps)
        if feat is not None:
            features.append(feat)
            label = case.get(label_key, "pass")
            labels.append(1 if label == "fail" else 0)

        if (i + 1) % 50 == 0:
            logger.info("  Extracted %d/%d features", i + 1, len(cases))

    if skipped:
        logger.warning("Skipped %d cases (no records)", skipped)

    return np.array(features), np.array(labels)


def main():
    from src.probe_solver import ProbeSolver
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, accuracy_score

    SEP = "=" * 60
    logger.info(SEP)
    logger.info("HIDDEN STATE PROBE TRAINING")
    logger.info(SEP)

    # Initialize probe solver (frozen LLM)
    model_name = os.environ.get("PROBE_MODEL", "Qwen/Qwen3.5-4B")
    probe = ProbeSolver(model_name)

    # Load training data
    data_dir = Path("/workspace/team6/training_data")
    train_cases = []
    for p in ["spec_train.json", "gap_cases.json"]:
        path = data_dir / p
        if path.exists():
            cases = json.loads(path.read_text())
            logger.info("Loaded %s: %d cases", p, len(cases))
            train_cases.extend(cases)

    # Load public 20 (most valuable — real distribution)
    pub_labels = {}
    label_path = Path("/dl2026/dataset/label.jsonl")
    if label_path.exists():
        for line in open(label_path):
            d = json.loads(line)
            pub_labels[d["filename"]] = d["label"]

    pub_cases = []
    for tc_file in sorted(glob.glob("/dl2026/dataset/testcases/tc*.json")):
        fname = os.path.basename(tc_file)
        if fname in pub_labels:
            steps = json.load(open(tc_file))
            pub_cases.append({"steps": steps, "label": pub_labels[fname]})

    logger.info("Public cases: %d", len(pub_cases))

    # Load val data
    val_path = data_dir / "spec_val.json"
    val_cases = json.loads(val_path.read_text()) if val_path.exists() else []

    # Extract features
    logger.info("\nExtracting training features...")
    t0 = time.time()
    X_train, y_train = extract_all_features(probe, train_cases)
    logger.info("Training: %d features in %.0fs", len(X_train), time.time() - t0)

    logger.info("\nExtracting public features...")
    X_pub, y_pub = extract_all_features(probe, pub_cases)
    logger.info("Public: %d features", len(X_pub))

    # Combine: synthetic + public (public upsampled 10x)
    if len(X_pub) > 0:
        X_combined = np.vstack([X_train] + [X_pub] * 10)
        y_combined = np.concatenate([y_train] + [y_pub] * 10)
    else:
        X_combined = X_train
        y_combined = y_train

    logger.info("Combined: %d features (train=%d + pub×10=%d)",
                len(X_combined), len(X_train), len(X_pub) * 10)

    # Train logistic regression
    logger.info("\nTraining logistic regression...")
    clf = LogisticRegression(
        C=1.0, max_iter=1000, class_weight="balanced",
        solver="lbfgs", random_state=42)
    clf.fit(X_combined, y_combined)
    logger.info("Train accuracy: %.1f%%", accuracy_score(y_combined, clf.predict(X_combined)) * 100)

    # Evaluate on val
    if val_cases:
        logger.info("\nExtracting val features...")
        X_val, y_val = extract_all_features(probe, val_cases)
        if len(X_val) > 0:
            val_pred = clf.predict(X_val)
            logger.info("Val accuracy: %.1f%%", accuracy_score(y_val, val_pred) * 100)
            logger.info("\n%s", classification_report(y_val, val_pred, target_names=["pass", "fail"]))

    # Evaluate on public 20
    if len(X_pub) > 0:
        pub_pred = clf.predict(X_pub)
        pub_proba = clf.predict_proba(X_pub)[:, 1]
        logger.info("\nPublic 20 results:")
        for i, case in enumerate(pub_cases):
            gold = case["label"]
            pred = "fail" if pub_pred[i] == 1 else "pass"
            ok = pred == gold
            logger.info("  %s: gold=%s pred=%s p_fail=%.3f %s",
                        os.path.basename(glob.glob("/dl2026/dataset/testcases/tc*.json")[i]),
                        gold, pred, pub_proba[i], "OK" if ok else "ERR")
        pub_acc = accuracy_score(y_pub, pub_pred)
        logger.info("Public accuracy: %.1f%%", pub_acc * 100)

    # Save probe
    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    probe_path = artifact_dir / "probe_classifier.pkl"
    probe_path.write_bytes(pickle.dumps(clf))
    logger.info("\nSaved probe to %s", probe_path)

    # Cleanup
    del probe
    import gc
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    logger.info("DONE")


if __name__ == "__main__":
    main()
