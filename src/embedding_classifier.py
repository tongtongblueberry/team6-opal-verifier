# Changed: implement embedding-based binary classifier per Buckmann & Hill (2024).
# Why: all previous approaches (logit, generation, status prediction) achieved fail recall ≤ 20%.
# The paper shows that LLM embedding + ridge regression achieves GPT-4 level accuracy
# with just 10 samples per class — we have exactly 10 pass + 10 fail public cases.
#
# Buckmann, M., & Hill, E. (2024). Logistic Regression makes small LLMs strong and
# explainable "tens-of-shot" classifiers. arXiv:2408.03414.
#
# Architecture:
#   Trajectory → Prompt → LLM → Penultimate Layer Embedding (4096 dim)
#                                          ↓
#   20 labeled embeddings → Ridge Regression (sklearn) → Binary Classifier
#                                          ↓
#   New case embedding → predict pass/fail

from __future__ import annotations

import json
import logging
import os
import re
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

Json = dict[str, Any]


def _extract_field(record: Json, name: str) -> str:
    for key in (name, name.lower(), name.capitalize()):
        val = record.get(key)
        if isinstance(val, dict):
            return str(val.get("Name", val.get("name", val)))
        elif val is not None:
            return str(val)
    return ""


def format_trajectory_for_embedding(records: list[Json]) -> str:
    """Format trajectory into a prompt for embedding extraction.

    Changed: following Buckmann & Hill (2024), wrap text with contextualizing
    prefix and suffix. The suffix asks for a classification decision so the
    embedding captures the model's internal representation of the answer.
    """
    if not records:
        return ""

    lines: list[str] = []
    for i, step in enumerate(records):
        if not isinstance(step, dict):
            continue
        cmd = step.get("input", {})
        out = step.get("output", {})
        method = _extract_field(cmd, "Method") or _extract_field(cmd, "method")
        inv = _extract_field(cmd, "InvokingID") or _extract_field(cmd, "invokingID")
        status = _extract_field(out, "Status") or _extract_field(out, "status")
        prefix = "[FINAL] " if i == len(records) - 1 else ""
        lines.append(f"{prefix}Step {i}: {method}({inv}) -> {status}")

    trajectory_text = "\n".join(lines)

    # Changed: prompt format from Buckmann & Hill (2024) Section 2.1
    # Prefix: task description. Text: trajectory. Suffix: question + options.
    prompt = (
        "The following is an SSD TCG/Opal command-response trajectory. "
        "The last response may or may not be consistent with the protocol specification.\n\n"
        f"{trajectory_text}\n\n"
        "Is the final response consistent with the specification? "
        "(a) pass (b) fail\n"
        "Answer: ("
    )
    return prompt


