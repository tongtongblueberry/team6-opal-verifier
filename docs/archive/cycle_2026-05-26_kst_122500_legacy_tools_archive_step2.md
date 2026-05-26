# Cycle 기록 - legacy tools archive 2단계

- 시각: 2026-05-26 12:25 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: active `tools/` 루트에서 과거 rule/public 중심 실험 도구를 분리한다.

## 결론

- active manifest cycle에 필요한 파일만 `tools/training`, `tools/eval`, `tools/analysis`, `tools/datagen` 루트에 남겼다.
- 과거 `/workspace/team6`, uncertainty resolver, public/rule eval, mutation/spec/gap generator 계열은 `tools/archive/legacy_rule_pipeline/tools/` 아래로 이동했다.
- `generate_long_shape_source.py`가 의존하는 `generate_long_trajectories.py`, `generate_spec_data.py`, `generate_gap_data.py`는 active datagen에 유지했다.
- `format_v4.py`는 `finetune_lora_v2.py` 의존 때문에 legacy archive로 함께 이동했다.

## 유지한 active 파일

- `tools/datagen/generate_long_shape_source.py`
- `tools/datagen/generate_long_trajectories.py`
- `tools/datagen/generate_spec_data.py`
- `tools/datagen/generate_gap_data.py`
- `tools/analysis/build_supervised_manifest.py`
- `tools/analysis/validate_manifest.py`
- `tools/analysis/data_audit.py`
- `tools/training/train_manifest_lora.py`
- `tools/training/train_manifest_full.py`
- `tools/training/run_manifest_lora_sweep.py`
- `tools/training/brier_trainer.py`
- `tools/training/deploy_and_train.sh`
- `tools/eval/eval_manifest_adapter.py`
- `tools/eval/select_manifest_sweep_candidate.py`
- `tools/eval/prepare_submit.sh`
- `tools/eval/prepare_submission.sh`
- `tools/eval/check_submit_package.py`
- `tools/eval/runtime_smoke_submit_package.py`
- `tools/eval/export_merged_model.py`
- `tools/eval/merge_adapters.py`

## 이동한 범주

- 과거 rule/spec/mutation/gap/distillation data generator
- uncertainty resolver와 legacy LoRA sweep/training script
- public/rule 기반 legacy eval script
- rule coverage/metamorphic coverage legacy analysis script

## 판단

- 이 commit은 active 학습 방법을 바꾸지 않는다.
- 목적은 active LLM-only manifest path와 legacy rule/public path를 분리하는 것이다.
- leaderboard 제출 사유는 아니다.
