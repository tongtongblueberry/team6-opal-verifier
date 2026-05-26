# Changed: LLM-only solver using Qwen3.5-27B-FP8 for submission.
# Why: DL course requires LLM usage. This solver uses ONLY the 27B model
# with logit comparison (pass vs fail) — no rule engine at inference time.
# Design: ACE table + protocol rules in system prompt, filtered trajectory,
# single forward pass per case, logit comparison for pass/fail decision.

from __future__ import annotations

import logging
import math
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)
Json = dict[str, Any]

# ---------------------------------------------------------------------------
# System prompt: ACE table (Markdown-KV) + protocol rules
# Changed: embed all key ACE entries and protocol rules directly in prompt.
# Why: gives the 27B model maximum context for correct verification.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a TCG/Opal SSD protocol compliance verifier.
You determine whether the FINAL response in an SSD command-response trajectory
is consistent with the TCG/Opal specification.

## Access Control Entries (ACE Table)

### Admin SP (opal/4.2.1.5, 4.2.1.6)
- C_PIN_SID Get: Admins OR SID → returns UID,CharSet,TryLimit,Tries,Persistence (NO PIN column)
- C_PIN_MSID Get: Anybody → returns UID and PIN (PIN readable by anyone)
- C_PIN_SID Set PIN: SID only
- SP Activate: SID only (ACE_SP_SID)
- SP Revert: SID only (ACE_SP_SID)
- Authority Enabled Set: SID only (ACE_Set_Enabled)

### Locking SP (opal/4.3.1.6, 4.3.1.7)
- Locking_Range Set ReadLocked: Admins (default), configurable to Admins OR UserN
- Locking_Range Set WriteLocked: Admins (default), configurable to Admins OR UserN
- Locking_Range Set RangeStart/RangeLength/ReadLockEnabled/WriteLockEnabled: Admins only
- GenKey on K_AES key: Admins only
- C_PIN_UserN Set PIN: Admins (default), configurable to Admins OR UserN
- C_PIN_AdminN Set PIN: Admins only
- Authority Enabled Set: Admins only

### Default Authority States (OFS = Original Factory State)
- Admin1: Enabled=True
- Admin2,Admin3,Admin4: Enabled=False
- User1-User8: Enabled=False

## Protocol Rules

1. Session requirement: methods invoked without an open session → NOT_AUTHORIZED
2. Authentication requirement: write ops (Set, Activate, GenKey, Revert) without auth → NOT_AUTHORIZED
3. Read-Only session: write ops (Set, Activate, GenKey, Revert) → NOT_AUTHORIZED
4. Column ACL: Set on column not in ACE's Columns list → NOT_AUTHORIZED (entire Set fails)
5. PIN changes: after Set on C_PIN.PIN, old PIN → NOT_AUTHORIZED, new PIN → SUCCESS
6. GenKey effect: after GenKey, original data becomes unreadable; read returning original data → FAIL
7. Locking: WriteLocked range + Write → NOT_AUTHORIZED; ReadLocked range + Read → NOT_AUTHORIZED
8. SP_BUSY: concurrent RW sessions to same SP → SP_BUSY (valid rejection)
9. SP_FROZEN: session to frozen SP → SP_FROZEN (valid rejection)
10. NO_SESSIONS_AVAILABLE: max sessions reached → NO_SESSIONS_AVAILABLE (valid rejection)
11. AUTHORITY_LOCKED_OUT: TryLimit exceeded → AUTHORITY_LOCKED_OUT (valid rejection)
12. Class authority: Authenticate or StartSession with class authority (Admins, Users) → INVALID_PARAMETER
13. Disabled authority: Authenticate with disabled authority → SUCCESS with result=False
14. Wrong password: Authenticate with wrong password → SUCCESS with result=False
15. Correct password: Authenticate with correct password and enabled authority → SUCCESS with result=True
16. GlobalRange: RangeStart and RangeLength are NOT modifiable (fixed at 0)
17. Activate copies SID PIN to LockingSP Admin1 C_PIN

## Verdict Rules

