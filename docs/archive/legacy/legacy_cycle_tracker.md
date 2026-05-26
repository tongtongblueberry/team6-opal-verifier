# 지속 개선 사이클 트래커

## 프로젝트: Team 6 Opal Verifier (LLM 전용)
- 마감: 2026-06-08
- 현재 리더보드 최고: 73.00 (룰 엔진 — LLM으로 대체 예정)
- 현재 LLM 전용 최고: 15/20 public (75%) — mutation_4b 어댑터
- 아키텍처: Qwen3.5-4B + LoRA, logit 비교, LLM 전용
- 제약: L40S 48GB, 네트워크 불가, 3시간 제한, 캐시된 모델만 사용

---

## 사이클 1 — 초기 평가 (2026-05-22)

### 0단계: 아키텍처 전환
- 상태: **완료**
- 목표: 룰 엔진 의존성 제거, LLM을 1차 솔버로 전환

### 1단계: 중간 평가
- 상태: **완료**
- 확인 대상: mutation_4b의 public 20 정확도 (깨끗한 재실행)

### 2단계: 문제 확인
- 상태: **완료**
- 확인된 문제:
  1. 학습 데이터 210건뿐
  2. 심각한 과적합 (5에폭 최고, 15에폭 = 50%)
  3. 데이터 증가(470건)가 오히려 성능 저하
  4. Weight decay가 오히려 성능 저하
  5. Type B 케이스 (데이터 값 차이)는 logit 모드로 해결 불가
  6. Train loss가 ~0.005까지 떨어지는데 test 성능은 악화

#### 데이터 문제 (상세)
- 학습 데이터 210건은 20개 public template에서 mutation 생성 → 소스 다양성 부족
- 470건으로 늘리면 오히려 50%로 하락 → 추가 데이터에 노이즈 포함
- 길이 분포 불일치: 학습 데이터 94% 짧은 trajectory, 테스트 median 16 steps

#### 학습 구조 문제 (상세)
- Rank r=16은 210건에 비해 과도 (논문: r=2-4 권장)
- Weight decay가 오히려 악화 (LoRA 자체가 정규화이므로 이중 정규화)
- 프롬프트 포맷 불일치로 2점 손실 (학습 시 format_for_training_v2 vs 추론 시 format_trajectory_rich)
- 정규화: dropout=0.1만 사용, NEFTune/R-Drop 미적용

#### 논문 조사 결과 (총 43편)
- LoRA 과적합 방지: 20편 (핵심: rank 축소, NEFTune, 앙상블, LoRA+)
- 데이터 증강/분포 매칭: 23편 (핵심: SynAlign, LESS, AlpaGasus, Long Is More)

### 3단계: 목표 설정
- 상태: **완료**

| 목표 | 기준 | 달성 방법 | 근거 논문 |
|------|------|----------|----------|
| 1차 (오늘) | Public 18/20 (90%) | 포맷 통일 + rank 축소 + NEFTune | NEFTune(ICLR 2024), rsLoRA, LoRA Resists Label Noise(ICML 2026) |
| 2차 (내일) | Public 19-20/20 + 리더보드 제출 | 앙상블 5개 + 데이터 필터링 | LoRA Ensembles, AlpaGasus(ICLR 2024), LESS(ICML 2024) |
| 궁극 (6/8) | 리더보드 85+ | 전체 최적화 | 종합 |

### 4단계: 달성 방법 결정
- 상태: **완료**

#### 실험 A (첫 번째 — 오늘 실행)
- Rank: r=4, alpha=8 (r=16에서 축소)
- NEFTune: noise_alpha=5
- 프롬프트: 학습과 추론 포맷 통일
- 데이터: 210 mutation cases (기존과 동일)
- 에폭: 3
- 학습률: LoRA+ 방식 (lr_A=5e-5, lr_B=8e-4)
- 근거: rank 축소(논문 3,5), NEFTune(논문 6), LoRA+(논문 14)

#### 실험 B (두 번째 — 실험 A 완료 후)
- 5개 어댑터 앙상블 (r=2,2,4,4,8, 다른 시드)
- 로짓 평균으로 최종 판정
- 근거: LoRA Ensembles(논문 13)

#### 실험 C (세 번째)
- 데이터 품질 필터링 (470건 → 길이>=10인 것만)
- Temperature scaling 후처리
- 근거: Long Is More(ICML 2024), AlpaGasus(ICLR 2024)

### 5단계: 구현
- 상태: **완료**

### 6단계: 실행
- 상태: **진행 중 (학습 86/270, KST 04:25)**

### 학습 모니터링 결과 (KST 04:25)
- Loss 추이: 2.63 → 0.99 → 0.41 → 0.26 (에폭 0→1→2→3)
- r=4 + NEFTune이 과적합을 효과적으로 억제 중 (r=16 대비 1.5배 높은 loss)
- Gradient norm: 0.15-0.25 안정
- LR schedule: cosine + warmup 정상
- **최적 체크포인트 예측: 에폭 3-5 (checkpoint-81, 108, 135)**
- 과적합 시작 예측: 에폭 5-6
- 10에폭 완주 후 전체 평가로 최적 선택 예정

---

## 의사결정 기록

| 날짜 | 결정 | 근거 | 결과 |
|------|------|------|------|
| 5/22 | LLM 전용 아키텍처로 전환 | DL 과제 요구사항, 룰 엔진 73에서 정체 | 진행 중 |
| 5/22 | Rank r=16→r=4 축소 | 20편 논문 일치: 210건에 r=2-4 적정 | 대기 중 |
| 5/22 | NEFTune noise_alpha=5 추가 | ICLR 2024 검증, 비용 0 | 대기 중 |
| 5/22 | 프롬프트 포맷 통일 | 동일 어댑터 17/20→15/20 차이 확인 | 대기 중 |
| 5/22 | LoRA+ 차등 학습률 | lr_B=16×lr_A, 논문 검증 | 대기 중 |
| 5/22 04:25 | 학습 모니터링: 에폭 3-5가 최적 예측 | loss curve 분석 (r=4 epoch3 loss 0.26 > r=16 epoch3 loss 0.17) | 대기 중 |

---

## 제출 기록

| # | 날짜 | 점수 | 방법 | 변경점 | 제출 근거 |
|---|------|------|------|--------|----------|
| (기존 23건 제출 기록은 docs/leaderboard_log.md 참조) | | | | | |

---

## 어댑터 성능 요약

| 어댑터 | 학습 데이터 | 에폭 | LR | Rank | Public 점수 | 비고 |
|--------|-----------|------|-----|------|------------|------|
| mutation_4b | 210 mutation | 5 | ? | ? | 15/20 (75%) | 최고 단일 어댑터 |
| mutation_15ep | 210 mutation | 15 | ? | ? | 10/20 (50%) | 과적합 |
| mutation_470 | 470 혼합 | 10 | ? | ? | 10/20 (50%) | 노이즈 데이터 |
| mutation_wd | 210 mutation+WD | 5 | ? | ? | 12/20 (60%) | WD가 오히려 악화 |

---

## 사이클 간 핵심 교훈

(각 사이클 완료 후 여기에 추가)

---

## 사이클 2 — r=8 실험 (2026-05-22 KST 05:30~)

### 사이클 1 결과 요약
- 실험A (r=4, NEFTune, LoRA+): **15/20 (75%)** — 기존 mutation_4b와 동일
- checkpoint-189 (에폭 7) @ threshold=0.70이 최적
- **문제**: r=4가 용량 부족 → tc6, tc8 (pass 케이스) 틀림
- **포맷 가설 기각**: format_for_training_v2 vs format_trajectory_rich 차이 없음 (코드 분석 확인)
- 학습 에폭 7에서 중단 (원인 미상, 체크포인트 7개 확보)

### 2단계: 문제 확인
- r=4의 trainable params: 786K → 부족. tc6, tc8 틀림
- r=16의 trainable params: 3.1M → 과적합 위험 있지만 17/20 달성
- **r=8 (1.57M)이 중간 균형점**

### 3단계: 목표
- Public 17/20 (90%) 이상 — tc6, tc8 복구

### 4단계: 방법
- r=8, alpha=16 (나머지 동일: NEFTune=5, LoRA+, 10에폭, 210건)
- 출력: /workspace/team6/adapters/exp_a_r8/

### 5단계: 구현
- train_exp_a.py의 서버 사본만 sed로 수정 (로컬은 미변경)
- 상태: **완료**

### 6단계: 실행
- 상태: **진행 중** (KST 05:30 시작, 270 steps, ~60분)
- Trainable: 1,572,864 / 4.2B (0.037%)
- 속도: ~13초/step

### 의사결정 기록 추가

| 5/22 05:30 | r=4→r=8 변경 | r=4가 tc6,tc8 틀림 (용량 부족), 포맷 가설 기각 | 진행 중 |

### 학습 모니터링 결과
- r=8 loss: 2.39→0.43→0.10→0.02→0.02→... (에폭 1-5)
- r=8 과적합 시작: 에폭 3-4 (loss 0.10→0.02 급락)
- r=8 최적: checkpoint-189 (에폭 7) @ threshold=0.70 → **16/20 (80%)**
- tc20 최초 해결! (p_fail=0.93) — 이전 어댑터 전부 실패했던 케이스

### mutation_4b 재현 결과 (실패)
- r=16, lr=1e-3, 5에폭, NEFTune 없음 → **10/20 (50%)**
- 원인: lr=1e-3이 신포맷에서 gradient explosion (norm 13.24)
- 전체 fail 케이스를 pass로 예측 (극심한 pass bias)
- **결론: mutation_4b 설정은 구포맷에서만 작동. 신포맷에서는 정규화 필수**

