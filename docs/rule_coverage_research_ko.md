<!-- Added: research-backed plan for expanding guidebook-grounded rule coverage. -->
<!-- Why: leaderboard 68.00 after public 100 means hidden coverage gaps must be handled systematically, not by guessing labels. -->

> **NOTE: This document reflects an earlier project phase (68.00 -> 71.50 journey).** The rule coverage
> expansion plan described here was executed through Cycle 10, culminating in 71.50 (Locking access rules).
> Post-71.50 rule changes caused regression (68.00); current approach is to keep 71.50 base unchanged
> and use LoRA 4B override instead. See `PROGRESS.md` for current state.

# Rule Coverage 확장 조사와 실행 계획

작성일: 2026-05-17

## 현재 문제 정의

[Original Text/Data] → 현재 서버 public train/dev는 `100.00`이고 leaderboard best는 `71.50`이다. 초기 제출은 `60.50`이었다.

[Exact Interpretation] → public 20개에 대한 parser/rule은 맞췄지만 hidden leaderboard scenario의 method/object/state/payload 조합을 충분히 덮지 못했다. 순수 rule engine은 71.50에서 plateau 상태다.

[Detailed Explanation/Example] → rule engine 확장은 계속 필요하지만, 수동 규칙 작성만으로는 500+ spec 문서의 모든 edge case를 커버하기 어렵다. 이에 따라 **confidence-gated hybrid** 아키텍처로 전환했다: rule engine이 판단하지 못하는 case (`DEFAULT_PASS`)를 RAG (BM25 spec retrieval) + LLM (Qwen3.5-27B-FP8)로 판정한다. 이것은 rule coverage를 대체하는 것이 아니라 보완하는 것이다.

## 관련 연구에서 배운 원칙

### 1. RESTler: 명세에서 dependency를 먼저 뽑고, response feedback으로 탐색 공간을 줄인다

[EXTERNAL KNOWLEDGE] Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API fuzzing*. 2019 IEEE/ACM 41st International Conference on Software Engineering. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf

[Original Text/Data] → RESTler는 Swagger specification을 분석해 producer-consumer dependency를 추론하고, 이전 실행 response feedback을 사용해 거절되는 sequence를 피한다.

[Exact Interpretation] → rule coverage 확장은 “모든 문서를 처음부터 읽기”가 아니라, `어떤 command가 어떤 state/resource를 만들고`, `어떤 command가 그 state/resource를 소비하는지`를 먼저 찾는 방식이어야 한다.

[Detailed Explanation/Example] → REST에서는 `POST -> id 생성 -> GET/PUT/DELETE가 id 소비`가 핵심 dependency다. 우리 문제에서는 `StartSession -> HostSessionID/SPSessionID 생성`, `Set C_PIN -> credential 변화`, `GenKey -> media key version 변화`, `Activate SP -> SP 상태 변화`가 같은 역할이다.

적용:

- guidebook을 method 단위로 읽지 말고 producer/consumer 단위로 색인한다.
- `state_writes`가 있는 rule부터 우선 확장한다.
- `state_reads`만 있고 producer가 없는 rule은 hidden에서 깨질 가능성이 높다.

### 2. AFLNet: recorded seed에서 시작하되 state coverage feedback을 본다

[EXTERNAL KNOWLEDGE] Pham, V.-T., Böhme, M., & Roychoudhury, A. (2020). *AFLNet: A greybox fuzzer for network protocols*. 2020 IEEE 13th International Conference on Software Testing, Validation and Verification. https://thuanpv.github.io/publications/AFLNet_ICST20.pdf

[Original Text/Data] → AFLNet은 recorded message exchange seed corpus에서 시작해 message sequence를 mutation하고, response code 기반 state feedback과 code coverage가 늘어난 case를 보존한다.

[Exact Interpretation] → public pass trajectory는 valid seed로 쓰되, coverage가 늘어나는 변형을 만들어 rule regression test로 삼아야 한다.

[Detailed Explanation/Example] → public `Read after GenKey` case에서 final output만 바꾸는 것이 아니라, `Write pattern`, `GenKey 위치`, `EndSession 위치`, `LBA 범위`, `Read result`를 각각 변형해 어떤 rule이 반응하는지 본다.

적용:

