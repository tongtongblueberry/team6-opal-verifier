#!/usr/bin/env python3
"""Self-Instruct Output-First Data Generation for Opal Verifier.

Runs on server with Qwen 0.9B (Qwen/Qwen3.5-0.8B).
Generates (trajectory, label) pairs using output-first:
  1. Select rule + label
  2. LM generates final record + reasoning first
  3. LM generates preceding trajectory
  4. Save raw output (compatible with parse_self_instruct_outputs.py)

Usage (on server):
  cd /workspace/sinjeongmin_opal_verifier/repo
  python3 runs/new/generate_server.py \
    --model Qwen/Qwen3.5-0.8B \
    --num-per-rule 5 \
    --max-new-tokens 4096 \
    --temperature 0.7 \
    --top-p 0.9
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]

# Fixed instruction (gen3 contract)
FIXED_INSTRUCTION = (
    "Given the full Opal command-response trajectory, "
    "judge only whether the final command-response pair (cN, rN) "
    "is valid under the cited rule-book."
)

KST = timezone(timedelta(hours=9))


# ========================================================================
# Rule-book parser
# ========================================================================

def parse_rulebook(path: Path) -> List[Dict[str, str]]:
    """Parse docs/legacy_spec_rules.md into individual rules."""
    text = path.read_text(encoding="utf-8")
    rules = []
    # Split by ### RULE pattern
    blocks = re.split(r"(?=^### RULE \d+)", text, flags=re.MULTILINE)
    for block in blocks:
        m = re.match(r"### (RULE \d+): (.+)", block)
        if not m:
            continue
        rule_ref = m.group(1).replace(" ", "_")
        title = m.group(2).strip()

        def _field(name: str) -> str:
            fm = re.search(rf"- {name}: (.+?)(?:\n- |\n\n|\n###|$)", block, re.DOTALL)
            return fm.group(1).strip() if fm else ""

        rules.append({
            "rule_ref": rule_ref,
            "title": title,
            "spec": _field("SPEC"),
            "condition": _field("CONDITION"),
            "expected_status": _field("EXPECTED_STATUS"),
            "if_violated": _field("IF_VIOLATED"),
            "example": _field("EXAMPLE_TRAJECTORY"),
            # Line range for source_span
            "start_line": text[:text.index(block)].count("\n") + 1 if block in text else 0,
            "block_text": block.strip(),
        })
    return rules


# ========================================================================
# Seed loader — load public20 pass/fail pairs as few-shot examples
# ========================================================================

def load_seeds(public20_input: Path, public20_labels: Path) -> Dict[str, Any]:
    """Load public20 rows grouped by (label, final_method)."""
    rows = []
    with open(public20_input) as f:
        for line in f:
            row = json.loads(line)
            row["_parsed"] = json.loads(row["input"])
            rows.append(row)
    labels = {}
    with open(public20_labels) as f:
        for line in f:
            obj = json.loads(line)
            labels[obj["sample_id"]] = obj["label"]

    seeds = {"pass": {}, "fail": {}}
    for row in rows:
        sid = row["sample_id"]
        label = labels[sid]
        recs = row["_parsed"]["records"]
        last = recs[-1]
        inp = last.get("input", {})
        if isinstance(inp, dict) and "method" in inp:
            method = inp["method"]["name"]
        elif isinstance(inp, dict) and "command" in inp:
            method = "CMD"
        else:
            method = "UNKNOWN"

        if method not in seeds[label]:
            seeds[label][method] = row
        # Prefer shorter examples (fewer records) for prompt brevity
        elif len(recs) < len(seeds[label][method]["_parsed"]["records"]):
            seeds[label][method] = row

    return seeds


def select_seed(seeds: Dict, label: str, method_hint: str) -> Optional[Dict]:
    """Select a seed example matching the method hint, fall back to any."""
    pool = seeds.get(label, {})
    if method_hint in pool:
        return pool[method_hint]
    # Fall back to shortest available
    if pool:
        return min(pool.values(), key=lambda r: len(r["_parsed"]["records"]))
    return None


# ========================================================================
# Prompt builder — output-first generation
# ========================================================================

def format_seed_compact(row: Dict) -> str:
    """Format a public20 row as a compact JSON string for the prompt."""
    recs = row["_parsed"]["records"]
    # Truncate if very long — show first 2 records and last 2 records
    if len(recs) > 6:
        shown = recs[:2] + [{"...": f"({len(recs) - 4} more records)"}] + recs[-2:]
    else:
        shown = recs
    return json.dumps({"records": shown}, ensure_ascii=False, indent=2)


def build_prompt(rule: Dict, label: str, seed_pass: Optional[Dict],
                 seed_fail: Optional[Dict]) -> str:
    """Build output-first generation prompt."""
    # Determine which method this rule targets
    status = rule["expected_status"]
    condition = rule["condition"]

    prompt_parts = []

    # System context
    prompt_parts.append(
        "You are generating training data for an Opal SSD protocol verifier.\n"
        "You must generate a COMPLETE Opal command-response trajectory in JSON format.\n"
        "The trajectory must demonstrate a specific specification rule.\n"
    )

    # Rule
    prompt_parts.append(
        f"## Specification Rule ({rule['rule_ref']})\n"
        f"Title: {rule['title']}\n"
        f"Spec: {rule['spec']}\n"
        f"Condition: {condition}\n"
        f"Expected Status: {status}\n"
        f"If Violated: {rule['if_violated']}\n"
    )

    # Target label
    if label == "pass":
        prompt_parts.append(
            f"## Target: PASS\n"
            f"Generate a trajectory where the final response CORRECTLY follows this rule.\n"
            f"The final record should demonstrate VALID behavior.\n"
        )
    else:
        prompt_parts.append(
            f"## Target: FAIL\n"
            f"Generate a trajectory where the final response VIOLATES this rule.\n"
            f"The final record should demonstrate INVALID behavior "
            f"(wrong status code, wrong data, or missing requirement).\n"
        )

    # Generation order instruction
    prompt_parts.append(
        "## Generation Order (IMPORTANT)\n"
        "1. FIRST decide the final command-response pair:\n"
        "   - What method is invoked?\n"
        "   - What status code does the TPer return?\n"
        "   - What return values?\n"
        f"   - Why is this {label} under the rule?\n"
        "2. THEN construct the preceding trajectory that leads to this final state:\n"
        "   - StartSession with proper authentication if needed\n"
        "   - Intermediate operations (Get, Set, Activate, etc.)\n"
        "   - EndSession where appropriate\n"
    )

    # Seed examples
    if seed_pass:
        prompt_parts.append(
            f"## Seed Example (pass):\n"
            f"```json\n{format_seed_compact(seed_pass)}\n```\n"
        )
    if seed_fail:
        prompt_parts.append(
            f"## Seed Example (fail):\n"
            f"```json\n{format_seed_compact(seed_fail)}\n```\n"
        )

    # Output format
    prompt_parts.append(
        '## Output Format\n'
        'Return ONLY a JSON object (no other text):\n'
        '```json\n'
        '{\n'
        f'  "instruction": "{FIXED_INSTRUCTION}",\n'
        f'  "label": "{label}",\n'
        '  "reasoning": "Brief explanation of why this is ' + label + ' under the rule",\n'
        '  "spec_grounding": {\n'
        f'    "rule_ref": "{rule["rule_ref"]}",\n'
        f'    "source_span": "docs/legacy_spec_rules.md:{rule["start_line"]}-{rule["start_line"] + rule["block_text"].count(chr(10))}",\n'
        '    "condition": "...",\n'
        '    "expected_status": "..."\n'
        '  },\n'
        '  "records": [\n'
        '    {"index": 1, "input": {"invoking_id": {...}, "method": {"name": "...", "uid": "...", "args": {"required": {...}, "optional": {...}}}, "status_codes": "SUCCESS"}, "output": {"return_values": ..., "status_codes": "..."}},\n'
        '    ...\n'
        '  ]\n'
        '}\n'
        '```\n'
    )

    return "\n".join(prompt_parts)


# ========================================================================
# Model runner
# ========================================================================

def load_model(model_name: str, device: str = "auto"):
    """Load Qwen model and tokenizer."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[MODEL] Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name, trust_remote_code=True, local_files_only=True,
        torch_dtype=torch.bfloat16, device_map=device,
    )
    model.eval()
    print(f"[MODEL] Loaded. Device: {model.device}")
    return model, tokenizer


