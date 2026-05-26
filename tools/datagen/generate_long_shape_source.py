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
DEFAULT_SOURCE_NAME = "long_shape_matched"

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
DENSE_CHAR_PAYLOAD_PREFIX = "shape-density"

# 변경: public content를 쓰지 않는 1-record synthetic family의 로컬 object pool을 둔다.
# 이유: target_lengths=1만으로는 기존 long case가 짧아지지 않아 min record_count=1을 만들 수 없기 때문이다.
SINGLE_RECORD_OBJECTS = (
    ("ShapeProbe_MSID", "00 00 00 0B 00 00 84 02"),
    ("ShapeProbe_Locking", "00 00 08 02 00 00 00 01"),
    ("ShapeProbe_Admin", "00 00 00 09 00 01 00 01"),
    ("ShapeProbe_MBR", "00 00 08 03 00 00 00 01"),
)
SINGLE_RECORD_EXPECTED_ERRORS = ("NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL")


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


# 변경: char shape gate를 생성 단계에서 직접 목표로 삼을 수 있게 char counter를 분리한다.
# 이유: v3는 token-bin gate를 통과했지만 char median ratio가 엄격 기준에서 낮았다.
def char_count_for_steps(steps: list[Json]) -> int:
    return len(compact_records_text(steps))


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


def repeated_enrichment_value(value: str, repeat: int) -> str:
    if repeat <= 1:
        return value
    return "|".join(value for _ in range(repeat))


def dense_char_enrichment_value(field_round: int, repeat: int) -> str:
    # 변경: whitespace token 수를 늘리지 않고 char 길이만 올리는 fallback payload를 추가한다.
    # 이유: v4에서 513-1024 token bin이 과다해진 원인을 막으면서 char median ratio를 유지하기 위해서다.
    unit = f"{DENSE_CHAR_PAYLOAD_PREFIX}-{field_round:02d}-0123456789abcdef"
    return "|".join(unit for _ in range(max(1, repeat * 4)))


def needs_enrichment(steps: list[Json], min_tokens: int, min_chars: int) -> bool:
    return token_count_for_steps(steps) < min_tokens or char_count_for_steps(steps) < min_chars


def needs_token_enrichment(steps: list[Json], min_tokens: int) -> bool:
    # 변경: token-bin matching 대상과 char-density 보강 대상을 분리한다.
    # 이유: char 보강 대상까지 257-token 이상으로 밀어 v4 length JSD가 악화된 문제를 막기 위해서다.
    return token_count_for_steps(steps) < min_tokens


def needs_char_enrichment(steps: list[Json], min_chars: int) -> bool:
    return min_chars > 0 and char_count_for_steps(steps) < min_chars


# 변경: enrichment 목표에 char length와 payload 반복 강도를 추가한다.
# 이유: v3 기본 동작은 유지하면서 v4에서 char median을 더 강하게 끌어올릴 수 있게 하기 위해서다.
def enrich_get_success_payloads(
    case: Json,
    min_tokens: int = 257,
    min_chars: int = 0,
    field_cycles: int = 2,
    value_repeat: int = 1,
    max_tokens: int = 0,
) -> Json:
    # 변경: label-relevant final step이 아니라 benign Get SUCCESS filler payload만 풍부하게 만든다.
    # 이유: record_count는 유지하면서 public20 token-bin reference에 가까운 입력 밀도를 만들기 위해서다.
    next_case = json.loads(json.dumps(case, ensure_ascii=False))
    steps = next_case["steps"]
    indexes = get_success_step_indexes(steps)
    if not indexes:
        return next_case

    field_round = 0
    max_field_rounds = len(PUBLIC_LIKE_PAYLOAD_FIELDS) * field_cycles
    while needs_enrichment(steps, min_tokens=min_tokens, min_chars=min_chars) and field_round < max_field_rounds:
        changed = False
        for step_index in indexes:
            key, value = PUBLIC_LIKE_PAYLOAD_FIELDS[field_round % len(PUBLIC_LIKE_PAYLOAD_FIELDS)]
            payload = ensure_first_return_value(steps[step_index])
            field_name = f"{key}_{field_round}"
            payload[field_name] = repeated_enrichment_value(value, value_repeat)
            if max_tokens > 0 and token_count_for_steps(steps) > max_tokens:
                if char_count_for_steps(steps) >= min_chars:
                    del payload[field_name]
                    continue
                payload[field_name] = dense_char_enrichment_value(field_round, value_repeat)
                if token_count_for_steps(steps) > max_tokens:
                    del payload[field_name]
                    continue
            changed = True
            if not needs_enrichment(steps, min_tokens=min_tokens, min_chars=min_chars):
                break
        if not changed:
            break
        field_round += 1
    return next_case


