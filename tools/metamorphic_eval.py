# Changed: add metamorphic/property-style validation for protocol rule invariants.
# Why: rule coverage alone can miss wrong behavior for unobserved but spec-implied variants.

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Changed: support direct server execution without package installation.
    # Why: diagnostics run from the repository checkout on the course server.
    sys.path.insert(0, str(ROOT))

from src.solver import StatefulOpalVerifier, _column_values, _contains_text, _method_name


Json = dict[str, Any]


@dataclass
class SyntheticCase:
    # Changed: keep synthetic tests self-describing.
    # Why: these cases are rule/property checks, not hidden-label guesses.
    name: str
    expected: str
    source: str
    reason: str
    steps: list[Json]


def case_number(path: Path) -> int:
    return int(path.stem.removeprefix("tc").split("_")[0])


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_public_cases(root: Path) -> dict[str, list[Json]]:
    return {
        path.name: load_json(path)
        for path in sorted((root / "testcases").glob("tc*.json"), key=case_number)
    }


def final_step_with_method(steps: list[Json], method_name: str) -> list[tuple[int, Json]]:
    matches: list[tuple[int, Json]] = []
    for index, step in enumerate(steps):
        command = step.get("input", {}) if isinstance(step, dict) else {}
        if _method_name(command).lower() == method_name.lower():
            matches.append((index, step))
    return matches


def genkey_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    cases: list[SyntheticCase] = []
    for source, steps in public.items():
        for index, _ in final_step_with_method(steps, "GenKey"):
            prefix = copy.deepcopy(steps[: index + 1])
            good = copy.deepcopy(prefix)
            good[-1]["output"] = {"return_values": [], "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:genkey_empty_success:{index}",
                    expected="pass",
                    source=source,
                    reason="GenKey success has empty return_values.",
                    steps=good,
                )
            )
            bad = copy.deepcopy(prefix)
            bad[-1]["output"] = {"return_values": [{"unexpected": "key"}], "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:genkey_nonempty_success:{index}",
                    expected="fail",
                    source=source,
                    reason="GenKey success should not return key material or non-empty payload.",
                    steps=bad,
                )
            )
    return cases


def malformed_challenge_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    cases: list[SyntheticCase] = []
    for source, steps in public.items():
        for index, step in final_step_with_method(steps, "StartSession"):
            command = step.get("input", {})
            if "HostChallenge" not in json.dumps(command):
                continue
            prefix = copy.deepcopy(steps[: index + 1])
            optional = prefix[-1]["input"].setdefault("method", {}).setdefault("args", {}).setdefault("optional", {})
            optional["HostChallenge"] = "a" * 33
            bad_success = copy.deepcopy(prefix)
            bad_success[-1]["output"] = {
                "return_values": {"HostSessionID": "00000001", "SPSessionID": "00000002"},
                "status_codes": "SUCCESS",
            }
            cases.append(
                SyntheticCase(
                    name=f"{source}:malformed_challenge_success:{index}",
                    expected="fail",
                    source=source,
                    reason="Malformed HostChallenge should not produce successful StartSession.",
                    steps=bad_success,
                )
            )
            good_error = copy.deepcopy(prefix)
            good_error[-1]["output"] = {"return_values": {}, "status_codes": "NOT_AUTHORIZED"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:malformed_challenge_not_authorized:{index}",
                    expected="pass",
                    source=source,
                    reason="Malformed HostChallenge can be correctly rejected.",
                    steps=good_error,
                )
            )
    return cases