- public pass case를 seed로 synthetic mutation을 만든다.
- mutation 목적은 hidden label 추정이 아니라 rule별 positive/negative regression test 확장이다.
- coverage metric은 code coverage가 아니라 `method x state_read x status x payload invariant` coverage로 정의한다.

### 3. StateAFL: response code만 state로 쓰면 틀린다

[EXTERNAL KNOWLEDGE] Natella, R. (2022). *StateAFL: Greybox fuzzing for stateful network servers*. Empirical Software Engineering, 27, Article 191. https://link.springer.com/article/10.1007/s10664-022-10233-3

[Original Text/Data] → StateAFL은 response code가 실제 protocol state를 잘 대표하지 못한다고 보고, long-lived memory snapshot을 fuzzy hashing해 state identifier를 만든다.

[Exact Interpretation] → 우리 solver도 `SUCCESS`, `FAIL`, `NOT_AUTHORIZED`만 보면 안 된다. 상태 변수 자체를 추적해야 한다.

[Detailed Explanation/Example] → public에서도 `SUCCESS`인 final response가 pass인 경우와 fail인 경우가 있었다. hidden에서는 이런 차이가 더 많을 가능성이 높다.

적용:

- trace에서 `state_reads`와 `state_writes`가 비어 있는 rule은 coverage gap으로 본다.
- final status가 `SUCCESS`인 case일수록 object identity, payload invariant, previous state effect를 더 엄격히 봐야 한다.
- `DEFAULT_PASS`로 끝나는 판정은 hidden에서 위험한 low-confidence 판정이다.

### 4. ChatAFL: LLM은 classifier가 아니라 grammar/state 후보 생성기다

[EXTERNAL KNOWLEDGE] Meng, R., Mirchev, M., Böhme, M., & Roychoudhury, A. (2024). *Large language model guided protocol fuzzing*. Network and Distributed System Security Symposium. https://www.ndss-symposium.org/ndss-paper/large-language-model-guided-protocol-fuzzing/

[Original Text/Data] → ChatAFL은 LLM으로 protocol grammar를 구성하고, stateful sequence에서 다음 message를 예측하거나 mutation을 돕는다. NDSS summary는 ChatAFL이 AFLNet/NSFuzz보다 state transition, state, code coverage를 더 많이 덮었다고 보고한다.

[Exact Interpretation] → LLM은 final `pass/fail`을 직접 예측하는 모델이 아니라, guidebook에서 machine-readable rule 후보를 추출하는 도구로 써야 한다.

[Detailed Explanation/Example] → 우리 문제에서 LLM에게 “이 testcase는 pass인가?”를 묻는 대신, “`Activate` method의 precondition/effect/status response rule을 guidebook chunk에서 JSON schema로 추출하라”라고 시키는 것이 맞다.

적용:

- 서버 shared cache의 Qwen/Gemma만 사용한다.
- LLM 출력은 `rule_proposals/*.jsonl`로 저장하고 사람이 검토한다.
- 검토된 rule만 `src/solver.py`에 deterministic rule로 넣는다.

### 5. MultiFuzz: RAG로 hallucination과 spec assumption을 줄인다

[EXTERNAL KNOWLEDGE] Maklad, Y., Wael, F., Hamdi, A., Elsersy, W., & Shaban, K. (2025). *MultiFuzz: A Dense Retrieval-based Multi-Agent System for Network Protocol Fuzzing*. arXiv. https://arxiv.org/abs/2508.14300

[Original Text/Data] → MultiFuzz는 ChatAFL의 unreliable output, hallucination, LLM이 protocol specification을 이미 안다는 가정을 문제로 보고, RFC 문서를 chunk로 만들어 dense retrieval/RAG pipeline에 넣는다.

[Exact Interpretation] → 우리도 LLM에게 TCG/Opal을 “알고 있겠지”라고 맡기면 안 된다. 반드시 `/dl2026/skeleton/artifacts/documents` chunk를 retrieval한 뒤 그 근거 안에서만 rule을 추출해야 한다.

[Detailed Explanation/Example] → `GenKey` rule을 만들 때 전체 guidebook을 prompt에 넣지 않는다. 먼저 `GenKey`, `K_AES_256`, `media encryption key`, `locking range` 키워드로 chunk를 좁히고, 그 chunk만 LLM에게 준다.

적용:

