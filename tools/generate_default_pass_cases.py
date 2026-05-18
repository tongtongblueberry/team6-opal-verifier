# Changed: generate synthetic test cases that trigger DEFAULT_PASS in the rule engine.
# Why: public 20 cases and metamorphic 1891 cases have 0 DEFAULT_PASS.
# To evaluate the RAG/LLM fallback, we need cases where the rule engine can't decide.
# These cases test unmodeled features: Read-Only sessions, Authenticate method, etc.

from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def make_readonly_session_set_case() -> tuple[list[Json], str, str]:
    """Read-Only session (Write=0) followed by Set → should return NOT_AUTHORIZED.

    Spec 5.2.3.1.3: Write=True for Read-Write, Write=False for Read-Only.
    In a Read-Only session, write operations (Set, GenKey) SHALL be rejected.
    Rule engine does not track Write parameter → DEFAULT_PASS.
    """
    steps = [
        {
            "input": {
                "method": {"name": "StartSession"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {
                    "required": {},
                    "optional": {
                        "HostSessionID": 1,
                        "SPID": "0000020500000001",
                        "Write": 0,  # Read-Only session
                    }
                }
            },
            "output": {
                "return_values": {"HostSessionID": 1, "SPSessionID": 12345},
                "status_codes": "Success"
            }
        },
        {
            "input": {
                "method": {"name": "Set"},
                "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "C_PIN"},
                "args": {
                    "required": {},
                    "optional": {
                        "Values": [{"0x03": "new_password_value"}]
                    }
                }
            },
            "output": {
                "return_values": [],
                "status_codes": "NOT_AUTHORIZED"
            }
        }
    ]
    # Expected: pass — NOT_AUTHORIZED is correct for Set in Read-Only session
    return steps, "pass", "ReadOnly session: Set should fail with NOT_AUTHORIZED"


def make_readonly_session_get_case() -> tuple[list[Json], str, str]:
    """Read-Only session (Write=0) followed by Get → should succeed.

    In a Read-Only session, read operations (Get, Properties) SHALL succeed.
    """
    steps = [
        {
            "input": {
                "method": {"name": "StartSession"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {
                    "required": {},
                    "optional": {
                        "HostSessionID": 1,
                        "SPID": "0000020500000001",
                        "Write": 0,
                    }
                }
            },
            "output": {
                "return_values": {"HostSessionID": 1, "SPSessionID": 12345},
                "status_codes": "Success"
            }
        },
        {
            "input": {
                "method": {"name": "Get"},
                "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "C_PIN"},
                "args": {
                    "required": {},
                    "optional": {
                        "startColumn": 0,
                        "endColumn": 3,
                    }
                }
            },
            "output": {
                "return_values": [{"0": "00 00 08 02 00 00 00 01", "3": "some_value"}],
                "status_codes": "NOT_AUTHORIZED"
            }
        }
    ]
    # Expected: could be pass (ACL restriction) or fail (should succeed).
    # In Read-Only session without auth, C_PIN access may require auth → NOT_AUTHORIZED valid.
    return steps, "pass", "ReadOnly session: Get C_PIN without auth, NOT_AUTHORIZED valid"


def make_authenticate_method_case() -> tuple[list[Json], str, str]:
    """Authenticate method (in-session explicit auth) → SUCCESS.

    Spec 3.4.2.1: Explicit Authentication via Authenticate method.
    Rule engine does not model Authenticate → DEFAULT_PASS if error returned.
    """
    steps = [
        {
            "input": {
                "method": {"name": "StartSession"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {
                    "required": {},
                    "optional": {
                        "HostSessionID": 1,
                        "SPID": "0000020500000001",
                        "Write": 1,
                    }
                }
            },
            "output": {
                "return_values": {"HostSessionID": 1, "SPSessionID": 12345},
                "status_codes": "Success"
            }
        },
        {
            "input": {
                "method": {"name": "Authenticate"},
                "invoking_id": {"uid": "00 00 00 09 00 00 00 01", "name": "Authority"},
                "args": {
                    "required": {},
                    "optional": {
                        "Challenge": "password123"
                    }
                }
            },
            "output": {
                "return_values": {"result": True},
                "status_codes": "Success"
            }
        },
        {
            "input": {
                "method": {"name": "Set"},
                "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "C_PIN"},
                "args": {
                    "required": {},
                    "optional": {
                        "Values": [{"0x03": "new_value"}]
                    }
                }
            },
            "output": {
                "return_values": [],
                "status_codes": "NOT_AUTHORIZED"
            }
        }
    ]
    # NOT_AUTHORIZED after Authenticate SUCCESS could mean wrong authority for this object.
    # The rule engine doesn't model Authenticate → DEFAULT_PASS.
    return steps, "pass", "Authenticate then Set: NOT_AUTHORIZED may be valid ACL restriction"


def make_unauthenticated_set_error_case() -> tuple[list[Json], str, str]:
    """StartSession without auth → Set → NOT_AUTHORIZED (expected).

    Session opened without HostSigningAuthority → unauthenticated.
    Set on C_PIN requires auth → NOT_AUTHORIZED is correct.
    Rule engine may or may not catch this depending on PRECONDITION_EXPECTED_ERROR.
    """
    steps = [
        {
            "input": {
                "method": {"name": "StartSession"},
                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager"},
                "args": {
                    "required": {},
                    "optional": {
                        "HostSessionID": 1,
                        "SPID": "0000020500000001",
                        "Write": 1,
                    }
                }
            },
            "output": {
                "return_values": {"HostSessionID": 1, "SPSessionID": 12345},
                "status_codes": "Success"
            }
        },
        {
            "input": {
                "method": {"name": "Set"},
                "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "C_PIN"},
                "args": {
                    "required": {},
                    "optional": {
                        "Values": [{"0x03": "new_password"}]
                    }
                }
            },
            "output": {
                "return_values": [],
                "status_codes": "NOT_AUTHORIZED"
            }
        }
    ]
    return steps, "pass", "Unauth session Set C_PIN: NOT_AUTHORIZED is correct"


def generate_all_default_pass_cases() -> list[dict[str, Any]]:
    """Generate all synthetic DEFAULT_PASS test cases."""
    generators = [
        make_readonly_session_set_case,
        make_readonly_session_get_case,
        make_authenticate_method_case,
        make_unauthenticated_set_error_case,
    ]
    cases = []
    for gen in generators:
        steps, expected, description = gen()
        cases.append({
            "steps": steps,
            "expected": expected,
            "description": description,
            "generator": gen.__name__,
        })
    return cases


def main() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.solver import StatefulOpalVerifier

    cases = generate_all_default_pass_cases()
    verifier = StatefulOpalVerifier()

    print(f"Generated {len(cases)} synthetic DEFAULT_PASS candidates\n")
    default_pass_count = 0
    for case in cases:
        result = verifier.verify_with_trace(case["steps"])
        pred = result["prediction"]
        trace = result.get("trace", [])
        rule_id = trace[-1].get("rule_id", "?") if trace else "?"
        detail = trace[-1].get("detail", "") if trace else ""
        is_default_pass = rule_id == "DEFAULT_PASS"
        if is_default_pass:
            default_pass_count += 1
        status = "DEFAULT_PASS!" if is_default_pass else rule_id
        correct = pred == case["expected"]
        print(f"{case['generator']}: rule={status} pred={pred} expected={case['expected']} {'OK' if correct else 'MISMATCH'}")
        print(f"  {case['description']}")
        if detail:
            print(f"  detail: {detail[:100]}")
        print()

    print(f"\nDEFAULT_PASS triggered: {default_pass_count}/{len(cases)}")


if __name__ == "__main__":
    main()
