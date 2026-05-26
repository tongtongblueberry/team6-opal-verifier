# 사이클 8 -- 4단계: 달성 방법 결정

날짜: 2026-05-22 KST
1차 목표: hidden 73 (5/27)
기준선: LLM-only hidden 70.00, public 16/20
아키텍처: Qwen3.5-4B + LoRA, logit 비교, LLM-only

---

## 채택된 개선 사항

| # | 항목 | 변경 | 파일:라인 | 근거 논문 | 예상 효과 |
|---|------|------|----------|----------|----------|
| 1 | threshold 파라미터화 | `f_logit > p_logit` (0.5 고정) -> `p_fail > THRESHOLD` (환경변수/기본 0.70) | `src/solver.py:1603` | Platt (1999), eval_checkpoints.py sweep 실측 | +1점 (비용 0) |
| 2 | label_smoothing 추가 | TrainingArguments에 `label_smoothing_factor=0.1` 추가 | `tools/training/train_exp_a.py:510-529` | Szegedy et al. (2016) "Rethinking Inception", Muller et al. (2019) "When Does Label Smoothing Help?" | loss floor 형성, 과적합 억제 |
| 3 | dropout 0.1 -> 0.0 | `LORA_DROPOUT = 0.1` -> `LORA_DROPOUT = 0.0` | `tools/training/train_exp_a.py:59` | ALLoRA (2024) "Allocating LoRA", 210건 극소 데이터에서 dropout이 수렴 불안정화 | 수렴 안정화 (소량 데이터) |
| 4 | fail oversampling 5x | 데이터 로드 후 fail 케이스를 5배 복제 | `tools/training/train_exp_a.py:440-448` 근처 | Buda et al. (2018) "Systematic study of class imbalance", He & Garcia (2009) | pass 83% bias 해소 |
| 5 | validation 20% + early stopping | train 80% / val 20% split + eval_strategy="steps" + early stopping patience=3 | `tools/training/train_exp_a.py:425-535` | 표준 ML practice, Prechelt (1998) "Early Stopping" | 과적합 방지, 최적 epoch 자동 선택 |
| 6 | grad_accum 8 -> 16 + LR 비례 감소 | `GRAD_ACCUM = 16`, `LR_B = 4e-4`, `LR_A = 2.5e-5` | `tools/training/train_exp_a.py:71,63-64` | Smith et al. (2018) "Don't Decay the LR, Increase the Batch Size" | gradient noise 감소, 안정화 |
| 7 | 서버 supervised 데이터 통합 학습 | mutation 210건 -> canonical manifest (서버 2,531건에서 선별) | `tools/training/train_exp_a.py` MUTATION_DATA 경로 변경 | AlpaGasus (ICLR 2024), LESS (ICML 2024) | hidden 일반화, +2-3점 |
| 8 | test-time self-consistency K=5 | solver.py에서 5개 temperature forward pass -> 평균/투표 | `src/solver.py:1590-1603` | Wang et al. (2023) "Self-Consistency", eval_consistency.py 이미 구현 | threshold 민감도 감소, +1점 |

---

## 배제된 개선 사항

| # | 항목 | 배제 이유 |
|---|------|----------|
| 1 | D2LoRA warm-up | 구현 난이도 중간. LoRA+ 이미 적용 중이므로 추가 효과 불확실. 5일 내 warm-up 커스텀 trainer 변경은 디버깅 리스크. |
| 2 | WSD schedule (cosine 대체) | cosine이 이미 안정적으로 동작 중. WSD 전환은 LR sweep 재실행 필요. 비용 대비 효과 불확실 (+0.1-0.2%). |
| 3 | Adapter merging (3-seed) | 학습 3회 반복 필요. L40S에서 학습 1회 ~2시간 40분이므로 3회 = ~8시간. 5일 일정에서 Day 3 전부를 소비. 2차 목표(5/31) 이후로 연기. |
| 4 | IFD 필터링 (0.8B 모델 기반) | 서버에서 0.8B 모델 추론 인프라 구축 필요. canonical manifest가 먼저 확보되어야 의미 있음. 1차에서는 manifest 구축 + 길이 기반 선별이 우선. |
| 5 | DPE (training-free RoPE 길이 외삽) | 유망하나 Qwen3.5-4B의 RoPE 구현에 대한 패치가 필요. 코드 검증 시간 불확실. 2차 목표로 연기. |
| 6 | Multi-source 긴 trajectory 합성 300건+ | 27B teacher 모델로 합성 시 L40S에서 생성 시간 불확실. canonical manifest 데이터에 긴 trajectory가 포함되어 있다면 불필요할 수 있음. 서버 데이터 감사 후 판단. |
| 7 | ResoFilter (resonance score 필터링) | NAACL 2025 논문. 구현 복잡도 중간, resonance score 계산에 추가 모델 필요. 1차 목표에 과잉. |
| 8 | SDFT (self-distillation) | ACL 2024. teacher 모델이 필요하고 2-stage 학습 파이프라인 구축 필요. 궁극 목표(6/7)용. |

