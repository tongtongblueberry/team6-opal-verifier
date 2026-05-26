# 사이클 8 -- 6단계: 결과 분석

날짜: 2026-05-23 KST
결과: public 15/20 (75%), 기존 최고 16/20 대비 -1
최적 체크포인트: epoch 2 (checkpoint-35) @ threshold 0.40

---

## 학습 결과 요약

| Epoch | Train Loss | Eval Loss | Public (sweep 최적) | 비고 |
|-------|-----------|-----------|---------------------|------|
| 1 | 2.88->1.37 | 0.3846 | 11/20 (55%) | 학습 초기, 미수렴 |
| **2** | **0.332** | **0.2505** | **15/20 (75%)** | 최적 체크포인트 |
| 3 | 0.025 | 0.1340 | ??? (로드 실패) | train loss 급락, 과적합 시작 |
| 5 | 0.006 | 0.0698 | 11/20 (55%) | 과적합 확정 |
| 7 | 0.004 | 0.0492 | 12/20 (60%) | 과적합 고착 |
| 10 | 0.003 | 0.0465 | 12/20 (60%) | 과적합 고착 |

핵심 관찰:
- epoch 2->3에서 train loss가 0.332->0.025으로 **13배 급락** (정상적이지 않은 수렴)
- eval loss는 계속 감소(0.38->0.05)하지만 실제 정확도는 epoch 2 이후 하락
- eval loss와 실제 정확도가 **역상관**: eval loss가 가장 낮은 epoch 10이 60%, eval loss가 높은 epoch 2가 75%
- 이는 모델이 training distribution을 "외우면서" eval set도 "외우는" 과정이며, public 20의 실제 분류 성능과 무관함을 시사

---

## 사이클 2 (최고) vs 사이클 8 비교

| 항목 | 사이클 2 (16/20) | 사이클 8 (15/20) | 차이 |
|------|-----------------|-----------------|------|
| **데이터** | mutation 210건 | supervised 694건 (oversampling 후 556:train, 138:val) | +484건 |
| **pass:fail 비율** (원본) | ~50:50 (mutation) | 197:359 (pass 35%, fail 65%) | fail 과다 |
| **pass:fail 비율** (oversampling 후) | 동일 | fail 더욱 과대 대표 | fail bias 심화 |
| **rank** | r=8 | r=8 | 동일 |
| **dropout** | 0.1 | 0.0 | 정규화 제거 |
| **LR_A / LR_B** | 5e-5 / 8e-4 | 2.5e-5 / 4e-4 | 절반 |
| **grad_accum** | 8 | 16 | 2배 |
| **effective batch** | 8 | 16 | 2배 |
| **label_smoothing** | 0.0 | 0.0 (계획은 0.1, OOM으로 철회) | 동일 |
| **validation split** | 없음 (전체 210건 학습) | 20% 분리 (556건 train / 138건 val) | 데이터 20% 감소 |
| **최적 threshold** | 0.70 | **0.40** | threshold 이동 |
| **최적 epoch** | 7 (checkpoint-189) | 2 (checkpoint-35) | 조기 정점 |
| **NEFTune** | 5.0 | 5.0 | 동일 |

---

## 변경별 영향 분석

### 변경 1: threshold 0.50->0.70 파라미터화

| 항목 | 판정 |
|------|------|
| 효과 | **중립 ~ 양성** |
| 근거 | threshold를 환경변수로 파라미터화한 것 자체는 올바른 엔지니어링. 그러나 사이클 8에서 sweep 최적이 0.40으로 변경됨 (사이클 2에서는 0.70). 이는 모델의 calibration 특성이 완전히 바뀌었음을 의미 |

threshold 0.70이 아닌 0.40이 최적인 이유:
- fail oversampling으로 모델이 **fail-biased** 되어 p_fail 분포가 전체적으로 상승
- 사이클 2에서는 pass:fail이 균형적이어서 p_fail 분포가 0.5 중심이었고, 0.70이 적절한 구분점
- 사이클 8에서는 fail이 65%인 데이터로 학습하여 모델이 "fail을 더 많이 예측"하도록 편향됨
- 결과: pass 케이스도 p_fail이 높게 나옴 -> threshold를 0.40까지 낮춰야 pass를 복구
- 이것은 oversampling이 threshold를 불안정하게 만든다는 직접 증거

### 변경 2: label_smoothing 0.1 (OOM으로 철회 -> 0.0)

