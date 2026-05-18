# Changed: implement 3 synthetic test data generation strategies and compare bias.
# Why: public 20 cases = train only. Need separate test data to evaluate RAG/LLM.
#
# Strategy 1 (RAGAS-style): Spec KG → QA pair generation
#   Extract rules from spec → generate trajectory that tests each rule
# Strategy 2 (CRAFT-style): Public seed + spec corpus → LLM augmentation
#   Use public cases as seeds, retrieve spec passages, LLM generates new cases
# Strategy 3 (ChatAFL-style): Protocol grammar → state-based test generation
#   Define state machine, generate valid/invalid sequences deterministically
#
# Each strategy produces cases with known ground truth labels.
# Compare: how many trigger DEFAULT_PASS? What's the LLM accuracy on those?

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Json = dict[str, Any]


# ── Strategy 3: ChatAFL-style deterministic state-based generation ────────────
# No LLM needed. Uses protocol state machine to generate valid/invalid traces.
# This is the least biased strategy because labels come from spec rules directly.

def _base_startsession(write: int = 1, sp: str = "AdminSP", auth: bool = False,
                       challenge: str = "", host_sid: int = 1) -> list[Json]:
    """Create a basic StartSession step."""
    optional: dict[str, Any] = {
        "HostSessionID": host_sid,
        "SPID": "0000020500000001" if sp == "LockingSP" else "0000020500000002",
        "Write": write,
    }
    if auth:
        optional["HostSigningAuthority"] = "0000000900000001"
        if challenge:
            optional["HostChallenge"] = challenge
    return [{
        "input": {
            "method": {"name": "StartSession", "uid": "00 00 00 00 00 00 FF 02"},
            "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
            "args": {"required": {}, "optional": optional},
        },
        "output": {
            "return_values": [{"HostSessionID": host_sid, "SPSessionID": 1000 + host_sid}],
            "status_codes": "Success",
        },
    }]


def _step(method: str, obj_name: str, obj_uid: str, status: str,
          optional: dict | None = None, return_values: Any = None) -> Json:
    return {
        "input": {
            "method": {"name": method, "uid": "00 00 00 06 00 00 00 06"},
            "invoking_id": {"uid": obj_uid, "name": obj_name},
            "args": {"required": {}, "optional": optional or {}},
        },
        "output": {
            "return_values": return_values if return_values is not None else [],
            "status_codes": status,
        },
    }


