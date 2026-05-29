# Gate C Manifest/Model Input Equivalence

- candidates: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST/gate_a_accepted.normalized.trajectory_signature.codex_agent_fallback.jsonl`
- manifest: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST/manifest.trajectory_signature.record_count_preserved.codex_agent_fallback.jsonl`
- overall_pass: `True`
- candidate_count: `25`
- manifest_count: `25`
- matched_count: `25`

## Issues
- none

## Trainer Loader

- loaded: `True`
- total_rows: `25`
- train_rows: `18`
- skipped_non_train_rows: `7`
- sample_id_set_match: `True`
- row_count_match: `True`

## Warnings

- `eval_solver_prompt_mismatch_possible`: trainer/eval manifest paths should use raw manifest input; submission solver prompt format must be audited separately without importing runtime solver here.
- `prompt_renderer_scope`: Gate C checks trainer build_messages only. eval/submission solver prompt renderers are not imported here.
- `first_forward_not_executed`: No tokenizer/model is loaded in this tool; heavy first-forward smoke belongs to package/runtime gates.
