"""LLM solver: zero-shot generation for uncertain cases.

Changed: replaces LoRA logit comparison with 9B zero-shot generation.
Why: LoRA logit approach failed 5 consecutive times (never improved over rule engine).
Root cause: synthetic training data has distribution mismatch with hidden test.
Zero-shot generation doesn't need training data → no distribution mismatch.

Approach inspired by teammate's solver3.py:
- filter trajectory to relevant steps only
- include TCG protocol rules in system prompt
- 9B model generates reasoning then pass/fail verdict
- Only used for LOW confidence cases (UNEXPECTED_ERROR_STATUS, DEFAULT_PASS)

Papers: Chain-of-Authorization (arXiv 2603.22869), LLMAC (arXiv 2602.09392)
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
Json = dict[str, Any]

# Changed: protocol rules embedded in prompt (from solver4 CODE_GEN_SYSTEM).
SYSTEM_PROMPT = """You are a TCG/Opal SSD protocol compliance verifier.

PASS: the final response is what the protocol REQUIRES (not necessarily SUCCESS)
FAIL: the final response VIOLATES the specification

Key rules:
- Methods without an open session → must return NOT_AUTHORIZED (PASS if it does)
- Protected ops (Set, Activate, GenKey) without auth → must return NOT_AUTHORIZED (PASS)
- Read-Only session + write method → NOT_AUTHORIZED (PASS)
- NOT_AUTHORIZED on column not in ACE → correct rejection (PASS)
- After PIN change: old PIN → NOT_AUTHORIZED (PASS); new PIN → SUCCESS (PASS)
- After GenKey: original data unreadable; read returning original → FAIL
- WriteLocked range + Write → NOT_AUTHORIZED (PASS)
- ReadLocked range + Read → NOT_AUTHORIZED (PASS)
- SP_BUSY/SP_FROZEN/NO_SESSIONS_AVAILABLE/AUTHORITY_LOCKED_OUT → valid rejections (PASS)

After reasoning, output your verdict on its own line as exactly: pass  or  fail"""

# Changed: from solver3.py — filter to relevant steps.
STATE_METHODS = {"startsession", "endsession", "authenticate", "activate", "revert", "revertsp", "genkey"}


def _method_name(step: Json) -> str:
    inp = step.get("input", {})
    m = inp.get("method", {})
    if isinstance(m, dict):
        return (m.get("name", "") or inp.get("command", "")).strip()
    return str(m).strip()


def _invoking_name(step: Json) -> str:
    inp = step.get("input", {})
    inv = inp.get("invoking_id", {})
    if isinstance(inv, dict):
        return (inv.get("name", "") or "").strip()
    return str(inv).strip()


def extract_relevant_steps(steps: list[Json]) -> list[Json]:
    """Filter to protocol-relevant steps only."""
    if len(steps) <= 3:
        return steps
    context = steps[:-1]
    final = steps[-1]
    final_method = _method_name(final).lower()
    final_invoking = _invoking_name(final).lower()

    relevant = []
    for step in context:
        method = _method_name(step).lower()
        invoking = _invoking_name(step).lower()
        if method in STATE_METHODS:
            relevant.append(step)
        elif method == "set" and "c_pin" in invoking:
            relevant.append(step)
        elif method == "set" and ("locking" in invoking or "range" in invoking):
            relevant.append(step)
        elif final_invoking and invoking == final_invoking:
            relevant.append(step)
        elif final_method in ("read", "write") and method in ("write", "read", "genkey"):
            relevant.append(step)
    return relevant + [final]


def parse_verdict(text: str) -> str:
    """Extract pass/fail from generation output."""
    if "</think>" in text:
        text = text.split("</think>")[-1]
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    for line in reversed(lines):
        if re.fullmatch(r"pass", line, re.IGNORECASE):
            return "pass"
        if re.fullmatch(r"fail", line, re.IGNORECASE):
            return "fail"
    for line in reversed(lines):
        if re.search(r"\bpass\b", line, re.IGNORECASE):
            return "pass"
        if re.search(r"\bfail\b", line, re.IGNORECASE):
            return "fail"
    return "fail"  # default to fail if can't parse


class LLMSolver:
    """Zero-shot LLM solver for uncertain cases. No training required."""

    def __init__(self, model_name: str | None = None):
        self.model = None
        self.tokenizer = None
        self.available = False

        if model_name is None:
            model_name = os.environ.get("LLM_MODEL", "Qwen/Qwen3.5-9B")

        try:
            self._load(model_name)
        except Exception as e:
            logger.warning("LLM solver failed to load: %s", e)

    def _load(self, model_name: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        t0 = time.time()
        logger.info("Loading LLM solver: %s", model_name)

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
        self.model.eval()
        self.available = True
        logger.info("LLM solver loaded in %.1fs", time.time() - t0)

    def predict(self, steps: list[Json], rule_context: dict | None = None) -> str:
        """Generate verdict via zero-shot reasoning."""
        if not self.available or not steps:
            return "pass"  # safe default

        import torch

        relevant = extract_relevant_steps(steps)
        content = json.dumps(relevant, ensure_ascii=False, indent=1)
        note = f"(Showing {len(relevant)} of {len(steps)} steps)"

        # Add rule engine context if available
        context_str = ""
        if rule_context:
            context_str = (
                f"\nRule engine analysis: predicted '{rule_context.get('prediction', '?')}' "
                f"via rule '{rule_context.get('rule_id', '?')}' "
                f"(confidence: {rule_context.get('tier', '?')}). "
                f"The rule engine may be wrong.\n"
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Trajectory {note}:{context_str}\n{content}\n\n"
                f"Is the final response protocol-compliant? Reason briefly then give your verdict:"
            )},
        ]

        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)

        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=8192
        ).to(next(self.model.parameters()).device)

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs, do_sample=False, max_new_tokens=256,
                pad_token_id=self.tokenizer.eos_token_id)

        new_ids = output_ids[0, inputs["input_ids"].shape[-1]:]
        response = self.tokenizer.decode(new_ids, skip_special_tokens=True).strip()

        verdict = parse_verdict(response)
        logger.debug("LLM verdict: %s (response: %s)", verdict, response[:100])
        return verdict