def strategy3_statebased() -> list[dict[str, Any]]:
    """Generate test cases from protocol state machine.

    Spec rules used:
    - 3.3.7.1: Read-Only sessions cannot make permanent changes
    - 5.2.3.1.3: Write parameter determines session type
    - 3.4.2.1: ACL controls method access based on authenticated authorities
    - Session required for Get/Set/Activate/GenKey
    """
    cases: list[dict[str, Any]] = []

    # Case 1: Read-Only session (Write=0) + Set → NOT_AUTHORIZED (valid error)
    # Spec 3.3.7.1: "explicit changes during Read-Only session SHALL NOT be made permanent"
    steps = _base_startsession(write=0) + [
        _step("Set", "C_PIN", "00 00 08 02 00 00 00 01", "NOT_AUTHORIZED",
              optional={"Values": [{"0x03": "newpin"}]}),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "ReadOnly+Set→NOT_AUTHORIZED (spec 3.3.7.1: valid error)",
                  "spec_rule": "Read-Only session cannot write"})

    # Case 2: Read-Only session + Set → SUCCESS (invalid — should have been rejected)
    steps = _base_startsession(write=0) + [
        _step("Set", "C_PIN", "00 00 08 02 00 00 00 01", "Success",
              optional={"Values": [{"0x03": "newpin"}]}),
    ]
    cases.append({"steps": steps, "expected": "fail", "strategy": "S3",
                  "description": "ReadOnly+Set→SUCCESS (spec violation: should be rejected)",
                  "spec_rule": "Read-Only session cannot write"})

    # Case 3: Read-Only session + Get → SUCCESS (valid)
    steps = _base_startsession(write=0) + [
        _step("Get", "C_PIN_MSID", "00 00 08 02 00 03 00 01", "Success",
              optional={"startColumn": 0, "endColumn": 3},
              return_values=[{"0": "uid", "3": "default_pin"}]),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "ReadOnly+Get→SUCCESS (reads allowed in ReadOnly)",
                  "spec_rule": "Read-Only session allows reads"})

    # Case 4: No session + Get → NOT_AUTHORIZED/FAIL (valid error)
    steps = [
        _step("Get", "Locking", "00 00 08 02 00 00 00 01", "NOT_AUTHORIZED",
              optional={"startColumn": 0, "endColumn": 5}),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "NoSession+Get→NOT_AUTHORIZED (valid: need session)",
                  "spec_rule": "Session required for method invocation"})

    # Case 5: Authenticated session + Set C_PIN → SUCCESS (valid)
    steps = _base_startsession(write=1, auth=True, challenge="correct_pin") + [
        _step("Set", "C_PIN", "00 00 08 02 00 00 00 01", "Success",
              optional={"Values": [{"0x03": "new_pin_value"}]}),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "Auth+Set(C_PIN)→SUCCESS (valid: authenticated with write)",
                  "spec_rule": "Authenticated RW session allows writes"})

    # Case 6: Unauthenticated session + Set C_PIN → NOT_AUTHORIZED (valid error)
    steps = _base_startsession(write=1, auth=False) + [
        _step("Set", "C_PIN", "00 00 08 02 00 00 00 01", "NOT_AUTHORIZED",
              optional={"Values": [{"0x03": "new_pin_value"}]}),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "Unauth+Set(C_PIN)→NOT_AUTHORIZED (valid: need auth)",
                  "spec_rule": "C_PIN write requires authentication"})

    # Case 7: Unauthenticated + Set C_PIN → SUCCESS (invalid — should fail)
    steps = _base_startsession(write=1, auth=False) + [
        _step("Set", "C_PIN", "00 00 08 02 00 00 00 01", "Success",
              optional={"Values": [{"0x03": "new_pin_value"}]}),
    ]
    cases.append({"steps": steps, "expected": "fail", "strategy": "S3",
                  "description": "Unauth+Set(C_PIN)→SUCCESS (violation: should need auth)",
                  "spec_rule": "C_PIN write requires authentication"})

    # Case 8: Session + Activate LockingSP → SUCCESS + Get Locking → NOT_AUTHORIZED
    # After Activate, need new session to access Locking SP objects
    steps = _base_startsession(write=1, auth=True, challenge="pin") + [
        _step("Activate", "LockingSP", "00 00 02 05 00 00 00 01", "Success"),
        _step("EndSession", "", "00 00 00 00 00 00 00 00", "Success"),
        _step("Get", "Locking", "00 00 08 02 00 00 00 01", "NOT_AUTHORIZED",
              optional={"startColumn": 3, "endColumn": 8}),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "Activate+EndSession+Get(no session)→NOT_AUTHORIZED (valid)",
                  "spec_rule": "Need session after EndSession"})

    # Case 9: GenKey without authentication → NOT_AUTHORIZED (valid)
    steps = _base_startsession(write=1, auth=False) + [
        _step("GenKey", "K_AES_256", "00 00 08 06 00 03 00 01", "NOT_AUTHORIZED"),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "Unauth+GenKey→NOT_AUTHORIZED (valid: need auth for GenKey)",
                  "spec_rule": "GenKey requires authentication"})

    # Case 10: Multiple sessions — second StartSession on same SP
    steps = _base_startsession(write=1, host_sid=1) + [
        {
            "input": {
                "method": {"name": "StartSession", "uid": "00 00 00 00 00 00 FF 02"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {"required": {}, "optional": {
                    "HostSessionID": 2, "SPID": "0000020500000002", "Write": 1,
                }},
            },
            "output": {"return_values": [], "status_codes": "FAIL"},
        },
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S3",
                  "description": "Second RW StartSession→FAIL (valid: only one RW at a time)",
                  "spec_rule": "Only one RW session per SP (3.3.7.1)"})

    return cases


# ── Strategy 1: RAGAS-style spec rule extraction ─────────────────────────────
# Extract rules from spec text → generate trajectory testing each rule.
# Uses spec text directly for ground truth, no LLM needed for labeling.

