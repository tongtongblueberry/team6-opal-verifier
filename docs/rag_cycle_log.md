# LLM Solver 개발 Cycle 기록

작성일: 2026-05-18 | 최종 갱신: 2026-05-19

> Cycle 1-6: RAG hybrid 실험 (폐기됨). Cycle 10: embedding classifier (폐기됨).
> Cycle 11-15: LoRA fine-tuning (현재 접근법).

## 프로젝트 컨텍스트

- 과제: SSD TCG/Opal trajectory pass/fail 분류 (SNU Introduction to Deep Learning M2177.0043)
- 마감: 2026-06-08
- 현재 best leaderboard: **71.50** (pure rule engine, commit `2df1e71`)
- 목표: leaderboard accuracy **≥ 85.00**

## 제약사항 (project.pdf p.8-10)

- GPU: NVIDIA L40S 48GB VRAM (practice server는 46068 MiB 표시)
- Evaluation phase: **네트워크 불가**, 3시간 제한
- Setup phase: 네트워크 가능, 20분 제한
- 사전 캐시 모델: `Qwen/Qwen3.5-{0.8B,2B,4B,9B}`, `Qwen/Qwen3.5-27B-FP8`, `google/gemma-4-*` 등
- 제출 크기: 12GB 이하
- Public labeled data: 20개 (practice server `/dl2026/dataset/`)
- Hidden test data: ~180개 (evaluation server에서만 실행)

## 서버 접속

- Host: `147.46.78.61`, Port: `2227`, User: `student`
- Password: **(저장소에 기록하지 않음)**
- Tool: `sshpass` (Homebrew 설치 완료)
- screen/tmux: **미설치** (sudo 없음). `nohup`으로 background job 실행
- 코드 경로: `/workspace/team6/team6-opal-verifier/`
- 배포: `sshpass -p '...' scp -P 2227 src/*.py student@147.46.78.61:/workspace/team6/team6-opal-verifier/src/`

## 서버 환경 (확인됨)

- PyTorch 2.11.0+cu130, transformers 5.8.1
- wandb 0.27.0 (설치됨, `pip install --break-system-packages wandb`)
- `kernels` 0.14.1 (FP8 지원, 설치됨)
- Qwen3.5-27B-FP8: 다운로드 완료 (HuggingFace cache), 모델 로딩 ~80초 (캐시 후)
- BM25 index: 1500 chunks (spec 문서 `/dl2026/skeleton/artifacts/documents/`)

## 논문 기반 아키텍처

### 선택 논문

Lewis, P., et al. (2020). *Retrieval-augmented generation for knowledge-intensive NLP tasks*. NeurIPS, 33, 9459-9474. https://arxiv.org/abs/2005.11401

### 핵심 수식: RAG-Sequence Marginalization

```
p(y|x) ≈ Σ_{z ∈ top-K} p_η(z|x) · p_θ(y|x, z)
```

Binary classification (pass/fail)에서는 RAG-Sequence = RAG-Token (single token output).

구현:
- p_η(z|x) = softmax(BM25_score) — retrieval weight
- p_θ(y|x, z) = softmax(logit_pass, logit_fail) — per-document forward pass
- 최종 결정: p_fail_marginal > fail_threshold → "fail", else "pass"

### Metric 정의

1. **Accuracy**: Acc = (1/N) Σ 1{ŷᵢ = yᵢ} — project.pdf p.8 공식 metric
2. **Retrieval R@K**: relevant chunk가 top-K에 포함되는 비율
3. **F1 (fail class)**: 2·P·R/(P+R)
4. **Total Latency**: T_init + Σ t_i < 10,800초

### 목표

| Metric | 현재 | 목표 | 근거 |
|--------|------|------|------|
| Leaderboard Accuracy | 71.50 | ≥ 85.00 | FEVER 2-way RAG 89.5%, 27B model |
| Retrieval R@8 | 미측정 | ≥ 0.85 | BM25 > DPR for FEVER (75.1 vs 72.5) |
| F1 (fail class) | 미측정 | ≥ 0.80 | accuracy 85% 대응 |
| Total Latency | ~80s init | < 3,600s | 3시간 한도의 33% |

## Cycle 1 기록

### 조사 (논문 10편)

