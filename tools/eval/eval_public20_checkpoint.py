#!/usr/bin/env python3
"""Evaluate checkpoints on public20 dataset."""
import json
import os
import sys
import gc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.solver import Solver, _parse_records


def evaluate_checkpoint(ckpt_path, inputs, labels):
    os.environ["OPAL_MERGED_MODEL_DIR"] = ckpt_path
    solver = Solver()
    correct = 0
    total = 0
    wrongs = []
    for idx, (inp, label) in enumerate(zip(inputs, labels)):
        records = _parse_records(inp)
        pred = solver.predict(records)
        match = pred == label
        correct += int(match)
        total += 1
        if not match:
            wrongs.append(f"  tc{idx+1}: true={label} pred={pred}")
    acc = correct / total if total else 0
    ckpt_name = os.path.basename(ckpt_path) or "final"
    print(f"{ckpt_name}: {correct}/{total} = {acc:.1%}")
    for w in wrongs:
        print(w)
    print()
    del solver
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    return acc


def main():
    inputs = []
    with open("data/local/public20/public20_input.jsonl") as f:
        for line in f:
            inputs.append(json.loads(line))

    labels = []
    with open("data/local/public20/public20_labels.local.jsonl") as f:
        for line in f:
            labels.append(json.loads(line)["label"])

    ckpt_root = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sinjeongmin_opal_verifier/ops/runs/gen200_09b_fullft/e10"

    checkpoints = [
        os.path.join(ckpt_root, "checkpoint-40"),   # epoch 2
        os.path.join(ckpt_root, "checkpoint-60"),   # epoch 3
        os.path.join(ckpt_root, "checkpoint-100"),  # epoch 5
        ckpt_root,                                   # final epoch 10
    ]

    best_acc = 0
    best_ckpt = ""
    for ckpt in checkpoints:
        if not os.path.exists(os.path.join(ckpt, "config.json")):
            print(f"SKIP {ckpt}: no config.json")
            continue
        acc = evaluate_checkpoint(ckpt, inputs, labels)
        if acc > best_acc:
            best_acc = acc
            best_ckpt = ckpt

    print(f"BEST: {best_ckpt} ({best_acc:.1%})")


if __name__ == "__main__":
    main()
