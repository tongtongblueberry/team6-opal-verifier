# 2026-05-26 KST 05:56 - Cycle 3 Step 6 r64 결과 및 최종 selector 결정

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- run root: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep`
- completed configs:
  - `r16_lr1e3_do10_ep5`
  - `r16_lr5e4_do10_ep5`
  - `r16_lr1e3_do05_ep5`
  - `r32_lr1e3_do10_ep5`
  - `r64_lr1e3_do05_ep5`
- final selector report:
  - `artifacts/threshold_aware_candidate_final.json`
  - `artifacts/threshold_aware_candidate_final.md`

## Hash

- r64 train report: `d189590b644054b08818dd8bd1eb7ee617119ca3ce9f3fa3360bc798745df7ae`
- r64 eval report: `15b86f59b276a880c8d1c00f0ff3ed3dd21a4c3a624f356b366a8d62bdf971e6`
- final selector JSON: `f0daac6c428226fdbfc0c825c013d7292c26d23fc629bf35624c26d2a6fb6b03`
- sweep results final snapshot: `12b6eaebd14e4053cccfc1803e99bc58ee9d0c345e0a909e772524fe535d82b2`

## r64 학습 설정

[Original Text/Data] → `lr=0.001`, `epochs=5.0`, `batch_size=2`, `grad_accum=4`, `max_seq_len=2048`, `lora_r=64`, `lora_alpha=128`, `lora_dropout=0.05`, `target_modules=q_proj,k_proj,v_proj,o_proj`, `seed=42`.

[Exact Interpretation] → r16/r32 대비 LoRA rank를 더 키운 high-rank capacity 실험이다.

[Detailed Explanation/Example] → trainable parameter는 `12,582,912`, trainable ratio는 `0.0029829101677474293`이다. r16 대비 4배, r32 대비 2배 trainable parameter를 사용한다.

## r64 학습 결과

[Original Text/Data] → `dataset_examples=337`, `total_params=4218334208`, `trainable_params=12582912`, `training_loss=8.937448820956918`, `elapsed_seconds=2715.9223506450653`.

[Exact Interpretation] → 5 epoch는 정상 완료됐지만 loss는 r16/r32보다 높다.

[Detailed Explanation/Example] → 마지막 logged loss 구간은 `6.366`, `6.657`, `6.697`, `6.554`였다. train/eval log에서 `OOM`, `NaN`, `RuntimeError`, `Traceback` alert는 확인되지 않았다. GPU는 약 `30.5GB` 사용으로 48GB 한도 안에서 안정적이었다.

## r64 평가 결과

### 기본 threshold 0.50

[Original Text/Data] → hidden split: `accuracy=0.8421052632`, `precision_fail=0.7413793103`, `recall_fail=1.0`, `f1_fail=0.8514851485`, `macro_f1=0.8414729113`, `balanced_accuracy=0.8557692308`, `ECE=0.1400879140`, `Brier=0.1420517901`, confusion `TP=43`, `TN=37`, `FP=15`, `FN=0`.

[Exact Interpretation] → r64는 hidden-like에서 크게 악화됐고, fail precision과 ECE 모두 1차 목표를 만족하지 못한다.

[Detailed Explanation/Example] → r16 best 후보의 hidden accuracy `0.968421@threshold0.70`와 비교하면 r64는 false positive가 `15`개로 너무 많다. rank를 키우는 방향이 데이터 분포/label prior 문제를 악화시켰다고 본다.

### threshold sweep

[Original Text/Data] → threshold `0.30`부터 `0.70`까지 hidden metric이 모두 `accuracy=0.8421052632`, `precision_fail=0.7413793103`, `recall_fail=1.0`, `ECE=0.1400879140`로 동일했다.

[Exact Interpretation] → r64는 threshold 조정으로 fail precision 제약을 회복할 수 없다.

[Detailed Explanation/Example] → pass 예제의 p_fail이 넓게 높아진 상태라 threshold `0.70`까지 올려도 false positive가 줄지 않는다. 이는 high-rank capacity 증가가 calibration을 해친 것으로 해석한다.

### calibration split

[Original Text/Data] → calibration split threshold 0.50: `accuracy=0.875`, `precision_fail=0.8275862069`, `recall_fail=0.96`, `ECE=0.1073085550`, `Brier=0.1169207181`.

[Exact Interpretation] → calibration ECE는 1차 상한 `0.12` 안이지만, hidden ECE와 fail precision이 너무 낮다.

[Detailed Explanation/Example] → calibration split만으로 r64를 살릴 근거가 없다. hidden-like split에서 primary failure가 명확하다.

## 최종 selector 결과

[Original Text/Data] → final selector best: `config_name=r16_lr5e4_do10_ep5`, `threshold=0.70`, `hidden accuracy=0.9684210526`, `precision_fail=0.9545454545`, `recall_fail=0.9767441860`, `Brier=0.0387454765`, `ECE=0.0455764314`.

[Exact Interpretation] → 전체 r16/r32/r64 sweep의 threshold-aware 최종 후보는 `r16_lr5e4_do10_ep5@0.70`이다.

[Detailed Explanation/Example] → runner base-threshold best는 `r16_lr1e3_do05_ep5@0.50`이지만, 제출 solver 기본 threshold는 `0.70`이다. final selector best는 threshold `0.70`이므로 package-level threshold lock 문제가 없다.

## 최종 후보

- adapter: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep/adapters/r16_lr5e4_do10_ep5/final`
- threshold: `0.70`
- 이유:
  - hidden-like accuracy 최고: `0.9684210526`
  - fail precision 목표 통과: `0.9545454545 >= 0.90`
  - fail recall 목표 통과: `0.9767441860 >= 0.80`
  - ECE 목표 통과: `0.0455764314 <= 0.12`
  - solver 기본 threshold와 일치: `0.70`

## 중간 결정

- r32/r64 high-rank LoRA는 최종 후보에서 제외한다.
- capacity를 단순히 키우는 방향은 현재 데이터 분포와 calibration 문제를 해결하지 못했다.
- 다음 단계는 `r16_lr5e4_do10_ep5@0.70` adapter를 merged model package로 export하고, static package gate와 offline first-forward smoke를 통과시키는 것이다.
- leaderboard 제출은 아직 NO-GO. merged package 검증과 server availability 확인이 끝난 뒤 제출 여부를 결정한다.
