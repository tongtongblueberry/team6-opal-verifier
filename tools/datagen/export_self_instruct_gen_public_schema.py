# Changed: add final export from gated Self-Instruct candidates to public-style gen files.
# Why: data/local/gen must contain only input and local-label JSONL artifacts after parse/invariant/dedup/judge/audit gates.
"""Export gated Self-Instruct candidates into data/local/gen public-style files."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.self_instruct_candidate_schema import (  # noqa: E402
    CandidateSchemaError,
    normalize_candidate,
)


Json = Dict[str, Any]
EXPORT_SCHEMA_VERSION = "self_instruct.public_schema_export.v1"
DEFAULT_PUBLIC20_REFERENCE = ROOT / "data" / "local" / "public20" / "public20_input.jsonl"


class SelfInstructGenExportError(ValueError):
    """Raised when final gen export inputs are invalid."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_public_input(records: Sequence[Any]) -> str:
    # Changed: hash the final public-style model input.
    # Why: public20 exact copies can be introduced only after public-shape export templating.
    return hashlib.sha256(_canonical_json({"records": list(records)}).encode("utf-8")).hexdigest()


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise SelfInstructGenExportError(f"line_{line_number}_not_object")
            yield line_number, payload


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_normalized_candidates(path: Path) -> List[Json]:
    # Changed: normalize again at export boundary before writing public-style files.
    # Why: final data/local/gen must not contain candidates that bypassed schema/invariant checks.
    candidates: List[Json] = []
    for line_number, row in _iter_jsonl(path):
        try:
            candidates.append(normalize_candidate(row))
        except CandidateSchemaError as exc:
            raise SelfInstructGenExportError(f"line_{line_number}:{exc}") from exc
    return candidates


def _status_scalar(value: Any, *, default: str = "SUCCESS") -> str:
    # Changed: export public-style status_codes as scalar strings.
    # Why: public20 uses string status fields internally, while parser-normalized candidates use lists.
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for item in value:
            if isinstance(item, str) and item.strip():
                value = item
                break
        else:
            return default
    if value is None:
        return default
    status = str(value).strip()
    if not status:
        return default
    return re.sub(r"\s*\(0x[0-9A-Fa-f]+\)\s*$", "", status).strip() or default


def _method_name_from_record(record: Mapping[str, Any]) -> Optional[str]:
    input_payload = record.get("input")
    if not isinstance(input_payload, Mapping):
        return None
    method = input_payload.get("method")
    if isinstance(method, Mapping) and isinstance(method.get("name"), str) and method["name"].strip():
        return method["name"].strip()
    command = input_payload.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()
    return None


def _public20_sequence_key(records: Sequence[Any]) -> Tuple[Tuple[Tuple[str, str], ...], Tuple[str, ...]]:
    # Changed: compute a public20 method/status/output-method skeleton key.
    # Why: final gen rows must not be near-copies of public20 trajectories after public-shape templating.
    method_status: List[Tuple[str, str]] = []
    output_methods: List[str] = []
    for record in records:
        method_name = ""
        output_status = ""
        output_method = ""
        if isinstance(record, Mapping):
            input_payload = record.get("input")
            if isinstance(input_payload, Mapping):
                method = input_payload.get("method")
                command = input_payload.get("command")
                if isinstance(method, Mapping):
                    method_name = str(method.get("name") or "")
                elif isinstance(command, str):
                    method_name = command
            output_payload = record.get("output")
            if isinstance(output_payload, Mapping):
                output_status = _status_scalar(output_payload.get("status_codes"), default="")
                out_method = output_payload.get("method")
                if isinstance(out_method, Mapping):
                    output_method = str(out_method.get("name") or "")
        method_status.append((method_name, output_status))
        output_methods.append(output_method)
    return tuple(method_status), tuple(output_methods)


def _public20_method_sequence_key(records: Sequence[Any]) -> Tuple[str, ...]:
    # Changed: compute a method/command-only trajectory key.
    # Why: adversarial review found public20 method-sequence copies that evade status/output skeleton duplicate checks.
    method_names: List[str] = []
    for record in records:
        method_name = ""
        if isinstance(record, Mapping):
            input_payload = record.get("input")
            if isinstance(input_payload, Mapping):
                method = input_payload.get("method")
                command = input_payload.get("command")
                if isinstance(method, Mapping):
                    method_name = str(method.get("name") or "")
                elif isinstance(command, str):
                    method_name = command
        method_names.append(method_name)
    return tuple(method_names)


