# Changed: generate test cases that ACTUALLY trigger DEFAULT_PASS based on code analysis.
# Why: previous generators failed to trigger DEFAULT_PASS (0/35 cases).
# Agent analysis of solver.py identified specific gaps:
# 1. Unknown object type (not cpin/authority/locking/mbrcontrol)
# 2. Non-MSID C_PIN in unauthenticated session
# 3. Data command (media) failures
# 4. GenKey/Activate with parameters the solver can't validate
#
# Train/Test split:
# - TRAIN: public 20 cases (for rule engine development)
# - TEST: these synthetic DEFAULT_PASS cases (for LLM evaluation)
# - NEVER use test cases to tune the rule engine or LLM

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Json = dict[str, Any]


def _startsession(write: int = 1, auth: bool = False, challenge: str = "",
                  sp_uid: str = "0000020500000002", host_sid: int = 1) -> Json:
    optional: dict[str, Any] = {"HostSessionID": host_sid, "SPID": sp_uid, "Write": write}
    if auth:
        optional["HostSigningAuthority"] = "0000000900000001"
        if challenge:
            optional["HostChallenge"] = challenge
    return {
        "input": {
            "method": {"name": "StartSession", "uid": "00 00 00 00 00 00 FF 02"},
            "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
            "args": {"required": {}, "optional": optional},
        },
        "output": {
            "return_values": [{"HostSessionID": host_sid, "SPSessionID": 1000 + host_sid}],
            "status_codes": "Success",
        },
    }


def _step(method: str, obj_name: str, obj_uid: str, status: str,
          optional: dict | None = None, return_values: Any = None) -> Json:
    return {
        "input": {
            "method": {"name": method},
            "invoking_id": {"uid": obj_uid, "name": obj_name},
            "args": {"required": {}, "optional": optional or {}},
        },
        "output": {
            "return_values": return_values if return_values is not None else [],
            "status_codes": status,
        },
    }