class EmbeddingClassifier:
    """LLM Embedding + Ridge Regression binary classifier.

    Buckmann & Hill (2024): penultimate layer embedding + ridge regression
    achieves GPT-4 level accuracy with 10 samples per class.

    Steps:
    1. Load a small LLM (4B/9B)
    2. Extract penultimate layer embeddings for each trajectory
    3. Train ridge regression on 20 public labeled cases
    4. Predict new cases
    """

    def __init__(
        self,
        model_name: str | None = None,
        dataset_root: str | Path | None = None,
    ) -> None:
        self.model: Any = None
        self.tokenizer: Any = None
        self.classifier: Any = None  # sklearn Ridge classifier
        self._embedding_dim: int = 0
        self._model_name = model_name or os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")

        # Load model
        self._load_model()

        # Changed: try to load pre-trained classifier from artifacts/ first.
        # Why: project.pdf allows artifacts/ with trained model weights.
        # The classifier trained on 2163 cases (tools/train_embedding_classifier.py)
        # is saved to artifacts/embedding_classifier.pkl. Loading it avoids
        # retraining on just 20 public cases at evaluation time.
        artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
        pkl_path = artifacts_dir / "embedding_classifier.pkl"
        if pkl_path.exists():
            self._load_pretrained(pkl_path)
        else:
            # Fallback: train on public labeled data
            if dataset_root is None:
                dataset_root = Path(os.environ.get("RAG_FEWSHOT_ROOT", "/dl2026/dataset"))
            else:
                dataset_root = Path(dataset_root)
            self._train_classifier(dataset_root)

    def _load_model(self) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info("Loading embedding model %s ...", self._model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(
                self._model_name, trust_remote_code=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                torch_dtype="auto",
                device_map="auto",
                trust_remote_code=True,
                output_hidden_states=True,  # Need hidden states for embedding
            )
            self.model.eval()

            # Get embedding dimension from model config
            self._embedding_dim = self.model.config.hidden_size
            logger.info("Model loaded. embedding_dim=%d", self._embedding_dim)
        except Exception as exc:
            logger.warning("Failed to load embedding model: %s", exc)
            self.model = None
            self.tokenizer = None

    def _load_pretrained(self, pkl_path: Path) -> None:
        """Load pre-trained classifier from artifacts/."""
        import pickle
        try:
            with pkl_path.open("rb") as f:
                data = pickle.load(f)
            self.classifier = data["classifier"]
            logger.info("Loaded pre-trained classifier from %s (n_train=%d, cv_acc=%.3f)",
                        pkl_path, data.get("n_train", 0), data.get("cv_accuracy", 0))
        except Exception as exc:
            logger.warning("Failed to load pre-trained classifier: %s", exc)

    @property
    def available(self) -> bool:
        return self.model is not None and self.classifier is not None

    def _extract_embedding(self, text: str) -> Any:
        """Extract penultimate layer embedding from the LLM.

        Changed: extract final hidden state of the last token from the penultimate layer.
        Why: Buckmann & Hill (2024) use "final layer activations before the prediction head".
        For causal LLMs, the last token's hidden state is the most informative for next-token
        prediction and thus classification.
        """
        import torch

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)

        # Changed: use the last hidden state (before lm_head) of the last token.
        # Why: this is the "penultimate layer" in Buckmann & Hill's terminology.
        # hidden_states[-1] is the final transformer layer output.
        last_hidden = outputs.hidden_states[-1]  # (batch, seq_len, hidden_dim)
        last_token_embedding = last_hidden[0, -1, :].cpu().float().numpy()  # (hidden_dim,)

        return last_token_embedding

    def _train_classifier(self, dataset_root: Path) -> None:
        """Train ridge regression on public labeled cases.

        Changed: implement Buckmann & Hill (2024) Section 2.3.
        Why: ridge regression on LLM embeddings achieves 0.80 mean accuracy
        across 17 tasks with just 100 samples. We have 20 samples.
        """
        if self.model is None:
            return

        testcase_dir = dataset_root / "testcases"
        label_path = dataset_root / "label.jsonl"
        if not testcase_dir.exists() or not label_path.exists():
            logger.info("Training data not found at %s — classifier not trained.", dataset_root)
            return

        # Load labels
        labels: dict[str, str] = {}
        with label_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                labels[rec["filename"]] = str(rec["label"]).strip().lower()

        # Extract embeddings for each case
        embeddings: list[Any] = []
        ys: list[int] = []

        for path in sorted(testcase_dir.glob("tc*.json"),
                           key=lambda p: int(p.stem.removeprefix("tc").split("_")[0])):
            label = labels.get(path.name)
            if label is None:
                continue
            with path.open() as f:
                steps = json.load(f)
            if isinstance(steps, dict) and "records" in steps:
                steps = steps["records"]
            if not isinstance(steps, list):
                continue
            records = [item for item in steps if isinstance(item, dict)]
            if not records:
                continue

            prompt = format_trajectory_for_embedding(records)
            emb = self._extract_embedding(prompt)
            embeddings.append(emb)
            ys.append(1 if label == "fail" else 0)

        if len(embeddings) < 4:
            logger.warning("Not enough training data (%d cases). Need at least 4.", len(embeddings))
            return

        X = np.stack(embeddings)  # (N, hidden_dim)
        y = np.array(ys)

        logger.info("Training ridge classifier on %d cases (pass=%d, fail=%d), dim=%d",
                     len(y), (y == 0).sum(), (y == 1).sum(), X.shape[1])

        # Changed: ridge regression per Buckmann & Hill (2024).
        # Why: L2 regularization is optimal for high-dimensional embeddings with few samples.
        # Paper uses R glmnet; we use sklearn LogisticRegression with L2 (equivalent).
        from sklearn.linear_model import LogisticRegression

        self.classifier = LogisticRegression(
            penalty="l2",
            C=1.0,  # inverse of lambda; paper uses lowest regularization
            solver="lbfgs",
            max_iter=1000,
        )
        self.classifier.fit(X, y)

        # Cross-validation accuracy estimate
        from sklearn.model_selection import cross_val_score
        cv_k = min(len(y), 10)
        if cv_k >= 2:
            scores = cross_val_score(self.classifier, X, y, cv=cv_k, scoring="accuracy")
            logger.info("Ridge CV accuracy: %.3f ± %.3f (k=%d)", scores.mean(), scores.std(), cv_k)

    def predict(self, records: list[Json]) -> str:
        """Predict pass/fail for a trajectory using embedding + ridge regression."""
        if not self.available:
            return "pass"

        prompt = format_trajectory_for_embedding(records)
        emb = self._extract_embedding(prompt)
        pred = self.classifier.predict(emb.reshape(1, -1))[0]
        proba = self.classifier.predict_proba(emb.reshape(1, -1))[0]

        label = "fail" if pred == 1 else "pass"
        logger.info("Embedding classifier: pred=%s proba=[pass=%.3f, fail=%.3f]",
                     label, proba[0], proba[1])
        return label
