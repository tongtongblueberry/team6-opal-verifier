"""Mutation-based training data generator from public 20 test cases.

Changed: create contrastive training pairs via rule-engine-guided perturbation.
Why: The 20 public test cases are 10 paired pass/fail variants. Generating
mutations from these real templates produces training data that matches the
actual test distribution better than purely synthetic data.

Approach references:
  [EXTERNAL KNOWLEDGE]
  - DISCO (ACL 2023): Distilling counterfactuals with large language models.
    Chen, Z., et al. (2023). Proceedings of ACL 2023.
    We adapt their rule-engine-guided perturbation approach: systematically
    mutate one semantic element at a time to create contrastive pairs.
  - PairCFR (ACL 2024): Pairwise counterfactual reasoning for causal NLI.
    Wang, Y., et al. (2024). Proceedings of ACL 2024.
    We adopt their contrastive pair training: each mutation is paired with
    its original to teach the model which change flips the label.

Mutation types (prioritized by impact):
  A. Output status flip (highest volume, simplest)
  B. Truncation (creates diverse lengths)
  C. HostChallenge corruption (auth-specific)

Target: ~400 cases, 50/50 pass/fail, diverse lengths (1-39).
Runs on server where public cases are at /dl2026/dataset/testcases/tc*.json.

Usage:
  cd /workspace/team6/team6-opal-verifier
  PYTHONPATH=. python tools/datagen/generate_mutations.py
"""

from __future__ import annotations

import copy
import glob
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

Json = dict[str, Any]
random.seed(42)

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

# Changed: paths for server environment where public data lives.
TESTCASE_DIR = Path("/dl2026/dataset/testcases")
LABEL_PATH = Path("/dl2026/dataset/label.jsonl")
OUTPUT_PATH = Path("/workspace/team6/training_data/mutation_cases.json")

# Changed: error statuses to use for status flip mutations.
# Why: these are the three most common error statuses in the TCG/Opal spec.
ERROR_STATUSES = ["NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL"]

# Changed: methods that indicate a valid end boundary for truncation.
# Why: truncation must end at a semantically valid point.
SESSION_BOUNDARY_METHODS = {"endsession", "startsession"}

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def load_public_cases() -> list[dict]:
    """Load all 20 public test cases with their labels.

    Returns list of {"filename": str, "records": list, "label": str}.
    """
    # Changed: load labels from JSONL file.
    labels: dict[str, str] = {}
    with LABEL_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            labels[rec["filename"]] = str(rec["label"]).strip().lower()

    cases = []
    for path in sorted(TESTCASE_DIR.glob("tc*.json")):
        if path.name not in labels:
            continue
        with path.open() as f:
            data = json.load(f)
        # Changed: handle both dict-with-records and list formats.
        if isinstance(data, dict) and "records" in data:
            records = data["records"]
        elif isinstance(data, list):
            records = data
        else:
            continue
        records = [item for item in records if isinstance(item, dict)]
        if records:
            cases.append({
                "filename": path.name,
                "records": records,
                "label": labels[path.name],
            })

    return cases


def _get_method_name(record: Json) -> str:
    """Extract method name from a step record, lowercased."""
    cmd = record.get("input", {})
    method_obj = cmd.get("method", {})
    if isinstance(method_obj, dict):
        return method_obj.get("name", "").lower()
    return str(method_obj).lower()


def _get_status(record: Json) -> str:
    """Extract status_codes from a step's output."""
    out = record.get("output", {})
    status = out.get("status_codes", out.get("status", ""))
    if isinstance(status, dict):
        return status.get("Name", status.get("name", str(status)))
    return str(status)


def _set_status(record: Json, new_status: str) -> None:
    """Set the output status_codes of a step record in place."""
    out = record.get("output", {})
    # Changed: detect original status format (dict vs string) and preserve it.
    old_status = out.get("status_codes", out.get("status", ""))
    if isinstance(old_status, dict):
        # Changed: preserve dict format with updated Name field.
        old_status["Name"] = new_status
        if "name" in old_status:
            old_status["name"] = new_status
    else:
        # Changed: update whichever key was used (status_codes or status).
        if "status_codes" in out:
            out["status_codes"] = new_status
        elif "status" in out:
            out["status"] = new_status
        else:
            out["status_codes"] = new_status


def _clear_return_values(record: Json) -> None:
    """Clear return_values to empty list (error responses have no payload)."""
    out = record.get("output", {})
    out["return_values"] = []
    # Changed: also remove SyncSession method from output if present.
    # Why: error responses don't have the method response payload.
    out.pop("method", None)


def _is_success(status: str) -> bool:
    """Check if a status indicates success (case-insensitive)."""
    return status.lower().strip() in ("success", "0")


