# Changed: add mutation testing framework for solver rule adequacy evaluation.
# Why: mutation score measures whether our test suite can detect rule removal/weakening,
# revealing which rules are untested (potentially over-aggressive) or essential.

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.eval.metamorphic_eval import SyntheticCase, build_synthetic_cases, load_public_cases

Json = dict[str, Any]


@dataclass
class MutantResult:
    mutant_id: str
    description: str
    operator: str
    killed_by_public: bool
    killed_by_synthetic: bool
    public_diff: int  # number of public predictions that changed
    synthetic_diff: int  # number of synthetic predictions that changed


# ---------------------------------------------------------------------------
# Mutation operators: each returns a modified StatefulOpalVerifier class
# ---------------------------------------------------------------------------

def _make_verifier_class():
    """Import fresh to avoid circular issues."""
    from src.solver import StatefulOpalVerifier
    return StatefulOpalVerifier


def _original_predictions(public_cases, synthetic_cases):
    """Run original solver and return predictions."""
    from src.solver import StatefulOpalVerifier
    v = StatefulOpalVerifier()
    public_preds = {}
    for name, steps in public_cases.items():
        public_preds[name] = v.verify(steps)
    synthetic_preds = {}
    for case in synthetic_cases:
        synthetic_preds[case.name] = v.verify(case.steps)
    return public_preds, synthetic_preds


def _mutant_predictions(mutant_verify_fn, public_cases, synthetic_cases):
    """Run mutant solver and return predictions."""
    public_preds = {}
    for name, steps in public_cases.items():
        public_preds[name] = mutant_verify_fn(steps)
    synthetic_preds = {}
    for case in synthetic_cases:
        synthetic_preds[case.name] = mutant_verify_fn(case.steps)
    return public_preds, synthetic_preds


# ---------------------------------------------------------------------------
# Individual mutants
# ---------------------------------------------------------------------------

def mutant_no_startsession_final():
    """Remove StartSession response-shape validation."""
    from src.solver import StatefulOpalVerifier, _compact, _method_name, _status_name
    class Mutant(StatefulOpalVerifier):
        def _start_session_inconsistent(self, state, command, output, status):
            return False  # never flag StartSession as inconsistent
    v = Mutant()
    return "NO_STARTSESSION_FINAL", "Remove StartSession response validation", "rule_deletion", v.verify


def mutant_no_known_field_expected_success():
    """Remove KNOWN_FIELD_EXPECTED_SUCCESS rule."""
    from src.solver import (
        StatefulOpalVerifier, ProtocolState, _compact, _method_name,
        _status_name, _object_kind, _invoking_uid, _known_field_access_expected_success,
    )
    class Mutant(StatefulOpalVerifier):
        def _final_is_inconsistent(self, state, record, step_index=-1):
            # Patch: skip the KNOWN_FIELD_EXPECTED_SUCCESS check
            command = self._input(record)
            output = self._output(record)
            method = _compact(_method_name(command))
            status = _status_name(output)
            # If we would have triggered KNOWN_FIELD_EXPECTED_SUCCESS, return False instead
            if method in {"get", "set", "activate", "genkey", "read", "write", "endsession"}:
                if status != self.success_status:
                    expected_success = _known_field_access_expected_success(method, command)
                    if expected_success:
                        # This is where the original would return True; mutant returns False
                        pass  # fall through to parent
            return super()._final_is_inconsistent(state, record, step_index)
    # Simpler approach: just override to always pass on error statuses for known fields
    from src.solver import StatefulOpalVerifier as SV
    original_final = SV._final_is_inconsistent

    class Mutant2(StatefulOpalVerifier):
        pass

    def patched_final(self, state, record, step_index=-1):
        command = self._input(record)
        output = self._output(record)
        method = _compact(_method_name(command))
        status = _status_name(output)
        if method in {"get", "set"} and status != self.success_status:
            kind = _object_kind(command)
            if kind in ("locking", "mbrcontrol", "authority", "cpin"):
                return False  # mutant: don't flag known field errors
        return original_final(self, state, record, step_index)

    v = Mutant2()
    v._final_is_inconsistent = patched_final.__get__(v, Mutant2)
    return "NO_KNOWN_FIELD_EXPECTED_SUCCESS", "Remove known-field expected success rule", "rule_deletion", v.verify