- sparse keyword search로 method/object 후보 chunk를 1차 필터링한다.
- dense retrieval 또는 reranker는 2차로만 쓴다.
- 최종 rule에는 `source_chunk`, `quoted_terms`, `precondition`, `effect`, `response_invariant`를 붙인다.

### 6. StatePre: state annotation을 보완하는 방향이 맞다

[EXTERNAL KNOWLEDGE] Zhang, Y., Zhu, K., Peng, J., Lu, Y., Chen, Q., & Li, Z. (2025). *StatePre: A large language model-based state-handling method for network protocol fuzzing*. Electronics, 14(10), 1931. https://www.mdpi.com/2079-9292/14/10/1931

[Original Text/Data] → StatePre는 LLM의 자연어 specification 이해와 code 이해를 사용해 RFC-defined state knowledge와 program state annotation 사이의 gap을 줄이는 방식으로 설명된다.

[Exact Interpretation] → 우리 solver의 약점은 final classifier가 아니라 state annotation 부족이다. 즉 `ProtocolState`에 어떤 변수가 더 필요한지 찾아야 한다.

[Detailed Explanation/Example] → 현재 state는 `active_sessions`, `authenticated`, `activated_sps`, `known_secrets`, `written_payloads`, `generated_key_after_write` 정도다. hidden에서 `locking range`, `MBRDone`, `MBREnable`, `ReadLocked`, `WriteLocked`, `Authority Enabled`, `SP lifecycle` 같은 state가 나오면 현재 solver가 놓칠 수 있다.

적용:

- guidebook에서 table/object field를 state variable 후보로 추출한다.
- 각 state variable에 writer method와 reader method를 연결한다.
- `ProtocolState` 확장은 method별로 하지 말고 object/table field별로 한다.

## 처음 보는 log에서 guidebook을 보는 순서

처음 보는 trajectory나 hidden에서 점수가 낮게 나온 상황에서는 다음 순서가 가장 빠르다.

1. **Final record fingerprint**
   - final method/command
   - invoking UID/name
   - final status
   - return payload shape
   - `SUCCESS`인데 fail일 가능성, error인데 pass일 가능성을 분리한다.

2. **Trace coverage 확인**
   - final 판정 rule_id가 무엇인가?
   - `state_reads`가 비어 있는가?
   - `state_writes`가 과거 step에서 실제로 발생했는가?
   - `DEFAULT_PASS`, `UNEXPECTED_ERROR_STATUS`, `PARSE_FINAL_COMMAND`가 나오면 우선 조사한다.

3. **Object identity 확인**
   - method 이름이 같아도 invoking object가 다르면 rule이 달라진다.
   - `SP`, `C_PIN`, `Authority`, `Locking`, `MBRControl`, `K_AES_256`, `DATA_COMMAND`를 분리한다.

4. **Producer-consumer dependency 확인**
   - 이전 step이 만든 값이 final step에서 소비되는가?
   - session id, authority credential, SP activation, locking range field, media key state, LBA payload를 추적한다.

5. **Guidebook retrieval**
   - query 순서: `method name` → `invoking object/table` → `field/column` → `status code` → `lifecycle/state term`.
   - core와 opal을 모두 검색하되, object-specific rule은 opal 우선, generic method/status rule은 core 우선으로 본다.

6. **Rule proposal 작성**
   - `precondition`
   - `state_reads`
   - `state_writes`
   - `expected response status`
   - `payload invariant`
   - `source chunks`

7. **Synthetic mutation으로 검증**
   - 새 rule이 public 20개를 깨지 않는지 확인한다.
   - rule-specific positive/negative mutation을 만든다.
   - filename-based rule이 생기지 않았는지 확인한다.

## 현재 방향의 문제점 탐지 방법

### A. Rule coverage matrix

행:

- `Properties`
- `StartSession`
- `EndSession`
- `Get`
- `Set`
- `Activate`
- `GenKey`
- `Read`
- `Write`

열:

- parser coverage
- object identity coverage
- precondition coverage
- state effect coverage
- status invariant coverage
- payload invariant coverage
- spec-backed 여부
- synthetic test 여부

판정:

- `implemented`: 코드에 rule 있음
- `traced`: trace에 rule_id/state_reads/state_writes가 나옴
- `spec-backed`: source chunk가 연결됨
- `tested`: public 또는 synthetic regression이 있음

현재 가장 위험한 영역:

