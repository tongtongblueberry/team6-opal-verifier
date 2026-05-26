# 2026-05-26 KST 06:52:51 - Step6 P0 calibration-first 재판정 결과

## 구조 Skeleton
- 목적
- 실행
- 결과
- 해석
- 다음 결정

## 목적
- 기존 Cycle 3 sweep 결과를 새 P0 구현으로 다시 판정했다.
- hidden split으로 threshold를 고른 기존 후보가 calibration-first gate를 통과하는지 확인했다.

## 실행
- 서버 repo: `/workspace/team6/team6-opal-verifier`
- sweep JSON: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep/artifacts/manifest_lora_sweep_results.json`
- output JSON: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep/artifacts/calibration_first_candidate_final.json`
- output MD: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep/artifacts/calibration_first_candidate_final.md`
- tool hash:
  - `tools/eval/eval_manifest_adapter.py`: `684e0c5b190c6d1ef7188bb3255e26150ba6ba1d3d37dbfdb231a4ddf80c3cac`
  - `tools/eval/select_manifest_sweep_candidate.py`: `0f326dc0b849db01be126c0056dc7de7c863eb44f9f48077bc49b53a05ff7900`
  - `tools/training/run_manifest_lora_sweep.py`: `fec58da635415fc3cf30b284b11e1305656e453835272a7962b81ef7f4ba7ebe`
- output hash:
  - JSON: `910dcc4c10e4e5ac59b130ab4053ee664a8b38c6c768e6363bf53384c802cffe`
  - Markdown: `e179492a283e507a1a8d0bea78db230fe3aed190eb4f05311682d5edd5ef309e`

## 결과
- split: `calibration`
- selection metric: `metrics.by_split.calibration.accuracy`
- precision constraint: `metrics.by_split.calibration.precision_fail >= 0.9`
- recall constraint: `metrics.by_split.calibration.recall_fail >= 0.8`
- candidate thresholds: `45`
- constraint-satisfying thresholds: `0`
- best: `None`
- relaxed best:
  - config: `r32_lr1e3_do10_ep5`
  - threshold: `0.30`
  - calibration accuracy: `0.8958333333333334`
  - calibration precision_fail: `0.8333333333333334`
  - calibration recall_fail: `1.0`
  - constraints_satisfied: `false`
- relaxed best hidden no-peek:
  - accuracy: `0.9368421052631579`
  - precision_fail: `0.8775510204081632`
  - recall_fail: `1.0`
  - ECE: `0.049137369809135474`
  - Brier: `0.04937571586646841`
  - confusion: `TP=43, TN=46, FP=6, FN=0`

## 해석
[Original Text/Data] calibration-first selector에서 제약 만족 후보가 `0`개다.

[Exact Interpretation] 기존 sweep의 hidden-selected 후보는 Step3의 calibration-first gate를 통과하지 못한다.

[Detailed Explanation/Example] 기존 hidden best `r16_lr5e4_do10_ep5@0.70`은 hidden metric이 좋았지만, calibration-first 기준에서는 fail precision hard target `0.90`을 넘는 threshold 후보가 없다. relaxed best도 precision `0.8333`으로 부족하다.

## 다음 결정
- 동일 후보를 추가 leaderboard 제출하지 않는다.
- Step4에서 정한 P1 보수적 LoRA/QLoRA sweep으로 이동한다.
- P1은 r32/r64 확대가 아니라 `r={4,8,16}`, 낮은 LR, dropout/regularization 중심으로 진행한다.
- batch size는 기존 r64 학습이 완료된 `batch_size=2, grad_accum=4`를 초기값으로 사용하되, GPU monitor agent가 OOM/VRAM 사용률을 보고 조정한다.
