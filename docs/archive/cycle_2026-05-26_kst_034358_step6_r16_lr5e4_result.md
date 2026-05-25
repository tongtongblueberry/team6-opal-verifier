# 2026-05-26 KST 03:43 - Cycle 3 Step 6 r16_lr5e4_do10_ep5 결과

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- run root: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep`
- config: `r16_lr5e4_do10_ep5`
- train report: `artifacts/r16_lr5e4_do10_ep5.train_report.json`
- eval report: `artifacts/r16_lr5e4_do10_ep5.eval_manifest.json`
- 다음 진행: `r16_lr1e3_do05_ep5` 학습 중

## Hash

- train report: `8c852598a258d1d753d990b55f5feac419a21164082f35ca9c559cacd6888095`
- eval report: `1d381937a1d55fccc629c7bf58dbe9b20b42871587c885da486f688fbdac5afe`
- sweep results snapshot: `d4c28d6a682c5316ffdd60fcfb5590cdf061d585eb64970c5f5783e659c804d7`

## 학습 설정

[Original Text/Data] → `lr=0.0005`, `epochs=5.0`, `batch_size=2`, `grad_accum=4`, `max_seq_len=2048`, `lora_r=16`, `lora_alpha=32`, `lora_dropout=0.1`, `seed=42`.

[Exact Interpretation] → `r16_lr1e3_do10_ep5`와 동일 용량에서 learning rate만 낮춘 충분 학습 비교이다.

[Detailed Explanation/Example] → Step 4에서 결정한 r16 baseline 재현 sweep의 두 번째 축이며, lr `1e-3` 대비 calibration/precision 변화가 핵심 비교 대상이다.

## 학습 결과

[Original Text/Data] → `dataset_examples=337`, `trainable_params=3145728`, `training_loss=8.508005683366642`, `elapsed_seconds=2719.914`.

[Exact Interpretation] → 5 epoch는 정상 완료됐고, loss는 lr `1e-3`의 `8.348`보다 약간 높다.

[Detailed Explanation/Example] → train log의 마지막 구간 loss는 `6.002`, `6.442`, `6.459`, `6.377`이며, `CUDA`, `OOM`, `NaN`, `RuntimeError`, `Traceback` alert는 확인되지 않았다.

## 평가 결과

### 기본 threshold 0.50

[Original Text/Data] → hidden split: `accuracy=0.9368421053`, `precision_fail=0.8775510204`, `recall_fail=1.0`, `f1_fail=0.9347826087`, `macro_f1=0.9367790594`, `balanced_accuracy=0.9423076923`, `ECE=0.0455764314`, `Brier=0.0387454765`, confusion `TP=43`, `TN=46`, `FP=6`, `FN=0`.

[Exact Interpretation] → 기본 threshold에서는 recall은 완전하지만 precision이 1차 목표 `0.90`에 미달한다.

[Detailed Explanation/Example] → lr `5e-4`는 threshold 0.50에서 lr `1e-3`보다 false positive가 하나 더 많아 precision이 더 낮다.

### threshold sweep

[Original Text/Data] → hidden threshold `0.70`: `accuracy=0.9684210526`, `precision_fail=0.9545454545`, `recall_fail=0.9767441860`, `f1_fail=0.9655172414`, `ECE=0.0455764314`.

[Exact Interpretation] → threshold 0.70 기준으로는 지금까지의 최고 hidden-like 결과이며 1차 목표를 넉넉히 통과한다.

[Detailed Explanation/Example] → threshold 0.65도 precision `0.9149`, recall `1.0`으로 목표를 넘지만, threshold 0.70은 accuracy와 fail F1이 더 높다. 현재까지는 `r16_lr5e4_do10_ep5@threshold0.70`이 internal hidden-like 최상위 후보이다.

### calibration split

[Original Text/Data] → calibration split threshold 0.50: `accuracy=0.8958333333`, `precision_fail=0.8333333333`, `recall_fail=1.0`, `ECE=0.1045653316`, `Brier=0.0992856761`.

[Exact Interpretation] → calibration split에서도 ECE는 1차 상한 `0.12` 안이지만 precision은 낮다.

[Detailed Explanation/Example] → 최종 threshold는 hidden-like 성능만으로 확정하지 않고 calibration split 및 패키지 threshold lock 검증과 함께 결정해야 한다.

## 중간 결정

- 이 config는 threshold 0.70 기준으로 현재까지 가장 강한 후보이다.
- 하지만 sweep은 아직 r16 dropout 0.05, r32, r64가 남아 있으므로 최종 best로 확정하지 않는다.
- leaderboard 제출은 계속 NO-GO. 전체 sweep, best adapter packaging, offline first-forward gate가 끝난 뒤 판단한다.