- `Get/Set`의 column-specific field semantics
- `Locking` object fields
- `MBRControl` fields
- `Authority` enable/disable semantics
- `SP` lifecycle
- `GenKey`가 영향 주는 data visibility 범위
- error status별 정확한 expected response

### B. Low-confidence detector

중간평가에서 정답/오답 여부와 무관하게 다음 case를 조사 대상으로 잡는다.

- final trace가 `DEFAULT_PASS`로 끝남
- `spec_ref_candidates`는 있는데 실제 `spec_hits`가 없음
- final method의 `state_reads`가 비어 있음
- final method의 invoking UID가 unknown
- payload가 있는데 parser가 payload를 비워 둠
- status가 `SUCCESS`인데 payload invariant rule이 없음
- status가 error인데 expected error reason이 없음

### C. Mutation-based regression

public pass trajectory에서 다음을 하나씩 바꾼다.

- final status만 바꾸기
- final invoking UID 바꾸기
- `HostChallenge` format 바꾸기
- session close 위치 바꾸기
- `Get` column range 바꾸기
- `Set` value 바꾸기
- `GenKey` 전후 `Read` result 바꾸기
- `Activate` 대상 SP 바꾸기

각 mutation은 기대 label을 rule reason으로 만든다. hidden label을 추정하지 않는다.

## 문제 해결 방법

### 1단계: Spec index 구축

파일:

- `tools/build_spec_index.py`
- output: `artifacts/spec_index.jsonl`

필드:

- `path`
- `section_title`
- `tokens`
- `method_names`
- `object_names`
- `uids`
- `field_names`
- `status_terms`

이 단계는 LLM 없이 가능하다.

### 2단계: Rule coverage matrix 생성

파일:

- `tools/rule_coverage.py`
- output: `reports/rule_coverage.json`

입력:

- `src/solver.py`의 `RULE_SPEC_QUERIES`
- public/synthetic trace
- spec index

출력:

- method별 missing cell
- spec-backed 없는 rule
- synthetic test 없는 rule

### 3단계: 서버 LLM rule proposal

서버에서만 실행한다. 로컬에는 모델을 받지 않는다.

입력 prompt는 retrieval된 chunk만 사용한다.

출력 JSONL schema:

```json
{
  "method": "Activate",
  "object": "SP",
  "preconditions": ["..."],
  "state_reads": ["..."],
  "state_writes": ["..."],
  "expected_status": {"valid": "SUCCESS", "invalid": "INVALID_PARAMETER"},
  "payload_invariants": ["..."],
  "source_chunks": ["opal/...txt"],
  "confidence": "low|medium|high"
}
```

### 4단계: Human-review gate

LLM proposal은 바로 solver에 넣지 않는다. 다음 기준을 통과해야 한다.

- source chunk가 실제로 존재한다.
- method/object/status가 public trace parser와 맞는다.
- rule이 filename이나 public label에 의존하지 않는다.
- synthetic positive/negative를 만들 수 있다.
- 기존 public 20개 100점을 깨지 않는다.

### 5단계: 제출 루프

1. local code 수정
2. public + synthetic regression
3. GitHub push
4. server clean archive
5. `submit -d ... -n team6-state-verifier-<commit>`
6. `submit --list`
7. score와 commit만 `docs/submission_log.md`에 기록

## 5회 반복에서 추가한 문제 확인 방법

### 1. Rule coverage만으로는 부족했다

[Original Text/Data] → `tools/rule_coverage.py`는 method별 missing cell과 low-confidence case를 찾았다. 하지만 `EndSession` 회차에서 rule coverage가 직접 가리키지 못한 structured empty-result parser 결함이 발견됐다.

[Exact Interpretation] → rule coverage는 "어떤 rule cell이 비었는가"를 찾는 데 유용하지만, parser가 정상 payload encoding을 잘못 정규화하는 문제, 중간 event가 final로 왔을 때의 final branch 누락, producer-consumer state link 누락은 별도 진단이 필요하다.

[Detailed Explanation/Example] → `EndSession` success output은 `{required: {}, optional: {}}` 형태일 수 있다. 단순 `values in ([], {}, "")` 검사만 쓰면 이 정상 empty result를 non-empty로 오판한다. 이 문제는 public final 20개에는 `EndSession` final이 없어서 드러나지 않았고, 중간 `EndSession`을 final로 승격한 synthetic mutation에서 드러났다.

