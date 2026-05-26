# Cycle 기록 - legacy workspace cleanup 1단계

- 시각: 2026-05-26 12:05 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: active LLM-only manifest cycle에서 과거 `/workspace/team6` pipeline을 분리한다.

## 결론

- active manifest 학습/평가 파일은 유지했다.
- tracked legacy pipeline shell과 과거 training archive 파일만 `tools/archive/legacy_rule_pipeline/training/`으로 이동했다.
- `tools/**/__pycache__`는 로컬 부산물이므로 제거했다.
- 이번 정리는 code path를 바꾸지 않고, 실수 실행 위험을 낮추는 구조 정리다.

## 이동한 파일

- `tools/training/run_full_pipeline.sh` → `tools/archive/legacy_rule_pipeline/training/run_full_pipeline.sh`
- `tools/training/run_9b_pipeline.sh` → `tools/archive/legacy_rule_pipeline/training/run_9b_pipeline.sh`
- `tools/training/archive/cycle2_train.py` → `tools/archive/legacy_rule_pipeline/training/cycle2_train.py`
- `tools/training/archive/cycle3_train.py` → `tools/archive/legacy_rule_pipeline/training/cycle3_train.py`

## 유지한 active 파일

- `tools/training/train_manifest_lora.py`
- `tools/training/train_manifest_full.py`
- `tools/training/run_manifest_lora_sweep.py`
- `tools/eval/eval_manifest_adapter.py`
- `tools/eval/select_manifest_sweep_candidate.py`
- `tools/eval/prepare_submit.sh`
- `tools/eval/prepare_submission.sh`
- `tools/eval/check_submit_package.py`
- `tools/eval/runtime_smoke_submit_package.py`
- `tools/analysis/build_supervised_manifest.py`
- `tools/analysis/validate_manifest.py`
- `tools/analysis/data_audit.py`
- `tools/datagen/generate_long_shape_source.py`

## 남은 정리 대상

- `tools/training`의 rule-id/uncertainty 계열 legacy trainer
- `tools/eval`의 과거 public/rule evaluation 스크립트
- `tools/analysis`의 rule coverage/metamorphic legacy script
- `tools/datagen`의 과거 rule/spec/mutation/distillation generator

## 제출 판단

- cleanup만으로 leaderboard 제출 사유는 생기지 않는다.
- 새 제출은 여전히 학습 완료, calibration/hidden 평가, package `<12GB`, offline smoke가 필요하다.