def generate_one(model, tokenizer, prompt: str, max_new_tokens: int,
                 temperature: float, top_p: float) -> str:
    """Generate one response from the model."""
    import torch

    # Use chat template if available, otherwise raw completion
    try:
        messages = [
            {"role": "system", "content": "You generate Opal SSD protocol training data in JSON format."},
            {"role": "user", "content": prompt},
        ]
        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        # Fallback: raw completion
        input_text = prompt + "\n```json\n{"

    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if temperature > 0 else 1.0,
            top_p=top_p,
            do_sample=temperature > 0,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True)


# ========================================================================
# Raw output writer — compatible with parse_self_instruct_outputs.py
# ========================================================================

def make_raw_row(request_id: str, rule_ref: str, label: str,
                 raw_text: str, prompt: str) -> Dict:
    """Wrap LM output into a raw row for the parser."""
    return {
        "request_id": request_id,
        "source_instruction_id": f"output_first_v2:{rule_ref}:{label}",
        "raw_output": raw_text,
        "generation_provenance": {
            "pipeline": "self_instruct_output_first_v2",
            "rule_ref": rule_ref,
            "target_label": label,
            "prompt_length": len(prompt),
        },
    }


# ========================================================================
# Main
# ========================================================================

def main():
    ap = argparse.ArgumentParser(description="Self-Instruct Output-First Generator")
    ap.add_argument("--model", type=str, default="Qwen/Qwen3.5-0.8B")
    ap.add_argument("--num-per-rule", type=int, default=5,
                    help="Generations per (rule, label) combination")
    ap.add_argument("--max-new-tokens", type=int, default=4096)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.9)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--output-dir", type=str, default=None,
                    help="Output directory (default: auto-timestamped)")
    ap.add_argument("--rules", type=str, default=None,
                    help="Comma-separated rule refs to generate for (default: all)")
    ap.add_argument("--labels", type=str, default="pass,fail",
                    help="Comma-separated labels to generate")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print prompts without running model")
    args = ap.parse_args()

    # Paths
    rulebook_path = ROOT / "docs" / "legacy_spec_rules.md"
    public20_input = ROOT / "data" / "local" / "public20" / "public20_input.jsonl"
    public20_labels = ROOT / "data" / "local" / "public20" / "public20_labels.local.jsonl"

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        output_dir = ROOT / "runs" / "new" / f"run_{ts}_KST"
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_output_path = output_dir / "raw_outputs.jsonl"
    requests_path = output_dir / "generation_requests.jsonl"

    print(f"=== Self-Instruct Output-First Generator ===")
    print(f"  model: {args.model}")
    print(f"  num_per_rule: {args.num_per_rule}")
    print(f"  max_new_tokens: {args.max_new_tokens}")
    print(f"  temperature: {args.temperature}")
    print(f"  output: {output_dir}")

    # Load rules
    rules = parse_rulebook(rulebook_path)
    if args.rules:
        selected = set(r.strip() for r in args.rules.split(","))
        rules = [r for r in rules if r["rule_ref"] in selected]
    print(f"\n[RULES] {len(rules)} rules loaded")

    # Load seeds
    seeds = load_seeds(public20_input, public20_labels)
    print(f"[SEEDS] pass methods: {list(seeds['pass'].keys())}")
    print(f"[SEEDS] fail methods: {list(seeds['fail'].keys())}")

    # Parse target labels
    target_labels = [l.strip() for l in args.labels.split(",")]

    # Build generation plan
    plan = []
    for rule in rules:
        for label in target_labels:
            for i in range(args.num_per_rule):
                plan.append((rule, label, i))
    print(f"[PLAN] {len(plan)} total generations")

    # Load model (skip for dry-run)
    model, tokenizer = None, None
    if not args.dry_run:
        model, tokenizer = load_model(args.model)

    # Save latest_run pointer
    latest_path = ROOT / "runs" / "new" / "latest_run.txt"
    latest_path.write_text(str(output_dir.relative_to(ROOT)) + "\n")

    # Generation loop
    generated = 0
    with open(raw_output_path, "a") as f_raw, open(requests_path, "a") as f_req:
        for idx, (rule, label, attempt) in enumerate(plan):
            request_id = f"req_{rule['rule_ref']}_{label}_{attempt:03d}"

            # Select seed examples based on rule's method hint
            method_hint = _guess_method(rule)
            seed_pass = select_seed(seeds, "pass", method_hint)
            seed_fail = select_seed(seeds, "fail", method_hint)

            # Build prompt
            prompt = build_prompt(rule, label, seed_pass, seed_fail)

            # Save request
            f_req.write(json.dumps({
                "request_id": request_id,
                "rule_ref": rule["rule_ref"],
                "target_label": label,
                "attempt": attempt,
                "prompt_length": len(prompt),
            }, ensure_ascii=False) + "\n")
            f_req.flush()

            if args.dry_run:
                if idx < 2:
                    print(f"\n--- Prompt for {request_id} ---")
                    print(prompt[:2000])
                    print("--- (truncated) ---")
                continue

            # Generate
            t0 = time.time()
            try:
                raw_text = generate_one(
                    model, tokenizer, prompt,
                    args.max_new_tokens, args.temperature, args.top_p
                )
            except Exception as e:
                print(f"[ERROR] {request_id}: {e}")
                raw_text = json.dumps({"error": str(e)})

            elapsed = time.time() - t0
            generated += 1

            # Save raw output
            raw_row = make_raw_row(request_id, rule["rule_ref"], label, raw_text, prompt)
            f_raw.write(json.dumps(raw_row, ensure_ascii=False) + "\n")
            f_raw.flush()

            if generated % 10 == 0 or generated <= 3:
                print(f"[{generated}/{len(plan)}] {request_id} "
                      f"({elapsed:.1f}s, {len(raw_text)} chars)")

    print(f"\n=== DONE ===")
    print(f"  Generated: {generated}")
    print(f"  Raw output: {raw_output_path}")
    print(f"  Requests: {requests_path}")


def _guess_method(rule: Dict) -> str:
    """Guess the primary method from rule text."""
    text = (rule["title"] + " " + rule["condition"] + " " + rule["example"]).lower()
    for method in ["Properties", "StartSession", "Get", "Set", "Activate",
                    "GenKey", "Revert", "RevertSP", "Authenticate", "Random"]:
        if method.lower() in text:
            return method
    return "Get"  # default


if __name__ == "__main__":
    main()