---

## 채택/배제 판단 상세 근거

### 채택 항목별 근거

**#1 threshold 파라미터화**: 비용 0. 코드 1줄 변경. eval_checkpoints.py sweep에서 threshold 0.70이 0.50보다 +1점인 것이 사이클 2에서 실측됨. solver.py 라인 1603에서 `f_logit > p_logit`으로 하드코딩되어 있어 sweep 결과가 제출에 반영되지 않는 치명적 버그. 무조건 채택.

**#2 label_smoothing=0.1**: 1줄 변경 (TrainingArguments에 파라미터 1개 추가). Muller et al. (2019)에서 소규모 데이터셋에서 0.1이 최적. loss가 0.005까지 떨어지는 과적합(사이클 1 관찰)을 loss floor 형성으로 억제. 부작용 없음.

**#3 dropout 0.0**: 1줄 변경 (`0.1` -> `0.0`). ALLoRA (2024) 결과: 극소량 데이터(수백 건)에서 LoRA dropout이 오히려 수렴을 방해. LoRA 자체가 low-rank constraint로 정규화 역할을 하므로 dropout은 이중 정규화. NEFTune이 이미 정규화를 담당.

**#4 fail oversampling 5x**: 5줄 추가 (데이터 로드 후 fail 케이스 리스트 확장). gap 데이터 pass:fail = 83:17. oversampling으로 50:50에 가깝게 균형화. threshold 조정(#1)과 상호보완적: threshold는 추론 시 bias 보정, oversampling은 학습 시 bias 방지.

**#5 validation 20% + early stopping**: 구현 난이도 중간이나, 과적합이 핵심 문제(5에폭 최적 vs 15에폭 50%)이므로 효과가 확실. Trainer에 `evaluation_strategy`, `eval_steps`, `load_best_model_at_end`, `early_stopping_patience` 파라미터 추가. 데이터셋을 80:20으로 분할하는 코드 ~10줄.

**#6 grad_accum 16 + LR 감소**: 2줄 변경 (GRAD_ACCUM, LR_A/B). effective batch size 8 -> 16. 선형 비례 원칙에 따라 LR을 50% 감소. gradient noise 감소로 안정적 수렴. 사이클 3(r=16, gradient explosion)의 재발 방지.

**#7 서버 supervised 데이터 통합**: 5일 일정의 핵심 작업. 현재 210건 mutation만 사용하는 것이 hidden 70 정체의 근본 원인. 서버에 2,531건 supervised 데이터 존재. canonical manifest 구축 + dedup + split 후 학습. Day 2에 해당.

**#8 test-time self-consistency K=5**: eval_consistency.py에 이미 완전 구현됨. solver.py에 통합하는 것은 ~30줄. 5개 temperature(0.5, 0.7, 0.9, 1.1, 1.3)에서 forward pass -> 평균 p_fail -> threshold 비교. 추론 시간 5배 증가하나 200케이스 x 0.5초 x 5 = ~500초 < 3시간 제한. Day 4에 해당.

### 배제 항목별 근거

- **D2LoRA, WSD, Adapter merging, SDFT**: 모두 구현 난이도 중간 이상. 5일 일정에서 핵심 작업(manifest 구축, 학습, 평가)에 시간을 쓰는 것이 우선. 2차 목표(5/31) 이후 검토.
- **IFD, DPE, ResoFilter**: canonical manifest가 없는 현재 상태에서 필터링/외삽을 논의하는 것은 순서가 맞지 않음. manifest 구축 후 데이터 감사 결과에 따라 판단.
- **긴 trajectory 합성**: 서버 2,531건에 이미 포함되어 있을 가능성. 감사 후 부족하면 2차에서 합성.

