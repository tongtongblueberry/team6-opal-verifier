# 2026-05-26 07:42:41 KST - Step 1 P1 첫 config 중간평가

## 판단

- leaderboard 제출은 하지 않는다.
- 이유: `p1_r4_lr5e4_do20_ep5`는 P1 sweep의 첫 후보 하나만 완료한 상태이며, 전체 P1 후보 비교가 끝나지 않았다. 또한 직전 제출은 서버 이슈로 reject 되었고, 제출 가능 상태가 바뀌었다는 근거도 아직 없다.
- 현재 결과는 제출용 결론이 아니라 P1 sweep 중간평가 및 Step 2 문제 검증 입력으로 기록한다.

## 실행 상태

- run root: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep`
- 완료 config: `p1_r4_lr5e4_do20_ep5`
- train 완료 시각: 2026-05-26 07:41 KST 부근
- eval report:
  - JSON: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep/artifacts/p1_r4_lr5e4_do20_ep5.eval_manifest.json`
  - Markdown: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep/artifacts/p1_r4_lr5e4_do20_ep5.eval_manifest.md`
- 다음 config `p1_r8_lr5e4_do20_ep5`가 자동으로 시작되었다.
- 2026-05-26 07:42:41 KST 기준 다음 config GPU 상태:
  - GPU memory: 30381 / 46068 MiB
  - GPU utilization: 100%
  - OOM/Error: 관측 없음

## P2 평가 코드 반영 확인

- `bucket_metrics`: 포함됨
- `threshold_sweep`: 포함됨
- `threshold_sweep.risk_coverage_summary`: 포함됨

## base threshold 0.50 결과

| split | n | accuracy | fail precision | fail recall | fail F1 | macro F1 | ECE | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 143 | 0.930070 | 0.891892 | 0.970588 | 0.929577 | 0.930067 | 0.049274 | 0.063030 |
| calibration | 48 | 0.875000 | 0.827586 | 0.960000 | 0.888889 | 0.873016 | 0.107627 | 0.103353 |
| hidden | 95 | 0.957895 | 0.933333 | 0.976744 | 0.954545 | 0.957665 | 0.038430 | 0.042656 |

## threshold sweep 관찰

| threshold | calibration accuracy | calibration precision | calibration recall | hidden accuracy | hidden precision | hidden recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.895833 | 0.833333 | 1.000000 | 0.926316 | 0.860000 | 1.000000 |
| 0.35 | 0.895833 | 0.833333 | 1.000000 | 0.926316 | 0.860000 | 1.000000 |
| 0.40 | 0.895833 | 0.833333 | 1.000000 | 0.926316 | 0.860000 | 1.000000 |
| 0.45 | 0.895833 | 0.833333 | 1.000000 | 0.936842 | 0.877551 | 1.000000 |
| 0.50 | 0.875000 | 0.827586 | 0.960000 | 0.957895 | 0.933333 | 0.976744 |
| 0.55 | 0.875000 | 0.827586 | 0.960000 | 0.947368 | 0.931818 | 0.953488 |
| 0.60 | 0.875000 | 0.827586 | 0.960000 | 0.947368 | 0.931818 | 0.953488 |
| 0.65 | 0.875000 | 0.827586 | 0.960000 | 0.947368 | 0.931818 | 0.953488 |
| 0.70 | 0.875000 | 0.827586 | 0.960000 | 0.947368 | 0.931818 | 0.953488 |

## P0 relaxed best와 비교

- P0 calibration-first relaxed best: `r32_lr1e3_do10_ep5@threshold=0.30`
  - calibration: accuracy 0.895833, precision_fail 0.833333, recall_fail 1.000000
  - hidden no-peek: accuracy 0.936842, precision_fail 0.877551, recall_fail 1.000000
- P1 `p1_r4_lr5e4_do20_ep5`:
  - threshold 0.45에서 P0 relaxed best와 사실상 동일한 calibration/hidden fail tradeoff를 재현했다.
  - threshold 0.50에서는 hidden accuracy와 precision이 좋아지지만 calibration accuracy와 fail recall이 낮아진다.

## bucket/risk 관찰

- selective risk summary:
  - AURC: 0.185300
  - full coverage risk error rate: 0.524476
  - max coverage at zero error: 0.363636
- bucket summary:
  - length bucket은 전부 `chars_0000_0512`라 길이 기반 약점 판단은 아직 제한적이다.
  - split worst accuracy는 `calibration` 0.875000이다.
  - source bucket은 140개 bucket에 143개 sample이라 대부분 n=1이다. 단일 source worst만으로 일반화 결론을 내리면 안 된다.

## 다음 결정

- P1 sweep은 계속 진행한다. 첫 후보만으로 중단하거나 제출하지 않는다.
- `p1_r4` 결과는 낮은 rank와 강한 dropout으로도 P0 relaxed best 수준의 threshold tradeoff가 재현된다는 근거다.
- 다만 calibration precision이 0.833333 수준에서 constraint 0.90에 못 미치므로 Step 2 검증은 계속 필요하다.
- 데이터 구조 검증, 학습 구조 검증, 관련 논문 검증 에이전트를 분리해서 실행한다.
