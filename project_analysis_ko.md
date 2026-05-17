<!-- Changed: update current scores and five-iteration verifier status. -->
<!-- Why: the project state changed after metamorphic, C_PIN, Set, EndSession, and Activate rule work. -->

# Team 6 SSD TCG/Opal Verifier 현재 분석

작성일: 2026-05-17

## 현재 결론

이 프로젝트는 순수 AI classifier 문제라기보다 **spec-grounded state verifier** 문제다. 입력 trajectory 전체가
주어지므로, 마지막 command-response pair가 현재 SSD/TCG/Opal 상태에서 명세상 가능한 응답인지 판단하면 된다.

현재 제출 solver는 LLM이나 Qwen을 런타임에 사용하지 않는다. `src/solver.py`는 JSON command/response를
정규화하고, session/auth/SP/key/data 상태를 추적한 뒤 마지막 record를 `pass` 또는 `fail`로 판정한다.

## 현재 구현 상태

- GitHub repo: `https://github.com/tongtongblueberry/team6-opal-verifier`
- Main entrypoint: `src/solver.py::Solver.predict(dataset)`
- Public train/dev score on `/dl2026/dataset`: `100.00` (`20/20`)
- Leaderboard best submission:
  - Job ID: `100`
  - Submission ID: `dcd43eb449a242e6a0cca623faae021f`
  - Job Name: `team6-coverage-67cd09d`
  - Score: `69.50`
- Latest local/server-validated commit: `67cd09d`
  - Public: `100.00`
  - Metamorphic/property diagnostics: `1453/1453`
  - Rule coverage with synthetic cases: all method-specific missing gaps are `none`.
  - Submitted on 2026-05-18 as job `100`.

## 55점이 낮게 나온 이유

초기 낮은 점수는 모델 크기나 fine-tuning 부족 때문이 아니었다. 원인은 parser/rule coverage 부족이었다.

- `HostSessionID`, `SPSessionID`를 session id로 인식하지 못했다.
- `HostChallenge`를 PIN 원문과 동일 비교하는 잘못된 가정이 있었다.
- `command: Read/Write` DATA_COMMAND를 TCG method session precondition과 섞어 처리했다.
- `Write` 입력의 `pattern` payload를 읽지 못했다.
- `Activate`에서 SP UID identity 검증이 부족했다.

이 문제들을 수정한 뒤 public train/dev는 100점이 됐다. guidebook 기반 `Get` field consistency,
DATA_COMMAND read/write, invalid Cellblock rule을 추가한 뒤 leaderboard는 68.00이 됐다. 이후 `Set(C_PIN)` column 3을 secret state로 추적해 StartSession authentication에 연결하면서 69.00이 됐고, method-specific coverage gap을 닫는 4회 해결 사이클 후 69.50까지 올랐다. 하지만 hidden scenario에 대한 rule/state semantics는 여전히 남아 있다.

## 5회 반복 결과

[Original Text/Data] → 2026-05-17에 다섯 번의 개선 루프를 수행했다. 서버 public 검증은 계속 `20/20`이었고, leaderboard는 일일 제출 한도 때문에 3회 신규 제출까지만 가능했다.

[Exact Interpretation] → rule coverage만으로는 문제를 충분히 찾지 못했다. 추가로 metamorphic/property mutation, producer-consumer state oracle, schema mutation, final method surface mutation, payload invariant mutation이 필요했다.

[Detailed Explanation/Example] → `EndSession` 회차에서 처음에는 metamorphic `855/948`로 실패했다. 이것은 `EndSession` rule 자체가 아니라 `{required: {}, optional: {}}` 형태의 structured empty result를 empty로 보지 못한 parser 결함이었다. 이 결함은 public 20개만 봐서는 드러나지 않았고, 중간 event를 final로 승격하는 synthetic mutation으로 드러났다.