def data_command_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    cases: list[SyntheticCase] = []
    for source, steps in public.items():
        read_indices = [index for index, step in enumerate(steps) if step.get("input", {}).get("command") == "Read"]
        genkey_indices = [index for index, step in enumerate(steps) if _method_name(step.get("input", {})) == "GenKey"]
        if not read_indices or not genkey_indices:
            continue
        final_read = read_indices[-1]
        if final_read < genkey_indices[-1]:
            continue
        old_pattern = copy.deepcopy(steps[: final_read + 1])
        old_pattern[-1]["output"] = {"command": "Read", "args": {"result": "Pattern 8E"}}
        cases.append(
            SyntheticCase(
                name=f"{source}:read_old_pattern_after_genkey:{final_read}",
                expected="fail",
                source=source,
                reason="After GenKey, old written pattern should not remain visible.",
                steps=old_pattern,
            )
        )
        random_data = copy.deepcopy(steps[: final_read + 1])
        random_data[-1]["output"] = {"command": "Read", "args": {"result": "Random Data"}}
        cases.append(
            SyntheticCase(
                name=f"{source}:read_random_after_genkey:{final_read}",
                expected="pass",
                source=source,
                reason="After GenKey, non-old data is expected for the old LBA pattern.",
                steps=random_data,
            )
        )
    return cases


def latest_cpin_secret(steps: list[Json]) -> str:
    secret = ""
    for step in steps:
        command = step.get("input", {}) if isinstance(step, dict) else {}
        if _method_name(command) != "Set" or not _contains_text(command, "C_PIN"):
            continue
        for column, value in _column_values(command).items():
            if column == "3" and isinstance(value, str) and value.strip():
                secret = value.strip()
    return secret


def pin_auth_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    # Changed: add model-based StartSession authentication mutations.
    # Why: rule coverage alone missed whether Set(C_PIN) state is consumed by later StartSession.
    cases: list[SyntheticCase] = []
    wrong_secret = "f" * 64
    for source, steps in public.items():
        for index, _ in final_step_with_method(steps, "StartSession"):
            secret = latest_cpin_secret(steps[:index])
            if not secret or secret == wrong_secret:
                continue
            prefix = copy.deepcopy(steps[: index + 1])
            optional = prefix[-1]["input"].setdefault("method", {}).setdefault("args", {}).setdefault("optional", {})

            known_success = copy.deepcopy(prefix)
            known_success[-1]["input"]["method"]["args"]["optional"]["HostChallenge"] = secret
            known_success[-1]["output"] = {
                "return_values": {
                    "required": {"HostSessionID": "00000001", "SPSessionID": "00000002"},
                    "optional": {},
                },
                "status_codes": "SUCCESS",
            }
            cases.append(
                SyntheticCase(
                    name=f"{source}:known_pin_success:{index}",
                    expected="pass",
                    source=source,
                    reason="A StartSession using the current C_PIN should be allowed.",
                    steps=known_success,
                )
            )

            known_rejected = copy.deepcopy(known_success)
            known_rejected[-1]["output"] = {"return_values": {}, "status_codes": "NOT_AUTHORIZED"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:known_pin_rejected:{index}",
                    expected="fail",
                    source=source,
                    reason="Rejecting the current C_PIN is inconsistent.",
                    steps=known_rejected,
                )
            )

            wrong_success = copy.deepcopy(prefix)
            wrong_success[-1]["input"]["method"]["args"]["optional"]["HostChallenge"] = wrong_secret
            wrong_success[-1]["output"] = known_success[-1]["output"]
            cases.append(
                SyntheticCase(
                    name=f"{source}:wrong_pin_success:{index}",
                    expected="fail",
                    source=source,
                    reason="A StartSession using a non-current C_PIN should not succeed.",
                    steps=wrong_success,
                )
            )

            wrong_rejected = copy.deepcopy(wrong_success)
            wrong_rejected[-1]["output"] = {"return_values": {}, "status_codes": "NOT_AUTHORIZED"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:wrong_pin_rejected:{index}",
                    expected="pass",
                    source=source,
                    reason="A StartSession using a non-current C_PIN can be correctly rejected.",
                    steps=wrong_rejected,
                )
            )
    return cases


