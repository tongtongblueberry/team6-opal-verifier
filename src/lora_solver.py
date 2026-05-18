# Changed: LoRA-based solver for DEFAULT_PASS cases.
# Why: zero-shot/few-shot LLM approaches all failed (fail recall ≤ 20%).
# Fine-tuned LoRA model can learn task-specific patterns from 2163 training examples.
# Papers: TOGLL (ASE 2024) shows fine-tuned small models beat large zero-shot 3.8x.
#
# Integration: Solver class loads LoRA adapter from artifacts/ and uses it
# for DEFAULT_PASS cases instead of (or alongside) RAG.

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

Json = dict[str, Any]


class LoRASolver:
    """Fine-tuned LoRA model for pass/fail classification of DEFAULT_PASS cases."""

    def __init__(self, adapter_path: str | None = None, base_model: str | None = None):
        self.model = None
        self.tokenizer = None
        self.available = False
        self._format_version = "v1"  # default; overridden if v2 adapter exists

        # Changed: auto-detect adapter path from artifacts/.
        root = Path(__file__).resolve().parents[1]
        if adapter_path is None:
            # Try v2 first, then v1
            v2_path = root / "artifacts" / "lora_adapter_v2"
            v1_path = root / "artifacts" / "lora_adapter"
            if v2_path.exists() and (v2_path / "adapter_config.json").exists():
                adapter_path = str(v2_path)
                self._format_version = "v2"
            elif v1_path.exists() and (v1_path / "adapter_config.json").exists():
                adapter_path = str(v1_path)
                self._format_version = "v1"
            else:
                logger.info("No LoRA adapter found in artifacts/")
                return

        if base_model is None:
            # Changed: default to 4B for v2 adapter, 0.8B for v1.
            # Why: 4B v2 achieves fail precision=100% on synthetic test set.
            if self._format_version == "v2":
                base_model = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")
            else:
                base_model = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-0.8B")

        try:
            self._load(adapter_path, base_model)
        except Exception as e:
            logger.warning("Failed to load LoRA model: %s", e)

    def _load(self, adapter_path: str, base_model: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        t0 = time.time()
        logger.info("Loading LoRA: base=%s, adapter=%s, format=%s",
                     base_model, adapter_path, self._format_version)

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

    def _format_records(self, records: list[Json]) -> str:
        """Format records using the appropriate version."""
        if self._format_version == "v2":
            from tools.finetune_lora_v2 import format_trajectory_rich
            return format_trajectory_rich(records)
        else:
            from src.embedding_classifier import format_trajectory_for_embedding
            prompt = format_trajectory_for_embedding(records)
            prompt = prompt.rstrip("(").rstrip()
            if prompt.endswith("Answer:"):
                prompt = prompt[:-len("Answer:")].rstrip()
            return prompt

    def _get_system_prompt(self) -> str:
        if self._format_version == "v2":
            return (
                "You are a TCG/Opal SSD protocol compliance verifier. "
                "Given a command-response trajectory with session state, "
                "determine if the final response is consistent with the specification. "
                "Answer exactly: pass or fail"
            )
        return (
            "You are a TCG/Opal protocol compliance checker. Given a command-response "
            "trajectory, determine if the final response is consistent with the "
            "specification. Answer with exactly one word: pass or fail"
        )

    def predict(self, records: list[Json], trace: list[Json] | None = None) -> str:
        """Predict pass/fail for a single trajectory."""
        if not self.available or not records:
            return "pass"  # fallback

        import torch

        prompt = self._format_records(records)
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
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

        max_len = 1024 if self._format_version == "v2" else 512
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=max_len)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=16,
                do_sample=False,
                temperature=1.0,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        generated = outputs[0][inputs["input_ids"].shape[1]:]
        answer = self.tokenizer.decode(generated, skip_special_tokens=True).strip().lower()

        if "fail" in answer:
            return "fail"
        elif "pass" in answer:
            return "pass"
        else:
            logger.warning("Ambiguous LoRA answer: %r → default pass", answer)
            return "pass"
