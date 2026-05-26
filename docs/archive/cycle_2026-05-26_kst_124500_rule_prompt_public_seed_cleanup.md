# Cycle 기록 - rule-prompt/public-seed cleanup

- 시각: 2026-05-26 12:45 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: active 경로에서 rule-prompt 실험 solver와 public label 오염 경로를 제거한다.

## 결론

- 제출 entrypoint는 `src/solver.py`만 유지한다.
- rule-prompt/27B public-eval 실험 solver와 public label 평가가 섞인 legacy prepare script는 archive로 이동했다.
- `generate_spec_data.py --include-public-seed`는 hard-fail로 바꿨다.
- leaderboard 제출 사유는 생기지 않는다. 서버 학습 상태, v4.1 strict gate, package smoke가 여전히 필요하다.

## 이동한 파일

- `src/spec_solver.py` → `tools/archive/legacy_rule_pipeline/src/spec_solver.py`
- `src/solver_27b.py` → `tools/archive/legacy_rule_pipeline/src/solver_27b.py`
- `tools/eval/test_27b_logit.py` → `tools/archive/legacy_rule_pipeline/tools/eval/test_27b_logit.py`
- `tools/eval/test_27b_submission.sh` → `tools/archive/legacy_rule_pipeline/tools/eval/test_27b_submission.sh`
- `tools/eval/prepare_submission.sh` → `tools/archive/legacy_rule_pipeline/tools/eval/prepare_submission.sh`

## Public Seed Gate

[Original Text/Data] `tools/datagen/generate_spec_data.py`에는 `--include-public-seed` 옵션이 있었고, 켜면 `training_cases.json` 중 `source`가 `public:`으로 시작하는 row를 supervised train에 추가할 수 있었다.
→ [Exact Interpretation] 기본값은 안전하지만, 실수로 옵션을 켜면 public/eval label이 학습 데이터로 들어갈 수 있었다.
→ [Detailed Explanation/Example] 해당 옵션은 이제 `parser.error("--include-public-seed is disabled by the LLM-only data contract")`로 즉시 실패한다.

## 남긴 active 경로

- `src/solver.py`
- `src/__init__.py`
- `tools/eval/prepare_submit.sh`
- `tools/eval/check_submit_package.py`
- `tools/eval/runtime_smoke_submit_package.py`
- `tools/eval/eval_manifest_adapter.py`
- `tools/training/train_manifest_lora.py`
- `tools/training/train_manifest_full.py`
- `tools/analysis/build_supervised_manifest.py`
- `tools/analysis/validate_manifest.py`
- `tools/datagen/generate_long_shape_source.py`
- `tools/datagen/generate_long_trajectories.py`
- `tools/datagen/generate_spec_data.py`
- `tools/datagen/generate_gap_data.py`

## 검증 기준

- active `src`에 rule-prompt 실험 solver가 남지 않아야 한다.
- `generate_spec_data.py --include-public-seed`는 nonzero exit이어야 한다.
- package readiness와 v4.1 datagen tests는 계속 통과해야 한다.