def dense_char_fill_payloads(
    case: Json,
    min_chars: int,
    field_cycles: int = 2,
    value_repeat: int = 1,
    max_tokens: int = 0,
) -> Json:
    # 변경: token-bin을 바꾸지 않는 char-density 전용 enrichment 단계를 추가한다.
    # 이유: v4.1은 257-512 bin 안팎의 token 분포를 유지하면서 char median ratio를 올려야 하기 때문이다.
    next_case = json.loads(json.dumps(case, ensure_ascii=False))
    steps = next_case["steps"]
    indexes = get_success_step_indexes(steps)
    if not indexes or not needs_char_enrichment(steps, min_chars=min_chars):
        return next_case

    field_round = 0
    max_field_rounds = len(PUBLIC_LIKE_PAYLOAD_FIELDS) * field_cycles
    while needs_char_enrichment(steps, min_chars=min_chars) and field_round < max_field_rounds:
        changed = False
        for step_index in indexes:
            payload = ensure_first_return_value(steps[step_index])
            field_name = f"DenseChar_{field_round}"
            payload[field_name] = dense_char_enrichment_value(field_round, value_repeat)
            if max_tokens > 0 and token_count_for_steps(steps) > max_tokens:
                del payload[field_name]
                continue
            changed = True
            if not needs_char_enrichment(steps, min_chars=min_chars):
                break
        if not changed:
            break
        field_round += 1
    return next_case


def enrich_subset(
    cases: list[Json],
    fraction: float,
    min_tokens: int,
    min_chars: int = 0,
    field_cycles: int = 2,
    value_repeat: int = 1,
    max_tokens: int = 0,
    selection_mode: str = "token-or-char",
) -> list[Json]:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("--enrich-fraction must be between 0 and 1")
    if min_tokens < 0:
        raise ValueError("--min-enriched-tokens must be non-negative")
    if min_chars < 0:
        raise ValueError("--min-enriched-chars must be non-negative")
    if field_cycles <= 0:
        raise ValueError("--enrichment-field-cycles must be positive")
    if value_repeat <= 0:
        raise ValueError("--enrichment-value-repeat must be positive")
    if max_tokens < 0:
        raise ValueError("--max-enriched-tokens must be non-negative")
    if max_tokens > 0 and min_tokens > max_tokens:
        raise ValueError("--min-enriched-tokens must be less than or equal to --max-enriched-tokens")
    if selection_mode not in {"token-or-char", "token-only"}:
        raise ValueError("--enrich-selection must be token-or-char or token-only")
    if selection_mode == "token-only":
        candidate_predicate = lambda steps: needs_token_enrichment(steps, min_tokens=min_tokens)
    else:
        candidate_predicate = lambda steps: needs_enrichment(steps, min_tokens=min_tokens, min_chars=min_chars)
    candidates = [
        index
        for index, case in enumerate(cases)
        if candidate_predicate(case["steps"])
    ]
    selected = set(candidates[: int(len(candidates) * fraction)])
    return [
        enrich_get_success_payloads(
            case,
            min_tokens=min_tokens,
            min_chars=min_chars,
            field_cycles=field_cycles,
            value_repeat=value_repeat,
            max_tokens=max_tokens,
        )
        if index in selected
        else case
        for index, case in enumerate(cases)
    ]


def dense_char_fill_subset(
    cases: list[Json],
    fraction: float,
    min_chars: int,
    field_cycles: int = 2,
    value_repeat: int = 1,
    max_tokens: int = 0,
) -> list[Json]:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("--dense-char-fill-fraction must be between 0 and 1")
    if min_chars < 0:
        raise ValueError("--dense-char-fill-min-chars must be non-negative")
    if field_cycles <= 0:
        raise ValueError("--enrichment-field-cycles must be positive")
    if value_repeat <= 0:
        raise ValueError("--enrichment-value-repeat must be positive")
    if max_tokens < 0:
        raise ValueError("--max-enriched-tokens must be non-negative")
    if min_chars == 0 or fraction == 0.0:
        return cases
    candidates = [
        index
        for index, case in enumerate(cases)
        if needs_char_enrichment(case["steps"], min_chars=min_chars)
    ]
    selected = set(candidates[: int(len(candidates) * fraction)])
    return [
        dense_char_fill_payloads(
            case,
            min_chars=min_chars,
            field_cycles=field_cycles,
            value_repeat=value_repeat,
            max_tokens=max_tokens,
        )
        if index in selected
        else case
        for index, case in enumerate(cases)
    ]