| # | 논문 | 핵심 결과 | 시사점 |
|---|------|----------|--------|
| 1 | Lewis et al. (2020) RAG, NeurIPS | FEVER 2-way: 89.5%. RAG-Seq=Token for classification | logit marginalization 적합 |
| 2 | Shi et al. (2026) BM25→CRAG, arXiv | **Hybrid+Rerank R@5=0.816** vs BM25 0.644 | reranking이 최대 개선 (+17pp MRR) |
| 3 | Shi et al. (2026) 같은 논문 | Multi-query expansion: **-0.4pp R@5** | query expansion 비효율 (specific query) |
| 4 | Shi et al. (2026) 같은 논문 | Contextual chunking: +2.2~7.3pp R@5 | contextual prefix 유효 |
| 5 | Anthropic (2024) Contextual Retrieval | BM25 contextual: **-49% failure**, +rerank: **-67%** | contextual+rerank 조합 최적 |
| 6 | Asai et al. (2024) Self-RAG, ICLR | PubHealth: retrieval 없어도 2%만 하락 | fact verification은 retrieval에 덜 의존 |
| 7 | FEVER Workshop (2024) RAG-Fusion | Question generation으로 evidence recall 향상 | claim→question 변환 |
| 8 | FEVER Workshop (2024) Evidence-backed | RAG+few-shot: +22% over baseline | few-shot 효과 큼 |
| 9 | Reconstructing Context (2025), arXiv | Fixed-window ≈ semantic chunking | 복잡한 chunking 불필요 |
| 10 | Wei et al. (2022) CoT, NeurIPS | Chain-of-thought로 복잡한 판단 향상 | thinking mode 활용 |

### 적용 (2가지 변경)

#### 변경 1: Query expansion 제거
- 근거: Shi et al. (2026) — multi-query 는 specific query에서 -0.4pp
- 결과: `expand_queries()`, `rrf_fuse()`는 코드에 남아 있지만 `RAGSolver.predict()`에서 사용하지 않음
- 직접 BM25 query로 전환

#### 변경 2: Confidence gate 확장 (DEFAULT_PASS + KNOWN_FIELD_EXPECTED_SUCCESS)
- 근거: KNOWN_FIELD_EXPECTED_SUCCESS가 hidden case에서 false positive를 만들 수 있다는 가설
- **결과: PUBLIC REGRESSION 발생**

### 확인 (서버 결과)

**변경 전 (DEFAULT_PASS만 RAG):**
```
accuracy=100.00 (20/20)
precision(fail)=1.0000, recall(fail)=1.0000, f1(fail)=1.0000
tp=10 fp=0 fn=0 tn=10
eval_time=0.1s (RAG 호출 0건, 모든 case가 HIGH confidence)
```

**변경 후 (DEFAULT_PASS + KNOWN_FIELD_EXPECTED_SUCCESS → RAG):**
```
accuracy=80.00 (16/20)  ← 20%p REGRESSION
precision(fail)=1.0000, recall(fail)=0.6000, f1(fail)=0.7500
tp=6 fp=0 fn=4 tn=10
eval_time=108.8s (RAG 호출 4건, ~27초/case)

Mismatches:
  tc12.json: gold=fail pred=pass (RAG가 fail→pass로 뒤집음)
  tc16.json: gold=fail pred=pass
  tc18.json: gold=fail pred=pass
  tc19.json: gold=fail pred=pass
```

**RAG marginalization logits:**
```
p_pass=0.9858 p_fail=0.0142  (→ pass, threshold 0.6)
p_pass=0.9151 p_fail=0.0849  (→ pass)
p_pass=0.8427 p_fail=0.1573  (→ pass)
p_pass=0.6544 p_fail=0.3456  (→ pass)
```

### 분석

1. KNOWN_FIELD_EXPECTED_SUCCESS를 RAG로 보내면 안 됨. 이 rule은 "알려진 field 접근이 성공해야 하는데 에러가 남"을 감지하는 것으로, rule engine의 판단이 정확함.
2. RAG (27B-FP8)가 4건 모두 "pass"로 잘못 판정. p_fail이 최대 0.35 — threshold 0.6에 한참 못 미침.
3. 원인: LLM이 spec context만으로는 "이 field 접근이 반드시 성공해야 한다"고 판단하기 어려움. Rule engine이 object table schema를 알고 있어서 더 정확.

### 결론 및 즉시 조치

**KNOWN_FIELD_EXPECTED_SUCCESS를 _LOW_CONFIDENCE_RULES에서 제거해야 함.**
DEFAULT_PASS만 RAG로 보내는 원래 설계가 맞았음. Public 20개에서는 DEFAULT_PASS case가 0개이므로 RAG 효과를 public에서는 측정 불가. 진짜 효과는 leaderboard submit으로만 확인 가능.

