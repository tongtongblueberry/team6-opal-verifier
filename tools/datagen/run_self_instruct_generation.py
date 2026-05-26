# Changed: add a dry-run Self-Instruct generation request builder.
# Why: synthetic data generation must follow the official output-first classification protocol without reintroducing ad-hoc generators.
"""Build Self-Instruct output-first generation request payloads.

This tool does not call an LLM by default and does not create candidate
trajectories. It writes prompt payloads and request metadata for an external
LLM runner. The prompt contract follows the Self-Instruct classification
output-first adaptation documented in ``third_party/self_instruct/README.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.self_instruct_seed_schema import (  # noqa: E402
    SeedSchemaError,
    load_seed_candidates,
    normalize_seeds,
)


Json = Dict[str, Any]
GENERATION_REQUEST_SCHEMA_VERSION = "self_instruct.generation_request.v1"
GENERATION_METADATA_SCHEMA_VERSION = "self_instruct.generation_metadata.v1"
PROMPT_CONTRACT_VERSION = "opal_final_response_output_first.v1"
OFFICIAL_SELF_INSTRUCT_SOURCE = {
    "paper": "Wang et al. 2023 Self-Instruct",
    "official_code": "https://github.com/yizhongw/self-instruct",
    "license": "Apache-2.0",
}


class SelfInstructGenerationError(ValueError):
    """Raised when generation request payloads cannot be built safely."""


def _now_kst() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).replace(microsecond=0).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _seed_context(seed: Mapping[str, Any]) -> Json:
    profile = seed.get("profile")
    if not isinstance(profile, Mapping):
        raise SelfInstructGenerationError("seed_profile_missing")
    return {
        "sample_id": seed.get("sample_id"),
        "source": seed.get("source"),
        "record_count": profile.get("record_count"),
        "method_sequence": profile.get("method_sequence"),
        "status_sequence": profile.get("status_sequence"),
        "final_method": profile.get("final_method"),
        "final_status": profile.get("final_status"),
        "input_json_chars": profile.get("input_json_chars"),
        "total_return_value_count": profile.get("total_return_value_count"),
        "final_return_value_count": profile.get("final_return_value_count"),
        "length_bin": profile.get("length_bin"),
    }


def load_input_only_seeds(path: Path) -> List[Json]:
    """Load input-only seeds and reject any label-like source field."""

    raw_rows = load_seed_candidates(path)
    normalized = normalize_seeds(raw_rows, allow_label_fields_for_audit=False)
    if not normalized:
        raise SelfInstructGenerationError("no_seed_rows")
    return normalized


def _select_seed_contexts(seeds: Sequence[Mapping[str, Any]], request_index: int, seeds_per_request: int) -> List[Json]:
    if seeds_per_request <= 0:
        raise SelfInstructGenerationError("seeds_per_request_must_be_positive")
    selected: List[Json] = []
    for offset in range(seeds_per_request):
        seed = seeds[(request_index * seeds_per_request + offset) % len(seeds)]
        selected.append(_seed_context(seed))
    return selected


def _generation_system_prompt() -> str:
    return (
        "You are generating Self-Instruct classification instances for an Opal "
        "final-response verifier. Follow output-first classification generation. "
        "Do not use public labels, rule-engine labels, rule ids, or archived verifier outputs."
    )


def _generation_user_prompt(seed_contexts: Sequence[Mapping[str, Any]], candidates_per_request: int) -> str:
    prompt_spec = {
        "task": "Create new Opal command-response trajectory verification candidates.",
        "official_protocol": "Self-Instruct classification output-first generation.",
        "output_first_order": [
            "choose target_label as pass or fail",
            "choose the target final response method/status/return value shape",
            "construct preceding records that provide only needed session/auth/object state",
            "make records[-1].output exactly equal target.final_response",
            "make primary_evidence.record_index equal target.final_response_index",
        ],
        "hard_constraints": [
            "label must be pass or fail",
            "label_target must be final_response",
            "target.final_response_index must be len(records) - 1",
            "primary_evidence.record_index must be len(records) - 1",
            "do not append EndSession SUCCESS after a fail verdict step",
            "do not use an intermediate response as the primary label evidence",
            "do not copy public20 trajectories exactly",
            "do not include public labels, rule ids, or rule-engine text",
        ],
        "seed_profile_context": list(seed_contexts),
        "required_response_json": {
            "candidates": [
                {
                    "sample_id": "unique string",
                    "instruction": "Judge whether the final response is valid for the trajectory state.",
                    "records": ["full trajectory records; final record is the verdict record"],
                    "label": "pass|fail",
                    "label_target": "final_response",
                    "target": {
                        "final_response_index": "integer len(records)-1",
                        "final_response": "exact output object from records[-1]",
                        "final_method": "optional final method name",
                    },
                    "primary_evidence": {
                        "record_index": "same integer len(records)-1",
                        "reason": "one concise final-response reason",
                    },
                    "source": "self_instruct_output_first",
                }
            ]
        },
        "candidate_count": candidates_per_request,
    }
    return json.dumps(prompt_spec, ensure_ascii=False, indent=2, sort_keys=True)


def build_generation_request(
    *,
    request_index: int,
    seeds: Sequence[Mapping[str, Any]],
    seeds_per_request: int,
    candidates_per_request: int,
    model: str,
    created_at_kst: str,
) -> Json:
    if request_index < 0:
        raise SelfInstructGenerationError("request_index_negative")
    if candidates_per_request <= 0:
        raise SelfInstructGenerationError("candidates_per_request_must_be_positive")

    request_id = f"self-instruct-gen-{request_index:05d}"
    seed_contexts = _select_seed_contexts(seeds, request_index, seeds_per_request)
    payload: Json = {
        "model": model,
        "messages": [
            {"role": "system", "content": _generation_system_prompt()},
            {"role": "user", "content": _generation_user_prompt(seed_contexts, candidates_per_request)},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "seed_profile_context": seed_contexts,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
    }
    return {
        "schema_version": GENERATION_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at_kst": created_at_kst,
        "execute": False,
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "source_seed_sample_ids": [str(context.get("sample_id")) for context in seed_contexts],
        "candidates_per_request": candidates_per_request,
        "payload_sha256": _sha256_json(payload),
        "payload": payload,
    }


def build_generation_requests(
    *,
    seeds: Sequence[Mapping[str, Any]],
    request_count: int,
    seeds_per_request: int,
    candidates_per_request: int,
    model: str,
    created_at_kst: Optional[str] = None,
) -> List[Json]:
    if request_count <= 0:
        raise SelfInstructGenerationError("request_count_must_be_positive")
    timestamp = created_at_kst or _now_kst()
    return [
        build_generation_request(
            request_index=index,
            seeds=seeds,
            seeds_per_request=seeds_per_request,
            candidates_per_request=candidates_per_request,
            model=model,
            created_at_kst=timestamp,
        )
        for index in range(request_count)
    ]


def build_metadata(seed_path: Path, requests: Sequence[Mapping[str, Any]]) -> Json:
    return {
        "schema_version": GENERATION_METADATA_SCHEMA_VERSION,
        "seed_input": str(seed_path),
        "request_count": len(requests),
        "execute": False,
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "request_ids": [request.get("request_id") for request in requests],
        "payload_sha256": {str(request.get("request_id")): request.get("payload_sha256") for request in requests},
        "notes": [
            "dry-run only: no LLM/API call was made",
            "request payloads contain input-only seed profiles, not public20 labels",
            "raw LLM outputs must be parsed by tools/datagen/parse_self_instruct_outputs.py",
        ],
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dry-run Self-Instruct generation request payloads.")
    parser.add_argument("--seed-jsonl", required=True, type=Path, help="Input-only seed JSON/JSONL. Label-like fields are rejected.")
    parser.add_argument("--requests-output", required=True, type=Path, help="Output request payload JSONL.")
    parser.add_argument("--metadata-json", required=True, type=Path, help="Output request metadata JSON.")
    parser.add_argument("--request-count", type=int, default=1, help="Number of dry-run request payloads to build.")
    parser.add_argument("--seeds-per-request", type=int, default=8, help="Number of input-only seed profiles per request.")
    parser.add_argument("--candidates-per-request", type=int, default=4, help="Requested candidates per external LLM call.")
    parser.add_argument("--model", default="external-llm", help="Model name recorded in the payload for an external runner.")
    parser.add_argument("--created-at-kst", default=None, help="Optional fixed KST timestamp for reproducible tests.")
    parser.add_argument("--execute", action="store_true", help="Reserved for future external runner integration; not implemented here.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if args.execute:
        print("run_self_instruct_generation: --execute is not implemented; no API call was made", file=sys.stderr)
        return 2
    try:
        seeds = load_input_only_seeds(args.seed_jsonl)
        requests = build_generation_requests(
            seeds=seeds,
            request_count=args.request_count,
            seeds_per_request=args.seeds_per_request,
            candidates_per_request=args.candidates_per_request,
            model=args.model,
            created_at_kst=args.created_at_kst,
        )
        _write_jsonl(requests, args.requests_output)
        args.metadata_json.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_json.write_text(
            json.dumps(build_metadata(args.seed_jsonl, requests), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, SeedSchemaError, SelfInstructGenerationError) as exc:
        print(f"run_self_instruct_generation: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