---

## 사이클 3 — r=16 + NEFTune + LoRA+ (2026-05-22 KST 07:30~)

### 사이클 2 최종 결과
| 실험 | Rank | NEFTune | LoRA+ | Public 20 |
|------|------|---------|-------|----------|
| exp_a (사이클1) | r=4 | 5.0 | O | 15/20 |
| exp_a_r8 (사이클2) | r=8 | 5.0 | O | **16/20** |
| replicate_best | r=16 | 없음 | X | 10/20 (실패) |

### 2단계: 문제 확인
- r=16의 용량은 필요하지만, lr=1e-3 + 정규화 없음 → gradient explosion + pass bias
- r=8은 안정적이지만 tc6, tc8 여전히 틀림 (용량 부족)
- **r=16 + 정규화(NEFTune + LoRA+)가 최적 조합 가설**

### 3단계: 목표
- Public 17/20 (85%) 이상 — r=8의 16/20에서 +1 이상

### 4단계: 방법
- r=16, alpha=32, NEFTune=5, LoRA+ (lr_A=5e-5, lr_B=8e-4)
- 10에폭, 210건, 매 에폭 체크포인트
- 출력: /workspace/team6/adapters/exp_r16_neft/

### 5/6단계: 구현 + 실행
- train_exp_a.py를 서버에서 sed 수정 (r=8→r=16, alpha=16→32)
- 상태: **진행 중**

### 의사결정 기록
| 5/22 07:30 | r=16+NEFTune+LoRA+ 실험 | r=8=16/20, r=16(no reg)=10/20 → 정규화+용량 조합 필요 | 진행 중 |

---

## 사이클 4 — 데이터 필터링 (2026-05-22 KST 09:00~09:30)

### 결과: 15/20 (개선 없음)
- r=8 + filtered_len10_all.json (87건)
- tc6, tc8 복구했지만 tc5, tc20 잃음 → 순 변화 0
- 학습 데이터 감소가 일부 케이스에 부정적 영향

---

## 리더보드 제출 #24 (KST 09:00)

| # | 날짜(KST) | 이름 | 점수 | 방법 | 제출 근거 |
|---|-----------|------|------|------|----------|
| 24 | 5/22 09:00 | r8-llm-only-16of20 | **70.00** | LLM-only, r=8+NEFTune+LoRA+ | 최초 LLM-only 제출, hidden 성능 확인 |

**핵심 발견**: LLM-only hidden 70.00 < Rule engine hidden 73.00
- Public 16/20 (80%) → Hidden 70.00 (70%) = 10pp 하락
- 원인: 학습 데이터가 public 20에서만 파생 → hidden 패턴 미커버

---

## 사이클 5 — 다양한 데이터 조합 (2026-05-22 KST 09:45~)

### 2단계: 문제 확인
- 핵심 문제는 rank/정규화가 아닌 **학습 데이터 다양성 부족**
- mutation 210건 = public 20 패턴만 → hidden 200 패턴 미커버
- 서버에 4종 데이터 존재: mutation(470), spec_aug(1572), gap(289), augmented(300)

### 3단계: 목표
- Hidden 73+ (rule engine 이상)

### 4단계: 방법
- 5종 데이터 조합 (~800-1000건)
- r=8 + NEFTune + LoRA+ (검증된 설정)
- 5에폭 (데이터 많으므로 축소)

### 5/6단계: 실행
- 상태: **진행 중** (데이터 생성 + 학습 시작)

### 의사결정 기록
| 5/22 09:00 | r=8 LLM-only 제출 | 최초 LLM-only, hidden 성능 확인 필수 | 70.00 (73 미만) |
| 5/22 09:45 | 다양한 데이터 조합 | hidden 70→73+ 위해 데이터 다양성 필수 | 진행 중 |

---

## 사이클 6 — LLM-only 데이터 문제 확정 및 운영 규칙 정리 (2026-05-22 KST)

<!-- 변경 사유: Cycle 1 / 2단계 문제 확인 결론과 다음 cycle 운영 규칙을 문서 끝에 append한다. -->

### 확정 결론

- [Original Text/Data] 현재 solver는 LLM-primary 의도이나 `StatefulOpalVerifier`, fallback, module-level `predict_one`에 rule engine이 남아 있음. 로컬에는 `artifacts/`가 없어 LLM-only 실행 보장 안 됨. README/PROGRESS는 rule-hybrid, cycle_tracker는 LLM-only로 문서 충돌. → [Exact Interpretation] architecture에서는 rule engine을 금지해야 하며, fallback/문서/제출 경로에서도 LLM-only 보장이 필요하다. → [Detailed Explanation/Example] 제출 경로 중 하나라도 rule engine fallback을 사용하면 실험명이 LLM-only여도 실제 decision path가 hybrid가 된다. 따라서 `StatefulOpalVerifier`, fallback, module-level `predict_one`, README/PROGRESS/cycle_tracker 설명, 제출 스크립트의 실행 경로가 모두 같은 LLM-only 계약을 가져야 한다.

- [Original Text/Data] hidden 70.00의 가장 큰 원인은 public 20 template overfit, `UNEXPECTED_ERROR_STATUS` decision boundary 데이터 부족, train/test 길이 분포 불일치, Type B 값 비교 coverage 부족, noisy expansion. → [Exact Interpretation] 현재 최대 문제는 모델 구조보다 데이터이며, 다음 cycle은 데이터 구조 metric과 hidden-like validation부터 만든다. → [Detailed Explanation/Example] public 20에서 파생된 mutation만으로는 hidden의 길이, status boundary, Type B 값 비교, noise 패턴을 대표하지 못한다. 다음 cycle에서는 학습 전에 데이터셋이 hidden-like 분포를 갖는지 측정하는 metric을 만들고, public template memorization을 분리해서 검증하는 validation split을 먼저 정의한다.

- [Original Text/Data] 210건 mutation 한계, epoch 3-4 이후 memorization, 스크립트별 LR/rank/epoch/threshold 불일치, 0.5 threshold 고정 문제, max_length/format 불일치. → [Exact Interpretation] 학습 실험은 데이터 검증 기준과 실행 설정 일관성이 확보된 뒤에만 의미가 있다. → [Detailed Explanation/Example] 같은 모델이라도 script별 LR, rank, epoch, threshold, max_length, prompt/output format이 다르면 성능 차이가 데이터 효과인지 실행 설정 효과인지 분리할 수 없다. threshold 0.5 고정은 calibration 실패를 숨길 수 있으므로 validation 기반 threshold 선택이 필요하다.

- [Original Text/Data] LLM judge bias/prompt sensitivity, public-derived mutation contamination, synthetic-heavy loop의 tail collapse, exact/string comparison 한계가 논문 조사 근거로 확인됨. → [Exact Interpretation] synthetic expansion과 exact-match 중심 평가는 hidden 일반화 실패를 과소평가할 수 있다. → [Detailed Explanation/Example] public-derived mutation이 많으면 모델은 실제 verifier semantics보다 template surface를 학습할 수 있다. LLM judge와 prompt가 민감하면 작은 formatting 차이도 label 또는 score 변동으로 이어질 수 있으므로, hidden-like validation에는 semantic category별 breakdown과 string-only 실패 분석이 포함되어야 한다.

- [Original Text/Data] dev는 origin/dev보다 8커밋 ahead, untracked 파일 2개, tracked credential 흔적 존재. 값은 절대 출력하지 말 것. → [Exact Interpretation] 현재 저장소 상태는 제출/공유 전에 정리와 보안 검토가 필요하다. → [Detailed Explanation/Example] ahead commit과 untracked 파일은 어떤 실험 상태가 재현 가능한 기준인지 흐릴 수 있다. credential 흔적은 값 자체를 문서나 로그에 남기지 않고, 파일 경로와 제거/rotate 필요성만 별도 보안 절차에서 다뤄야 한다.

- [Original Text/Data] leaderboard 제출은 학습/검증 기준을 통과할 때만 한다. 지금은 제출하지 않는다. → [Exact Interpretation] 다음 leaderboard 제출은 데이터 구조 metric, hidden-like validation, LLM-only 실행 보장, 학습 설정 일관성 검증을 모두 통과한 뒤에만 허용한다. → [Detailed Explanation/Example] 현재는 hidden 70.00의 원인이 데이터 문제로 확정되었고 LLM-only 경로 보장도 문서/실행 간 충돌이 남아 있다. 따라서 지금 제출하면 leaderboard를 디버깅 루프로 사용하는 것이 되어 contamination과 과적합 위험이 커진다.

### 다음 단계로 넘길 결정

- 데이터 구조 metric을 먼저 만든다: template source, status boundary, trace length, Type B 값 비교, noise type, label balance를 측정한다.
- hidden-like validation split을 먼저 만든다: public 20 template 직접 파생 샘플과 독립 구조 샘플을 분리한다.
- architecture에서 rule engine을 금지한다: `StatefulOpalVerifier`, fallback, module-level `predict_one`, 제출 경로가 LLM-only인지 검증한다.
- README/PROGRESS/cycle_tracker의 LLM-only/rule-hybrid 설명 충돌을 다음 문서 정리 작업에서 해소한다.
- 학습 스크립트의 LR/rank/epoch/threshold/max_length/format을 단일 실험 매니페스트로 고정한다.
- threshold는 0.5 고정이 아니라 validation 기반으로 선택한다.
- leaderboard 제출은 위 기준을 통과한 뒤에만 한다. 지금은 제출하지 않는다.
- Git 상태는 제출 전 정리한다: ahead commit, untracked 파일, credential 흔적을 값 노출 없이 별도 점검한다.

---

