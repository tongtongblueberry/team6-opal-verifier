# Team 6 Opal Verifier -- 통합 진행 기록

작성일: 2026-05-19 | 과제: SNU Introduction to Deep Learning (M2177.0043) | 마감: 2026-06-08

---

## 0. 절대 원칙

**이 과제는 "딥러닝의 기초" (Introduction to Deep Learning) 수업 과제다.** 따라서:
- **LLM approach는 필수**. 순수 rule engine만으로는 과제 취지에 맞지 않는다.
- LLM 결과가 안 좋으면 -> **LLM을 잘못 쓰고 있다는 뜻**. LLM 폐기는 절대 선택지가 아니다.
- 500+ spec 문서를 전부 수동 규칙화하는 것은 **불가능**. LLM이 spec을 읽고 판단해야 한다.
- 핵심 질문은 항상: **"어떻게 LLM을 더 잘 쓸까?"**

## 1. 프로젝트 요약

SSD TCG/Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 부합하는지 `pass`/`fail`로 판정하는 문제다. 공개 라벨 20개, hidden test ~180개, GPU L40S 48GB, 평가 시 네트워크 불가, 3시간 제한.

**현재 아키텍처**: Rule Engine (71.50 base) + LoRA Override
- Rule engine (`StatefulOpalVerifier`): UNEXPECTED_ERROR_STATUS로 unexplained error를 aggressive하게 fail 판정
- LoRA 4B adapter: UNEXPECTED_ERROR_STATUS false positive를 rescue (pass로 override)

**현재 성능**: Leaderboard best **71.50** | LoRA 4B v2: fail precision 100%, fail recall 46.9%

---

## 2. 왜 이 접근인가 (동기 체인)

### 2-1. 왜 rule engine인가

이 문제는 순수 분류 AI 문제가 아니다. 전체 trajectory가 주어지므로, 마지막 command-response가 현재 SSD/TCG/Opal 상태에서 명세상 가능한 응답인지 판단하면 된다. 공개 라벨이 20개뿐이라 supervised fine-tuning은 과적합 위험이 크다.

관련 방법론 조사 결과, DeepLog/LogBERT/LogGPT류(정상 sequence 수천 개 필요)보다 RESTler/AFLNet/StateAFL/ChatAFL류(명세 기반 상태 추적)가 적합했다. -> 상세: `docs/methodology_survey_ko.md`

### 2-2. 왜 UNEXPECTED_ERROR_STATUS가 핵심인가

71.50 달성 후, rule engine 변경 시도에서 regression 원인을 분석한 결과:
- `UNEXPECTED_ERROR_STATUS` (모든 unexplained error -> fail): **71.50**
- `DEFAULT_PASS` (모든 unexplained error -> pass): **68.00** (3.5점 regression)

Hidden test에서 unexplained error의 대다수가 실제로 "fail"이라는 것을 의미한다. 이 aggressive 접근이 정답.

### 2-3. 왜 LoRA override인가

UNEXPECTED_ERROR_STATUS는 aggressive하므로 일부 false positive가 있다 (valid한 error를 fail로 잘못 판정). LoRA fine-tuned model이 이런 false positive를 감지하여 pass로 rescue하면 점수 향상 가능.

[EXTERNAL KNOWLEDGE] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR 2022. https://arxiv.org/abs/2106.09685

### 2-4. 왜 RAG는 폐기했나

RAG (BM25 + Qwen3.5-27B-FP8)는 Cycle 1-6에서 철저히 테스트한 결과:
- Zero-shot logit: fail recall 0% (심각한 pass-bias)
- Few-shot ICL logit: fail recall 0% (동일)
- Generation + thinking: 13분/case (3시간 초과)
- LLM의 zero-shot spec reasoning 능력이 부족하여 RAG 판정 불가

LoRA fine-tuning이 유일하게 유의미한 fail 감지를 달성 (fail recall 46.9%).

### 2-5. 왜 metamorphic testing / mutation testing인가

public 100%, metamorphic 100%, coverage low_confidence 0은 모두 필요하지만 충분하지 않다. 같은 패턴의 case를 5000개로 늘려도 weak MR이면 hidden fault를 못 잡는다 (Chen et al. 2019: 개별 MR이 mutant의 0.91~16.79%만 탐지). Mutation score가 test suite adequacy의 더 강한 기준이다.

---

## 3. 의사결정 타임라인

