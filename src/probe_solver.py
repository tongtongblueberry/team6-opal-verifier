"""Hidden State Probe Solver: LLM as feature extractor + logistic regression.

Changed: completely new approach — instead of using LLM to generate pass/fail,
extract the hidden state from the last token and classify with a trained probe.

Why: LoRA logit comparison and generation both failed 8 consecutive times.
The LLM's vocabulary logits for "pass"/"fail" are a tiny fraction of what the
model internally "knows." Hidden states capture richer protocol understanding.

Papers:
- "Probing Hidden States for Calibrated Predictions in LLMs" (2025)
- "Fine-Tuning Causal LLMs: Embedding-Based vs Instruction-Based" (2025)

Architecture:
1. Feed trajectory through frozen LLM (Qwen3.5-4B or 9B)
2. Extract hidden state at last token position (4096-dim vector)
3. Classify with logistic regression trained on labeled data
4. Use ONLY for LOW confidence cases (rule engine handles the rest)

Training: only needs 20 public cases + synthetic data → no distribution mismatch
issue because the probe learns from the LLM's internal representation, not from
generated text.
"""
from __future__ import annotations

import json
import logging
import math
import os
import pickle
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)
Json = dict[str, Any]


class ProbeSolver:
    """LLM hidden state + logistic regression classifier."""

    def __init__(self, model_name: str | None = None):
        self.model = None
        self.tokenizer = None
        self.probe = None
        self.available = False

        if model_name is None:
            model_name = os.environ.get("PROBE_MODEL", "Qwen/Qwen3.5-4B")

        try:
            self._load(model_name)
        except Exception as e:
            logger.warning("Probe solver failed to load: %s", e)

    def _load(self, model_name: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        t0 = time.time()
        logger.info("Loading probe solver: %s", model_name)

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="auto",
            trust_remote_code=True, output_hidden_states=True)
        self.model.eval()

        # Load trained probe if available
        root = Path(__file__).resolve().parents[1]
        probe_path = root / "artifacts" / "probe_classifier.pkl"
        if probe_path.exists():
            self.probe = pickle.loads(probe_path.read_bytes())
            logger.info("Loaded probe classifier from %s", probe_path)
        else:
            logger.warning("No probe classifier found at %s — will extract features only", probe_path)

        self.available = True
        logger.info("Probe solver loaded in %.1fs", time.time() - t0)

    def extract_features(self, steps: list[Json], system_prompt: str = "") -> np.ndarray | None:
        """Extract hidden state from last token as feature vector."""
        if not self.available:
            return None

        import torch
        from src.llm_solver import extract_relevant_steps, SYSTEM_PROMPT

        # Filter trajectory
        relevant = extract_relevant_steps(steps)
        content = json.dumps(relevant, ensure_ascii=False, indent=1)
        note = f"(Showing {len(relevant)} of {len(steps)} steps)"

        prompt = system_prompt or SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Trajectory {note}:\n{content}\n\nVerdict:"},
        ]

        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(next(self.model.parameters()).device) for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs, output_hidden_states=True)

        # Extract last layer, last token hidden state
        last_hidden = outputs.hidden_states[-1]  # (1, seq_len, hidden_dim)
        seq_len = inputs["attention_mask"].sum().item()
        features = last_hidden[0, seq_len - 1, :].cpu().float().numpy()  # (hidden_dim,)

        return features

    def predict(self, steps: list[Json], rule_context: dict | None = None) -> str:
        """Predict pass/fail using hidden state probe."""
        if not self.available or self.probe is None:
            return "pass"  # safe default

        features = self.extract_features(steps)
        if features is None:
            return "pass"

        # Classify with trained probe
        prediction = self.probe.predict(features.reshape(1, -1))[0]
        return "fail" if prediction == 1 else "pass"

    def predict_proba(self, steps: list[Json]) -> float:
        """Return P(fail) from probe classifier."""
        if not self.available or self.probe is None:
            return 0.5

        features = self.extract_features(steps)
        if features is None:
            return 0.5

        proba = self.probe.predict_proba(features.reshape(1, -1))[0]
        return float(proba[1])  # P(fail)