## 사이클 6 — 3단계 목표 설정 결정 (2026-05-22 KST)

<!-- 변경 사유: Cycle 1 / 3단계 목표 결정과 제출 gate를 문서 끝에 append한다. 기존 기록은 삭제하지 않는다. -->

### 결정 근거

- [Original Text/Data] Metric 조사 agent: no-go gate는 source exact duplicate 0, Type B scorer audit 통과, private/public gap ≤8pp. 분포 gate는 length JSD ≤0.08, synthetic-real AUC ≤0.65, template entropy ≥0.75. robustness gate는 worst-group ≥60%, contrast ≥60%, ECE ≤0.08. 1차 private hidden-like acc ≥72%, 2차 ≥75%, 궁극 ≥78%+/leaderboard 85+. → [Exact Interpretation] Cycle 1 / 3단계 목표는 단일 public accuracy가 아니라 no-go, 분포, robustness, hidden-like accuracy를 동시에 만족하는 gate 기반 목표로 설정한다. → [Detailed Explanation/Example] source exact duplicate가 0이 아니면 public-derived leakage 위험이 남아 학습 또는 제출을 중단한다. Type B scorer audit이 실패하면 값 비교 coverage와 채점 신뢰성이 부족하므로 목표 달성으로 인정하지 않는다. private/public gap이 8pp를 넘으면 public 점수가 높아도 hidden 일반화가 불충분하다고 판단한다.

- [Original Text/Data] 중간평가 agent: 현재 검증된 LLM-only 기준선은 public 16/20, hidden 70.00. public 최고 17/20은 참고값이지만 문서 충돌 있음. 지금은 제출 금지. 제출은 #24와 구조적으로 달라야 함: public-derived mutation 중심 탈피, hidden-like validation 통과, Type B/긴 trajectory coverage 개선. → [Exact Interpretation] 현재 기준선은 검증된 LLM-only public 16/20과 hidden 70.00이며, public 17/20은 충돌이 있어 공식 목표 산정의 기준선으로 쓰지 않는다. 지금 leaderboard에 제출하지 않고, 다음 제출 후보는 #24와 구조적으로 다른 데이터/검증/coverage 개선을 증명해야 한다. → [Detailed Explanation/Example] public-derived mutation 중심 데이터로 public 점수만 개선하면 #24와 같은 실패 모드가 반복될 수 있다. 따라서 hidden-like validation을 통과하고 Type B 및 긴 trajectory coverage가 개선된 경우에만 새 제출 후보로 인정한다.

- [Original Text/Data] Git agent: `docs/cycle_tracker.md`는 unstaged 변경 중. credential blocker는 성능 목표가 아니라 실행/제출 blocker로 기록해야 함. 값은 절대 기록하지 말 것. → [Exact Interpretation] 현재 문서 파일의 기존 unstaged 변경은 보존해야 하며, credential 관련 이슈는 accuracy 목표가 아니라 실행과 제출을 막는 blocker로만 기록한다. credential 값은 문서에 남기지 않는다. → [Detailed Explanation/Example] 성능 목표 표에는 credential을 포함하지 않는다. 대신 제출 조건에는 credential blocker 해결이 필요하다고만 적고, 값이나 식별 가능한 secret 본문은 기록하지 않는다.

### 목표

| 구분 | 목표 기준 | 필수 gate | 판정 |
|---|---:|---|---|
| 1차 목표 | private hidden-like acc ≥72% | no-go gate 통과, 분포 gate 통과, robustness gate 통과 | 제출 후보 전 단계 |
| 2차 목표 | private hidden-like acc ≥75% | 1차 gate 유지, Type B/긴 trajectory coverage 개선 확인 | leaderboard 제출 검토 가능 |
| 궁극 목표 | private hidden-like acc ≥78%+ 및 leaderboard 85+ | public-derived mutation 중심 탈피, hidden-like validation 통과, #24 대비 구조적 차별성 확인 | 최종 목표 |

### Gate 기준

- [Original Text/Data] no-go gate는 source exact duplicate 0, Type B scorer audit 통과, private/public gap ≤8pp. → [Exact Interpretation] 이 세 조건 중 하나라도 실패하면 실험 결과를 목표 달성으로 인정하지 않는다. → [Detailed Explanation/Example] source exact duplicate가 1건이라도 있으면 leakage 가능성이 있으므로 no-go다. Type B scorer audit이 통과하지 못하면 Type B 값 비교 성능을 신뢰할 수 없다. private/public gap이 8pp를 넘으면 public 기준 개선이 hidden-like 일반화로 이어졌다고 볼 수 없다.

- [Original Text/Data] 분포 gate는 length JSD ≤0.08, synthetic-real AUC ≤0.65, template entropy ≥0.75. → [Exact Interpretation] 학습/검증 데이터는 길이 분포, synthetic 구분 가능성, template 다양성 기준을 충족해야 한다. → [Detailed Explanation/Example] length JSD가 0.08을 넘으면 trajectory 길이 분포가 hidden-like하지 않다. synthetic-real AUC가 0.65를 넘으면 synthetic 데이터가 너무 쉽게 구분되어 real-like 분포라고 보기 어렵다. template entropy가 0.75 미만이면 template 다양성이 부족하다.

- [Original Text/Data] robustness gate는 worst-group ≥60%, contrast ≥60%, ECE ≤0.08. → [Exact Interpretation] 평균 성능만으로는 통과할 수 없고, 취약 그룹과 contrast 사례 및 calibration이 함께 기준을 만족해야 한다. → [Detailed Explanation/Example] worst-group이 60% 미만이면 특정 유형에서 모델이 실패한다. contrast가 60% 미만이면 의미 차이를 구분하지 못한다. ECE가 0.08을 넘으면 confidence calibration이 부족해 threshold 기반 제출 안정성이 낮다.

### Leaderboard 제출 조건

- [Original Text/Data] 지금은 제출 금지. 제출은 #24와 구조적으로 달라야 함: public-derived mutation 중심 탈피, hidden-like validation 통과, Type B/긴 trajectory coverage 개선. → [Exact Interpretation] 현재 상태에서는 leaderboard 제출을 하지 않는다. 다음 제출은 #24 반복이 아니라 데이터 구성, 검증 방식, coverage 측면에서 구조적 차별점을 갖춘 경우에만 허용한다. → [Detailed Explanation/Example] 단순히 public 16/20 또는 참고값 17/20을 재현하는 제출은 금지한다. 제출 후보는 public-derived mutation 비중을 낮추고, hidden-like validation에서 목표 acc와 gate를 통과하며, Type B와 긴 trajectory 사례에서 coverage 개선을 보여야 한다.

- [Original Text/Data] no-go gate, 분포 gate, robustness gate 기준과 1차/2차/궁극 목표가 제시됨. → [Exact Interpretation] leaderboard 제출 전에는 최소 2차 목표인 private hidden-like acc ≥75%와 모든 gate 통과가 필요하다. 궁극 목표는 private hidden-like acc ≥78%+ 및 leaderboard 85+로 둔다. → [Detailed Explanation/Example] 1차 목표 72%는 제출 후보를 만들기 전의 내부 유효성 확인 기준이다. 2차 목표 75%와 gate 통과가 확인되어야 제출 검토가 가능하며, 최종적으로는 78%+ hidden-like와 leaderboard 85+를 지향한다.

- [Original Text/Data] credential blocker는 성능 목표가 아니라 실행/제출 blocker로 기록해야 함. 값은 절대 기록하지 말 것. → [Exact Interpretation] credential 문제는 모델 성능과 별도로 제출 실행을 막는 blocker다. 값은 문서화하지 않는다. → [Detailed Explanation/Example] credential 상태가 해결되지 않으면 성능 gate를 통과해도 제출하지 않는다. 이 문서에는 credential 값, 토큰 문자열, secret 본문을 기록하지 않고 blocker 존재만 남긴다.

### 다음 단계로 넘길 결정

- 1차 목표는 private hidden-like acc ≥72%와 no-go/분포/robustness gate 전부 통과로 확정한다.
- 2차 목표는 private hidden-like acc ≥75%, Type B/긴 trajectory coverage 개선, 모든 gate 유지로 확정한다.
- 궁극 목표는 private hidden-like acc ≥78%+ 및 leaderboard 85+로 확정한다.
- 지금은 leaderboard에 제출하지 않는다.
- 다음 제출 후보는 #24와 구조적으로 달라야 한다: public-derived mutation 중심 탈피, hidden-like validation 통과, Type B/긴 trajectory coverage 개선이 필요하다.
- credential은 성능 목표가 아니라 실행/제출 blocker로만 추적한다.
- credential 값은 어떤 문서에도 기록하지 않는다.

---

## 사이클 6 — 4단계 달성 방법 결정 (2026-05-22 KST)

<!-- 변경 사유: Cycle 1 / 4단계 달성 방법 결정을 문서 끝에 append한다. 기존 기록은 삭제, 수정, 재정렬하지 않는다. -->

### 방법론 근거 요약

- [Original Text/Data] 조사 agent가 제공한 근거: Lopez-Paz & Oquab의 classifier two-sample test, Xie et al.의 importance resampling, Cheng et al.의 proxy-label enhanced distribution matching, Lee et al.의 deduplication, Deng et al.의 contamination audit, Ribeiro et al.의 CheckList, Gardner et al.의 contrast sets, Swayamdipta et al.의 dataset cartography, Guo et al.의 calibration, Hu et al./Dettmers et al.의 LoRA/QLoRA, Bergstra & Bengio의 random search, Prechelt의 early stopping. → [Exact Interpretation] 현재 Cycle 6의 달성 방법은 모델 구조 변경보다 데이터 분포 통제, 누수 제거, hidden-like 검증 세트 고정, 행동 기반 평가, 학습 설정 고정을 먼저 수행하는 방향이어야 한다. → [Detailed Explanation/Example] synthetic-real AUC, length JSD, template entropy, exact/near duplicate, contrast accuracy, ECE, source별 성능을 측정하지 않으면 public 20 template 암기와 hidden 일반화를 구분할 수 없다. 따라서 먼저 데이터 audit과 split/config manifest를 만들고, 그 결과가 gate를 통과한 뒤에만 LoRA sweep, curriculum, calibration, distillation을 실행한다.

