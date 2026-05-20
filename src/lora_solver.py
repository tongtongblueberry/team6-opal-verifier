# Changed: LoRA-based solver with confidence-gated predictions and self-contained format.
# Why: submission environment may not have tools/ in path. Inlined format_trajectory_rich.

from __future__ import annotations

import logging
import math
import os
import re
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

# Changed: v3 system prompt includes rule engine awareness.
# Why: LLM trained with rule engine context needs matching system prompt at inference.
SYSTEM_PROMPT_V3 = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory, session state, and a rule engine's analysis, "
    "determine if the final response is consistent with the specification. "
    "The rule engine may be wrong — use your understanding of the protocol to decide. "
    "Answer exactly: pass or fail"
)


def _compact_json(obj, max_depth=2, cur_depth=0) -> str:
    if cur_depth >= max_depth:
        if isinstance(obj, dict):
            return "{...}"
        elif isinstance(obj, list):
            return "[...]"
        return str(obj)
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            parts.append(f"{k}={_compact_json(v, max_depth, cur_depth+1)}")
        return "{" + ", ".join(parts) + "}"
    elif isinstance(obj, list):
        if len(obj) == 0:
            return "[]"
        if len(obj) <= 3:
            return "[" + ", ".join(_compact_json(x, max_depth, cur_depth+1) for x in obj) + "]"
        return f"[{_compact_json(obj[0], max_depth, cur_depth+1)}, ... ({len(obj)} items)]"
    elif isinstance(obj, str) and len(obj) > 60:
        return obj[:60] + "..."
    return str(obj)


def format_trajectory_rich(records: list) -> str:
    """Format trajectory with full constraint-relevant information."""
    if not records:
        return ""

    lines = []
    session_active = False
    authenticated = False
    current_sp = ""

    for i, step in enumerate(records):
        if not isinstance(step, dict):
            continue
        cmd = step.get("input", {})
        out = step.get("output", {})

        method_obj = cmd.get("method", {})
        method_name = method_obj.get("name", "") if isinstance(method_obj, dict) else str(method_obj)
        method_args = method_obj.get("args", {}) if isinstance(method_obj, dict) else {}

        inv_obj = cmd.get("invoking_id", {})
        inv_name = inv_obj.get("name", "") if isinstance(inv_obj, dict) else str(inv_obj)
        inv_uid = inv_obj.get("uid", "") if isinstance(inv_obj, dict) else ""

        status = out.get("status_codes", out.get("status", ""))
        if isinstance(status, dict):
            status = status.get("Name", status.get("name", str(status)))
        return_values = out.get("return_values", out.get("payload", None))

        method_lower = str(method_name).lower()
        status_lower = str(status).lower()
        if method_lower == "startsession" and "success" in status_lower:
            session_active = True
            if isinstance(method_args, dict):
                req = method_args.get("required", method_args)
                if isinstance(req, dict):
                    spid = req.get("SPID", "")
                    write = req.get("Write", "")
                    if spid:
                        current_sp = f"SPID={spid}"
                    if write:
                        current_sp += f",Write={write}"
            authenticated = True
        elif method_lower == "endsession":
            session_active = False
            authenticated = False

        is_final = (i == len(records) - 1)
        prefix = "[FINAL] " if is_final else ""

        args_str = ""
        if method_args:
            if isinstance(method_args, dict):
                req = method_args.get("required", {})
                if isinstance(req, dict) and req:
                    args_str = _compact_json(req)
                elif isinstance(method_args, dict) and not req:
                    args_str = _compact_json(method_args)
            else:
                args_str = _compact_json(method_args)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."

        rv_str = ""
        if return_values is not None:
            rv_str = _compact_json(return_values)
            if len(rv_str) > 150:
                rv_str = rv_str[:150] + "..."

        line = f"{prefix}Step {i}: {method_name}"
        if inv_name:
            line += f" target={inv_name}"
        if inv_uid:
            line += f"[{inv_uid}]"
        if args_str and args_str != "{}":
            line += f" args={args_str}"
        line += f" -> {status}"
        if rv_str and rv_str != "[]" and rv_str != "{}":
            line += f" payload={rv_str}"
        lines.append(line)

    state_line = f"SessionState: active={session_active}, auth={authenticated}"
    if current_sp:
        state_line += f", {current_sp}"

    trajectory_text = "\n".join(lines)

    prompt = (
        "TCG/Opal SSD protocol trajectory verification.\n"
        f"{state_line}\n\n"
        f"{trajectory_text}\n\n"
        "Is the final response consistent with the TCG/Opal specification? Answer: "
    )
    return prompt


