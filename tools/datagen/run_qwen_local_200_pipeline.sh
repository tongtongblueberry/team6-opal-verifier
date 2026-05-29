#!/usr/bin/env bash
# Changed: add a server-side cached-Qwen production pipeline for final 200 generated rows.
# Why: data/local/gen must be rebuilt from Qwen local inference through parse/invariant/dedup/judge/audit gates without API keys.
set -euo pipefail

REQUEST_COUNT="${REQUEST_COUNT:-480}"
CANDIDATES_PER_REQUEST="${CANDIDATES_PER_REQUEST:-1}"
LOCAL_MODEL_PATH="${LOCAL_MODEL_PATH:-/workspace/cache/hf_cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28}"
BATCH_SIZE="${BATCH_SIZE:-16}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-4096}"
JUDGE_BATCH_SIZE="${JUDGE_BATCH_SIZE:-16}"
JUDGE_MAX_NEW_TOKENS="${JUDGE_MAX_NEW_TOKENS:-512}"
FINAL_LIMIT="${FINAL_LIMIT:-200}"
AUDIT_SAMPLE_SIZE="${AUDIT_SAMPLE_SIZE:-40}"
PROMPT_MODE="${PROMPT_MODE:-full}"
FAIL_TARGET_PERIOD="${FAIL_TARGET_PERIOD:-3}"
CURRICULUM_WARMUP_REQUESTS="${CURRICULUM_WARMUP_REQUESTS:-160}"
REQUIRE_BALANCED_LABELS="${REQUIRE_BALANCED_LABELS:-1}"
MIN_AUTH_ROW_RATE="${MIN_AUTH_ROW_RATE:-0.60}"
RUN_ROOT="${RUN_ROOT:-runs/self_instruct}"
RUN="${RUN:-${RUN_ROOT}/qwen_local_200_batch16_$(date +%Y%m%d_%H%M%S_KST)}"

mkdir -p "${RUN}"
printf '%s\n' "${RUN}" > "${RUN_ROOT}/latest_qwen_local_200_batch16.txt"

python3 - "${RUN}/target_schedule.json" "${REQUEST_COUNT}" "${CANDIDATES_PER_REQUEST}" "data/local/public20/public20_input.jsonl" "${FAIL_TARGET_PERIOD}" "${CURRICULUM_WARMUP_REQUESTS}" <<'PY'
import json
import sys