- [Original Text/Data] main 결정: architecture에는 rule engine을 절대 포함하지 않고 LLM-only submission path를 P0 gate로 둔다. → [Exact Interpretation] rule engine은 fallback, 검증 보조 경로, module-level 예외 처리 경로까지 submission architecture에 포함될 수 없다. → [Detailed Explanation/Example] `src/solver.py`에 rule engine fallback이 남아 있으면 adapter가 없거나 LLM inference가 실패하는 순간 제출 경로가 hybrid가 된다. 이 경우 hidden 점수가 좋아도 LLM 과제의 architecture 조건을 위반하므로 제출 후보가 아니다.

- [Original Text/Data] main 결정: 현재 가장 큰 병목은 데이터이며, 모델 구조/대규모 학습보다 hidden-like validation, dedup/contamination audit, distribution matching, split/config manifest를 먼저 구현한다. → [Exact Interpretation] 다음 구현은 학습량 증가나 rank 변경이 아니라 데이터 검증 도구와 split 계약을 우선 대상으로 한다. → [Detailed Explanation/Example] public-derived mutation만 늘리면 public 점수는 오를 수 있지만 hidden 70.00 실패 원인인 length mismatch, Type B coverage 부족, status boundary 부족, template leakage를 해결했다는 증거가 없다. 따라서 `tools/analysis` 중심의 audit 결과가 먼저 필요하다.

### 최종 우선순위

- [Original Text/Data] P0. LLM-only submission path 보장, split contract, dedup/contamination audit, source exact duplicate 0, train-hidden overlap 0. → [Exact Interpretation] 이 항목은 성능 개선 단계가 아니라 제출 가능성의 최소 조건이다. → [Detailed Explanation/Example] `src/solver.py`가 rule engine 없이 동작해야 하며, train/validation/test 또는 hidden-like split 사이에 exact/near duplicate가 없어야 한다. 이 조건이 실패하면 학습이나 leaderboard 제출을 중단한다.

- [Original Text/Data] P1. Hidden-like validation 구축: real/private-like distribution table, length JSD, template entropy, source/type 비율 고정. → [Exact Interpretation] 내부 검증 세트가 목표 hidden 분포를 대표하도록 먼저 고정한다. → [Detailed Explanation/Example] `split_manifest.jsonl`에 `sample_id`, `source`, `template_id`, `mutation_family`, `length_bin`, `label`, `split`을 기록하고, 이후 학습/threshold/prompt 탐색이 이 split을 오염시키지 않도록 한다.

- [Original Text/Data] P2. Distribution matching loop: C2ST AUC, length JSD, template entropy를 매 생성/선별 라운드마다 gate로 사용. → [Exact Interpretation] 데이터 추가는 수량 기준이 아니라 hidden-like 분포와의 거리 기준으로 결정한다. → [Detailed Explanation/Example] synthetic-real AUC가 0.65를 넘거나 length JSD가 0.08을 넘거나 template entropy가 0.75 미만이면 해당 데이터 조합은 학습 후보에서 제외하거나 resampling/filtering을 적용한다.

- [Original Text/Data] P3. Synthetic filtering: quality, diversity, difficulty, real-like discriminator 기준을 결합. → [Exact Interpretation] synthetic data는 많이 만드는 것이 아니라 public template shortcut과 noisy label을 줄이는 방향으로 선별한다. → [Detailed Explanation/Example] Self-Instruct식 생성 결과를 그대로 쓰지 않고, AlpaGasus/DEITA/CrowdSelect 계열 근거에 맞춰 품질, 난이도, 다양성, real-like 점수를 함께 보고 quota를 둔다.

- [Original Text/Data] P4. Behavioral/contrast audit: scorer audit과 public-private gap 원인 분석용으로 별도 보관. → [Exact Interpretation] 평균 accuracy만으로는 Type B, status boundary, 긴 trajectory 실패를 설명할 수 없으므로 행동 단위 검증을 분리한다. → [Detailed Explanation/Example] CheckList/contrast set 방식으로 invariant case, label-flip case, robustness case를 나누고, Type B 값 비교와 `UNEXPECTED_ERROR_STATUS` 경계에서 실패율을 따로 보고한다.

- [Original Text/Data] P5. Hard mining, curriculum, distillation, calibration은 P0-P4가 안정된 뒤 적용. → [Exact Interpretation] 학습 고도화는 데이터 검증 계약이 통과한 뒤의 2차 단계다. → [Detailed Explanation/Example] dataset cartography로 hard-but-clean과 noisy-hard를 분리하고, curriculum은 easy/clean에서 ambiguous/hard로 진행하며, calibration은 best checkpoint 이후 validation-only로 temperature/threshold를 결정한다.

### 구현 대상으로 넘길 파일/모듈 후보

- [Original Text/Data] 구현 후보 1: `tools/analysis/data_audit.py`. → [Exact Interpretation] 데이터셋을 읽어 no-go gate, 분포 gate, robustness 준비 지표를 산출하는 독립 분석 도구가 필요하다. → [Detailed Explanation/Example] 입력 후보는 `/workspace/team6/training_data/*.json`, public label jsonl, 향후 hidden-like 후보 파일이며, 출력은 exact duplicate, near-duplicate 후보, source/template/label/length 분포, length JSD, template entropy, synthetic-real 판별용 feature table, Type B/status boundary coverage를 포함하는 JSON/Markdown 리포트다.

- [Original Text/Data] 구현 후보 2: `tools/analysis/build_hidden_like_split.py` 또는 `tools/analysis/data_audit.py` 내부 split 기능. → [Exact Interpretation] random split이 아니라 group-aware hidden-like split manifest가 필요하다. → [Detailed Explanation/Example] 같은 `template_id`, `source`, `mutation_family`가 train/validation/test를 넘나들지 않도록 `split_manifest.jsonl`을 생성하고, public-derived mutation 직접 파생 샘플과 독립 구조 샘플을 분리한다.

- [Original Text/Data] 구현 후보 3: `configs/train_manifest.yaml` 또는 동등한 단일 실험 manifest. → [Exact Interpretation] rank, alpha, dropout, LR, scheduler, epoch, max_length, batch, gradient accumulation, threshold, prompt format을 스크립트별 기본값으로 흩어 두지 않는다. → [Detailed Explanation/Example] `tools/training/train_wd.py` 같은 개별 학습 스크립트가 서로 다른 하이퍼파라미터와 output path를 갖고 실행되면 결과 비교가 불가능하므로, manifest를 유일한 설정 원천으로 둔다.

- [Original Text/Data] 구현 후보 4: `src/solver.py` LLM-only guarantee 검증/수정. → [Exact Interpretation] data audit 구현과 solver architecture 수정은 파일과 책임을 분리해서 진행한다. → [Detailed Explanation/Example] `src/solver.py`에서는 rule engine fallback, module-level rule-engine prediction path, adapter 누락 시 silent fallback 여부를 검토하고, LLM-only가 불가능하면 명시적으로 실패하도록 수정 후보를 만든다. 이 작업은 data audit 구현과 별도 diff로 관리한다.

- [Original Text/Data] 구현 후보 5: `docs/leaderboard_log.md`와 `docs/cycle_tracker.md` 제출 archive. → [Exact Interpretation] leaderboard 제출을 하지 않는 현재 단계에서는 새 제출 archive를 만들지 않고, 제출하지 않은 이유만 cycle tracker에 기록한다. → [Detailed Explanation/Example] 실제 제출이 발생한 경우에만 submission id, 시간(KST), public/hidden 점수, #24 대비 구조적 차이, 사용 데이터/adapter/checkpoint/threshold를 md로 아카이빙한다.

### Leaderboard 미제출 결정

- [Original Text/Data] 기존 #24 LLM-only 결과는 hidden 70.00, public 16/20이며, 현재는 #24와 구조적으로 다른 검증 통과 결과가 없다. → [Exact Interpretation] 지금 leaderboard에 제출하지 않는다. → [Detailed Explanation/Example] hidden-like validation, dedup/contamination audit, distribution gate, LLM-only path 보장이 완료되지 않았으므로 지금 제출하면 동일한 실패 모드를 leaderboard 기회로 재확인하는 것뿐이다.

- [Original Text/Data] 제출 조건: public-derived mutation 중심 탈피, hidden-like validation 통과, Type B/긴 trajectory coverage 개선, no-go/분포/robustness gate 통과, credential blocker 해결. → [Exact Interpretation] 다음 제출은 최소 2차 목표와 gate 통과 후 검토한다. → [Detailed Explanation/Example] private hidden-like acc ≥75%, public-private gap ≤8pp, source exact duplicate 0, length JSD ≤0.08, synthetic-real AUC ≤0.65, template entropy ≥0.75, ECE ≤0.08이 충족되고 #24 대비 구조적 차이가 문서화되어야 제출 후보가 된다.

### Git/secret blocker

