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

from src.solver import StatefulOpalVerifier, _method_name


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
            optional["HostChallenge"] = "bad"
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


def build_synthetic_cases(public: dict[str, list[Json]]) -> list[SyntheticCase]:
    return genkey_cases(public) + malformed_challenge_cases(public) + data_command_cases(public)


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
