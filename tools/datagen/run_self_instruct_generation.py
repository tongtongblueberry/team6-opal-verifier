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
from tools.datagen.self_instruct_candidate_schema import (  # noqa: E402
    FIXED_OPAL_VERIFIER_INSTRUCTION,
)
# Changed: connect the optional external provider runner behind --execute.
# Why: generation requests can now be executed only through env-gated provider code that writes raw parser input.
from tools.datagen.self_instruct_llm_runner import (  # noqa: E402
    SelfInstructLLMRunnerError,
    provider_env_var,
    run_generation_requests,
    run_generation_requests_with_hf_model,
)


Json = Dict[str, Any]
GENERATION_REQUEST_SCHEMA_VERSION = "self_instruct.generation_request.v1"
GENERATION_METADATA_SCHEMA_VERSION = "self_instruct.generation_metadata.v1"
INSTRUCTION_ARTIFACT_SCHEMA_VERSION = "self_instruct.machine_generated_instructions.dry_run.v1"
CLASSIFICATION_DETECTION_SCHEMA_VERSION = "self_instruct.is_clf_or_not.audited_noop.v1"
# Changed: bump the prompt contract for gen3.1 auth-skeleton and state-trace fixes.
# Why: gen3 raw rows reached the parser but repeatedly missed authenticated StartSession evidence and target-aligned final state.
PROMPT_CONTRACT_VERSION = "opal_final_response_spec_grounded_output_first.v3"
DEFAULT_SPEC_RULES_PATH = ROOT / "docs" / "legacy_spec_rules.md"
TARGET_SCHEDULE_ALLOWED_KEYS = frozenset(
    {
        "target_label",
        "target_record_count",
        "target_length_bin",
        "target_final_method",
        "target_final_status",
        "allowed_source_rule_refs",
        "requires_auth_session",
        "required_context_domains",
    }
)
TARGET_SCHEDULE_FORBIDDEN_KEYS = frozenset(
    {
        "answer",
        "expected_answer",
        "expected_label",
        "expected_output",
        "final_response",
        "gold",
        "gold_label",
        "gold_output",
        "label",
        "output",
        "public_answer",
        "public_label",
        "public_output",
        "target_final_response",
    }
)
TARGET_LENGTH_BINS = frozenset({"1-32", "33-64", "65-128", "129-256", "257-512"})
RULE_REF_PATTERN = re.compile(r"^RULE \d{2}$")
PROMPT_MODES = ("full", "compact")
OFFICIAL_SELF_INSTRUCT_SOURCE = {
    "paper": "Wang et al. 2023 Self-Instruct",
    "official_code": "https://github.com/yizhongw/self-instruct",
    "license": "Apache-2.0",
}
OFFICIAL_PIPELINE_STAGE_MAP = {
    "instruction_generation": "machine_generated_instructions.jsonl",
    "classification_detection": "is_clf_or_not_<engine>_<template>.jsonl",
    "instance_generation": "machine_generated_instances.jsonl",
    "candidate_preparation": "prepare_for_finetuning.py outputs",
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


def _record_method(record: Any) -> str:
    input_payload = record.get("input") if isinstance(record, Mapping) else None
    method = input_payload.get("method") if isinstance(input_payload, Mapping) else None
    if isinstance(method, Mapping):
        return str(method.get("name") or "").strip()
    if isinstance(method, str):
        return method.strip()
    command = input_payload.get("command") if isinstance(input_payload, Mapping) else None
    return command.strip() if isinstance(command, str) else ""


def _delexicalized_value(field_name: str, value: Any) -> Any:
    # Changed: expose public20 input-only auth shapes without leaking exact public20 values.
    # Why: the generator needs concrete authenticated-session structure, but exact public trajectories must not be copied.
    normalized_name = field_name.lower()
    if isinstance(value, Mapping):
        return {str(key): _delexicalized_value(str(key), item) for key, item in value.items() if item is not None}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_delexicalized_value(field_name, item) for item in value[:4] if item is not None]
    if value is None:
        return None
    if normalized_name == "hostchallenge":
        return "MUTATE_HEX_HOST_CHALLENGE"
    if normalized_name == "hostsigningauthority":
        return "MUTATE_AUTHORITY_UID_OR_SID"
    if normalized_name == "spsessionid":
        return "MUTATE_UNIQUE_8_HEX_SPSESSIONID"
    if normalized_name == "hostsessionid":
        return "00000001"
    if normalized_name == "spid":
        return "MUTATE_ADMINSP_OR_LOCKINGSP_UID"
    if normalized_name == "name" and isinstance(value, str):
        return value
    if normalized_name in {"uid", "invoking_id"}:
        return "MUTATE_PUBLIC_LIKE_UID"
    if isinstance(value, str):
        if len(value) >= 8 or any(ch.isdigit() for ch in value):
            return f"MUTATE_{field_name.upper()}_VALUE"
        return value
    return value


def _delexicalized_mapping(value: Any) -> Json:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _delexicalized_value(str(key), item)
        for key, item in value.items()
        if item is not None and str(key) != "type"
    }


def _authenticated_start_session_skeletons(seed: Mapping[str, Any], *, limit: int = 2) -> List[Json]:
    # Changed: derive prompt-only auth skeletons from public20 input records.
    # Why: gen3 rejected all parsed candidates for missing HostChallenge/HostSigningAuthority, while public20 contains the correct shape.
    records = seed.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
        return []
    skeletons: List[Json] = []
    for record in records:
        if _record_method(record) != "StartSession" or not isinstance(record, Mapping):
            continue
        input_payload = record.get("input")
        output_payload = record.get("output")
        if not isinstance(input_payload, Mapping) or not isinstance(output_payload, Mapping):
            continue
        method = input_payload.get("method")
        if not isinstance(method, Mapping):
            continue
        args = method.get("args")
        if not isinstance(args, Mapping):
            continue
        optional = args.get("optional")
        if not isinstance(optional, Mapping):
            optional = {}
        if "HostChallenge" not in optional and "HostSigningAuthority" not in optional:
            continue
        required = args.get("required") if isinstance(args.get("required"), Mapping) else {}
        skeletons.append(
            {
                "source": "public20_input_only_delexicalized_auth_skeleton",
                "source_seed_sample_id": seed.get("sample_id"),
                "copy_policy": "Use this as a method/field skeleton only; mutate every concrete id, challenge, authority, session id, UID, and table value.",
                "placement": "If target requires an authenticated session and final method is not StartSession, place this before records[-1].",
                "input": {
                    "invoking_id": _delexicalized_mapping(input_payload.get("invoking_id")),
                    "method": {
                        "name": "StartSession",
                        "args": {
                            "required": _delexicalized_mapping(required),
                            "optional": _delexicalized_mapping(optional),
                        },
                    },
                    "status_codes": ["SUCCESS"],
                },
                "output": {
                    "status_codes": ["SUCCESS"],
                    "method": {
                        "name": "SyncSession",
                        "args": {
                            "required": {
                                "HostSessionID": "00000001",
                                "SPSessionID": "MUTATE_UNIQUE_8_HEX_SPSESSIONID",
                            },
                            "optional": {},
                        },
                    },
                    "return_values": {
                        "required": {
                            "HostSessionID": "00000001",
                            "SPSessionID": "MUTATE_UNIQUE_8_HEX_SPSESSIONID",
                        },
                        "optional": {},
                    },
                },
                "must_keep": [
                    "method.args.required and method.args.optional are objects",
                    "method.args.optional.HostChallenge is concrete and non-empty",
                    "method.args.optional.HostSigningAuthority is concrete and non-empty",
                    "later records use the returned HostSessionID/SPSessionID consistently",
                ],
            }
        )
        if len(skeletons) >= limit:
            break
    return skeletons


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
        "auth_session_skeletons": _authenticated_start_session_skeletons(seed),
    }