| Loop | Commit | Added diagnosis | Fixed issue | Server diagnostic | Leaderboard |
|---:|---|---|---|---|---|
| 1 | `0c5e6d8` | Metamorphic/property invariant tests | GenKey success empty-result rule | public 20/20, metamorphic 174/174 | 68.00 |
| 2 | `bf6c40b` | Producer-consumer auth oracle | `Set(C_PIN.Values[3]) -> StartSession.HostChallenge` state link | public 20/20, metamorphic 474/474 | 69.00 |
| 3 | `bcfdc94` | Schema mutation | duplicate Set RowValues column and Set empty-result invariant | public 20/20, metamorphic 576/576 | 69.00 |
| 4 | `fc6b8df` | Final method surface mutation | EndSession branch and structured empty-result parser | public 20/20, metamorphic 948/948 | blocked: daily limit |
| 5 | `a814a87` | Payload invariant mutation | Activate empty-result invariant | public 20/20, metamorphic 970/970 | submitted via `fc0289e`: 69.00 |

## 4회 해결 사이클 결과

[Original Text/Data] → 69.00에서 정체된 뒤, 새로운 문제를 더 찾기보다 현재 coverage matrix에 남아 있던 gap을 해결하는 방향으로 네 번 반복했다. 최종 서버 검증은 public `20/20`, metamorphic `1453/1453`, synthetic-inclusive rule coverage의 method-specific missing gap `none`이다.

[Exact Interpretation] → 기존 문제 일부는 solver rule 부족이었고, 일부는 진단 기준이 부정확해서 생긴 false gap이었다. public-only coverage가 아니라 synthetic-inclusive coverage와 method별 applicable column을 써야 실제 gap과 false gap을 분리할 수 있었다.

[Detailed Explanation/Example] → `Properties`에 `state_effect`를 요구하거나 DATA_COMMAND `Read/Write`에 session precondition을 요구하면 잘못된 gap이 된다. 반대로 `StartSession` success response가 `SyncSession`인지, `HostSessionID`가 echo되는지, `SPSessionID`가 있는지 보는 것은 실제 producer-consumer rule이다.

| Cycle | Current issue | Applied method | Change | Result |
|---:|---|---|---|---|
| 1 | public-only coverage false gap | AFLNet/metamorphic seed mutation coverage | `--include-synthetic`, method-specific applicable columns | coverage gap 진단 정확화 |
| 2 | StartSession response shape too loose | RESTler producer-consumer dependency | `SyncSession`, HostSessionID echo, SPSessionID validation | synthetic expanded |
| 3 | Properties/Get object/precondition weak | model-based conformance | Properties target check, Get no-session tests | `Get`, `Properties` missing none |
| 4 | DATA_COMMAND Read/Write weak oracle | message-level protocol oracle | Read result, command identity, Write payload checks | leaderboard 69.50 |

## 현재 방향

다음 개선은 leaderboard hidden label을 역추론하는 것이 아니라, guidebook 기반 rule coverage를 늘리는 것이다.

권장 구조:

1. `StatefulOpalVerifier`의 trace mode로 mismatch 원인을 빠르게 확인한다.
2. 각 rule에 `rule_id`, `state_reads`, `state_writes`, `spec_ref_candidates`를 붙인다.
3. `/dl2026/skeleton/artifacts/documents`의 core/opal chunk를 lightweight index로 검색한다.
4. 서버에서만 Qwen/Gemma 등 LLM을 사용해 rule 후보와 spec reference 후보를 추출한다.
5. 제출 solver runtime은 deterministic rule engine으로 유지한다.

## 데이터 분리 원칙

- Public labeled data `/dl2026/dataset`은 train/dev 용도로만 사용한다.
- Leaderboard 결과는 점수와 commit 기록에만 사용한다.
- Hidden leaderboard/test sample label을 역추론해 rule에 직접 박지 않는다.
- 로컬과 GitHub에는 Qwen 같은 대형 모델을 받거나 커밋하지 않는다.
- 서버 비밀번호나 GitHub token은 파일, 커밋, 문서에 저장하지 않는다.
