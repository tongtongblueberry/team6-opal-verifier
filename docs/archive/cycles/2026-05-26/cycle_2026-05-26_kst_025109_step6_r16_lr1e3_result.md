# 2026-05-26 KST 02:51 - Cycle 3 Step 6 r16_lr1e3_do10_ep5 결과

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- HEAD: `5af9f8b archive manifest lora sweep start`
- run root: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep`
- config: `r16_lr1e3_do10_ep5`
- train report: `artifacts/r16_lr1e3_do10_ep5.train_report.json`
- eval report: `artifacts/r16_lr1e3_do10_ep5.eval_manifest.json`
- 다음 진행: sweep runner가 `r16_lr5e4_do10_ep5`로 이동하여 학습 중

## Hash

- manifest: `25eec0c65def9ada2a96487a502378a34514b46d3fc7c1f4071764649b761b80`
- train report: `c6a0e851ee67494f4fd75a446c3298ba114ba411ee7a03e3fe3f84ed0f824ad0`
- eval report: `818124b50a74588513699bba926564ec136de3d9c101d460dc77e769f3948701`
- sweep results snapshot: `68dce01910e67cc424ca54bba7ea049b2d804581f59775255890934c4c84b2e1`

## 학습 설정

[Original Text/Data] → `lr=0.001`, `epochs=5.0`, `batch_size=2`, `grad_accum=4`, `max_seq_len=2048`, `lora_r=16`, `lora_alpha=32`, `lora_dropout=0.1`, `target_modules=q_proj,k_proj,v_proj,o_proj`, `seed=42`.

[Exact Interpretation] → 기존 충분 학습 baseline을 재현하는 r16 LoRA 설정이다.

[Detailed Explanation/Example] → 기존 dcv2 baseline과 같은 핵심 설정을 새 manifest-only runner/evaluator로 다시 실행해, 이후 r32/r64 비교의 기준점으로 사용한다.

## 학습 결과

[Original Text/Data] → `dataset_examples=337`, `trainable_params=3145728`, `trainable_ratio=0.0007473996`, `training_loss=8.348232828184615`, `elapsed_seconds=2719.057`.

[Exact Interpretation] → 5 epoch 학습은 정상 완료됐고, adapter-size LoRA 학습 기준으로 기존 `8.412`와 유사한 loss까지 내려갔다.

[Detailed Explanation/Example] → 로그의 loss는 `34.09 → 17.61 → 7.756 → ... → 6.37`, 최종 train loss는 `8.348`이다. `CUDA`, `OOM`, `NaN`, `RuntimeError`, `Traceback` alert는 확인되지 않았다.

## 평가 결과

### 기본 threshold 0.50

[Original Text/Data] → hidden split: `accuracy=0.9473684211`, `precision_fail=0.8958333333`, `recall_fail=1.0`, `f1_fail=0.9450549451`, `macro_f1=0.9472749473`, `balanced_accuracy=0.9519230769`, `ECE=0.0301283692`, `Brier=0.039436115`, confusion `TP=43`, `TN=47`, `FP=5`, `FN=0`.

[Exact Interpretation] → hidden-like accuracy, recall, ECE는 1차 목표를 넘었지만 fail precision `0.8958`은 목표 `0.90`에 근소하게 미달한다.

[Detailed Explanation/Example] → threshold 0.50은 fail을 과하게 예측해 false positive가 5개 남았다. 이 문제는 Step 2에서 지적한 label prior/calibration 병목과 일치한다.

### threshold sweep

[Original Text/Data] → hidden threshold `0.60`: `accuracy=0.9578947368`, `precision_fail=0.9333333333`, `recall_fail=0.9767441860`, `f1_fail=0.9545454545`, `ECE=0.0399976455`.

[Exact Interpretation] → threshold 0.60을 쓰면 1차 목표인 hidden-like `>=0.9146`, fail precision `>=0.90`, fail recall `>=0.80`, ECE `<=0.12`를 모두 만족한다.

[Detailed Explanation/Example] → threshold 0.55도 precision `0.9130`, recall `0.9767`로 목표를 넘지만, threshold 0.60이 hidden accuracy와 fail F1을 더 높인다. 따라서 이 config는 calibration/threshold 조정 기준으로는 현재 유효 후보이다.

### calibration split

[Original Text/Data] → calibration split threshold 0.50: `accuracy=0.875`, `precision_fail=0.8275862069`, `recall_fail=0.96`, `ECE=0.1186005437`, `Brier=0.1084914531`.

[Exact Interpretation] → calibration split에서는 hidden보다 precision이 낮고 ECE가 목표 상한에 가까워 threshold/label-prior 검증을 계속해야 한다.

[Detailed Explanation/Example] → hidden threshold 0.60이 좋아 보이지만, 최종 threshold는 calibration split과 hidden-like split을 함께 보고 결정해야 한다. leaderboard 제출 전에는 같은 패키지에서 threshold lock을 명시적으로 기록해야 한다.

## 중간 결정

- 이 config는 threshold 0.60 기준으로 1차 internal metric 목표를 만족한다.
- sweep runner의 best selection은 아직 precision constraint를 기본 threshold 0.50 기준으로 보므로 `constraints_applied=False`로 남았다.
- 다음 판단은 `r16_lr5e4_do10_ep5`, `r16_lr1e3_do05_ep5`, `r32`, `r64` 결과와 비교한 뒤 한다.
- leaderboard 제출은 아직 NO-GO. 현재 서버 availability reject 상태가 해소됐다는 증거가 없고, sweep 전체 및 package smoke가 끝나지 않았다.
