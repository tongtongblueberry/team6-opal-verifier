<!-- 변경: 사이클 8 2단계 문제 확인 결론 문서 신규 작성. 이유: 3개 agent(데이터 구조, 학습 구조, 논문 조사) 결과를 종합하여 결함 우선순위와 해결책 매핑을 기록하기 위함. -->
# 사이클 8 — 2단계: 문제 확인 결과

날짜: 2026-05-22 KST
기준선: LLM-only hidden 70.00, public 16/20
목표: hidden 73+ (rule engine 수준 이상)

---

## 1. 데이터 결함 (우선순위순)

### D-P0 [CRITICAL]: 긴 trajectory 학습 데이터 전무 — 길이 분포 불일치

- **현상**: 학습 데이터(spec/gap)의 96%가 1-2 step trajectory. hidden 테스트의 median은 16 step.
- **영향**: 모델이 10+ step trajectory를 한 번도 보지 못한 채 추론해야 함. 긴 trajectory에서 attention pattern, positional encoding 활용 패턴이 학습되지 않아 hidden 성능이 70에서 정체.
- **근거**: 사이클 1 분석에서도 "길이 분포 불일치"가 hidden 성능 병목으로 확인됨. 사이클 4(길이>=10 필터링, 87건)에서는 오히려 데이터 부족으로 15/20 정체.
- **핵심**: 긴 trajectory를 "충분한 수량"으로 생성해야 함. 단순 필터링으로는 해결 불가.

### D-P1 [HIGH]: 소스 다양성 결핍 — template overfit

- **현상**: mutation 데이터의 origin이 public 20개 template에 100% 의존. unique origin 최대 20개.
- **영향**: 모델이 20개 패턴의 변형만 학습하므로 hidden의 새로운 template 구조에 일반화 실패.
- **근거**: 사이클 2(hidden 70.00)에서 public 16/20(80%)이지만 hidden 70.00(70%)인 10%p 격차가 template overfit의 직접 증거.

### D-P2 [MEDIUM]: label 불균형 — pass bias

- **현상**: gap 데이터의 pass:fail = 83%:17%.
- **영향**: fail 케이스 학습 부족 → fail을 pass로 오분류하는 경향. threshold 조정으로 부분 완화 가능하나 근본 해결 아님.
- **근거**: 사이클 3(r=16, no reg)에서 pass bias 발생 확인. threshold 0.50→0.70 변경 시 +1점 효과.

### D-P3 [MEDIUM]: 학습 스크립트가 mutation_cases.json(210건)만 참조

- **현상**: train_exp_a.py가 spec_cases.json, gap_cases.json을 참조하지 않음.
- **영향**: 생성해둔 spec/gap 데이터가 학습에 전혀 활용되지 않음. 사이클 5에서 1172건 조합을 시도했으나 결과 미확인.
- **조치**: manifest 기반 통합 학습 파이프라인 필요.

### D-P4 [LOW]: data_audit.py에 step_count 분포 검증 부재

- **현상**: token count만 측정, step 수 분포는 미측정.
- **영향**: 데이터 품질 게이트에서 길이 분포 불일치를 자동 감지 불가.
- **조치**: audit 스크립트에 step_count histogram + hidden 분포 대비 gate 추가.

---

## 2. 학습 구조 결함 (우선순위순)

### T-P0 [CRITICAL]: solver.py threshold=0.5 하드코딩

- **현상**: `src/solver.py`에서 pass/fail 판정 threshold가 0.5로 고정.
- **영향**: eval_checkpoints.py의 threshold sweep 결과(최적 0.70)가 실제 제출에 반영되지 않음. 최적 threshold 적용 시 +1점 이상 가능.
- **조치**: threshold를 config 파라미터화하거나, sweep 결과를 자동 반영하는 메커니즘 추가.
- **구현 난이도**: 매우 낮음. 즉시 적용 가능.

### T-P1 [HIGH]: Validation loss 모니터링 부재

