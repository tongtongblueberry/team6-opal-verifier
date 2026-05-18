# Team 6 Opal Verifier -- 통합 진행 기록

작성일: 2026-05-18 | 과제: SNU Introduction to Deep Learning (M2177.0043) | 마감: 2026-06-08

---

## 0. 절대 원칙

**이 과제는 "딥러닝의 기초" (Introduction to Deep Learning) 수업 과제다.** 따라서:
- **LLM approach는 필수**. 순수 rule engine만으로는 과제 취지에 맞지 않는다.
- LLM 결과가 안 좋으면 → **LLM을 잘못 쓰고 있다는 뜻**. LLM 폐기는 절대 선택지가 아니다.
- 500+ spec 문서를 전부 수동 규칙화하는 것은 **불가능**. LLM이 spec을 읽고 판단해야 한다.
- 핵심 질문은 항상: **"어떻게 LLM을 더 잘 쓸까?"**

## 1. 프로젝트 요약

SSD TCG/Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 부합하는지 `pass`/`fail`로 판정하는 문제다. 공개 라벨 20개, hidden test ~180개, GPU L40S 48GB, 평가 시 네트워크 불가, 3시간 제한.

**현재 아키텍처**: Confidence-Gated Hybrid Solver
- 확신이 높은 case (~70%): deterministic rule engine (`StatefulOpalVerifier`)
- 확신이 낮은 case (`DEFAULT_PASS`, ~30%): BM25 spec retrieval + Qwen3.5-27B-FP8 LLM 판정

**현재 성능**: Leaderboard best **71.50** | Public 20/20 | Metamorphic 1891/1891 | Mutation score 1.0

---

## 2. 왜 이 접근인가 (동기 체인)

### 2-1. 왜 rule engine인가

이 문제는 순수 분류 AI 문제가 아니다. 전체 trajectory가 주어지므로, 마지막 command-response가 현재 SSD/TCG/Opal 상태에서 명세상 가능한 응답인지 판단하면 된다. 공개 라벨이 20개뿐이라 supervised fine-tuning은 과적합 위험이 크다.

관련 방법론 조사 결과, DeepLog/LogBERT/LogGPT류(정상 sequence 수천 개 필요)보다 RESTler/AFLNet/StateAFL/ChatAFL류(명세 기반 상태 추적)가 적합했다. -> 상세: `docs/methodology_survey_ko.md`

### 2-2. 왜 hybrid로 전환했나

순수 rule engine은 71.50에서 plateau했다. 500+ spec 문서의 모든 edge case를 수동 규칙으로 커버하기 어렵다. 확실한 case는 rule engine(빠르고 정확), 불확실한 case만 LLM(spec 원문 참조)으로 처리하면 regression 최소화 + unmodeled case 처리가 가능하다.

Lewis et al. (2020)의 RAG-Sequence marginalization을 적용: `p(y|x) = sum_z p_eta(z|x) * p_theta(y|x,z)`. -> 상세: `docs/approach_ko.md`

### 2-3. 왜 metamorphic testing / mutation testing인가

public 100%, metamorphic 100%, coverage low_confidence 0은 모두 필요하지만 충분하지 않다. 같은 패턴의 case를 5000개로 늘려도 weak MR이면 hidden fault를 못 잡는다 (Chen et al. 2019: 개별 MR이 mutant의 0.91~16.79%만 탐지). Mutation score가 test suite adequacy의 더 강한 기준이다.

Ba et al. (2025)의 Metamorphic Coverage를 solver trace feature에 이식하여, source/follow-up pair가 실제로 서로 다른 rule/state path를 검증하는지 측정했다. -> 상세: `docs/metamorphic_coverage_application_ko.md`, `docs/rule_coverage_research_ko.md`

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
| 05-18 | MC metric 도입 | Ba et al. 2025 Metamorphic Coverage 적용 | mc_cv 0.77 > coverage_cv 0.32, MC가 relation 차이를 더 잘 분리 |
| 05-18 | Locking access rules | ReadLocked/WriteLocked DATA_COMMAND 접근 제어 | leaderboard 69.50 -> 71.50 |
| 05-18 | mutation testing | solver rule mutant 11개 생성, 전수 kill | mutation score 1.0 (11/11) |
| 05-18 | RAG+LLM hybrid | confidence-gated hybrid 구현 (BM25 + Qwen3.5-27B-FP8) | rule engine plateau 돌파 시도 |