---

## 구체적 코드 변경 사항

### 파일 1: src/solver.py

#### 변경 1: threshold 파라미터화

```
라인 1597-1603
변경 전:
            mx = max(p_logit, f_logit)
            p_fail = math.exp(f_logit - mx) / (
                math.exp(p_logit - mx) + math.exp(f_logit - mx)
            )

            prediction = "fail" if f_logit > p_logit else "pass"

변경 후:
            mx = max(p_logit, f_logit)
            p_fail = math.exp(f_logit - mx) / (
                math.exp(p_logit - mx) + math.exp(f_logit - mx)
            )

            # Changed: threshold를 환경변수로 파라미터화. 기본값 0.70.
            # Why: eval_checkpoints.py sweep에서 0.70이 최적. 하드코딩 0.5는 +1점 손해.
            _THRESHOLD = float(os.environ.get("OPAL_THRESHOLD", "0.70"))
            prediction = "fail" if p_fail > _THRESHOLD else "pass"
```

이유: T-P0(solver.py threshold 하드코딩) 해결. 비용 0으로 +1점.

#### 변경 2: test-time self-consistency (Day 4에 적용)

```
라인 1590-1603 영역
변경 전: (단일 forward pass)
            with torch.no_grad():
                logits = self.model(**inputs).logits[0, -1, :]

            p_logit = logits[self._pass_id].item()
            f_logit = logits[self._fail_id].item()

            mx = max(p_logit, f_logit)
            p_fail = math.exp(f_logit - mx) / (
                math.exp(p_logit - mx) + math.exp(f_logit - mx)
            )
            prediction = "fail" if f_logit > p_logit else "pass"

변경 후: (5-temperature self-consistency)
            # Changed: self-consistency K=5. 여러 temperature에서 forward pass -> 평균 p_fail.
            # Why: Wang et al. (2023). threshold 경계 케이스에서 안정적 판정.
            _TEMPERATURES = [0.5, 0.7, 0.9, 1.1, 1.3]
            _THRESHOLD = float(os.environ.get("OPAL_THRESHOLD", "0.70"))
            p_fails = []
            with torch.no_grad():
                logits = self.model(**inputs).logits[0, -1, :]
            for temp in _TEMPERATURES:
                p_l = logits[self._pass_id].item() / temp
                f_l = logits[self._fail_id].item() / temp
                mx = max(p_l, f_l)
                pf = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
                p_fails.append(pf)
            p_fail = sum(p_fails) / len(p_fails)
            prediction = "fail" if p_fail > _THRESHOLD else "pass"
```

이유: 단일 forward pass만으로 5개 temperature scaling. logit은 1회만 계산하므로 추가 GPU 시간 0. 수치 연산만 5회 반복.

### 파일 2: tools/training/train_exp_a.py

#### 변경 1: dropout 제거

```
라인 59
변경 전: LORA_DROPOUT = 0.1
변경 후: LORA_DROPOUT = 0.0
```

이유: ALLoRA (2024). 극소량 데이터에서 LoRA dropout은 수렴 방해. NEFTune이 정규화 담당.

#### 변경 2: grad_accum + LR 비례 감소

```
라인 63-64
변경 전:
LR_A = 5e-5
LR_B = 8e-4

변경 후:
LR_A = 2.5e-5          # Changed: grad_accum 2배 → LR 50% 감소 (선형 비례)
LR_B = 4e-4            # Changed: grad_accum 2배 → LR 50% 감소 (선형 비례)

라인 71
변경 전: GRAD_ACCUM = 8
변경 후: GRAD_ACCUM = 16    # Changed: effective batch size 8 → 16 (gradient 안정화)
```

이유: Smith et al. (2018). effective batch size 증가 시 LR 비례 감소.

#### 변경 3: label_smoothing 추가

```
라인 510-529 (TrainingArguments 블록)
변경: TrainingArguments(...) 에 다음 파라미터 추가:
    label_smoothing_factor=0.1,      # Changed: label smoothing으로 과적합 억제
```

이유: Muller et al. (2019). loss가 0.005까지 떨어지는 과적합 억제.

#### 변경 4: fail oversampling 5x

