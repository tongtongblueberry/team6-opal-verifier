# 2026-05-26 KST 05:09 - Cycle 3 Step 6 r32_lr1e3_do10_ep5 결과

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- run root: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep`
- config: `r32_lr1e3_do10_ep5`
- train report: `artifacts/r32_lr1e3_do10_ep5.train_report.json`
- eval report: `artifacts/r32_lr1e3_do10_ep5.eval_manifest.json`
- 다음 진행: `r64_lr1e3_do05_ep5` 학습 시작

## Hash

- train report: `8ff1d6197d67b83dede15e45bf9f53cc0aca908dbe1f6bb70982a39f41c35b09`
- eval report: `1cc2931419937ce9d455c6de05c9393eba00e7d7345feb48d46e7587cf5b48b8`
- sweep results snapshot: `6c68c29f8e06a4aab7d29cc22fd2538f09e0844f63904cd5f113ab70f135bda2`

## 학습 설정

[Original Text/Data] → `lr=0.001`, `epochs=5.0`, `batch_size=2`, `grad_accum=4`, `max_seq_len=2048`, `lora_r=32`, `lora_alpha=64`, `lora_dropout=0.1`, `target_modules=q_proj,k_proj,v_proj,o_proj`, `seed=42`.

[Exact Interpretation] → r16 baseline 대비 LoRA rank와 alpha를 2배로 늘린 high-rank LoRA 비교 실험이다.

[Detailed Explanation/Example] → trainable parameter는 `6,291,456`, trainable ratio는 `0.0014936828447462064`로 r16의 약 2배다. 같은 data/epoch/lr에서 capacity 증가가 hidden-like metric을 개선하는지 확인하는 목적이다.

## 학습 결과

[Original Text/Data] → `dataset_examples=337`, `trainable_params=6291456`, `total_params=4212042752`, `training_loss=8.3248751085858`, `elapsed_seconds=2744.842588663101`.

[Exact Interpretation] → 5 epoch 학습은 정상 완료됐고, loss는 r16 dropout 0.05의 `8.3323`보다 약간 낮다.

[Detailed Explanation/Example] → 마지막 logged loss 구간은 `5.966`, `6.444`, `6.512`, `6.368`이었다. `OOM`, `NaN`, `RuntimeError`, `Traceback` alert는 train/eval log에서 확인되지 않았다.

## 평가 결과

### 기본 threshold 0.50

[Original Text/Data] → hidden split: `accuracy=0.9368421053`, `precision_fail=0.8775510204`, `recall_fail=1.0`, `f1_fail=0.9347826087`, `macro_f1=0.9367790594`, `balanced_accuracy=0.9423076923`, `ECE=0.0491373698`, `Brier=0.0493757159`, confusion `TP=43`, `TN=46`, `FP=6`, `FN=0`.

[Exact Interpretation] → 기본 threshold에서는 fail recall은 완전하지만 fail precision이 1차 목표 `0.90`에 미달한다.

[Detailed Explanation/Example] → r16 dropout 0.05의 hidden accuracy `0.9578947368`, precision `0.9148936170`, ECE `0.0411300572`보다 낮다. high-rank r32는 train loss를 낮췄지만 hidden-like 일반화와 calibration을 개선하지 못했다.

### threshold sweep

[Original Text/Data] → threshold `0.30`부터 `0.65`까지 hidden metric은 `accuracy=0.9368421053`, `precision_fail=0.8775510204`, `recall_fail=1.0`으로 동일했다. threshold `0.70`은 `accuracy=0.9263157895`, `precision_fail=0.875`, `recall_fail=0.9767441860`이었다.

[Exact Interpretation] → r32는 threshold를 조정해도 fail precision `0.90` 제약을 만족하지 못한다.

[Detailed Explanation/Example] → threshold-aware selector를 r32 포함 4개 결과로 갱신했을 때도 best는 `r16_lr5e4_do10_ep5@0.70`이었다. r32는 constraint-satisfying 후보를 추가하지 못했다.

### calibration split

[Original Text/Data] → calibration split threshold 0.50: `accuracy=0.8958333333`, `precision_fail=0.8333333333`, `recall_fail=1.0`, `ECE=0.1000282191`, `Brier=0.0947385173`.

[Exact Interpretation] → calibration ECE는 1차 목표 `0.12` 안이지만 precision은 낮다.

[Detailed Explanation/Example] → hidden과 calibration 양쪽에서 false positive가 많다. capacity 증가가 pass class margin을 충분히 넓히지 못한 것으로 본다.

## GPU 및 다음 config

[Original Text/Data] → r32 학습 중 GPU는 약 `30467 MiB` 사용, free `14992 MiB`, util `100%`였고 OOM alert는 없었다.

[Exact Interpretation] → r32 rank 증가는 48GB L40S에서 memory blocker가 아니었다.

[Detailed Explanation/Example] → r64 시작 직후 KST `05:09:35` 기준 GPU는 `30435 MiB` 사용, free `15024 MiB`, util `100%`, r64는 `2/215 step`, alert `0`이었다.

## 중간 결정

- r32는 r16 best보다 낮으므로 최종 후보에서 제외한다.
- r32 결과는 capacity 부족보다는 threshold/calibration 또는 데이터 분포 병목이 더 크다는 신호다.
- r64가 아직 남아 있으므로 전체 sweep 최종 best는 확정하지 않는다.
- leaderboard 제출은 계속 NO-GO. r64 완료, final selector, merged package gate 이후 판단한다.
