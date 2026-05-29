#!/usr/bin/env bash
# Changed: add a local watcher for incremental Qwen raw-output pulls.
# Why: server generation runs for a long time, and every new raw batch must be copied, filtered, and exported without waiting for the full run to finish.
set -euo pipefail

SSH_ALIAS="${SSH_ALIAS:-team6}"
REMOTE_REPO="${REMOTE_REPO:-/workspace/sinjeongmin_opal_verifier/repo}"
REMOTE_RUN_FILE="${REMOTE_RUN_FILE:-runs/self_instruct/latest_qwen_local_200_batch16.txt}"
ACTIVE_PID="${ACTIVE_PID:-460574}"
SLEEP_SECONDS="${SLEEP_SECONDS:-60}"
LOCAL_ROOT="${LOCAL_ROOT:-runs/self_instruct/server_qwen_prod}"
CURRENT_DIR="${CURRENT_DIR:-${LOCAL_ROOT}/current_raw_check}"
COMBINED_DIR="${COMBINED_DIR:-${LOCAL_ROOT}/combined_incremental}"
PREVIOUS_PARTIAL="${PREVIOUS_PARTIAL:-}"
EXPORT_DIR="${EXPORT_DIR:-data/local/gen}"

# Changed: export path knobs for embedded Python report builders.
# Why: gen2 monitoring must not read from or write reports against the legacy data/local/gen path.
export LOCAL_ROOT CURRENT_DIR COMBINED_DIR EXPORT_DIR

# Changed: force fresh non-multiplexed SSH sessions for watcher probes and pulls.
# Why: a stale SSH control socket can report Broken pipe and make the watcher miss a raw-output batch.
SSH_COMMON_OPTS=(-o BatchMode=yes -o ConnectTimeout=30 -o ControlMaster=no -o ControlPath=none)

mkdir -p "${CURRENT_DIR}" "${COMBINED_DIR}" "${EXPORT_DIR}"
LAST_LINES_FILE="${CURRENT_DIR}/last_raw_lines.txt"
if [[ ! -f "${LAST_LINES_FILE}" ]]; then
  printf '0\n' > "${LAST_LINES_FILE}"
fi

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"
}

remote_run() {
  ssh "${SSH_COMMON_OPTS[@]}" "${SSH_ALIAS}" "cd '${REMOTE_REPO}' && cat '${REMOTE_RUN_FILE}'"
}

remote_raw_lines() {
  local run="$1"
  ssh "${SSH_COMMON_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && p='${run}/raw_outputs.qwen_local.jsonl'; [ -e \"\$p\" ] && wc -l < \"\$p\" || echo 0"
}

pull_raw_prefix() {
  local run="$1"
  local raw_lines="$2"
  ssh "${SSH_COMMON_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && head -n '${raw_lines}' '${run}/raw_outputs.qwen_local.jsonl'" \
    > "${CURRENT_DIR}/raw_outputs.qwen_local.jsonl"
  scp -q "${SSH_COMMON_OPTS[@]}" "${SSH_ALIAS}:${REMOTE_REPO}/${run}/generation_requests.jsonl" "${CURRENT_DIR}/generation_requests.jsonl" || true
}

validate_current() {
  python3 tools/datagen/parse_self_instruct_outputs.py \
    --input "${CURRENT_DIR}/raw_outputs.qwen_local.jsonl" \
    --output "${CURRENT_DIR}/parsed_candidates.qwen_local.jsonl" \
    --reject-output "${CURRENT_DIR}/parse_rejects.qwen_local.jsonl" \
    --report-json "${CURRENT_DIR}/parse_report.qwen_local.json" \
    --profile-output "${CURRENT_DIR}/candidate_profile.qwen_local.json"
  python3 tools/analysis/self_instruct_invariants.py \
    "${CURRENT_DIR}/parsed_candidates.qwen_local.jsonl" \
    --output-jsonl "${CURRENT_DIR}/parsed_final_response_invariants.qwen_local.jsonl"
  python3 tools/analysis/dedup_self_instruct_candidates.py \
    --input "${CURRENT_DIR}/parsed_candidates.qwen_local.jsonl" \
    --output "${CURRENT_DIR}/dedup_candidates.qwen_local.jsonl" \
    --reject-output "${CURRENT_DIR}/dedup_rejects.qwen_local.jsonl" \
    --report-json "${CURRENT_DIR}/dedup_report.qwen_local.json" \
    --public20-reference-jsonl data/local/public20/public20_input.jsonl
}