```
라인 440-448 근처 (데이터 포맷팅 후)
추가할 코드:
    # Changed: fail 케이스 5x oversampling으로 label bias 해소.
    # Why: Buda et al. (2018). pass 83% bias -> 균형화.
    fail_data = [d for d in train_data if d["messages"][-1]["content"].strip() == "fail"]
    if fail_data:
        oversample_factor = 4  # 원본 1 + 추가 4 = 총 5x
        train_data.extend(fail_data * oversample_factor)
        logger.info("Fail oversampling: +%d (total %d)", len(fail_data) * oversample_factor, len(train_data))
```

이유: gap 데이터 pass:fail = 83:17 불균형 해소.

#### 변경 5: validation split + early stopping

```
라인 470-472 근처 (Dataset 생성 전)
추가할 코드:
    # Changed: 80/20 train/val split + early stopping.
    # Why: Prechelt (1998). 사이클 1에서 5에폭 최적 vs 15에폭 50% 과적합 관찰.
    import random
    random.seed(42)
    random.shuffle(train_data)
    split_idx = int(len(train_data) * 0.8)
    val_data_raw = train_data[split_idx:]
    train_data = train_data[:split_idx]
    logger.info("Split: train=%d, val=%d", len(train_data), len(val_data_raw))

    val_dataset = MutationDataset(val_data_raw, tokenizer, MAX_SEQ_LEN)

라인 510-529 (TrainingArguments 블록)
추가 파라미터:
    evaluation_strategy="steps",       # Changed: validation 모니터링
    eval_steps=50,                     # Changed: 50 step마다 eval
    load_best_model_at_end=True,       # Changed: 최적 모델 자동 선택
    metric_for_best_model="eval_loss", # Changed: eval loss 기준
    greater_is_better=False,           # Changed: loss는 낮을수록 좋음

라인 532-536 (Trainer 생성)
변경: eval_dataset 추가
    trainer = LoraPlusTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        eval_dataset=val_dataset,       # Changed: validation 데이터셋 추가
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],  # Changed: patience=3
    )

imports 추가:
    from transformers import EarlyStoppingCallback
```

이유: 과적합이 핵심 문제. validation loss 모니터링 + early stopping으로 자동 최적 epoch 선택.

---

## 5일 실행 타임라인

### Day 1 (5/23): threshold + validation 인프라

| 시간 | 작업 | 상세 |
|------|------|------|
| 오전 | solver.py threshold 파라미터화 | 라인 1603 변경, 환경변수 OPAL_THRESHOLD 기본값 0.70 |
| 오전 | train_exp_a.py 수정 | dropout 0.0, grad_accum 16, LR 비례 감소, label_smoothing, fail oversampling, validation split, early stopping |
| 오후 | 로컬 코드 검증 | 문법 오류, import 확인, dry run |
| 오후 | 서버 코드 배포 | git push -> 서버에서 pull |

### Day 2 (5/24): canonical manifest 구축

| 시간 | 작업 | 상세 |
|------|------|------|
| 오전 | 서버 접속, build_supervised_manifest.py 실행 | 2,531건 supervised 데이터에서 canonical manifest 생성 |
| 오전 | validate_manifest.py 실행 | source exact dup = 0, unknown label = 0, group leakage = 0 확인 |
| 오후 | data_audit.py 실행 | step_count 분포, label 분포, token 길이 분포 확인 |
| 오후 | manifest 선별 | 길이 10+ step 비중 15% 이상 확보, 저품질 제거 |

### Day 3 (5/25): 재학습

| 시간 | 작업 | 상세 |
|------|------|------|
| 오전 | Config A: r=8, alpha=16, canonical manifest | 수정된 train_exp_a.py로 학습 시작 (~2시간 40분) |
| 오후 | Config B: (옵션) 데이터 건수/비율 변경 | A 학습 중 B 준비, A 완료 후 B 실행 |
| 밤 | 학습 완료 대기 | 워치독 모니터링 |

### Day 4 (5/26): 전수 평가 + calibration

| 시간 | 작업 | 상세 |
|------|------|------|
| 오전 | eval_checkpoints.py --sweep 실행 | 전 체크포인트 x 전 threshold 매트릭스 |
| 오전 | 최적 (checkpoint, threshold) 조합 선택 | sweep 결과 기반 |
| 오후 | self-consistency 통합 | solver.py에 temperature scaling 추가 (이미 구현된 eval_consistency.py 참조) |
| 오후 | hidden-like validation acc 측정 | G-SUB-1 gate (>= 72%) 통과 여부 확인 |

