# Cycle 기록 - runs/tests cleanup

<!-- Changed: preserve the cleanup rationale after deleting raw/probe run artifacts. -->
<!-- Why: raw LLM outputs can contain full generated text and should not remain in git-facing run directories when only verdict-level evidence is needed. -->

## Scope

- 기준 시각: 2026-05-26 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- active spec source: `docs/legacy_spec_rules.md`
- runtime rule engine: 금지
- public20 역할: train/val 기준 및 synthetic Gate B reference/profile
- hidden leaderboard 역할: test
- `sample.md`: Gate A/B/C full pass 전 생성 금지

## Moved Spec Source

[Original Text/Data] -> archive-only legacy spec source

[Exact Interpretation] -> active synthetic grounding source가 archive-only 위치에 남아 있었다.

[Detailed Explanation/Example] -> active generation/gate 문서가 참조해야 하는 spec source를 `docs/legacy_spec_rules.md`로 이동했다. legacy archive에는 과거 decision/evidence 문서만 남기고, 현재 spec-grounded synthetic planning은 root `docs/` 바로 아래 source를 기준으로 한다.

## Runs Deleted

[Original Text/Data] -> `runs/self_instruct/external_llm_probe/`

[Exact Interpretation] -> external probe는 Gate A `pass`, Gate B `insufficient`, Gate C `no_go`였고 active accepted synthetic 후보가 아니다.

[Detailed Explanation/Example] -> generated count `1` probe는 public20 count `20`, public aggregate `pass=10/fail=10`와 비교해 Gate B가 부족했다. raw Gemini generation, prompt, judge request/result, parsed candidate, dedup intermediate, probe-local gate outputs는 accepted data나 reusable baseline이 아니므로 삭제했다.

[Original Text/Data] -> `runs/self_instruct/gemini_batch_v2/`

[Exact Interpretation] -> batch v2는 Gate A `pass`, Gate B `conditional pass`, Gate C `pass`였지만 strict full-pass 기준에서는 accepted sample publication 자격이 없었다.

[Detailed Explanation/Example] -> 9 accepted candidates는 qualitative/equivalence check를 통과했지만, pool size와 distribution 폭이 public20 reference보다 좁아 Gate B가 conditional이었다. `sample.md`를 만들지 않았고 training-ready accepted synthetic으로 승격하지 않았으므로 raw generation, prompt, judge, manifest, normalized candidate, gate intermediates를 삭제했다.

[Original Text/Data] -> `runs/self_instruct/gemini_batch_v3/`

[Exact Interpretation] -> batch v3는 spec-grounded source 없이 shape/profile 중심으로 생성된 ungrounded output이다.

[Detailed Explanation/Example] -> v3 verdict는 accepted synthetic use `no`, Gate A/B/C candidate eligibility `no`, sample eligibility `no`였다. raw generation, retry output, prompt request, generation request, ungrounded verdict, regeneration draft request는 active accepted data가 아니므로 삭제했다. 향후 재생성은 `docs/legacy_spec_rules.md`에서 retrieved rule context와 source line provenance를 포함해야 한다.

## Runs Retained

[Original Text/Data] -> `runs/self_instruct/public20_baseline/`

[Exact Interpretation] -> public20 reference reports and profiles are still active Gate A/B baselines.

[Detailed Explanation/Example] -> `gate_a/public20_reference_audit_report.*`, `gate_a/public20_reference_audit_pack.md`, `gate_b/public20.profile.json`, `gate_b/public20.normalized.jsonl`, and profile verification reports are retained because synthetic quality gates compare candidates against these public20 references.

[Original Text/Data] -> `runs/model_validation/public20_splits/`

[Exact Interpretation] -> public20 train/val split artifacts are active model-validation inputs.

[Detailed Explanation/Example] -> `split_seed_11`, `split_seed_29`, and `split_seed_47` train/val JSONL files and split reports are retained because public20 is the train/val 기준 while hidden leaderboard remains test.

## Tests Deleted

[Original Text/Data] -> `tests/__pycache__/`

[Exact Interpretation] -> compiled bytecode cache is not source test coverage and is not connected to active code semantics.

[Detailed Explanation/Example] -> `.pyc` files under `tests/__pycache__/` were deleted. Running tests with `PYTHONDONTWRITEBYTECODE=1` avoids recreating them during verification.

## Tests Retained

[Original Text/Data] -> `tests/test_build_public20_train_val_split.py`, `tests/test_audit_public20_reference.py`, `tests/test_compare_public20_dimensions.py`

[Exact Interpretation] -> public20 split/reference/profile tests remain active.

[Detailed Explanation/Example] -> These tests cover the public20 train/val split and Gate B reference/profile comparison surface requested for retention.

[Original Text/Data] -> Self-Instruct tests in `tests/test_self_instruct_candidate_schema.py`, `tests/test_self_instruct_seed_schema.py`, `tests/test_parse_self_instruct_outputs.py`, `tests/test_dedup_self_instruct_candidates.py`, `tests/test_filter_self_instruct_judge.py`, `tests/test_audit_self_instruct_quality.py`, `tests/test_self_instruct_final_response_invariant.py`, `tests/test_validate_manifest_shape_gates.py`, `tests/test_build_supervised_manifest.py`, `tests/test_check_manifest_model_input_equivalence.py`

[Exact Interpretation] -> schema/parser/invariant/judge/gate/equivalence coverage remains active.

[Detailed Explanation/Example] -> These tests import active `tools/datagen` and `tools/analysis` modules. They do not depend on removed v4/v4.1 generators or runtime rule engine execution.

[Original Text/Data] -> training/evaluator/package tests in `tests/test_train_manifest_full.py`, `tests/test_eval_manifest_full_model.py`, `tests/test_train_manifest_lora_cli.py`, `tests/test_run_manifest_lora_sweep.py`, `tests/test_prepare_public20_sft_dataset.py`, `tests/test_run_trl_sft_public20.py`, `tests/test_eval_trl_sft_public20_generation.py`, `tests/test_eval_manifest_adapter_metrics.py`, `tests/test_select_manifest_sweep_candidate.py`, `tests/test_prepare_submit_script.py`, `tests/test_submit_package_readiness.py`, `tests/test_runtime_smoke_submit_package.py`, `tests/test_solver_merged_model_path.py`

[Exact Interpretation] -> full FT evaluator, active TRL/LoRA adapter, sweep selection, solver artifact loading, and packaging tests remain active.

[Detailed Explanation/Example] -> These tests target active `tools/training`, `tools/eval`, and `src/solver.py` behavior. Rule-engine marker tests in packaging readiness are retained because they enforce the LLM-only no-rule package gate rather than testing a rule runtime.
