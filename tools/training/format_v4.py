"""V4 format: filtered trajectory + TCG rule summary in prompt.

Changed: inspired by teammate's solver3/solver4 approach.
Why: instead of showing ALL steps, filter to only protocol-relevant ones:
- Session lifecycle (StartSession, EndSession, Authenticate)
- State changes (Set on C_PIN/Locking, Activate, GenKey)
- Same target as final step
This reduces token count AND focuses the model on what matters.

Also adds a condensed TCG rule summary to the prompt, inspired by solver4's
CODE_GEN_SYSTEM prompt which encodes key protocol rules explicitly.
"""
from __future__ import annotations
from typing import Any

Json = dict[str, Any]

# Changed: borrowed and adapted from teammate's solver3.py extract_relevant_steps().
STATE_CHANGING_METHODS = {
    "startsession", "endsession", "authenticate",
    "activate", "revert", "revertsp", "genkey",
}

# Changed: condensed TCG rule summary from solver4's CODE_GEN_SYSTEM.
# Why: embedding key rules in the prompt helps the model reason about edge cases.
TCG_RULES_SUMMARY = """Key TCG/Opal rules:
- Methods without session → NOT_AUTHORIZED (correct rejection = pass)
- Write ops without auth → NOT_AUTHORIZED (correct = pass)
- Read-Only session + write → NOT_AUTHORIZED (correct = pass)
- NOT_AUTHORIZED on ACL-restricted column → correct rejection (pass)
- After PIN change: old PIN → NOT_AUTHORIZED (pass), new PIN → SUCCESS (pass)
- After GenKey: original data unreadable (read returning original = fail)
- WriteLocked range + Write → NOT_AUTHORIZED (pass)
- ReadLocked range + Read → NOT_AUTHORIZED (pass)
- SP_BUSY/SP_FROZEN/NO_SESSIONS_AVAILABLE/AUTHORITY_LOCKED_OUT are valid rejections (pass)"""


def _get_method(step: Json) -> str:
    inp = step.get("input", {})
    m = inp.get("method", {})
    if isinstance(m, dict):
        return (m.get("name", "") or inp.get("command", "")).lower().strip()
    return str(m).lower().strip()


def _get_invoking(step: Json) -> str:
    inp = step.get("input", {})
    inv = inp.get("invoking_id", {})
    if isinstance(inv, dict):
        return (inv.get("name", "") or "").lower().strip()
    return str(inv).lower().strip()


def extract_relevant_steps(records: list[Json]) -> list[Json]:
    """Filter trajectory to only protocol-relevant steps.

    Changed: adapted from teammate's solver3.py.
    Why: reduces token count by 40-60% while keeping all decision-relevant info.
    """
    if len(records) <= 3:
        return records  # Short trajectories: keep all

    context = records[:-1]
    final = records[-1]
    final_method = _get_method(final)
    final_invoking = _get_invoking(final)

    relevant = []
    for step in context:
        method = _get_method(step)
        invoking = _get_invoking(step)

        # Always: session/auth/key lifecycle
        if method in STATE_CHANGING_METHODS:
            relevant.append(step)
        # Always: PIN changes
        elif method == "set" and "c_pin" in invoking:
            relevant.append(step)
        # Always: locking state changes
        elif method == "set" and ("locking" in invoking or "range" in invoking):
            relevant.append(step)
        # Same target object as final
        elif final_invoking and invoking == final_invoking:
            relevant.append(step)
        # Data command context
        elif final_method in ("read", "write") and method in ("write", "read", "genkey"):
            relevant.append(step)

    return relevant + [final]


def format_trajectory_v4(records: list[Json], rule_context: dict | None = None) -> str:
    """V4: filtered steps + rule summary + rule engine context.

    Combines:
    - extract_relevant_steps (from teammate's solver3)
    - TCG rule summary (from teammate's solver4)
    - Rule engine analysis (our v3 neuro-symbolic approach)
    """
    from tools.training.finetune_lora_v2 import _compact_json

    if not records:
        return ""

    # Filter to relevant steps
    filtered = extract_relevant_steps(records)

    # Build trajectory text (same format as format_trajectory_rich but on filtered steps)
    lines = []
    session_active = False
    authenticated = False

    for i, step in enumerate(filtered):
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
            authenticated = True
        elif method_lower == "endsession":
            session_active = False
            authenticated = False

        is_final = (i == len(filtered) - 1)
        prefix = "[FINAL] " if is_final else ""

        args_str = ""
        if method_args and isinstance(method_args, dict):
            req = method_args.get("required", {})
            if isinstance(req, dict) and req:
                args_str = _compact_json(req)
            elif not req:
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
    trajectory_text = "\n".join(lines)
    note = f"(Showing {len(filtered)} of {len(records)} steps)"

    # Build prompt with rule summary and optional rule context
    prompt = (
        f"TCG/Opal SSD protocol trajectory verification {note}.\n"
        f"{state_line}\n\n"
        f"{TCG_RULES_SUMMARY}\n\n"
        f"{trajectory_text}\n\n"
    )

    if rule_context:
        rule_id = rule_context.get("rule_id", "UNKNOWN")
        rule_pred = rule_context.get("prediction", "unknown")
        rule_detail = rule_context.get("detail", "")
        tier = rule_context.get("tier", "unknown")
        prompt += (
            f"--- Rule Engine Analysis ---\n"
            f"Rule: {rule_id}\n"
            f"Prediction: {rule_pred}\n"
            f"Detail: {rule_detail}\n"
            f"Confidence: {tier}\n"
            f"---\n\n"
            f"The rule engine predicted '{rule_pred}' with {tier} confidence.\n"
        )

    prompt += "Is the final response consistent with the TCG/Opal specification? Answer: "
    return prompt