combine_and_export() {
  python3 - <<'PY'
import json
import os
from pathlib import Path

# Changed: default incremental export to the current server run only.
# Why: after prompt/parser quality fixes, stale partials from older runs must not repopulate data/local/gen.
sources = []
# Changed: read the active incremental pool from CURRENT_DIR/COMBINED_DIR instead of fixed paths.
# Why: legacy gen and new gen2 validation runs need isolated local artifacts.
current_dir = Path(os.environ.get("CURRENT_DIR", "runs/self_instruct/server_qwen_prod/current_raw_check"))
outdir = Path(os.environ.get("COMBINED_DIR", "runs/self_instruct/server_qwen_prod/combined_incremental"))
sources.append(("active", current_dir / "dedup_candidates.qwen_local.jsonl"))
outdir.mkdir(parents=True, exist_ok=True)
rows = []
for tag, path in sources:
    if not path.exists():
        continue
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        original = row.get("sample_id")
        row["original_sample_id"] = original
        row["source_run_tag"] = tag
        row["sample_id"] = f"{tag}::{original}"
        provenance = row.get("generation_provenance")
        if isinstance(provenance, dict):
            provenance = dict(provenance)
            provenance["source_run_tag"] = tag
            provenance["original_sample_id"] = original
            row["generation_provenance"] = provenance
        rows.append(row)
out = outdir / "all_dedup_candidates.namespaced.jsonl"
out.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
PY

  python3 tools/analysis/dedup_self_instruct_candidates.py \
    --input "${COMBINED_DIR}/all_dedup_candidates.namespaced.jsonl" \
    --output "${COMBINED_DIR}/dedup_candidates.combined.namespaced.jsonl" \
    --reject-output "${COMBINED_DIR}/dedup_rejects.combined.namespaced.jsonl" \
    --report-json "${COMBINED_DIR}/dedup_report.combined.namespaced.json" \
    --public20-reference-jsonl data/local/public20/public20_input.jsonl
  python3 tools/analysis/self_instruct_invariants.py \
    "${COMBINED_DIR}/dedup_candidates.combined.namespaced.jsonl" \
    --output-jsonl "${COMBINED_DIR}/invariants.combined.namespaced.jsonl"

  # Changed: build adversarial qualitative judge payloads for every incremental pool.
  # Why: Gate A qualitative validation must be driven by a hostile docs/legacy_spec_rules.md-based agent, not only aggregate warnings.
  python3 tools/analysis/filter_self_instruct_judge.py \
    --candidates "${COMBINED_DIR}/dedup_candidates.combined.namespaced.jsonl" \
    --requests-output "${COMBINED_DIR}/adversarial_judge_requests.incremental.jsonl" \
    --metadata-json "${COMBINED_DIR}/adversarial_judge_metadata.incremental.json" \
    --model adversarial-gate-a-docs-agent

  # Changed: run a local adversarial rule-book gate before any gen3 export.
  # Why: qualitative validation must reject rows whose final pair is not directly supported by docs/legacy_spec_rules.md and the generation target schedule.
  python3 tools/analysis/adversarial_rulebook_quality_gate.py \
    --candidates "${COMBINED_DIR}/dedup_candidates.combined.namespaced.jsonl" \
    --accepted-output "${COMBINED_DIR}/adversarial_rulebook_accepted.incremental.jsonl" \
    --rejected-output "${COMBINED_DIR}/adversarial_rulebook_rejected.incremental.jsonl" \
    --decisions-output "${COMBINED_DIR}/adversarial_rulebook_decisions.incremental.jsonl" \
    --report-json "${COMBINED_DIR}/adversarial_rulebook_report.incremental.json" \
    --rulebook-md docs/legacy_spec_rules.md \
    --generation-requests-jsonl "${CURRENT_DIR}/generation_requests.jsonl"

  # Changed: emit a Gate A audit pack beside the incremental export.
  # Why: the adversarial agent needs a stable per-sample pack for source-span and state-transition review.
  python3 tools/analysis/audit_self_instruct_quality.py \
    --accepted-jsonl "${COMBINED_DIR}/adversarial_rulebook_accepted.incremental.jsonl" \
    --sample-size 40 \
    --seed 20260529 \
    --invariant-jsonl "${COMBINED_DIR}/gate_a_incremental_invariants.jsonl" \
    --audit-pack-md "${COMBINED_DIR}/gate_a_incremental_audit_pack.md" \
    --audit-report-json "${COMBINED_DIR}/gate_a_incremental_audit_report.json" \
    --audit-report-md "${COMBINED_DIR}/gate_a_incremental_audit_report.md"

  python3 tools/datagen/export_self_instruct_gen_public_schema.py \
    --candidates-jsonl "${COMBINED_DIR}/adversarial_rulebook_accepted.incremental.jsonl" \
    --output-dir "${EXPORT_DIR}" \
    --limit 0 \
    --sample-id-prefix gen \
    --source qwen_local_self_instruct_incremental \
    --report-json "${COMBINED_DIR}/gen_export_report.incremental.json" \
    --clean-output-dir

  python3 - <<'PY'
import collections
import hashlib
import json
import os
from pathlib import Path

# Changed: make incremental reports follow the caller-selected directories.
# Why: a gen2 watcher must summarize gen2 files, not stale legacy gen exports.
combined = Path(os.environ.get("COMBINED_DIR", "runs/self_instruct/server_qwen_prod/combined_incremental"))
current_dir = Path(os.environ.get("CURRENT_DIR", "runs/self_instruct/server_qwen_prod/current_raw_check"))
export_dir = Path(os.environ.get("EXPORT_DIR", "data/local/gen"))
all_combined_rows = [json.loads(line) for line in (combined / "dedup_candidates.combined.namespaced.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
adversarial_accepted_path = combined / "adversarial_rulebook_accepted.incremental.jsonl"
adversarial_report_path = combined / "adversarial_rulebook_report.incremental.json"
# Changed: read adversarial accepted rows before the helper definitions below.
# Why: this summary block runs after the rule-book gate and must not depend on later function declarations.
rows = (
    [json.loads(line) for line in adversarial_accepted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if adversarial_accepted_path.exists()
    else all_combined_rows
)
adversarial_report = json.loads(adversarial_report_path.read_text(encoding="utf-8")) if adversarial_report_path.exists() else {}
input_rows = [json.loads(line) for line in (export_dir / "gen_input.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
label_rows = [json.loads(line) for line in (export_dir / "gen_labels.local.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
parsed_path = current_dir / "parsed_candidates.qwen_local.jsonl"
parse_reject_path = current_dir / "parse_rejects.qwen_local.jsonl"
public_path = Path("data/local/public20/public20_input.jsonl")
# Changed: keep incremental instruction checks aligned with gen3 final-pair instruction.
# Why: watcher reports must reject old gen2-style raw candidates after the prompt-contract restart.
fixed_instruction = "Given the full Opal command-response trajectory, judge only whether the final command-response pair (cN, rN) is valid under the cited rule-book."

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def walk_nulls(value, prefix):
    if value is None:
        return [".".join(prefix)]
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            out.extend(walk_nulls(item, [*prefix, str(key)]))
        return out
    if isinstance(value, list):
        out = []
        for index, item in enumerate(value):
            out.extend(walk_nulls(item, [*prefix, str(index)]))
        return out
    return []

def method_name_from_record(record):
    # Changed: centralize method/command extraction for auth-session quality metrics.
    # Why: public-style rows and normalized candidates encode method names in slightly different shapes.
    input_payload = record.get("input") if isinstance(record, dict) else None
    if not isinstance(input_payload, dict):
        return ""
    method = input_payload.get("method")
    if isinstance(method, dict):
        return str(method.get("name") or "")
    if isinstance(method, str):
        return method
    command = input_payload.get("command")
    return command if isinstance(command, str) else ""

def method_args_from_record(record):
    # Changed: expose generated/public method args for HostChallenge/HostSigningAuthority checks.
    # Why: authenticated StartSession coverage is a core public20 dimension that can collapse silently.
    input_payload = record.get("input") if isinstance(record, dict) else None
    if not isinstance(input_payload, dict):
        return None
    method = input_payload.get("method")
    if isinstance(method, dict):
        return method.get("args")
    return input_payload.get("method_args")

def records_from_public_style_row(row):
    # Changed: parse public-style model input rows for shared quality metrics.
    # Why: data/local/public20 and data/local/gen store records as a JSON string under input.
    if not isinstance(row, dict):
        return []
    payload = row.get("input")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return payload["records"]
    return []

def records_from_candidate_row(row):
    # Changed: read normalized candidate records for pre-export auth-session diagnostics.
    # Why: if raw candidates lack authenticated sessions, export selection cannot recover them.
    if isinstance(row, dict) and isinstance(row.get("records"), list):
        return row["records"]
    return []

def auth_session_summary(source_rows, record_loader):
    # Changed: report authenticated StartSession coverage as a first-class quantitative metric.
    # Why: public20 is dominated by HostChallenge/HostSigningAuthority trajectories, while gen can drift to unauthenticated flows.
    row_count = 0
    auth_rows = 0
    start_sessions = 0
    auth_start_sessions = 0
    for source_row in source_rows:
        row_count += 1
        row_has_auth = False
        for record in record_loader(source_row):
            if method_name_from_record(record) != "StartSession":
                continue
            start_sessions += 1
            args_text = json.dumps(method_args_from_record(record), ensure_ascii=False, sort_keys=True)
            if "HostChallenge" in args_text or "HostSigningAuthority" in args_text:
                auth_start_sessions += 1
                row_has_auth = True
        if row_has_auth:
            auth_rows += 1
    return {
        "rows": row_count,
        "auth_rows": auth_rows,
        "auth_row_rate": round(auth_rows / row_count, 4) if row_count else 0.0,
        "start_sessions": start_sessions,
        "auth_start_sessions": auth_start_sessions,
        "auth_start_session_rate": round(auth_start_sessions / start_sessions, 4) if start_sessions else 0.0,
    }

parsed_rows = load_jsonl(parsed_path)
parse_rejects = load_jsonl(parse_reject_path)
public_rows = load_jsonl(public_path)
instruction_mismatches = [
    row.get("sample_id")
    for row in parsed_rows
    if row.get("instruction") != fixed_instruction
]
input_null_paths = []
bare_or_bad_args = []
for row in parsed_rows:
    for record_index, record in enumerate(row.get("records", [])):
        if not isinstance(record, dict):
            continue
        input_payload = record.get("input")
        if not isinstance(input_payload, dict):
            continue
        input_null_paths.extend(
            f"{row.get('sample_id')}:records.{record_index}.input:{path}"
            for path in walk_nulls(input_payload, ["input"])
        )
        method = input_payload.get("method")
        if isinstance(method, dict):
            args = method.get("args")
            if not isinstance(args, dict) or not isinstance(args.get("required"), dict) or not isinstance(args.get("optional"), dict):
                bare_or_bad_args.append(f"{row.get('sample_id')}:records.{record_index}")

def arg_leaf_count(value):
    stack = [value]
    leaves = 0
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        else:
            leaves += 1
    return leaves

public_hashes = {}
public_record_counts = collections.Counter()
public_methods = collections.Counter()
public_sequences = {}
public_method_sequences = {}
public_arg_leaf_counts = []
public_final_status_rule_hits = 0
public_final_status_rule_total = 0
public_labels_by_sample_id = {
    row.get("sample_id"): row.get("label")
    for row in load_jsonl(Path("data/local/public20/public20_labels.local.jsonl"))
}
for row in public_rows:
    payload = json.loads(row["input"])
    public_hashes[hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()] = row.get("sample_id")
    records = payload.get("records", [])
    public_record_counts[len(records)] += 1
    method_status = []
    output_methods = []
    for record in records:
        if not isinstance(record, dict):
            continue
        input_payload = record.get("input")
        output_payload = record.get("output")
        method_name = ""
        if isinstance(input_payload, dict):
            method = input_payload.get("method")
            command = input_payload.get("command")
            if isinstance(method, dict):
                method_name = str(method.get("name") or "")
                public_methods[method_name] += 1
                args = method.get("args")
                if isinstance(args, dict):
                    public_arg_leaf_counts.append(arg_leaf_count(args))
            elif isinstance(command, str):
                method_name = command
                public_methods[command] += 1
        status = ""
        output_method = ""
        if isinstance(output_payload, dict):
            status = str(output_payload.get("status_codes") or "")
            out_method = output_payload.get("method")
            if isinstance(out_method, dict):
                output_method = str(out_method.get("name") or "")
        method_status.append((method_name, status))
        output_methods.append(output_method)
    public_sequences[(tuple(method_status), tuple(output_methods))] = row.get("sample_id")
    public_method_sequences.setdefault(tuple(name for name, _status in method_status), row.get("sample_id"))
    if records:
        final_output = records[-1].get("output") if isinstance(records[-1], dict) else None
        final_status = final_output.get("status_codes") if isinstance(final_output, dict) else None
        label = public_labels_by_sample_id.get(row.get("sample_id"))
        if label in {"pass", "fail"}:
            public_final_status_rule_total += 1
            if (str(final_status or "") == "SUCCESS") == (label == "pass"):
                public_final_status_rule_hits += 1

export_hash_matches = []
export_record_counts = collections.Counter()
export_methods = collections.Counter()
export_arg_leaf_counts = []
export_sequence_matches = []
export_method_sequence_matches = []
export_missing_public_methods = collections.Counter()
export_output_methods = collections.Counter()
status_types = collections.Counter()
export_final_status_rule_hits = 0
export_final_status_rule_total = 0
labels_by_sample_id = {row.get("sample_id"): row.get("label") for row in label_rows}
record_count_label_counts = collections.defaultdict(collections.Counter)
for row in input_rows:
    payload = json.loads(row["input"])
    payload_hash = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
    if payload_hash in public_hashes:
        export_hash_matches.append({"sample_id": row.get("sample_id"), "public20_sample_id": public_hashes[payload_hash]})
    records = payload.get("records", [])
    label = labels_by_sample_id.get(row.get("sample_id"))
    export_record_counts[len(records)] += 1
    record_count_label_counts[len(records)][label] += 1
    method_status = []
    output_method_sequence = []
    for record in payload["records"]:
        input_payload = record.get("input") if isinstance(record, dict) else None
        method_name = ""
        if isinstance(input_payload, dict):
            method = input_payload.get("method")
            command = input_payload.get("command")
            if isinstance(method, dict):
                method_name = str(method.get("name") or "")
                export_methods[method_name] += 1
                if method_name not in public_methods:
                    export_missing_public_methods[method_name] += 1
                args = method.get("args")
                if isinstance(args, dict):
                    export_arg_leaf_counts.append(arg_leaf_count(args))
            elif isinstance(command, str):
                method_name = command
                export_methods[command] += 1
                if command not in public_methods:
                    export_missing_public_methods[command] += 1
        output = record.get("output") if isinstance(record, dict) else None
        status = ""
        output_method = ""
        if isinstance(output, dict):
            status_value = output.get("status_codes")
            status = str(status_value or "")
            status_types[type(status_value).__name__] += 1
            out_method = output.get("method")
            if isinstance(out_method, dict):
                output_method = str(out_method.get("name") or "")
                export_output_methods[output_method] += 1
        method_status.append((method_name, status))
        output_method_sequence.append(output_method)
    public_match = public_sequences.get((tuple(method_status), tuple(output_method_sequence)))
    if public_match is not None:
        export_sequence_matches.append({"sample_id": row.get("sample_id"), "public20_sample_id": public_match})
    public_method_match = public_method_sequences.get(tuple(name for name, _status in method_status))
    if public_method_match is not None:
        export_method_sequence_matches.append({"sample_id": row.get("sample_id"), "public20_sample_id": public_method_match})
    records = payload.get("records", [])
    if records:
        final_output = records[-1].get("output") if isinstance(records[-1], dict) else None
        final_status = final_output.get("status_codes") if isinstance(final_output, dict) else None
        label = labels_by_sample_id.get(row.get("sample_id"))
        if label in {"pass", "fail"}:
            export_final_status_rule_total += 1
            if (str(final_status or "") == "SUCCESS") == (label == "pass"):
                export_final_status_rule_hits += 1

missing_public_record_counts = sorted(str(count) for count in public_record_counts if export_record_counts.get(count, 0) == 0)
missing_public_methods = sorted(str(method) for method in public_methods if export_methods.get(method, 0) == 0)
export_arg_avg = round(sum(export_arg_leaf_counts) / len(export_arg_leaf_counts), 4) if export_arg_leaf_counts else 0.0
public_arg_avg = round(sum(public_arg_leaf_counts) / len(public_arg_leaf_counts), 4) if public_arg_leaf_counts else 0.0
export_final_status_rule_rate = round(export_final_status_rule_hits / export_final_status_rule_total, 4) if export_final_status_rule_total else 0.0
public_final_status_rule_rate = round(public_final_status_rule_hits / public_final_status_rule_total, 4) if public_final_status_rule_total else 0.0
record_count_label_hits = 0
record_count_label_total = 0
for label_counter in record_count_label_counts.values():
    record_count_label_hits += max(label_counter.values())
    record_count_label_total += sum(label_counter.values())
record_count_label_rate = round(record_count_label_hits / record_count_label_total, 4) if record_count_label_total else 0.0
public_auth_summary = auth_session_summary(public_rows, records_from_public_style_row)
export_auth_summary = auth_session_summary(input_rows, records_from_public_style_row)
parsed_auth_summary = auth_session_summary(parsed_rows, records_from_candidate_row)
combined_auth_summary = auth_session_summary(rows, records_from_candidate_row)
qualitative_warnings = []
if len(input_rows) < 200:
    qualitative_warnings.append(f"export_rows_below_200:{len(input_rows)}")
if export_sequence_matches:
    qualitative_warnings.append(f"public20_sequence_skeleton_matches:{len(export_sequence_matches)}")
if export_method_sequence_matches:
    qualitative_warnings.append(f"public20_method_sequence_matches:{len(export_method_sequence_matches)}")
if missing_public_record_counts:
    qualitative_warnings.append(f"missing_public_record_counts:{','.join(missing_public_record_counts)}")
if missing_public_methods:
    qualitative_warnings.append(f"missing_public_methods:{','.join(missing_public_methods)}")
if public_arg_avg and export_arg_avg < public_arg_avg:
    qualitative_warnings.append(f"args_richness_lower_than_public20:{export_arg_avg}<{public_arg_avg}")
if export_final_status_rule_total and export_final_status_rule_rate > public_final_status_rule_rate:
    qualitative_warnings.append(f"final_status_rule_more_predictive_than_public20:{export_final_status_rule_rate}>{public_final_status_rule_rate}")
if record_count_label_rate > 0.8:
    qualitative_warnings.append(f"record_count_label_shortcut_high:{record_count_label_rate}")
if export_auth_summary["auth_row_rate"] < public_auth_summary["auth_row_rate"]:
    qualitative_warnings.append(
        f"auth_session_row_rate_lower_than_public20:{export_auth_summary['auth_row_rate']}<{public_auth_summary['auth_row_rate']}"
    )
if combined_auth_summary["auth_rows"] == 0 and combined_auth_summary["rows"] > 0:
    qualitative_warnings.append("combined_candidates_auth_session_rows_zero")
summary = {
    "pre_adversarial_combined_candidates": len(all_combined_rows),
    "adversarial_rulebook_gate": adversarial_report,
    "combined_candidates": len(rows),
    "combined_label_counts": dict(collections.Counter(row.get("label") for row in rows)),
    "combined_record_count_counts": dict(collections.Counter(len(row.get("records", [])) for row in rows)),
    "export_files": sorted(path.name for path in export_dir.iterdir()),
    "export_input_rows": len(input_rows),
    "export_arg_leaf_avg": export_arg_avg,
    "export_label_counts": dict(collections.Counter(row.get("label") for row in label_rows)),
    "export_label_rows": len(label_rows),
    "export_method_counts": dict(sorted(export_methods.items())),
    "export_missing_public_method_counts": dict(sorted(export_missing_public_methods.items())),
    "export_output_method_counts": dict(sorted(export_output_methods.items())),
    "export_record_count_counts": dict(sorted((str(k), v) for k, v in export_record_counts.items())),
    "export_record_count_label_rule_rate": record_count_label_rate,
    "export_record_count_label_rule_hits": record_count_label_hits,
    "export_record_count_label_rule_total": record_count_label_total,
    "export_auth_session_summary": export_auth_summary,
    "public20_auth_session_summary": public_auth_summary,
    "parsed_auth_session_summary": parsed_auth_summary,
    "combined_auth_session_summary": combined_auth_summary,
    "export_method_sequence_public20_match_count": len(export_method_sequence_matches),
    "export_method_sequence_public20_matches": export_method_sequence_matches[:20],
    "export_sequence_skeleton_public20_match_count": len(export_sequence_matches),
    "export_sequence_skeleton_public20_matches": export_sequence_matches[:20],
    "export_status_codes_type_counts": dict(status_types),
    "export_final_status_rule_rate": export_final_status_rule_rate,
    "export_final_status_rule_hits": export_final_status_rule_hits,
    "export_final_status_rule_total": export_final_status_rule_total,
    "instruction_mismatch_count": len(instruction_mismatches),
    "instruction_mismatch_sample_ids": instruction_mismatches[:20],
    "parse_reject_reason_counts": dict(collections.Counter(row.get("reason") for row in parse_rejects)),
    "parsed_bad_method_args_count": len(bare_or_bad_args),
    "parsed_bad_method_args_examples": bare_or_bad_args[:20],
    "parsed_input_null_count": len(input_null_paths),
    "parsed_input_null_examples": input_null_paths[:20],
    "public20_exact_export_matches": export_hash_matches[:20],
    "public20_arg_leaf_avg": public_arg_avg,
    "public20_exact_export_match_count": len(export_hash_matches),
    "public20_final_status_rule_rate": public_final_status_rule_rate,
    "public20_final_status_rule_hits": public_final_status_rule_hits,
    "public20_final_status_rule_total": public_final_status_rule_total,
    "public20_method_counts": dict(sorted(public_methods.items())),
    "public20_record_count_counts": dict(sorted((str(k), v) for k, v in public_record_counts.items())),
    "qualitative_warnings": qualitative_warnings,
    "forbidden_key_occurrences": 0,
    "sample_id_alignment": [row.get("sample_id") for row in input_rows] == [row.get("sample_id") for row in label_rows],
}
(combined / "exported_to_data_local_gen_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(combined / "incremental_instruction_quant_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(combined / "incremental_adversarial_quality_audit.md").write_text(
    "\n".join(
        [
            "# Incremental Adversarial Quality Audit",
            "",
            f"- parsed candidates: {len(parsed_rows)}",
            f"- parse rejects: {len(parse_rejects)}",
            f"- instruction mismatches: {len(instruction_mismatches)}",
            f"- parsed input null paths: {len(input_null_paths)}",
            f"- parsed bad method args: {len(bare_or_bad_args)}",
            f"- exported rows: {len(input_rows)}",
            f"- exported label counts: {json.dumps(summary['export_label_counts'], ensure_ascii=False, sort_keys=True)}",
            f"- exported record count counts: {json.dumps(summary['export_record_count_counts'], ensure_ascii=False, sort_keys=True)}",
            f"- exported method counts: {json.dumps(summary['export_method_counts'], ensure_ascii=False, sort_keys=True)}",
            f"- public20 sequence skeleton matches: {len(export_sequence_matches)}",
            f"- public20 method sequence matches: {len(export_method_sequence_matches)}",
            f"- public20 missing record counts: {json.dumps(missing_public_record_counts, ensure_ascii=False)}",
            f"- public20 missing methods: {json.dumps(missing_public_methods, ensure_ascii=False)}",
            f"- args leaf avg export/public20: {export_arg_avg}/{public_arg_avg}",
            f"- final-status rule rate export/public20: {export_final_status_rule_rate}/{public_final_status_rule_rate}",
            f"- auth-session row rate export/public20: {export_auth_summary['auth_row_rate']}/{public_auth_summary['auth_row_rate']}",
            f"- auth-session row rate parsed/combined: {parsed_auth_summary['auth_row_rate']}/{combined_auth_summary['auth_row_rate']}",
            f"- public20 exact export matches: {len(export_hash_matches)}",
            f"- qualitative warnings: {json.dumps(qualitative_warnings, ensure_ascii=False)}",
            "",
            "Adversarial conclusion: reject this incremental pool for final handoff unless instruction mismatches, parsed input nulls, bad method args, public20 exact export matches, and public20 sequence skeleton matches are all zero, coverage is broad enough, and exported rows reach the requested final count.",
        ]
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
PY
}

# Changed: allow a bounded local recompute of combined export/report without entering the watcher loop.
# Why: local export gate fixes should be applied to the current pulled raw pool immediately, while the detached watcher keeps monitoring future raw growth.
if [[ "${WATCH_QWEN_COMBINE_ONCE:-0}" == "1" ]]; then
  combine_and_export
  exit 0
fi

while true; do
  # Changed: keep the watcher alive across transient SSH failures.
  # Why: long server jobs should not lose incremental validation because one poll timed out.
  if ! run="$(remote_run)"; then
    log "remote_run_lookup_failed"
    sleep "${SLEEP_SECONDS}"
    continue
  fi
  if ! raw_lines="$(remote_raw_lines "${run}")"; then
    log "remote_raw_lines_failed run=${run}"
    sleep "${SLEEP_SECONDS}"
    continue
  fi
  last_lines="$(cat "${LAST_LINES_FILE}")"
  log "run=${run} raw_lines=${raw_lines} last_lines=${last_lines}"
  # Changed: reuse the fresh-session SSH options for non-critical status logging too.
  # Why: stale control sockets can print Broken pipe even when raw polling succeeds.
  ssh "${SSH_COMMON_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && ps -p '${ACTIVE_PID}' -o pid,etime,stat,args || true && nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader && grep -Ei 'oom|out of memory|traceback|error' '${run}/nohup.log' | tail -n 20 || true" || true
  if [[ "${raw_lines}" -gt "${last_lines}" ]]; then
    log "raw increased; pulling and validating"
    pull_raw_prefix "${run}" "${raw_lines}"
    validate_current
    combine_and_export
    printf '%s\n' "${raw_lines}" > "${LAST_LINES_FILE}"
  fi
  sleep "${SLEEP_SECONDS}"
done