| 항목 | 판정 |
|------|------|
| 효과 | **미적용 (중립)** |
| 근거 | OOM으로 0.0 유지. 사이클 2와 동일. 영향 없음. 다만, label_smoothing이 적용되었다면 loss floor가 생겨 epoch 2->3의 급격한 loss 하락을 억제하고 과적합 시작을 지연시켰을 가능성이 있다. 향후 batch=1 환경에서 label_smoothing OOM을 우회하는 방법(예: custom loss function)을 검토할 가치가 있다. |

### 변경 3: dropout 0.1->0.0

| 항목 | 판정 |
|------|------|
| 효과 | **부정적** |
| 근거 | epoch 2에서 train loss 0.332, epoch 3에서 0.025 -- 한 에폭 만에 13배 하락. dropout 0.1이 있었다면 이 급격한 수렴을 어느 정도 억제했을 것이다. |

상세 분석:
- ALLoRA (2024)의 "소량 데이터에서 dropout 해로움" 근거를 적용했으나, 사이클 8은 694건(oversampling 포함)으로 사이클 2의 210건보다 **3.3배 많은 데이터**
- ALLoRA 논문의 "소량"은 수십 건 수준이며, 700건은 dropout이 정당화되는 수준
- dropout 0.0 + NEFTune 5.0 조합에서 NEFTune만으로는 충분한 정규화가 되지 않았음
- 증거: epoch 2->3 사이에 train loss가 0.332->0.025로 급격히 떨어지며 과적합 가속
- 사이클 2 (dropout 0.1)에서는 epoch 7까지 안정적으로 성능 유지

### 변경 4: fail oversampling (pass:fail = 197:359, fail 65%)

| 항목 | 판정 |
|------|------|
| 효과 | **부정적 (가장 큰 해악)** |
| 근거 | threshold가 0.70->0.40으로 이동한 것이 결정적 증거. fail bias가 모델의 calibration을 파괴함. |

상세 분석:
1. **의도**: gap 데이터의 pass 83% bias를 해소하려 했으나, 실제 supervised 데이터(694건)의 원본 pass:fail 비율이 이미 197:359 = 35:65로 **fail이 과대 대표**
2. **oversampling 적용 결과**: 원본에서 이미 fail이 많은 상태에서 추가로 fail을 oversampling하면 fail 비율이 더욱 극단적으로 편향 (코드상 `oversample_factor = max(1, round(n_pass / n_fail) - 1)` -> 이미 fail > pass이므로 oversampling이 적용되지 않았을 수도 있으나, 데이터 합산 순서에 따라 mutation의 pass-heavy와 supervised의 fail-heavy가 섞이면서 불균형 발생)
3. **실제 문제**: 학습 데이터의 label 분포가 hidden 테스트의 분포와 불일치 시, 모델의 prior가 왜곡됨. hidden이 pass:fail = 50:50에 가깝다면, fail 65% 학습은 모델을 fail-biased로 만듦
4. **threshold 이동의 의미**: 모델이 fail-biased되어 pass 케이스의 p_fail도 높게 출력 -> threshold를 0.40까지 내려야 pass를 살릴 수 있음. 그러나 이렇게 낮은 threshold는 진짜 fail 케이스도 놓칠 위험 증가
5. **사이클 2와의 대비**: 사이클 2의 mutation 210건은 pass:fail이 대략 균형적이었고, threshold 0.70이 자연스러운 구분점이었음. 이것이 16/20을 가능하게 한 요인 중 하나

### 변경 5: grad_accum 16 + LR 50% 감소

| 항목 | 판정 |
|------|------|
| 효과 | **약한 부정** |
| 근거 | effective batch size 8->16, LR 절반. gradient noise 감소로 수렴은 안정화되지만, 탐색 다양성도 감소. 소량 데이터에서 gradient noise는 오히려 일반화에 유리할 수 있음(Li et al., 2022). |

상세 분석:
- Smith et al. (2018)의 linear scaling rule은 대규모 데이터셋에서 검증된 것
- 556건 학습 데이터에서 effective batch 16은 전체 데이터의 약 3%를 한 step에 소비
- 작은 데이터셋에서 큰 effective batch는 SGD noise 감소 -> sharp minima 수렴 경향
- sharp minima는 일반화 성능 저하와 연관 (Keskar et al., 2017)
- 다만, 이 효과가 -1점에 기여한 정도는 다른 변경(oversampling, dropout)보다 작을 것

### 변경 6: validation 20% + early stopping

| 항목 | 판정 |
|------|------|
| 효과 | **혼재 (긍정 + 부정)** |
| 근거 | validation 자체는 올바른 방향이나, 두 가지 문제 발생. |

