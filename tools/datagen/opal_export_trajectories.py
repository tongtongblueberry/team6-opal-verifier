# Changed: create trajectory exporter with counterfactual labeling
# Why: convert GFlowNet raw trajectories to training-ready JSONL with pass/fail labels
"""
Opal Trajectory Exporter
=========================
Reads raw GFlowNet trajectories (JSON) and exports:
  - gen_input.jsonl: Opal JSON records
  - gen_labels.local.jsonl: pass/fail labels with rule references

Counterfactual labeling:
  - records[0..n-2]: always use FSM expected output (all correct)
  - records[n-1]: 50% expected output (pass), 50% flipped output (fail)
"""

import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.datagen.opal_record_builder import OpalRecordBuilder


# ── Counterfactual flip ──

ERROR_STATUSES = ["NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL",
                  "SP_BUSY", "SP_FROZEN", "AUTHORITY_LOCKED_OUT",
                  "NO_SESSIONS_AVAILABLE"]


def flip_status(expected: str, rng: random.Random) -> str:
    """Flip expected output to create a fail case.

    If expected = SUCCESS → random error code
    If expected = ERROR → SUCCESS
    """
    if expected == "SUCCESS":
        return rng.choice(ERROR_STATUSES)
    else:
        return "SUCCESS"


def export(raw_path: str, output_dir: str, pass_ratio: float = 0.5,
           seed: int = 42, min_length: int = 1, exclude_cutoff: bool = False):
    """Export GFlowNet trajectories to training JSONL.

    Args:
        raw_path: path to raw_trajectories.json from GFlowNet
        output_dir: output directory for gen_input.jsonl / gen_labels.local.jsonl
        pass_ratio: fraction of pass labels (0.5 = balanced)
        seed: random seed
        min_length: minimum trajectory length (skip shorter ones)
    """
    rng = random.Random(seed)

    with open(raw_path) as f:
        raw_trajs = json.load(f)

    # Changed: filter out trajectories that were force-terminated at T_MAX
    # Why: trajectories hitting T_MAX=40 have an unintended final target (cutoff artifact)
    if exclude_cutoff:
        original_count = len(raw_trajs)
        max_raw_len = max(len(t) for t in raw_trajs)
        raw_trajs = [t for t in raw_trajs if len(t) < max_raw_len]
        print(f"  Filtered cutoff trajectories: {original_count - len(raw_trajs)} removed")

    # Changed: ACE Set cap — limit SET_ACE_BOOLEXPR to max 2 per trajectory
    # Why: SET_ACE_BOOLEXPR self-loop produces 29.8% of all records, public20 has 0% ACE
    ace_capped = 0
    for traj in raw_trajs:
        ace_count = 0
        filtered = []
        for step in traj:
            if step['action'] == 'SET_ACE_BOOLEXPR':
                ace_count += 1
                if ace_count > 2:
                    continue  # skip excess ACE steps
            filtered.append(step)
        if len(filtered) < len(traj):
            ace_capped += 1
        traj.clear()
        traj.extend(filtered)
    print(f"  ACE Set cap: {ace_capped} trajectories trimmed")

    # Changed: post-hoc truncation to shift final-method distribution toward public20
    # Why: GFlowNet final methods are Activate-heavy (33.6% vs public20 5%).
    #      public20 final is StartSession 35% + Get 30% + Properties/Set/Read 30%.
    P_TRUNCATE_GET = 0.35
    P_TRUNCATE_START = 0.35
    P_TRUNCATE_SET = 0.1       # Set/Properties/Read also as final (public20 ~30%)
    truncated_count = 0
    new_trajs = []
    for traj in raw_trajs:
        get_idx = [i for i, s in enumerate(traj) if s['action'].startswith('GET_')]
        start_idx = [i for i, s in enumerate(traj) if s['action'].startswith('START_')]
        set_idx = [i for i, s in enumerate(traj)
                   if s['action'].startswith('SET_') and s['action'] != 'SET_ACE_BOOLEXPR']

        if get_idx and rng.random() < P_TRUNCATE_GET:
            cut = rng.choice(get_idx)
            new_trajs.append(traj[:cut + 1])
            truncated_count += 1
        elif start_idx and rng.random() < P_TRUNCATE_START:
            cut = rng.choice(start_idx)
            new_trajs.append(traj[:cut + 1])
            truncated_count += 1
        elif set_idx and rng.random() < P_TRUNCATE_SET:
            cut = rng.choice(set_idx)
            new_trajs.append(traj[:cut + 1])
            truncated_count += 1
        else:
            # If still ends on Activate, try to truncate before it
            if traj and traj[-1]['action'].startswith('ACTIVATE'):
                non_activate = [i for i, s in enumerate(traj)
                                if not s['action'].startswith('ACTIVATE') and i > 0]
                if non_activate and rng.random() < 0.7:
                    cut = rng.choice(non_activate[-3:]) if len(non_activate) >= 3 else rng.choice(non_activate)
                    new_trajs.append(traj[:cut + 1])
                    truncated_count += 1
                else:
                    new_trajs.append(traj)
            else:
                new_trajs.append(traj)
    raw_trajs = new_trajs
    print(f"  Post-hoc truncation: {truncated_count}/{len(raw_trajs)} trajectories truncated")

    os.makedirs(output_dir, exist_ok=True)
    inp_path = os.path.join(output_dir, "gen_input.jsonl")
    lab_path = os.path.join(output_dir, "gen_labels.local.jsonl")

    inputs = []
    labels = []
    builder = OpalRecordBuilder(seed=seed)

    label_counts = Counter()
    rule_counts = Counter()
    status_counts = Counter()
    length_counts = Counter()

    for traj_idx, traj in enumerate(raw_trajs):
        if len(traj) < min_length:
            continue

        builder.reset_trajectory()

        # Changed: find the last step that produces a real record (not None)
        # Why: POWER_CYCLE/POWER_ON return None from RecordBuilder; if the last
        # trajectory step is one of these, the label metadata won't match the
        # actual last record in the JSON, causing Gate C failures
        last_valid_idx = len(traj) - 1
        while last_valid_idx >= 0:
            test_record = builder.build(
                action_name=traj[last_valid_idx]['action'],
                output_status=traj[last_valid_idx]['expected_status'],
                index=999,
            )
            if test_record is not None:
                break
            last_valid_idx -= 1

        if last_valid_idx < 0:
            continue  # skip entirely — no valid records in this trajectory

        # Reset builder state since test builds above consumed RNG
        builder.reset_trajectory()

        # Build prefix records[0..last_valid_idx-1] with expected (correct) outputs
        records = []
        for step_idx, step in enumerate(traj[:last_valid_idx]):
            record = builder.build(
                action_name=step['action'],
                output_status=step['expected_status'],
                index=step_idx + 1,
            )
            # Changed: skip None records (e.g. POWER_CYCLE/POWER_ON return None)
            if record is not None:
                records.append(record)

        # Build the judged record at last_valid_idx with counterfactual labeling
        last_step = traj[last_valid_idx]
        expected_status = last_step['expected_status']
        rules = last_step.get('rules', [])

        is_pass = rng.random() < pass_ratio

        if is_pass:
            actual_status = expected_status
            label = "pass"
        else:
            actual_status = flip_status(expected_status, rng)
            label = "fail"

        last_record = builder.build(
            action_name=last_step['action'],
            output_status=actual_status,
            index=len(records) + 1,
        )
        # Changed: last_valid_idx guarantees this is not None, but guard anyway
        if last_record is not None:
            records.append(last_record)

        # Build sample
        sid = f"gfn{traj_idx + 1:04d}"
        inp = {
            "input": json.dumps({"records": records}),
            "sample_id": sid,
            "source": "opal_fsm_gflownet_v1",
        }
        lab = {
            "label": label,
            "sample_id": sid,
            "source": "opal_fsm_gflownet_v1.deterministic",
            "rules": rules,
            "expected_status": expected_status,
            "actual_status": actual_status,
        }

        inputs.append(inp)
        labels.append(lab)

        label_counts[label] += 1
        for r in rules:
            rule_counts[r] += 1
        status_counts[f"{expected_status}→{actual_status}"] += 1
        length_counts[len(records)] += 1

    # Write JSONL
    with open(inp_path, "w") as f:
        for inp in inputs:
            f.write(json.dumps(inp) + "\n")

    with open(lab_path, "w") as f:
        for lab in labels:
            f.write(json.dumps(lab) + "\n")

    # Report
    report = {
        "total": len(inputs),
        "label_distribution": dict(label_counts),
        "pass_ratio": pass_ratio,
        "min_length": min_length,
        "seed": seed,
        "generator": "opal_fsm_gflownet_v1",
        "label_method": "deterministic_counterfactual",
        "rule_coverage": dict(sorted(rule_counts.items())),
        "unique_rules": len(rule_counts),
        "status_transitions": dict(sorted(status_counts.items(), key=lambda x: -x[1])),
        "record_count_distribution": dict(sorted(length_counts.items())),
    }
    report_path = os.path.join(output_dir, "generation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Exported {len(inputs)} samples to {output_dir}")
    print(f"  Labels: {dict(label_counts)}")
    print(f"  Rules covered: {len(rule_counts)}")
    print(f"  Record lengths: min={min(length_counts.keys())}, max={max(length_counts.keys())}")
    print(f"  Status transitions (top 5):")
    for st, cnt in sorted(status_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"    {st}: {cnt}")


def main():
    parser = argparse.ArgumentParser(description="Export GFlowNet trajectories")
    parser.add_argument("--raw", default="runs/gflownet/raw_trajectories.json",
                        help="Path to raw_trajectories.json")
    parser.add_argument("--output-dir", default="data/local/gen_gflownet",
                        help="Output directory")
    parser.add_argument("--pass-ratio", type=float, default=0.5,
                        help="Fraction of pass labels (default: 0.5)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-length", type=int, default=1,
                        help="Minimum trajectory length (default: 1)")
    parser.add_argument("--exclude-cutoff", action="store_true",
                        help="Exclude trajectories that hit T_MAX (cutoff artifact)")
    args = parser.parse_args()

    export(args.raw, args.output_dir, args.pass_ratio, args.seed, args.min_length,
           args.exclude_cutoff)


if __name__ == "__main__":
    main()