### 2. 추가한 진단 방법

[EXTERNAL KNOWLEDGE] Segura, S., Fraser, G., Sánchez, A. B., & Ruiz-Cortés, A. (2016). *A survey on metamorphic testing*. IEEE Transactions on Software Engineering, 42(9), 805-824. https://doi.org/10.1109/TSE.2016.2532875

[Original Text/Data] → Metamorphic testing은 직접 oracle을 알기 어려운 입력에서, source test와 follow-up test 사이에 성립해야 하는 관계를 검사한다.

[Exact Interpretation] → hidden label을 알 수 없는 이 과제에서는 "이 trajectory의 label은 무엇인가"를 추측하지 않고, guidebook에서 확실한 관계만 synthetic positive/negative로 만든다.

[Detailed Explanation/Example] → `GenKey` success는 empty result여야 한다. 따라서 같은 prefix에서 final output을 empty success로 바꾸면 pass, non-empty success로 바꾸면 fail이어야 한다. 이것은 hidden label이 아니라 명세 기반 metamorphic relation이다.

[EXTERNAL KNOWLEDGE] Claessen, K., & Hughes, J. (2000). *QuickCheck: A lightweight tool for random testing of Haskell programs*. Proceedings of the Fifth ACM SIGPLAN International Conference on Functional Programming, 268-279. https://doi.org/10.1145/351240.351266

[Original Text/Data] → Property-based testing은 개별 example이 아니라 일반 property를 정의하고 생성된 입력으로 검증한다.

[Exact Interpretation] → `tools/metamorphic_eval.py`는 QuickCheck식 무작위 생성기는 아니지만 같은 원칙을 따른다. public seed에서 rule-specific follow-up case를 만들고 solver가 property를 지키는지 확인한다.

[Detailed Explanation/Example] → `Set`의 duplicate RowValues column은 `INVALID_PARAMETER`여야 한다. 따라서 duplicate column success는 fail, duplicate column invalid-parameter는 pass가 되어야 한다.

[EXTERNAL KNOWLEDGE] Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API fuzzing*. 2019 IEEE/ACM 41st International Conference on Software Engineering. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf

[Original Text/Data] → RESTler는 specification에서 producer-consumer dependency를 추론하고, response에서 생성된 값을 후속 request에 연결한다.

[Exact Interpretation] → 우리 문제의 핵심 producer-consumer link는 `StartSession -> active session`, `Set(C_PIN.Values[3]) -> known secret`, `Write -> written payload`, `GenKey -> key generation after write`다.

[Detailed Explanation/Example] → 2회차에서 `Set(C_PIN.Values[3])`를 `known_secrets`에 쓰고 `StartSession.HostChallenge`에서 읽도록 바꿨다. 이 변경으로 leaderboard best가 68.00에서 69.00으로 올랐다.

[EXTERNAL KNOWLEDGE] Pham, V.-T., Böhme, M., & Roychoudhury, A. (2020). *AFLNET: A greybox fuzzer for network protocols*. 2020 IEEE 13th International Conference on Software Testing, Validation and Verification. https://doi.org/10.1109/ICST46399.2020.00062

[Original Text/Data] → AFLNet은 recorded message exchange seed에서 시작해 message sequence를 mutation하고 response code/state feedback으로 유효한 탐색을 늘린다.

[Exact Interpretation] → public pass trajectory는 seed corpus이고, mutation 대상은 filename이 아니라 final method/status/payload/object/session field다.

[Detailed Explanation/Example] → `EndSession`, `Activate`처럼 public에서는 final이 아닌 중간 method를 final로 승격해 검사하면 final branch 누락을 찾을 수 있다.

## 5회 반복 결과 요약

| Loop | Commit | Diagnosis method | Fix | Result |
|---:|---|---|---|---|
| 1 | `0c5e6d8` | metamorphic/property invariant | GenKey empty result | leaderboard 68.00 |
| 2 | `bf6c40b` | producer-consumer state oracle | C_PIN secret tracking | leaderboard 69.00 |
| 3 | `bcfdc94` | schema mutation | Set duplicate column + empty result | leaderboard 69.00 |
| 4 | `fc6b8df` | final method surface mutation | EndSession + structured empty result | server diagnostics pass, submission blocked |
| 5 | `a814a87` | payload invariant mutation | Activate empty result | server diagnostics pass, submission blocked |