| 날짜 | 단계 | 핵심 결정 | 근거 |
|------|------|----------|------|
| 05-17 | 초기 구현 | deterministic state verifier 선택 | 공개 20개로 classifier 학습 불가, spec 기반 상태 추적이 적합 |
| 05-17 | parser 보강 | HostSessionID/SPSessionID parser, HostChallenge rule 수정 | public 55 -> 100 (parser 결함이 원인) |
| 05-17 | rule 확장 1 | spec index + Get field/data rules + DATA_COMMAND 정규화 | leaderboard 60.50 -> 68.00 |
| 05-17 | rule 확장 2 | C_PIN secret tracking (producer-consumer dependency) | leaderboard 68.00 -> 69.00 |
| 05-17 | 진단 도구 추가 | metamorphic/property tests, rule coverage matrix | case 수 174 -> 970, regression 안전망 |
| 05-18 | coverage gap 해결 | method-specific coverage, StartSession validation, DATA_COMMAND invariant | leaderboard 69.00 -> 69.50 |
| 05-18 | field semantics | C_PIN/Authority/Locking/MBRControl known field rules | low_confidence 4 -> 0, leaderboard 69.50 유지 |
| 05-18 | MC metric 도입 | Ba et al. 2025 Metamorphic Coverage 적용 | mc_cv 0.77 > coverage_cv 0.32 |
| 05-18 | Locking access rules | ReadLocked/WriteLocked DATA_COMMAND 접근 제어 | leaderboard 69.50 -> **71.50** |
| 05-18 | mutation testing | solver rule mutant 11개 생성, 전수 kill | mutation score 1.0 (11/11) |
| 05-18 | RAG+LLM hybrid | confidence-gated hybrid 구현 (BM25 + Qwen3.5-27B-FP8) | rule engine plateau 돌파 시도 |
| 05-18~19 | RAG Cycle 1-6 | zero-shot/few-shot/logit/generation 전수 테스트 | fail recall=0% (logit), 시간 초과 (generation) |
| 05-19 | Cycle 10 | embedding classifier + ridge regression 시도 | leaderboard 68.00 (regression) |
| 05-19 | Cycle 11 | LoRA fine-tuning 조사 (20편) + 0.8B v1 구현 | synthetic fail recall 0% (format 문제) |
| 05-19 | Cycle 12 | 논문 42편 조사 + LoRA 4B v2 (rich format) | **fail precision 100%, fail recall 46.9%** |
| 05-19 | Cycle 13 | regression 원인 확정 + spec mining (15 rules) | UNEXPECTED_ERROR_STATUS가 71.50 핵심 |
| 05-19 | Cycle 14 | 71.50 base 복원 + LoRA override 설계 | best-71.50 branch만 사용 |
| 05-19 | Cycle 15 | HP sweep 계획 + sweep script 구현 + 실행 | 26 runs, 각 ~56분 |

---

## 4. 실험 결과 요약

### 4-1. Leaderboard 제출 이력

| Commit / Job | 핵심 변경 | Public | Leaderboard |
|--------------|----------|--------|-------------|
| `872f31d` | 초기 state verifier | 20/20 | 60.50 |
| `fd43bd5` | spec index, Get field/data rules | 20/20 | 68.00 |
| `0c5e6d8` | GenKey empty result, metamorphic 도구 | 20/20 | 68.00 |
| `bf6c40b` | C_PIN secret tracking | 20/20 | 69.00 |
| `bcfdc94` | Set duplicate column, empty result | 20/20 | 69.00 |
| `fc0289e` | docs update (solver 동일) | 20/20 | 69.00 |
| `67cd09d` | method-specific coverage gaps | 20/20 | 69.50 |
| `c613397` | known field semantics, low_confidence 0 | 20/20 | 69.50 |
| `41b4df6` | MC metric 도입 | 20/20 | 69.50 |
| `2df1e71` | Locking ReadLocked/WriteLocked rules | 20/20 | **71.50** (best) |
| Job 185 | post-71.50 rule changes | 20/20 | 68.00 (regression) |
| Job 186 | embedding classifier | 20/20 | 68.00 (regression) |
| Job 187 | revert to best-71.50 | 20/20 | 71.50 |
| Job 188 | auth rule on 71.50 base | 20/20 | 71.50 |

상세 제출 로그: `docs/submission_log.md`

### 4-2. LLM 접근법 비교 (전 cycle 종합)