긍정적 측면:
- 과적합을 객관적으로 모니터링할 수 있게 됨
- epoch 2가 최적임을 확인할 수 있었음 (validation 없었으면 더 늦은 epoch를 선택했을 수 있음)

부정적 측면:
1. **데이터 감소**: 694건에서 20% 분리 -> 556건 학습. 사이클 2의 210건보다 여전히 많지만, 감소분이 특정 패턴의 학습 기회를 빼앗았을 수 있음
2. **eval loss와 실제 성능의 괴리**: eval loss는 epoch 10까지 계속 감소하지만, 실제 public 정확도는 epoch 2에서 최적. 이는 `load_best_model_at_end=True`가 eval_loss 기준으로 epoch 10의 모델을 "최적"으로 선택하여 **최악의 모델을 반환**할 위험이 있다는 의미
3. **early stopping 미작동**: patience 미설정 또는 eval loss가 계속 감소하여 early stopping이 트리거되지 않음. 10 epoch 전체를 실행함

---

## 실패 원인 (확정)

### 1차 원인: fail oversampling으로 인한 label prior 왜곡 [CRITICAL]

fail 과대 대표(65%) -> 모델이 fail-biased -> threshold가 0.70에서 0.40으로 이동 -> calibration 불안정 -> 경계 케이스에서 오분류 증가

사이클 2의 핵심 성공 요인 중 하나가 **균형적인 pass:fail 비율**이었다는 것이 사이클 8의 실패로 확인됨.

### 2차 원인: dropout 0.0으로 인한 과적합 가속 [HIGH]

dropout 제거 -> epoch 2->3에서 train loss 13배 급락 -> epoch 2 이후 모든 checkpoint에서 성능 저하. 사이클 2 (dropout 0.1)에서는 epoch 7까지 안정적이었음.

### 3차 원인: eval_loss 기준 best model 선택의 오류 [MEDIUM]

eval_loss가 계속 감소하므로 `load_best_model_at_end=True`가 과적합된 후기 checkpoint를 "최적"으로 반환. eval_loss는 모델이 분류를 잘하는 것이 아니라 training distribution을 잘 외우는 것을 반영.

### 기여하지 않은 요인:

- **threshold 파라미터화**: 올바른 변경. 문제는 oversampling이 threshold 최적값 자체를 변동시킨 것
- **validation split**: 올바른 방향이나, eval_loss 기준 선택이 오류 유발
- **LR/grad_accum 변경**: 약한 부정적 기여이나 핵심 원인은 아님
- **데이터 건수 증가 (210->694)**: 데이터가 많아진 것 자체는 긍정. 문제는 데이터의 label 분포

---

## 사이클 9 권장 사항

| 항목 | 유지/되돌림 | 이유 |
|------|-----------|------|
| **threshold 파라미터화** (OPAL_THRESHOLD) | **유지** | 올바른 엔지니어링. sweep으로 최적값 선택 가능하게 함 |
| **label_smoothing 0.0** | **되돌림 -> 0.1 재시도** | OOM 우회 방법을 찾아 적용 (custom loss 또는 gradient_checkpointing 최적화). loss floor가 과적합 억제에 기여할 것 |
| **dropout 0.0** | **되돌림 -> 0.05 또는 0.1** | 694건은 "극소량"이 아님. dropout 정규화 필요. 0.05로 시작하여 0.1과 비교 |
| **fail oversampling** | **제거** | 가장 큰 해악. 원본 데이터의 pass:fail 비율 유지. 불균형이 있다면 focal loss 또는 class weight로 대응하되, 데이터 자체를 복제하지 않을 것 |
| **grad_accum 16 + LR 50% 감소** | **되돌림 -> accum=8, LR_A=5e-5, LR_B=8e-4** | 사이클 2의 검증된 설정으로 복귀. 소량 데이터에서 큰 effective batch는 sharp minima 위험 |
| **validation 20%** | **유지 (단, eval 기준 변경)** | validation은 필요하나, `metric_for_best_model`을 eval_loss가 아닌 **eval_accuracy**로 변경. 또는 load_best_model_at_end=False로 두고 수동으로 최적 checkpoint를 sweep 선택 |
| **데이터 694건** | **유지** | 데이터 증가 자체는 올바른 방향. 다만 label 비율을 자연 비율로 유지 |
| **self-consistency** | **유지** | solver.py에 이미 구현됨. 추가 비용 없음 (logit 후처리만). 다만 threshold 변동에 민감하므로, calibration이 안정적인 모델에서만 효과적 |