### Day 5 (5/27): 오류 분석 + 제출

| 시간 | 작업 | 상세 |
|------|------|------|
| 오전 | 오분류 케이스 분석 | p_fail 경계값, 특정 method type 오류 패턴 |
| 오전 | 최종 adapter를 artifacts/lora_adapter_dcv2_final로 복사 | 제출 패키징 |
| 오후 | Must-have gate 전체 확인 | G-NO-1~5, G-SUB-1~3 |
| 오후 | 제출 | 제출 조건 충족 시 leaderboard 제출 |

---

## 위험 요소 및 완화 방안

| 위험 | 확률 | 영향 | 완화 방안 |
|------|------|------|----------|
| 서버 SSH 접속 불안정 | 높음 | 모든 작업 지연 | sshpass 3-4회 재시도, ControlSocket, Day 1에 접속 확인 |
| supervised 2,531건에 실제 사용 가능 데이터 부족 | 중간 | canonical manifest 건수 부족 | fallback: mutation 210건 + threshold/consistency만으로 71-72 확보 |
| validation split으로 train 데이터 20% 감소 -> 성능 하락 | 낮음 | early stopping 효과 < 데이터 감소 효과 | 10% split으로 축소하거나, K-fold cross-validation으로 전체 데이터 활용 |
| label_smoothing + dropout 0.0 조합이 수렴 불안정 | 낮음 | 학습 실패 | Config B에서 dropout 0.05로 설정하여 비교 |
| self-consistency가 오히려 성능 하락 (잘못된 케이스 투표) | 낮음 | -1점 | 환경변수 OPAL_USE_CONSISTENCY=false로 비활성화 가능하도록 구현 |
| 학습 시간 초과 (grad_accum 16으로 step 수 감소) | 낮음 | 학습 미완료 | epoch 5 유지, early stopping이 조기 종료 담당 |

---

## 성공 판정 기준

### 1차 목표 (5/27) 성공 조건

1. **Hidden score >= 73.00** (leaderboard 제출 확인)
2. **hidden-like validation acc >= 72%** (G-SUB-1 gate)
3. **Must-have gate 전부 통과** (G-NO-1~5)
4. **threshold가 calibration split 기반으로 선택됨** (G-SUB-2)

### 부분 성공 조건

- Hidden 71-72: threshold + consistency 효과만 반영됨. 데이터 다양성 개선 필요 -> 2차 목표 계속 진행.
- Hidden 70 (변화 없음): 데이터 품질 또는 manifest 구축에 문제. 오류 분석 후 방향 재설정.

### 실패 조건

- Hidden < 70: 코드 변경이 regression 유발. 즉시 revert, 사이클 2 adapter로 복원.

### 측정 항목

| 항목 | 현재값 | 목표값 | 측정 방법 |
|------|--------|--------|----------|
| Hidden score | 70.00 | 73.00 | leaderboard |
| Public score | 16/20 (80%) | 17/20 (85%) | eval_checkpoints.py |
| Threshold | 0.50 (하드코딩) | 0.70 (sweep 최적) | solver.py 환경변수 |
| Train data 건수 | 210 | 500+ | canonical manifest |
| Fail:Pass ratio | ~17:83 | ~40:60 (oversampling 후) | 학습 로그 |
| 최적 epoch | 수동 선택 | early stopping 자동 | Trainer callback |
| Eval loss 모니터링 | 없음 | eval_steps=50 | 학습 로그 |

---

## 변경 우선순위 (구현 순서)

1. **threshold 파라미터화** (solver.py) -- 비용 0, 즉시
2. **dropout 0.0** (train_exp_a.py) -- 1줄
3. **label_smoothing 0.1** (train_exp_a.py) -- 1줄
4. **grad_accum 16 + LR 비례 감소** (train_exp_a.py) -- 2줄
5. **fail oversampling 5x** (train_exp_a.py) -- 5줄
6. **validation split + early stopping** (train_exp_a.py) -- 15줄
7. **서버 canonical manifest 구축** (서버 작업) -- Day 2
8. **self-consistency 통합** (solver.py) -- Day 4
