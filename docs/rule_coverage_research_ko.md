<!-- Added: research-backed plan for expanding guidebook-grounded rule coverage. -->
<!-- Why: leaderboard 60.50 after public 100 means hidden coverage gaps must be handled systematically, not by guessing labels. -->

# Rule Coverage 확장 조사와 실행 계획

작성일: 2026-05-17

## 현재 문제 정의

[Original Text/Data] → 현재 서버 public train/dev는 `100.00`이고 leaderboard 제출 `team6-state-verifier-872f31d`는 `60.50`이다.

[Exact Interpretation] → public 20개에 대한 parser/rule은 맞췄지만 hidden leaderboard scenario의 method/object/state/payload 조합을 충분히 덮지 못했다.

[Detailed Explanation/Example] → 이것은 “Qwen을 fine-tuning하면 해결”할 문제가 아니다. hidden label을 모르기 때문에 supervised fine-tuning 대상이 없다. 현재 필요한 것은 guidebook과 trace를 사용해 **rule coverage를 확장하는 것**이다.

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
7. score와 commit만 `reports/submission_log.md`에 기록

## 바로 다음 구현 TODO

우선순위는 다음 순서다.

1. `tools/build_spec_index.py` 구현
2. `tools/rule_coverage.py` 구현
3. synthetic mutation generator 구현
4. current solver trace를 coverage matrix에 연결
5. guidebook retrieval로 `Locking`, `MBRControl`, `Authority`, `SP`, `C_PIN`, `K_AES_256`별 rule proposal 생성
6. 사람이 검토한 rule만 solver에 추가
7. leaderboard 재제출

## 참고문헌

- Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API fuzzing*. 2019 IEEE/ACM 41st International Conference on Software Engineering. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf
- Maklad, Y., Wael, F., Hamdi, A., Elsersy, W., & Shaban, K. (2025). *MultiFuzz: A Dense Retrieval-based Multi-Agent System for Network Protocol Fuzzing*. arXiv. https://arxiv.org/abs/2508.14300
- Meng, R., Mirchev, M., Böhme, M., & Roychoudhury, A. (2024). *Large language model guided protocol fuzzing*. Network and Distributed System Security Symposium. https://www.ndss-symposium.org/ndss-paper/large-language-model-guided-protocol-fuzzing/
- Natella, R. (2022). *StateAFL: Greybox fuzzing for stateful network servers*. Empirical Software Engineering, 27, Article 191. https://link.springer.com/article/10.1007/s10664-022-10233-3
- Pham, V.-T., Böhme, M., & Roychoudhury, A. (2020). *AFLNET: A greybox fuzzer for network protocols*. 2020 IEEE 13th International Conference on Software Testing, Validation and Verification. https://thuanpv.github.io/publications/AFLNet_ICST20.pdf
- Zhang, Y., Zhu, K., Peng, J., Lu, Y., Chen, Q., & Li, Z. (2025). *StatePre: A large language model-based state-handling method for network protocol fuzzing*. Electronics, 14(10), 1931. https://www.mdpi.com/2079-9292/14/10/1931