class LoRASolver:
    """Fine-tuned LoRA model for pass/fail classification."""

    def __init__(self, adapter_path: str | None = None, base_model: str | None = None):
        self.model = None
        self.tokenizer = None
        self.available = False
        self._pass_id = None
        self._fail_id = None

        root = Path(__file__).resolve().parents[1]
        if adapter_path is None:
            # Changed: prefer v3 adapter (uncertainty resolver) over v2.
            # Why: v3 is trained with rule engine context → better integration.
            v3_dir = root / "artifacts" / "lora_adapter_v3"
            adapter_dir = root / "artifacts" / "lora_adapter_v2"
            if v3_dir.exists() and (v3_dir / "adapter_config.json").exists():
                adapter_dir = v3_dir
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

        self._pass_id = self.tokenizer.encode("pass", add_special_tokens=False)[0]
        self._fail_id = self.tokenizer.encode("fail", add_special_tokens=False)[0]

        logger.info("LoRA model loaded in %.1fs", time.time() - t0)

    def predict_prob(self, records: list[Json], rule_context: dict | None = None) -> float:
        """Return P(fail) probability.

        Changed: support v3 format with rule engine context.
        Why: neuro-symbolic approach — LLM uses rule engine analysis for better decisions.
        Falls back to v2 format if no rule_context provided.
        """
        if not self.available or not records:
            return 0.5

        import torch

        # Changed: build prompt based on format version.
        # Why: v3 includes rule engine context, v2 is plain trajectory.
        if rule_context:
            prompt = self._format_v3_prompt(records, rule_context)
            system_prompt = SYSTEM_PROMPT_V3
        else:
            prompt = format_trajectory_rich(records)
            system_prompt = SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": system_prompt},
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

        p_logit = logits[self._pass_id].item()
        f_logit = logits[self._fail_id].item()

        mx = max(p_logit, f_logit)
        p_fail = math.exp(f_logit - mx) / (math.exp(p_logit - mx) + math.exp(f_logit - mx))
        return p_fail

    def _format_v3_prompt(self, records: list[Json], rule_context: dict) -> str:
        """Format trajectory with rule engine context (v3 neuro-symbolic format)."""
        base_prompt = format_trajectory_rich(records)
        if not base_prompt:
            return ""

        rule_id = rule_context.get("rule_id", "UNKNOWN")
        rule_pred = rule_context.get("prediction", "unknown")
        rule_detail = rule_context.get("detail", "")
        tier = rule_context.get("tier", "unknown")

        context = (
            f"\n--- Rule Engine Analysis ---\n"
            f"Rule: {rule_id}\n"
            f"Prediction: {rule_pred}\n"
            f"Detail: {rule_detail}\n"
            f"Confidence: {tier}\n"
            f"---\n\n"
            f"The rule engine predicted '{rule_pred}' with {tier} confidence.\n"
            f"Given the trajectory and this analysis, is the final response "
            f"consistent with the TCG/Opal specification? Answer: "
        )

        base_parts = base_prompt.rsplit("Is the final response", 1)
        if len(base_parts) == 2:
            return base_parts[0] + context
        return base_prompt + context

    def predict(self, records: list[Json], trace: list[Json] | None = None) -> str:
        """Predict pass/fail (binary)."""
        p_fail = self.predict_prob(records)
        return "fail" if p_fail > 0.5 else "pass"