- **현상**: 학습 중 validation set이 없어 과적합 조기 감지 불가.
- **영향**: 최적 checkpoint 선택이 사후 평가에만 의존. 5에폭이 최적이고 15에폭은 50%까지 하락하는 과적합이 학습 중 감지되지 않음.
- **조치**: 학습 데이터의 10-20%를 template 단위로 holdout하여 validation loss 모니터링 + early stopping.

### T-P1 [HIGH]: 스크립트 기본값과 최적값 불일치

- **현상**: train_exp_a.py 기본값 r=4이지만 실험적 최적은 r=8.
- **영향**: 서버에서 sed로 매번 수동 변경 필요. 실수로 기본값으로 학습할 위험.
- **조치**: 기본값을 r=8로 변경하거나, config 파일에서 분리.

### 정상 확인 항목

- format 일관성: 학습/추론/제출 모두 동일한 format 사용 (format_for_training_v2 = format_trajectory_rich 확인됨)
- system prompt: 학습과 추론 동일
- LLM-only 경로: solver.py의 USE_RULE_ENGINE=False 보장
- LoRA 파라미터: r=8, alpha=16, NEFTune=5, LoRA+ 조합이 현재 최적

---

## 3. 논문 기반 해결책 매핑

| 결함 ID | 결함 설명 | 적용할 논문/방법 | 구현 난이도 | 예상 효과 | 우선 적용 |
|---------|----------|-----------------|-----------|----------|----------|
| D-P0 | 긴 trajectory 전무 | **DPE** (training-free RoPE 길이 외삽) | 낮음 | 짧은 학습 데이터로 긴 추론 가능. 길이 분포 gap 직접 해소 | 1순위 |
| D-P0 | 긴 trajectory 전무 | **Multi-source synthetic** (ACL 2026): 다양한 LLM으로 긴 trajectory 합성 | 중간 | 10-20 step 데이터 직접 생성. 근본 해결 | 2순위 |
| D-P1 | template overfit | **Multi-source synthetic** (ACL 2026) | 중간 | 다양한 LLM이 다양한 template 구조 생성 → origin 다양성 확보 | 2순위 |
| D-P1 | template overfit | **ResoFilter** (NAACL 2025): resonance score 필터링 | 중간 | 유해/중복 데이터 제거로 template overfit 완화 | 3순위 |
| D-P2 | label 불균형 | **SDFT** (ACL 2024): self-distillation | 중간 | distribution gap 브릿지로 불균형 완화 | 4순위 |
| D-P2 | label 불균형 | **IFD** (NAACL 2024): filter_data.py에 이미 구현 | 낮음 | 고품질 fail 케이스 선별 + 저품질 pass 제거 | 1순위 |
| D-P3 | 데이터 미활용 | manifest 기반 통합 (train_manifest_lora.py 활용) | 낮음 | 기존 spec/gap 데이터 즉시 학습에 투입 | 1순위 |
| T-P0 | threshold 하드코딩 | config 파라미터화 (논문 무관, 엔지니어링) | 매우 낮음 | sweep 최적값 즉시 반영, +1점 이상 | 1순위 |
| T-P1 | validation 부재 | **Complexity-aware FT** + holdout validation | 낮음 | 과적합 조기 감지, 최적 checkpoint 자동 선택 | 2순위 |

---

## 4. 다음 단계로 넘길 결정사항

### 즉시 적용 (구현 난이도 낮음, 효과 확실)

1. **T-P0 해결**: solver.py의 threshold를 0.5 → 0.70으로 변경 (또는 config 파라미터화). 이것만으로 +1점 가능.
2. **D-P2 부분 해결**: IFD 필터링 즉시 적용. filter_data.py가 이미 구현되어 있음.
3. **D-P3 해결**: train_manifest_lora.py를 활용하여 spec/gap 데이터를 학습에 통합.

### 사이클 8 핵심 실험 (1-2일 소요)

