#!/usr/bin/env bash
# Self-Instruct Output-First Pipeline — Local Watcher
# Polls server for new raw outputs, runs the full filtering pipeline locally.
#
# Usage:
#   bash runs/new/watch.sh
#
# Or one-shot (combine only, no loop):
#   WATCH_COMBINE_ONCE=1 bash runs/new/watch.sh
set -euo pipefail

# --- Config ---
SSH_ALIAS="${SSH_ALIAS:-team6}"
REMOTE_REPO="${REMOTE_REPO:-/workspace/sinjeongmin_opal_verifier/repo}"
SLEEP_SECONDS="${SLEEP_SECONDS:-60}"

# Read latest run from server
REMOTE_RUN_FILE="runs/new/latest_run.txt"

# Local directories
LOCAL_ROOT="runs/new/local_mirror"
CURRENT_DIR="${LOCAL_ROOT}/current"
COMBINED_DIR="${LOCAL_ROOT}/combined"
EXPORT_DIR="data/local/gen_new"

export LOCAL_ROOT CURRENT_DIR COMBINED_DIR EXPORT_DIR

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=30 -o ControlMaster=no -o ControlPath=none)

mkdir -p "${CURRENT_DIR}" "${COMBINED_DIR}" "${EXPORT_DIR}"

LAST_LINES_FILE="${CURRENT_DIR}/last_raw_lines.txt"
if [[ ! -f "${LAST_LINES_FILE}" ]]; then
  printf '0\n' > "${LAST_LINES_FILE}"
fi

log() {
  printf '%s %s\n' "$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S KST')" "$*"
}

# --- Pull raw outputs from server ---
remote_run_dir() {
  ssh "${SSH_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && cat '${REMOTE_RUN_FILE}' 2>/dev/null || echo ''"
}

remote_raw_lines() {
  local run="$1"
  ssh "${SSH_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && p='${run}/raw_outputs.jsonl'; [ -e \"\$p\" ] && wc -l < \"\$p\" || echo 0"
}

pull_raw() {
  local run="$1" lines="$2"
  ssh "${SSH_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && head -n '${lines}' '${run}/raw_outputs.jsonl'" \
    > "${CURRENT_DIR}/raw_outputs.jsonl"
  scp -q "${SSH_OPTS[@]}" \
    "${SSH_ALIAS}:${REMOTE_REPO}/${run}/generation_requests.jsonl" \
    "${CURRENT_DIR}/generation_requests.jsonl" 2>/dev/null || true
}