- [Original Text/Data] Git agent 기록: 로컬 `dev`는 `origin/dev`보다 8커밋 ahead, `docs/cycle_tracker.md`는 unstaged 변경 중, untracked 파일은 `tools/eval/eval_3adapters.py`, `tools/training/train_wd.py` 2개. → [Exact Interpretation] 구현 commit은 문서 append, 평가 도구, 학습 스크립트, 실제 data audit/solver 수정으로 분리해야 한다. → [Detailed Explanation/Example] 현재 문서 변경과 untracked 실험 스크립트를 하나의 commit에 섞으면 어떤 변경이 목표 설정 기록이고 어떤 변경이 실행 도구인지 추적하기 어렵다. 다음 구현 전후에는 `git diff --check`, staged 범위 확인, 파일별 commit 분리를 수행한다.

- [Original Text/Data] credential blocker는 tracked 파일과 문서에 흔적이 있으며, 값은 절대 기록하지 않는다. → [Exact Interpretation] secret 문제는 성능 문제가 아니라 실행/제출/공유 blocker다. → [Detailed Explanation/Example] 문서에는 경로와 조치 필요성만 남기고 credential 값, 토큰 문자열, secret 본문은 기록하지 않는다. 이미 history에 포함된 credential이면 단순 삭제만으로 충분하지 않을 수 있으므로 rotate와 history 처리 필요성을 별도 보안 절차로 판단한다.

### 다음 단계로 넘길 결정

- [Original Text/Data] Cycle 6 / 4단계 최종 결정: P0-P2를 먼저 구현하고 P3-P5는 audit 결과 이후 적용한다. → [Exact Interpretation] 다음 implementation worker의 1차 범위는 `tools/analysis` 데이터 audit과 hidden-like split manifest이며, `src/solver.py` LLM-only guarantee는 별도 worker/별도 diff로 검증한다. → [Detailed Explanation/Example] 한 worker가 데이터 audit과 solver architecture를 동시에 바꾸면 책임 경계가 흐려진다. 따라서 data audit worker는 `tools/analysis`만, solver guarantee worker는 `src/solver.py`만, validation worker는 실행/재시작/파일 위치/타인 파일 미수정 여부만 검증한다.

- [Original Text/Data] Cycle 6 / 4단계 제출 결정: 지금은 leaderboard 제출을 하지 않는다. → [Exact Interpretation] 제출 기회를 보존한다. → [Detailed Explanation/Example] #24 대비 구조적으로 다른 검증 결과가 아직 없으므로, 다음 제출 근거는 data audit 리포트와 hidden-like validation 통과 기록이 생긴 뒤에만 작성한다.

## 사이클 6 — 5-6단계 구현 및 실행 결과 (2026-05-22 KST)

- [Original Text/Data] `src/solver.py`에서 LLM-only 제출 경로를 보장하도록 5단계 구현이 완료되었다. `predict`/`predict_one`/`Solver.predict`는 LoRA-only 경로이며, adapter/model이 없으면 `RuntimeError`로 fail-closed한다. `USE_RULE_ENGINE`는 없고, `StatefulOpalVerifier` legacy class는 파일에 남아 있지만 제출 경로에서 호출되지 않는다. → [Exact Interpretation] 제출 경로는 rule engine fallback 없이 LoRA adapter/model 존재를 전제로만 동작한다. → [Detailed Explanation/Example] adapter/model이 준비되지 않은 환경에서는 조용히 rule-based 추론으로 대체하지 않고 즉시 실패하므로, leaderboard 제출 산출물이 LLM-only 조건을 만족했는지 추적 가능하다.

- [Original Text/Data] `tools/analysis/data_audit.py`가 신규 추가되었다. 구현은 stdlib-only이며 JSON/JSONL input, group-aware split manifest, source/label/length/template/duplicate/leakage/JSD/report/gate 생성을 목표로 한다. → [Exact Interpretation] 데이터 audit 실행을 위한 독립 도구가 추가되었지만 외부 패키지 의존성은 만들지 않았다. → [Detailed Explanation/Example] 실제 데이터가 주어지면 source 분포, label 분포, 길이 분포, template 반복, 중복, leakage, JSD와 gate 결과를 한 번의 audit 흐름에서 산출할 수 있다.

- [Original Text/Data] 검증 명령 `python3 -m py_compile`, `git diff --check`, `/tmp` smoke test가 통과했다. → [Exact Interpretation] 5단계 구현은 최소 문법 검증, whitespace 검증, 임시 데이터 기반 기능 smoke test를 통과했다. → [Detailed Explanation/Example] repository 실제 데이터 없이도 Python compile 단계와 diff check, `/tmp`에 만든 샘플 JSON/JSONL 기반 audit 실행이 실패하지 않았음을 기록한다.

- [Original Text/Data] 6단계 실행에서 실제 데이터 경로 `/workspace/team6/training_data`, `training_data`, `data`가 로컬에 없었다. 따라서 실제 audit 산출물은 repo에 만들지 않았고 `/tmp` smoke test만 실행했다. → [Exact Interpretation] 현재 repo에는 실제 데이터 기반 audit report, gate output, split manifest가 없다. → [Detailed Explanation/Example] 로컬에 접근 가능한 실제 학습 데이터가 없으므로 `docs`나 repo 내부 산출물 디렉터리에 실제 audit 결과를 생성하지 않았고, 임시 경로 검증만 수행했다.

- [Original Text/Data] 현재 로컬 환경에는 `nvidia-smi`가 없고 Apple GPU 환경이며 `torch`가 없다. 서버 L40S 48GB 상태는 확인할 수 없다. → [Exact Interpretation] 현재 환경에서는 CUDA GPU 학습 가능 여부와 서버 GPU 상태를 검증하지 못했다. → [Detailed Explanation/Example] `nvidia-smi` 부재와 `torch` 미설치 때문에 로컬 학습 실행, VRAM 확인, L40S 48GB availability 확인을 수행할 수 없었다.

- [Original Text/Data] 현재 학습 시작은 no-go다. 없는 gate 실행 기록은 source duplicate, Type B scorer audit, private/public gap, length JSD actual report, synthetic-real AUC, template entropy pass record, worst-group/contrast/ECE, validation threshold, group-aware split manifest, single train manifest다. → [Exact Interpretation] 학습을 시작할 최소 검증 근거가 아직 부족하다. → [Detailed Explanation/Example] 데이터 중복과 contamination, scorer 품질, public/private 일반화 격차, 길이 분포 차이, synthetic-real 구분 가능성, template 다양성, calibration과 threshold, group-aware split, 단일 train manifest가 모두 기록되어야 학습 재개 여부를 판단할 수 있다.

- [Original Text/Data] leaderboard 제출은 하지 않는다. 이유는 #24 대비 구조적 개선이 leaderboard로 증명될 상태가 아니고, 데이터/GPU/gate blocker가 있기 때문이다. → [Exact Interpretation] 현재 제출은 성능 검증이 아니라 불확실성 재확인에 가깝다. → [Detailed Explanation/Example] 실제 데이터 audit과 GPU 상태 확인, missing gate 통과 기록이 없는 상태에서 제출하면 #24 대비 개선 근거를 설명할 수 없으므로 제출을 보류한다.

- [Original Text/Data] 다음 cycle의 직접 목표는 실제 데이터 접근 후 audit 실행, missing gate tool 확장(Type B/scorer, synthetic-real AUC, ECE/threshold, train_manifest), 그 후 학습 여부 재판단이다. → [Exact Interpretation] 다음 cycle은 학습 실행보다 데이터 접근, audit 보강, gate 충족 여부 판단을 우선한다. → [Detailed Explanation/Example] 실제 데이터가 확인되면 `tools/analysis/data_audit.py`를 실행하고, 부족한 Type B/scorer audit, synthetic-real AUC, ECE/threshold, train manifest 기능을 추가한 뒤 학습 start/go 여부를 다시 결정한다.

## 사이클 7 — 2단계 문제 확인 결정 (2026-05-22 KST)

1. [Original Text/Data] leaderboard 제출/학습은 계속 금지한다. #24 대비 구조적으로 다른 gate 통과 모델이 없고, 서버 데이터 audit 결과가 fail이다. → [Exact Interpretation] 현재 상태는 제출 또는 학습 재개 조건을 만족하지 못한다. → [Detailed Explanation/Example] #24 이후 모델 구조, 데이터 검증, gate 결과가 새 제출을 정당화할 만큼 달라지지 않았고 서버 실제 데이터 audit도 overall gate false이므로, leaderboard 제출과 학습 실행은 모두 보류한다.

2. [Original Text/Data] 서버 실제 데이터 audit 결과는 `/workspace/team6/training_data` 381086 records, groups 10577, group leakage 0, unknown label 378555(99.3358%), pass 1544, fail 987, duplicate groups 6299, normalized_template_entropy 0.394601 < 0.75, top_template_share 0.178834 <= 0.20, length_jsd skipped, overall gate false이다. → [Exact Interpretation] 데이터 규모는 크지만 supervised label 품질과 template 다양성 gate를 통과하지 못했다. → [Detailed Explanation/Example] unknown label이 99.3358%로 대부분을 차지하므로 pass/fail supervised 학습셋으로 보기 어렵고, duplicate groups 6299 및 normalized_template_entropy 0.394601은 반복 artifact 비중이 높다는 신호다. length_jsd도 skipped 상태라 분포 비교 근거가 완결되지 않았으며, 최종 overall gate는 false다.

3. [Original Text/Data] 문제 1순위는 `/workspace/team6/training_data`가 clean supervised dataset이 아니라 ckpt/distillation/spec/gap 등이 섞인 raw artifact pool이라는 점이다. → [Exact Interpretation] 해당 경로를 그대로 학습/검증 데이터로 사용하면 안 된다. → [Detailed Explanation/Example] supervised manifest 없이 raw artifact pool 전체를 train/validation에 투입하면 label unknown, 중복 group, distillation 산출물, checkpoint 관련 artifact가 섞여 평가 계약을 오염시킬 수 있다.

