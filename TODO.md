<!-- Added: durable handoff notes for future sessions. -->
<!-- Why: another Codex session should be able to continue without reconstructing the full conversation. -->

# TODO / Handoff

작성일: 2026-05-17

## 프로젝트 한 줄 요약

SSD TCG/Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 부합하는지 `pass`/`fail`로
판정하는 과제다. 현재 접근은 **deterministic state verifier + RAG/LLM-assisted rule coverage expansion**이다.

## 현재 저장소 상태

- Local path: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`
- GitHub: `https://github.com/tongtongblueberry/team6-opal-verifier`
- Main branch: `main`
- Server clone path used: `/workspace/team6/team6-opal-verifier`
- Clean submission path used: `/workspace/team6/submission-clean`
- Server non-secret access memo: `server_access.md`
- 비밀번호와 token은 저장소에 저장하지 않는다.

## 현재 성능

- Public train/dev: `100.00` on `/dl2026/dataset` (`20/20`)
- Leaderboard best:
  - Job ID: `94`
  - Submission ID: `d59207632cad4289b347a2bb84fd71f8`
  - Job Name: `team6-rule-coverage-fd43bd5`
  - Score: `68.00`
- Previous leaderboard:
  - Job ID: `93`
  - Submission ID: `6629d72c38474f839b3723e553b557f6`
  - Job Name: `team6-state-verifier-872f31d`
  - Score: `60.50`

## 중요한 해석

public 100점과 leaderboard 68.00의 차이는 public 20개 과적합/coverage gap을 의미한다. 다음 개선은 hidden
label을 추정해서 맞추는 방식이 아니라, guidebook과 trace를 사용해 rule coverage를 체계적으로 넓히는 방향이어야 한다.

## 주요 파일

- `src/solver.py`: 제출 solver. `Solver.predict(dataset)`가 공식 entrypoint다.
- `tools/intermediate_eval.py`: public train/dev 중간평가 도구. 기본은 짧은 stdout만 출력한다.
- `docs/methodology_survey_ko.md`: 관련 방법론 조사.
- `docs/data_protocol.md`: train/leaderboard/test 분리 원칙.
- `project_analysis_ko.md`: 현재 프로젝트 상태 요약.
- `tools/build_spec_index.py`: 서버 guidebook chunk index 생성.
- `tools/rule_coverage.py`: trace 기반 rule/state/spec coverage matrix 생성.

## 이미 해결한 문제

- 공식 evaluator가 `Solver` class를 요구한다는 점 반영.
- `HostSessionID`, `SPSessionID` session id parser 보강.
- `HostChallenge`를 PIN 원문과 비교하던 잘못된 rule 제거.
- DATA_COMMAND `Read/Write`와 TCG method precondition 분리.
- `Write`의 `pattern` payload parser 추가.
- `Activate` 대상 SP UID 검증 추가.
- `Set`이 쓴 object column 값을 `object_fields`로 추적하고, `Get` payload를 requested column/known field와 비교.
- DATA_COMMAND `Read` 결과에서 old pattern visibility를 정규화해 검사.
- invalid `Get` Cellblock range에 대해 expected `INVALID_PARAMETER` rule 추가.
- guidebook chunk index와 rule coverage matrix 도구 추가.
- trace mode 추가:
  - `rule_id`
  - `state_reads`
  - `state_writes`
  - `spec_ref_candidates`

## 빠른 검증 명령

로컬:

```bash
bash setup.sh
python3 -m compileall src tools
```

서버 public 중간평가:

```bash
python3 tools/intermediate_eval.py --dataset-root /dl2026/dataset
```

서버에서 spec 후보까지 포함한 중간평가:

```bash
python3 tools/intermediate_eval.py \
  --dataset-root /dl2026/dataset \
  --spec-root /dl2026/skeleton/artifacts/documents \
  --spec-hits 2
```

서버 guidebook index:

```bash
python3 tools/build_spec_index.py \
  --spec-root /dl2026/skeleton/artifacts/documents \
  --out artifacts/spec_index.jsonl
```

서버 rule coverage matrix:

```bash
python3 tools/rule_coverage.py \
  --dataset-root /dl2026/dataset \
  --spec-index artifacts/spec_index.jsonl \
  --out reports/rule_coverage_<commit>.json
```

제출:

```bash
git archive HEAD | tar -x -C /workspace/team6/submission-clean
submit -d /workspace/team6/submission-clean -n team6-state-verifier-<commit>
submit --list
```

## 다음 TODO

1. Guidebook chunk index를 고도화한다.
   - 기본 index 도구는 추가됨.
   - 다음은 section title mapping, table row/column extraction, method UID/object UID metadata 품질 개선이다.

2. Rule coverage matrix를 고도화한다.
   - 기본 matrix 도구는 추가됨.
   - 행: method/command (`Properties`, `StartSession`, `EndSession`, `Get`, `Set`, `Activate`, `GenKey`, `Read`, `Write`)
   - 열: precondition, state effect, response status, return payload invariant, object identity, session/auth requirement
   - 각 cell: implemented / traced / spec-backed / tested 여부.
   - 현재 public coverage 기준 missing:
     - `Activate`: status_invariant, payload_invariant
     - `Get`: precondition
     - `Properties`: object_identity, precondition, state_effect
     - `Read`: precondition, status_invariant
     - `Set`: precondition, payload_invariant
     - `StartSession`: precondition, status_invariant, payload_invariant

3. Trace-driven gap detector를 만든다.
   - 기본 low-confidence 출력은 추가됨.
   - 다음은 low-confidence reason을 더 세분화한다.
   - rule_id가 `DEFAULT_PASS`로 끝나는 케이스, spec hit가 없는 케이스, state read/write가 빈 케이스를 우선 조사한다.

4. Spec-grounded rule extraction을 서버에서만 실험한다.
   - Qwen/Gemma는 로컬에 다운로드하지 않는다.
   - 서버 shared cache 모델만 사용한다.
   - LLM output은 바로 solver에 넣지 않고, 사람이 검토 가능한 rule proposal로 저장한다.

5. Synthetic protocol mutation을 만든다.
   - public pass trajectory에서 마지막 status/payload/object/session을 바꿔 controlled negative를 만든다.
   - filename-based memorization이 아니라 rule-specific regression tests로 사용한다.

6. Regression tests를 추가한다.
   - public 20개 전체.
   - synthetic positives/negatives.
   - DATA_COMMAND after `GenKey`.
   - invalid SP UID `Activate`.
   - malformed `HostChallenge`.

7. 제출 로그를 남긴다.
   - 현재 best commit: `fd43bd5`
   - public score: `100.00`
   - leaderboard score: `68.00`
   - hidden sample-level label 추정은 금지.

## 다음 연구 질문

- 처음 보는 log trajectory에서 어떤 순서로 guidebook을 봐야 rule gap을 빨리 찾을 수 있는가?
- RESTler/StateAFL/ChatAFL/StatePre/MultiFuzz류는 coverage gap을 어떻게 줄였는가?
- 우리 문제에서 “coverage”를 code coverage가 아니라 rule/state/spec coverage로 어떻게 정의할 것인가?
