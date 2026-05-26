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
import re
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
# Changed: connect the optional external provider runner behind --execute.
# Why: generation requests can now be executed only through env-gated provider code that writes raw parser input.
from tools.datagen.self_instruct_llm_runner import (  # noqa: E402
    SelfInstructLLMRunnerError,
    provider_env_var,
    run_generation_requests,
)


Json = Dict[str, Any]
GENERATION_REQUEST_SCHEMA_VERSION = "self_instruct.generation_request.v1"
GENERATION_METADATA_SCHEMA_VERSION = "self_instruct.generation_metadata.v1"
# Changed: bump the prompt contract to include required legacy spec source spans.
# Why: output-first generation must be spec-grounded before raw outputs can become candidates.
PROMPT_CONTRACT_VERSION = "opal_final_response_spec_grounded_output_first.v1"
DEFAULT_SPEC_RULES_PATH = ROOT / "docs" / "legacy_spec_rules.md"
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


# Changed: parse docs/legacy_spec_rules.md into explicit source-span cards for prompts.
# Why: generation requests must be grounded in the spec-rule text, not just seed shape profiles.
def load_spec_rule_cards(path: Path) -> List[Json]:
    source_path = str(path.relative_to(ROOT)) if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    cards: List[Json] = []
    category = ""
    current: Optional[Json] = None

    def flush(end_line: int) -> None:
        if current is None:
            return
        fields = current.pop("_fields")
        required = ("SPEC", "CONDITION", "EXPECTED_STATUS", "IF_VIOLATED")
        missing = [field for field in required if field not in fields]
        if missing:
            raise SelfInstructGenerationError(f"spec_rule_fields_missing:{current.get('rule_ref')}:{','.join(missing)}")
        start_line = int(current["source_start_line"])
        current["source_end_line"] = end_line
        current["source_span"] = f"{source_path}:{start_line}-{end_line}"
        current["spec_section"] = fields["SPEC"]
        current["condition"] = fields["CONDITION"]
        current["expected_status"] = fields["EXPECTED_STATUS"]
        current["if_violated"] = fields["IF_VIOLATED"]
        if "EXAMPLE_TRAJECTORY" in fields:
            current["example_trajectory"] = fields["EXAMPLE_TRAJECTORY"]
        cards.append(current)

    for line_number, line in enumerate(lines, start=1):
        category_match = re.match(r"^##\s+(CATEGORY\s+\d+:.+)$", line)
        if category_match:
            category = category_match.group(1).strip()

        rule_match = re.match(r"^###\s+(RULE\s+\d+):\s*(.+)$", line)
        if rule_match:
            if current is not None:
                flush(line_number - 1)
            current = {
                "rule_ref": rule_match.group(1).strip(),
                "title": rule_match.group(2).strip(),
                "category": category,
                "source_path": source_path,
                "source_start_line": line_number,
                "_fields": {},
            }
            continue

        if current is None or not line.startswith("- "):
            continue
        key, separator, value = line[2:].partition(":")
        if not separator:
            continue
        current["_fields"][key.strip()] = value.strip()

    if current is not None:
        flush(len(lines))
    if not cards:
        raise SelfInstructGenerationError("no_spec_rule_cards")
    return cards


def _select_spec_rule_contexts(cards: Sequence[Mapping[str, Any]], request_index: int, spec_rules_per_request: int) -> List[Json]:
    if spec_rules_per_request <= 0:
        raise SelfInstructGenerationError("spec_rules_per_request_must_be_positive")
    selected: List[Json] = []
    for offset in range(spec_rules_per_request):
        card = cards[(request_index * spec_rules_per_request + offset) % len(cards)]
        selected.append(dict(card))
    return selected


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
        "You are generating spec-grounded Self-Instruct classification instances "
        "for an Opal final-response verifier. Follow output-first classification "
        "generation. Use only the supplied spec_rule_context entries as normative "
        "grounding. Do not use public labels, rule-engine labels, archived verifier "
        "outputs, or any unstated Opal facts."
    )