## 69점 정체 후 4회 해결 사이클

[Original Text/Data] → `fc0289e` 제출은 leaderboard `69.00`이었다. 이후 현재 coverage matrix에 남은 문제를 해결하는 방향으로 4회 반복했고, `67cd09d` 제출은 leaderboard `69.50`이었다.

[Exact Interpretation] → 새 문제를 계속 찾기보다 현재 gap을 더 정확히 분해하자 두 종류가 섞여 있었다. 하나는 실제 solver invariant 부족이고, 다른 하나는 method별로 적용 불가능한 coverage column까지 missing으로 세는 진단 오류였다.

[Detailed Explanation/Example] → `Properties`는 discovery 성격이라 state mutation을 요구하면 안 된다. 반대로 `StartSession`은 session id producer이므로 response가 `SyncSession` 형태이고 `HostSessionID`를 echo하며 `SPSessionID`를 만들어야 한다. 이 둘은 같은 "missing coverage"처럼 보였지만 해결 방법이 달랐다.

| Cycle | 문제 확인 | 방법론 | 적용 | 확인 결과 |
|---:|---|---|---|---|
| 1 | public-only rule coverage가 false gap을 만든다 | AFLNet seed mutation feedback, metamorphic/property testing | `tools/rule_coverage.py --include-synthetic`, method-specific applicable columns | false `Properties`/DATA_COMMAND gaps 제거 |
| 2 | `StartSession` success response validation이 느슨하다 | RESTler producer-consumer dependency | `SyncSession`, `HostSessionID` echo, `SPSessionID` presence check | public 유지, synthetic 증가 |
| 3 | `Properties` target과 `Get` no-session precondition 검증이 약하다 | model-based conformance/object identity | Properties Session Manager target check, Get no-session synthetic tests | `Get`, `Properties` missing none |
| 4 | DATA_COMMAND `Read/Write` final oracle이 약하다 | message-level protocol oracle | Read result presence, Read/Write response command identity, Write payload presence | public 20/20, metamorphic 1453/1453, coverage missing none, leaderboard 69.50 |

현재 남은 문제:

- method-specific coverage gap은 닫혔다.
- `c613397`에서 `C_PIN`, `Authority.Enabled`, `Locking`, `MBRControl` known field semantics를 추가해 synthetic-inclusive `low_confidence=0`까지 만들었다.
- 그런데 leaderboard는 `69.50`에서 오르지 않았다.
- 따라서 현재 문제는 "기존 coverage grid의 빈칸"이라기보다 "coverage grid 밖에 있는 rule universe" 또는 "진단 지표의 hidden gap 탐지력 부족"일 가능성이 높다.

## c613397 field-semantics 후속 결과

[Original Text/Data] → `c613397`은 public `20/20`, metamorphic `1821/1821`, synthetic-inclusive rule coverage `low_confidence=0`을 달성했고, job `102`로 제출한 leaderboard score는 `69.50`이었다.

[Exact Interpretation] → field semantics rule은 trace confidence와 regression coverage를 개선했지만 hidden leaderboard score를 개선하지는 못했다. 이 결과는 현재 public/metamorphic/coverage 지표가 saturated되어 더 이상 hidden gap을 충분히 발견하지 못할 수 있음을 보여준다.

[Detailed Explanation/Example] → `tc12`, `tc16`, `tc18`, `tc19`의 final error는 이제 generic `UNEXPECTED_ERROR_STATUS`가 아니라 `KNOWN_FIELD_EXPECTED_SUCCESS`나 `KNOWN_FIELD_INVALID_VALUE` 계열로 설명된다. 하지만 hidden set에는 다른 field/lifecycle/state semantics가 더 많거나, 지금 rule이 hidden discriminative boundary와 직접 맞지 않을 수 있다.

## 지표 해석과 다음 진단 기준

[EXTERNAL KNOWLEDGE] Roelofs, R., Shankar, V., Recht, B., Fridovich-Keil, S., Hardt, M., Miller, J., & Schmidt, L. (2019). *A meta-analysis of overfitting in machine learning*. Advances in Neural Information Processing Systems, 32. https://papers.nips.cc/paper/9117-a-meta-analysis