4. [Original Text/Data] 문제 2순위는 서버 repo가 로컬 Cycle 6 변경을 반영하지 않았다는 점이다. 서버 `src/solver.py`에는 아직 rule fallback이 남아 있고, 서버에는 `tools/analysis/data_audit.py`도 없다. → [Exact Interpretation] 서버 학습/제출 경로는 로컬에서 정한 LLM-only 및 data-audit 기준과 불일치한다. → [Detailed Explanation/Example] 서버에서 현재 상태 그대로 학습하거나 제출하면 rule fallback이 제출 경로에 개입할 위험이 있고, 데이터 audit 도구가 없어서 gate 결과를 재현하거나 검증할 수 없다. 따라서 서버 학습/제출은 LLM-only 정책 위반 위험이 있다.

5. [Original Text/Data] 문제 3순위는 일부 학습 데이터/스크립트가 rule engine context를 prompt feature로 쓰고, 로컬 LLM-only solver는 plain prompt를 사용한다는 점이다. → [Exact Interpretation] train/inference format mismatch 위험이 있다. → [Detailed Explanation/Example] 학습 중에는 rule engine context가 포함된 prompt를 보고, 실제 LLM-only inference에서는 plain prompt만 보게 되면 모델이 학습한 입력 형식과 제출 시 입력 형식이 달라져 일반화와 calibration이 깨질 수 있다.

6. [Original Text/Data] contamination/dedup/group split/C2ST/synthetic filtering/calibration/memorization/shortcut 관련 10편 이상 논문 조사 결과는 모두 데이터 검증 계약 선행을 지지한다. → [Exact Interpretation] 모델 학습보다 canonical data contract, split contract, filtering contract, calibration contract를 먼저 확정해야 한다. → [Detailed Explanation/Example] 중복 제거, group-aware split, synthetic-real 구분 가능성 점검, contamination 방지, shortcut 학습 차단, calibration 검증이 빠진 상태에서는 validation 성능이 실제 hidden 성능을 대표한다고 보기 어렵다.

7. [Original Text/Data] 다음 단계 목표는 canonical supervised dataset manifest 작성, unlabeled/ckpt artifact 제외, dedup, hidden-like group split, reference 결합 또는 C2ST 준비, 서버 repo LLM-only/data-audit 동기화 계획 수립이다. → [Exact Interpretation] Cycle 7 다음 작업은 학습 실행이 아니라 데이터 계약과 서버 실행 환경을 맞추는 것이다. → [Detailed Explanation/Example] 먼저 학습 가능한 supervised record만 manifest로 고정하고, unknown label 및 ckpt artifact를 제외하며, duplicate group을 정리한다. 이후 hidden-like group split과 reference 결합 또는 C2ST를 준비하고, 서버 `src/solver.py`와 `tools/analysis/data_audit.py`를 로컬 기준에 맞게 동기화할 계획을 세운다.

8. [Original Text/Data] secret 값은 기록하지 말고, credential blocker는 값 없이 “push/공유/기존 deploy 스크립트 실행 금지”로만 적는다. → [Exact Interpretation] 보안 관련 값, 토큰, credential 본문은 문서에 남기지 않는다. → [Detailed Explanation/Example] credential blocker는 값 없이 `push/공유/기존 deploy 스크립트 실행 금지`로만 기록하며, secret 원문이나 식별 가능한 credential 문자열은 포함하지 않는다.
## 사이클 7 — 3단계 목표 설정 결정 (2026-05-22 KST)

1. [Original Text/Data] 현재 직접 목표는 학습 정확도 개선이 아니라 데이터 계약과 제출 계약 통과다. → [Exact Interpretation] 사이클 7의 3단계는 모델 성능 튜닝보다 데이터 계약과 제출 계약의 통과 여부를 우선 판정한다. → [Detailed Explanation/Example] 학습 정확도 개선 실험은 canonical supervised manifest, 중복 제거, leakage 점검, 제출 서버 실행 경로 검증이 먼저 통과된 뒤에만 다음 목표로 다룬다.

2. [Original Text/Data] 1차 목표 1은 canonical supervised manifest에서 labeled coverage 100%, unknown label 0이다. → [Exact Interpretation] supervised manifest에 포함되는 모든 record는 라벨이 확정되어야 하며 unknown label record는 0개여야 한다. → [Detailed Explanation/Example] manifest 검증 결과에서 labeled coverage가 100%가 아니거나 unknown label count가 1개라도 있으면 1차 gate를 통과하지 못한다.

3. [Original Text/Data] 1차 목표 2는 exact duplicate groups 0이다. → [Exact Interpretation] canonical supervised manifest 기준으로 완전 중복 group은 남기지 않는다. → [Detailed Explanation/Example] 같은 입력 또는 동일하게 정규화된 record가 중복 group으로 묶이면 학습/검증 분리 신뢰도가 깨지므로 duplicate group count를 0으로 만들어야 한다.

4. [Original Text/Data] 1차 목표 3은 group leakage 0 유지다. → [Exact Interpretation] 동일 group이 train/eval/inference 검증 경계에 걸쳐 누출되면 안 된다. → [Detailed Explanation/Example] 같은 template, source group, duplicate family가 서로 다른 split에 동시에 들어가면 hidden-like 평가를 과대평가할 수 있으므로 leakage count를 0으로 유지한다.

5. [Original Text/Data] 1차 목표 4는 normalized template entropy >= 0.75이며 최소 중간 점검은 >=0.60이다. → [Exact Interpretation] template 분포가 과도하게 한쪽으로 몰리지 않았는지 entropy로 점검하고, 최종 기준은 0.75 이상이다. → [Detailed Explanation/Example] 중간 점검에서 0.60 미만이면 template 다양성 확보 작업을 계속해야 하며, 최종 manifest에서는 normalized template entropy가 0.75 이상이어야 한다.

6. [Original Text/Data] 1차 목표 5는 top template share <=0.20 유지다. → [Exact Interpretation] 가장 큰 단일 template이 전체 manifest의 20%를 초과하면 안 된다. → [Detailed Explanation/Example] top template share가 0.20을 넘으면 모델이 특정 template shortcut을 학습할 위험이 커지므로 record 조정 또는 filtering으로 0.20 이하를 유지한다.

7. [Original Text/Data] 1차 목표 6은 length JSD를 skipped에서 actual metric으로 전환하고 <=0.08을 목표로 하는 것이다. → [Exact Interpretation] 길이 분포 차이 검사는 생략 상태가 아니라 실제 산출 metric이어야 하며 목표값은 0.08 이하이다. → [Detailed Explanation/Example] audit report에서 length JSD가 skipped로 남아 있으면 gate 미완료이고, 실제 값이 계산된 뒤 0.08 이하인지 확인해야 한다.

8. [Original Text/Data] 1차 목표 7은 artifact exclusion으로 ckpt_*, embeddings, intermediate, unknown-label records를 supervised manifest에서 제외하는 것이다. → [Exact Interpretation] supervised manifest에는 학습 대상 record만 들어가야 하며 checkpoint, embedding, intermediate artifact, unknown-label record는 제외한다. → [Detailed Explanation/Example] `ckpt_*` 파일, embedding 산출물, 중간 처리물, 라벨 미확정 record가 manifest에 포함되면 supervised data contract 위반으로 처리한다.

9. [Original Text/Data] 1차 목표 8은 server LLM-only sync로 USE_RULE_ENGINE/rule fallback 제출 경로 0, audit tool 서버 재현 가능을 달성하는 것이다. → [Exact Interpretation] 서버 제출 경로는 rule engine 또는 rule fallback 없이 LLM-only로 동작해야 하며 audit tool이 서버에서도 재현 가능해야 한다. → [Detailed Explanation/Example] 제출 경로에서 `USE_RULE_ENGINE`이나 rule fallback에 의존하는 분기가 1개라도 남아 있으면 실패이고, 서버에서 동일한 audit tool을 실행해 같은 계약 검증을 재현해야 한다.

10. [Original Text/Data] 1차 목표 9는 train/eval/inference prompt schema 1개로 고정하는 것이다. → [Exact Interpretation] 학습, 평가, 추론 단계가 서로 다른 prompt 구조를 쓰면 안 되며 하나의 schema로 통일해야 한다. → [Detailed Explanation/Example] train에는 rule context가 들어가고 inference에는 plain prompt만 들어가는 식의 schema mismatch가 있으면 hidden-like 성능과 calibration을 신뢰할 수 없다.

11. [Original Text/Data] 1차 목표 10은 threshold는 calibration split only, ECE는 1차 <=0.12 기록이다. → [Exact Interpretation] threshold 선택은 calibration split에서만 수행하고, 1차 calibration 품질 기준으로 ECE 0.12 이하를 기록한다. → [Detailed Explanation/Example] eval 또는 hidden-like split을 보며 threshold를 고르면 검증 누수이므로 금지하고, calibration split 기준 ECE가 0.12 이하인지 별도 metric으로 남긴다.

12. [Original Text/Data] 2차 목표는 hidden-like acc >=72%, duplicate 0, Type B scorer audit 통과, public-private gap <=8pp, worst-group/contrast >=60%, ECE <=0.08이다. → [Exact Interpretation] 1차 데이터/제출 계약 통과 후에는 hidden-like 정확도와 scorer audit, public-private 안정성, worst-group 성능, calibration을 함께 올리는 것을 2차 기준으로 삼는다. → [Detailed Explanation/Example] hidden-like accuracy가 72% 이상이어도 duplicate가 남거나 Type B scorer audit을 통과하지 못하거나 public-private gap이 8pp를 초과하면 2차 목표 달성으로 보지 않는다.