PASS = the final response is what the protocol REQUIRES (correct behavior, even if status is an error)
FAIL = the final response VIOLATES the specification (wrong status, wrong data, missing rejection)

Based on the ACE table, protocol rules, and the trajectory below, is the final response correct?
Answer: pass or fail"""


# ---------------------------------------------------------------------------
# Trajectory filtering (inlined from format_v4.py / llm_solver.py)
# Changed: self-contained to avoid cross-module imports in submission.
# Why: submission environment may not have tools/ on sys.path.
# ---------------------------------------------------------------------------
STATE_CHANGING_METHODS = {
    "startsession", "endsession", "authenticate",
    "activate", "revert", "revertsp", "genkey",
}


def _get_method(step: Json) -> str:
    """Extract method name from step."""
    inp = step.get("input", {})
    m = inp.get("method", {})
    if isinstance(m, dict):
        return (m.get("name", "") or inp.get("command", "")).lower().strip()
    return str(m).lower().strip()


def _get_invoking(step: Json) -> str:
    """Extract invoking ID name from step."""
    inp = step.get("input", {})
    inv = inp.get("invoking_id", {})
    if isinstance(inv, dict):
        return (inv.get("name", "") or "").lower().strip()
    return str(inv).lower().strip()


def extract_relevant_steps(records: list[Json]) -> list[Json]:
    """Filter trajectory to protocol-relevant steps only.

    Changed: inlined from format_v4.py to be self-contained.
    Why: reduces token count by 40-60% while keeping decision-relevant info.
    """
    if len(records) <= 3:
        return records

    context = records[:-1]
    final = records[-1]
    final_method = _get_method(final)
    final_invoking = _get_invoking(final)

    relevant = []
    for step in context:
        method = _get_method(step)
        invoking = _get_invoking(step)

        # Always keep: session/auth/key lifecycle
        if method in STATE_CHANGING_METHODS:
            relevant.append(step)
        # Always keep: PIN changes
        elif method == "set" and "c_pin" in invoking:
            relevant.append(step)
        # Always keep: locking state changes
        elif method == "set" and ("locking" in invoking or "range" in invoking):
            relevant.append(step)
        # Same target object as final step
        elif final_invoking and invoking == final_invoking:
            relevant.append(step)
        # Data command context (read/write after genkey)
        elif final_method in ("read", "write") and method in ("write", "read", "genkey"):
            relevant.append(step)

    return relevant + [final]


def _compact_json(obj: Any, max_depth: int = 2, cur_depth: int = 0) -> str:
    """Compact JSON representation for prompt formatting.

    Changed: inlined from lora_solver.py.
    Why: self-contained module, no cross-imports.
    """
    if cur_depth >= max_depth:
        if isinstance(obj, dict):
            return "{...}"
        elif isinstance(obj, list):
            return "[...]"
        return str(obj)
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            parts.append(f"{k}={_compact_json(v, max_depth, cur_depth + 1)}")
        return "{" + ", ".join(parts) + "}"
    elif isinstance(obj, list):
        if len(obj) == 0:
            return "[]"
        if len(obj) <= 3:
            return "[" + ", ".join(_compact_json(x, max_depth, cur_depth + 1) for x in obj) + "]"
        return f"[{_compact_json(obj[0], max_depth, cur_depth + 1)}, ... ({len(obj)} items)]"
    elif isinstance(obj, str) and len(obj) > 60:
        return obj[:60] + "..."
    return str(obj)


def format_step(step: Json, index: int, is_final: bool) -> str:
    """Format a single trajectory step into a compact string.

    Changed: extracted from format_trajectory_rich for clarity.
    Why: each step gets method, target, args, status, payload on one line.
    """
    if not isinstance(step, dict):
        return ""

    cmd = step.get("input", {})
    out = step.get("output", {})

    method_obj = cmd.get("method", {})
    if isinstance(method_obj, dict):
        method_name = method_obj.get("name", "")
        method_args = method_obj.get("args", {})
    else:
        method_name = str(method_obj)
        method_args = {}

    inv_obj = cmd.get("invoking_id", {})
    if isinstance(inv_obj, dict):
        inv_name = inv_obj.get("name", "")
        inv_uid = inv_obj.get("uid", "")
    else:
        inv_name = str(inv_obj)
        inv_uid = ""

    # Extract status
    status = out.get("status_codes", out.get("status", ""))
    if isinstance(status, dict):
        status = status.get("Name", status.get("name", str(status)))
    return_values = out.get("return_values", out.get("payload", None))

    prefix = "[FINAL] " if is_final else ""

    # Format args compactly
    args_str = ""
    if method_args and isinstance(method_args, dict):
        req = method_args.get("required", {})
        if isinstance(req, dict) and req:
            args_str = _compact_json(req)
        elif not req:
            args_str = _compact_json(method_args)
    if len(args_str) > 200:
        args_str = args_str[:200] + "..."

    # Format return values compactly
    rv_str = ""
    if return_values is not None:
        rv_str = _compact_json(return_values)
        if len(rv_str) > 150:
            rv_str = rv_str[:150] + "..."

    line = f"{prefix}Step {index}: {method_name}"
    if inv_name:
        line += f" target={inv_name}"
    if inv_uid:
        line += f"[{inv_uid}]"
    if args_str and args_str != "{}":
        line += f" args={args_str}"
    line += f" -> {status}"
    if rv_str and rv_str not in ("[]", "{}"):
        line += f" payload={rv_str}"

    return line


def format_trajectory(records: list[Json]) -> str:
    """Format filtered trajectory into a prompt string.

    Changed: combines extract_relevant_steps + format_step.
    Why: single function call for the full formatting pipeline.
    """
    if not records:
        return ""

    filtered = extract_relevant_steps(records)
    lines = []
    session_active = False
    authenticated = False
    current_sp = ""

    for i, step in enumerate(filtered):
        if not isinstance(step, dict):
            continue

        # Track session state for context line
        method_lower = _get_method(step)
        status = step.get("output", {}).get("status_codes", step.get("output", {}).get("status", ""))
        if isinstance(status, dict):
            status = status.get("Name", status.get("name", str(status)))
        status_lower = str(status).lower()

        if method_lower == "startsession" and "success" in status_lower:
            session_active = True
            authenticated = True
            inp = step.get("input", {})
            m = inp.get("method", {})
            if isinstance(m, dict):
                args = m.get("args", {})
                if isinstance(args, dict):
                    req = args.get("required", args)
                    if isinstance(req, dict):
                        spid = req.get("SPID", "")
                        write = req.get("Write", "")
                        if spid:
                            current_sp = f"SPID={spid}"
                        if write is not None:
                            current_sp += f",Write={write}"
        elif method_lower == "endsession":
            session_active = False
            authenticated = False

        is_final = (i == len(filtered) - 1)
        line = format_step(step, i, is_final)
        if line:
            lines.append(line)

    state_line = f"SessionState: active={session_active}, auth={authenticated}"
    if current_sp:
        state_line += f", {current_sp}"

    note = f"(Showing {len(filtered)} of {len(records)} steps)"
    trajectory_text = "\n".join(lines)

    prompt = (
        f"TCG/Opal SSD protocol trajectory verification {note}.\n"
        f"{state_line}\n\n"
        f"{trajectory_text}\n\n"
        f"Is the final response correct? Answer: "
    )
    return prompt


# ---------------------------------------------------------------------------
# Solver class — the submission entry point
# ---------------------------------------------------------------------------
class Solver:
    """LLM-only solver using Qwen3.5-27B-FP8 logit comparison.

    Changed: clean LLM-only solver for submission (no rule engine).
    Why: DL course mandates LLM usage. Uses single forward pass + logit
    comparison for speed (200 cases in 3 hours on L40S 48GB).
    """

    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Changed: load Qwen3.5-27B-FP8 — the largest available pre-cached model.
        # Why: 27B has best reasoning capability; FP8 fits in L40S 48GB.
        model_name = os.environ.get("MODEL_NAME", "Qwen/Qwen3.5-27B-FP8")

        t0 = time.time()
        logger.info("Loading model: %s", model_name)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        self.model.eval()

        # Changed: pre-compute token IDs for pass/fail.
        # Why: logit comparison needs these IDs at every forward pass.
        self._pass_id = self.tokenizer.encode("pass", add_special_tokens=False)[0]
        self._fail_id = self.tokenizer.encode("fail", add_special_tokens=False)[0]

        # Changed: also check alternative token IDs (capitalized, with prefix space).
        # Why: tokenizer may encode "Pass"/"Fail" differently from "pass"/"fail".
        self._pass_ids = [self._pass_id]
        self._fail_ids = [self._fail_id]
        for variant in ["Pass", "PASS", " pass", " Pass"]:
            tokens = self.tokenizer.encode(variant, add_special_tokens=False)
            if tokens and tokens[0] not in self._pass_ids:
                self._pass_ids.append(tokens[0])
        for variant in ["Fail", "FAIL", " fail", " Fail"]:
            tokens = self.tokenizer.encode(variant, add_special_tokens=False)
            if tokens and tokens[0] not in self._fail_ids:
                self._fail_ids.append(tokens[0])

        logger.info(
            "Model loaded in %.1fs. pass_ids=%s, fail_ids=%s",
            time.time() - t0,
            self._pass_ids,
            self._fail_ids,
        )

    def _get_logit_scores(self, logits: Any) -> tuple[float, float]:
        """Get aggregated pass/fail logit scores across all token variants.

        Changed: aggregate across all token ID variants.
        Why: different casing or space-prefixed tokens may get different logits.
        We take the max logit across all variants for each class.
        """
        pass_logit = max(logits[tid].item() for tid in self._pass_ids)
        fail_logit = max(logits[tid].item() for tid in self._fail_ids)
        return pass_logit, fail_logit

    def predict(self, dataset: Any) -> dict[str, str]:
        """Predict pass/fail for each case in dataset.

        Changed: LLM-only prediction — no rule engine.
        Why: single forward pass per case using logit comparison.

        Args:
            dataset: list of {"id": str, "steps": list} dicts.

        Returns:
            dict mapping case_id to "pass" or "fail".
        """
        import torch

        if not isinstance(dataset, list):
            return {}

        predictions: dict[str, str] = {}
        total = len(dataset)

        for index, item in enumerate(dataset):
            t0 = time.time()

            # Changed: extract case_id and steps from item dict.
            # Why: submission format uses {"id": str, "steps": list}.
            if isinstance(item, dict):
                case_id = str(item.get("id", f"case_{index}"))
                steps = item.get("steps", item)
            else:
                case_id = f"case_{index}"
                steps = item

            # Changed: handle edge case of empty or non-list steps.
            # Why: robustness against malformed input.
            if not isinstance(steps, list) or len(steps) == 0:
                predictions[case_id] = "pass"
                continue

            # Format trajectory into prompt
            user_prompt = format_trajectory(steps)

            # Build chat messages
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            # Changed: apply chat template with thinking disabled.
            # Why: we only need the first token logit, not full generation.
            try:
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                # Changed: fallback without enable_thinking for older transformers.
                # Why: some tokenizer versions don't support enable_thinking param.
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )

            # Changed: tokenize with truncation to fit in memory.
            # Why: 27B-FP8 on L40S 48GB — need to limit context length.
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=4096,
            )
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            # Changed: single forward pass, extract logits at last position.
            # Why: logit comparison is 10-50x faster than generation.
            with torch.inference_mode():
                logits = self.model(**inputs).logits[0, -1, :]

            # Changed: compare pass vs fail logits to make prediction.
            # Why: higher logit = model's preferred next token.
            pass_logit, fail_logit = self._get_logit_scores(logits)

            # Compute probability for logging
            mx = max(pass_logit, fail_logit)
            p_fail = math.exp(fail_logit - mx) / (
                math.exp(pass_logit - mx) + math.exp(fail_logit - mx)
            )

            prediction = "fail" if p_fail > 0.5 else "pass"
            predictions[case_id] = prediction

            elapsed = time.time() - t0
            logger.info(
                "[%d/%d] %s → %s (p_fail=%.3f, %.1fs)",
                index + 1,
                total,
                case_id,
                prediction,
                p_fail,
                elapsed,
            )

        return predictions