def mutant_no_get_payload():
    """Remove Get payload column-subset validation."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _get_payload_inconsistent(self, state, command, output):
            return False
    v = Mutant()
    return "NO_GET_PAYLOAD", "Remove Get payload column validation", "rule_deletion", v.verify


def mutant_no_read_payload():
    """Remove Read old-pattern check."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _read_payload_inconsistent(self, state, command, output):
            return False
    v = Mutant()
    return "NO_READ_PAYLOAD", "Remove Read payload pattern check", "rule_deletion", v.verify


def mutant_no_precondition_error():
    """Remove session/auth precondition checks."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _expected_error_for_state(self, state, command, method, invoking, invoking_uid):
            return ""  # never predict expected errors
    v = Mutant()
    return "NO_PRECONDITION_ERROR", "Remove all precondition/expected-error checks", "rule_deletion", v.verify


def mutant_no_properties_payload():
    """Remove Properties payload validation."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _has_properties_payload(self, output):
            return True  # always accept Properties payload
    v = Mutant()
    return "NO_PROPERTIES_PAYLOAD", "Remove Properties payload validation", "rule_weakening", v.verify


def mutant_no_empty_result():
    """Remove empty-result checks for Set/GenKey/Activate/EndSession."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _empty_result_inconsistent(self, output):
            return False
        def _genkey_payload_inconsistent(self, output):
            return False
    v = Mutant()
    return "NO_EMPTY_RESULT", "Remove empty-result validation for Set/GenKey/etc", "rule_deletion", v.verify


def mutant_no_locking_data_access():
    """Remove Locking ReadLocked/WriteLocked enforcement."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _locking_data_access_blocked(self, state, method):
            return False
    v = Mutant()
    return "NO_LOCKING_DATA_ACCESS", "Remove Locking lock enforcement", "rule_deletion", v.verify