# --- Filtering pipeline (Phase 4) ---
run_filters() {
  log "=== [4-1] Parse validity ==="
  python3 tools/datagen/parse_self_instruct_outputs.py \
    --input "${CURRENT_DIR}/raw_outputs.jsonl" \
    --output "${CURRENT_DIR}/parsed_candidates.jsonl" \
    --reject-output "${CURRENT_DIR}/parse_rejects.jsonl" \
    --report-json "${CURRENT_DIR}/parse_report.json" \
    --profile-output "${CURRENT_DIR}/candidate_profile.json"

  log "=== [4-2] Final-response invariant ==="
  python3 tools/analysis/self_instruct_invariants.py \
    "${CURRENT_DIR}/parsed_candidates.jsonl" \
    --output-jsonl "${CURRENT_DIR}/invariant_audit.jsonl"

  log "=== [4-3] Dedup (ROUGE-L 0.7) ==="
  python3 tools/analysis/dedup_self_instruct_candidates.py \
    --input "${CURRENT_DIR}/parsed_candidates.jsonl" \
    --output "${CURRENT_DIR}/dedup_candidates.jsonl" \
    --reject-output "${CURRENT_DIR}/dedup_rejects.jsonl" \
    --report-json "${CURRENT_DIR}/dedup_report.json" \
    --public20-reference-jsonl data/local/public20/public20_input.jsonl

  log "=== [4-4] LLM Judge payload ==="
  python3 tools/analysis/filter_self_instruct_judge.py \
    --candidates "${CURRENT_DIR}/dedup_candidates.jsonl" \
    --requests-output "${COMBINED_DIR}/judge_requests.jsonl" \
    --metadata-json "${COMBINED_DIR}/judge_metadata.json" \
    --model adversarial-gate-a-docs-agent

  log "=== [4-5] Adversarial rule-book gate ==="
  python3 tools/analysis/adversarial_rulebook_quality_gate.py \
    --candidates "${CURRENT_DIR}/dedup_candidates.jsonl" \
    --accepted-output "${COMBINED_DIR}/accepted.jsonl" \
    --rejected-output "${COMBINED_DIR}/rejected.jsonl" \
    --decisions-output "${COMBINED_DIR}/decisions.jsonl" \
    --report-json "${COMBINED_DIR}/rulebook_report.json" \
    --rulebook-md docs/legacy_spec_rules.md \
    --generation-requests-jsonl "${CURRENT_DIR}/generation_requests.jsonl"

  log "=== [4-7] Qualitative audit (Gate A) ==="
  python3 tools/analysis/audit_self_instruct_quality.py \
    --accepted-jsonl "${COMBINED_DIR}/accepted.jsonl" \
    --sample-size 40 \
    --seed 20260529 \
    --invariant-jsonl "${COMBINED_DIR}/gate_a_invariants.jsonl" \
    --audit-pack-md "${COMBINED_DIR}/gate_a_audit_pack.md" \
    --audit-report-json "${COMBINED_DIR}/gate_a_report.json" \
    --audit-report-md "${COMBINED_DIR}/gate_a_report.md" \
    2>/dev/null || log "audit_self_instruct_quality.py skipped (no accepted rows?)"

  log "=== [5-1] Export to public20 schema ==="
  python3 tools/datagen/export_self_instruct_gen_public_schema.py \
    --candidates-jsonl "${COMBINED_DIR}/accepted.jsonl" \
    --output-dir "${EXPORT_DIR}" \
    --limit 0 \
    --sample-id-prefix gen \
    --source self_instruct_output_first_v2 \
    --report-json "${COMBINED_DIR}/export_report.json" \
    --clean-output-dir \
    2>/dev/null || log "export skipped (no accepted rows?)"

  # --- [4-6] Public20 quantitative comparison ---
  log "=== [4-6] Public20 comparison report ==="
  python3 - <<'REPORT_PY'
import json, collections
from pathlib import Path

export_dir = Path("${EXPORT_DIR}")
inp_path = export_dir / "gen_input.jsonl"
lbl_path = export_dir / "gen_labels.local.jsonl"
pub_inp = Path("data/local/public20/public20_input.jsonl")
pub_lbl = Path("data/local/public20/public20_labels.local.jsonl")
combined = Path("${COMBINED_DIR}")

def load_jsonl(p):
    if not p.exists(): return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

gen_inputs = load_jsonl(inp_path)
gen_labels = {r["sample_id"]: r["label"] for r in load_jsonl(lbl_path)}
pub_inputs = load_jsonl(pub_inp)
pub_labels = {r["sample_id"]: r["label"] for r in load_jsonl(pub_lbl)}

# Record counts
gen_rc = collections.Counter()
pub_rc = collections.Counter()
for r in gen_inputs:
    recs = json.loads(r["input"]).get("records", [])
    gen_rc[len(recs)] += 1
for r in pub_inputs:
    recs = json.loads(r["input"]).get("records", [])
    pub_rc[len(recs)] += 1

missing_rc = sorted(k for k in pub_rc if k not in gen_rc)

# Auth session rate
def auth_rate(rows):
    total = len(rows)
    if not total: return 0.0
    auth = 0
    for r in rows:
        recs = json.loads(r["input"]).get("records", [])
        for rec in recs:
            inp = rec.get("input", {})
            if not isinstance(inp, dict): continue
            m = inp.get("method", {})
            if not isinstance(m, dict): continue
            args_str = json.dumps(m.get("args", {}))
            if "HostChallenge" in args_str or "HostSigningAuthority" in args_str:
                auth += 1
                break
    return round(auth / total, 4)

# Label distribution
gen_label_ct = collections.Counter(gen_labels.values())

# Shortcut detection: can record_count predict label >80%?
rc_label = collections.defaultdict(collections.Counter)
for r in gen_inputs:
    sid = r["sample_id"]
    rc = len(json.loads(r["input"]).get("records", []))
    rc_label[rc][gen_labels.get(sid, "?")] += 1
shortcut_hits = sum(max(c.values()) for c in rc_label.values() if c)
shortcut_total = sum(sum(c.values()) for c in rc_label.values())
shortcut_rate = round(shortcut_hits / shortcut_total, 4) if shortcut_total else 0

report = {
    "gen_total": len(gen_inputs),
    "gen_labels": dict(gen_label_ct),
    "gen_record_counts": dict(sorted(gen_rc.items())),
    "pub_record_counts": dict(sorted(pub_rc.items())),
    "missing_public_record_counts": missing_rc,
    "gen_auth_rate": auth_rate(gen_inputs),
    "pub_auth_rate": auth_rate(pub_inputs),
    "record_count_label_shortcut_rate": shortcut_rate,
    "warnings": [],
}
if missing_rc:
    report["warnings"].append(f"missing_record_counts:{missing_rc}")
if report["gen_auth_rate"] < report["pub_auth_rate"]:
    report["warnings"].append(f"auth_rate_low:{report['gen_auth_rate']}<{report['pub_auth_rate']}")
if shortcut_rate > 0.8:
    report["warnings"].append(f"record_count_shortcut_high:{shortcut_rate}")

out = combined / "public20_comparison.json"
out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(report, indent=2, ensure_ascii=False))
REPORT_PY

  log "=== Filter pipeline complete ==="
  # Summary
  if [[ -f "${COMBINED_DIR}/rulebook_report.json" ]]; then
    python3 -c "