## Cycle 2 기록

### 조사 (논문 10편, 주제: LLM 판단 품질 개선)

| # | 논문 | 핵심 | 시사점 |
|---|------|------|--------|
| 1 | Singal et al. (2024) RAG+Few-shot, FEVER | few-shot ICL로 +22% 향상 | **few-shot이 최대 개선** |
| 2 | "Label with Confidence" (Amazon, 2024) | logit binary: yes/no 분포 skew | calibration 필요 |
| 3 | NAACL 2024 Calibration Survey | temperature scaling 개선 | temperature scaling 적용 가능 |
| 4 | "Calibration-Tuning" (2024) | held-out 분포에서 temp scaling 저하 | 다른 분포 주의 |
| 5 | "Rubric Is All You Need" (ACM 2025) | structured rubric으로 judge 향상 | 이미 적용 (system prompt) |
| 6 | Autorubric (2025) | analytic rubric: 기준별 독립 채점 | criteria 분해 가능 |
| 7 | ToolGate (2026) | Hoare-style contract 검증 | rule engine이 이 역할 |
| 8 | Wei et al. (2022) CoT | step-by-step reasoning | thinking mode = CoT |
| 9 | Asai et al. (2024) Self-RAG | reflection tokens | retrieved chunk 관련성 평가 |
| 10 | Anthropic (2024) Contextual Retrieval | contextual prefix -49% failure | 이미 적용 |

### 확인: RAG 강제 실행 결과 (모든 20개 public case)

```
RAG accuracy on public (forced): 11/20 = 55.0%
- pass cases: 10/10 정확 (100%)
- fail cases: 1/10 정확 (10%) ← 심각한 pass 편향

Per-case details:
tc1  pass→pass OK  p_fail=0.0037
tc2  pass→pass OK  p_fail=0.2702
tc3  pass→pass OK  p_fail=0.0678
tc4  pass→pass OK  p_fail=0.0434
tc5  pass→pass OK  p_fail=0.0347
tc6  pass→pass OK  p_fail=0.1928
tc7  pass→pass OK  p_fail=0.0367
tc8  pass→pass OK  p_fail=0.0536
tc9  pass→pass OK  p_fail=0.0540
tc10 pass→pass OK  p_fail=0.0265
tc11 fail→pass WRONG p_fail=0.3568  (PROPERTIES_PAYLOAD)
tc12 fail→pass WRONG p_fail=0.0142  (KNOWN_FIELD_EXPECTED_SUCCESS)
tc13 fail→pass WRONG p_fail=0.3234  (STARTSESSION_FINAL)
tc14 fail→pass WRONG p_fail=0.0489  (STARTSESSION_FINAL)
tc15 fail→fail OK    p_fail=0.6488  (PRECONDITION_EXPECTED_ERROR) ← 유일한 정답
tc16 fail→pass WRONG p_fail=0.0849  (KNOWN_FIELD_EXPECTED_SUCCESS)
tc17 fail→pass WRONG p_fail=0.3542  (STARTSESSION_FINAL)
tc18 fail→pass WRONG p_fail=0.1573  (KNOWN_FIELD_EXPECTED_SUCCESS)
tc19 fail→pass WRONG p_fail=0.3456  (KNOWN_FIELD_EXPECTED_SUCCESS)
tc20 fail→pass WRONG p_fail=0.0481  (READ_PAYLOAD)

Latency: 4.2s/case (8 forward passes)
```

### 분석

1. **RAG는 "pass" 편향이 매우 심함.** fail case 10개 중 1개만 정확.
2. **Logit scoring의 한계**: 모델이 spec을 읽어도 fail에 대한 확신을 logit으로 표현 못함.
   p_fail 최대 0.65 (1건), 대부분 0.05~0.35.
3. **System prompt의 "lean towards pass" 지시가 편향을 강화**할 수 있음.
4. **Confidence gate가 정상 작동**: DEFAULT_PASS만 RAG로 보내므로, 이 pass 편향은
   hidden case에서 DEFAULT_PASS의 실제 답이 pass인 경우에는 올바르게 작동함.
   단, 실제 fail인 DEFAULT_PASS case는 놓칠 가능성 높음.

### 핵심 문제: Logit scoring vs Generation

현재 아키텍처는 **logit scoring** (thinking 없이 첫 토큰 logit만 봄).
이것은 빠르지만 (4.2s/case), 모델이 spec을 깊이 읽고 추론할 기회가 없음.