13. [Original Text/Data] 궁극 목표는 hidden-like acc >=78%+, 모든 gate 유지, 그 뒤 leaderboard 85+를 제출 목표로 승격하는 것이다. → [Exact Interpretation] leaderboard 85+는 즉시 제출 목표가 아니라 hidden-like 78% 이상과 모든 gate 유지 이후에만 승격되는 후속 목표이다. → [Detailed Explanation/Example] hidden-like acc가 78% 이상이고 데이터, 중복, leakage, entropy, prompt schema, calibration, server sync gate가 모두 유지될 때 leaderboard 85+를 공식 제출 목표로 바꾼다.

14. [Original Text/Data] leaderboard 제출은 현재 목표가 아니다. 현재 목표는 “제출하지 않는 것”이다. → [Exact Interpretation] 현재 단계에서는 leaderboard 제출을 실행하지 않는 것이 명시적 목표이다. → [Detailed Explanation/Example] 데이터 계약과 제출 계약 검증이 끝나기 전에는 점수 확인 목적의 제출도 하지 않으며, 제출 유보 상태 자체를 gate 보호 조치로 취급한다.

15. [Original Text/Data] git blocker는 `tools/eval/eval_consistency.py`가 owner 불명 변경으로 새로 보이므로 커밋에서 제외하고, secret 후보 경로 때문에 push 금지이며, secret 값은 기록하지 않는다는 것이다. → [Exact Interpretation] owner가 확인되지 않은 변경 파일은 이번 커밋 대상에서 제외하고, secret 후보 경로가 남아 있는 동안 push를 금지하며, secret 원문은 문서화하지 않는다. → [Detailed Explanation/Example] `tools/eval/eval_consistency.py`는 소유자와 의도를 확인하기 전까지 stage/commit하지 않고, secret 후보 경로 문제는 값 없이 blocker로만 유지하여 push, 공유, 기존 deploy 스크립트 실행을 막는다.

## 사이클 7 — 4단계 달성 방법 결정 (2026-05-22 KST)

1. [Original Text/Data] 지금은 학습 방법을 바꾸는 단계가 아니라 데이터/실행 계약을 구현하는 단계다. → [Exact Interpretation] 사이클 7의 4단계 결정은 optimizer, adapter, epoch, threshold 같은 학습 방법 변경이 아니라 canonical data contract와 execution contract 구현을 우선한다. → [Detailed Explanation/Example] 학습 성능을 올리기 위한 새 training recipe를 추가하거나 기존 training script를 수정하지 않고, 먼저 학습에 들어갈 수 있는 데이터 범위, split 기준, prompt schema, 제출 전 server no-rule 검증 조건을 구현 대상으로 고정한다.

2. [Original Text/Data] 채택 방법 P0은 artifact exclusion + canonical supervised manifest 생성이다. → [Exact Interpretation] supervised manifest에는 실제 학습 가능한 labeled record만 포함하고, checkpoint, embedding, intermediate artifact, unknown-label record는 제외한다. → [Detailed Explanation/Example] `ckpt_*`, embedding 산출물, 중간 처리 산출물, label이 확정되지 않은 record가 manifest에 들어가면 학습 데이터 계약 위반으로 처리하며, manifest가 canonical source가 되기 전에는 학습을 시작하지 않는다.

3. [Original Text/Data] 채택 방법 P1은 exact/near dedup + contamination audit이다. → [Exact Interpretation] 완전 중복과 근접 중복을 함께 점검하고, 학습/검증/참조 경계에서 contamination 가능성을 audit 대상으로 삼는다. → [Detailed Explanation/Example] 동일하거나 매우 유사한 prompt/record가 서로 다른 split에 걸치면 hidden-like 평가가 과대평가될 수 있으므로, duplicate group과 contamination 의심 사례를 manifest 검증 단계에서 기록하고 차단한다.

4. [Original Text/Data] 채택 방법 P2는 group-aware hidden/calibration split 재생성이다. → [Exact Interpretation] hidden-like split과 calibration split은 record 단위 무작위 분리가 아니라 group 경계를 보존하는 방식으로 다시 생성해야 한다. → [Detailed Explanation/Example] 같은 source, template, duplicate family가 train, hidden-like, calibration split에 동시에 들어가면 leakage가 발생하므로, threshold 선택과 hidden-like 성능 판단은 group-aware split 재생성 뒤에만 유효하다.

5. [Original Text/Data] 채택 방법 P3은 entropy balancing + source/template quota이다. → [Exact Interpretation] manifest의 source 및 template 분포가 한쪽으로 과도하게 몰리지 않도록 entropy와 quota 기준을 함께 적용한다. → [Detailed Explanation/Example] 특정 template이 manifest의 대부분을 차지하면 모델이 문제 해결 능력보다 template shortcut을 학습할 수 있으므로, normalized template entropy와 top template share 같은 지표를 quota 조정 기준으로 사용한다.

6. [Original Text/Data] 채택 방법 P4는 public/reference 결합으로 length JSD와 C2ST 산출 준비이다. → [Exact Interpretation] public 데이터와 reference 데이터를 결합해 길이 분포 차이와 synthetic-real 구분 가능성 검사를 실제 metric으로 계산할 준비를 한다. → [Detailed Explanation/Example] length JSD가 skipped로 남아 있으면 데이터 분포 점검이 미완료 상태이므로, public/reference 기반으로 length JSD를 산출하고 C2ST를 준비해 manifest가 hidden-like 분포를 대표하는지 확인한다.

7. [Original Text/Data] 채택 방법 P5는 synthetic filtering quality/diversity/difficulty/relevance 적용은 audit 이후이다. → [Exact Interpretation] synthetic record filtering은 먼저 audit 결과를 확보한 뒤 quality, diversity, difficulty, relevance 기준으로 적용한다. → [Detailed Explanation/Example] audit 없이 synthetic filtering을 먼저 적용하면 어떤 문제를 고친 것인지 검증할 수 없으므로, dedup, contamination, split, entropy, distribution audit 이후에 synthetic record의 품질, 다양성, 난이도, 관련성을 기준으로 선별한다.

8. [Original Text/Data] 채택 방법 P6은 train/inference schema contract와 format hash 고정이다. → [Exact Interpretation] 학습과 추론의 입력 schema를 하나로 고정하고, format hash를 통해 adapter와 schema의 호환성을 검증한다. → [Detailed Explanation/Example] train에는 rule context가 있고 inference에는 plain prompt만 있는 방식은 금지하며, schema hash가 없는 adapter는 어떤 입력 형식으로 학습되었는지 검증할 수 없으므로 무효로 취급한다.

9. [Original Text/Data] 운영 원칙은 manifest 없으면 학습 금지, schema hash 없으면 adapter 무효, calibration split 없으면 threshold 무효, server no-rule 검증 없으면 제출 금지이다. → [Exact Interpretation] 데이터, schema, calibration, server execution gate 중 하나라도 없으면 다음 실행 단계로 넘어가지 않는다. → [Detailed Explanation/Example] manifest가 없으면 training job을 시작하지 않고, schema hash가 없는 adapter는 평가 대상으로 쓰지 않으며, calibration split이 없으면 threshold를 선택하지 않고, server no-rule 검증이 없으면 leaderboard나 제출 경로 실행을 금지한다.

10. [Original Text/Data] 5단계 구현 범위는 `tools/analysis/build_supervised_manifest.py`, `tools/analysis/validate_manifest.py`, `.gitignore` 산출물 ignore 보강이다. 가능하면 `configs/train_manifest.cycle7.json` skeleton도 추가하되 학습 스크립트 수정은 하지 않는다. → [Exact Interpretation] 다음 구현 단계는 manifest 생성기, manifest 검증기, 산출물 ignore 규칙 보강에 한정하며, 선택적으로 train manifest config skeleton만 추가한다. → [Detailed Explanation/Example] `tools/analysis/build_supervised_manifest.py`는 canonical supervised manifest를 만들고, `tools/analysis/validate_manifest.py`는 manifest gate를 점검하며, `.gitignore`는 생성 산출물이 커밋되지 않도록 보강한다. `configs/train_manifest.cycle7.json`은 가능할 때 skeleton만 추가하고, training script의 동작은 변경하지 않는다.

11. [Original Text/Data] 제외 대상은 `tools/eval/eval_consistency.py`, `tools/eval/eval_3adapters.py`, `tools/training/train_wd.py`, 기존 training scripts 수정 금지이다. → [Exact Interpretation] 평가 스크립트와 학습 스크립트 변경은 이번 단계 범위에서 제외한다. → [Detailed Explanation/Example] manifest와 validation 계약을 먼저 확정하기 전에는 `eval_consistency`, `eval_3adapters`, `train_wd` 또는 기존 training script를 건드리지 않으며, 학습 방법 변경으로 문제를 덮지 않는다.

12. [Original Text/Data] server sync tool은 이후 단계로 미루되, password/sshpass/secret 저장 방식은 금지한다. → [Exact Interpretation] 서버 동기화 자동화는 이번 5단계 구현 범위가 아니며, credential을 파일이나 스크립트에 저장하는 방식은 허용하지 않는다. → [Detailed Explanation/Example] 서버 sync tool은 후속 단계에서 별도 설계하고, password, sshpass, secret 값을 repo, 문서, 스크립트, config에 남기지 않는다. 이 기록에도 secret 값은 포함하지 않는다.