def mutant_no_activate_target():
    """Remove Activate SP UID target validation."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _activate_target_invalid(self, invoking, invoking_uid):
            return False
    v = Mutant()
    return "NO_ACTIVATE_TARGET", "Remove Activate target UID check", "rule_deletion", v.verify


def mutant_no_properties_target():
    """Remove Properties Session Manager target check."""
    from src.solver import StatefulOpalVerifier
    class Mutant(StatefulOpalVerifier):
        def _properties_target_invalid(self, invoking, invoking_uid):
            return False
    v = Mutant()
    return "NO_PROPERTIES_TARGET", "Remove Properties target validation", "rule_weakening", v.verify


def mutant_no_disabled_authority():
    """Remove Authority.Enabled check for StartSession."""
    from src.solver import StatefulOpalVerifier, _compact, _method_name, _status_name, _start_session_authority_refs
    class Mutant(StatefulOpalVerifier):
        def _final_is_inconsistent(self, state, record, step_index=-1):
            command = self._input(record)
            method = _compact(_method_name(command))
            if method == "startsession":
                # Skip disabled authority check, go straight to response validation
                output = self._output(record)
                status = _status_name(output)
                return self._start_session_inconsistent(state, command, output, status)
            return super()._final_is_inconsistent(state, record, step_index)
    v = Mutant()
    return "NO_DISABLED_AUTHORITY", "Remove disabled authority StartSession check", "rule_deletion", v.verify


def mutant_always_pass():
    """Baseline: predict pass for everything."""
    def verify(steps):
        return "pass"
    return "ALWAYS_PASS", "Always predict pass", "baseline", verify


def mutant_always_fail():
    """Baseline: predict fail for everything."""
    def verify(steps):
        return "fail"
    return "ALWAYS_FAIL", "Always predict fail", "baseline", verify


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_MUTANT_FACTORIES = [
    mutant_no_startsession_final,
    mutant_no_known_field_expected_success,
    mutant_no_get_payload,
    mutant_no_read_payload,
    mutant_no_precondition_error,
    mutant_no_properties_payload,
    mutant_no_empty_result,
    mutant_no_locking_data_access,
    mutant_no_activate_target,
    mutant_no_properties_target,
    mutant_no_disabled_authority,
    mutant_always_pass,
    mutant_always_fail,
]


def main():
    parser = argparse.ArgumentParser(description="Mutation testing for solver rules")
    parser.add_argument("--dataset-root", type=Path, default=Path("/dl2026/dataset"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    public = load_public_cases(args.dataset_root)
    synthetic = build_synthetic_cases(public)

    # Load labels
    labels = {}
    label_file = args.dataset_root / "label.jsonl"
    if label_file.exists():
        with label_file.open() as f:
            for line in f:
                d = json.loads(line)
                labels[d["filename"]] = d["label"]

    # Original predictions
    orig_public, orig_synthetic = _original_predictions(public, synthetic)

    # Check original accuracy on public
    orig_public_correct = sum(
        1 for name, pred in orig_public.items() if pred == labels.get(name, "")
    )
    print(f"original_public_accuracy={orig_public_correct}/{len(labels)}")

    # Run each mutant
    results: list[MutantResult] = []
    for factory in ALL_MUTANT_FACTORIES:
        mutant_id, description, operator, verify_fn = factory()
        mut_public, mut_synthetic = _mutant_predictions(verify_fn, public, synthetic)

        # Count differences
        public_diff = sum(
            1 for name in orig_public
            if orig_public[name] != mut_public.get(name, orig_public[name])
        )
        synthetic_diff = sum(
            1 for name in orig_synthetic
            if orig_synthetic[name] != mut_synthetic.get(name, orig_synthetic[name])
        )

        # Killed = at least one test detects the mutant (different output)
        killed_public = public_diff > 0
        killed_synthetic = synthetic_diff > 0

        # Also check: does mutant score BETTER on public labels?
        mut_public_correct = sum(
            1 for name, pred in mut_public.items() if pred == labels.get(name, "")
        )
        score_change = mut_public_correct - orig_public_correct

        results.append(MutantResult(
            mutant_id=mutant_id,
            description=description,
            operator=operator,
            killed_by_public=killed_public,
            killed_by_synthetic=killed_synthetic,
            public_diff=public_diff,
            synthetic_diff=synthetic_diff,
        ))

        status = "KILLED" if (killed_public or killed_synthetic) else "SURVIVED"
        print(
            f"{status:8s} {mutant_id:40s} "
            f"pub_diff={public_diff:3d} syn_diff={synthetic_diff:4d} "
            f"pub_score_change={score_change:+d}"
        )

    # Summary
    total = len(results)
    killed = sum(1 for r in results if r.killed_by_public or r.killed_by_synthetic)
    # Exclude baselines from mutation score
    non_baseline = [r for r in results if r.operator != "baseline"]
    non_baseline_killed = sum(1 for r in non_baseline if r.killed_by_public or r.killed_by_synthetic)
    ms = non_baseline_killed / len(non_baseline) if non_baseline else 0.0

    print(f"\n--- Mutation Score ---")
    print(f"total_mutants={len(non_baseline)}")
    print(f"killed={non_baseline_killed}")
    print(f"survived={len(non_baseline) - non_baseline_killed}")
    print(f"mutation_score={ms:.4f}")
    print(f"target=0.90")

    surviving = [r for r in non_baseline if not (r.killed_by_public or r.killed_by_synthetic)]
    if surviving:
        print(f"\n--- Surviving Mutants (potential over-aggressive rules) ---")
        for r in surviving:
            print(f"  {r.mutant_id}: {r.description}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        out_data = {
            "mutation_score": ms,
            "total": len(non_baseline),
            "killed": non_baseline_killed,
            "survived": len(non_baseline) - non_baseline_killed,
            "results": [
                {
                    "mutant_id": r.mutant_id,
                    "description": r.description,
                    "operator": r.operator,
                    "killed_by_public": r.killed_by_public,
                    "killed_by_synthetic": r.killed_by_synthetic,
                    "public_diff": r.public_diff,
                    "synthetic_diff": r.synthetic_diff,
                }
                for r in results
            ],
        }
        args.out.write_text(json.dumps(out_data, indent=2) + "\n")
        print(f"\nout={args.out}")


if __name__ == "__main__":
    main()