# Changed: validate request-only target schedules before they can influence prompt construction.
# Why: target quotas may guide external generation, but public labels, gold outputs, and malformed rule refs must never enter the request.
def _target_record_count_bin(record_count: int) -> str:
    if record_count <= 32:
        return "1-32"
    if record_count <= 64:
        return "33-64"
    if record_count <= 128:
        return "65-128"
    if record_count <= 256:
        return "129-256"
    return "257-512"


def _ensure_target_schedule_rows(payload: Any) -> List[Mapping[str, Any]]:
    if isinstance(payload, list):
        raw_targets = payload
    elif isinstance(payload, Mapping):
        forbidden_top_level = sorted(key for key in payload.keys() if str(key) in TARGET_SCHEDULE_FORBIDDEN_KEYS)
        if forbidden_top_level:
            raise SelfInstructGenerationError(f"target_schedule_forbidden_fields:{','.join(forbidden_top_level)}")
        unknown_top_level = sorted(str(key) for key in payload.keys() if str(key) != "targets")
        if unknown_top_level:
            raise SelfInstructGenerationError(f"target_schedule_unknown_top_level_fields:{','.join(unknown_top_level)}")
        raw_targets = payload.get("targets")
        if not isinstance(raw_targets, list):
            raise SelfInstructGenerationError("target_schedule_targets_not_array")
    else:
        raise SelfInstructGenerationError("target_schedule_root_not_array_or_object")

    if len(raw_targets) == 0:
        raise SelfInstructGenerationError("target_schedule_empty")
    rows: List[Mapping[str, Any]] = []
    for index, target in enumerate(raw_targets):
        if not isinstance(target, Mapping):
            raise SelfInstructGenerationError(f"target_schedule_{index}_not_object")
        rows.append(target)
    return rows


def _normalize_string_list(value: Any, *, target_index: int, field_name: str) -> List[str]:
    # Changed: validate request-only coverage hints as explicit string lists.
    # Why: gen3 target schedules need auditable domain coverage requirements without smuggling labels or outputs.
    if not isinstance(value, list):
        raise SelfInstructGenerationError(f"target_schedule_{target_index}_{field_name}_not_list")
    if len(value) == 0:
        raise SelfInstructGenerationError(f"target_schedule_{target_index}_{field_name}_empty")
    normalized: List[str] = []
    for item_index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SelfInstructGenerationError(f"target_schedule_{target_index}_{field_name}_{item_index}_not_string")
        stripped = item.strip()
        if stripped in normalized:
            raise SelfInstructGenerationError(f"target_schedule_{target_index}_{field_name}_{item_index}_duplicate:{stripped}")
        normalized.append(stripped)
    return normalized


def _normalize_allowed_source_rule_refs(value: Any, *, target_index: int, valid_rule_refs: Sequence[str]) -> List[str]:
    if not isinstance(value, list):
        raise SelfInstructGenerationError(f"target_schedule_{target_index}_allowed_source_rule_refs_not_list")
    if len(value) == 0:
        raise SelfInstructGenerationError(f"target_schedule_{target_index}_allowed_source_rule_refs_empty")

    valid_refs = set(valid_rule_refs)
    normalized: List[str] = []
    for ref_index, ref in enumerate(value):
        if not isinstance(ref, str) or not ref.strip():
            raise SelfInstructGenerationError(
                f"target_schedule_{target_index}_allowed_source_rule_refs_{ref_index}_not_string"
            )
        rule_ref = ref.strip()
        if RULE_REF_PATTERN.fullmatch(rule_ref) is None:
            raise SelfInstructGenerationError(
                f"target_schedule_{target_index}_allowed_source_rule_refs_{ref_index}_malformed:{rule_ref}"
            )
        if rule_ref not in valid_refs:
            raise SelfInstructGenerationError(
                f"target_schedule_{target_index}_allowed_source_rule_refs_{ref_index}_unknown:{rule_ref}"
            )
        if rule_ref in normalized:
            raise SelfInstructGenerationError(
                f"target_schedule_{target_index}_allowed_source_rule_refs_{ref_index}_duplicate:{rule_ref}"
            )
        normalized.append(rule_ref)
    return normalized


def normalize_target_schedule(payload: Any, *, valid_rule_refs: Sequence[str]) -> List[Json]:
    rows = _ensure_target_schedule_rows(payload)
    normalized: List[Json] = []
    for index, target in enumerate(rows):
        forbidden_fields = sorted(key for key in target.keys() if str(key) in TARGET_SCHEDULE_FORBIDDEN_KEYS)
        if forbidden_fields:
            raise SelfInstructGenerationError(f"target_schedule_{index}_forbidden_fields:{','.join(forbidden_fields)}")
        unknown_fields = sorted(str(key) for key in target.keys() if str(key) not in TARGET_SCHEDULE_ALLOWED_KEYS)
        if unknown_fields:
            raise SelfInstructGenerationError(f"target_schedule_{index}_unknown_fields:{','.join(unknown_fields)}")

        target_label = target.get("target_label")
        if not isinstance(target_label, str) or target_label.strip().lower() not in {"pass", "fail"}:
            raise SelfInstructGenerationError(f"target_schedule_{index}_target_label_invalid")

        target_record_count = target.get("target_record_count")
        if isinstance(target_record_count, bool) or not isinstance(target_record_count, int) or target_record_count <= 0:
            raise SelfInstructGenerationError(f"target_schedule_{index}_target_record_count_not_positive_int")

        row: Json = {
            "target_index": index,
            "target_label": target_label.strip().lower(),
            "target_record_count": target_record_count,
        }
        for optional_key in ("target_final_method", "target_final_status"):
            optional_value = target.get(optional_key)
            if optional_value is None:
                continue
            if not isinstance(optional_value, str) or not optional_value.strip():
                raise SelfInstructGenerationError(f"target_schedule_{index}_{optional_key}_invalid")
            row[optional_key] = optional_value.strip()

        target_length_bin = target.get("target_length_bin")
        if target_length_bin is not None:
            if not isinstance(target_length_bin, str) or target_length_bin.strip() not in TARGET_LENGTH_BINS:
                raise SelfInstructGenerationError(f"target_schedule_{index}_target_length_bin_invalid")
            normalized_bin = target_length_bin.strip()
            expected_bin = _target_record_count_bin(target_record_count)
            if normalized_bin != expected_bin:
                raise SelfInstructGenerationError(
                    f"target_schedule_{index}_target_length_bin_mismatch:{normalized_bin}!={expected_bin}"
                )
            row["target_length_bin"] = normalized_bin

        if "allowed_source_rule_refs" in target:
            row["allowed_source_rule_refs"] = _normalize_allowed_source_rule_refs(
                target["allowed_source_rule_refs"],
                target_index=index,
                valid_rule_refs=valid_rule_refs,
            )
        if "required_context_domains" in target:
            row["required_context_domains"] = _normalize_string_list(
                target["required_context_domains"],
                target_index=index,
                field_name="required_context_domains",
            )
        requires_auth_session = target.get("requires_auth_session")
        if requires_auth_session is not None:
            if not isinstance(requires_auth_session, bool):
                raise SelfInstructGenerationError(f"target_schedule_{index}_requires_auth_session_not_bool")
            row["requires_auth_session"] = requires_auth_session
        normalized.append(row)
    return normalized