def strategy1_spec_rules() -> list[dict[str, Any]]:
    """Generate cases from extracted spec rules.

    Rules extracted manually from spec sections read on server.
    Each case tests one specific spec rule with known ground truth.
    """
    cases: list[dict[str, Any]] = []

    # Rule: Properties SHALL return supported capabilities (5.2.2.2)
    cases.append({
        "steps": [{
            "input": {
                "method": {"name": "Properties", "uid": "00 00 00 00 00 00 FF 01"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {"required": {}, "optional": {}},
            },
            "output": {
                "return_values": {"MaxMethods": 1, "MaxSubpackets": 1, "MaxPacketSize": 2028},
                "status_codes": "Success",
            },
        }],
        "expected": "pass", "strategy": "S1",
        "description": "Properties returns valid capabilities (5.2.2.2)",
        "spec_rule": "Properties SHALL return supported capability pairs",
    })

    # Rule: Properties with missing mandatory properties → still valid
    cases.append({
        "steps": [{
            "input": {
                "method": {"name": "Properties", "uid": "00 00 00 00 00 00 FF 01"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {"required": {}, "optional": {}},
            },
            "output": {
                "return_values": {},
                "status_codes": "Success",
            },
        }],
        "expected": "fail", "strategy": "S1",
        "description": "Properties returns empty → fail (should return at least some properties)",
        "spec_rule": "Properties SHALL return all supported property pairs",
    })

    # Rule: StartSession Write parameter (5.2.3.1.3)
    steps = _base_startsession(write=0) + [
        _step("GenKey", "K_AES_256", "00 00 08 06 00 03 00 01", "NOT_AUTHORIZED"),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S1",
                  "description": "ReadOnly+GenKey→NOT_AUTHORIZED (5.2.3.1.3: Write=0 forbids writes)",
                  "spec_rule": "Write=False means Read-Only session"})

    # Rule: Mutually exclusive sessions (3.3.7.1)
    # "Read-Only and Read-Write sessions are mutually exclusive"
    steps = _base_startsession(write=1, host_sid=1) + [
        {
            "input": {
                "method": {"name": "StartSession", "uid": "00 00 00 00 00 00 FF 02"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {"required": {}, "optional": {
                    "HostSessionID": 2, "SPID": "0000020500000002", "Write": 0,
                }},
            },
            "output": {"return_values": [], "status_codes": "FAIL"},
        },
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S1",
                  "description": "RW+RO StartSession→FAIL (3.3.7.1: mutually exclusive)",
                  "spec_rule": "RO and RW sessions are mutually exclusive"})

    # Rule: EndSession successful close (5.2.3.3)
    steps = _base_startsession(write=1) + [
        _step("EndSession", "", "00 00 00 00 00 00 00 00", "Success"),
    ]
    cases.append({"steps": steps, "expected": "pass", "strategy": "S1",
                  "description": "StartSession+EndSession→SUCCESS (normal close)",
                  "spec_rule": "Session ended by host"})

    return cases


# ── Strategy 2: CRAFT-style seed augmentation ─────────────────────────────────
# Uses public cases as seeds. Modifies status/parameters to create new cases.
# No LLM needed — deterministic mutations with spec-based labels.

def strategy2_seed_augmentation(dataset_root: Path) -> list[dict[str, Any]]:
    """Augment public cases by mutating final response status.

    For each public case:
    - If gold=pass: flip status to error → new label depends on state
    - If gold=fail: flip status to success → new label depends on state
    """
    cases: list[dict[str, Any]] = []
    testcase_dir = dataset_root / "testcases"
    label_path = dataset_root / "label.jsonl"

    if not testcase_dir.exists() or not label_path.exists():
        return cases

    labels: dict[str, str] = {}
    with label_path.open() as f:
        for line in f:
            rec = json.loads(line.strip())
            labels[rec["filename"]] = rec["label"].strip().lower()

    for path in sorted(testcase_dir.glob("tc*.json")):
        if path.name not in labels:
            continue
        with path.open() as f:
            steps = json.load(f)
        gold = labels[path.name]
        if not steps:
            continue

        # Deep copy and mutate the final step's status
        mutated = copy.deepcopy(steps)
        final_out = mutated[-1].get("output", {})
        current_status = str(final_out.get("status_codes", "")).lower()

        if "success" in current_status:
            # Flip success → NOT_AUTHORIZED
            final_out["status_codes"] = "NOT_AUTHORIZED"
            # If original was pass (success was correct), then NOT_AUTHORIZED is wrong → fail
            # If original was fail (success was wrong), then NOT_AUTHORIZED might be correct → pass
            new_expected = "fail" if gold == "pass" else "pass"
        else:
            # Flip error → Success
            final_out["status_codes"] = "Success"
            # If original was pass (error was correct), then Success is wrong → fail
            # If original was fail (error was wrong), then Success might be correct → pass
            new_expected = "fail" if gold == "pass" else "pass"

        cases.append({
            "steps": mutated,
            "expected": new_expected,
            "strategy": "S2",
            "description": f"Mutated {path.name} (gold={gold}): status flipped",
            "spec_rule": f"Status flip from {path.name}",
            "source": path.name,
        })

    return cases


# ── Main: run all strategies, test with rule engine, report DEFAULT_PASS ──────

def main() -> None:
    from src.solver import StatefulOpalVerifier

    dataset_root = Path("/dl2026/dataset")

    print("=== Strategy 1: RAGAS-style spec rules ===")
    s1 = strategy1_spec_rules()
    print(f"Generated: {len(s1)} cases")

    print("\n=== Strategy 2: CRAFT-style seed augmentation ===")
    s2 = strategy2_seed_augmentation(dataset_root)
    print(f"Generated: {len(s2)} cases")

    print("\n=== Strategy 3: ChatAFL-style state-based ===")
    s3 = strategy3_statebased()
    print(f"Generated: {len(s3)} cases")

    all_cases = s1 + s2 + s3
    print(f"\nTotal: {len(all_cases)} cases")

    verifier = StatefulOpalVerifier()
    results_by_strategy: dict[str, list] = {"S1": [], "S2": [], "S3": []}

    for case in all_cases:
        result = verifier.verify_with_trace(case["steps"])
        pred = result["prediction"]
        trace = result.get("trace", [])
        rule_id = trace[-1].get("rule_id", "?") if trace else "?"
        detail = trace[-1].get("detail", "")[:60] if trace else ""
        expected = case["expected"]
        correct = pred == expected
        is_dp = rule_id == "DEFAULT_PASS"
        results_by_strategy[case["strategy"]].append({
            "description": case["description"],
            "expected": expected,
            "pred": pred,
            "correct": correct,
            "rule_id": rule_id,
            "detail": detail,
            "is_default_pass": is_dp,
        })

    # Report per strategy
    for strat, results in results_by_strategy.items():
        n = len(results)
        if n == 0:
            continue
        correct = sum(1 for r in results if r["correct"])
        dp_count = sum(1 for r in results if r["is_default_pass"])
        print(f"\n{'='*60}")
        print(f"Strategy {strat}: {n} cases, rule_engine_accuracy={100*correct/n:.1f}%, DEFAULT_PASS={dp_count}")
        for r in results:
            tag = "DP!" if r["is_default_pass"] else "   "
            ok = "OK" if r["correct"] else "WRONG"
            print(f"  {tag} [{ok}] pred={r['pred']} exp={r['expected']} rule={r['rule_id']} | {r['description'][:70]}")

    # Summary
    all_results = [r for rs in results_by_strategy.values() for r in rs]
    total_dp = sum(1 for r in all_results if r["is_default_pass"])
    total_correct = sum(1 for r in all_results if r["correct"])
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(all_results)} cases, accuracy={100*total_correct/len(all_results):.1f}%, DEFAULT_PASS={total_dp}")

    # Save for LLM evaluation
    dp_cases = [case for case, r in zip(all_cases, all_results) if r["is_default_pass"]]
    if dp_cases:
        out_path = Path("/workspace/team6/default_pass_test_cases.json")
        out_path.write_text(json.dumps(dp_cases, indent=2, default=str), encoding="utf-8")
        print(f"\nDEFAULT_PASS cases saved to {out_path} ({len(dp_cases)} cases)")


if __name__ == "__main__":
    main()