| 접근법 | Synthetic Fail Recall | Fail Precision | Accuracy | 시간/case | 결론 |
|--------|----------------------|----------------|----------|-----------|------|
| Zero-shot logit (27B) | 0% | N/A | 80.6% | 4.2s | pass-bias -- 폐기 |
| Few-shot ICL logit (27B, 20-shot) | 0% | N/A | 80.6% | 15.2s | logit mode에서 효과 없음 |
| Generation+thinking (27B) | - | - | 67% | 407s | 시간 초과 |
| Embedding+Ridge (9B) | - | - | 68.00 (LB) | - | distribution mismatch |
| LoRA 0.8B v1 (compressed format) | 0% | N/A | 80.6% | - | format 정보 손실 |
| **LoRA 4B v2 (rich format)** | **46.9%** | **100%** | **89.7%** | - | **유일한 성공** |

### 4-3. LoRA 4B v2 상세 결과 (Cycle 12)

| Dataset | Fail Recall | Fail Precision | Accuracy |
|---------|-------------|----------------|----------|
| Synthetic 252 | **46.9%** (23/49) | **100%** (23/23) | **89.7%** (226/252) |
| Public 20 | 80% (8/10) | 44.4% (8/18) | 50% (10/20) |

- Synthetic에서 false positive 0건 (pass를 fail로 뒤집지 않음)
- Public에서 false positive 과다 (pass 10건 중 8건을 fail로 오판) -- distribution mismatch
- **결론**: Override mode (rule engine fail -> LoRA pass만 허용)로 사용하면 안전

### 4-4. 진단 지표 현황

| 지표 | 현재 값 | 의미 |
|------|---------|------|
| Public accuracy | 100.00 (20/20) | sanity check 통과 |
| Metamorphic pass rate | 1891/1891 | regression 없음 |
| Rule coverage low_confidence | 0 | coverage grid 완전 |
| Mutation score | 1.0 (11/11 killed) | test suite가 rule mutant 전수 탐지 |
| LoRA fail precision | 100% (synthetic) | false positive 없음 |
| LoRA fail recall | 46.9% (synthetic) | 약 절반의 fail 감지 |

---

## 5. 해결한 문제 요약

**Parser 결함**:
- HostSessionID/SPSessionID 인식 실패
- HostChallenge를 PIN 원문과 동일 비교
- DATA_COMMAND Read/Write를 TCG method와 혼동
- Write pattern payload parser 누락
- structured empty result (`{required: {}, optional: {}}`) 오판

**Rule 부족**:
- Activate SP UID 검증 미흡
- Get payload의 requested column/known field 비교 부재
- Set duplicate RowValues column 검증 부재
- GenKey/Set/EndSession/Activate success empty-result invariant 부재
- StartSession response (SyncSession, HostSessionID echo, SPSessionID) 검증 부재
- C_PIN secret tracking -> StartSession authentication 연결 부재
- Locking/MBRControl/Authority.Enabled known field semantics 부재
- ReadLocked/WriteLocked DATA_COMMAND 접근 제어 부재

**LLM 접근법 탐색**:
- RAG (BM25 + 27B) zero-shot/few-shot: fail recall 0% -> 폐기
- Embedding classifier: leaderboard regression (68.00) -> 폐기
- LoRA 0.8B v1: format 정보 손실 -> 폐기
- LoRA 4B v2 (rich format): fail precision 100%, fail recall 46.9% -> **채택**

**Regression 원인**:
- UNEXPECTED_ERROR_STATUS -> DEFAULT_PASS 변경이 71.50 -> 68.00 regression 원인
- 71.50 base로 revert 확인 (Job 187)

**진단 도구**:
- rule coverage matrix -> `tools/rule_coverage.py`
- metamorphic/property tests -> `tools/metamorphic_eval.py`
- metamorphic coverage -> `tools/metamorphic_coverage.py`
- mutation testing -> `tools/mutation_eval.py`

---

## 6. 현재 아키텍처

```
Input trajectory
       |
[1] Rule Engine (StatefulOpalVerifier.verify_with_trace)
       |
  prediction + rule_id
       |
  rule_id == UNEXPECTED_ERROR_STATUS?
       NO  -> rule prediction 그대로 사용 (high confidence)
       YES -> LoRA 4B override
              |
[2] Qwen3.5-4B + LoRA adapter
       |
  LoRA prediction
       |
  LoRA says "pass" -> override to pass (rescue false positive)
  LoRA says "fail" -> keep fail (agree with rule engine)
```

**이전 아키텍처 (폐기됨)**:
- Confidence-gated hybrid (rule engine + RAG/LLM): DEFAULT_PASS case를 BM25 + 27B로 판정
- 실패 이유: LLM zero-shot spec reasoning이 fail recall 0% (logit), 시간 초과 (generation)

---

## 7. 주요 파일