def load_target_schedule(path: Path, spec_rule_cards: Sequence[Mapping[str, Any]]) -> List[Json]:
    valid_rule_refs = [str(card.get("rule_ref")) for card in spec_rule_cards if isinstance(card.get("rule_ref"), str)]
    return normalize_target_schedule(json.loads(path.read_text(encoding="utf-8")), valid_rule_refs=valid_rule_refs)


def _target_schedule_summary(target_schedule: Sequence[Mapping[str, Any]]) -> Json:
    label_counts: Json = {}
    record_count_counts: Json = {}
    for target in target_schedule:
        label = str(target.get("target_label"))
        label_counts[label] = label_counts.get(label, 0) + 1
        record_count = str(target.get("target_record_count"))
        record_count_counts[record_count] = record_count_counts.get(record_count, 0) + 1
    auth_required_count = sum(1 for target in target_schedule if target.get("requires_auth_session") is True)
    return {
        "target_count": len(target_schedule),
        "label_counts": label_counts,
        "record_count_counts": record_count_counts,
        "requires_auth_session_count": auth_required_count,
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
        # Changed: include exact rule-book text in each source-span card.
        # Why: generation must be grounded in docs/legacy_spec_rules.md body text, not only copied CONDITION/EXPECTED_STATUS summaries.
        current["source_text"] = "\n".join(f"{line_no}: {lines[line_no - 1]}" for line_no in range(start_line, end_line + 1))
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
    if not any(context.get("auth_session_skeletons") for context in selected):
        for offset in range(len(seeds)):
            fallback_seed = seeds[(request_index + offset) % len(seeds)]
            fallback = _authenticated_start_session_skeletons(fallback_seed, limit=1)
            if fallback:
                for context in selected:
                    context["auth_session_skeletons"] = fallback
                    context["auth_session_skeleton_source"] = "fallback_public20_input_only_delexicalized"
                break
    return selected


# Changed: add any scheduled rule refs to the request-local source-span context.
# Why: allowed_source_rule_refs must stay grounded in loaded spec cards instead of becoming uncited prompt hints.
def _include_target_rule_contexts(
    selected_contexts: Sequence[Mapping[str, Any]],
    spec_rule_cards: Sequence[Mapping[str, Any]],
    candidate_targets: Optional[Sequence[Mapping[str, Any]]],
) -> List[Json]:
    contexts = [dict(context) for context in selected_contexts]
    if not candidate_targets:
        return contexts

    by_ref = {str(card.get("rule_ref")): card for card in spec_rule_cards if isinstance(card.get("rule_ref"), str)}
    included = {str(context.get("rule_ref")) for context in contexts}
    for target in candidate_targets:
        refs = target.get("allowed_source_rule_refs")
        if not isinstance(refs, Sequence) or isinstance(refs, (bytes, bytearray, str)):
            continue
        for rule_ref in refs:
            ref = str(rule_ref)
            if ref in included:
                continue
            card = by_ref.get(ref)
            if card is None:
                raise SelfInstructGenerationError(f"target_schedule_allowed_rule_not_loaded:{ref}")
            contexts.append(dict(card))
            included.add(ref)
    return contexts


# Changed: materialize official-stage dry-run instruction artifacts separately from instance requests.
# Why: a fixed Opal verification instruction must not be mislabeled as official Self-Instruct machine generation output.
def build_instruction_artifact(
    *,
    request_index: int,
    seed_contexts: Sequence[Mapping[str, Any]],
    spec_rule_contexts: Sequence[Mapping[str, Any]],
    created_at_kst: str,
) -> Json:
    instruction_id = f"self-instruct-instruction-{request_index:05d}"
    return {
        "schema_version": INSTRUCTION_ARTIFACT_SCHEMA_VERSION,
        "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["instruction_generation"],
        "official_stage": "instruction_generation",
        "artifact_role": "dry_run_request_artifact",
        "instruction_id": instruction_id,
        "instruction": FIXED_OPAL_VERIFIER_INSTRUCTION,
        "created_at_kst": created_at_kst,
        "machine_generated_by_llm": False,
        "not_accepted_synthetic": True,
        "status": "dry_run_request_only_not_machine_generated_instruction",
        "source_seed_sample_ids": [str(context.get("sample_id")) for context in seed_contexts],
        "source_spec_rule_refs": [str(context.get("rule_ref")) for context in spec_rule_contexts],
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
    }


# Changed: write the domain classification decision as an audited no-op artifact.
# Why: official Self-Instruct has a classification detection JSONL stage even though this domain is always pass/fail classification.
def build_classification_detection_artifact(
    *,
    request_index: int,
    instruction_artifact: Mapping[str, Any],
    created_at_kst: str,
) -> Json:
    instruction_id = str(instruction_artifact["instruction_id"])
    return {
        "schema_version": CLASSIFICATION_DETECTION_SCHEMA_VERSION,
        "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["classification_detection"],
        "official_stage": "classification_detection",
        "artifact_role": "audited_noop_artifact",
        "classification_detection_id": f"self-instruct-clf-{request_index:05d}",
        "instruction_id": instruction_id,
        "instruction": instruction_artifact["instruction"],
        "is_classification": True,
        "audited_noop": True,
        "not_accepted_synthetic": True,
        "created_at_kst": created_at_kst,
        "rationale": "The Opal verifier target is a closed pass/fail classification task, so no LLM classification detector is called.",
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
    }


def _generation_system_prompt() -> str:
    return (
        "You are generating spec-grounded Self-Instruct classification instances "
        "for an Opal final-pair verifier. Follow output-first classification "
        "generation: the label is only about the last command-response pair "
        "(cN, rN), after reading the full preceding trajectory as state context. "
        "Use only the supplied spec_rule_context entries and their source_text from "
        "docs/legacy_spec_rules.md as normative grounding. Do not use public labels, "
        "rule-engine labels, archived verifier outputs, or any unstated Opal facts."
    )


def _generation_user_prompt(
    seed_contexts: Sequence[Mapping[str, Any]],
    spec_rule_contexts: Sequence[Mapping[str, Any]],
    instruction_artifact: Mapping[str, Any],
    classification_detection_artifact: Mapping[str, Any],
    candidates_per_request: int,
    candidate_targets: Optional[Sequence[Mapping[str, Any]]] = None,
    request_index: Optional[int] = None,
    request_id: Optional[str] = None,
) -> str:
    # Changed: bind full prompts to deterministic request-local sample ids and record-count quotas.
    # Why: local Qwen full prompts produced better multi-record trajectories, but must not reuse public20 ids.
    request_tag = request_id or "self-instruct-gen-unknown"
    indexed_targets: List[Json] = []
    if candidate_targets is not None:
        for index, target in enumerate(candidate_targets):
            row = dict(target)
            row["candidate_index"] = index
            row["required_sample_id"] = f"{request_tag}-cand-{index:02d}"
            row["required_record_count"] = row.get("target_record_count")
            indexed_targets.append(row)

    prompt_spec = {
        "task": "Create new Opal command-response trajectory verification candidates whose label judges only the final pair (cN, rN).",
        "official_protocol": "Self-Instruct classification output-first instance generation.",
        "official_pipeline_mapping": OFFICIAL_PIPELINE_STAGE_MAP,
        "request_id": request_tag,
        "request_index": request_index,
        "source_instruction_artifact": dict(instruction_artifact),
        "classification_detection_artifact": dict(classification_detection_artifact),
        "grounding_policy": {
            "source": "docs/legacy_spec_rules.md",
            "allowed_normative_source": "Only cite and use entries in spec_rule_context, especially source_text copied from docs/legacy_spec_rules.md.",
            "required_per_candidate": "Each candidate must include spec_grounding with rule_ref, source_path, source_span, condition, expected_status, and state_transition_notes copied or derived only from a supplied card.",
            "no_ungrounded_text": "Do not create candidates whose label rationale cannot be traced to a supplied source_span.",
            "not_runtime_rule_engine": "These source spans are offline generation/audit provenance and must not be embedded in solver/runtime prompts.",
        },
        "final_pair_classification_contract": {
            "trajectory": "records encode [(c0,r0), ..., (cN,rN)] in order.",
            "decision_target": "Read all records to track state, then judge only whether rN is the proper response for cN under that final state.",
            "pass": "label=pass iff the final response rN is compliant with the cited rule-book source_text and the preceding state.",
            "fail": "label=fail iff the final response rN contradicts the cited rule-book source_text or is impossible under the preceding state.",
            "forbidden": "Do not label a candidate from any intermediate pair (ci,ri) for i<N; move the violating pair to records[-1] instead.",
        },
        "public20_auth_skeleton_policy": {
            "source": "seed_profile_context[*].auth_session_skeletons",
            "allowed_use": "Use these input-only delexicalized skeletons to learn the authenticated StartSession field layout only.",
            "forbidden_use": "Do not copy exact public20 values, sample ids, full trajectories, labels, or public row order.",
            "mutation_required": "Every UID, SPID, SPSessionID, HostChallenge, HostSigningAuthority, PIN/key/table value must be changed to a new concrete public-like value.",
            "auth_required_targets": "When requires_auth_session is true, at least one StartSession input must contain method.args.optional.HostChallenge and method.args.optional.HostSigningAuthority.",
            "syncsession_status_shape": "StartSession success should use output.status_codes=[\"SUCCESS\"] and may use output.method.name=\"SyncSession\"; do not put \"SUCCESS (SYNCSESSION)\" inside status_codes.",
        },
        "output_first_order": [
            "choose target_label as pass or fail",
            "choose the target final response method/status/return value shape",
            "choose one or more supplied spec_rule_context cards that entail or refute that final response",
            "construct preceding records that provide only needed session/auth/object state",
            "before emitting JSON, trace session/auth/object state against the cited rule-book source_text and the candidate target schedule",
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
            "For every candidate, internally build a state table with rows: record_index, method, input session id, output session id, authenticated authority, relevant domain/object, cited rule, expected final status, actual final status.",
            "Then write the result of that state table into spec_grounding[*].state_transition_notes and primary_evidence.reason in concise text; do not add a separate rule engine output.",
            "Track session open/closed state, read-write vs read-only state, authentication state, lifecycle state, TryLimit/Tries state, and object/table state when relevant.",
            "Preceding records must make the final response logically reachable.",
            "Model authenticated Opal sessions with StartSession method args optional.HostChallenge and optional.HostSigningAuthority; do not use a separate Authenticate method as a substitute for StartSession authentication.",
            "When StartSession returns a HostSessionID or SPSessionID, subsequent records in the same session must use the returned concrete id consistently.",
            "Do not use placeholder ids such as H0001, H0002, H-test, SP001, Session1, or a single repeated SPSessionID across unrelated candidates; use public-like concrete hex ids such as 00000001 and varied 8-hex SPSessionID values.",
            "For Locking, MBRControl, LockingInfo, Authority, C_PIN, SP, or K_AES_256 scenarios, include those domains in invoking_id.name or concrete UIDs/arguments so the state is auditable.",
            "Do not use an earlier error/success as the label target when records[-1].output is compliant.",
            "If a fail case is caused by an intermediate event, move the violating response to records[-1] instead of appending a later EndSession SUCCESS.",
        ],
        "raw_to_manifest_loader_compatibility": [
            "Return JSON object with top-level candidates list only.",
            "Do not wrap the JSON in markdown fences or explanatory text.",
            "Return exactly candidate_count candidates; if candidate_count is 1, return exactly one candidate.",
            "Each candidate must satisfy self_instruct.candidate.v1 fields: sample_id, source_instruction_id, instruction, records, label, label_target, target, primary_evidence, source, spec_grounding.",
            f"instruction must exactly equal {json.dumps(FIXED_OPAL_VERIFIER_INSTRUCTION)}.",
            "records must be the full trajectory list; do not flatten records into separate samples.",
            "Each record must be an object with input and output objects; record.input must not be empty.",
            "Do not emit JSON null anywhere under record.input; use concrete UID/status/argument values or omit optional fields.",
            "For Opal method rows, record.input.method must be an object with a non-empty name string; do not put the method only in record.output.",
            "For Opal method rows, record.input.method.args must be an object with required and optional objects; do not emit bare args: {}.",
            "For StartSession rows, method.args.required must include HostSessionID, SPID, and Write; authenticated StartSession rows must also include optional.HostChallenge and optional.HostSigningAuthority.",
            "For Opal method rows with invoking_id, record.input.invoking_id.uid must be a non-empty UID string, not null.",
            "When a target requires an authenticated session, at least one StartSession record must contain method.args.optional.HostChallenge and method.args.optional.HostSigningAuthority with concrete non-empty values.",
            "Do not use placeholder HostSessionID or SPSessionID strings: forbidden examples include H0001, H0002, H0003, H-test, SP001, Session1, and repeated 000065ab.",
            "For command rows, record.input.command must be a non-empty string; do not leave record.input empty.",
            "Use output.status_codes as a list of one or more status strings for Opal statuses, not output.status.",
            "Do not place spec text, source_span, public labels, or judge commentary inside records or instruction.",
            "spec_grounding is audit metadata only; manifest/model input later uses stable JSON {'records': records}.",
        ],
        "hard_constraints": [
            "source_instruction_id must equal the supplied source_instruction_artifact.instruction_id",
            f"instruction must equal the fixed_instruction value exactly: {FIXED_OPAL_VERIFIER_INSTRUCTION}",
            "generation_provenance.classification_detection_id must equal the supplied classification_detection_artifact.classification_detection_id",
            "label must be pass or fail",
            "label_target must be final_response",
            "target.final_response_index must be len(records) - 1",
            "For one record, target.final_response_index and primary_evidence.record_index must be 0; for two records they must be 1.",
            "target.final_method must equal records[-1].input.method.name or records[-1].input.command",
            "The label must answer the fixed instruction: judge only final pair (cN, rN) after reading the full trajectory.",
            "primary_evidence.record_index must be len(records) - 1",
            "spec_grounding must be a non-empty list",
            "every spec_grounding item must cite a supplied source_span from spec_rule_context",
            "do not append EndSession SUCCESS after a fail verdict step",
            "do not use an intermediate response as the primary label evidence",
            "do not copy public20 trajectories exactly",
            "sample_id must be newly generated and must not reuse seed sample ids such as tc1, tc2, or public20 ids",
            "if candidate_target_schedule is supplied, sample_id must exactly equal candidate_targets[i].required_sample_id",
            "if candidate_target_schedule is supplied, len(records) must exactly equal candidate_targets[i].required_record_count",
            "if required_record_count is greater than 1, create preceding context records before the final response; do not collapse the trajectory to one record",
            "if required_context_domains is supplied, records must contain auditable invoking_id.name, invoking_id.uid, method args, or return values for every requested domain.",
            "do not include public labels, rule-engine text, archived verifier output, or uncited spec claims",
        ],
        "seed_profile_context": list(seed_contexts),
        "spec_rule_context": list(spec_rule_contexts),
        "required_response_json": {
            "candidates": [
                {
                    "sample_id": f"{request_tag}-cand-00",
                    "source_instruction_id": instruction_artifact["instruction_id"],
                    "instruction": FIXED_OPAL_VERIFIER_INSTRUCTION,
                    "records": [
                        {
                            "index": 0,
                            "input": {
                                "method": {
                                    "name": "StartSession",
                                    "args": {
                                        "required": {"HostSessionID": 1, "SPID": "0000020500000001", "Write": 1},
                                        "optional": {
                                            "HostChallenge": "a1b2c3d4e5f60708",
                                            "HostSigningAuthority": "0000000900000001",
                                        },
                                    },
                                },
                                "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager UID"},
                                "status_codes": ["SUCCESS"],
                            },
                            "output": {
                                "status_codes": ["SUCCESS"],
                                "method": {"name": "SyncSession"},
                                "return_values": {
                                    "required": {"HostSessionID": "00000001", "SPSessionID": "a3f09c12"},
                                    "optional": {},
                                },
                            },
                        },
                        {
                            "index": "integer final step number len(records)-1",
                            "input": {
                                "method": {
                                    "name": "target_final_method",
                                    "args": {"required": {"HostSessionID": "00000001"}, "optional": {}},
                                },
                                "invoking_id": {"uid": "public-like UID for target domain", "name": "required target domain"},
                                "status_codes": ["target input status if applicable"],
                            },
                            "output": {
                                "status_codes": ["target_final_status"],
                                "return_values": [],
                            },
                        }
                    ],
                    "label": "pass|fail",
                    "label_target": "final_response",
                    "target": {
                        "final_response_index": "integer len(records)-1",
                        "final_response": "exact output object from records[-1]",
                        "final_method": "optional final method name",
                    },
                    "primary_evidence": {
                        "record_index": "same integer len(records)-1",
                        "reason": "one concise final-response reason tied to cited source_span after tracing session/auth/object state",
                    },
                    "spec_grounding": [
                        {
                            "rule_ref": "RULE NN from supplied spec_rule_context",
                            "source_path": "docs/legacy_spec_rules.md",
                            "source_span": "docs/legacy_spec_rules.md:start-end",
                            "spec_section": "SPEC value from supplied card",
                            "condition": "CONDITION value from supplied card",
                            "expected_status": "EXPECTED_STATUS value from supplied card",
                            "state_transition_notes": "state trace summary: authenticated authority, session id continuity, required domains, final method/status, and why the final response satisfies or violates the cited condition",
                        }
                    ],
                    "generation_provenance": {
                        "official_instance_artifact": OFFICIAL_PIPELINE_STAGE_MAP["instance_generation"],
                        "source_instruction_id": instruction_artifact["instruction_id"],
                        "classification_detection_id": classification_detection_artifact["classification_detection_id"],
                    },
                    "source": "self_instruct_output_first",
                }
            ]
        },
        "candidate_count": candidates_per_request,
    }
    # Changed: surface bounded per-candidate targets inside the prompt only when explicitly scheduled.
    # Why: the external generator must match request-order quotas without receiving public labels or gold outputs.
    if candidate_targets is not None:
        prompt_spec["candidate_target_schedule"] = {
            "assignment_policy": "candidate_targets are zero-based and assigned to candidates in request order.",
            "candidate_targets": indexed_targets,
            "matching_requirements": [
                "Candidate at index i must use candidate_targets[i].target_label as its label.",
                "Candidate at index i must set len(records) equal to candidate_targets[i].target_record_count.",
                "Candidate at index i must set sample_id exactly equal to candidate_targets[i].required_sample_id.",
                "If target_length_bin is present, it must match the generated record count.",
                "If target_final_method is present, records[-1].input method and target.final_method must match it.",
                "If target_final_status is present, records[-1].output status and target.final_response status must match it.",
                "If requires_auth_session is true, include a StartSession record with optional.HostChallenge and optional.HostSigningAuthority; if the final method is not StartSession, place this authenticated StartSession before the final record.",
                "If requires_auth_session is true, do not satisfy it with an Authenticate method; the authenticated session signal must be StartSession optional args.",
                "If allowed_source_rule_refs is present, every spec_grounding.rule_ref for that candidate must be one of those refs.",
                "If required_context_domains is present, include auditable invoking_id.name/uid, method args, or return values for every listed domain.",
                "Before finalizing, compare target_label, target_record_count, target_final_method, target_final_status, allowed_source_rule_refs, requires_auth_session, and required_context_domains against the candidate JSON.",
                "Targets are request-only quotas, not public labels, gold outputs, or a substitute for source-span grounding.",
                "Even with assigned targets, the label must be justified only by records[-1].output and supplied spec_rule_context source spans.",
            ],
        }
    return json.dumps(prompt_spec, ensure_ascii=False, indent=2, sort_keys=True)