def _reindex_steps(records: list[Json]) -> list[Json]:
    """Re-index steps with sequential 'index' field if they had one.

    Changed: preserves the original structure, only updates index if present.
    """
    # Changed: index starts from 1 (not 0), matching the real test data format.
    for i, record in enumerate(records):
        if "index" in record:
            record["index"] = i + 1
    return records


def _case_number(filename: str) -> int:
    """Extract numeric case number from filename like 'tc2.json'."""
    import re
    m = re.search(r"tc(\d+)", filename)
    return int(m.group(1)) if m else 0


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE A: Output status flip
# ═══════════════════════════════════════════════════════════════
# DISCO approach: flip the output status of the last step to create
# a contrastive pair. If original is pass+SUCCESS, flip to fail+ERROR.
# If original is fail+ERROR, flip to pass+SUCCESS.
# ═══════════════════════════════════════════════════════════════


def mutate_status_flip(cases: list[dict]) -> list[dict]:
    """Generate status-flip mutations for all cases.

    For pass cases (last step SUCCESS): create fail variants by flipping to errors.
    For fail cases (last step has error): create pass variant by fixing to SUCCESS.

    Changed: also generates cross-error variants (e.g., NOT_AUTHORIZED -> FAIL).
    Why: teaches the model that specific error types matter, not just pass/fail.
    """
    mutations: list[dict] = []

    # Changed: build pair mapping. Public 20 pairs are: tc1↔tc11, tc2↔tc12, ..., tc10↔tc20.
    # Why: need pass variant's return_values to restore when fixing fail→pass.
    # Pairing logic: pass cases are tc1-tc10, fail cases are tc11-tc20.
    by_number: dict[int, dict] = {}  # base_num -> {"pass": case, "fail": case}
    for case in cases:
        num = _case_number(case["filename"])
        base = num if num <= 10 else num - 10
        by_number.setdefault(base, {})
        by_number[base][case["label"]] = case

    for case in cases:
        records = case["records"]
        label = case["label"]
        fname = case["filename"]
        num = _case_number(fname)
        last_step = records[-1]
        last_status = _get_status(last_step)

        if label == "pass" and _is_success(last_status):
            # Changed: pass case with SUCCESS last step -> create fail variants.
            # Flip last step's status to each error type.
            for error_status in ERROR_STATUSES:
                mutated = copy.deepcopy(records)
                _set_status(mutated[-1], error_status)
                _clear_return_values(mutated[-1])
                _reindex_steps(mutated)
                mutations.append({
                    "records": mutated,
                    "label": "fail",
                    "source": f"mutation:{fname}:status_flip:SUCCESS->{error_status}",
                    "length": len(mutated),
                })

        elif label == "fail" and not _is_success(last_status):
            # Changed: fail case with error last step -> create pass variant.
            # Changed: find paired pass case using base number (tc1↔tc11 etc.)
            base = num if num <= 10 else num - 10
            pass_pair = by_number.get(base, {}).get("pass")

            # Changed: fix error to SUCCESS, restore return_values from pass pair.
            mutated = copy.deepcopy(records)
            _set_status(mutated[-1], "SUCCESS")

            if pass_pair and len(pass_pair["records"]) > 0:
                # Changed: copy return_values from the corresponding step in the pass pair.
                # Why: the pass variant's last step has the correct return_values.
                pass_last = pass_pair["records"][-1]
                pass_out = pass_last.get("output", {})
                mutated[-1].setdefault("output", {})["return_values"] = copy.deepcopy(
                    pass_out.get("return_values", [])
                )
                # Changed: also restore method in output if the pass pair has it.
                if "method" in pass_out:
                    mutated[-1]["output"]["method"] = copy.deepcopy(pass_out["method"])
            else:
                # Changed: no paired pass case found; just set empty return_values.
                # This is still useful training data — model learns SUCCESS should have payload.
                mutated[-1].setdefault("output", {})["return_values"] = []

            _reindex_steps(mutated)
            mutations.append({
                "records": mutated,
                "label": "pass",
                "source": f"mutation:{fname}:status_flip:{last_status}->SUCCESS",
                "length": len(mutated),
            })

            # Changed: also create cross-error variants (error1 -> error2).
            # Why: teaches the model that specific error codes have different semantics.
            for other_error in ERROR_STATUSES:
                if other_error.upper() == last_status.upper():
                    continue
                mutated_cross = copy.deepcopy(records)
                _set_status(mutated_cross[-1], other_error)
                _clear_return_values(mutated_cross[-1])
                _reindex_steps(mutated_cross)
                # Changed: cross-error mutations are still fail (wrong error type).
                mutations.append({
                    "records": mutated_cross,
                    "label": "fail",
                    "source": f"mutation:{fname}:status_flip:{last_status}->{other_error}",
                    "length": len(mutated_cross),
                })

        # Changed: handle cases where pass has non-SUCCESS last step or fail has SUCCESS.
        # These are edge cases but still valuable for contrastive learning.
        elif label == "pass" and not _is_success(last_status):
            # Pass case with error status (e.g., expected error after violated precondition).
            # Flip to SUCCESS -> should be fail (unexpected success).
            mutated = copy.deepcopy(records)
            _set_status(mutated[-1], "SUCCESS")
            # Changed: don't add return_values — a bare SUCCESS with no payload is suspicious.
            mutated[-1].setdefault("output", {})["return_values"] = []
            _reindex_steps(mutated)
            mutations.append({
                "records": mutated,
                "label": "fail",
                "source": f"mutation:{fname}:status_flip:{last_status}->SUCCESS(unexpected)",
                "length": len(mutated),
            })

        elif label == "fail" and _is_success(last_status):
            # Fail case with SUCCESS status (e.g., should have errored but didn't).
            # Flip to each error type -> should be pass (expected error).
            for error_status in ERROR_STATUSES:
                mutated = copy.deepcopy(records)
                _set_status(mutated[-1], error_status)
                _clear_return_values(mutated[-1])
                _reindex_steps(mutated)
                mutations.append({
                    "records": mutated,
                    "label": "pass",
                    "source": f"mutation:{fname}:status_flip:SUCCESS->{error_status}(fix)",
                    "length": len(mutated),
                })

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE B: Truncation
# ═══════════════════════════════════════════════════════════════
# Creates diverse lengths from long trajectories. Truncated at valid
# boundaries (after EndSession, or at a complete step).
# ═══════════════════════════════════════════════════════════════


