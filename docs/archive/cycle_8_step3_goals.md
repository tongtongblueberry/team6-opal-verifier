# 사이클 8 — 3단계: 목표 설정

날짜: 2026-05-22 KST
기준선: LLM-only hidden 70.00, public 16/20
Rule engine 최고: hidden 73.00 (71.50 확인, 73.00은 MEMORY 기록)
마감: 2026-06-08 (17일 남음)

---

## 1. Agent 불일치 해소

### 1차 목표: Agent 3-1(78) vs Agent 3-2(73)

**결정: Agent 3-2의 73을 채택하되, 기한을 5일로 조정한다.**

근거:
- Agent 3-1의 78은 metric 목표(ECE, MCC, Vendi Score 등)가 모두 충족된 이상적 상태를 가정한다. 그러나 현재 canonical supervised manifest조차 없고, 서버에서 actual audit를 실행하지 못한 상태다(사이클 7 기록). 데이터 계약 미완성 상태에서 hidden +8점(70→78)을 3일 내 달성하는 것은 비현실적이다.
- Agent 3-2의 73은 "threshold 조정(+1-2점) + 기존 2,531건 supervised 데이터 활용"이라는 즉시 실행 가능한 작업에 기반한다. hidden 70→73은 +3점이며, 이는 threshold 최적화(+1점)와 데이터 다양성 개선(+2점)으로 달성 가능한 범위다.
- 단, Agent 3-2의 "3일"은 사이클 6-7의 데이터 계약 gate를 모두 통과해야 하는 현실을 과소평가한다. 5일(5/27 KST)로 완화한다.

배제 이유 (Agent 3-1의 78):
- 현재 Vendi Score ~3-5 → 15, Length Coverage ~0.04 → 0.50, ECE ~0.20 → 0.08을 동시에 달성하려면 데이터 생성, 분포 매칭, calibration 파이프라인을 새로 구축해야 한다. 이는 1차 목표가 아니라 2차 이후 점진적 개선 대상이다.

### 궁극 목표: Agent 3-1(85) vs Agent 3-2(80)

**결정: 80을 채택한다. 85는 stretch goal로만 기록한다.**

근거:
- Agent 3-2의 분석이 정확하다: Qwen3.5-4B + LoRA의 현실적 상한은 ~80-84다. 4B 모델의 reasoning capacity, LoRA의 표현력 한계, 학습 데이터 품질 상한을 종합하면 80이 도전적이지만 달성 가능한 목표다.
- 85+는 더 큰 모델(9B/27B) 또는 앙상블, 또는 rule engine 하이브리드를 필요로 할 가능성이 높다. 현재 LLM-only 아키텍처 제약과 L40S 48GB / 3시간 제한을 고려하면 4B 단일 모델이 주력이다.
- 9B LoRA를 시도할 여지는 있으나 (L40S 48GB에서 QLoRA로 가능), 먼저 4B에서 80을 달성한 뒤 모델 스케일업을 검토하는 것이 리스크 관리상 합리적이다.

배제 이유 (Agent 3-1의 85):
- 85는 4B LoRA 단독으로 달성한 선행 사례가 없다. Agent 3-1이 근거로 제시한 metric 개선(Vendi 15+, ECE 0.08 이하)이 실현되더라도 85 도달 보장이 없다.
- 17일 안에 데이터 계약 구축 + 분포 매칭 + 학습 + 평가 + 제출을 모두 수행하면서 85를 목표로 하면, gate를 타협할 유혹이 생긴다. 80을 확실히 달성하는 것이 과제 평가에서 더 유리하다.

### Metric 목표 vs Leaderboard 목표

**결정: 둘 다 추적하되, 제출 판정은 Leaderboard 목표만 사용한다. Metric은 진단 도구로 활용한다.**

