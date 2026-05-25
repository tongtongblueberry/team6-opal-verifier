# 2026-05-26 08:29:03 KST - Step 1 P1 r8 중간평가

## 판단

- leaderboard 제출은 하지 않는다.
- 이유: `p1_r8_lr5e4_do20_ep5`는 Step3 1차 hard gate인 calibration precision_fail `>=0.90`을 통과하지 못했다.
- 또한 서버 제출 가능 상태가 개선되었다는 근거가 없고, P1 sweep은 아직 진행 중이다.

## 실행 상태

- run root: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep`
- 완료 config: `p1_r8_lr5e4_do20_ep5`
- eval JSON: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep/artifacts/p1_r8_lr5e4_do20_ep5.eval_manifest.json`
- 다음 config: `p1_r16_lr2e4_do20_ep5`
- 2026-05-26 08:29:03 KST 기준 다음 config GPU 상태:
  - GPU memory: 30393 / 46068 MiB
  - GPU utilization: 100%
  - OOM/Error: 관측 없음

## P2 평가 코드 반영 확인

- `bucket_metrics`: 포함됨
- `threshold_sweep.risk_coverage_summary`: 포함됨

## base threshold 0.50 결과

| split | n | accuracy | fail precision | fail recall | fail F1 | macro F1 | ECE | Brier | confusion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| overall | 143 | 0.923077 | 0.860759 | 1.000000 | 0.925170 | 0.923017 | 0.051504 | 0.060099 | TP=68, TN=64, FP=11, FN=0 |
| calibration | 48 | 0.895833 | 0.833333 | 1.000000 | 0.909091 | 0.893570 | 0.104368 | 0.100980 | TP=25, TN=18, FP=5, FN=0 |
| hidden | 95 | 0.936842 | 0.877551 | 1.000000 | 0.934783 | 0.936779 | 0.034662 | 0.039443 | TP=43, TN=46, FP=6, FN=0 |

## recall >= 0.95 조건의 precision 최대 operating point

- calibration 기준 best threshold: `0.50`
- calibration precision_fail: `0.833333`
- calibration recall_fail: `1.000000`
- calibration accuracy: `0.895833`
- 결론: recall 조건은 만족하지만 precision hard gate `0.90`에는 미달한다.

## r4와 비교

- r4@0.50:
  - calibration precision 0.827586, recall 0.960000, accuracy 0.875000, ECE 0.107627
  - hidden precision 0.933333, recall 0.976744, accuracy 0.957895, ECE 0.038430
- r8@0.50:
  - calibration precision 0.833333, recall 1.000000, accuracy 0.895833, ECE 0.104368
  - hidden precision 0.877551, recall 1.000000, accuracy 0.936842, ECE 0.034662

해석:
- r8은 calibration accuracy/recall/ECE를 약간 개선했지만, calibration precision은 여전히 0.833333 수준이다.
- hidden precision과 hidden accuracy는 r4보다 나빠졌다.
- 따라서 r8은 Step3 1차 목표 통과 후보가 아니다.

## 다음 결정

- P1 sweep은 계속 진행한다.
- 현재 시작된 `p1_r16_lr2e4_do20_ep5` 결과를 기다린다.
- r4/r8 결과만 보면 rank 증가 자체가 calibration precision hard gate를 해결한다는 근거는 아직 없다.
- rule engine은 architecture에 추가하지 않는다.
