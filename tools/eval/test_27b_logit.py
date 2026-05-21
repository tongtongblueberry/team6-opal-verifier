#!/usr/bin/env python3
"""27B-FP8 logit-mode evaluation with ACE-grounded prompt on public 20.

Changed: new evaluation script for frozen 27B model (no LoRA).
Why: test whether a large frozen model with ACE-grounded prompts can outperform
     the rule engine (71.50) via single forward-pass logit comparison.

Design:
- Loads Qwen3.5-27B-FP8 frozen (no LoRA adapter)
- Filters trajectory via extract_relevant_steps
- Builds prompt with ACE table (Rules 62-69) + protocol rules + filtered trajectory
- Single forward pass, extract logits for "pass"/"fail" tokens
- p_fail = softmax(fail_logit, pass_logit); predict "fail" if p_fail > 0.5
- ~1-2s per case, 200 cases < 7 minutes total (time-safe for 3h limit)

Usage (on server):
  python tools/eval/test_27b_logit.py --dataset-root /dl2026/dataset
  python tools/eval/test_27b_logit.py --model Qwen/Qwen3.5-9B  # smaller model test
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("test_27b_logit")

Json = dict[str, Any]

# ---------------------------------------------------------------------------
# ACE table: Rules 62-69 from docs/spec_rules.md (Markdown-KV format)
# Changed: embed ACE rules directly in prompt for grounding.
# Why: ACE rules are the most actionable access-control constraints; they
#      cover column-level permission, GenKey auth, Activate/Revert auth, etc.
# ---------------------------------------------------------------------------
ACE_TABLE = """\
## Access Control (ACE) Rules

Rule 62 | C_PIN_SID Get excludes PIN column
- Get on C_PIN_SID with Admins OR SID authority -> SUCCESS but PIN column OMITTED
- Only UID, CharSet, TryLimit, Tries, Persistence columns returned
- If PIN column is returned -> FAIL

Rule 63 | C_PIN_MSID Get returns PIN
- Get on C_PIN_MSID with Anybody authority -> SUCCESS with UID and PIN columns
- PIN must be present in result
- If PIN not returned -> FAIL

Rule 64 | Set PIN on C_PIN_SID requires SID authority
- Set PIN column on C_PIN_SID -> SUCCESS only if SID authenticated
- NOT_AUTHORIZED if any other authority
- If unauthorized entity changes SID PIN -> FAIL

Rule 65 | Locking range ReadLocked/WriteLocked Set requires proper ACE
- Set ReadLocked on Locking_Range1 requires ACE_Locking_Range1_Set_RdLocked
- Default: Admins authority required
- NOT_AUTHORIZED if non-Admin authority; SUCCESS if Admin

Rule 66 | GenKey requires Admin authority for Locking range keys
- GenKey on K_AES key object requires Admins authority
- NOT_AUTHORIZED if not Admin; SUCCESS if Admin

Rule 67 | Activate on LockingSP requires SID
- Activate method on SP object requires SID authority
- NOT_AUTHORIZED if not SID

Rule 68 | Revert on SP requires SID or Admins
- Revert on SP object requires SID or Admins authority
- NOT_AUTHORIZED if neither SID nor Admins authenticated

Rule 69 | Authority Enabled column modifiable only by SID (Admin SP)
- Set Enabled column on Authority objects in Admin SP requires SID
- NOT_AUTHORIZED if not SID
"""

# ---------------------------------------------------------------------------
# Protocol rules (session, auth, locking) — compact reference
# ---------------------------------------------------------------------------
PROTOCOL_RULES = """\
## Protocol Rules

Session:
- Methods without an open session -> NOT_AUTHORIZED (PASS if it does)
- Read-Only session + write method (Set, GenKey, Activate, Revert) -> NOT_AUTHORIZED (PASS)
- SP_BUSY: only one RW session per SP at a time; RO and RW are mutually exclusive
- NO_SESSIONS_AVAILABLE: max concurrent sessions reached

Auth:
- Protected ops without auth -> NOT_AUTHORIZED (PASS)
- After PIN change: old PIN -> NOT_AUTHORIZED (PASS); new PIN -> SUCCESS (PASS)
- Class authority in Authenticate -> INVALID_PARAMETER
- Class authority as HostSigningAuthority in StartSession -> INVALID_PARAMETER
- Disabled authority -> Authenticate returns SUCCESS/False
- AUTHORITY_LOCKED_OUT: Tries == TryLimit (TryLimit != 0)