| 파일 | 역할 |
|------|------|
| `src/solver.py` | 제출 entrypoint. Rule engine (71.50 base) + LoRA override |
| `src/lora_solver.py` | LoRA adapter loading and prediction |
| `src/rag.py` | BM25 retrieval + LLM judge (legacy, 미사용) |
| `tools/finetune_lora_v2.py` | LoRA training with rich format + label masking |
| `tools/sweep_lora.py` | HP sweep script |
| `tools/eval_lora.py` | LoRA evaluation |
| `tools/intermediate_eval.py` | public train/dev 중간평가 |
| `tools/mutation_eval.py` | mutation testing adequacy |
| `artifacts/lora_adapter_v2/` | 4B LoRA adapter (~32MB) |
| `docs/sweep_plan.md` | HP sweep 계획 및 architecture 상세 |

---

## 8. 데이터 분리 원칙

- Public labeled data는 train/dev 용도로만 사용
- Leaderboard 결과는 commit-level score만 기록 (sample-level label 역추론 금지)
- Private test 내용을 저장소에 커밋하지 않음
- 서버 비밀번호/token을 문서/코드에 저장하지 않음
- Training data: rule engine이 생성한 2163건 (metamorphic 1891 + synthetic 252 + public 20)
- Validation: synthetic test set 마지막 52건 (pass=3, fail=49)

상세: `docs/data_protocol.md`

---

## 9. 다음 TODO

### 즉시 (우선순위 순)

1. **HP sweep 완료 대기** -- 서버에서 실행 중 (26 runs, Phase 1)
2. **Best config로 50-epoch 본 학습** -- 매 5 epoch validation, best checkpoint 저장
3. **Leaderboard 제출** -- fail precision >= 90% 확인 후 제출

### 중기

4. **9B model 비교** -- 4B vs 9B (같은 config)
5. **Rule engine 확장** (71.50 base에서 안전한 규칙만)
   - Set NOT_AUTHORIZED (column-level ACL) -- 10-20 cases
   - Class authority INVALID_PARAMETER -- 5-15 cases
   - Authenticate rules -- 5-10 cases
6. **Training data 개선** -- hidden distribution에 더 가까운 synthetic data 생성

---

## 10. 상세 문서 참조 색인

| 문서 | 내용 | 참조 시점 |
|------|------|----------|
| `docs/submission_log.md` | commit-level 제출 이력 전체 | 제출 결과 확인 시 |
| `docs/sweep_plan.md` | LoRA HP sweep 계획, architecture, loss function 상세 | LoRA 관련 의사결정 시 |
| `docs/current_task.md` | 세션 이어받기용 최신 상태 | 세션 시작 시 |
| `docs/rag_cycle_log.md` | RAG 실험 Cycle 1-10 상세 (legacy) | RAG 관련 맥락 필요 시 |
| `docs/approach_ko.md` | 접근 방식 근거 | 아키텍처 설명 필요 시 |
| `docs/methodology_survey_ko.md` | 관련 방법론 조사 9편 | 방법론 선택 근거 필요 시 |
| `docs/rule_coverage_research_ko.md` | rule coverage 확장 계획 | coverage 진단 맥락 필요 시 |
| `docs/data_protocol.md` | 데이터 분리 원칙 | 데이터 사용 기준 확인 시 |

---

## 11. 핵심 교훈

1. **낮은 점수의 원인은 모델 크기가 아니라 parser/rule coverage였다.** 초기 55점 -> 100점은 parser 수정만으로 달성.
2. **Public 100점은 hidden 일반화를 보장하지 않는다.** 20개는 sanity check일 뿐.
3. **UNEXPECTED_ERROR_STATUS가 71.50의 핵심이다.** Aggressive하게 unexplained error를 fail로 판정하는 것이 hidden test에서 정확.
4. **Post-71.50 rule 변경은 regression을 유발한다.** UNEXPECTED_ERROR_STATUS를 DEFAULT_PASS로 바꾸면 3.5점 하락.
5. **LLM zero-shot spec reasoning은 fail을 감지하지 못한다.** Logit scoring fail recall 0%, generation mode는 시간 초과.
6. **LoRA fine-tuning이 유일한 성공적 LLM 접근법이다.** Rich format + label masking + 4B model로 fail recall 46.9% 달성.
7. **LoRA는 override mode로 사용해야 안전하다.** 직접 판정이 아니라, rule engine의 false positive rescue용.
8. **Leaderboard feedback은 commit-level score만 사용해야 한다.** Sample-level 역추론은 holdout 적응 위험.
9. **논문 조사는 필수다.** 42편(Cycle 12) + 20편(Cycle 11) 조사로 LoRA + rich format 조합 발견.