[Original Text/Data] → Roelofs et al.은 100개 이상 Kaggle competition에서 public leaderboard와 final/private ranking 차이를 분석했다.

[Exact Interpretation] → public/leaderboard feedback은 유용한 신호지만, 반복적으로 그 신호에 맞춰 solver를 수정하면 public holdout에 적응할 위험이 있다.

[Detailed Explanation/Example] → 우리 상황에서 public `100.00`은 20개 sanity check 통과일 뿐이다. public을 더 맞출 수 없고, leaderboard score 변화만 보고 hidden label을 역추론하면 데이터 분리 원칙을 깨게 된다.

[EXTERNAL KNOWLEDGE] Blum, A., & Hardt, M. (2015). *The ladder: A reliable leaderboard for machine learning competitions*. Proceedings of Machine Learning Research, 37, 1006-1014. https://proceedings.mlr.press/v37/blum15.html

[Original Text/Data] → Blum and Hardt는 반복 제출 과정에서 leaderboard feedback이 holdout estimate를 편향시킬 수 있음을 이론적으로 다뤘다.

[Exact Interpretation] → leaderboard는 commit-level score만 기록하고, sample-level label 역추론에는 쓰지 않아야 한다.

[Detailed Explanation/Example] → `c613397`이 `69.50`으로 유지됐다는 사실은 "field semantics가 hidden에서 틀렸다"가 아니다. 다만 "이 변경이 leaderboard aggregate score를 올릴 만큼 hidden sample을 바꾸지 않았다"까지만 해석해야 한다.

[EXTERNAL KNOWLEDGE] Chen, J., Wang, Y., Guo, Y., & Jiang, M. (2019). A metamorphic testing approach for event sequences. *PLOS ONE, 14*(2), e0212476. https://doi.org/10.1371/journal.pone.0212476

[Original Text/Data] → Chen et al.의 event-sequence metamorphic testing에서는 전체 MR 조합이 한 실험에서 mutant의 `39.23%`를 잡았고, 개별 MR은 `0.91%`부터 `16.79%`까지 크게 갈렸다.

[Exact Interpretation] → metamorphic pass rate 100은 충분한 fault-detection capability를 뜻하지 않는다. 중요한 것은 어떤 MR이 어떤 mutant/fault type을 잡는지다.

[Detailed Explanation/Example] → 우리 `1821/1821`은 "현재 생성한 1821개 case를 통과"라는 뜻이다. 같은 패턴의 case를 5000개로 늘려도 weak MR이면 hidden fault를 못 잡는다.

[EXTERNAL KNOWLEDGE] Saha, P., & Kanewala, U. (2019). *Fault detection effectiveness of metamorphic relations developed for testing supervised classifiers*. arXiv. https://doi.org/10.48550/arXiv.1904.07348

[Original Text/Data] → Saha and Kanewala는 supervised classifier용 기존 MRs가 reachable mutant `709`개 중 `14.8%`만 탐지했다고 보고했다.

[Exact Interpretation] → MR 수나 test case 수가 많아도 fault model과 맞지 않으면 탐지력이 낮을 수 있다.

[Detailed Explanation/Example] → 우리도 method/status만 반복 mutation하면 object lifecycle이나 locking semantics mutant를 못 잡을 수 있다.

[EXTERNAL KNOWLEDGE] Ba, J., Jiang, Y., & Rigger, M. (2025). *Metamorphic coverage*. arXiv. https://doi.org/10.48550/arXiv.2508.16307

[Original Text/Data] → Ba et al.은 일반 code coverage가 metamorphic testing의 실제 검증 정도를 잘 설명하지 못하고, pairwise/differential execution 관점의 metamorphic coverage가 더 유용할 수 있다고 본다.

[Exact Interpretation] → 우리 coverage도 "line coverage"가 아니라 "rule/state/spec coverage"이지만, 여전히 우리가 정의한 grid 안에서만 완전하다.

[Detailed Explanation/Example] → `low_confidence=0`은 좋은 신호지만, grid에 `SP lifecycle transition`이나 `Locking range state machine`이 없으면 그 영역의 hidden bug는 보이지 않는다.

다음 진단 기준:

- public 20/20은 제출 전 sanity check로만 본다.
- metamorphic 100%는 regression pass로만 본다.
- coverage low_confidence 0은 current grid confidence로만 본다.
- 다음 핵심 지표는 mutation score다.

