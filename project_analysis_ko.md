<!-- Changed: replace the outdated initial analysis with the current project state. -->
<!-- Why: the previous version said the repo only had a PDF and recommended model-first work, which no longer matches the actual solution path. -->

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
  - Job ID: `94`
  - Submission ID: `d59207632cad4289b347a2bb84fd71f8`
  - Job Name: `team6-rule-coverage-fd43bd5`
  - Score: `68.00`

## 55점이 낮게 나온 이유

초기 낮은 점수는 모델 크기나 fine-tuning 부족 때문이 아니었다. 원인은 parser/rule coverage 부족이었다.

- `HostSessionID`, `SPSessionID`를 session id로 인식하지 못했다.
- `HostChallenge`를 PIN 원문과 동일 비교하는 잘못된 가정이 있었다.
- `command: Read/Write` DATA_COMMAND를 TCG method session precondition과 섞어 처리했다.
- `Write` 입력의 `pattern` payload를 읽지 못했다.
- `Activate`에서 SP UID identity 검증이 부족했다.

이 문제들을 수정한 뒤 public train/dev는 100점이 됐다. guidebook 기반 `Get` field consistency,
DATA_COMMAND read/write, invalid Cellblock rule을 추가한 뒤 leaderboard는 68.00이 됐다. 하지만 hidden scenario에
대한 rule coverage가 여전히 부족하다.

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