# 변경: 별도 1-record family를 append할 수 있게 한다.
# 이유: public20 shortest-case shape를 content 복사 없이 덮기 위한 v4 옵션이다.
def single_record_step(method_name: str, object_name: str, object_uid: str, status: str, variant: int) -> Json:
    required: Json = {}
    if method_name == "Get":
        required["Cellblock"] = [{"startColumn": 3}, {"endColumn": 3 + (variant % 3)}]
    elif method_name == "Set":
        required["Values"] = [{"3": f"shape_value_{variant:02d}"}]
    else:
        raise ValueError(f"unsupported single-record method: {method_name}")

    return_values: list[Any]
    if status == "SUCCESS" and method_name == "Get":
        return_values = [{"3": f"shape_value_{variant:02d}"}]
    else:
        return_values = []

    return {
        "input": {
            "method": {"name": method_name},
            "invoking_id": {"uid": object_uid, "name": object_name},
            "args": {"required": required, "optional": {"shape_family": "synthetic_single_record"}},
        },
        "output": {"return_values": return_values, "status_codes": status},
    }


def build_single_record_family(per_label: int) -> list[Json]:
    if per_label < 0:
        raise ValueError("--single-record-per-label must be non-negative")
    cases: list[Json] = []
    for index in range(per_label):
        object_name, object_uid = SINGLE_RECORD_OBJECTS[index % len(SINGLE_RECORD_OBJECTS)]
        method_name = "Get" if index % 2 == 0 else "Set"
        expected_error = SINGLE_RECORD_EXPECTED_ERRORS[index % len(SINGLE_RECORD_EXPECTED_ERRORS)]
        cases.append(
            {
                "steps": [single_record_step(method_name, object_name, object_uid, expected_error, index)],
                "label": "pass",
                "spec_rule": "single-record-nosession-expected-error",
                "description": f"single-record {method_name}({object_name})->{expected_error}",
            }
        )
        cases.append(
            {
                "steps": [single_record_step(method_name, object_name, object_uid, "SUCCESS", index)],
                "label": "fail",
                "spec_rule": "single-record-nosession-unexpected-success",
                "description": f"single-record {method_name}({object_name})->SUCCESS",
            }
        )
    return cases


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