**Generation mode (thinking enabled)** 를 사용하면:
- 모델이 spec을 읽고 단계별 추론 후 답변
- 더 정확할 수 있지만 느림 (~60s/case)
- 3시간 제한 내 가능 (60s × 60cases = 3600s = 1시간)

→ **Cycle 3에서 generation mode를 DEFAULT_PASS case에 적용하고 비교해야 함.**

## Cycle 3 기록

### 적용: Generation mode (thinking enabled, 8192 max tokens)

### 확인 결과 (부분)

- tc1: gold=pass, rag=fail **WRONG**, 811.2초 (13.5분/case)
- 8192 tokens 생성은 case당 ~13분 → 20 cases = 4.4시간 (3시간 제한 초과)
- pass case를 fail로 오판 → "lean towards pass" 제거가 과도한 fail 편향 유발

### 분석

1. **Logit mode**: 55% accuracy, severe pass-bias (fail recall 10%)
2. **Generation mode**: case당 13분 (너무 느림), pass→fail 오판 발생
3. 근본 문제: **LLM의 zero-shot spec reasoning 능력이 부족**
   - 27B 모델이 TCG/Opal spec을 읽어도 pass/fail 판단을 정확하게 못함
   - Logit mode에서는 pass-bias, generation mode에서는 시간 초과 + 불안정

### 결론: 전략 전환 필요

RAG-LLM approach의 한계가 명확해짐:
- Public 20개에서 RAG 단독 accuracy 55% (logit) vs rule engine 100%
- LLM은 rule engine의 domain-specific knowledge를 대체할 수 없음
- RAG는 DEFAULT_PASS case에서만 사용되는데, hidden case의 DEFAULT_PASS 분포를 모름

**다음 전략: LLM을 판단에 사용하지 말고, rule engine 자체를 더 정밀하게 만드는 것이 더 효과적.**
RAG는 "rule 발견 도구"로 전환 — LLM이 spec을 읽고 새로운 rule을 제안.

## 현재 코드 상태 (Cycle 3 이후)

- `_LOW_CONFIDENCE_RULES = {"DEFAULT_PASS"}` — DEFAULT_PASS만 RAG로 보냄 (reverted)
- RAG predict()는 `judge_generate()` 사용 (generation + thinking mode)
- System prompt: "lean towards pass" 제거, "think step by step" 추가
- max_new_tokens: 8192
- `</think>` 태그 기반 answer extraction + thinking content fallback parsing
- Public 20개에서 DEFAULT_PASS = 0 → RAG 호출 없음 → public 100.00 유지
- **제출 대기 중** (일일 한도 초과)

## Cycle 4 이후 방향 (논문 기반)

### 조사한 논문

| # | 논문 | 핵심 | 시사점 |
|---|------|------|--------|
| 1 | RulePilot (2025) | LLM→executable security rule | rule discovery에 LLM 활용 |
| 2 | Executable Governance (2025) | policy→clause mining→SMT validation | 자동 rule extraction pipeline |
| 3 | Self-Refine (Madaan et al., 2023, NeurIPS) | iterative self-feedback로 +20% | 반복 개선 |
| 4 | VERIFYAI | NL→formal spec 변환 | spec→rule 자동화 가능성 |

### 전략 옵션

**Option A: RAG를 유지하되 leaderboard 결과를 보고 tuning**
- 현재 코드를 제출 → hidden DEFAULT_PASS case에서 RAG 효과 확인
- 점수 변화에 따라 threshold/prompt 조정
- 장점: 이미 구현됨, 추가 작업 적음
- 단점: LLM 판단 품질이 낮을 수 있음 (Cycle 2에서 55%)

**Option B: LLM을 rule discovery tool로 전환**
- LLM이 spec을 읽고 새 rule을 제안 → 사람이 검증 후 solver.py에 추가
- 장점: rule engine의 정밀도 활용, regression 위험 낮음
- 단점: 수작업 필요, 자동화 어려움

**Option C: Hybrid — 제출 후 결과 보고 결정**
- 먼저 현재 코드로 제출
- leaderboard 결과에 따라 A 또는 B 선택

→ **Option C 채택**

## Cycle 4 기록: Train/Test 분리 + 대규모 test set 생성

### 조사 (논문 20편)
- RAGAS, Know Your RAG, CRAFT, Self-Instruct 등 20편 조사 (자세한 목록은 상단)
- 핵심: 자체 생성 데이터는 bias 있음. Spec에서 직접 ground truth 도출이 필요.