근거:
- Agent 3-1이 제안한 10개 metric 중 실제로 hidden 점수와 인과관계가 입증된 것은 Length Coverage, ECE, MCC 3개다. 나머지(NovelSum, Vendi, MAUVE 등)는 상관은 있으나 인과는 미검증이다.
- Metric 목표를 제출 gate로 쓰면 false negative(metric은 미달이지만 실제 hidden은 개선)이 발생할 수 있다. 17일 남은 상황에서 false negative는 치명적이다.
- 대신 Length Coverage, ECE, MCC를 대시보드 지표로 추적하여 "왜 hidden이 올랐는지/안 올랐는지" 진단에 사용한다.

---

## 2. 최종 목표

### 1차 목표
- **기한**: 2026-05-27 KST (5일)
- **Hidden 점수**: 73.00 (rule engine 수준 도달)
- **핵심 metric**:
  - threshold sweep 최적값 적용 (현재 0.5 → 최적값)
  - hidden-like validation acc >= 72%
  - Length JSD 실측값 산출 (skipped → actual)
- **핵심 작업**:
  1. T-P0 해결: solver.py threshold 파라미터화 + sweep 최적값 반영 (비용 0, +1점 즉시)
  2. D-P3 해결: 서버 supervised 2,531건에서 canonical manifest 생성 (build_supervised_manifest.py 실행)
  3. D-P0 부분 해결: manifest에서 길이 10+ step 데이터 비중 확보 (최소 15%)
  4. 학습 실행: r=8, alpha=16, NEFTune=5, LoRA+, 5 epoch
  5. eval_checkpoints.py --sweep로 최적 checkpoint + threshold 선택
- **제출 조건**: hidden-like validation acc >= 72% AND threshold가 calibration split 기반으로 선택됨 AND source exact duplicate 0

### 2차 목표
- **기한**: 2026-05-31 KST (9일)
- **Hidden 점수**: 76.00
- **핵심 metric**:
  - ECE <= 0.12
  - MCC >= 0.55
  - Length Coverage >= 0.25 (현재 ~0.04에서 6배 개선)
  - normalized template entropy >= 0.60
- **핵심 작업**:
  1. D-P0 본격 해결: 10-20 step trajectory 합성 생성 (캐시된 Qwen3.5-2B/9B 활용, multi-source synthetic)
  2. D-P1 해결: public 20 template 외 독립 template 구조 생성으로 origin 다양성 확보
  3. D-P2 해결: pass:fail 비율 밸런싱 (IFD 필터링으로 고품질 fail 선별)
  4. DPE 적용 테스트: training-free RoPE 길이 외삽으로 긴 trajectory 추론 개선
  5. validation split으로 early stopping 적용
- **제출 조건**: 1차 조건 유지 + hidden-like validation acc >= 75% + public-private gap <= 8pp + Type B coverage 개선 확인

### 궁극 목표
- **기한**: 2026-06-07 KST (마감 전일, 16일)
- **Hidden 점수**: 80.00
- **Stretch**: 85.00 (4B 상한 초과 시 9B QLoRA 또는 앙상블 검토)
- **핵심 metric**:
  - ECE <= 0.08
  - MCC >= 0.65
  - Length Coverage >= 0.50
  - Vendi Score >= 10
  - worst-group acc >= 60%
  - contrast acc >= 60%
- **핵심 작업**:
  1. Self-Consistency: 동일 입력 다중 추론 + 다수결 (사이클 7 논문 조사 결과 적용)
  2. Adapter Merging: 다양한 데이터 조합으로 학습한 2-3개 adapter의 가중 병합
  3. SDFT: self-distillation fine-tuning으로 distribution gap 브릿지
  4. Temperature scaling 기반 calibration 최적화
  5. (조건부) 9B QLoRA 또는 4B 앙상블로 모델 capacity 확장
- **제출 조건**: 2차 조건 유지 + hidden-like validation acc >= 78% + 모든 gate 유지 + #24 대비 구조적 차별성 문서화

---

## 3. Gate 분류

### Must-have (학습/제출 전 반드시 통과)