def _generation_user_prompt_compact(
    seed_contexts: Sequence[Mapping[str, Any]],
    spec_rule_contexts: Sequence[Mapping[str, Any]],
    instruction_artifact: Mapping[str, Any],
    classification_detection_artifact: Mapping[str, Any],
    candidates_per_request: int,
    candidate_targets: Optional[Sequence[Mapping[str, Any]]] = None,
    request_index: Optional[int] = None,
    request_id: Optional[str] = None,
) -> str:
    # Changed: add a compact local-model prompt for high-throughput cached Qwen generation.
    # Why: server GPU utilization was high but long prompts/outputs made 200 accepted rows unnecessarily slow and OOM-sensitive.
    request_tag = request_id or "self-instruct-gen-unknown"
    indexed_targets: List[Json] = []
    if candidate_targets is not None:
        for index, target in enumerate(candidate_targets):
            row = dict(target)
            row["candidate_index"] = index
            row["required_sample_id"] = f"{request_tag}-cand-{index:02d}"
            row["required_record_count"] = row.get("target_record_count")
            indexed_targets.append(row)

    prompt_spec: Json = {
        "task": "Generate new Opal final-pair verifier Self-Instruct candidates. Read the full trajectory, then label only the final pair (cN,rN).",
        "output": "JSON only: {\"candidates\":[...]} with exactly candidate_count items. No markdown.",
        "candidate_count": candidates_per_request,
        "request_id": request_tag,
        "request_index": request_index,
        "required_fields": [
            "sample_id",
            "source_instruction_id",
            "instruction",
            "records",
            "label",
            "label_target",
            "target",
            "primary_evidence",
            "spec_grounding",
            "generation_provenance",
            "source",
        ],
        "hard_rules": [
            "Use only supplied spec_rule_context as normative source.",
            "label is pass or fail and must target records[-1].output only; records[-1] is the final pair (cN,rN).",
            "Read all prior records only as state context; never label an intermediate pair.",
            "records is a non-empty list; every record has input and output objects.",
            "Do not copy schema_example values. The schema_example shows shape only.",
            "candidate.instruction must exactly equal fixed_instruction.",
            "Every candidate sample_id must equal its candidate_target_schedule.required_sample_id when a schedule is supplied.",
            "Every candidate len(records) must equal candidate_target_schedule.required_record_count when a schedule is supplied.",
            "For required_record_count > 1, create preceding context records before the final response. Do not collapse to one record.",
            "Use different method/status trajectories across candidates. Do not repeat the same records JSON.",
            "Method record input uses {\"method\":{\"name\":METHOD,\"args\":{\"required\":{...},\"optional\":{...}}},\"invoking_id\":{\"uid\":\"non-empty UID string\"},\"status_codes\":[STATUS]}.",
            "Authenticated Opal sessions are represented by StartSession method.args.optional.HostChallenge and HostSigningAuthority, not by a separate Authenticate method.",
            "Use public-like concrete ids: HostSessionID such as 00000001 or 1; varied 8-hex SPSessionID values. Never use H0001/H0002/H-test/SP001/Session1 or one repeated SPSessionID.",
            "If target requires Locking, MBRControl, LockingInfo, Authority, C_PIN, SP, or K_AES_256 context, include that domain in invoking_id.name/uid or method args.",
            "Do not emit JSON null under record.input, and do not emit bare method args: {}.",
            "Output statuses use {\"status_codes\":[STATUS],\"return_values\":[]}.",
            "target.final_response_index and primary_evidence.record_index equal len(records)-1.",
            "target.final_response equals records[-1].output exactly.",
            "target.final_method equals records[-1].input.method.name.",
            "source_instruction_id equals source_instruction_artifact.instruction_id.",
            "generation_provenance.classification_detection_id equals classification_detection_artifact.classification_detection_id.",
            "Do not reuse public sample ids tc1..tc20.",
        ],
        "fixed_instruction": FIXED_OPAL_VERIFIER_INSTRUCTION,
        "source_instruction_artifact": {
            "instruction_id": instruction_artifact["instruction_id"],
        },
        "classification_detection_artifact": {
            "classification_detection_id": classification_detection_artifact["classification_detection_id"],
        },
        "seed_profile_context": list(seed_contexts),
        "spec_rule_context": list(spec_rule_contexts),
        "schema_example": {
            "candidates": [
                {
                    "sample_id": f"{request_tag}-cand-00",
                    "source_instruction_id": instruction_artifact["instruction_id"],
                    "instruction": FIXED_OPAL_VERIFIER_INSTRUCTION,
                    "records": [
                        {
                            "input": {
                                "method": {
                                    "name": "Get",
                                "args": {"required": {"HostSessionID": "00000001", "Cellblock": [{"startColumn": 1}, {"endColumn": 1}]}, "optional": {}},
                            },
                            "invoking_id": {"uid": "00 00 00 06 00 00 00 01", "name": "Locking"},
                                "status_codes": ["SUCCESS"],
                            },
                            "output": {"status_codes": ["SUCCESS"], "return_values": []},
                        }
                    ],
                    "label": "pass",
                    "label_target": "final_response",
                    "target": {
                        "final_response_index": 0,
                        "final_response": {"status_codes": ["SUCCESS"], "return_values": []},
                        "final_method": "Get",
                    },
                    "primary_evidence": {"record_index": 0, "reason": "Final response is supported by cited rule."},
                    "spec_grounding": [
                        {
                            "rule_ref": "RULE NN",
                            "source_path": "docs/legacy_spec_rules.md",
                            "source_span": "docs/legacy_spec_rules.md:start-end",
                            "condition": "copy from supplied card",
                            "expected_status": "copy from supplied card",
                        }
                    ],
                    "generation_provenance": {
                        "official_instance_artifact": "machine_generated_instances.jsonl",
                        "source_instruction_id": instruction_artifact["instruction_id"],
                        "classification_detection_id": classification_detection_artifact["classification_detection_id"],
                    },
                    "source": "self_instruct_output_first",
                }
            ]
        },
    }
    if candidate_targets is not None:
        prompt_spec["candidate_target_schedule"] = {
            "candidate_targets": indexed_targets,
            "requirements": [
                "candidate i uses candidate_targets[i].required_sample_id exactly as sample_id",
                "candidate i uses candidate_targets[i].target_label",
                "len(records) equals required_record_count exactly",
                "final method/status match target_final_method/target_final_status when present",
                "if requires_auth_session is true, include StartSession with optional.HostChallenge and optional.HostSigningAuthority concrete values",
                "if requires_auth_session is true, do not use Authenticate as the substitute for StartSession authentication",
                "spec_grounding.rule_ref is within allowed_source_rule_refs when present",
                "if required_context_domains is present, include each listed domain in the trajectory with auditable invoking_id or args",
                "records[0:-1] are context records and records[-1] is the final response label target",
            ],
            "context_record_skeletons": [
                "StartSession SUCCESS before session-bound final methods",
                "StartSession with optional.HostChallenge and optional.HostSigningAuthority before authority-sensitive final methods",
                "Locking range Get/Set/GenKey records for Locking and K_AES_256 rules",
                "MBRControl Set/Get records for MBR rules",
                "LockingInfo Get records when LockingInfo coverage is requested",
                "Get SUCCESS before Set/GenKey/RevertSP when object/range context is needed",
                "Set SUCCESS before Get when table/object state should be established",
                "EndSession SUCCESS only if it is itself the final target, not after a fail target",
            ],
        }
    return json.dumps(prompt_spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
    candidate_targets: Optional[Sequence[Mapping[str, Any]]] = None,
    prompt_mode: str = "full",
) -> Json:
    if request_index < 0:
        raise SelfInstructGenerationError("request_index_negative")
    if candidates_per_request <= 0:
        raise SelfInstructGenerationError("candidates_per_request_must_be_positive")
    if prompt_mode not in PROMPT_MODES:
        raise SelfInstructGenerationError(f"prompt_mode_not_supported:{prompt_mode}")

    request_id = f"self-instruct-gen-{request_index:05d}"
    seed_contexts = _select_seed_contexts(seeds, request_index, seeds_per_request)
    if candidate_targets is not None and len(candidate_targets) != candidates_per_request:
        raise SelfInstructGenerationError(f"{request_id}:candidate_targets_count_mismatch")
    normalized_candidate_targets = [dict(target) for target in candidate_targets] if candidate_targets is not None else None
    spec_rule_contexts = _include_target_rule_contexts(
        _select_spec_rule_contexts(spec_rule_cards, request_index, spec_rules_per_request),
        spec_rule_cards,
        normalized_candidate_targets,
    )
    instruction_artifact = build_instruction_artifact(
        request_index=request_index,
        seed_contexts=seed_contexts,
        spec_rule_contexts=spec_rule_contexts,
        created_at_kst=created_at_kst,
    )
    classification_detection_artifact = build_classification_detection_artifact(
        request_index=request_index,
        instruction_artifact=instruction_artifact,
        created_at_kst=created_at_kst,
    )
    user_prompt = _generation_user_prompt(
        seed_contexts,
        spec_rule_contexts,
        instruction_artifact,
        classification_detection_artifact,
        candidates_per_request,
        normalized_candidate_targets,
        request_index=request_index,
        request_id=request_id,
    )
    if prompt_mode == "compact":
        user_prompt = _generation_user_prompt_compact(
            seed_contexts,
            spec_rule_contexts,
            instruction_artifact,
            classification_detection_artifact,
            candidates_per_request,
            normalized_candidate_targets,
            request_index=request_index,
            request_id=request_id,
        )
    payload: Json = {
        "model": model,
        "messages": [
            {"role": "system", "content": _generation_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "seed_profile_context": seed_contexts,
        "spec_rule_context": spec_rule_contexts,
        "source_instruction_artifact": instruction_artifact,
        "classification_detection_artifact": classification_detection_artifact,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "prompt_mode": prompt_mode,
    }
    if normalized_candidate_targets is not None:
        payload["candidate_targets"] = normalized_candidate_targets

    request: Json = {
        "schema_version": GENERATION_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at_kst": created_at_kst,
        "execute": False,
        "official_stage": "instance_generation",
        "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["instance_generation"],
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
        "source_instruction_id": instruction_artifact["instruction_id"],
        "classification_detection_id": classification_detection_artifact["classification_detection_id"],
        "source_instruction_artifact": instruction_artifact,
        "classification_detection_artifact": classification_detection_artifact,
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "prompt_mode": prompt_mode,
        "source_seed_sample_ids": [str(context.get("sample_id")) for context in seed_contexts],
        "source_spec_rule_refs": [str(context.get("rule_ref")) for context in spec_rule_contexts],
        "candidates_per_request": candidates_per_request,
        "payload_sha256": _sha256_json(payload),
        "payload": payload,
    }
    if normalized_candidate_targets is not None:
        request["candidate_targets"] = normalized_candidate_targets
    return request


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
    target_schedule: Optional[Sequence[Mapping[str, Any]]] = None,
    prompt_mode: str = "full",
) -> List[Json]:
    if request_count <= 0:
        raise SelfInstructGenerationError("request_count_must_be_positive")
    if candidates_per_request <= 0:
        raise SelfInstructGenerationError("candidates_per_request_must_be_positive")
    if prompt_mode not in PROMPT_MODES:
        raise SelfInstructGenerationError(f"prompt_mode_not_supported:{prompt_mode}")
    if target_schedule is not None:
        expected_targets = request_count * candidates_per_request
        if len(target_schedule) != expected_targets:
            raise SelfInstructGenerationError(
                f"target_schedule_count_mismatch:expected_{expected_targets}:actual_{len(target_schedule)}"
            )
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
            candidate_targets=(
                target_schedule[index * candidates_per_request : (index + 1) * candidates_per_request]
                if target_schedule is not None
                else None
            ),
            prompt_mode=prompt_mode,
        )
        for index in range(request_count)
    ]