Locking:
- WriteLocked range + Write -> NOT_AUTHORIZED (PASS)
- ReadLocked range + Read -> NOT_AUTHORIZED (PASS)
- After GenKey: original data unreadable; read returning original data -> FAIL
- SP_FROZEN / SP_BUSY / NO_SESSIONS_AVAILABLE -> valid rejections (PASS)

Verdict meaning:
- PASS = the final response is what the protocol REQUIRES (even if it's an error)
- FAIL = the final response VIOLATES the specification
"""

# ---------------------------------------------------------------------------
# Trajectory filtering (from src/llm_solver.py)
# Changed: inlined from llm_solver.py to keep script self-contained.
# Why: server may not have src/ in PYTHONPATH reliably.
# ---------------------------------------------------------------------------
STATE_METHODS = {
    "startsession", "endsession", "authenticate",
    "activate", "revert", "revertsp", "genkey",
}


def _method_name(step: Json) -> str:
    """Extract method name from a trajectory step."""
    inp = step.get("input", {})
    m = inp.get("method", {})
    if isinstance(m, dict):
        return (m.get("name", "") or inp.get("command", "")).strip()
    return str(m).strip()


def _invoking_name(step: Json) -> str:
    """Extract invoking object name from a trajectory step."""
    inp = step.get("input", {})
    inv = inp.get("invoking_id", {})
    if isinstance(inv, dict):
        return (inv.get("name", "") or "").strip()
    return str(inv).strip()


def _status_str(step: Json) -> str:
    """Extract status string from a trajectory step."""
    out = step.get("output", {})
    status = out.get("status_codes", out.get("status", ""))
    if isinstance(status, dict):
        return status.get("Name", status.get("name", str(status)))
    return str(status)


def extract_relevant_steps(steps: list[Json]) -> list[Json]:
    """Filter to protocol-relevant steps only.

    Changed: inlined from llm_solver.py.
    Why: self-contained script for server execution.
    """
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


def _compact_json(obj: Any, max_depth: int = 2, cur_depth: int = 0) -> str:
    """Compact JSON representation for trajectory display.

    Changed: inlined from lora_solver.py.
    Why: self-contained script.
    """
    if cur_depth >= max_depth:
        if isinstance(obj, dict):
            return "{...}"
        elif isinstance(obj, list):
            return "[...]"
        return str(obj)
    if isinstance(obj, dict):
        parts = [f"{k}={_compact_json(v, max_depth, cur_depth + 1)}" for k, v in obj.items()]
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


def format_step(i: int, step: Json, is_final: bool) -> str:
    """Format a single trajectory step for the prompt."""
    inp = step.get("input", {})
    out = step.get("output", {})

    method_obj = inp.get("method", {})
    method_name = method_obj.get("name", "") if isinstance(method_obj, dict) else str(method_obj)
    method_args = method_obj.get("args", {}) if isinstance(method_obj, dict) else {}

    inv_obj = inp.get("invoking_id", {})
    inv_name = inv_obj.get("name", "") if isinstance(inv_obj, dict) else str(inv_obj)
    inv_uid = inv_obj.get("uid", "") if isinstance(inv_obj, dict) else ""

    status = _status_str(step)
    return_values = out.get("return_values", out.get("payload", None))

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
    return line


def build_prompt(steps: list[Json]) -> str:
    """Build the full ACE-grounded prompt for logit-mode evaluation.

    Structure:
    1. ACE table (Rules 62-69) in Markdown-KV at the START
    2. Protocol rules (session, auth, locking)
    3. Filtered trajectory
    4. Final question
    """
    relevant = extract_relevant_steps(steps)

    # Format trajectory lines
    lines = []
    for i, step in enumerate(relevant):
        if not isinstance(step, dict):
            continue
        is_final = (i == len(relevant) - 1)
        lines.append(format_step(i, step, is_final))
    trajectory_text = "\n".join(lines)

    # Track session state
    session_active = False
    authenticated = False
    current_sp = ""
    for step in relevant:
        method = _method_name(step).lower()
        status = _status_str(step).lower()
        if method == "startsession" and "success" in status:
            session_active = True
            authenticated = True
            inp = step.get("input", {})
            m_args = inp.get("method", {})
            if isinstance(m_args, dict):
                m_args = m_args.get("args", {})
            if isinstance(m_args, dict):
                req = m_args.get("required", m_args)
                if isinstance(req, dict):
                    spid = req.get("SPID", "")
                    write = req.get("Write", "")
                    if spid:
                        current_sp = f"SPID={spid}"
                    if write:
                        current_sp += f",Write={write}"
        elif method == "endsession":
            session_active = False
            authenticated = False

    state_line = f"SessionState: active={session_active}, auth={authenticated}"
    if current_sp:
        state_line += f", {current_sp}"

    # Assemble prompt: ACE table -> protocol rules -> trajectory -> question
    prompt = (
        f"{ACE_TABLE}\n"
        f"{PROTOCOL_RULES}\n"
        f"## Trajectory\n"
        f"{state_line}\n"
        f"(Showing {len(relevant)} of {len(steps)} steps)\n\n"
        f"{trajectory_text}\n\n"
        f"Is the final response consistent with the TCG/Opal specification? Answer: "
    )
    return prompt


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given the ACE access control rules, protocol rules, and a command-response trajectory, "
    "determine if the final response is consistent with the specification. "
    "Answer exactly: pass or fail"
)


# ---------------------------------------------------------------------------
# Model loading and inference
# ---------------------------------------------------------------------------
def load_model(model_name: str):
    """Load a frozen causal LM (no LoRA) for logit extraction.

    Changed: loads frozen model only (no adapter).
    Why: testing base 27B-FP8 capability without fine-tuning.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t0 = time.time()
    logger.info("Loading model: %s", model_name)

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    logger.info("Model loaded in %.1fs", time.time() - t0)
    return model, tokenizer


def predict_logit(
    model,
    tokenizer,
    steps: list[Json],
    max_length: int = 4096,
) -> tuple[str, float, float]:
    """Single forward pass -> logit comparison for pass/fail.

    Changed: uses ACE-grounded prompt instead of plain trajectory.
    Why: ACE rules provide grounding context for the model's decision.

    Returns: (prediction, p_pass, p_fail)
    """
    import torch

    prompt = build_prompt(steps)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # Changed: try enable_thinking=False first (Qwen3.5 specific).
    # Why: disable thinking mode to get direct logit output without CoT overhead.
    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        logits = model(**inputs).logits[0, -1, :]

    # Changed: get token IDs for "pass" and "fail".
    # Why: logit comparison is faster than generation (single forward pass).
    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    p_logit = logits[pass_id].item()
    f_logit = logits[fail_id].item()

    # Numerically stable softmax over {pass, fail}
    mx = max(p_logit, f_logit)
    exp_p = math.exp(p_logit - mx)
    exp_f = math.exp(f_logit - mx)
    p_fail = exp_f / (exp_p + exp_f)
    p_pass = exp_p / (exp_p + exp_f)

    pred = "fail" if p_fail > 0.5 else "pass"

    logger.debug(
        "logit pass=%.3f fail=%.3f -> p_fail=%.4f pred=%s (input_len=%d)",
        p_logit, f_logit, p_fail, pred, input_len,
    )
    return pred, p_pass, p_fail


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_labels(dataset_root: Path) -> dict[str, str]:
    """Load gold labels from label.jsonl."""
    labels = {}
    label_path = dataset_root / "label.jsonl"
    if not label_path.exists():
        logger.error("label.jsonl not found at %s", label_path)
        return labels
    with label_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            labels[rec["filename"]] = str(rec["label"]).strip().lower()
    logger.info("Loaded %d labels", len(labels))
    return labels


def load_testcases(dataset_root: Path) -> dict[str, list[Json]]:
    """Load test case trajectories from testcases/ directory."""
    testcase_dir = dataset_root / "testcases"
    if not testcase_dir.exists():
        logger.error("testcases/ directory not found at %s", testcase_dir)
        return {}
    cases = {}
    for path in sorted(testcase_dir.glob("tc*.json")):
        with path.open() as f:
            data = json.load(f)
        if isinstance(data, dict) and "records" in data:
            steps = data["records"]
        elif isinstance(data, list):
            steps = data
        else:
            steps = []
        records = [item for item in steps if isinstance(item, dict)]
        if records:
            cases[path.name] = records
    logger.info("Loaded %d test cases", len(cases))
    return cases


# ---------------------------------------------------------------------------
# Evaluation loop
# ---------------------------------------------------------------------------
def evaluate(
    model,
    tokenizer,
    dataset_root: Path,
    max_length: int = 4096,
    threshold: float = 0.5,
) -> list[dict]:
    """Run logit-mode evaluation on public 20 cases.

    Returns list of result dicts with file, gold, pred, p_pass, p_fail, time.
    """
    labels = load_labels(dataset_root)
    cases = load_testcases(dataset_root)

    if not labels:
        logger.error("No labels loaded. Check dataset path.")
        return []
    if not cases:
        logger.error("No test cases loaded. Check dataset path.")
        return []

    results = []
    total_t0 = time.time()

    for filename in sorted(cases.keys()):
        if filename not in labels:
            logger.warning("Skipping %s: no label", filename)
            continue

        gold = labels[filename]
        steps = cases[filename]

        t0 = time.time()
        pred, p_pass, p_fail = predict_logit(model, tokenizer, steps, max_length)

        # Changed: apply threshold (default 0.5).
        # Why: allows tuning the decision boundary in later experiments.
        pred = "fail" if p_fail > threshold else "pass"

        elapsed = time.time() - t0
        correct = "OK" if pred == gold else "MISS"

        results.append({
            "file": filename,
            "gold": gold,
            "pred": pred,
            "p_pass": p_pass,
            "p_fail": p_fail,
            "time": elapsed,
        })

        logger.info(
            "[%s] %s gold=%s pred=%s p_fail=%.4f (%.1fs)",
            correct, filename, gold, pred, p_fail, elapsed,
        )

    total_time = time.time() - total_t0
    logger.info("Total evaluation time: %.1fs", total_time)
    return results


def print_metrics(results: list[dict]) -> None:
    """Print classification metrics."""
    tp = sum(1 for r in results if r["gold"] == "fail" and r["pred"] == "fail")
    fp = sum(1 for r in results if r["gold"] == "pass" and r["pred"] == "fail")
    fn = sum(1 for r in results if r["gold"] == "fail" and r["pred"] == "pass")
    tn = sum(1 for r in results if r["gold"] == "pass" and r["pred"] == "pass")

    total = len(results)
    correct = tp + tn
    acc = correct / total if total > 0 else 0

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    total_time = sum(r["time"] for r in results)
    avg_time = total_time / total if total > 0 else 0

    print("\n" + "=" * 60)
    print("27B-FP8 LOGIT MODE + ACE-GROUNDED PROMPT")
    print("=" * 60)
    print(f"Accuracy:       {acc * 100:.2f}% ({correct}/{total})")
    print(f"Precision(fail): {prec:.4f}")
    print(f"Recall(fail):    {rec:.4f}")
    print(f"F1(fail):        {f1:.4f}")
    print(f"Confusion:       TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"Time:            {total_time:.1f}s total, {avg_time:.1f}s/case")
    print(f"Projected 200:   {avg_time * 200:.0f}s ({avg_time * 200 / 60:.1f}min)")
    print()

    # Per-case details
    print("Per-case results:")
    print(f"{'File':<15} {'Gold':<6} {'Pred':<6} {'p_fail':>8} {'Time':>6} {'Status'}")
    print("-" * 60)
    for r in results:
        status = "OK" if r["gold"] == r["pred"] else "MISS"
        print(
            f"{r['file']:<15} {r['gold']:<6} {r['pred']:<6} "
            f"{r['p_fail']:>8.4f} {r['time']:>5.1f}s {status}"
        )

    # Mismatches summary
    mismatches = [r for r in results if r["gold"] != r["pred"]]
    if mismatches:
        print(f"\nMismatches ({len(mismatches)}):")
        for r in mismatches:
            print(f"  {r['file']}: gold={r['gold']} pred={r['pred']} p_fail={r['p_fail']:.4f}")
    else:
        print("\nNo mismatches -- perfect accuracy on public 20.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="27B-FP8 logit-mode eval with ACE-grounded prompt on public 20",
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen3.5-27B-FP8",
        help="Model name or path (default: Qwen/Qwen3.5-27B-FP8)",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("/dl2026/dataset"),
        help="Path to dataset with label.jsonl and testcases/ (default: /dl2026/dataset)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=4096,
        help="Max input token length (default: 4096)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Decision threshold for p_fail (default: 0.5)",
    )
    parser.add_argument(
        "--save-results",
        type=Path,
        default=None,
        help="Save per-case results to JSON file",
    )
    args = parser.parse_args()

    model, tokenizer = load_model(args.model)

    # Log token IDs for verification
    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]
    logger.info("Token IDs: pass=%d, fail=%d", pass_id, fail_id)

    results = evaluate(
        model, tokenizer,
        dataset_root=args.dataset_root,
        max_length=args.max_length,
        threshold=args.threshold,
    )

    if not results:
        logger.error("No results produced. Check dataset path and model.")
        sys.exit(1)

    print_metrics(results)

    if args.save_results:
        args.save_results.parent.mkdir(parents=True, exist_ok=True)
        with args.save_results.open("w") as f:
            json.dump(results, f, indent=2)
        logger.info("Results saved to %s", args.save_results)


if __name__ == "__main__":
    main()
