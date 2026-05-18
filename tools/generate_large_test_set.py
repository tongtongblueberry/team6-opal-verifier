# Changed: generate large-scale DEFAULT_PASS test set (100+ cases).
# Why: 8 cases is statistically meaningless. Need 50-100+ for valid evaluation.
# Strategy: combinatorial generation across all identified DEFAULT_PASS gaps.
#
# Train/Test split:
# - TRAIN: public 20 cases (rule engine development)
# - TEST: these synthetic DEFAULT_PASS cases (LLM evaluation ONLY)

from __future__ import annotations
import json, sys, itertools
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Json = dict[str, Any]

# ── TCG/Opal objects that the rule engine does NOT model ──
# _object_kind() only returns non-empty for: cpin, authority, locking, mbrcontrol
# All other objects → DEFAULT_PASS when error status received

UNKNOWN_OBJECTS = [
    ("K_AES_256", "00 00 08 06 00 03 00 01"),
    ("K_AES_128", "00 00 08 06 00 02 00 01"),
    ("SP", "00 00 02 05 00 00 00 01"),
    ("SPInfo", "00 00 02 05 00 00 00 02"),
    ("DataStore", "00 00 10 01 00 00 00 00"),
    ("Table", "00 00 00 01 00 00 00 01"),
    ("ACE", "00 00 00 08 00 00 00 01"),
    ("ACE_Locking_GR", "00 00 00 08 00 03 E0 01"),
    ("Template", "00 00 00 02 00 00 00 01"),
    ("MethodID", "00 00 00 06 00 00 00 01"),
    ("SecretProtect", "00 00 00 04 00 00 00 01"),
    ("Log", "00 00 0F 01 00 00 00 01"),
    ("LogList", "00 00 0F 02 00 00 00 01"),
]

# Non-MSID C_PIN UIDs (triggers DEFAULT_PASS path for C_PIN without auth)
NON_MSID_CPINS = [
    ("C_PIN_SID", "00 00 00 0B 00 00 00 01"),
    ("C_PIN_Admin1", "00 00 00 0B 00 01 00 01"),
    ("C_PIN_Admin2", "00 00 00 0B 00 01 00 02"),
    ("C_PIN_Admin3", "00 00 00 0B 00 01 00 03"),
    ("C_PIN_Admin4", "00 00 00 0B 00 01 00 04"),
    ("C_PIN_User1", "00 00 00 0B 00 03 00 01"),
    ("C_PIN_User2", "00 00 00 0B 00 03 00 02"),
    ("C_PIN_User3", "00 00 00 0B 00 03 00 03"),
    ("C_PIN_User4", "00 00 00 0B 00 03 00 04"),
]

ERROR_STATUSES = ["NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL"]

SESSION_STATES = [
    {"label": "unauth_rw", "write": 1, "auth": False},
    {"label": "auth_rw", "write": 1, "auth": True},
    {"label": "unauth_ro", "write": 0, "auth": False},
]


def _startsession(state: dict) -> Json:
    optional: dict[str, Any] = {
        "HostSessionID": 1,
        "SPID": "0000020500000001",
        "Write": state["write"],
    }
    if state["auth"]:
        optional["HostSigningAuthority"] = "0000000900000001"
        optional["HostChallenge"] = "password"
    return {
        "input": {
            "method": {"name": "StartSession"},
            "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
            "args": {"required": {}, "optional": optional},
        },
        "output": {
            "return_values": [{"HostSessionID": 1, "SPSessionID": 1001}],
            "status_codes": "Success",
        },
    }


def _method_step(method: str, obj_name: str, obj_uid: str, status: str,
                 columns: str = "", values: dict | None = None) -> Json:
    optional: dict[str, Any] = {}
    rv: Any = []
    if method == "Get":
        if columns:
            parts = columns.split("-")
            optional["startColumn"] = int(parts[0])
            optional["endColumn"] = int(parts[-1])
        if status == "Success":
            rv = [{"0": "uid_val"}]
    elif method == "Set":
        optional["Values"] = [values or {"0x03": "new_value"}]
    return {
        "input": {
            "method": {"name": method},
            "invoking_id": {"uid": obj_uid, "name": obj_name},
            "args": {"required": {}, "optional": optional},
        },
        "output": {
            "return_values": rv,
            "status_codes": status,
        },
    }


def generate_gap1_unknown_objects() -> list[dict[str, Any]]:
    """Gap 1: Unknown object type × methods × error statuses × session states."""
    cases = []
    for (obj_name, obj_uid), status, state in itertools.product(
        UNKNOWN_OBJECTS, ERROR_STATUSES, SESSION_STATES
    ):
        for method in ["Get", "Set"]:
            steps = [_startsession(state), _method_step(method, obj_name, obj_uid, status, columns="0-3")]
            # Most errors on unknown objects are valid (access control, unsupported)
            expected = "pass"
            cases.append({
                "steps": steps,
                "expected": expected,
                "description": f"{state['label']}+{method}({obj_name})→{status}",
                "gap": "unknown_object",
            })
    return cases