def build_summary(
    cases: list[Json],
    output_path: Path,
    target_lengths: list[int],
    enrich_fraction: float,
    single_record_per_label: int = 0,
    min_enriched_tokens: int = 257,
    min_enriched_chars: int = 0,
    enrichment_field_cycles: int = 2,
    enrichment_value_repeat: int = 1,
    max_enriched_tokens: int = 0,
    enrich_selection: str = "token-or-char",
    dense_char_fill_fraction: float = 0.0,
    dense_char_fill_min_chars: int = 0,
    dense_char_fill_field_cycles: int = 0,
    dense_char_fill_value_repeat: int = 0,
    source_name: str = DEFAULT_SOURCE_NAME,
) -> dict[str, Any]:
    record_counts = [len(case["steps"]) for case in cases]
    token_counts = [token_count_for_steps(case["steps"]) for case in cases]
    char_counts = [char_count_for_steps(case["steps"]) for case in cases]
    return {
        "output_path": str(output_path),
        "source_name": source_name,
        "count": len(cases),
        "label_counts": dict(Counter(case["label"] for case in cases)),
        "record_count": stats(record_counts),
        "whitespace_token_count": stats(token_counts),
        "char_count": stats(char_counts),
        "token_bins": {key: Counter(token_bin(count) for count in token_counts)[key] for key in ("1-32", "33-64", "65-128", "129-256", "257-512", "513-1024", "1025+")},
        "target_length_counts": dict(Counter(target_lengths)),
        "enrich_fraction": enrich_fraction,
        "single_record_per_label": single_record_per_label,
        "single_record_total": single_record_per_label * 2,
        "min_enriched_tokens": min_enriched_tokens,
        "min_enriched_chars": min_enriched_chars,
        "max_enriched_tokens": max_enriched_tokens,
        "enrich_selection": enrich_selection,
        "dense_char_fill_fraction": dense_char_fill_fraction,
        "dense_char_fill_min_chars": dense_char_fill_min_chars,
        "dense_char_fill_field_cycles": dense_char_fill_field_cycles,
        "dense_char_fill_value_repeat": dense_char_fill_value_repeat,
        "enrichment_field_cycles": enrichment_field_cycles,
        "enrichment_value_repeat": enrichment_value_repeat,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate public-free long trajectory source with public20-like shape.")
    parser.add_argument("--output", default=str(DEFAULT_RUN_ROOT / "raw" / "long_shape_matched.jsonl"))
    parser.add_argument("--summary-output", default=str(DEFAULT_RUN_ROOT / "reports" / "long_shape_matched_raw_summary.json"))
    parser.add_argument("--target-lengths", default=DEFAULT_TARGET_LENGTHS)
    parser.add_argument("--enrich-fraction", type=float, default=DEFAULT_ENRICH_FRACTION)
    parser.add_argument("--min-enriched-tokens", type=int, default=257)
    parser.add_argument("--min-enriched-chars", type=int, default=0)
    parser.add_argument("--max-enriched-tokens", type=int, default=0)
    parser.add_argument("--enrich-selection", choices=("token-or-char", "token-only"), default="token-or-char")
    parser.add_argument("--dense-char-fill-fraction", type=float, default=0.0)
    parser.add_argument("--dense-char-fill-min-chars", type=int, default=0)
    parser.add_argument("--dense-char-fill-field-cycles", type=int, default=0)
    parser.add_argument("--dense-char-fill-value-repeat", type=int, default=0)
    parser.add_argument("--enrichment-field-cycles", type=int, default=2)
    parser.add_argument("--enrichment-value-repeat", type=int, default=1)
    parser.add_argument("--single-record-per-label", type=int, default=0)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--allow-deprecated-v4-v41", action="store_true",
                        help="Allow audit-only reproduction of deprecated v4/v4.1 shape data")
    args = parser.parse_args()

    # 변경: v4/v4.1 shape-source CLI 기본 실행을 차단하고 감사 재현 전용으로 남긴다.
    # 이유: 이 도구는 label-invalid long trajectory source를 상속해 학습 데이터로 쓰면 안 된다.
    if not args.allow_deprecated_v4_v41:
        parser.error(
            "deprecated v4/v4.1 shape datagen is audit-only; see "
            "docs/archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md"
        )
    return args


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    summary_path = Path(args.summary_output)
    target_lengths = parse_target_lengths(args.target_lengths)

    cases = add_length_padding(gen_all(), target_lengths)
    cases.extend(build_single_record_family(args.single_record_per_label))
    cases = enrich_subset(
        cases,
        fraction=args.enrich_fraction,
        min_tokens=args.min_enriched_tokens,
        min_chars=args.min_enriched_chars,
        field_cycles=args.enrichment_field_cycles,
        value_repeat=args.enrichment_value_repeat,
        max_tokens=args.max_enriched_tokens,
        selection_mode=args.enrich_selection,
    )
    dense_field_cycles = args.dense_char_fill_field_cycles or args.enrichment_field_cycles
    dense_value_repeat = args.dense_char_fill_value_repeat or args.enrichment_value_repeat
    cases = dense_char_fill_subset(
        cases,
        fraction=args.dense_char_fill_fraction,
        min_chars=args.dense_char_fill_min_chars,
        field_cycles=dense_field_cycles,
        value_repeat=dense_value_repeat,
        max_tokens=args.max_enriched_tokens,
    )
    write_jsonl(cases, output_path=output_path, source_name=args.source_name)

    summary = build_summary(
        cases,
        output_path=output_path,
        target_lengths=target_lengths,
        enrich_fraction=args.enrich_fraction,
        single_record_per_label=args.single_record_per_label,
        min_enriched_tokens=args.min_enriched_tokens,
        min_enriched_chars=args.min_enriched_chars,
        max_enriched_tokens=args.max_enriched_tokens,
        enrich_selection=args.enrich_selection,
        dense_char_fill_fraction=args.dense_char_fill_fraction,
        dense_char_fill_min_chars=args.dense_char_fill_min_chars,
        dense_char_fill_field_cycles=dense_field_cycles,
        dense_char_fill_value_repeat=dense_value_repeat,
        enrichment_field_cycles=args.enrichment_field_cycles,
        enrichment_value_repeat=args.enrichment_value_repeat,
        source_name=args.source_name,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