import json
r = json.load(open('${COMBINED_DIR}/rulebook_report.json'))
print(f\"  Accepted: {r.get('accepted_count', 0)}\")
print(f\"  Rejected: {r.get('rejected_count', 0)}\")
"
  fi
  if [[ -f "${COMBINED_DIR}/export_report.json" ]]; then
    python3 -c "
import json
r = json.load(open('${COMBINED_DIR}/export_report.json'))
print(f\"  Exported: {r.get('exported_count', r.get('effective_limit', 0))}\")
"
  fi
}

# --- One-shot mode ---
if [[ "${WATCH_COMBINE_ONCE:-0}" == "1" ]]; then
  run_filters
  exit 0
fi

# --- Watcher loop ---
log "Starting watcher (poll every ${SLEEP_SECONDS}s)"
while true; do
  run_dir="$(remote_run_dir 2>/dev/null || echo '')"
  if [[ -z "${run_dir}" ]]; then
    log "No active run found on server"
    sleep "${SLEEP_SECONDS}"
    continue
  fi

  raw_lines="$(remote_raw_lines "${run_dir}" 2>/dev/null || echo 0)"
  last_lines="$(cat "${LAST_LINES_FILE}")"
  log "run=${run_dir} raw=${raw_lines} last=${last_lines}"

  # Check server process status
  ssh "${SSH_OPTS[@]}" "${SSH_ALIAS}" \
    "cd '${REMOTE_REPO}' && nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader" \
    2>/dev/null || true

  if [[ "${raw_lines}" -gt "${last_lines}" ]]; then
    log "New data detected: ${last_lines} → ${raw_lines}"
    pull_raw "${run_dir}" "${raw_lines}"
    run_filters
    printf '%s\n' "${raw_lines}" > "${LAST_LINES_FILE}"
  fi

  sleep "${SLEEP_SECONDS}"
done
