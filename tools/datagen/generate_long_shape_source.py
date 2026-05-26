#!/usr/bin/env python3
# 변경: public-free long trajectory source를 public20 shape target에 맞춰 생성하는 도구를 추가한다.
# 이유: public contents/labels 없이 record-count와 token-bin 분포만 맞춘 manifest 후보를 재현 가능하게 만들기 위해서다.

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.generate_long_trajectories import add_length_padding, gen_all


DEFAULT_RUNTIME_ROOT = Path(os.environ.get("OPAL_RUNTIME_ROOT", "/workspace/sinjeongmin_opal_verifier"))
DEFAULT_RUN_ROOT = DEFAULT_RUNTIME_ROOT / "ops" / "runs" / "long_shape_source"
DEFAULT_TARGET_LENGTHS = "1,2,7,10,11,21,26,21,27,39,1,2,7,10,9,21,26,21,27,39"
DEFAULT_ENRICH_FRACTION = 0.65

PUBLIC_LIKE_PAYLOAD_FIELDS = (
    ("Authority", "00 00 00 09 00 01 00 01"),
    ("Credential", "00 00 00 0B 00 00 84 02"),
    ("LockingRange", "00 00 08 02 00 00 00 01"),
    ("MBRControl", "00 00 08 03 00 00 00 01"),
    ("ReadLocked", "False"),
    ("WriteLocked", "True"),
    ("LockOnReset", "PowerCycle"),
    ("RangeStart", "0000000000000000"),
    ("RangeLength", "0000000000100000"),
    ("ActiveKey", "00 00 00 09 00 00 00 01"),
    ("HostChallenge", "AB CD EF 01 23 45 67 89"),
)


Json = dict[str, Any]


def parse_target_lengths(raw: str) -> list[int]:
    lengths = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not lengths:
        raise ValueError("--target-lengths must contain at least one integer")
    if any(length <= 0 for length in lengths):
        raise ValueError("--target-lengths must be positive integers")
    return lengths


def compact_records_text(steps: list[Json]) -> str:
    return json.dumps({"records": steps}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def token_count_for_steps(steps: list[Json]) -> int:
    return len(compact_records_text(steps).split())


def token_bin(count: int) -> str:
    if count <= 32:
        return "1-32"
    if count <= 64:
        return "33-64"
    if count <= 128:
        return "65-128"
    if count <= 256:
        return "129-256"
    if count <= 512:
        return "257-512"
    if count <= 1024:
        return "513-1024"
    return "1025+"


def get_success_step_indexes(steps: list[Json]) -> list[int]:
    indexes: list[int] = []
    for index, step in enumerate(steps):
        method = step.get("input", {}).get("method", {})
        output = step.get("output", {})
        if not isinstance(method, dict):
            continue
        if method.get("name") == "Get" and output.get("status_codes") == "SUCCESS":
            indexes.append(index)
    return indexes


def ensure_first_return_value(step: Json) -> Json:
    output = step.setdefault("output", {})
    return_values = output.setdefault("return_values", [{}])
    if not isinstance(return_values, list) or not return_values:
        output["return_values"] = [{}]
        return_values = output["return_values"]
    if not isinstance(return_values[0], dict):
        return_values[0] = {}
    return return_values[0]


def enrich_get_success_payloads(case: Json, min_tokens: int = 257) -> Json:
    # 변경: label-relevant final step이 아니라 benign Get SUCCESS filler payload만 풍부하게 만든다.
    # 이유: record_count는 유지하면서 public20 token-bin reference에 가까운 입력 밀도를 만들기 위해서다.
    next_case = json.loads(json.dumps(case, ensure_ascii=False))
    steps = next_case["steps"]
    indexes = get_success_step_indexes(steps)
    if not indexes:
        return next_case

    field_round = 0
    while token_count_for_steps(steps) < min_tokens and field_round < len(PUBLIC_LIKE_PAYLOAD_FIELDS) * 2:
        for step_index in indexes:
            key, value = PUBLIC_LIKE_PAYLOAD_FIELDS[field_round % len(PUBLIC_LIKE_PAYLOAD_FIELDS)]
            payload = ensure_first_return_value(steps[step_index])
            payload[f"{key}_{field_round}"] = value
            if token_count_for_steps(steps) >= min_tokens:
                break
        field_round += 1
    return next_case


def enrich_subset(cases: list[Json], fraction: float, min_tokens: int) -> list[Json]:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("--enrich-fraction must be between 0 and 1")
    token_counts = [token_count_for_steps(case["steps"]) for case in cases]
    candidates = [index for index, count in enumerate(token_counts) if count < min_tokens]
    selected = set(candidates[: int(len(candidates) * fraction)])
    return [
        enrich_get_success_payloads(case, min_tokens=min_tokens) if index in selected else case
        for index, case in enumerate(cases)
    ]


def stats(values: list[int]) -> dict[str, float | int]:
    return {
        "min": min(values),
        "median": median(values),
        "mean": round(sum(values) / len(values), 6),
        "max": max(values),
    }


def write_jsonl(cases: list[Json], output_path: Path, source_name: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for index, case in enumerate(cases):
            row = {
                "sample_id": f"{source_name}-{index:06d}",
                "records": case["steps"],
                "label": case["label"],
                "source": source_name,
                "spec_rule": str(case.get("spec_rule", "")),
                "description": str(case.get("description", "")),
            }
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def build_summary(cases: list[Json], output_path: Path, target_lengths: list[int], enrich_fraction: float) -> dict[str, Any]:
    record_counts = [len(case["steps"]) for case in cases]
    token_counts = [token_count_for_steps(case["steps"]) for case in cases]
    char_counts = [len(compact_records_text(case["steps"])) for case in cases]
    return {
        "output_path": str(output_path),
        "count": len(cases),
        "label_counts": dict(Counter(case["label"] for case in cases)),
        "record_count": stats(record_counts),
        "whitespace_token_count": stats(token_counts),
        "char_count": stats(char_counts),
        "token_bins": {key: Counter(token_bin(count) for count in token_counts)[key] for key in ("1-32", "33-64", "65-128", "129-256", "257-512", "513-1024", "1025+")},
        "target_length_counts": dict(Counter(target_lengths)),
        "enrich_fraction": enrich_fraction,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate public-free long trajectory source with public20-like shape.")
    parser.add_argument("--output", default=str(DEFAULT_RUN_ROOT / "raw" / "long_shape_matched.jsonl"))
    parser.add_argument("--summary-output", default=str(DEFAULT_RUN_ROOT / "reports" / "long_shape_matched_raw_summary.json"))
    parser.add_argument("--target-lengths", default=DEFAULT_TARGET_LENGTHS)
    parser.add_argument("--enrich-fraction", type=float, default=DEFAULT_ENRICH_FRACTION)
    parser.add_argument("--min-enriched-tokens", type=int, default=257)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    summary_path = Path(args.summary_output)
    target_lengths = parse_target_lengths(args.target_lengths)

    cases = add_length_padding(gen_all(), target_lengths)
    cases = enrich_subset(cases, fraction=args.enrich_fraction, min_tokens=args.min_enriched_tokens)
    write_jsonl(cases, output_path=output_path, source_name="long_shape_matched")

    summary = build_summary(cases, output_path=output_path, target_lengths=target_lengths, enrich_fraction=args.enrich_fraction)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