| Gate ID | 조건 | 판정 기준 | 실패 시 조치 |
|---------|------|----------|-------------|
| G-NO-1 | source exact duplicate = 0 | manifest dedup 후 확인 | 학습 금지, manifest 재생성 |
| G-NO-2 | unknown label = 0 (manifest 내) | supervised label 확정 record만 포함 | 미확정 record 제외 |
| G-NO-3 | LLM-only 제출 경로 보장 | solver.py에 rule fallback 0 | solver.py 수정 |
| G-NO-4 | train/inference prompt schema 일치 | format hash 비교 | schema 통일 후 재학습 |
| G-NO-5 | group leakage = 0 | train/validation split 간 동일 group 없음 | split 재생성 |
| G-SUB-1 | hidden-like validation acc >= 목표 | 1차 72%, 2차 75%, 궁극 78% | 제출 보류, 다음 실험 |
| G-SUB-2 | threshold는 calibration split only | eval/hidden-like split으로 threshold 선택 금지 | threshold 재선정 |
| G-SUB-3 | #24 대비 구조적 차별성 | 데이터 구성, 검증 방식, coverage 중 1개 이상 변경 | 동일 구조 제출 금지 |

### Nice-to-have (개선 추적용, 제출 차단 아님)

| Gate ID | 조건 | 현재 | 목표 | 용도 |
|---------|------|------|------|------|
| G-NICE-1 | ECE <= 0.08 | ~0.20 | 0.08 | calibration 품질 진단 |
| G-NICE-2 | MCC >= 0.65 | ~0.40 | 0.65 | 불균형 판별력 진단 |
| G-NICE-3 | Length Coverage >= 0.50 | ~0.04 | 0.50 | 길이 분포 매칭 진단 |
| G-NICE-4 | Vendi Score >= 15 | ~3-5 | 15 | 학습 데이터 다양성 진단 |
| G-NICE-5 | normalized template entropy >= 0.75 | 0.39 | 0.75 | template 다양성 진단 |
| G-NICE-6 | top template share <= 0.20 | 0.18 | 0.20 | template 집중도 모니터링 |
| G-NICE-7 | worst-group acc >= 60% | 미측정 | 60% | 취약 그룹 진단 |
| G-NICE-8 | contrast acc >= 60% | 미측정 | 60% | 의미 차이 구분 진단 |
| G-NICE-9 | public-private gap <= 8pp | 10pp | 8pp | 일반화 격차 진단 |

---

## 4. 제출 기준

### 원칙
- 사이클 6-7에서 확립한 "제출 금지" 정책을 **조건부 해제**한다.
- 이유: 17일 남은 상황에서 hidden 점수 피드백 없이 개선하는 것은 불가능하다. 완벽주의가 아닌 빠른 실험 반복이 필요하다 (Agent 3-2 경고).