Mutation-style adequacy TODO:

1. `tools/mutation_eval.py`를 추가한다.
2. solver rule을 삭제/약화한 mutant variant를 만든다.
3. public + synthetic suite가 mutant prediction을 원본과 다르게 만드는지 측정한다.
4. killed / survived / equivalent 후보를 기록한다.
5. survived mutant가 나오면 그 mutant가 가리키는 rule category를 guidebook에서 다시 찾는다.

## 바로 다음 구현 TODO

우선순위는 다음 순서다.

1. mutation-style adequacy 평가를 만든다.
2. survived mutant가 어떤 rule category를 가리키는지 분류한다.
3. guidebook retrieval로 grid 밖 rule universe를 찾는다.
4. `Locking`, `MBRControl`, `Authority`, `SP`, `C_PIN`, `K_AES_256`별 field/lifecycle semantics를 재점검한다.
5. synthetic mutation은 case 수가 아니라 MR diversity를 기준으로 확장한다.
6. 사람이 검토한 rule만 solver에 추가한다.
7. public/metamorphic/coverage/mutation score를 확인한 뒤 leaderboard에 제출한다.

## 참고문헌

- Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API fuzzing*. 2019 IEEE/ACM 41st International Conference on Software Engineering. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf
- Ba, J., Jiang, Y., & Rigger, M. (2025). *Metamorphic coverage*. arXiv. https://doi.org/10.48550/arXiv.2508.16307
- Blum, A., & Hardt, M. (2015). *The ladder: A reliable leaderboard for machine learning competitions*. Proceedings of Machine Learning Research, 37, 1006-1014. https://proceedings.mlr.press/v37/blum15.html
- Chen, J., Wang, Y., Guo, Y., & Jiang, M. (2019). A metamorphic testing approach for event sequences. *PLOS ONE, 14*(2), e0212476. https://doi.org/10.1371/journal.pone.0212476
- Claessen, K., & Hughes, J. (2000). *QuickCheck: A lightweight tool for random testing of Haskell programs*. Proceedings of the Fifth ACM SIGPLAN International Conference on Functional Programming, 268-279. https://doi.org/10.1145/351240.351266
- Maklad, Y., Wael, F., Hamdi, A., Elsersy, W., & Shaban, K. (2025). *MultiFuzz: A Dense Retrieval-based Multi-Agent System for Network Protocol Fuzzing*. arXiv. https://arxiv.org/abs/2508.14300
- Meng, R., Mirchev, M., Böhme, M., & Roychoudhury, A. (2024). *Large language model guided protocol fuzzing*. Network and Distributed System Security Symposium. https://www.ndss-symposium.org/ndss-paper/large-language-model-guided-protocol-fuzzing/
- Natella, R. (2022). *StateAFL: Greybox fuzzing for stateful network servers*. Empirical Software Engineering, 27, Article 191. https://link.springer.com/article/10.1007/s10664-022-10233-3
- Pham, V.-T., Böhme, M., & Roychoudhury, A. (2020). *AFLNET: A greybox fuzzer for network protocols*. 2020 IEEE 13th International Conference on Software Testing, Validation and Verification. https://thuanpv.github.io/publications/AFLNet_ICST20.pdf
- Roelofs, R., Shankar, V., Recht, B., Fridovich-Keil, S., Hardt, M., Miller, J., & Schmidt, L. (2019). *A meta-analysis of overfitting in machine learning*. Advances in Neural Information Processing Systems, 32. https://papers.nips.cc/paper/9117-a-meta-analysis
- Saha, P., & Kanewala, U. (2019). *Fault detection effectiveness of metamorphic relations developed for testing supervised classifiers*. arXiv. https://doi.org/10.48550/arXiv.1904.07348
- Segura, S., Fraser, G., Sánchez, A. B., & Ruiz-Cortés, A. (2016). *A survey on metamorphic testing*. IEEE Transactions on Software Engineering, 42(9), 805-824. https://doi.org/10.1109/TSE.2016.2532875
- Zhang, Y., Zhu, K., Peng, J., Lu, Y., Chen, Q., & Li, Z. (2025). *StatePre: A large language model-based state-handling method for network protocol fuzzing*. Electronics, 14(10), 1931. https://www.mdpi.com/2079-9292/14/10/1931