def _generation_user_prompt(
    seed_contexts: Sequence[Mapping[str, Any]],
    spec_rule_contexts: Sequence[Mapping[str, Any]],
    candidates_per_request: int,
) -> str:
    prompt_spec = {
        "task": "Create new Opal command-response trajectory verification candidates.",
        "official_protocol": "Self-Instruct classification output-first generation.",
        "grounding_policy": {
            "source": "docs/legacy_spec_rules.md",
            "allowed_normative_source": "Only cite and use entries in spec_rule_context.",
            "required_per_candidate": "Each candidate must include spec_grounding with rule_ref, source_path, source_span, condition, and expected_status copied from a supplied card.",
            "no_ungrounded_text": "Do not create candidates whose label rationale cannot be traced to a supplied source_span.",
            "not_runtime_rule_engine": "These source spans are offline generation/audit provenance and must not be embedded in solver/runtime prompts.",
        },
        "output_first_order": [
            "choose target_label as pass or fail",
            "choose the target final response method/status/return value shape",
            "choose one or more supplied spec_rule_context cards that entail or refute that final response",
            "construct preceding records that provide only needed session/auth/object state",
            "make records[-1].output exactly equal target.final_response",
            "make primary_evidence.record_index equal target.final_response_index",
        ],
        "pass_fail_balance": {
            "if_candidate_count_is_at_least_2": "include at least one pass and one fail candidate",
            "batch_goal": "avoid all-pass or all-fail batches unless candidate_count is 1",
            "pass_definition": "final response is compliant with the cited source_span and preceding state",
            "fail_definition": "final response contradicts the cited source_span or the required state transition",
        },
        "state_transition_consistency": [
            "Track session open/closed state, read-write vs read-only state, authentication state, lifecycle state, TryLimit/Tries state, and object/table state when relevant.",
            "Preceding records must make the final response logically reachable.",
            "Do not use an earlier error/success as the label target when records[-1].output is compliant.",
            "If a fail case is caused by an intermediate event, move the violating response to records[-1] instead of appending a later EndSession SUCCESS.",
        ],
        "raw_to_manifest_loader_compatibility": [
            "Return JSON object with top-level candidates list only.",
            "Each candidate must satisfy self_instruct.candidate.v1 fields: sample_id, instruction, records, label, label_target, target, primary_evidence, source, spec_grounding.",
            "records must be the full trajectory list; do not flatten records into separate samples.",
            "Do not place spec text, source_span, public labels, or judge commentary inside records or instruction.",
            "spec_grounding is audit metadata only; manifest/model input later uses stable JSON {'records': records}.",
        ],
        "hard_constraints": [
            "label must be pass or fail",
            "label_target must be final_response",
            "target.final_response_index must be len(records) - 1",
            "primary_evidence.record_index must be len(records) - 1",
            "spec_grounding must be a non-empty list",
            "every spec_grounding item must cite a supplied source_span from spec_rule_context",
            "do not append EndSession SUCCESS after a fail verdict step",
            "do not use an intermediate response as the primary label evidence",
            "do not copy public20 trajectories exactly",
            "do not include public labels, rule-engine text, archived verifier output, or uncited spec claims",
        ],
        "seed_profile_context": list(seed_contexts),
        "spec_rule_context": list(spec_rule_contexts),
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
                        "reason": "one concise final-response reason tied to cited source_span",
                    },
                    "spec_grounding": [
                        {
                            "rule_ref": "RULE NN from supplied spec_rule_context",
                            "source_path": "docs/legacy_spec_rules.md",
                            "source_span": "docs/legacy_spec_rules.md:start-end",
                            "spec_section": "SPEC value from supplied card",
                            "condition": "CONDITION value from supplied card",
                            "expected_status": "EXPECTED_STATUS value from supplied card",
                            "state_transition_notes": "short note explaining how preceding records satisfy or violate the cited condition",
                        }
                    ],
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
    spec_rule_cards: Sequence[Mapping[str, Any]],
    spec_rules_per_request: int,
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
    spec_rule_contexts = _select_spec_rule_contexts(spec_rule_cards, request_index, spec_rules_per_request)
    payload: Json = {
        "model": model,
        "messages": [
            {"role": "system", "content": _generation_system_prompt()},
            {"role": "user", "content": _generation_user_prompt(seed_contexts, spec_rule_contexts, candidates_per_request)},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "seed_profile_context": seed_contexts,
        "spec_rule_context": spec_rule_contexts,
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
        "source_spec_rule_refs": [str(context.get("rule_ref")) for context in spec_rule_contexts],
        "candidates_per_request": candidates_per_request,
        "payload_sha256": _sha256_json(payload),
        "payload": payload,
    }


def build_generation_requests(
    *,
    seeds: Sequence[Mapping[str, Any]],
    spec_rule_cards: Sequence[Mapping[str, Any]],
    request_count: int,
    seeds_per_request: int,
    spec_rules_per_request: int,
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
            spec_rule_cards=spec_rule_cards,
            spec_rules_per_request=spec_rules_per_request,
            candidates_per_request=candidates_per_request,
            model=model,
            created_at_kst=timestamp,
        )
        for index in range(request_count)
    ]


