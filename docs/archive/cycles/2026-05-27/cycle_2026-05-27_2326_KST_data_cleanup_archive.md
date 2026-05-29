<!-- Changed: archive the DATA-CLEANUP filesystem result for self_instruct runs. -->
<!-- Why: active docs need a dated record of what moved, what was deleted, and which final files remain active. -->

# 2026-05-27 23:26 KST DATA-CLEANUP Archive

## 결론

DATA-CLEANUP completed for `runs/self_instruct`. The active final artifact remains
`runs/self_instruct/targeted_schedule_20260527_192440_KST/manifest.record_count_preserved.codex_agent_fallback.jsonl`.
This cleanup is organizational only; it does not change the no-go boundary for provider provenance,
ablations, Gate D, package, or training.

## Archived

- `runs/self_instruct/official_restart_20260527_v1` moved to
  `runs/self_instruct/_archive/20260527_data_cleanup/official_restart_20260527_v1`.
- `runs/self_instruct/datagen_try_20260527_174226_KST` moved to
  `runs/self_instruct/_archive/20260527_data_cleanup/datagen_try_20260527_174226_KST`.
- Targeted pre-record-count-preserved files moved to
  `runs/self_instruct/_archive/20260527_data_cleanup/targeted_schedule_pre_record_count_preserved/`:
  `manifest.codex_agent_fallback.jsonl`,
  `manifest_selected_candidates.codex_agent_fallback.jsonl`,
  `manifest_selected_candidates.normalized.codex_agent_fallback.jsonl`,
  `manifest_report.{json,md}`,
  `manifest_validation.codex_agent_fallback.{json,md}`,
  `gate_b_comparison.manifest_selected.codex_agent_fallback.{json,md}`,
  `gate_c_equivalence.codex_agent_fallback.{json,md}`,
  `self_instruct_eval_summary.codex_agent_fallback.{json,md}`.

## Deleted

These targeted reject files were deleted only after `wc -l` confirmed `0` rows:

- `parse_rejects.codex_agent_fallback.jsonl`
- `dedup_rejects.codex_agent_fallback.jsonl`
- `judge_rejects.codex_agent_fallback.jsonl`
- `gate_a_rejects.codex_agent_fallback.jsonl`

## Active Files

Keep active under `runs/self_instruct/targeted_schedule_20260527_192440_KST/`:

- `manifest.record_count_preserved.codex_agent_fallback.jsonl`
- `manifest_selected_candidates.record_count_preserved.codex_agent_fallback.jsonl`
- `manifest_selected_candidates.normalized.record_count_preserved.codex_agent_fallback.jsonl`
- `manifest_report.record_count_preserved.{json,md}`
- `manifest_validation.record_count_preserved.codex_agent_fallback.{json,md}`
- `gate_b_comparison.manifest_selected.record_count_preserved.codex_agent_fallback.{json,md}`
- `gate_c_equivalence.record_count_preserved.codex_agent_fallback.{json,md}`
- `candidate_profile.manifest_selected.record_count_preserved.codex_agent_fallback.json`
- `target_schedule.json`, `generation_metadata.json`, `target_coverage.codex_agent_fallback.json`
- Raw/parse/dedup/judge/Gate A provenance files.

Protected roots were not touched: `runs/self_instruct/public20_baseline`, `data/local/public20`,
`runs/model_validation/public20_10_10_splits`, `runs/model_validation/public20_trl_sft_10_10`,
and `runs/model_validation/public20_trl_sft_10_10_augmented20`.

## Verification

- Final manifest rows `20`; labels `fail=10/pass=10`; splits `train=14`, `hidden=4`,
  `calibration=2`.
- Manifest validation `overall_gate_passed=true`.
- Gate B `no_go_warnings=[]`.
- Gate C `overall_pass=true`, `manifest_count=20`, `candidate_count=20`, `matched_count=20`.