# Changed: expose official-stage dry-run artifacts as separate JSONL streams.
# Why: downstream parser/judge metadata must distinguish instruction generation, classification detection, and instance generation artifacts.
def instruction_artifacts_from_requests(requests: Sequence[Mapping[str, Any]]) -> List[Json]:
    return [dict(request["source_instruction_artifact"]) for request in requests]


def classification_detection_artifacts_from_requests(requests: Sequence[Mapping[str, Any]]) -> List[Json]:
    return [dict(request["classification_detection_artifact"]) for request in requests]


def build_metadata(
    seed_path: Path,
    spec_rules_path: Path,
    spec_rule_cards: Sequence[Mapping[str, Any]],
    requests: Sequence[Mapping[str, Any]],
    instruction_artifact_path: Optional[Path] = None,
    classification_artifact_path: Optional[Path] = None,
    target_schedule_path: Optional[Path] = None,
    target_schedule: Optional[Sequence[Mapping[str, Any]]] = None,
    runner_report: Optional[Mapping[str, Any]] = None,
    runner_report_path: Optional[Path] = None,
) -> Json:
    executed_count = 0
    if isinstance(runner_report, Mapping) and isinstance(runner_report.get("executed_count"), int):
        executed_count = int(runner_report["executed_count"])
    prompt_modes = sorted({str(request.get("prompt_mode")) for request in requests if request.get("prompt_mode") is not None})
    metadata: Json = {
        "schema_version": GENERATION_METADATA_SCHEMA_VERSION,
        "seed_input": str(seed_path),
        "spec_rules_input": str(spec_rules_path),
        "spec_rule_count": len(spec_rule_cards),
        "request_count": len(requests),
        "execute": executed_count > 0,
        "official_source": OFFICIAL_SELF_INSTRUCT_SOURCE,
        "official_pipeline_stage_map": OFFICIAL_PIPELINE_STAGE_MAP,
        "artifacts": {
            "instruction_generation": {
                "path": str(instruction_artifact_path) if instruction_artifact_path is not None else None,
                "schema_version": INSTRUCTION_ARTIFACT_SCHEMA_VERSION,
                "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["instruction_generation"],
                "status": "dry_run_request_only_not_machine_generated_instruction",
            },
            "classification_detection": {
                "path": str(classification_artifact_path) if classification_artifact_path is not None else None,
                "schema_version": CLASSIFICATION_DETECTION_SCHEMA_VERSION,
                "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["classification_detection"],
                "status": "audited_noop_true_for_pass_fail_domain",
            },
            "instance_generation": {
                "path": None,
                "schema_version": GENERATION_REQUEST_SCHEMA_VERSION,
                "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["instance_generation"],
                "status": "dry_run_request_only_no_llm_call",
            },
            "candidate_preparation": {
                "path": None,
                "official_counterpart": OFFICIAL_PIPELINE_STAGE_MAP["candidate_preparation"],
                "status": "handled_by_parse_self_instruct_outputs_and_candidate_schema_after_raw_llm_output",
            },
        },
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "prompt_modes": prompt_modes,
        "request_ids": [request.get("request_id") for request in requests],
        "source_instruction_ids": [request.get("source_instruction_id") for request in requests],
        "classification_detection_ids": [request.get("classification_detection_id") for request in requests],
        "payload_sha256": {str(request.get("request_id")): request.get("payload_sha256") for request in requests},
        "source_spec_rule_refs": {
            str(request.get("request_id")): request.get("source_spec_rule_refs") for request in requests
        },
        "notes": [
            "dry-run only: no LLM/API call was made",
            "request payloads contain input-only seed profiles, not public20 labels",
            "request payloads contain spec rule cards with source spans from docs/legacy_spec_rules.md",
            "instruction and classification artifacts are dry-run provenance, not accepted synthetic data",
            "raw candidates without spec_grounding/source_span must be rejected before manifest creation",
            "raw candidates without source_instruction_id or generation_provenance.source_instruction_id must be migrated before normalization",
            "raw LLM outputs must be parsed by tools/datagen/parse_self_instruct_outputs.py",
        ],
    }
    # Changed: report target schedule quotas as request metadata only.
    # Why: downstream data gates should know requested coverage without treating it as accepted labels or generated data.
    if target_schedule is not None:
        metadata["target_schedule"] = {
            "path": str(target_schedule_path) if target_schedule_path is not None else None,
            "sha256": _sha256_json(list(target_schedule)),
            "summary": _target_schedule_summary(target_schedule),
            "scope": "request_only_generation_guidance_not_label_source",
        }
        metadata["notes"].append("target schedule contains request-only candidate targets, not accepted synthetic labels")
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
    parser.add_argument("--instruction-artifact-output", type=Path, default=None, help="Dry-run machine_generated_instructions.jsonl counterpart.")
    parser.add_argument("--classification-artifact-output", type=Path, default=None, help="Audited no-op is_clf_or_not_*.jsonl counterpart.")
    parser.add_argument("--spec-rules-md", type=Path, default=DEFAULT_SPEC_RULES_PATH, help="Spec rule markdown used as grounding source.")
    parser.add_argument("--target-schedule-json", type=Path, default=None, help="Optional request-only target schedule JSON.")
    parser.add_argument("--request-count", type=int, default=1, help="Number of dry-run request payloads to build.")
    parser.add_argument("--seeds-per-request", type=int, default=8, help="Number of input-only seed profiles per request.")
    parser.add_argument("--spec-rules-per-request", type=int, default=8, help="Number of source-span spec rule cards per request.")
    parser.add_argument("--candidates-per-request", type=int, default=4, help="Requested candidates per external LLM call.")
    parser.add_argument("--prompt-mode", choices=PROMPT_MODES, default="full", help="Prompt detail level for generation requests.")
    parser.add_argument("--model", default="external-llm", help="Model name recorded in the payload for an external runner.")
    parser.add_argument("--created-at-kst", default=None, help="Optional fixed KST timestamp for reproducible tests.")
    # Changed: expose explicit provider execution flags while keeping dry-run as the default.
    # Why: paid API calls must require --execute plus the matching provider API-key environment variable.
    parser.add_argument("--execute", action="store_true", help="Execute requests with an external provider when the provider API key env var is present.")
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini", "qwen"),
        default="openai",
        help="Provider used only with --execute. Env vars: OPENAI_API_KEY, GEMINI_API_KEY, or QWEN_API_KEY plus optional QWEN_BASE_URL.",
    )
    parser.add_argument("--raw-output-jsonl", type=Path, default=None, help="Parser-compatible raw LLM output JSONL path for successful --execute calls.")
    parser.add_argument("--runner-report-json", type=Path, default=None, help="Runner report JSON path for --execute attempts and env-missing skips.")
    parser.add_argument("--request-timeout-seconds", type=int, default=120, help="HTTP timeout for each provider request when --execute is active.")
    # Changed: expose cached-model execution as a first-class backend.
    # Why: server Qwen weights must be usable when external API keys are absent.
    parser.add_argument("--local-model-path", type=Path, default=None, help="Execute with a cached Hugging Face CausalLM model instead of an external API provider.")
    parser.add_argument("--local-model-max-new-tokens", type=int, default=4096, help="Max new tokens per local-model request.")
    parser.add_argument("--local-model-temperature", type=float, default=0.7, help="Sampling temperature for local-model generation.")
    parser.add_argument("--local-model-top-p", type=float, default=0.95, help="Top-p sampling for local-model generation.")
    parser.add_argument("--local-model-device-map", default="auto", help="Transformers device_map for local-model loading; use 'none' to omit.")
    parser.add_argument("--local-model-torch-dtype", default="auto", help="Torch dtype for local-model loading: auto, bfloat16, float16, or float32.")
    parser.add_argument("--local-model-batch-size", type=int, default=1, help="Number of local-model request prompts to decode in one batch.")
    parser.add_argument("--local-model-allow-download", action="store_true", help="Allow Hugging Face download if --local-model-path is not fully cached.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        seeds = load_input_only_seeds(args.seed_jsonl)
        spec_rule_cards = load_spec_rule_cards(args.spec_rules_md)
        # Changed: load target schedules after spec cards so allowed rule refs can be validated against the active rule source.
        # Why: malformed or unknown refs must fail before any request artifact is written.
        target_schedule = load_target_schedule(args.target_schedule_json, spec_rule_cards) if args.target_schedule_json is not None else None
        requests = build_generation_requests(
            seeds=seeds,
            spec_rule_cards=spec_rule_cards,
            request_count=args.request_count,
            seeds_per_request=args.seeds_per_request,
            spec_rules_per_request=args.spec_rules_per_request,
            candidates_per_request=args.candidates_per_request,
            model=args.model,
            created_at_kst=args.created_at_kst,
            target_schedule=target_schedule,
            prompt_mode=args.prompt_mode,
        )
        _write_jsonl(requests, args.requests_output)
        # Changed: write official-stage artifacts next to the instance request by default.
        # Why: dry-run runs must keep instruction generation and classification detection separate from instance generation.
        instruction_artifact_path = args.instruction_artifact_output or args.requests_output.with_name("machine_generated_instructions.dry_run.jsonl")
        classification_artifact_path = args.classification_artifact_output or args.requests_output.with_name("is_clf_or_not_audited_noop.jsonl")
        _write_jsonl(instruction_artifacts_from_requests(requests), instruction_artifact_path)
        _write_jsonl(classification_detection_artifacts_from_requests(requests), classification_artifact_path)
        runner_report: Optional[Json] = None
        runner_report_path: Optional[Path] = None
        if args.execute:
            # Changed: perform env-gated external execution only after the dry-run request artifact is written.
            # Why: every raw response must retain the exact request provenance even if execution is skipped or partial.
            raw_output_path = args.raw_output_jsonl or args.requests_output.with_name("raw_outputs.jsonl")
            runner_report_path = args.runner_report_json or args.metadata_json.with_name("runner_report.json")
            if args.local_model_path is not None:
                # Changed: execute generation through cached Qwen/HF weights when requested.
                # Why: local model generation must not require QWEN_API_KEY, DASHSCOPE_API_KEY, or any provider env.
                runner_report = run_generation_requests_with_hf_model(
                    requests,
                    model_path=args.local_model_path,
                    output_path=raw_output_path,
                    max_new_tokens=args.local_model_max_new_tokens,
                    temperature=args.local_model_temperature,
                    top_p=args.local_model_top_p,
                    device_map=args.local_model_device_map,
                    torch_dtype=args.local_model_torch_dtype,
                    local_files_only=not args.local_model_allow_download,
                    batch_size=args.local_model_batch_size,
                    created_at_kst=args.created_at_kst,
                )
            else:
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
            if args.local_model_path is None and runner_report.get("status") == "skipped_missing_env":
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
                    instruction_artifact_path=instruction_artifact_path,
                    classification_artifact_path=classification_artifact_path,
                    target_schedule_path=args.target_schedule_json,
                    target_schedule=target_schedule,
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