def build_metadata(
    seed_path: Path,
    spec_rules_path: Path,
    spec_rule_cards: Sequence[Mapping[str, Any]],
    requests: Sequence[Mapping[str, Any]],
    runner_report: Optional[Mapping[str, Any]] = None,
    runner_report_path: Optional[Path] = None,
) -> Json:
    executed_count = 0
    if isinstance(runner_report, Mapping) and isinstance(runner_report.get("executed_count"), int):
        executed_count = int(runner_report["executed_count"])
    metadata: Json = {
        "schema_version": GENERATION_METADATA_SCHEMA_VERSION,
        "seed_input": str(seed_path),
        "spec_rules_input": str(spec_rules_path),
        "spec_rule_count": len(spec_rule_cards),
        "request_count": len(requests),
        "execute": executed_count > 0,
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "request_ids": [request.get("request_id") for request in requests],
        "payload_sha256": {str(request.get("request_id")): request.get("payload_sha256") for request in requests},
        "source_spec_rule_refs": {
            str(request.get("request_id")): request.get("source_spec_rule_refs") for request in requests
        },
        "notes": [
            "dry-run only: no LLM/API call was made",
            "request payloads contain input-only seed profiles, not public20 labels",
            "request payloads contain spec rule cards with source spans from docs/legacy_spec_rules.md",
            "raw candidates without spec_grounding/source_span must be rejected before manifest creation",
            "raw LLM outputs must be parsed by tools/datagen/parse_self_instruct_outputs.py",
        ],
    }
    # Changed: summarize optional execution without embedding raw provider text or secrets in metadata.
    # Why: downstream audit needs to know whether API execution happened while raw output remains parser-owned.
    if runner_report is not None:
        metadata["execute_requested"] = True
        metadata["runner"] = {
            "schema_version": runner_report.get("schema_version"),
            "provider": runner_report.get("provider"),
            "provider_env_var": runner_report.get("provider_env_var"),
            "status": runner_report.get("status"),
            "request_count": runner_report.get("request_count"),
            "executed_count": runner_report.get("executed_count"),
            "skipped_count": runner_report.get("skipped_count"),
            "failed_count": runner_report.get("failed_count"),
            "output_path": runner_report.get("output_path"),
            "report_path": str(runner_report_path) if runner_report_path is not None else None,
        }
    return metadata


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dry-run Self-Instruct generation request payloads.")
    parser.add_argument("--seed-jsonl", required=True, type=Path, help="Input-only seed JSON/JSONL. Label-like fields are rejected.")
    parser.add_argument("--requests-output", required=True, type=Path, help="Output request payload JSONL.")
    parser.add_argument("--metadata-json", required=True, type=Path, help="Output request metadata JSON.")
    parser.add_argument("--spec-rules-md", type=Path, default=DEFAULT_SPEC_RULES_PATH, help="Spec rule markdown used as grounding source.")
    parser.add_argument("--request-count", type=int, default=1, help="Number of dry-run request payloads to build.")
    parser.add_argument("--seeds-per-request", type=int, default=8, help="Number of input-only seed profiles per request.")
    parser.add_argument("--spec-rules-per-request", type=int, default=8, help="Number of source-span spec rule cards per request.")
    parser.add_argument("--candidates-per-request", type=int, default=4, help="Requested candidates per external LLM call.")
    parser.add_argument("--model", default="external-llm", help="Model name recorded in the payload for an external runner.")
    parser.add_argument("--created-at-kst", default=None, help="Optional fixed KST timestamp for reproducible tests.")
    # Changed: expose explicit provider execution flags while keeping dry-run as the default.
    # Why: paid API calls must require --execute plus the matching provider API-key environment variable.
    parser.add_argument("--execute", action="store_true", help="Execute requests with an external provider when the provider API key env var is present.")
    parser.add_argument("--provider", choices=("openai", "gemini"), default="openai", help="Provider used only with --execute. Env vars: OPENAI_API_KEY or GEMINI_API_KEY.")
    parser.add_argument("--raw-output-jsonl", type=Path, default=None, help="Parser-compatible raw LLM output JSONL path for successful --execute calls.")
    parser.add_argument("--runner-report-json", type=Path, default=None, help="Runner report JSON path for --execute attempts and env-missing skips.")
    parser.add_argument("--request-timeout-seconds", type=int, default=120, help="HTTP timeout for each provider request when --execute is active.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        seeds = load_input_only_seeds(args.seed_jsonl)
        spec_rule_cards = load_spec_rule_cards(args.spec_rules_md)
        requests = build_generation_requests(
            seeds=seeds,
            spec_rule_cards=spec_rule_cards,
            request_count=args.request_count,
            seeds_per_request=args.seeds_per_request,
            spec_rules_per_request=args.spec_rules_per_request,
            candidates_per_request=args.candidates_per_request,
            model=args.model,
            created_at_kst=args.created_at_kst,
        )
        _write_jsonl(requests, args.requests_output)
        runner_report: Optional[Json] = None
        runner_report_path: Optional[Path] = None
        if args.execute:
            # Changed: perform env-gated external execution only after the dry-run request artifact is written.
            # Why: every raw response must retain the exact request provenance even if execution is skipped or partial.
            raw_output_path = args.raw_output_jsonl or args.requests_output.with_name("raw_outputs.jsonl")
            runner_report_path = args.runner_report_json or args.metadata_json.with_name("runner_report.json")
            runner_report = run_generation_requests(
                requests,
                provider=args.provider,
                output_path=raw_output_path,
                timeout_seconds=args.request_timeout_seconds,
                created_at_kst=args.created_at_kst,
            )
            runner_report_path.parent.mkdir(parents=True, exist_ok=True)
            runner_report_path.write_text(
                json.dumps(runner_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if runner_report.get("status") == "skipped_missing_env":
                print(
                    f"run_self_instruct_generation: skipped provider execution; missing {provider_env_var(args.provider)}",
                    file=sys.stderr,
                )
        args.metadata_json.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_json.write_text(
            json.dumps(
                build_metadata(
                    args.seed_jsonl,
                    args.spec_rules_md,
                    spec_rule_cards,
                    requests,
                    runner_report=runner_report,
                    runner_report_path=runner_report_path,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, SeedSchemaError, SelfInstructGenerationError, SelfInstructLLMRunnerError) as exc:
        print(f"run_self_instruct_generation: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