def set_schema_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    # Changed: add schema/property mutations for Set RowValues.
    # Why: guidebook says duplicate RowValues columns are INVALID_PARAMETER and success returns an empty list.
    cases: list[SyntheticCase] = []
    for source, steps in public.items():
        for index, _ in final_step_with_method(steps, "Set"):
            prefix = copy.deepcopy(steps[: index + 1])
            optional = prefix[-1]["input"].setdefault("method", {}).setdefault("args", {}).setdefault("optional", {})
            optional["Values"] = [{"5": 1}, {"5": 0}]

            duplicate_rejected = copy.deepcopy(prefix)
            duplicate_rejected[-1]["output"] = {"return_values": [], "status_codes": "INVALID_PARAMETER"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:set_duplicate_column_rejected:{index}",
                    expected="pass",
                    source=source,
                    reason="Duplicate Set RowValues columns should be INVALID_PARAMETER.",
                    steps=duplicate_rejected,
                )
            )

            duplicate_success = copy.deepcopy(prefix)
            duplicate_success[-1]["output"] = {"return_values": [], "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:set_duplicate_column_success:{index}",
                    expected="fail",
                    source=source,
                    reason="Duplicate Set RowValues columns should not succeed.",
                    steps=duplicate_success,
                )
            )

            nonempty_success = copy.deepcopy(steps[: index + 1])
            nonempty_success[-1]["output"] = {"return_values": [{"unexpected": 1}], "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:set_nonempty_success_payload:{index}",
                    expected="fail",
                    source=source,
                    reason="Successful Set returns an empty list.",
                    steps=nonempty_success,
                )
            )
    return cases


def end_session_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    # Changed: cover EndSession as a possible final method.
    # Why: public traces contain EndSession only as intermediate steps, so final-branch coverage missed it.
    cases: list[SyntheticCase] = []
    for source, steps in public.items():
        for index, step in final_step_with_method(steps, "EndSession"):
            prefix = copy.deepcopy(steps[: index + 1])
            valid_close = copy.deepcopy(prefix)
            valid_close[-1]["output"] = {"return_values": {"required": {}, "optional": {}}, "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:endsession_success:{index}",
                    expected="pass",
                    source=source,
                    reason="EndSession closes an active session and returns an empty result.",
                    steps=valid_close,
                )
            )

            nonempty_close = copy.deepcopy(prefix)
            nonempty_close[-1]["output"] = {"return_values": [{"unexpected": 1}], "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:endsession_nonempty_success:{index}",
                    expected="fail",
                    source=source,
                    reason="Successful EndSession should not return payload data.",
                    steps=nonempty_close,
                )
            )

            no_session_success = copy.deepcopy(step)
            no_session_success["output"] = {"return_values": {}, "status_codes": "SUCCESS"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:endsession_no_session_success:{index}",
                    expected="fail",
                    source=source,
                    reason="EndSession without an active session should not succeed.",
                    steps=[no_session_success],
                )
            )

            no_session_rejected = copy.deepcopy(step)
            no_session_rejected["output"] = {"return_values": {}, "status_codes": "NOT_AUTHORIZED"}
            cases.append(
                SyntheticCase(
                    name=f"{source}:endsession_no_session_rejected:{index}",
                    expected="pass",
                    source=source,
                    reason="EndSession without an active session can be correctly rejected.",
                    steps=[no_session_rejected],
                )
            )
    return cases


def build_synthetic_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    return (
        genkey_cases(public)
        + malformed_challenge_cases(public)
        + data_command_cases(public)
        + pin_auth_cases(public)
        + set_schema_cases(public)
        + end_session_cases(public)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--jsonl-out", type=Path, default=None)
    args = parser.parse_args()

    public = load_public_cases(args.dataset_root)
    synthetic = build_synthetic_cases(public)
    verifier = StatefulOpalVerifier()

    results: list[dict[str, Any]] = []
    correct = 0
    for case in synthetic:
        prediction = verifier.verify(case.steps)
        ok = prediction == case.expected
        correct += int(ok)
        results.append({**asdict(case), "prediction": prediction, "correct": ok})

    if args.jsonl_out is not None:
        args.jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        args.jsonl_out.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in results),
            encoding="utf-8",
        )

    total = len(results)
    score = 100.0 * correct / total if total else 0.0
    print(f"metamorphic_score={score:.2f}")
    print(f"correct={correct}/{total}")
    for item in results:
        if not item["correct"]:
            print(
                f"fail {item['name']}: expected={item['expected']} "
                f"pred={item['prediction']} reason={item['reason']}"
            )


if __name__ == "__main__":
    main()