---

## 4. 실험 결과 요약

### 4-1. Leaderboard 제출 이력

| Commit | 핵심 변경 | Public | Metamorphic | Leaderboard |
|--------|----------|--------|-------------|-------------|
| `872f31d` | 초기 state verifier | 20/20 | - | 60.50 |
| `fd43bd5` | spec index, Get field/data rules | 20/20 | - | 68.00 |
| `0c5e6d8` | GenKey empty result, metamorphic 도구 | 20/20 | 174/174 | 68.00 |
| `bf6c40b` | C_PIN secret tracking | 20/20 | 474/474 | 69.00 |
| `bcfdc94` | Set duplicate column, empty result | 20/20 | 576/576 | 69.00 |
| `fc0289e` | docs update (solver 동일) | 20/20 | 970/970 | 69.00 |
| `67cd09d` | method-specific coverage gaps | 20/20 | 1453/1453 | 69.50 |
| `c613397` | known field semantics, low_confidence 0 | 20/20 | 1821/1821 | 69.50 |
| `41b4df6` | MC metric 도입 | 20/20 | 1821/1821 | 69.50 |
| `2df1e71` | Locking ReadLocked/WriteLocked rules | 20/20 | 1839/1839 | **71.50** |

상세 제출 로그: `docs/submission_log.md`

### 4-2. RAG+LLM 실험 결과 (Cycle 1-3)

| 모드 | 전체 accuracy | fail recall | case당 시간 | 결론 |
|------|-------------|-------------|------------|------|
| Logit scoring (DEFAULT_PASS only) | 100% (RAG 호출 0건) | - | 0.1s | public에서 DEFAULT_PASS 없음 |
| Logit scoring (KNOWN_FIELD 포함) | 80% (16/20) | 60% | 27s | **regression** -- KNOWN_FIELD을 RAG로 보내면 안 됨 |
| Logit scoring (전체 강제) | 55% (11/20) | 10% | 4.2s | 심각한 pass 편향 |
| Generation mode (thinking 8192) | - | - | 811s/case | 시간 초과 (13분/case) |

**결론**: LLM의 zero-shot spec reasoning 능력이 부족. DEFAULT_PASS만 RAG로 보내는 설계 유지. 진짜 효과는 hidden case에서만 확인 가능.

상세 RAG 실험 기록: `docs/rag_cycle_log.md`

### 4-3. 진단 지표 현황

| 지표 | 현재 값 | 의미 |
|------|---------|------|
| Public accuracy | 100.00 (20/20) | sanity check 통과. hidden 일반화 보장 아님 |
| Metamorphic pass rate | 1891/1891 | 현재 MR 집합 regression 없음 |
| Rule coverage low_confidence | 0 | 정의된 coverage grid 안에서 generic trace 없음 |
| Mutation score | 1.0 (11/11 killed) | 현재 test suite가 rule mutant를 전수 탐지 |
| MC mean pair size | 14.81 | source/follow-up pair당 평균 differential feature 수 |
| MC zero pairs | 86 | differential trace 없는 pair (relation 재설계 필요) |
| MC CV | 0.77 vs coverage CV 0.32 | MC가 relation 차이를 더 잘 분리 |

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

**진단 도구 부재**:
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
  prediction + trace (rule_id 포함)
       |
  HIGH confidence (rule_id != DEFAULT_PASS)?
       YES -> rule prediction 그대로 사용
       NO  -> RAG-Sequence marginalization
              |
[2] Query 추출 (method, object, status, trace context)
       |
[3] BM25 Retrieval -> top-K spec chunks + BM25 scores
       |
[4] Per-document LLM scoring (Qwen3.5-27B-FP8)
       |
[5] Marginalization: p("pass"|x) = sum w_i * p("pass"|x, z_i)
       |
  "pass" if p > 0.5, else "fail"
