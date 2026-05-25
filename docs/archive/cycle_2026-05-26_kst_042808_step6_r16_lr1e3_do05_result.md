# 2026-05-26 KST 04:28 - Cycle 3 Step 6 r16_lr1e3_do05_ep5 결과

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- run root: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep`
- config: `r16_lr1e3_do05_ep5`
- train report: `artifacts/r16_lr1e3_do05_ep5.train_report.json`
- eval report: `artifacts/r16_lr1e3_do05_ep5.eval_manifest.json`
- 다음 진행: `r32_lr1e3_do10_ep5` 학습 중

## Hash

- train report: `64cf17917fff1c02667958b21424c766883f66aaf53893196c6bb6d0443a51c0`
- eval report: `35d03e70324da09c1806f71480b3d19e88655b8241b5e38e478dbc14fac3a719`
- sweep results snapshot: `605e482c7e01eb2860d2f7812ab49e0c4ea04cd84d348ba1e9e027b44634324d`

## 학습 설정

[Original Text/Data] → `lr=0.001`, `epochs=5.0`, `batch_size=2`, `grad_accum=4`, `max_seq_len=2048`, `lora_r=16`, `lora_alpha=32`, `lora_dropout=0.05`, `seed=42`.

[Exact Interpretation] → `r16_lr1e3_do10_ep5`와 learning rate, rank, alpha는 유지하고 dropout만 `0.10`에서 `0.05`로 낮춘 비교 실험이다.

[Detailed Explanation/Example] → Step 4에서 결정한 normalization/sweep 축 중 regularization 강도 축이다. 같은 r16 용량에서 dropout 감소가 hidden-like split의 false positive와 calibration을 어떻게 바꾸는지 검증한다.

## 학습 결과

[Original Text/Data] → `dataset_examples=337`, `trainable_params=3145728`, `training_loss=8.33230771796648`, `elapsed_seconds=2715.9785902500153`.

[Exact Interpretation] → 5 epoch 학습은 정상 완료됐고, loss는 현재 완료된 r16 계열 중 가장 낮다.

[Detailed Explanation/Example] → `r16_lr1e3_do10_ep5`의 loss `8.3482328282`, `r16_lr5e4_do10_ep5`의 loss `8.5080056834`보다 낮다. 단, 이 데이터셋 규모에서는 train loss만으로 leaderboard 성능을 판단할 수 없으므로 hidden/calibration metric을 함께 본다.

## 평가 결과

### 기본 threshold 0.50

[Original Text/Data] → hidden split: `accuracy=0.9578947368`, `precision_fail=0.9148936170`, `recall_fail=1.0`, `f1_fail=0.9555555556`, `macro_f1=0.9577777778`, `balanced_accuracy=0.9615384615`, `ECE=0.0411300572`, `Brier=0.0385200400`, confusion `TP=43`, `TN=48`, `FP=4`, `FN=0`.

[Exact Interpretation] → 기본 threshold 0.50에서 1차 목표인 hidden-like `0.9146`, fail precision `0.90`, fail recall `0.80`, ECE `0.12`를 모두 통과한다.

[Detailed Explanation/Example] → 기존 `r16_lr1e3_do10_ep5`의 false positive `5`개보다 하나 줄었고, recall은 그대로 `1.0`이다. runner의 base-threshold constrained best 기준으로는 현재 이 config가 최상위다.

### threshold sweep

[Original Text/Data] → hidden threshold `0.45`와 `0.50`: `accuracy=0.9578947368`, `precision_fail=0.9148936170`, `recall_fail=1.0`, `ECE=0.0411300572`. hidden threshold `0.65`와 `0.70`: `accuracy=0.9578947368`, `precision_fail=0.9333333333`, `recall_fail=0.9767441860`, `ECE=0.0484699547`.

[Exact Interpretation] → threshold를 높이면 accuracy는 유지하면서 fail precision이 올라가지만 fail recall이 소폭 하락한다.

[Detailed Explanation/Example] → 제출 threshold를 고정해야 한다면 이 config는 `0.50`이 가장 보수적이다. `0.65` 또는 `0.70`은 false positive를 줄이는 대신 false negative 위험을 하나 늘릴 가능성이 있으므로 public-hidden gap이 클 때만 후보로 둔다.

### calibration split

[Original Text/Data] → calibration split threshold 0.50: `accuracy=0.875`, `precision_fail=0.8275862069`, `recall_fail=0.96`, `ECE=0.1149042345`, `Brier=0.1137305472`.

[Exact Interpretation] → calibration ECE는 1차 상한 `0.12` 안에 있지만, calibration fail precision은 낮다.

[Detailed Explanation/Example] → hidden-like split에서는 가장 안정적이나, calibration split의 precision 약점은 최종 leaderboard 제출 전 threshold lock과 public-hidden gap 검토에서 다시 확인해야 한다.

## 중간 결정

- 이 config는 기본 threshold 0.50 기준으로 현재까지 가장 안정적인 후보이다.
- threshold-aware 최고 hidden accuracy만 보면 `r16_lr5e4_do10_ep5@threshold0.70`이 아직 더 높다.
- 최종 best 결정은 r32/r64 결과까지 완료한 뒤, base-threshold 안정성 후보와 threshold-aware 최고 후보를 함께 비교해서 한다.
- leaderboard 제출은 계속 NO-GO. 전체 sweep, best adapter packaging, offline first-forward gate가 끝난 뒤 판단한다.