### 적용: DEFAULT_PASS 코드 분석 + 대규모 test case 생성

Agent 분석으로 DEFAULT_PASS 트리거 조건 6가지 파악:
1. Unknown object type (cpin/authority/locking/mbrcontrol 외)
2. Non-MSID C_PIN without auth
3. Data command (media) failures
4. GenKey/Activate unmodeled params
5. Authority-specific credentials
6. Unrecognized methods

조합 생성으로 **206건의 DEFAULT_PASS test set** 확보:
- unknown_object: 156, non_msid_cpin: 27, data_command: 20, data_contradiction: 3
- Labels: pass=203, fail=3

### Train/Test 분리
- **TRAIN**: public 20개 (rule engine 개발)
- **TEST**: 206개 DEFAULT_PASS synthetic cases (LLM 평가 전용)
- test set은 /workspace/team6/large_dp_test_set.json에 저장

### Generation mode 부분 결과 (8건 중 6건 완료)
```
[OK]    pass→pass 535s | Get K_AES_256 unauth → NOT_AUTHORIZED
[OK]    pass→pass 238s | Get K_AES_256 auth → NOT_AUTHORIZED
[WRONG] pass→fail 597s | Get SP table → FAIL
[OK]    pass→pass 186s | Get C_PIN_SID unauth → NOT_AUTHORIZED
[OK]    pass→pass 340s | Get C_PIN_Admin1 unauth → NOT_AUTHORIZED
[WRONG] pass→fail 538s | Read after EndSession → FAIL
accuracy: 4/6 = 67% (진행 중)
```

### Generation mode 최종 결과 (8건 중 6건 완료, SSH 끊김으로 중단)

```
[OK]    pass→pass 535s | Get K_AES_256 unauth → NOT_AUTHORIZED
[OK]    pass→pass 238s | Get K_AES_256 auth → NOT_AUTHORIZED
[WRONG] pass→fail 597s | Get SP table → FAIL
[OK]    pass→pass 186s | Get C_PIN_SID unauth → NOT_AUTHORIZED
[OK]    pass→pass 340s | Get C_PIN_Admin1 unauth → NOT_AUTHORIZED
[WRONG] pass→fail 538s | Read after EndSession → FAIL

Accuracy: 4/6 = 66.7%
Avg time: 407s/case
Errors: 2 false negatives (pass→fail) — LLM incorrectly judges valid errors as violations
```

### 모드별 비교 요약

| Mode | Test data | Accuracy | fail recall | Time/case | 핵심 문제 |
|------|-----------|----------|-------------|-----------|----------|
| Logit marginalization | public 20 (forced) | 55% | 10% | 4.2s | pass-bias 심함 |
| Generation+thinking | DEFAULT_PASS 6건 | 67% | 0% (fail case 미도달) | 407s | 느림, fail case 부족 |
| Rule engine | public 20 | 100% | 100% | 0.01s | hidden에서 71.50 |

### Logit mode 252건 최종 결과

```
=== LOGIT MODE on 252 DEFAULT_PASS TEST SET ===
accuracy=80.6% (203/252)
precision(fail)=0.0000 recall(fail)=0.0000 f1(fail)=0.0000
tp=0 fp=0 fn=49 tn=203
time=965.7s (3.8s/case)

All 49 fail cases predicted as pass. Zero fail detection.
All 203 pass cases correctly predicted. 100% pass accuracy.
```

### 결론: LLM logit scoring은 fail을 전혀 감지하지 못함

Logit mode의 pass-bias는 치명적. FEVER 논문 기준 fail 비율 ~20%에서도 recall=0%.
이 결과는 Cycle 2 (public 55%)와 일관: LLM이 zero-shot으로 "이 에러가 잘못됐다"고 판단하기 매우 어려움.

### 근본 원인 분석

1. **LLM의 default behavior가 "에러는 valid"**: spec에서 에러가 필요한 상황이 많으므로,
   모호한 경우 pass로 기울어짐
2. **Logit scoring의 구조적 한계**: 첫 토큰 logit만으로는 복잡한 state reasoning 불가
3. **Zero-shot의 한계**: FEVER에서 RAG가 89.5%를 달성한 건 fine-tuned BART (400M)를 사용.
   우리는 zero-shot 27B — parameter가 크지만 task-specific 학습 없음

## Cycle 5 기록: Logit 252건 + 논문 선정

### 확인: Logit mode 252건 balanced test set