### 제출 허용 조건
1. Must-have gate G-NO-1 ~ G-NO-5 전부 통과
2. Must-have gate G-SUB-1 (hidden-like validation acc >= 해당 단계 목표) 통과
3. Must-have gate G-SUB-3 (#24 대비 구조적 차별성) 통과
4. 위 조건 충족 시, **하루 최대 1회** 제출

### 제출 금지 조건
- Must-have gate 1개라도 실패
- 직전 제출과 데이터/모델/threshold가 동일 (구조적 차별성 없음)
- hidden-like validation에서 직전 제출보다 낮은 acc

### 제출 전략
- 1차 목표 달성 시 (hidden-like >= 72%): 첫 제출로 hidden 실측값 확보
- 이후: hidden 실측값과 hidden-like validation 간 gap 분석 → 다음 실험 방향 결정
- 마감 3일 전 (6/5): 최고 성능 모델 최종 제출, 이후 안전 마진 확보

---

## 5. 결정 근거

### 1차 목표 73의 근거
- **threshold 효과**: 사이클 2에서 0.50→0.70 변경 시 +1점 확인. 현재 solver.py에 0.5 하드코딩이므로 즉시 +1점 가능 (2단계 분석 T-P0).
- **데이터 활용**: 서버에 supervised 2,531건 존재 (Agent 3-2). 현재 210건만 사용. 10배 이상 데이터 증가는 hidden +2-3점 예상 (AlpaGasus, ICLR 2024; Long Is More, ICML 2024).
- **현실적 제약**: canonical manifest 생성 + dedup + split + 학습 + 평가에 최소 3-4일 필요.

### 2차 목표 76의 근거
- **길이 분포 매칭**: D-P0(길이 분포 불일치)이 hidden 70 정체의 최대 원인. 10-20 step trajectory를 합성 생성하면 Length Coverage 0.04→0.25로 개선 가능 (Multi-source synthetic, ACL 2026).
- **DPE**: training-free RoPE 외삽으로 추론 시 긴 trajectory 처리 개선 (비용 0).
- **pass:fail 밸런싱**: IFD 필터링으로 label 불균형 완화 (NAACL 2024, 이미 구현됨).

### 궁극 목표 80의 근거
- **Self-Consistency + Adapter Merging**: 사이클 7 논문 조사에서 teacher 초월 가능성 확인. 동일 모델의 다중 추론 + 다수결은 +2-4점 개선 보고 (Wang et al., 2023).
- **SDFT**: distribution gap 브릿지로 synthetic-real 격차 완화 (ACL 2024).
- **4B 상한 ~80-84**: Agent 3-2 분석 기반. 4B LoRA로 80 달성 후 추가 개선은 모델 스케일업 필요.

### 85(stretch) 배제 이유
- 4B 단독으로 85 달성 선례 없음.
- 9B QLoRA는 L40S 48GB에서 가능하나 학습 시간 2-3배 증가 → 실험 반복 횟수 감소.
- 80 달성 후 남은 시간에 따라 9B 또는 앙상블을 시도하는 것이 리스크 최소화.

### 사이클 6-7의 gate 정책 완화 근거
- 사이클 6-7은 "제출 금지, 학습 금지, 데이터 계약 선행"을 결정했다. 이는 원칙적으로 옳으나, 17일 마감에서 실행 가능성을 고려하지 않았다.
- Agent 3-2의 핵심 경고: "gate 완벽주의 < 빠른 실험 반복". 모든 gate를 완벽히 통과한 뒤 학습하면 학습 시작이 5/28 이후가 되어 실험 반복 횟수가 3-4회로 제한된다.
- 타협안: Must-have gate는 유지하되, Nice-to-have gate(Vendi Score, MAUVE, worst-group 등)는 "추적용"으로 격하한다. Must-have gate만 통과하면 학습과 제출을 허용한다.
- 구체적으로: source exact duplicate 0, unknown label 0, LLM-only 경로 보장, prompt schema 일치, group leakage 0은 반드시 통과. ECE, MCC, Vendi Score, Length Coverage, template entropy는 추적만 한다.

---

## 6. 추적할 Metric 체계

| Metric | 현재 | 1차 (5/27) | 2차 (5/31) | 궁극 (6/7) | 측정 방법 | 역할 |
|--------|------|-----------|-----------|-----------|----------|------|
| Hidden Score | 70.00 | 73.00 | 76.00 | 80.00 | leaderboard 제출 | **판정 기준** |
| hidden-like val acc | 미측정 | >= 72% | >= 75% | >= 78% | eval_checkpoints.py (calibration split 제외) | **Must-have gate** |
| threshold | 0.50 | sweep 최적값 | sweep 최적값 | sweep 최적값 | eval_checkpoints.py --sweep (calibration split only) | **Must-have gate** |
| source exact dup | 미측정 | 0 | 0 | 0 | validate_manifest.py | **Must-have gate** |
| group leakage | 0 | 0 | 0 | 0 | validate_manifest.py | **Must-have gate** |
| Length Coverage | ~0.04 | 실측값 산출 | >= 0.25 | >= 0.50 | 학습/hidden 길이 분포 겹침 면적 | Nice-to-have |
| ECE | ~0.20 | 실측값 산출 | <= 0.12 | <= 0.08 | calibration split에서 산출 | Nice-to-have |
| MCC | ~0.40 | 실측값 산출 | >= 0.55 | >= 0.65 | hidden-like validation에서 산출 | Nice-to-have |
| Vendi Score | ~3-5 | 실측값 산출 | >= 8 | >= 10 | 학습 manifest의 embedding diversity | Nice-to-have |
| template entropy | 0.39 | >= 0.50 | >= 0.60 | >= 0.75 | validate_manifest.py | Nice-to-have |
| public-private gap | 10pp | 측정 | <= 8pp | <= 8pp | public acc - hidden acc | Nice-to-have |

---

## 7. 다음 단계

### 즉시 실행 (오늘, 5/22)
1. **T-P0**: solver.py의 threshold를 0.5 하드코딩에서 config 파라미터로 변경
2. 서버 접속하여 build_supervised_manifest.py 실행 → canonical manifest 생성
3. validate_manifest.py로 Must-have gate 확인

### 5/23-24
4. canonical manifest 기반 첫 학습 (r=8, alpha=16, NEFTune=5, LoRA+, 5 epoch)
5. eval_checkpoints.py --sweep로 최적 checkpoint + threshold 선택
6. hidden-like validation acc 측정 → G-SUB-1 통과 여부 판정

### 5/25-27 (1차 목표 마감)
7. 1차 gate 전부 통과 시 leaderboard 제출
8. hidden 실측값과 hidden-like validation 간 gap 분석

### 5/28-31 (2차 목표)
9. 10-20 step trajectory 합성 생성 (multi-source synthetic)
10. DPE 적용 테스트
11. IFD 기반 pass:fail 밸런싱
12. 2차 제출

### 6/1-7 (궁극 목표)
13. Self-Consistency 적용
14. Adapter Merging 실험
15. (조건부) 9B QLoRA 또는 앙상블
16. 최종 제출 (6/5까지, 안전 마진 2일)

---

## 8. 위험 요소 및 대응

| 위험 | 확률 | 영향 | 대응 |
|------|------|------|------|
| 서버 SSH 접속 불안정 | 높음 | 모든 작업 지연 | sshpass 3-4회 재시도, ControlSocket 설정 |
| supervised 2,531건 중 실제 사용 가능 데이터 부족 | 중간 | 1차 목표 지연 | 210건 mutation으로 threshold만 개선하여 71-72 먼저 확보 |
| 긴 trajectory 합성 품질 낮음 | 중간 | 2차 목표 미달 | DPE (training-free)로 우회, 합성 대신 서버 기존 데이터 활용 |
| 4B 모델 상한에 근접 (80 이상 어려움) | 높음 | 궁극 목표 미달 | 76-78에서 멈추면 9B QLoRA 전환 검토 |
| 마감 전 제출 실패 (timeout 등) | 낮음 | 최종 점수 미반영 | 6/5까지 최종 제출, 이후 2일 안전 마진 |

---

## 부록: 사이클 6-7 gate 정책과의 관계

사이클 6-7에서 확립한 gate 정책의 핵심 원칙(데이터 검증 선행, LLM-only 보장, contamination 방지)은 유지한다. 변경된 것은 gate의 **분류**다:

- **유지**: source exact duplicate 0, unknown label 0, LLM-only 경로, prompt schema 일치, group leakage 0 → Must-have
- **격하**: ECE, MCC, Vendi Score, Length Coverage, template entropy, worst-group, contrast, synthetic-real AUC → Nice-to-have (추적용)
- **삭제**: "학습 금지" → 조건부 해제 (Must-have gate 통과 시 학습 허용)
- **삭제**: "제출 금지" → 조건부 해제 (Must-have gate + hidden-like acc 통과 시 제출 허용)

이 변경의 근거는 Agent 3-2의 "gate 완벽주의 < 빠른 실험 반복" 경고와, 17일 마감이라는 시간 제약이다. 모든 Nice-to-have gate를 통과한 뒤 학습하면 실험 반복이 3-4회로 제한되어 목표 달성 확률이 오히려 낮아진다.