4. **D-P0 해결 (DPE)**: training-free RoPE 길이 외삽을 추론 시 적용. 학습 데이터 변경 없이 긴 trajectory 추론 성능 개선 가능. 코드 변경 최소.
5. **D-P0 + D-P1 해결 (Multi-source synthetic)**: 다양한 LLM(캐시된 Qwen3.5-2B, 9B 등)으로 10-20 step trajectory를 합성 생성. 최소 200건 이상 목표.
6. **T-P1 해결**: validation split 추가 + early stopping 적용.

### 우선순위 판단 근거

- **hidden 70 → 73+ 달성에 가장 큰 병목은 D-P0(길이 분포 불일치)**. public 80%인데 hidden 70%인 이유가 길이 분포 차이로 설명됨.
- **T-P0(threshold)은 비용 0으로 +1점 가능**하므로 무조건 먼저 적용.
- **D-P1(template overfit)은 D-P0과 동시 해결 가능** (multi-source synthetic이 두 문제를 모두 커버).
- DPE는 training-free이므로 학습 없이 추론 단계에서 즉시 테스트 가능. 실패해도 비용 없음.

---

## 참고 논문 (15편)

### 데이터 품질/필터링 (5편)
1. **ResoFilter** (NAACL 2025) — Resonance score 기반 유해 데이터 필터링
2. **IFD** (NAACL 2024) — Instruction-Following Difficulty score로 데이터 품질 평가. filter_data.py에 구현 완료.
3. **AlpaGasus** (ICLR 2024) — LLM-as-judge로 데이터 필터링
4. **LESS** (ICML 2024) — 데이터 선별로 학습 효율화
5. **Long Is More** (ICML 2024) — 긴 응답 데이터의 학습 효과

### 학습 방법론 (5편)
6. **SDFT** (ACL 2024) — Self-distillation fine-tuning. Distribution gap 브릿지. 코드 공개.
7. **NEFTune** (ICLR 2024) — Noisy embedding으로 과적합 방지. 이미 적용 중(noise_alpha=5).
8. **LoRA+** — LoRA A/B 행렬 차별 학습률. 이미 적용 중(lr_A=5e-5, lr_B=8e-4).
9. **Complexity-aware FT** — 난이도별 차별 학습으로 데이터 효율 극대화
10. **rsLoRA** — Rank-stabilized LoRA. 낮은 rank에서 안정성 향상.

### 데이터 생성/증강 (3편)
11. **Multi-source synthetic** (ACL 2026) — 다양한 LLM으로 합성 데이터 생성. Template overfit 방지.
12. **SynAlign** — 합성 데이터 정렬 기법
13. LLM augmentation이 seed 20개 수준에서 기존 방법보다 우수 (논문 #10 결과)

### 추론 최적화 (2편)
14. **DPE** (training-free) — RoPE 길이 외삽. 짧은 학습 → 긴 추론. 코드 변경 최소.
15. **LoRA Ensembles** — 다중 어댑터 로짓 평균. 사이클 2에서 앙상블 실험 계획 있었으나 미실행.

---

## 부록: 사이클 1-7 실험 결과 요약

| 사이클 | r | 데이터 | 건수 | Public | Hidden | 비고 |
|--------|---|--------|------|--------|--------|------|
| 1 | 4 | mutation | 210 | 15/20 | - | 초기 baseline |
| **2** | **8** | **mutation** | **210** | **16/20** | **70.00** | 현재 최고 LLM-only |
| 3 | 16 | mutation(NEFTune) | 210 | 15/20 | - | r=16 불안정 |
| 3 | 16 | mutation(no reg) | 210 | 10/20 | - | gradient explosion |
| 4 | 8 | filtered(len>=10) | 87 | 15/20 | - | 데이터 부족 |
| 5 | 8 | diverse combo | 1172 | ??? | ??? | 결과 미확인 |
| 6-7 | - | self-consistency + adapter merging | - | - | - | 논문 단계 |
