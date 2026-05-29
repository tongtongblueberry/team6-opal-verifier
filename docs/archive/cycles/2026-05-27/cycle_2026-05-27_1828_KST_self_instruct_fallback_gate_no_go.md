<!-- Changed: archive the codex_agent_fallback DATA-GATE result. -->
<!-- Why: future workers need a dated record that the fallback artifacts are not Gemini/provider data and are not training eligible. -->

# 2026-05-27 18:28 KST Self-Instruct Fallback Gate No-Go

## Scope

- Updated active docs: `PROGRESS.md`, `docs/current_task.md`, `docs/current_self_instruct_data_plan.md`, `docs/agent_handoff.md`, `docs/server_operations_current.md`.
- This record covers data provenance, parser/dedup/judge/Gate A/B/C, manifest validation, ablation, sample, and verification status.

## Data Provenance

- Server Gemini check at `team6` showed `GEMINI_API_KEY=false`, `GOOGLE_API_KEY=false`; no real Gemini raw output was created.
- Agent fallback generation used `runs/self_instruct/official_restart_20260527_v1/01_generation_requests/generation_requests.jsonl` because it had 4 official requests.
- Created fallback artifacts under `runs/self_instruct/official_restart_20260527_v1/02_raw_generation/`, including `raw_outputs.codex_agent_fallback.jsonl`, parsed/dedup/judge/gate reports. This is explicitly `codex_agent_fallback`, not Gemini/provider data.

## Gate Results

- Raw wrapper rows `4`; candidates `12`; parser accepted `12` rejected `0`; dedup accepted `12` rejected `0`; Gate A hard invariant `12` pass `0` fail; initial label distribution `pass=8` `fail=4`.
- Judge decisions: `12` total, `11` accepted, `1` rejected. Judge provenance `codex_agent_fallback_judge`, not Gemini.
- Rejected `codex-agent-fallback-self-instruct-gen-00003-02` because RULE 21 ACL support was not established by record state.
- Gate A qualitative fallback audit reviewed all `11` judge-accepted candidates and accepted `11`.
- Gate B no-go: `record_count_mean_difference`; generated mean `2.09` vs public20 mean `16.4`; labels after Gate A `pass=8` `fail=3` vs public20 `pass=10` `fail=10`.
- Gate C manifest/model-input equivalence passed.
- Manifest validation failed due `length_jsd_lte_threshold` and `split_label_counts_nonzero_where_possible`.
- Ablations `200/500/1000/2000/4000` blocked by count; only `11` accepted candidates.

## Decision

- `docs/samples/self_instruct_sample.md` remains absent/no-go.
- Generated synthetic data training eligibility is `false`.
- Focused Self-Instruct/data-gate tests `49 OK`; `git diff --check OK`.