def generate_default_pass_cases() -> list[dict[str, Any]]:
    """Generate cases targeting the 6 DEFAULT_PASS scenarios from code analysis."""
    cases: list[dict[str, Any]] = []

    # ── Gap 1: Unknown object type ──────────────────────────────────────
    # _object_kind() returns "" for objects not in {cpin, authority, locking, mbrcontrol}
    # Examples: K_AES_256, SP, Table, ACE, DataStore

    # 1a. Get on K_AES_256 → NOT_AUTHORIZED (valid: need auth for key object)
    cases.append({
        "steps": [_startsession(write=1, auth=False)] + [
            _step("Get", "K_AES_256", "00 00 08 06 00 03 00 01", "NOT_AUTHORIZED",
                  optional={"startColumn": 0, "endColumn": 3}),
        ],
        "expected": "pass",
        "description": "Get K_AES_256 without auth → NOT_AUTHORIZED (valid: key needs auth)",
        "gap": "unknown_object_type",
    })

    # 1b. Get on K_AES_256 → SUCCESS (might be valid if authorized)
    cases.append({
        "steps": [_startsession(write=1, auth=True, challenge="pin")] + [
            _step("Get", "K_AES_256", "00 00 08 06 00 03 00 01", "NOT_AUTHORIZED",
                  optional={"startColumn": 0, "endColumn": 3}),
        ],
        "expected": "pass",
        "description": "Get K_AES_256 with auth → NOT_AUTHORIZED (valid: might need specific authority)",
        "gap": "unknown_object_type",
    })

    # 1c. Set on DataStore table → NOT_AUTHORIZED
    cases.append({
        "steps": [_startsession(write=1, auth=False)] + [
            _step("Set", "DataStore", "00 00 10 01 00 00 00 00", "NOT_AUTHORIZED",
                  optional={"Values": [{"0": "data"}]}),
        ],
        "expected": "pass",
        "description": "Set DataStore without auth → NOT_AUTHORIZED (valid)",
        "gap": "unknown_object_type",
    })

    # 1d. Get on SP table → FAIL
    cases.append({
        "steps": [_startsession(write=1, auth=True, challenge="pin")] + [
            _step("Get", "SP", "00 00 02 05 00 00 00 01", "FAIL",
                  optional={"startColumn": 0, "endColumn": 5}),
        ],
        "expected": "pass",
        "description": "Get SP table → FAIL (valid: SP table may not support Get)",
        "gap": "unknown_object_type",
    })

    # ── Gap 2: Non-MSID C_PIN without auth ──────────────────────────────
    # C_PIN access where UID is not MSID (8402) and session is unauthenticated

    # 2a. Get C_PIN (SID, UID 0B000001) without auth → NOT_AUTHORIZED (valid)
    cases.append({
        "steps": [_startsession(write=1, auth=False)] + [
            _step("Get", "C_PIN_SID", "00 00 00 0B 00 00 00 01", "NOT_AUTHORIZED",
                  optional={"startColumn": 0, "endColumn": 3}),
        ],
        "expected": "pass",
        "description": "Get C_PIN_SID without auth → NOT_AUTHORIZED (valid: non-MSID needs auth)",
        "gap": "non_msid_cpin_no_auth",
    })

    # 2b. Get C_PIN (Admin1, UID 0B000101) without auth → NOT_AUTHORIZED (valid)
    cases.append({
        "steps": [_startsession(write=1, auth=False)] + [
            _step("Get", "C_PIN_Admin1", "00 00 00 0B 00 01 00 01", "NOT_AUTHORIZED",
                  optional={"startColumn": 3, "endColumn": 3}),
        ],
        "expected": "pass",
        "description": "Get C_PIN_Admin1 without auth → NOT_AUTHORIZED (valid)",
        "gap": "non_msid_cpin_no_auth",
    })

    # 2c. Set C_PIN_Admin1 without auth → NOT_AUTHORIZED (valid)
    cases.append({
        "steps": [_startsession(write=1, auth=False)] + [
            _step("Set", "C_PIN_Admin1", "00 00 00 0B 00 01 00 01", "NOT_AUTHORIZED",
                  optional={"Values": [{"0x03": "new_pin"}]}),
        ],
        "expected": "pass",
        "description": "Set C_PIN_Admin1 without auth → NOT_AUTHORIZED (valid)",
        "gap": "non_msid_cpin_no_auth",
    })

    # ── Gap 3: Data command failures ────────────────────────────────────
    # Media Read/Write errors that the solver can't explain

    # 3a. Read from locked range after session ended → FAIL
    cases.append({
        "steps": [
            _startsession(write=1, auth=True, challenge="pin"),
            _step("EndSession", "", "00 00 00 00 00 00 00 00", "Success"),
            {"input": {"command": "Read", "args": {"LBA": "100 ~ 107"}},
             "output": {"command": "Read", "args": {"result": ""}, "status_codes": "FAIL"}},
        ],
        "expected": "pass",
        "description": "Read after EndSession → FAIL (valid: no session context for locked range)",
        "gap": "data_command_failure",
    })

    # 3b. Write to range with wrong pattern → FAIL
    cases.append({
        "steps": [
            _startsession(write=1, auth=True, challenge="pin"),
            {"input": {"command": "Write", "args": {"LBA": "200 ~ 207", "pattern": "0xFF"}},
             "output": {"command": "Write", "status_codes": "FAIL"}},
        ],
        "expected": "pass",
        "description": "Write with pattern → FAIL (valid: range may be locked)",
        "gap": "data_command_failure",
    })

    # ── Gap 4: GenKey with unmodeled parameters ─────────────────────────

    # 4a. GenKey on unknown key object → INVALID_PARAMETER
    cases.append({
        "steps": [_startsession(write=1, auth=True, challenge="pin")] + [
            _step("GenKey", "UnknownKey", "00 00 08 06 00 FF 00 01", "INVALID_PARAMETER"),
        ],
        "expected": "pass",
        "description": "GenKey on unknown key UID → INVALID_PARAMETER (valid: UID not recognized)",
        "gap": "genkey_unknown_params",
    })

    # ── Gap 5: Activate with unexpected error ───────────────────────────

    # 5a. Activate on already-active SP → FAIL
    cases.append({
        "steps": [_startsession(write=1, auth=True, challenge="pin")] + [
            _step("Activate", "LockingSP", "00 00 02 05 00 00 00 01", "FAIL"),
        ],
        "expected": "pass",
        "description": "Activate already-active SP → FAIL (valid: SP already activated)",
        "gap": "activate_unexpected_error",
    })

    return cases


def main() -> None:
    from src.solver import StatefulOpalVerifier

    cases = generate_default_pass_cases()
    verifier = StatefulOpalVerifier()

    print(f"Generated {len(cases)} cases targeting DEFAULT_PASS gaps\n")

    dp_cases = []
    non_dp_cases = []

    for case in cases:
        result = verifier.verify_with_trace(case["steps"])
        pred = result["prediction"]
        trace = result.get("trace", [])
        rule_id = trace[-1].get("rule_id", "?") if trace else "?"
        detail = trace[-1].get("detail", "")[:60] if trace else ""
        is_dp = rule_id == "DEFAULT_PASS"
        correct = pred == case["expected"]

        if is_dp:
            dp_cases.append(case)

        tag = "DEFAULT_PASS" if is_dp else rule_id
        ok = "OK" if correct else "MISMATCH"
        print(f"[{ok}] [{tag}] pred={pred} exp={case['expected']} gap={case['gap']}")
        print(f"   {case['description']}")
        if detail:
            print(f"   detail: {detail}")
        print()

    print(f"\n{'='*60}")
    print(f"DEFAULT_PASS triggered: {len(dp_cases)}/{len(cases)}")
    print(f"Non-DEFAULT_PASS: {len(cases) - len(dp_cases)}/{len(cases)}")

    if dp_cases:
        out_path = Path("/workspace/team6/default_pass_test_set.json")
        out_path.write_text(json.dumps(dp_cases, indent=2, default=str), encoding="utf-8")
        print(f"\nTEST SET saved: {out_path} ({len(dp_cases)} cases)")
        print("These cases are for LLM evaluation ONLY. Do NOT use them to tune the rule engine.")


if __name__ == "__main__":
    main()