```
accuracy=80.6% (203/252)
precision(fail)=0.0000 recall(fail)=0.0000 f1(fail)=0.0000
tp=0 fp=0 fn=49 tn=203
time=965.7s (3.8s/case)
```

**LLM이 모든 49개 fail case를 pass로 예측.** fail recall = 0%.
Zero-shot logit scoring은 fail 감지가 불가능함을 확정.

### Label 비율 조사 (논문 기반)

| Dataset | fail 비율 | 근거 |
|---------|:---:|------|
| FEVER 2-way train | 27% | Thorne et al. (2018) |
| FEVER 2-way dev/test | 50% | balanced |
| Public 20 | 50% | 과제 데이터 |
| 우리 synthetic (초기) | 1.5% | 비정상 |
| 우리 synthetic (수정) | 19.4% | FEVER train 수준 |

### 논문 선정: Many-Shot In-Context Learning

Agrawal, R., et al. (2024). *Many-shot in-context learning*. NeurIPS 2024 (Spotlight).
https://arxiv.org/abs/2404.11018

**선정 이유**:
- Code Verification task (binary Yes/No)가 우리와 동일 구조
- Zero-shot → few-shot 전환으로 classification 정확도 대폭 개선
- Reinforced ICL: 모델 생성 rationale로 +11%p (BBH 72.1→83%)
- Pre-training bias 극복 가능 (우리의 pass-bias 문제)

**핵심 적용 방법**:
- Public 20개 case를 few-shot in-context examples로 prompt에 추가
- Zero-shot (현재, fail recall=0%) → 20-shot ICL
- 논문 기준 16-shot Code Verification에서 유의미한 개선 확인됨
- 262K context window로 20개 example 충분히 수용

## Cycle 6: Few-Shot ICL 적용 (진행 중)

### 조사 완료
- Many-Shot ICL (Agrawal et al., NeurIPS 2024) 완전 분석
- 9개 task, 13+ benchmark, 5+ metric
- 핵심: Code Verification에서 16-shot → significant improvement
- Reinforced ICL: 모델 생성 rationale이 human rationale과 동등

### 적용 중
- Agent가 src/rag.py에 few-shot ICL 구현 중
- Public 20개 case를 in-context examples로 추가
- Logit scoring + generation mode 양쪽에 적용

### 확인: Few-Shot ICL Logit Mode (252건)

```
=== FEW-SHOT ICL LOGIT MODE on 252 cases ===
accuracy=80.6% (203/252)
precision(fail)=0.0000 recall(fail)=0.0000 f1(fail)=0.0000
tp=0 fp=0 fn=49 tn=203
time=3823.7s (15.2s/case)
```

**20-shot ICL을 추가해도 logit scoring의 fail recall = 0%. Zero-shot과 동일.**
Few-shot examples는 logit 분포를 변경하지 못함.

### 분석: 왜 few-shot이 logit mode에서 효과 없나

1. **Logit scoring은 첫 토큰만 봄**: 모델이 20개 예시를 읽어도, 최종 logit 계산에서
   "pass" token이 항상 "fail" token보다 높은 확률을 받음
2. **Agrawal et al.의 Code Verification은 다른 방식 사용**:
   `IP(Yes) = exp(L_Yes) / (exp(L_Yes) + exp(L_No))` — 이것은 logit 방식이지만,
   논문에서는 128-256 shot에서 효과를 봄. 우리는 20-shot으로 부족할 수 있음
3. **또는 generation mode가 필요**: 모델이 reasoning을 거친 후 답변해야
   few-shot 패턴을 제대로 활용할 수 있음

### 결론: Logit mode 폐기, Generation mode + Few-shot으로 전환

| Mode | Zero-shot | 20-shot ICL | 비고 |
|------|-----------|-------------|------|
| Logit | fail recall=0% | fail recall=0% | **폐기** |
| Generation | 67% (6건) | **미측정** | **다음 cycle** |

### 다음 TODO
1. RAGSolver.predict()를 generation mode로 전환 (이미 judge_generate 코드 존재)
2. 252건 test set으로 generation + few-shot 평가
3. Leaderboard 제출
4. 결과에 따라 Reinforced ICL 적용 검토

## 파일 변경 이력