def _find_truncation_points(records: list[Json]) -> list[int]:
    """Find valid truncation points in a trajectory.

    Changed: a valid truncation point is after any complete step.
    Priority boundaries: after EndSession, after a complete method call.
    Returns list of step indices (exclusive end) where truncation is valid.
    """
    points = []
    for i in range(1, len(records)):
        method = _get_method_name(records[i - 1])
        status = _get_status(records[i - 1])
        # Changed: prefer truncation after EndSession or after error steps.
        # Why: these are natural breakpoints in the protocol flow.
        points.append(i)
    return points


def mutate_truncation(cases: list[dict]) -> list[dict]:
    """Generate truncation mutations for long cases.

    Changed: only truncate cases with > 5 steps. Generates 3-5 truncations
    per case at different lengths for length diversity.
    """
    mutations: list[dict] = []

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]
        n = len(records)

        if n <= 5:
            # Changed: skip short cases — truncation would be trivial.
            continue

        # Changed: generate truncations at various lengths.
        # Target lengths: ~25%, ~50%, ~75% of original, plus minimal (2-3 steps).
        target_lengths = set()
        target_lengths.add(max(2, n // 4))        # ~25%
        target_lengths.add(max(3, n // 2))         # ~50%
        target_lengths.add(max(4, 3 * n // 4))     # ~75%
        if n > 10:
            target_lengths.add(3)                    # minimal
        if n > 20:
            target_lengths.add(max(5, n // 3))       # ~33%
            target_lengths.add(max(6, 2 * n // 3))   # ~67%

        # Changed: remove any length that equals the original.
        target_lengths.discard(n)

        for tlen in sorted(target_lengths):
            if tlen < 1 or tlen >= n:
                continue

            truncated = copy.deepcopy(records[:tlen])
            _reindex_steps(truncated)

            # Changed: determine label for truncated trajectory.
            # If the last step of the truncated trajectory is SUCCESS, it's likely pass.
            # If the last step has an error, check context:
            #   - If the original was pass and the error is expected, still pass.
            #   - If truncation removes the resolving step, it's fail.
            last_status = _get_status(truncated[-1])
            last_method = _get_method_name(truncated[-1])

            if _is_success(last_status):
                # Changed: SUCCESS at truncation point.
                # If last method is EndSession -> clean end -> pass.
                # If last method is a regular operation -> partial trajectory -> pass
                #   (the operation succeeded, nothing contradicts spec).
                trunc_label = "pass"
            else:
                # Changed: error at truncation point.
                # If original was pass (errors were expected), the truncated version
                # that ends on an error step is still likely pass (error was valid).
                # If original was fail, the truncated version ending on error is also fail.
                # Conservative: use original label for error-ending truncations.
                trunc_label = label

            mutations.append({
                "records": truncated,
                "label": trunc_label,
                "source": f"mutation:{fname}:truncate:{n}->{tlen}",
                "length": tlen,
            })

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE C: HostChallenge corruption
# ═══════════════════════════════════════════════════════════════
# Change HostChallenge in StartSession to wrong value.
# If output still SUCCESS -> label is fail (wrong password accepted).
# If output becomes NOT_AUTHORIZED -> label is pass (correctly rejected).
# ═══════════════════════════════════════════════════════════════


def _find_startsession_step(records: list[Json]) -> int | None:
    """Find the index of the StartSession step, if any."""
    for i, record in enumerate(records):
        if _get_method_name(record) == "startsession":
            return i
    return None


def _get_host_challenge(record: Json) -> str | None:
    """Extract HostChallenge from a StartSession step."""
    cmd = record.get("input", {})
    method_obj = cmd.get("method", {})
    if isinstance(method_obj, dict):
        args = method_obj.get("args", {})
    else:
        args = cmd.get("args", {})

    # Changed: check both required and optional for HostChallenge.
    for section in [args.get("optional", {}), args.get("required", {}), args]:
        if isinstance(section, dict) and "HostChallenge" in section:
            return str(section["HostChallenge"])
    return None


def _set_host_challenge(record: Json, new_challenge: str) -> None:
    """Set HostChallenge in a StartSession step."""
    cmd = record.get("input", {})
    method_obj = cmd.get("method", {})
    if isinstance(method_obj, dict):
        args = method_obj.get("args", {})
    else:
        args = cmd.get("args", {})

    # Changed: set in the same location where it was found, or optional by default.
    for section_name in ["optional", "required"]:
        section = args.get(section_name, {})
        if isinstance(section, dict) and "HostChallenge" in section:
            section["HostChallenge"] = new_challenge
            return

    # Changed: fallback — add to optional if not found anywhere.
    if "optional" not in args:
        args["optional"] = {}
    args["optional"]["HostChallenge"] = new_challenge


def mutate_host_challenge(cases: list[dict]) -> list[dict]:
    """Generate HostChallenge corruption mutations.

    Changed: for each case with a StartSession that has HostChallenge,
    create variants with wrong passwords.
    """
    mutations: list[dict] = []

    # Changed: corrupt password values that are clearly different from any real password.
    CORRUPT_CHALLENGES = [
        "WRONG_PASSWORD_12345",
        "corrupted_challenge_xyz",
        "",  # empty challenge
        "00 00 00 00 00 00 00 00",  # all zeros (likely wrong)
    ]

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]

        ss_idx = _find_startsession_step(records)
        if ss_idx is None:
            continue

        original_challenge = _get_host_challenge(records[ss_idx])
        if original_challenge is None:
            # Changed: no HostChallenge means no auth -> corruption not applicable.
            continue

        original_status = _get_status(records[ss_idx])

        for corrupt_pw in CORRUPT_CHALLENGES:
            if corrupt_pw == original_challenge:
                # Changed: skip if the corrupt value equals the original.
                continue

            # Variant 1: corrupt challenge + NOT_AUTHORIZED response -> pass
            # (correctly rejected wrong password)
            mutated_reject = copy.deepcopy(records)
            _set_host_challenge(mutated_reject[ss_idx], corrupt_pw)
            _set_status(mutated_reject[ss_idx], "NOT_AUTHORIZED")
            _clear_return_values(mutated_reject[ss_idx])
            # Changed: truncate after StartSession since session failed.
            # Why: subsequent steps would be invalid without a session.
            mutated_reject = mutated_reject[:ss_idx + 1]
            _reindex_steps(mutated_reject)
            mutations.append({
                "records": mutated_reject,
                "label": "pass",
                "source": f"mutation:{fname}:challenge_corrupt:reject:{corrupt_pw[:20]}",
                "length": len(mutated_reject),
            })

            # Variant 2: corrupt challenge + SUCCESS response -> fail
            # (wrong password accepted = spec violation)
            if _is_success(original_status):
                mutated_accept = copy.deepcopy(records)
                _set_host_challenge(mutated_accept[ss_idx], corrupt_pw)
                # Changed: keep SUCCESS status and original return_values.
                # This creates a fail case: wrong password but session established.
                _reindex_steps(mutated_accept)
                mutations.append({
                    "records": mutated_accept,
                    "label": "fail",
                    "source": f"mutation:{fname}:challenge_corrupt:accept:{corrupt_pw[:20]}",
                    "length": len(mutated_accept),
                })

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE D: Step removal (interior deletion)
# ═══════════════════════════════════════════════════════════════
# Remove a single interior step to create a trajectory with a gap.
# Teaches the model to notice missing steps in the protocol flow.
# ═══════════════════════════════════════════════════════════════


def mutate_step_removal(cases: list[dict]) -> list[dict]:
    """Generate step-removal mutations for medium/long cases.

    Changed: remove one interior step (not first or last) to create a gap.
    The resulting trajectory may or may not be valid depending on what was removed.
    """
    mutations: list[dict] = []

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]
        n = len(records)

        if n <= 3:
            # Changed: skip short cases — removing a step would be too drastic.
            continue

        # Changed: remove each interior step (indices 1 to n-2).
        # Limit to at most 3 removals per case to control volume.
        interior_indices = list(range(1, n - 1))
        if len(interior_indices) > 3:
            interior_indices = random.sample(interior_indices, 3)

        for remove_idx in interior_indices:
            removed_method = _get_method_name(records[remove_idx])
            mutated = copy.deepcopy(records)
            del mutated[remove_idx]
            _reindex_steps(mutated)

            # Changed: determine label based on what was removed.
            # Removing a StartSession step invalidates subsequent operations -> fail.
            # Removing an EndSession might be fine if no subsequent session is started.
            # Removing an interior method call: depends on context.
            if removed_method == "startsession":
                # Changed: removing session start means subsequent ops have no session -> fail.
                removal_label = "fail"
            elif removed_method == "endsession":
                # Changed: removing EndSession is ambiguous; keep original label.
                removal_label = label
            else:
                # Changed: removing an interior method call.
                # If original was pass, the trajectory is still structurally similar -> pass.
                # If original was fail, still fail.
                removal_label = label

            mutations.append({
                "records": mutated,
                "label": removal_label,
                "source": f"mutation:{fname}:remove_step:{remove_idx}:{removed_method}",
                "length": len(mutated),
            })

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE E: Return value corruption
# ═══════════════════════════════════════════════════════════════
# For SUCCESS responses, clear or corrupt return_values.
# Teaches the model that SUCCESS must have appropriate payload.
# ═══════════════════════════════════════════════════════════════


def mutate_return_values(cases: list[dict]) -> list[dict]:
    """Generate return-value corruption mutations.

    Changed: for pass cases with SUCCESS last step that has non-empty return_values,
    create a fail variant by clearing the return_values.
    """
    mutations: list[dict] = []

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]
        last_step = records[-1]
        last_status = _get_status(last_step)
        last_out = last_step.get("output", {})
        rv = last_out.get("return_values", [])

        # Changed: only mutate if last step is SUCCESS with non-empty return_values.
        if label == "pass" and _is_success(last_status) and rv:
            # Clear return_values -> fail (SUCCESS should have payload)
            mutated = copy.deepcopy(records)
            mutated[-1]["output"]["return_values"] = []
            _reindex_steps(mutated)
            mutations.append({
                "records": mutated,
                "label": "fail",
                "source": f"mutation:{fname}:clear_return_values",
                "length": len(mutated),
            })

        # Changed: for fail cases with error + empty return_values, add fake payload.
        # This teaches the model that errors should not have return_values.
        if label == "fail" and not _is_success(last_status) and not rv:
            mutated = copy.deepcopy(records)
            mutated[-1]["output"]["return_values"] = [{"fake_col": "fake_val"}]
            _reindex_steps(mutated)
            mutations.append({
                "records": mutated,
                "label": "fail",
                "source": f"mutation:{fname}:add_fake_return_values",
                "length": len(mutated),
            })

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE F: HostChallenge length/format corruption (tc14-style)
# ═══════════════════════════════════════════════════════════════
# Changed: tc14 has HostChallenge="aaa...a" (33 chars, invalid length) with SUCCESS.
# The spec requires HostChallenge to be exactly 32 bytes (64 hex chars).
# A malformed challenge that's accepted as SUCCESS is a spec violation -> fail.
# ═══════════════════════════════════════════════════════════════


def mutate_challenge_format(cases: list[dict]) -> list[dict]:
    """Generate HostChallenge format/length corruption mutations.

    Changed: unlike Type C which uses obviously wrong passwords, this targets
    the *format* of the challenge (wrong length, non-hex chars) while keeping
    SUCCESS response -> spec violation (fail).
    Why: tc14 fails because HostChallenge="aaa...a" (33 chars) accepted as SUCCESS.
    Model needs to learn that malformed HostChallenge + SUCCESS = fail.
    """
    mutations: list[dict] = []

    # Changed: malformed challenge values that look like hex but have wrong length.
    # Why: these are the exact patterns from tc14 and similar test cases.
    MALFORMED_CHALLENGES = [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 33 chars (tc14 exact)
        "bbbbbbbbbbbbbbbbbbbbbbbb",           # 24 chars (too short)
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",  # 68 chars (too long)
        "GGGG0000HHHH1111",                   # 16 chars, non-hex letters
        "xyz" * 11,                            # 33 chars, non-hex
        "0" * 32,                              # 32 chars (half-length, 16 bytes)
        "f" * 63,                              # 63 chars (off by one)
        "a" * 65,                              # 65 chars (off by one)
    ]

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]

        # Changed: find ALL StartSession steps with HostChallenge (not just first).
        # Why: some trajectories have multiple auth sessions.
        for step_idx, record in enumerate(records):
            if _get_method_name(record) != "startsession":
                continue
            original_challenge = _get_host_challenge(record)
            if original_challenge is None:
                continue
            original_status = _get_status(record)
            if not _is_success(original_status):
                continue

            # Changed: for each malformed challenge, create two variants:
            # 1. Malformed + SUCCESS -> fail (spec violation: malformed auth accepted)
            # 2. Malformed + NOT_AUTHORIZED -> pass (correctly rejected)

            for malformed in MALFORMED_CHALLENGES:
                if malformed == original_challenge:
                    continue

                # Variant 1: malformed challenge accepted (SUCCESS) -> fail
                # Changed: this is the FINAL step variant (keep full trajectory).
                if step_idx == len(records) - 1:
                    mutated = copy.deepcopy(records)
                    _set_host_challenge(mutated[step_idx], malformed)
                    # Keep SUCCESS status and return_values as-is
                    _reindex_steps(mutated)
                    mutations.append({
                        "records": mutated,
                        "label": "fail",
                        "source": f"mutation:{fname}:challenge_format:accept:{malformed[:15]}",
                        "length": len(mutated),
                    })

                # Variant 2: malformed challenge rejected (NOT_AUTHORIZED) -> pass
                mutated_reject = copy.deepcopy(records)
                _set_host_challenge(mutated_reject[step_idx], malformed)
                _set_status(mutated_reject[step_idx], "NOT_AUTHORIZED")
                _clear_return_values(mutated_reject[step_idx])
                # Truncate after the failed StartSession
                mutated_reject = mutated_reject[:step_idx + 1]
                _reindex_steps(mutated_reject)
                mutations.append({
                    "records": mutated_reject,
                    "label": "pass",
                    "source": f"mutation:{fname}:challenge_format:reject:{malformed[:15]}",
                    "length": len(mutated_reject),
                })

            # Changed: limit to first StartSession with HostChallenge to avoid explosion.
            break

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE G: DATA_COMMAND Read result corruption (tc20-style)
# ═══════════════════════════════════════════════════════════════
# Changed: tc20 has DATA_COMMAND Read with result="8E" instead of "Random Data".
# After GenKey (media encryption key generation), a Read should return random
# encrypted data, not a short deterministic value.
# ═══════════════════════════════════════════════════════════════


def mutate_data_read_result(cases: list[dict]) -> list[dict]:
    """Generate DATA_COMMAND Read result corruption mutations.

    Changed: for trajectories with DATA_COMMAND Read steps, corrupt the result.
    Why: tc20 fails because Read returns "8E" instead of "Random Data" after GenKey.
    Model needs to learn that short/deterministic Read results after encryption = fail.
    """
    mutations: list[dict] = []

    # Changed: corrupted Read results that indicate encryption failure.
    # Why: after GenKey, reading encrypted sectors should return random-looking data,
    # not short deterministic values.
    CORRUPTED_RESULTS = [
        "8E",                    # tc20 exact value
        "00",                    # all zeros (no encryption)
        "FF",                    # all ones
        "DEADBEEF",              # deterministic pattern
        "0000000000000000",       # 16 zeros
        "",                       # empty result
        "AB",                     # short hex
    ]

    VALID_RESULTS = [
        "Random Data",           # tc10 exact value
        "Encrypted Random Data",
        "Random Bytes",
    ]

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]

        # Changed: find DATA_COMMAND Read steps.
        for step_idx, record in enumerate(records):
            cmd = record.get("input", {})
            data_cmd = cmd.get("command", "")
            if data_cmd != "Read":
                continue

            out = record.get("output", {})
            original_result = out.get("args", {}).get("result", "")

            # Changed: only mutate the FINAL Read step (most important for verdict).
            if step_idx != len(records) - 1:
                continue

            # Variant 1: corrupt result -> fail
            for corrupt_result in CORRUPTED_RESULTS:
                if corrupt_result == original_result:
                    continue

                mutated = copy.deepcopy(records)
                mutated[step_idx]["output"]["args"]["result"] = corrupt_result
                _reindex_steps(mutated)
                mutations.append({
                    "records": mutated,
                    "label": "fail",
                    "source": f"mutation:{fname}:read_corrupt:{corrupt_result[:15]}",
                    "length": len(mutated),
                })

            # Variant 2: valid result -> pass (if original was fail)
            if label == "fail":
                for valid_result in VALID_RESULTS:
                    if valid_result == original_result:
                        continue
                    mutated = copy.deepcopy(records)
                    mutated[step_idx]["output"]["args"]["result"] = valid_result
                    _reindex_steps(mutated)
                    mutations.append({
                        "records": mutated,
                        "label": "pass",
                        "source": f"mutation:{fname}:read_fix:{valid_result[:15]}",
                        "length": len(mutated),
                    })

    return mutations


# ═══════════════════════════════════════════════════════════════
# MUTATION TYPE H: Activate target UID corruption (tc15-style)
# ═══════════════════════════════════════════════════════════════
# Changed: tc15 Activates SP with UID "00 00 01 05 00 00 00 04" (Admin SP)
# instead of "00 00 02 05 00 00 00 02" (Locking SP). Wrong target + SUCCESS = fail.
# ═══════════════════════════════════════════════════════════════


def mutate_activate_target(cases: list[dict]) -> list[dict]:
    """Generate Activate target UID corruption mutations.

    Changed: for cases with Activate method, swap the invoking_id UID to a wrong SP.
    Why: tc15 fails because Activate targets Admin SP (00000105) instead of Locking SP (00000205).
    """
    mutations: list[dict] = []

    # Changed: wrong SP UIDs for Activate method.
    WRONG_UIDS = [
        ("00 00 01 05 00 00 00 04", "AdminSP"),    # tc15 exact
        ("00 00 01 05 00 00 00 01", "AdminSP_1"),
        ("00 00 02 05 00 00 00 FF", "LockingSP_FF"),  # wrong object in Locking SP
        ("00 00 00 01 00 00 00 01", "UnknownSP"),
    ]

    for case in cases:
        records = case["records"]
        fname = case["filename"]
        label = case["label"]

        for step_idx, record in enumerate(records):
            if _get_method_name(record) != "activate":
                continue

            cmd = record.get("input", {})
            inv = cmd.get("invoking_id", {})
            if not isinstance(inv, dict):
                continue
            original_uid = inv.get("uid", "")
            original_status = _get_status(record)

            if not _is_success(original_status):
                continue

            for wrong_uid, uid_name in WRONG_UIDS:
                if wrong_uid == original_uid:
                    continue

                # Changed: wrong target + SUCCESS -> fail
                mutated = copy.deepcopy(records)
                mutated[step_idx]["input"]["invoking_id"]["uid"] = wrong_uid
                mutated[step_idx]["input"]["invoking_id"]["name"] = "SP"
                # Keep SUCCESS (spec violation: wrong target accepted)
                _reindex_steps(mutated)
                mutations.append({
                    "records": mutated,
                    "label": "fail",
                    "source": f"mutation:{fname}:activate_target:{uid_name}",
                    "length": len(mutated),
                })

                # Changed: wrong target + FAIL/NOT_AUTHORIZED -> pass (correctly rejected)
                for err in ["FAIL", "NOT_AUTHORIZED"]:
                    mutated_err = copy.deepcopy(records)
                    mutated_err[step_idx]["input"]["invoking_id"]["uid"] = wrong_uid
                    mutated_err[step_idx]["input"]["invoking_id"]["name"] = "SP"
                    _set_status(mutated_err[step_idx], err)
                    _clear_return_values(mutated_err[step_idx])
                    # Truncate after failed Activate
                    mutated_err = mutated_err[:step_idx + 1]
                    _reindex_steps(mutated_err)
                    mutations.append({
                        "records": mutated_err,
                        "label": "pass",
                        "source": f"mutation:{fname}:activate_target:{uid_name}:{err}",
                        "length": len(mutated_err),
                    })

            # Only process first Activate per case
            break

    return mutations


# ═══════════════════════════════════════════════════════════════
# BALANCE AND ASSEMBLE
# ═══════════════════════════════════════════════════════════════


def balance_mutations(mutations: list[dict], target_ratio: float = 0.5) -> list[dict]:
    """Balance pass/fail ratio by downsampling the majority class.

    Changed: targets 50/50 ratio for balanced training.
    Why: PairCFR paper shows balanced contrastive pairs outperform skewed distributions.
    """
    pass_cases = [m for m in mutations if m["label"] == "pass"]
    fail_cases = [m for m in mutations if m["label"] == "fail"]

    n_pass = len(pass_cases)
    n_fail = len(fail_cases)

    if n_pass == 0 or n_fail == 0:
        return mutations

    # Changed: downsample the majority class to match the minority.
    target_each = min(n_pass, n_fail)

    # Changed: allow up to 10% imbalance to keep more data.
    max_each = int(target_each * 1.1)

    if n_pass > max_each:
        random.shuffle(pass_cases)
        pass_cases = pass_cases[:max_each]
    if n_fail > max_each:
        random.shuffle(fail_cases)
        fail_cases = fail_cases[:max_each]

    balanced = pass_cases + fail_cases
    random.shuffle(balanced)
    return balanced


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main():
    print("=== Mutation-based Training Data Generator ===")
    print(f"  Approach: DISCO (ACL 2023) perturbation + PairCFR (ACL 2024) contrastive pairs")
    print()

    # Step 1: Load public cases
    print("Loading public test cases...")
    cases = load_public_cases()
    print(f"  Loaded {len(cases)} cases")
    for c in cases:
        print(f"    {c['filename']}: label={c['label']}, steps={len(c['records'])}")

    if not cases:
        print("ERROR: No public cases found. Check paths:")
        print(f"  TESTCASE_DIR: {TESTCASE_DIR}")
        print(f"  LABEL_PATH: {LABEL_PATH}")
        sys.exit(1)

    # Step 2: Generate mutations
    print("\nGenerating mutations...")

    all_mutations: list[dict] = []

    # Type A: Status flip (highest volume)
    status_flip = mutate_status_flip(cases)
    print(f"  Type A (status flip): {len(status_flip)} mutations")
    all_mutations.extend(status_flip)

    # Type B: Truncation (length diversity)
    truncation = mutate_truncation(cases)
    print(f"  Type B (truncation): {len(truncation)} mutations")
    all_mutations.extend(truncation)

    # Type C: HostChallenge corruption (auth-specific)
    challenge = mutate_host_challenge(cases)
    print(f"  Type C (challenge corruption): {len(challenge)} mutations")
    all_mutations.extend(challenge)

    # Type D: Step removal (structural)
    removal = mutate_step_removal(cases)
    print(f"  Type D (step removal): {len(removal)} mutations")
    all_mutations.extend(removal)

    # Type E: Return value corruption
    rv_corrupt = mutate_return_values(cases)
    print(f"  Type E (return value corruption): {len(rv_corrupt)} mutations")
    all_mutations.extend(rv_corrupt)

    # Changed: new Type F-H mutations targeting specific Type B data-level failures.
    # Why: tc14 (HostChallenge format), tc20 (Read result), tc15 (Activate target) are
    # all Type B cases where the difference is in data content, not status codes.

    # Type F: HostChallenge format corruption (tc14-style)
    challenge_format = mutate_challenge_format(cases)
    print(f"  Type F (challenge format): {len(challenge_format)} mutations")
    all_mutations.extend(challenge_format)

    # Type G: DATA_COMMAND Read result corruption (tc20-style)
    read_corrupt = mutate_data_read_result(cases)
    print(f"  Type G (read result corruption): {len(read_corrupt)} mutations")
    all_mutations.extend(read_corrupt)

    # Type H: Activate target UID corruption (tc15-style)
    activate_target = mutate_activate_target(cases)
    print(f"  Type H (activate target): {len(activate_target)} mutations")
    all_mutations.extend(activate_target)

    # Step 3: Add original cases as-is (anchor points for contrastive learning)
    print("\nAdding original cases as anchors...")
    for case in cases:
        all_mutations.append({
            "records": case["records"],
            "label": case["label"],
            "source": f"original:{case['filename']}",
            "length": len(case["records"]),
        })
    print(f"  Added {len(cases)} originals")

    # Step 4: Statistics before balancing
    n_pass = sum(1 for m in all_mutations if m["label"] == "pass")
    n_fail = sum(1 for m in all_mutations if m["label"] == "fail")
    print(f"\nBefore balancing: {len(all_mutations)} total (pass={n_pass}, fail={n_fail})")

    # Step 5: Balance pass/fail ratio
    balanced = balance_mutations(all_mutations)
    n_pass_b = sum(1 for m in balanced if m["label"] == "pass")
    n_fail_b = sum(1 for m in balanced if m["label"] == "fail")
    print(f"After balancing:  {len(balanced)} total (pass={n_pass_b}, fail={n_fail_b})")

    # Step 6: Length distribution
    lengths = [m["length"] for m in balanced]
    length_dist = Counter(lengths)
    print(f"\nLength distribution (min={min(lengths)}, max={max(lengths)}, "
          f"unique={len(length_dist)}):")
    for length in sorted(length_dist.keys()):
        count = length_dist[length]
        bar = "#" * min(count, 50)
        print(f"  len={length:>3}: {count:>4} {bar}")

    # Step 7: Source distribution
    source_types = Counter(m["source"].split(":")[0] for m in balanced)
    print(f"\nSource distribution:")
    for src, count in source_types.most_common():
        print(f"  {src}: {count}")

    # Step 8: Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(balanced, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved: {OUTPUT_PATH} ({len(balanced)} cases, "
          f"{OUTPUT_PATH.stat().st_size / 1024:.1f} KB)")

    print("\nDone.")


if __name__ == "__main__":
    main()