13. [Original Text/Data] leaderboard/학습은 계속 금지이다. → [Exact Interpretation] 현재 결정 이후에도 leaderboard 제출과 학습 실행은 gate 통과 전까지 금지 상태를 유지한다. → [Detailed Explanation/Example] 5단계 구현은 manifest와 validation contract를 만드는 작업이며, 해당 산출물이 검증되기 전에는 training job을 실행하거나 leaderboard 제출로 점수를 확인하지 않는다.

## 사이클 7 — 5-6단계 구현 및 실행 결과 (2026-05-22 KST)

1. [Original Text/Data] 5단계 구현 완료 대상은 `tools/analysis/build_supervised_manifest.py`, `tools/analysis/validate_manifest.py`, `.gitignore`, `configs/train_manifest.cycle7.json`이다. → [Exact Interpretation] 사이클 7의 5단계 구현 범위는 supervised manifest builder, manifest validator, 산출물 ignore 규칙, train manifest config skeleton까지 완료된 것으로 기록한다. → [Detailed Explanation/Example] `tools/analysis/build_supervised_manifest.py`는 canonical supervised manifest 생성 책임을 갖고, `tools/analysis/validate_manifest.py`는 manifest gate 검증 책임을 갖는다. `.gitignore`는 생성 산출물이 repo에 섞이지 않도록 보호하며, `configs/train_manifest.cycle7.json`은 실제 canonical manifest가 없을 때 null skeleton으로 남아 있는 config 기준점이다.

2. [Original Text/Data] builder 구현 내용은 pass/fail label만 포함, unknown/blocklist/rule-context 제외, exact dedup, group split, report 생성이다. → [Exact Interpretation] builder는 학습 대상 supervised label을 pass/fail로 제한하고, 불확실하거나 금지된 입력 및 rule context 오염 가능성이 있는 record를 제외하며, 중복 제거와 group-aware split 및 실행 report 생성을 수행한다. → [Detailed Explanation/Example] label이 unknown인 record는 학습 신호가 아니므로 제외하고, blocklist 또는 rule-context literal이 포함된 record는 leakage와 policy contamination 위험 때문에 제외한다. exact dedup은 동일 record의 반복 학습을 막고, group split은 같은 계열의 record가 train/validation 계열 split에 동시에 들어가는 leakage를 줄인다. report는 포함, 제외, split, dedup 결과를 사후 audit할 수 있게 하는 산출물이다.

3. [Original Text/Data] validator 구현 내용은 required fields, hard gates, reference length JSD fail-on-skipped, exit code 반영이다. → [Exact Interpretation] validator는 manifest record schema의 필수 필드 존재 여부를 확인하고, hard gate 실패를 명시적으로 실패 처리하며, reference length JSD가 skipped인 경우도 실패로 간주하고, 검증 결과를 process exit code로 반영한다. → [Detailed Explanation/Example] required fields가 누락되면 downstream training이 같은 record를 일관되게 해석할 수 없으므로 실패한다. hard gates는 contamination, schema, split, distribution 조건을 통과해야 한다는 계약이며, reference length JSD가 skipped이면 실제 분포 검사가 완료되지 않은 상태이므로 성공으로 처리하지 않는다. exit code는 CI, shell smoke, 서버 실행에서 사람이 로그를 읽지 않아도 실패를 감지하게 하는 인터페이스이다.

4. [Original Text/Data] 검증은 py_compile 통과, json.tool 통과, git diff --check 통과, /tmp integration smoke 통과이다. rule_context literal 누락 발견 후 수정했고 재검증 통과했다. → [Exact Interpretation] 구현 산출물은 Python syntax compile, JSON syntax validation, whitespace/error diff check, 임시 디렉터리 기반 integration smoke를 통과했으며, rule_context literal exclusion 누락은 결함으로 발견되어 수정 후 같은 검증을 다시 통과했다. → [Detailed Explanation/Example] `py_compile` 통과는 Python 파일이 문법적으로 import 가능한 상태임을 의미하고, `json.tool` 통과는 config skeleton이 JSON 문법을 만족함을 의미한다. `git diff --check` 통과는 trailing whitespace나 conflict marker 같은 diff-level 문제가 없음을 뜻한다. `/tmp integration smoke` 통과는 repo 외부 임시 경로에서도 builder와 validator가 최소 실행 계약을 만족했음을 의미한다. 초기 smoke에서 rule_context literal 제외가 누락된 것이 확인되었고, exclusion logic을 보강한 뒤 재검증이 통과했다.

5. [Original Text/Data] 6단계 실행에서 서버 actual manifest 생성은 실패했다. 이유는 비밀번호 없는 SSH 또는 ControlSocket이 없고, sshpass, 명령행 비밀번호, 파일 저장 방식은 보안상 금지이기 때문이다. 기존 deploy script 실행도 금지했다. → [Exact Interpretation] 서버 접속을 자동화할 안전한 인증 경로가 없어서 `/workspace/team6/training_data`에서 실제 manifest를 생성하지 못했으며, credential을 노출하거나 저장하는 우회 방식 및 기존 deploy script 실행은 허용하지 않았다. → [Detailed Explanation/Example] 비밀번호 없는 SSH key 또는 이미 열린 SSH ControlSocket이 없으면 agent가 서버 명령을 안전하게 실행할 수 없다. `sshpass`, command-line password, password file 저장은 process list, shell history, filesystem에 secret이 남을 수 있으므로 금지한다. 기존 deploy script는 범위와 부작용이 확인되지 않은 상태에서 실행하면 repo sync, training, submission 같은 예상 밖 동작을 일으킬 수 있으므로 실행하지 않았다.

6. [Original Text/Data] GPU는 이번 agent가 로컬 macOS에서만 확인되어 서버 NVIDIA 상태 실측에 실패했다. batch 결정은 불가하다. → [Exact Interpretation] 서버에서 `nvidia-smi` 또는 동등한 실측 정보를 확보하지 못했기 때문에 GPU memory, utilization, driver/runtime 상태를 근거로 batch size를 정할 수 없다. → [Detailed Explanation/Example] 로컬 macOS 환경의 확인 결과는 서버 GPU 상태를 대표하지 않는다. 서버 NVIDIA 장치 수, VRAM, 현재 점유율, CUDA runtime 상태가 없으면 batch size, gradient accumulation, precision 설정을 근거 있게 선택할 수 없으므로 batch 결정은 보류한다.

7. [Original Text/Data] 학습 모니터링 상태는 config skeleton null 45개, actual canonical manifest 없음, validator report 없음, safety gate 비활성이다. 학습 시작은 no-go이다. → [Exact Interpretation] 현재 학습 입력 계약은 skeleton 상태일 뿐 실제 데이터와 검증 report가 없고 safety gate도 켜지지 않았으므로 training job을 시작하면 안 된다. → [Detailed Explanation/Example] `configs/train_manifest.cycle7.json`에 null 값이 45개 남아 있으면 실행 가능한 actual config가 아니라 placeholder skeleton이다. actual canonical manifest가 없으면 학습 record 집합이 확정되지 않았고, validator report가 없으면 hard gate 통과 여부를 증명할 수 없다. safety gate가 비활성인 상태에서는 contamination, schema mismatch, skipped metric을 막을 수 없으므로 학습 시작은 no-go로 기록한다.

8. [Original Text/Data] git 상태는 서버 산출물이 로컬 repo에 섞이지 않았고 staged 없음이다. push 금지는 유지한다. owner 불명 `tools/eval/eval_consistency.py`, 기존 untracked `eval_3adapters.py`, `train_wd.py`는 제외 유지한다. → [Exact Interpretation] 서버 실행 실패로 인해 서버 산출물이 local working tree에 유입되지 않았고, commit 대상으로 staged된 파일도 없으며, push는 계속 금지 상태이다. 소유자와 범위가 불명확한 평가 및 학습 관련 파일은 이번 단계에서 건드리지 않는 대상으로 유지한다. → [Detailed Explanation/Example] server output이 local repo에 섞이면 actual manifest, report, logs가 의도치 않게 commit될 수 있으므로 유입 없음은 중요한 상태다. staged 없음은 아직 commit 준비 상태가 아님을 뜻한다. `tools/eval/eval_consistency.py`, `eval_3adapters.py`, `train_wd.py`는 현재 5-6단계 manifest/gate 기록 범위가 아니므로 수정, staging, push 대상에서 제외한다.

9. [Original Text/Data] 다음 반복의 시작점은 안전한 SSH ControlSocket 또는 키 기반 접속이 확보되면 `/workspace/team6/training_data`에서 builder와 validator를 실행하는 것이다. 그 전에는 서버 학습과 leaderboard 제출을 금지한다. → [Exact Interpretation] 후속 agent는 credential을 노출하지 않는 서버 접속 경로를 먼저 확보한 뒤 actual canonical manifest와 validator report를 생성해야 하며, 그 산출물이 없으면 training 및 leaderboard 경로를 열 수 없다. → [Detailed Explanation/Example] 안전한 SSH ControlSocket 또는 key-based login이 준비되면 서버의 `/workspace/team6/training_data`에서 `tools/analysis/build_supervised_manifest.py`와 `tools/analysis/validate_manifest.py`를 실행한다. 실행 뒤 canonical manifest, validator report, hard gate 통과 여부, reference length JSD 결과를 확인해야 한다. 그 전까지는 서버 training job 시작과 leaderboard 제출 모두 금지한다.

10. [Original Text/Data] secret 값은 절대 기록하지 않는다. → [Exact Interpretation] 이 섹션에는 password, token, private key, command-line credential, credential file path 또는 secret으로 재구성 가능한 값을 포함하지 않는다. → [Detailed Explanation/Example] 서버 접속 실패 원인은 안전한 인증 경로 부재로만 기록하고, 실제 비밀번호나 인증 material은 문서, command, config, report에 남기지 않는다.
