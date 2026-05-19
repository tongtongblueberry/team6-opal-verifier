# Changed: LoRA-based solver for UNEXPECTED_ERROR_STATUS override.
# Why: rule engine aggressively marks unexplained errors as fail. LoRA can selectively correct.
# Changed: removed v1 format/adapter support. Why: v1 (0.8B, compressed) had 0% fail recall.
# Only v2 (4B, rich format) is used.

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

Json = dict[str, Any]

SYSTEM_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory with session state, "
    "determine if the final response is consistent with the specification. "
    "Answer exactly: pass or fail"
)


class LoRASolver:
    """Fine-tuned LoRA model for pass/fail classification."""

    def __init__(self, adapter_path: str | None = None, base_model: str | None = None):
        self.model = None
        self.tokenizer = None
        self.available = False

        root = Path(__file__).resolve().parents[1]
        if adapter_path is None:
            adapter_dir = root / "artifacts" / "lora_adapter_v2"
            if adapter_dir.exists() and (adapter_dir / "adapter_config.json").exists():
                adapter_path = str(adapter_dir)
            else:
                logger.info("No LoRA adapter found in artifacts/lora_adapter_v2/")
                return

        if base_model is None:
            base_model = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")

        try:
            self._load(adapter_path, base_model)
        except Exception as e:
            logger.warning("Failed to load LoRA model: %s", e)

    def _load(self, adapter_path: str, base_model: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        t0 = time.time()
        logger.info("Loading LoRA: base=%s, adapter=%s", base_model, adapter_path)

        self.tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        self.model = PeftModel.from_pretrained(self.model, adapter_path)
        self.model.eval()
        self.available = True

        logger.info("LoRA model loaded in %.1fs", time.time() - t0)

    def predict(self, records: list[Json], trace: list[Json] | None = None) -> str:
        # Changed: switched from generation to logit comparison.
        # Why: generation produces random trajectory text instead of "pass"/"fail".
        # Logit comparison directly compares P(pass) vs P(fail) at the next token — matches sweep evaluation.
        """Predict pass/fail using logit comparison (not generation)."""
        if not self.available or not records:
            return "pass"

        import math
        import torch
        from tools.training.finetune_lora_v2 import format_trajectory_rich

        prompt = format_trajectory_rich(records)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = self.model(**inputs).logits[0, -1, :]

        # Changed: compare logits for "pass" vs "fail" tokens directly.
        # Why: this matches sweep_lora.py evaluate_model() — same method that achieved 80%+ val acc.
        pass_ids = self.tokenizer.encode("pass", add_special_tokens=False)
        fail_ids = self.tokenizer.encode("fail", add_special_tokens=False)
        p_logit = logits[pass_ids[0]].item()
        f_logit = logits[fail_ids[0]].item()

        mx = max(p_logit, f_logit)
        p_fail = math.exp(f_logit - mx) / (math.exp(p_logit - mx) + math.exp(f_logit - mx))

        return "fail" if p_fail > 0.5 else "pass"