### 구체적 사이클 9 설정 제안

```
# 사이클 2의 검증된 설정을 기반으로, 데이터만 694건으로 확대
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05          # 0.0에서 복원 (0.1보다 약하게 시작)
LR_A = 5e-5                  # 사이클 2와 동일
LR_B = 8e-4                  # 사이클 2와 동일
GRAD_ACCUM = 8               # 사이클 2와 동일
BATCH_SIZE = 1               # OOM 안전
label_smoothing = 0.0        # OOM 우회 시 0.1로 변경
NEFTUNE_NOISE_ALPHA = 5.0    # 유지
NUM_EPOCHS = 10              # 유지 (sweep으로 최적 epoch 선택)
validation = 20%             # 유지 (모니터링용)
load_best_model_at_end = False  # 변경 (수동 sweep 선택)
fail oversampling = OFF      # 제거
데이터 = supervised 694건 (원본 pass:fail 비율 유지)
```

### 실험 우선순위

1. **사이클 9A**: 위 설정 그대로 실행. 예상 결과: 16/20 (사이클 2 재현) 이상
2. **사이클 9B** (9A 성공 시): dropout 0.1로 변경하여 비교
3. **사이클 9C** (9A 성공 시): class_weight 또는 focal_loss로 불균형 대응 (oversampling 대신)

---

## 교훈

### 1. 한 번에 여러 변수를 변경하지 말 것
사이클 8에서 6가지를 동시에 변경하여 어느 것이 성능 하락의 원인인지 분리가 어려웠다. 사이클 9에서는 **사이클 2 설정 + 데이터만 확대** (1개 변수)로 시작해야 한다.

### 2. oversampling은 threshold를 파괴할 수 있다
label 비율 변경은 모델의 prior를 바꾸며, 이는 threshold 최적값의 이동으로 직결된다. 불균형 대응은 데이터 복제가 아닌 loss 가중치(focal loss, class weight)로 해야 데이터 분포를 보존할 수 있다.

### 3. eval_loss는 분류 성능의 proxy가 아니다
eval_loss가 계속 감소하는데 실제 정확도가 하락하는 현상이 관찰되었다. 이는 모델이 training distribution을 외우면서 eval set의 loss도 감소시키지만, 실제 분류 경계는 악화되기 때문이다. 모니터링 지표를 eval_accuracy로 변경하거나, load_best_model_at_end를 비활성화하고 수동 sweep을 사용해야 한다.

### 4. dropout은 데이터 크기에 비례하여 결정해야 한다
ALLoRA (2024)의 "극소량 데이터에서 dropout 해로움"은 수십 건 수준에 해당한다. 700건은 dropout 정규화가 정당화되는 수준이며, dropout 없이 NEFTune만으로는 과적합을 충분히 억제하지 못한다.

### 5. 사이클 2의 성공 요인을 정확히 이해해야 한다
사이클 2의 16/20은 (1) 균형적 pass:fail 비율, (2) dropout 0.1, (3) moderate LR, (4) 적절한 effective batch size의 조합으로 달성되었다. 이 중 어느 하나라도 변경하면 성능 하락 위험이 있다. 데이터를 확대할 때는 이 조건들을 유지하면서 데이터만 변경해야 한다.

---

## 부록: 사이클 1-8 실험 결과 전체

| 사이클 | r | 데이터 | 건수 | Dropout | LR_B | grad_accum | Oversampling | Public | Hidden |
|--------|---|--------|------|---------|------|------------|-------------|--------|--------|
| 1 | 4 | mutation | 210 | 0.1 | 8e-4 | 8 | 없음 | 15/20 | - |
| **2** | **8** | **mutation** | **210** | **0.1** | **8e-4** | **8** | **없음** | **16/20** | **70.00** |
| 3a | 16 | mutation(NEFTune) | 210 | 0.1 | 8e-4 | 8 | 없음 | 15/20 | - |
| 3b | 16 | mutation(no reg) | 210 | 0.0 | 1e-3 | 8 | 없음 | 10/20 | - |
| 4 | 8 | filtered(len>=10) | 87 | 0.1 | 8e-4 | 8 | 없음 | 15/20 | - |
| 5 | 8 | diverse combo | 1172 | 0.1 | 8e-4 | 8 | 없음 | ??? | ??? |
| **8** | **8** | **supervised** | **694 (556 train)** | **0.0** | **4e-4** | **16** | **fail 65%** | **15/20** | **???** |