| Commit | 파일 | 변경 |
|--------|------|------|
| `3b1d5cd` | `src/rag.py` | 신규: BM25 + RAG-Sequence marginalization, Qwen3.5-27B-FP8 |
| `3b1d5cd` | `src/solver.py` | Solver class: confidence-gated hybrid |
| `3b1d5cd` | 문서 다수 | README, TODO, docs 전면 업데이트 |
| uncommitted | `src/rag.py` | query expansion 제거 (직접 BM25), contextual chunking, state summary |
| uncommitted | `src/solver.py` | `_LOW_CONFIDENCE_RULES` 추가 (KNOWN_FIELD_EXPECTED_SUCCESS → **제거 필요**) |
| uncommitted | `tools/rag_eval.py` | 신규: Solver 기반 평가 스크립트 |

## 서버 설치 패키지

```bash
pip install --break-system-packages wandb   # 0.27.0
pip install --break-system-packages -U kernels  # 0.14.1 (FP8 support)
```

## 빠른 재현 명령

```bash
# 로컬 → 서버 배포
sshpass -p '$PASSWORD' scp -P 2227 -o StrictHostKeyChecking=no \
  src/solver.py src/lora_solver.py \
  student@147.46.78.61:/workspace/team6/team6-opal-verifier/src/ 2>&1

# 서버에서 평가
sshpass -p '$PASSWORD' ssh student@147.46.78.61 -p 2227 \
  -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
  "cd /workspace/team6/team6-opal-verifier && python3 tools/eval_lora.py --dataset-root /dl2026/dataset 2>&1"

# 서버에서 제출
sshpass -p '$PASSWORD' ssh student@147.46.78.61 -p 2227 \
  -o StrictHostKeyChecking=no \
  "cd /workspace/team6 && \
   cp -r team6-opal-verifier/src team6-opal-verifier/setup.sh team6-opal-verifier/pyproject.toml team6-opal-verifier/uv.lock submission-\$(cd team6-opal-verifier && git rev-parse --short HEAD)/ && \
   submit -d submission-\$(cd team6-opal-verifier && git rev-parse --short HEAD) -n team6-lora 2>&1"
```

**Note:** `$PASSWORD`는 별도 관리. 저장소에 기록하지 않음.

## Cycle 10 결과: Embedding Classifier — LEADERBOARD REGRESSION

### Leaderboard: 68.00 (이전 best 71.50에서 -3.50)

9B embedding (2163 training cases, CV acc 0.569) + ridge regression.
Embedding classifier가 DEFAULT_PASS case에서 rule engine 기본값(pass)보다 나쁜 성능.

### 원인 분석
1. Synthetic training data가 hidden test distribution과 다름
2. Metamorphic cases는 rule engine이 만든 것 → rule engine이 이미 맞추는 패턴만 학습
3. DEFAULT_PASS의 hidden 분포에서 대부분이 실제 "pass"일 가능성 → classifier가 "fail"로 바꾸면 regression

### Solver reverted to RAG mode (commit cb70d7b)

### 전체 Leaderboard 이력

| Commit | Method | Score |
|--------|--------|:-----:|
| 872f31d | rule engine v1 | 60.50 |
| fd43bd5 | +spec index, Get rules | 68.00 |
| bf6c40b | +C_PIN secret tracking | 69.00 |
| 67cd09d | +coverage gaps | 69.50 |
| 2df1e71 | +Locking access rules | **71.50** (best) |
| **submission-emb** | **+embedding classifier** | **68.00** (regression) |

## Cycle 11 기록: LoRA Fine-Tuning 조사

### 조사 (논문 20편)
- LoRA (Hu et al., ICLR 2022), QLoRA (Dettmers et al., NeurIPS 2023), AdaLoRA, LongLoRA 등
- 핵심: LoRA는 full fine-tuning의 97% 성능을 1-10% 파라미터로 달성
- BCO (ACL 2025), Calibration-Aware RL (2026) 등 binary classification 특화 방법 조사

### 적용: LoRA 0.8B v1
- Model: Qwen3.5-0.8B, compressed format (method/status만 포함)
- Training: 2163건 synthetic data, 10 epochs

### 확인
| Dataset | Fail Recall | Fail Precision | Accuracy |
|---------|-------------|----------------|----------|
| Public 20 | **80%** | 20% | 50% |
| Synthetic 252 | **0%** | N/A | 80.6% |

### 분석
- Public에서 fail 감지 가능 (80%) but pass->fail 오판 과다
- Synthetic DEFAULT_PASS에서 여전히 무력 (distribution mismatch)
- **Format 정보 손실이 핵심 원인**: method/status만 보존, payload/session context 미포함

## Cycle 12 기록: LoRA 4B v2 (Rich Format)