def generate_gap2_non_msid_cpin() -> list[dict[str, Any]]:
    """Gap 2: Non-MSID C_PIN without auth (known relaxation in rule engine)."""
    cases = []
    for (cpin_name, cpin_uid), status in itertools.product(NON_MSID_CPINS, ERROR_STATUSES):
        # Unauthenticated session + access non-MSID C_PIN
        steps = [_startsession({"label": "unauth_rw", "write": 1, "auth": False}),
                 _method_step("Get", cpin_name, cpin_uid, status, columns="0-3")]
        expected = "pass"  # Error is valid (needs auth for non-MSID)
        cases.append({
            "steps": steps,
            "expected": expected,
            "description": f"unauth+Get({cpin_name})→{status}",
            "gap": "non_msid_cpin",
        })
    return cases


def generate_gap3_data_commands() -> list[dict[str, Any]]:
    """Gap 3: Data command (media) failures."""
    cases = []
    lba_ranges = ["0 ~ 7", "80 ~ 87", "100 ~ 107", "200 ~ 207", "1000 ~ 1007"]

    for lba in lba_ranges:
        for status in ["FAIL", "NOT_AUTHORIZED"]:
            # Read with error
            steps = [
                _startsession({"label": "auth_rw", "write": 1, "auth": True}),
                {"input": {"command": "Read", "args": {"LBA": lba}},
                 "output": {"command": "Read", "args": {"result": ""}, "status_codes": status}},
            ]
            cases.append({
                "steps": steps,
                "expected": "pass",  # Error on read is valid (locked range, etc)
                "description": f"auth+Read(LBA={lba})→{status}",
                "gap": "data_command",
            })

            # Write with error
            steps = [
                _startsession({"label": "auth_rw", "write": 1, "auth": True}),
                {"input": {"command": "Write", "args": {"LBA": lba, "pattern": "0xBB"}},
                 "output": {"command": "Write", "status_codes": status}},
            ]
            cases.append({
                "steps": steps,
                "expected": "pass",
                "description": f"auth+Write(LBA={lba})→{status}",
                "gap": "data_command",
            })

    # FAIL cases: Write succeeded but Read fails (contradiction)
    for lba in lba_ranges[:3]:
        steps = [
            _startsession({"label": "auth_rw", "write": 1, "auth": True}),
            {"input": {"command": "Write", "args": {"LBA": lba, "pattern": "0xCC"}},
             "output": {"command": "Write", "status_codes": "Success"}},
            {"input": {"command": "Read", "args": {"LBA": lba}},
             "output": {"command": "Read", "args": {"result": ""}, "status_codes": "FAIL"}},
        ]
        cases.append({
            "steps": steps,
            "expected": "fail",  # Write succeeded, Read should not FAIL
            "description": f"Write+Read(LBA={lba})→FAIL (contradiction)",
            "gap": "data_command_contradiction",
        })

    return cases


def main() -> None:
    from src.solver import StatefulOpalVerifier

    g1 = generate_gap1_unknown_objects()
    g2 = generate_gap2_non_msid_cpin()
    g3 = generate_gap3_data_commands()
    all_cases = g1 + g2 + g3

    print(f"Generated: gap1={len(g1)} gap2={len(g2)} gap3={len(g3)} total={len(all_cases)}")

    verifier = StatefulOpalVerifier()
    dp_cases = []
    non_dp = 0

    for case in all_cases:
        result = verifier.verify_with_trace(case["steps"])
        pred = result["prediction"]
        trace = result.get("trace", [])
        rule_id = trace[-1].get("rule_id", "?") if trace else "?"
        if rule_id == "DEFAULT_PASS":
            dp_cases.append(case)
        else:
            non_dp += 1

    print(f"DEFAULT_PASS: {len(dp_cases)}, other: {non_dp}")
    print(f"Expected labels: pass={sum(1 for c in dp_cases if c['expected']=='pass')}, "
          f"fail={sum(1 for c in dp_cases if c['expected']=='fail')}")

    # Save test set
    out = Path("/workspace/team6/large_dp_test_set.json")
    out.write_text(json.dumps(dp_cases, indent=2, default=str), encoding="utf-8")
    print(f"\nTEST SET: {out} ({len(dp_cases)} cases)")

    # Gap distribution
    gap_counts: dict[str, int] = {}
    for c in dp_cases:
        gap_counts[c["gap"]] = gap_counts.get(c["gap"], 0) + 1
    print("\nGap distribution:")
    for gap, count in sorted(gap_counts.items(), key=lambda x: -x[1]):
        print(f"  {gap}: {count}")


if __name__ == "__main__":
    main()
