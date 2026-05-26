"""Test cases where DEFAULT_PASS should yield 'fail' (error is invalid)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.solver import StatefulOpalVerifier

verifier = StatefulOpalVerifier()

test_cases = [
    # Case A: Auth session Get K_AES_256 → SUCCESS but empty result (suspicious)
    {
        "name": "auth_get_k_aes_empty_success",
        "expected": "fail",  # SUCCESS with empty result for key object is suspicious
        "steps": [
            {"input": {"method": {"name": "StartSession"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"}, "args": {"required": {}, "optional": {"HostSessionID": 1, "SPID": "0000020500000001", "Write": 1, "HostSigningAuthority": "0000000900000001", "HostChallenge": "pin"}}},
             "output": {"return_values": [{"HostSessionID": 1, "SPSessionID": 1001}], "status_codes": "Success"}},
            {"input": {"method": {"name": "Get"}, "invoking_id": {"uid": "00 00 08 06 00 03 00 01", "name": "K_AES_256"}, "args": {"required": {}, "optional": {"startColumn": 0, "endColumn": 3}}},
             "output": {"return_values": [], "status_codes": "Success"}},
        ],
    },
    # Case B: Write then Read same LBA → FAIL (should return written data)
    {
        "name": "write_read_same_lba_fail",
        "expected": "fail",  # After successful Write, Read should not FAIL
        "steps": [
            {"input": {"method": {"name": "StartSession"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"}, "args": {"required": {}, "optional": {"HostSessionID": 1, "SPID": "0000020500000001", "Write": 1, "HostSigningAuthority": "0000000900000001", "HostChallenge": "pin"}}},
             "output": {"return_values": [{"HostSessionID": 1, "SPSessionID": 1001}], "status_codes": "Success"}},
            {"input": {"command": "Write", "args": {"LBA": "80 ~ 87", "pattern": "0xAA"}},
             "output": {"command": "Write", "status_codes": "Success"}},
            {"input": {"command": "Read", "args": {"LBA": "80 ~ 87"}},
             "output": {"command": "Read", "args": {"result": ""}, "status_codes": "FAIL"}},
        ],
    },
    # Case C: Get C_PIN_MSID → NOT_AUTHORIZED (MSID is Anybody-accessible, should succeed)
    {
        "name": "get_cpin_msid_not_authorized",
        "expected": "fail",  # MSID is accessible without auth per Opal spec
        "steps": [
            {"input": {"method": {"name": "StartSession"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"}, "args": {"required": {}, "optional": {"HostSessionID": 1, "SPID": "0000020500000002", "Write": 0}}},
             "output": {"return_values": [{"HostSessionID": 1, "SPSessionID": 1001}], "status_codes": "Success"}},
            {"input": {"method": {"name": "Get"}, "invoking_id": {"uid": "00 00 00 0B 00 84 02 01", "name": "C_PIN_MSID"}, "args": {"required": {}, "optional": {"startColumn": 3, "endColumn": 3}}},
             "output": {"return_values": [], "status_codes": "NOT_AUTHORIZED"}},
        ],
    },
    # Case D: Auth session Set Locking → NOT_AUTHORIZED (auth session should allow Set)
    {
        "name": "auth_set_locking_not_authorized",
        "expected": "fail",  # Authenticated RW session should allow Set on Locking
        "steps": [
            {"input": {"method": {"name": "StartSession"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"}, "args": {"required": {}, "optional": {"HostSessionID": 1, "SPID": "0000020500000001", "Write": 1, "HostSigningAuthority": "0000000900000001", "HostChallenge": "pin"}}},
             "output": {"return_values": [{"HostSessionID": 1, "SPSessionID": 1001}], "status_codes": "Success"}},
            {"input": {"method": {"name": "Set"}, "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "Locking"}, "args": {"required": {}, "optional": {"Values": [{"5": 1, "7": 1}]}}},
             "output": {"return_values": [], "status_codes": "NOT_AUTHORIZED"}},
        ],
    },
]

print(f"Testing {len(test_cases)} potential FAIL DEFAULT_PASS cases\n")
dp_pass = []
dp_fail = []
for case in test_cases:
    result = verifier.verify_with_trace(case["steps"])
    pred = result["prediction"]
    trace = result.get("trace", [])
    rule_id = trace[-1].get("rule_id", "?") if trace else "?"
    detail = trace[-1].get("detail", "")[:80] if trace else ""
    is_dp = rule_id == "DEFAULT_PASS"
    correct = pred == case["expected"]

    if is_dp:
        if case["expected"] == "pass":
            dp_pass.append(case)
        else:
            dp_fail.append(case)

    tag = "DP!" if is_dp else rule_id
    ok = "OK" if correct else "MISMATCH"
    print(f"[{ok}] [{tag}] pred={pred} exp={case['expected']} | {case['name']}")
    print(f"   detail: {detail}")

print(f"\nDEFAULT_PASS(pass): {len(dp_pass)}, DEFAULT_PASS(fail): {len(dp_fail)}")
print(f"Total DEFAULT_PASS: {len(dp_pass)+len(dp_fail)}/{len(test_cases)}")