```

---

## 7. 주요 파일

| 파일 | 역할 |
|------|------|
| `src/solver.py` | 제출 entrypoint. Confidence-gated hybrid |
| `src/rag.py` | BM25 retrieval + LLM judge |
| `tools/intermediate_eval.py` | public train/dev 중간평가 |
| `tools/build_spec_index.py` | guidebook chunk index 생성 |
| `tools/rule_coverage.py` | trace 기반 rule/state/spec coverage |
| `tools/metamorphic_eval.py` | property-based synthetic tests |
| `tools/metamorphic_coverage.py` | Ba et al. 2025 MC metric |
| `tools/mutation_eval.py` | mutation testing adequacy |
| `tools/download_model.py` | 서버 LLM 사전 다운로드 |

---

## 8. 데이터 분리 원칙

- Public labeled data는 train/dev 용도로만 사용
- Leaderboard 결과는 commit-level score만 기록 (sample-level label 역추론 금지)
- Private test 내용을 저장소에 커밋하지 않음
- 서버 비밀번호/token을 문서/코드에 저장하지 않음
- LLM은 spec 원문을 읽고 판단 (공개 라벨 주입 없음)

상세: `docs/data_protocol.md`

---

## 9. 다음 TODO

### 즉시 (우선순위 순)

1. **서버에서 RAG hybrid solver 검증** -- DEFAULT_PASS case에서 LLM 판정 로그 확인
2. **Hybrid solver leaderboard 제출** -- 1차 목표 >= 78.00, 2차 목표 >= 85.00
3. **결과에 따라 prompt/retrieval 튜닝** -- top_k (5->3 or 8), chunk_size (800->500 or 1200), thinking mode 활성화

### 중기

4. **Rule engine 자체 확장**
   - Authenticate method (in-session auth)
   - Byte table operations
   - Session type (Read-Only vs Read-Write) 구분
   - Guidebook rule universe 확장: Revert/RevertSP, Random, Next, ACL/ACE

5. **Mutation testing 강화** -- survived mutant가 가리키는 rule category를 guidebook에서 재탐색

6. **MC-guided relation 재설계** -- zero-MC pair 86개의 relation을 differential coverage가 생기도록 개선

---

## 10. 상세 문서 참조 색인

| 문서 | 내용 | 참조 시점 |
|------|------|----------|
| `docs/submission_log.md` | commit-level 제출 이력 전체 | 제출 결과 확인 시 |
| `docs/rag_cycle_log.md` | RAG 실험 Cycle 1-4 상세 (서버 환경, 논문 20편, 결과) | RAG 관련 의사결정 맥락 필요 시 |
| `docs/approach_ko.md` | 접근 방식 근거 (왜 hybrid인가) | 아키텍처 설명 필요 시 |
| `docs/methodology_survey_ko.md` | 관련 방법론 조사 9편 (DeepLog~StatePre) | 방법론 선택 근거 필요 시 |
| `docs/rule_coverage_research_ko.md` | rule coverage 확장 계획 + 5회 반복 결과 + 지표 해석 | coverage 진단 맥락 필요 시 |
| `docs/metamorphic_coverage_application_ko.md` | Ba et al. 2025 MC metric 적용 계획 | MC metric 이해 필요 시 |
| `docs/data_protocol.md` | 데이터 분리 원칙 | 데이터 사용 기준 확인 시 |

---

## 11. 핵심 교훈

1. **낮은 점수의 원인은 모델 크기가 아니라 parser/rule coverage였다.** 초기 55점 -> 100점은 parser 수정만으로 달성.
2. **Public 100점은 hidden 일반화를 보장하지 않는다.** 20개는 sanity check일 뿐.
3. **진단 지표 포화 != 문제 해결.** Coverage grid 안의 완전성과 grid 밖의 rule universe 부재는 다른 문제다.
4. **LLM의 zero-shot spec reasoning은 제한적이다.** fail recall 10% (logit mode). Rule engine의 domain-specific knowledge를 대체할 수 없다.
5. **Leaderboard feedback은 commit-level score만 사용해야 한다.** Sample-level 역추론은 holdout 적응 위험을 만든다.
6. **Metamorphic test 수보다 MR diversity가 중요하다.** 같은 패턴 반복은 hidden fault를 잡지 못한다.