out, request_count, candidates_per_request, public20_input, fail_target_period, curriculum_warmup_requests = (
    sys.argv[1],
    int(sys.argv[2]),
    int(sys.argv[3]),
    sys.argv[4],
    int(sys.argv[5]),
    int(sys.argv[6]),
)
total = request_count * candidates_per_request
record_counts = []
with open(public20_input, "r", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        row = json.loads(line)
        payload = json.loads(row["input"])
        record_counts.append(len(payload["records"]))
if not record_counts:
    raise SystemExit("public20_record_counts_empty")
record_count_values = []
for count in record_counts:
    if count not in record_count_values:
        record_count_values.append(count)
# Changed: restrict scheduled final operations to public20's input vocabulary.
# Why: final data/local/gen must export without wasting Qwen budget on unsupported methods that the public-schema exporter will reject.
# Changed: schedule semantic target families instead of deriving label from row index/status.
# Why: the previous run leaked labels through record count and final status, and did not force authenticated StartSession context.
pass_plans = [
    # Changed: gen3 targets force public20-like domains instead of generic short C_PIN/session flows.
    # Why: gen2 had no Locking/MBRControl/LockingInfo coverage and reused placeholder session ids.
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 20"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 21},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 27"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 10},
    {"target_final_method": "Activate", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 48"], "requires_auth_session": True, "required_context_domains": ["SP", "Authority"], "target_record_count": 11},
    {"target_final_method": "StartSession", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 46"], "requires_auth_session": True, "required_context_domains": ["SP"], "target_record_count": 2},
    {"target_final_method": "Properties", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 79"], "requires_auth_session": False, "target_record_count": 1},
    {"target_final_method": "GenKey", "target_final_status": "NOT_AUTHORIZED", "allowed_source_rule_refs": ["RULE 66"], "requires_auth_session": True, "required_context_domains": ["Locking", "K_AES_256", "Authority"], "target_record_count": 26},
    {"target_final_method": "Set", "target_final_status": "NOT_AUTHORIZED", "allowed_source_rule_refs": ["RULE 02"], "requires_auth_session": True, "required_context_domains": ["Locking", "Authority"], "target_record_count": 21},
    {"target_final_method": "Get", "target_final_status": "INVALID_PARAMETER", "allowed_source_rule_refs": ["RULE 85"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 9},
    {"target_final_method": "Set", "target_final_status": "INVALID_PARAMETER", "allowed_source_rule_refs": ["RULE 73"], "requires_auth_session": True, "required_context_domains": ["MBRControl"], "target_record_count": 26},
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 01"], "requires_auth_session": True, "required_context_domains": ["LockingInfo"], "target_record_count": 7},
    {"target_final_method": "Set", "target_final_status": "INVALID_PARAMETER", "allowed_source_rule_refs": ["RULE 82"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 39},
    {"target_final_method": "Set", "target_final_status": "NOT_AUTHORIZED", "allowed_source_rule_refs": ["RULE 65"], "requires_auth_session": True, "required_context_domains": ["Locking", "Authority"], "target_record_count": 27},
]
fail_plans = [
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 18"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 21},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 02"], "requires_auth_session": True, "required_context_domains": ["Locking", "Authority"], "target_record_count": 21},
    {"target_final_method": "Activate", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 49"], "requires_auth_session": True, "required_context_domains": ["SP"], "target_record_count": 11},
    {"target_final_method": "StartSession", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 07"], "requires_auth_session": True, "required_context_domains": ["SP", "Authority"], "target_record_count": 2},
    {"target_final_method": "Properties", "target_final_status": "INVALID_PARAMETER", "allowed_source_rule_refs": ["RULE 79"], "requires_auth_session": False, "target_record_count": 1},
    {"target_final_method": "GenKey", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 66"], "requires_auth_session": True, "required_context_domains": ["Locking", "K_AES_256", "Authority"], "target_record_count": 26},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 73"], "requires_auth_session": True, "required_context_domains": ["MBRControl"], "target_record_count": 26},
    {"target_final_method": "Get", "target_final_status": "NOT_AUTHORIZED", "allowed_source_rule_refs": ["RULE 62"], "requires_auth_session": True, "required_context_domains": ["C_PIN", "Authority"], "target_record_count": 10},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 82"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 39},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 65"], "requires_auth_session": True, "required_context_domains": ["Locking", "Authority"], "target_record_count": 27},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 22"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 9},
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 84"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 20},
]
easy_pass_plans = [
    # Changed: add a gen3.1 warm-up curriculum before the harder long/domain schedule.
    # Why: gen3 produced zero accepted rows because it missed authenticated StartSession structure before reaching rule-book support.
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 20"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 21},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 27"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 10},
    {"target_final_method": "Activate", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 48"], "requires_auth_session": True, "required_context_domains": ["SP", "Authority"], "target_record_count": 11},
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 01"], "requires_auth_session": True, "required_context_domains": ["LockingInfo"], "target_record_count": 7},
]
easy_fail_plans = [
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 02"], "requires_auth_session": True, "required_context_domains": ["Locking", "Authority"], "target_record_count": 21},
    {"target_final_method": "Get", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 18"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 21},
    {"target_final_method": "Set", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 22"], "requires_auth_session": True, "required_context_domains": ["Locking"], "target_record_count": 9},
    {"target_final_method": "Activate", "target_final_status": "SUCCESS", "allowed_source_rule_refs": ["RULE 49"], "requires_auth_session": True, "required_context_domains": ["SP"], "target_record_count": 11},
]
targets = []
for index in range(total):
    label = "pass" if index % 2 == 0 else "fail"
    pair_index = index // 2
    in_warmup = index < curriculum_warmup_requests
    plan_pool = (
        easy_pass_plans
        if label == "pass" and in_warmup
        else easy_fail_plans
        if label == "fail" and in_warmup
        else pass_plans
        if label == "pass"
        else fail_plans
    )
    plan = plan_pool[pair_index % len(plan_pool)]
    record_count = int(plan.get("target_record_count") or record_count_values[pair_index % len(record_count_values)])
    if plan["requires_auth_session"] and plan["target_final_method"] != "StartSession" and record_count == 1:
        record_count = next(count for count in record_count_values if count > 1)
    target = {
        "target_label": label,
        "target_record_count": record_count,
        "target_final_method": plan["target_final_method"],
        "target_final_status": plan["target_final_status"],
        "allowed_source_rule_refs": plan["allowed_source_rule_refs"],
        "requires_auth_session": plan["requires_auth_session"],
    }
    if "required_context_domains" in plan:
        target["required_context_domains"] = plan["required_context_domains"]
    targets.append(target)
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"targets": targets}, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
PY

python3 tools/datagen/run_self_instruct_generation.py \
  --seed-jsonl data/local/public20/public20_input.jsonl \
  --requests-output "${RUN}/generation_requests.jsonl" \
  --metadata-json "${RUN}/generation_metadata.json" \
  --target-schedule-json "${RUN}/target_schedule.json" \
  --request-count "${REQUEST_COUNT}" \
  --seeds-per-request 1 \
  --spec-rules-per-request 1 \
  --candidates-per-request "${CANDIDATES_PER_REQUEST}" \
  --prompt-mode "${PROMPT_MODE}" \
  --model qwen2.5-7b-instruct-local \
  --execute \
  --local-model-path "${LOCAL_MODEL_PATH}" \
  --local-model-max-new-tokens "${MAX_NEW_TOKENS}" \
  --local-model-temperature 0.45 \
  --local-model-top-p 0.9 \
  --local-model-torch-dtype bfloat16 \
  --local-model-batch-size "${BATCH_SIZE}" \
  --raw-output-jsonl "${RUN}/raw_outputs.qwen_local.jsonl" \
  --runner-report-json "${RUN}/runner_report.qwen_local.json"

python3 - "${RUN}/raw_outputs.qwen_local.jsonl" "${RUN}/runner_report.qwen_local.json" <<'PY'
import json
import sys
from pathlib import Path

raw_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
raw_rows = sum(1 for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()) if raw_path.exists() else 0
report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
if raw_rows == 0:
    # Changed: abort after a failed local generation stage before judge/export reloads the model.
    # Why: OOM can produce a completed_with_errors runner report with zero raw rows; downstream stages cannot recover candidates from that.
    raise SystemExit(f"qwen_generation_produced_zero_raw_rows status={report.get('status')} failed_count={report.get('failed_count')}")
PY

python3 tools/datagen/parse_self_instruct_outputs.py \
  --input "${RUN}/raw_outputs.qwen_local.jsonl" \
  --output "${RUN}/parsed_candidates.qwen_local.jsonl" \
  --reject-output "${RUN}/parse_rejects.qwen_local.jsonl" \
  --report-json "${RUN}/parse_report.qwen_local.json" \
  --profile-output "${RUN}/candidate_profile.qwen_local.json"

python3 tools/analysis/self_instruct_invariants.py \
  "${RUN}/parsed_candidates.qwen_local.jsonl" \
  --output-jsonl "${RUN}/parsed_final_response_invariants.qwen_local.jsonl"

python3 tools/analysis/dedup_self_instruct_candidates.py \
  --input "${RUN}/parsed_candidates.qwen_local.jsonl" \
  --output "${RUN}/dedup_candidates.qwen_local.jsonl" \
  --reject-output "${RUN}/dedup_rejects.qwen_local.jsonl" \
  --report-json "${RUN}/dedup_report.qwen_local.json" \
  --public20-reference-jsonl data/local/public20/public20_input.jsonl

python3 tools/analysis/self_instruct_invariants.py \
  "${RUN}/dedup_candidates.qwen_local.jsonl" \
  --output-jsonl "${RUN}/dedup_final_response_invariants.qwen_local.jsonl"

python3 tools/analysis/filter_self_instruct_judge.py \
  --candidates "${RUN}/dedup_candidates.qwen_local.jsonl" \
  --requests-output "${RUN}/judge_requests.jsonl" \
  --metadata-json "${RUN}/judge_metadata.json" \
  --model qwen2.5-7b-instruct-local

python3 tools/analysis/run_self_instruct_judge_local.py \
  --requests-jsonl "${RUN}/judge_requests.jsonl" \
  --raw-output-jsonl "${RUN}/judge_raw_outputs.qwen_local.jsonl" \
  --runner-report-json "${RUN}/judge_runner_report.qwen_local.json" \
  --local-model-path "${LOCAL_MODEL_PATH}" \
  --max-new-tokens "${JUDGE_MAX_NEW_TOKENS}" \
  --temperature 0.0 \
  --top-p 1.0 \
  --torch-dtype bfloat16 \
  --batch-size "${JUDGE_BATCH_SIZE}"

python3 tools/analysis/filter_self_instruct_judge.py \
  --candidates "${RUN}/dedup_candidates.qwen_local.jsonl" \
  --requests-output "${RUN}/judge_requests.reparse.jsonl" \
  --metadata-json "${RUN}/judge_metadata.reparse.json" \
  --judge-results "${RUN}/judge_raw_outputs.qwen_local.jsonl" \
  --accepted-output "${RUN}/judge_accepted_candidates.qwen_local.jsonl" \
  --reject-output "${RUN}/judge_rejects.qwen_local.jsonl" \
  --decisions-output "${RUN}/judge_decisions.qwen_local.json" \
  --report-json "${RUN}/judge_filter_report.qwen_local.json" \
  --model qwen2.5-7b-instruct-local

python3 tools/analysis/adversarial_rulebook_quality_gate.py \
  --candidates "${RUN}/judge_accepted_candidates.qwen_local.jsonl" \
  --accepted-output "${RUN}/rulebook_accepted_candidates.qwen_local.jsonl" \
  --rejected-output "${RUN}/rulebook_rejected_candidates.qwen_local.jsonl" \
  --decisions-output "${RUN}/rulebook_decisions.qwen_local.jsonl" \
  --report-json "${RUN}/rulebook_quality_report.qwen_local.json" \
  --rulebook-md docs/legacy_spec_rules.md \
  --generation-requests-jsonl "${RUN}/generation_requests.jsonl"

python3 tools/analysis/audit_self_instruct_quality.py \
  --accepted-jsonl "${RUN}/rulebook_accepted_candidates.qwen_local.jsonl" \
  --sample-size "${AUDIT_SAMPLE_SIZE}" \
  --seed 20260528 \
  --invariant-jsonl "${RUN}/gate_a_invariants.qwen_local.jsonl" \
  --audit-pack-md "${RUN}/gate_a_audit_pack.qwen_local.md" \
  --audit-report-json "${RUN}/gate_a_audit_report.qwen_local.json" \
  --audit-report-md "${RUN}/gate_a_audit_report.qwen_local.md"

python3 tools/datagen/export_self_instruct_gen_public_schema.py \
  --candidates-jsonl "${RUN}/rulebook_accepted_candidates.qwen_local.jsonl" \
  --output-dir "${RUN}/gen_export" \
  --limit "${FINAL_LIMIT}" \
  --sample-id-prefix gen \
  --source qwen_local_self_instruct_batch16 \
  --report-json "${RUN}/gen_export_report.json" \
  --clean-output-dir \
  --min-auth-row-rate "${MIN_AUTH_ROW_RATE}" \
  $(if [ "${REQUIRE_BALANCED_LABELS}" = "1" ]; then printf '%s' "--require-balanced-labels"; fi)

python3 - "${RUN}" "${FINAL_LIMIT}" <<'PY'
import collections
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
limit = int(sys.argv[2])

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def count_jsonl(path):
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

def label_counts(path):
    counts = collections.Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        counts[json.loads(line).get("label")] += 1
    return dict(sorted(counts.items()))

summary = {
    "run": str(run),
    "requested_final_limit": limit,
    "raw_output_rows": count_jsonl(run / "raw_outputs.qwen_local.jsonl"),
    "parsed_candidates": count_jsonl(run / "parsed_candidates.qwen_local.jsonl"),
    "parse_rejects": count_jsonl(run / "parse_rejects.qwen_local.jsonl"),
    "dedup_candidates": count_jsonl(run / "dedup_candidates.qwen_local.jsonl"),
    "dedup_rejects": count_jsonl(run / "dedup_rejects.qwen_local.jsonl"),
    "judge_accepted_candidates": count_jsonl(run / "judge_accepted_candidates.qwen_local.jsonl"),
    "judge_rejects": count_jsonl(run / "judge_rejects.qwen_local.jsonl"),
    "rulebook_accepted_candidates": count_jsonl(run / "rulebook_accepted_candidates.qwen_local.jsonl"),
    "rulebook_rejected_candidates": count_jsonl(run / "rulebook_rejected_candidates.qwen_local.jsonl"),
    "export_input_rows": count_jsonl(run / "gen_export" / "gen_input.jsonl"),
    "export_label_rows": count_jsonl(run / "gen_export" / "gen_labels.local.jsonl"),
    "judge_accepted_label_counts": label_counts(run / "judge_accepted_candidates.qwen_local.jsonl"),
    "rulebook_accepted_label_counts": label_counts(run / "rulebook_accepted_candidates.qwen_local.jsonl"),
    "export_label_counts": label_counts(run / "gen_export" / "gen_labels.local.jsonl"),
    "runner_report": load_json(run / "runner_report.qwen_local.json"),
    "parse_report": load_json(run / "parse_report.qwen_local.json"),
    "dedup_report": load_json(run / "dedup_report.qwen_local.json"),
    "judge_filter_report": load_json(run / "judge_filter_report.qwen_local.json"),
    "rulebook_quality_report": load_json(run / "rulebook_quality_report.qwen_local.json"),
    "gate_a_report": load_json(run / "gate_a_audit_report.qwen_local.json"),
    "export_report": load_json(run / "gen_export_report.json"),
}
(run / "quantitative_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(run / "quantitative_report.md").write_text(
    "\n".join(
        [
            "# Qwen Local 200 Quantitative Report",
            "",
            f"- run: `{run}`",
            f"- raw output rows: {summary['raw_output_rows']}",
            f"- parsed candidates: {summary['parsed_candidates']}",
            f"- parse rejects: {summary['parse_rejects']}",
            f"- dedup candidates: {summary['dedup_candidates']}",
            f"- dedup rejects: {summary['dedup_rejects']}",
            f"- judge accepted candidates: {summary['judge_accepted_candidates']}",
            f"- judge rejects: {summary['judge_rejects']}",
            f"- rule-book accepted candidates: {summary['rulebook_accepted_candidates']}",
            f"- rule-book rejected candidates: {summary['rulebook_rejected_candidates']}",
            f"- export input rows: {summary['export_input_rows']}",
            f"- export label rows: {summary['export_label_rows']}",
            f"- export label counts: `{json.dumps(summary['export_label_counts'], ensure_ascii=False, sort_keys=True)}`",
        ]
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
if summary["export_input_rows"] != limit or summary["export_label_rows"] != limit:
    raise SystemExit(3)
PY

printf '%s\n' "${RUN}" > "${RUN_ROOT}/completed_qwen_local_200_batch16.txt"