### 조사 (논문 42편)
- LLM fine-tuning, calibration, rule extraction, neuro-symbolic 등
- 핵심: BCO (ACL25), Calibration-Aware RL (2026), RBCTest (ASE24), TOGLL (ASE24)
- Rich input format이 classification 성능에 결정적이라는 다수 논문 확인

### 적용: LoRA 4B v2
- Model: Qwen/Qwen3.5-4B
- Format: rich format (method, status, payload, session context, state summary 포함)
- Training: 2163건, max_length=1024, label masking
- Adapter: artifacts/lora_adapter_v2/ (~32MB)

### 확인
| Dataset | Fail Recall | Fail Precision | Accuracy |
|---------|-------------|----------------|----------|
| Synthetic 252 | **46.9%** (23/49) | **100%** (23/23) | **89.7%** (226/252) |
| Public 20 | 80% (8/10) | 44.4% (8/18) | 50% (10/20) |

### 분석
- **유일한 성공적 LLM 접근**: false positive 0건 (synthetic)
- Public에서 distribution mismatch로 false positive 과다 (reference only)
- Override mode (rule engine fail -> LoRA pass만 허용)로 사용하면 안전

## Cycle 13 기록: Regression 원인 확정 + Spec Mining

### Regression 원인 확정
- Post-71.50 rule engine 변경이 68.00 regression의 원인
- UNEXPECTED_ERROR_STATUS -> DEFAULT_PASS 변경이 핵심
- 새 규칙 (class authority, read-only) 자체는 무관
- team6-revert-71 제출 -> 71.50 재확인

### Spec Mining: 15개 미구현 규칙 발견
1. Set NOT_AUTHORIZED (column-level ACL) -- 10-20 cases
2. Class authority INVALID_PARAMETER -- 5-15 cases
3. Get silent column omit -- 5-15 cases
4. Authenticate rules -- 5-10 cases
5. SP_BUSY session exclusivity -- 5-10 cases
... (총 15개, 모두 71.50 base에서 안전하게 추가 가능한지 검증 필요)

### 결론
- **71.50 base만 사용** -- post-71.50 변경 금지
- 규칙 추가보다 LoRA override가 더 안전한 접근

## Cycle 14 기록: 71.50 Base 복원 + LoRA Override 설계

### 목표
71.50 base에 안전한 개선 추가

### 진행
- 71.50 코드 복원 완료 (main branch)
- Authenticate method 추가 검토 -> UNEXPECTED_ERROR_STATUS가 valid error를 잡아서 위험
- LoRA 4B v2 학습 완료, override integration 설계

### LoRA Override Architecture
```
Rule engine (71.50 base)
  -> UNEXPECTED_ERROR_STATUS fail?
     -> LoRA 4B: pass? -> override to pass (rescue false positive)
     -> LoRA 4B: fail? -> keep fail
```

### 결론
- 직접적인 rule 추가는 regression 위험이 높음
- LoRA override가 유일하게 safe한 개선 경로

## Cycle 15 기록: HP Sweep 계획 + Script 구현

### 목표
LoRA 4B v2의 fail recall 향상 (46.9% -> 60%+)

### 조사
- Scheduler: cosine annealing (Loshchilov & Hutter, 2017)이 linear보다 우수
- Optimizer: NAdam (Dozat, 2016)이 Adam/AdamW보다 LoRA에 적합
- Rank/alpha: rank 16-64, alpha = 2*rank가 일반적 권장

### Sweep 설정
- **고정**: Scheduler=cosine, Optimizer=NAdam
- **탐색**: LR (1e-5 ~ 5e-4), rank (8, 16, 32, 64), alpha (16 ~ 128),
  dropout (0.0 ~ 0.2), max_length (512, 768, 1024), batch_size (2, 4, 8)
- 26 runs, 각 ~56분
- Script: `tools/sweep_lora.py`

### 현재 상태
- Sweep script 준비 완료
- 서버 SSH rate limiting으로 접속 제한 중
- 오늘 leaderboard 제출 한도 초과

## 다음 방향

1. **HP sweep 실행 및 완료** -- 서버 접속 안정화 후
2. **Best config로 50-epoch 본 학습** -- 매 5 epoch validation, best checkpoint
3. **Leaderboard 제출** -- fail precision >= 90% 확인 후
4. **9B model 비교** -- 4B vs 9B
5. **Rule engine 확장** -- 71.50 base에서 안전한 규칙만 (spec mining 15개 중 선별)