def _load_public20_record_templates(path: Path) -> Json:
    # Changed: derive record-shape templates from public20 at export time.
    # Why: final gen inputs must match public20's internal method/command/status/invoking_id shape, not raw LLM shape.
    if not path.is_file():
        raise SelfInstructGenExportError(f"public20_reference_missing:{path}")
    method_templates: Dict[str, Json] = {}
    method_status_templates: Dict[str, Json] = {}
    command_templates: Dict[str, Json] = {}
    public_input_hashes: Dict[str, str] = {}
    public_sequence_keys: Dict[Any, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            payload = json.loads(row["input"])
            records = payload.get("records")
            if not isinstance(records, Sequence) or isinstance(records, (bytes, bytearray, str)):
                raise SelfInstructGenExportError(f"public20_line_{line_number}_records_not_list")
            sample_id = str(row.get("sample_id") or f"public20_line_{line_number}")
            public_input_hashes[_sha256_public_input(records)] = sample_id
            public_sequence_keys.setdefault(_public20_sequence_key(records), sample_id)
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                input_payload = record.get("input")
                output_payload = record.get("output")
                if not isinstance(input_payload, Mapping) or not isinstance(output_payload, Mapping):
                    continue
                if isinstance(input_payload.get("method"), Mapping):
                    method_name = str(input_payload["method"].get("name") or "").strip()
                    if not method_name:
                        continue
                    method_templates.setdefault(method_name, copy.deepcopy(dict(record)))
                    status = _status_scalar(output_payload.get("status_codes"))
                    method_status_templates.setdefault(f"{method_name}\t{status}", copy.deepcopy(dict(record)))
                elif isinstance(input_payload.get("command"), str):
                    command = input_payload["command"].strip()
                    if command:
                        command_templates.setdefault(command, copy.deepcopy(dict(record)))
    return {
        "method": method_templates,
        "method_status": method_status_templates,
        "command": command_templates,
        "public_input_hashes": public_input_hashes,
        "public_sequence_keys": public_sequence_keys,
    }


def _public_output_for_method(method_name: str, status: str, templates: Mapping[str, Any]) -> Json:
    method_status = templates.get("method_status") if isinstance(templates.get("method_status"), Mapping) else {}
    method_templates = templates.get("method") if isinstance(templates.get("method"), Mapping) else {}
    template_record = method_status.get(f"{method_name}\t{status}") or method_templates.get(method_name)
    if isinstance(template_record, Mapping) and isinstance(template_record.get("output"), Mapping):
        output_payload = copy.deepcopy(dict(template_record["output"]))
    else:
        output_payload = {"return_values": [], "status_codes": status}
    output_payload["status_codes"] = status
    return output_payload


def _public_input_for_method(method_name: str, status: str, generated_input: Mapping[str, Any], templates: Mapping[str, Any]) -> Json:
    method_status = templates.get("method_status") if isinstance(templates.get("method_status"), Mapping) else {}
    method_templates = templates.get("method") if isinstance(templates.get("method"), Mapping) else {}
    template_record = method_status.get(f"{method_name}\t{status}") or method_templates.get(method_name)
    if isinstance(template_record, Mapping) and isinstance(template_record.get("input"), Mapping):
        input_payload = copy.deepcopy(dict(template_record["input"]))
    else:
        input_payload = {
            "invoking_id": {"name": None, "type": None, "uid": None},
            "method": {"args": {"optional": {}, "required": {}}, "name": method_name, "uid": None},
            "status_codes": "SUCCESS",
        }
    input_payload["status_codes"] = _status_scalar(generated_input.get("status_codes"), default=str(input_payload.get("status_codes") or "SUCCESS"))
    if isinstance(input_payload.get("invoking_id"), Mapping):
        invoking_id = dict(input_payload["invoking_id"])
    else:
        invoking_id = {}
    input_payload["invoking_id"] = {
        "name": invoking_id.get("name"),
        "type": invoking_id.get("type"),
        "uid": invoking_id.get("uid"),
    }
    method = input_payload.get("method")
    if isinstance(method, Mapping):
        method_payload = dict(method)
    else:
        method_payload = {}
    method_payload["name"] = method_name
    method_payload.setdefault("uid", None)
    args = method_payload.get("args")
    if args in ({}, None):
        method_payload["args"] = {"optional": {}, "required": {}}
    generated_method = generated_input.get("method")
    generated_args = generated_method.get("args") if isinstance(generated_method, Mapping) else None
    if (
        isinstance(generated_args, Mapping)
        and isinstance(generated_args.get("required"), Mapping)
        and isinstance(generated_args.get("optional"), Mapping)
        and (generated_args.get("required") or generated_args.get("optional"))
    ):
        # Changed: preserve generated public-shaped method args instead of always using a public20 template.
        # Why: authenticated StartSession context and value-level state variation live in required/optional args.
        method_payload["args"] = copy.deepcopy(dict(generated_args))
    input_payload["method"] = method_payload
    return input_payload


def _has_authenticated_start_session(records: Sequence[Any]) -> bool:
    # Changed: detect HostChallenge/HostSigningAuthority rows after public-shape export.
    # Why: final selection must be able to protect authenticated-session coverage.
    for record in records:
        if not isinstance(record, Mapping):
            continue
        input_payload = record.get("input")
        if not isinstance(input_payload, Mapping):
            continue
        method = input_payload.get("method")
        if not isinstance(method, Mapping) or str(method.get("name") or "") != "StartSession":
            continue
        args_text = _canonical_json(method.get("args"))
        if "HostChallenge" in args_text or "HostSigningAuthority" in args_text:
            return True
    return False


def _public_command_record(command: str, index: int, templates: Mapping[str, Any]) -> Json:
    command_templates = templates.get("command") if isinstance(templates.get("command"), Mapping) else {}
    template_record = command_templates.get(command)
    if isinstance(template_record, Mapping):
        record = copy.deepcopy(dict(template_record))
    else:
        record = {
            "input": {"args": {}, "command": command},
            "output": {"command": command, "result": "pass" if command == "Write" else None},
        }
    record["index"] = index
    return record


def _to_public20_records(records: Sequence[Any], templates: Mapping[str, Any]) -> List[Json]:
    # Changed: strip generated-candidate record shape into public20-compatible records.
    # Why: data/local/gen input rows must not carry LLM-specific empty args, list statuses, or 0-based/string indices.
    public_records: List[Json] = []
    method_templates = templates.get("method") if isinstance(templates.get("method"), Mapping) else {}
    command_templates = templates.get("command") if isinstance(templates.get("command"), Mapping) else {}
    for index, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            raise SelfInstructGenExportError(f"record_{index}_not_object")
        input_payload = record.get("input")
        output_payload = record.get("output")
        if not isinstance(input_payload, Mapping) or not isinstance(output_payload, Mapping):
            raise SelfInstructGenExportError(f"record_{index}_input_or_output_missing")
        method_name = _method_name_from_record(record)
        if method_name is None:
            raise SelfInstructGenExportError(f"record_{index}_method_missing")
        if method_name in command_templates:
            public_records.append(_public_command_record(method_name, index, templates))
            continue
        if method_name not in method_templates:
            raise SelfInstructGenExportError(f"record_{index}_unsupported_public20_method:{method_name}")
        output_status = _status_scalar(output_payload.get("status_codes"))
        public_records.append(
            {
                "index": index,
                "input": _public_input_for_method(method_name, output_status, input_payload, templates),
                "output": _public_output_for_method(method_name, output_status, templates),
            }
        )
    return public_records


def _public20_compatible_candidates(
    candidates: Sequence[Mapping[str, Any]],
    templates: Mapping[str, Any],
) -> Tuple[List[Json], Dict[str, int]]:
    # Changed: drop candidates that cannot be rendered in public20's internal method/command vocabulary.
    # Why: unsupported generated methods like Authenticate/RevertSP should not appear in data/local/gen.
    compatible: List[Json] = []
    reject_counts: Dict[str, int] = {}
    public_input_hashes = templates.get("public_input_hashes") if isinstance(templates.get("public_input_hashes"), Mapping) else {}
    public_sequence_keys = templates.get("public_sequence_keys") if isinstance(templates.get("public_sequence_keys"), Mapping) else {}
    # Changed: track hashes after public-shape templating, not only before candidate dedup.
    # Why: adversarial audit found duplicate exported rows that survived candidate-level dedup.
    seen_export_input_hashes = set()
    for candidate in candidates:
        try:
            records = candidate.get("records")
            if not isinstance(records, list) or not records:
                raise SelfInstructGenExportError("records_missing")
            public_records = _to_public20_records(records, templates)
            public_hash = _sha256_public_input(public_records)
            if public_hash in public_input_hashes:
                raise SelfInstructGenExportError("exact_public20_input_duplicate")
            if public_hash in seen_export_input_hashes:
                raise SelfInstructGenExportError("duplicate_export_input")
            # Changed: reject public20 sequence skeleton duplicates before data/local/gen publication.
            # Why: adversarial qualitative audit flagged exact trajectory skeleton copies that hash checks miss.
            if _public20_sequence_key(public_records) in public_sequence_keys:
                raise SelfInstructGenExportError("public20_sequence_skeleton_duplicate")
            seen_export_input_hashes.add(public_hash)
            row = dict(candidate)
            row["records"] = public_records
            compatible.append(row)
        except SelfInstructGenExportError as exc:
            reason = str(exc).split(":", 1)[0]
            reject_counts[reason] = reject_counts.get(reason, 0) + 1
    return compatible, reject_counts


def _select_balanced(
    candidates: Sequence[Mapping[str, Any]],
    limit: int,
    *,
    require_balanced_labels: bool = False,
    min_auth_row_rate: float = 0.0,
) -> List[Json]:
    if limit <= 0:
        raise SelfInstructGenExportError("limit_must_be_positive")
    indexed_candidates: List[Tuple[int, Mapping[str, Any]]] = list(enumerate(candidates))
    groups: Dict[str, List[Tuple[int, Mapping[str, Any]]]] = {"pass": [], "fail": []}
    for index, candidate in indexed_candidates:
        label = str(candidate.get("label"))
        if label in groups:
            groups[label].append((index, candidate))
    if sum(len(group) for group in groups.values()) < limit:
        raise SelfInstructGenExportError(f"insufficient_candidates:{sum(len(group) for group in groups.values())}<{limit}")

    selected: List[Json] = []
    selected_indices = set()
    min_auth_count = int(limit * min_auth_row_rate)
    if min_auth_row_rate > 0 and min_auth_count < limit * min_auth_row_rate:
        min_auth_count += 1
    if min_auth_count:
        auth_available = sum(1 for _index, candidate in indexed_candidates if _has_authenticated_start_session(candidate.get("records", [])))
        if auth_available < min_auth_count:
            raise SelfInstructGenExportError(f"insufficient_auth_session_candidates:{auth_available}<{min_auth_count}")
    per_label_target = limit // 2
    if require_balanced_labels:
        for label in ("pass", "fail"):
            if len(groups[label]) < per_label_target:
                raise SelfInstructGenExportError(
                    f"insufficient_{label}_candidates_for_balanced_export:{len(groups[label])}<{per_label_target}"
                )
    ordered_groups: Dict[str, List[Tuple[int, Mapping[str, Any]]]] = {}
    for label, group in groups.items():
        # Changed: prefer authenticated-session rows inside each label bucket.
        # Why: label balancing alone can still starve the final export of auth/session semantics.
        ordered_groups[label] = sorted(
            group,
            key=lambda item: (not _has_authenticated_start_session(item[1].get("records", [])), item[0]),
        )
    for label in ("pass", "fail"):
        for index, candidate in ordered_groups[label][:per_label_target]:
            selected.append(dict(candidate))
            selected_indices.add(index)
    if min_auth_count:
        selected_auth_count = sum(1 for candidate in selected if _has_authenticated_start_session(candidate.get("records", [])))
        if selected_auth_count < min_auth_count:
            raise SelfInstructGenExportError(
                f"insufficient_auth_session_candidates_after_label_balance:{selected_auth_count}<{min_auth_count}"
            )
    remainder = limit - len(selected)
    if remainder:
        for index, candidate in indexed_candidates:
            if index in selected_indices:
                continue
            if str(candidate.get("label")) in {"pass", "fail"}:
                selected.append(dict(candidate))
                selected_indices.add(index)
            if len(selected) == limit:
                break
    if len(selected) != limit:
        raise SelfInstructGenExportError(f"selected_count_mismatch:{len(selected)}!={limit}")
    return selected


def _interleave_labels_for_export(selected: Sequence[Mapping[str, Any]]) -> List[Json]:
    # Changed: write selected rows in deterministic evenly spaced label order.
    # Why: pass-then-fail blocks and end-of-file majority tails leak labels through sample_id/file position.
    selected_groups: Dict[str, List[Json]] = {"pass": [], "fail": []}
    other_selected: List[Json] = []
    for candidate in selected:
        label = str(candidate.get("label"))
        if label in selected_groups:
            selected_groups[label].append(dict(candidate))
        else:
            other_selected.append(dict(candidate))
    if not selected_groups["pass"] or not selected_groups["fail"]:
        return [dict(candidate) for candidate in selected]
    minority_label, majority_label = sorted(("pass", "fail"), key=lambda label: len(selected_groups[label]))
    total = len(selected_groups["pass"]) + len(selected_groups["fail"])
    minority_count = len(selected_groups[minority_label])
    ordered_slots: List[Optional[Json]] = [None] * total
    used_slots = set()
    for index, candidate in enumerate(selected_groups[minority_label]):
        slot = round((index + 0.5) * total / minority_count - 0.5)
        slot = max(0, min(total - 1, slot))
        while slot in used_slots and slot + 1 < total:
            slot += 1
        while slot in used_slots and slot > 0:
            slot -= 1
        ordered_slots[slot] = candidate
        used_slots.add(slot)
    majority_iter = iter(selected_groups[majority_label])
    ordered: List[Json] = []
    for slot_value in ordered_slots:
        if slot_value is None:
            ordered.append(next(majority_iter))
        else:
            ordered.append(slot_value)
    ordered.extend(other_selected)
    return ordered


def _clean_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def export_public_schema(
    *,
    candidates: Sequence[Mapping[str, Any]],
    output_dir: Path,
    limit: int,
    sample_id_prefix: str,
    source: str,
    clean_output_dir: bool,
    require_balanced_labels: bool,
    public20_reference_jsonl: Path,
    min_auth_row_rate: float,
) -> Json:
    if clean_output_dir:
        _clean_output_dir(output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    templates = _load_public20_record_templates(public20_reference_jsonl)
    compatible_candidates, public_shape_reject_counts = _public20_compatible_candidates(candidates, templates)
    # Changed: limit<=0 means export all compatible rows for incremental partial pools.
    # Why: partial local pulls should publish every currently valid row without pre-knowing public-shape reject counts.
    effective_limit = len(compatible_candidates) if limit <= 0 else limit
    if effective_limit == 0:
        # Changed: allow incremental watcher exports to represent an empty accepted pool.
        # Why: early gen3 polls can have raw rows but zero parser/dedup-compatible candidates; that should produce a waiting report, not kill the watcher.
        input_path = output_dir / "gen_input.jsonl"
        label_path = output_dir / "gen_labels.local.jsonl"
        _write_jsonl([], input_path)
        _write_jsonl([], label_path)
        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "output_dir": str(output_dir),
            "input_path": str(input_path),
            "label_path": str(label_path),
            "row_count": 0,
            "requested_limit": limit,
            "effective_limit": 0,
            "label_counts": {},
            "record_count_counts": {},
            "source": source,
            "clean_output_dir": clean_output_dir,
            "require_balanced_labels": require_balanced_labels,
            "public20_reference_jsonl": str(public20_reference_jsonl),
            "min_auth_row_rate": min_auth_row_rate,
            "auth_session_row_count": 0,
            "public_shape_reject_counts": public_shape_reject_counts,
            "public_shape_compatible_count": 0,
            "status": "empty_accepted_pool_waiting_for_more_raw",
        }
    selected = _select_balanced(
        compatible_candidates,
        effective_limit,
        require_balanced_labels=require_balanced_labels,
        min_auth_row_rate=min_auth_row_rate if limit > 0 else 0.0,
    )
    selected = _interleave_labels_for_export(selected)

    input_rows: List[Json] = []
    label_rows: List[Json] = []
    label_counts: Dict[str, int] = {}
    record_count_counts: Dict[str, int] = {}
    for index, candidate in enumerate(selected, start=1):
        sample_id = f"{sample_id_prefix}{index:04d}"
        records = candidate.get("records")
        if not isinstance(records, list) or not records:
            raise SelfInstructGenExportError(f"{sample_id}:records_missing")
        label = str(candidate.get("label"))
        label_counts[label] = label_counts.get(label, 0) + 1
        record_count = str(len(records))
        record_count_counts[record_count] = record_count_counts.get(record_count, 0) + 1
        input_rows.append(
            {
                "input": _canonical_json({"records": records}),
                "sample_id": sample_id,
                "source": source,
            }
        )
        label_rows.append(
            {
                "label": label,
                "sample_id": sample_id,
                "source": f"{source}.local_reference",
            }
        )

    input_path = output_dir / "gen_input.jsonl"
    label_path = output_dir / "gen_labels.local.jsonl"
    _write_jsonl(input_rows, input_path)
    _write_jsonl(label_rows, label_path)
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "output_dir": str(output_dir),
        "input_path": str(input_path),
        "label_path": str(label_path),
        "row_count": len(selected),
        "requested_limit": limit,
        "effective_limit": effective_limit,
        "label_counts": label_counts,
        "record_count_counts": record_count_counts,
        "source": source,
        "clean_output_dir": clean_output_dir,
        "require_balanced_labels": require_balanced_labels,
        "public20_reference_jsonl": str(public20_reference_jsonl),
        "min_auth_row_rate": min_auth_row_rate,
        "auth_session_row_count": sum(1 for candidate in selected if _has_authenticated_start_session(candidate.get("records", []))),
        "public_shape_reject_counts": public_shape_reject_counts,
        "public_shape_compatible_count": len(compatible_candidates),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export gated Self-Instruct candidates into data/local/gen public-style JSONL files.")
    parser.add_argument("--candidates-jsonl", required=True, type=Path, help="Gated candidate JSONL.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory, usually data/local/gen.")
    parser.add_argument("--limit", required=True, type=int, help="Number of final rows to write; use 0 to export all public20-compatible rows.")
    parser.add_argument("--sample-id-prefix", default="gen", help="Sample ID prefix.")
    parser.add_argument("--source", default="qwen_local_self_instruct", help="Source string for exported rows.")
    parser.add_argument("--report-json", required=True, type=Path, help="Export report path.")
    parser.add_argument(
        "--public20-reference-jsonl",
        type=Path,
        default=DEFAULT_PUBLIC20_REFERENCE,
        help="Public20 input JSONL used to derive internal record-shape templates.",
    )
    parser.add_argument("--clean-output-dir", action="store_true", help="Remove existing files/directories in output-dir before export.")
    parser.add_argument(
        "--require-balanced-labels",
        action="store_true",
        help="Require at least limit/2 pass and limit/2 fail candidates before export.",
    )
    parser.add_argument(
        "--min-auth-row-rate",
        type=float,
        default=0.0,
        help="Minimum final row fraction containing StartSession HostChallenge/HostSigningAuthority; enforced only when limit > 0.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        candidates = load_normalized_candidates(args.candidates_jsonl)
        report = export_public_schema(
            candidates=candidates,
            output_dir=args.output_dir,
            limit=args.limit,
            sample_id_prefix=args.sample_id_prefix,
            source=args.source,
            clean_output_dir=args.clean_output_dir,
            require_balanced_labels=args.require_balanced_labels,
            public20_reference_jsonl=args.public20_reference_jsonl,
            min_auth_row_rate=args.min_auth_row_rate,
        )
        _write_json(report, args.report_json)
    except (OSError, json.JSONDecodeError, CandidateSchemaError, SelfInstructGenExportError) as exc:
        print(f"export_self_instruct_gen_public_schema: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
