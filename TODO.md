<!-- Changed: refresh durable handoff notes after five verifier improvement loops. -->
<!-- Why: another Codex session should know the latest commits, scores, blocked submissions, and next work. -->

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
- Clean submission paths used: `/workspace/team6/submission-<commit>`
- Server non-secret access memo: `server_access.md`
- 비밀번호와 token은 저장소에 저장하지 않는다.

## 현재 성능

- Public train/dev: `100.00` on `/dl2026/dataset` (`20/20`)
- Leaderboard best:
  - Job ID: `100`
  - Submission ID: `dcd43eb449a242e6a0cca623faae021f`
  - Job Name: `team6-coverage-67cd09d`
  - Score: `69.50`
- Latest validated commit:
  - Commit: `67cd09d`
  - Public score: `100.00`
  - Metamorphic diagnostics: `1453/1453`
  - Rule coverage with synthetic cases: all method-specific missing gaps are `none`.
  - Leaderboard: submitted on 2026-05-18 as job `100`.
- Previous leaderboard:
  - `99` / `team6-latest-fc0289e` / `1dd86a84d1d34235acd8438bcf4967d5` / `69.00`
  - `97` / `team6-set-schema-bcfdc94` / `a366f0990fc14ab2a5a9f44e82805a4f` / `69.00`
  - `96` / `team6-cpin-auth-bf6c40b` / `f6e155417ebc4d3f8cf5b2af035363e5` / `69.00`
  - `95` / `team6-metamorphic-0c5e6d8` / `134f35f7e0dc4a0a89666a7590d8cb53` / `68.00`
  - `94` / `team6-rule-coverage-fd43bd5` / `d59207632cad4289b347a2bb84fd71f8` / `68.00`
  - `93` / `team6-state-verifier-872f31d` / `6629d72c38474f839b3723e553b557f6` / `60.50`

## 중요한 해석

public 100점과 leaderboard 69.50의 차이는 public 20개 과적합/coverage gap을 의미한다. 다음 개선은 hidden
label을 추정해서 맞추는 방식이 아니라, guidebook과 trace를 사용해 rule coverage를 체계적으로 넓히는 방향이어야 한다.

## 주요 파일

- `src/solver.py`: 제출 solver. `Solver.predict(dataset)`가 공식 entrypoint다.
- `tools/intermediate_eval.py`: public train/dev 중간평가 도구. 기본은 짧은 stdout만 출력한다.
- `docs/methodology_survey_ko.md`: 관련 방법론 조사.
- `docs/data_protocol.md`: train/leaderboard/test 분리 원칙.
- `project_analysis_ko.md`: 현재 프로젝트 상태 요약.
- `tools/build_spec_index.py`: 서버 guidebook chunk index 생성.
- `tools/rule_coverage.py`: trace 기반 rule/state/spec coverage matrix 생성.
- `tools/metamorphic_eval.py`: public seed에서 생성한 synthetic positive/negative property tests.
- `docs/submission_log.md`: commit-level leaderboard 기록. hidden sample label 추정은 기록하지 않는다.

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
- `tools/metamorphic_eval.py` 추가. 현재 서버 기준 `970/970`.
- `GenKey`, `Set`, `EndSession`, `Activate` 성공 response의 empty-result invariant 추가.
- `Set(C_PIN.Values[3])`를 `known_secrets`로 추적하고 `StartSession.HostChallenge`와 연결.
- `Set` duplicate RowValues column을 `INVALID_PARAMETER`로 검증.
- structured empty result인 `{"required": {}, "optional": {}}`를 정상 empty payload로 정규화.
- synthetic-inclusive rule coverage를 추가하고 method-specific applicable columns로 false gap을 줄임.
- `StartSession` success response가 `SyncSession`, `HostSessionID` echo, `SPSessionID`를 만족하는지 검증.
- `Properties` target을 Session Manager로 제한하고 `Get` no-session precondition synthetic tests 추가.
- DATA_COMMAND `Read/Write` response command identity와 payload presence invariant 추가.

## 5회 반복 요약

| Loop | Commit | Diagnosis added | Fix | Server result | Leaderboard |
|---:|---|---|---|---|---|
| 1 | `0c5e6d8` | Metamorphic/property invariant tests | GenKey empty-result check | public 20/20, metamorphic 174/174 | 68.00 |
| 2 | `bf6c40b` | producer-consumer auth oracle | C_PIN column 3 secret tracking | public 20/20, metamorphic 474/474 | 69.00 |
| 3 | `bcfdc94` | schema mutation | Set duplicate-column and empty-result checks | public 20/20, metamorphic 576/576 | 69.00 |
| 4 | `fc6b8df` | final-method surface mutation | EndSession + structured empty result parser | public 20/20, metamorphic 948/948 | blocked: daily limit |
| 5 | `a814a87` | payload invariant mutation | Activate empty-result check | public 20/20, metamorphic 970/970 | submitted via `fc0289e`: 69.00 |

## 4회 해결 사이클 요약

| Cycle | Current issue | Methodology used | Applied change | Verification | Leaderboard |
|---:|---|---|---|---|---|
| 1 | public-only coverage가 이미 검증된 rule도 missing으로 표시 | AFLNet식 seed mutation coverage, metamorphic/property testing | `rule_coverage.py --include-synthetic`, method-specific applicable columns | method-specific missing gaps can be tracked without false `Properties`/DATA_COMMAND gaps | included in `67cd09d` |
| 2 | `StartSession` success response shape가 느슨함 | RESTler식 producer-consumer dependency | `SyncSession`, `HostSessionID` echo, `SPSessionID` validation | public 20/20, synthetic expanded | included in `67cd09d` |
| 3 | `Properties` object identity와 `Get` precondition coverage 부족 | model-based protocol conformance/object identity checks | Properties Session Manager target check, Get no-session synthetic tests | coverage: `Get: none`, `Properties: none` | included in `67cd09d` |
| 4 | DATA_COMMAND final `Read/Write`가 payload/status oracle이 약함 | message-level protocol oracle | Read result presence, Read/Write response command identity, Write payload presence | public 20/20, metamorphic 1453/1453, all method-specific coverage gaps none | 69.50 |

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

서버 metamorphic/property diagnostics:

```bash
python3 tools/metamorphic_eval.py \
  --dataset-root /dl2026/dataset \
  --jsonl-out reports/metamorphic_<commit>.jsonl
```

제출:

```bash
mkdir -p /workspace/team6/submission-<commit>
git archive -o /workspace/team6/submission-<commit>.tar HEAD
tar -xf /workspace/team6/submission-<commit>.tar -C /workspace/team6/submission-<commit>
submit -d /workspace/team6/submission-<commit> -n team6-state-verifier-<commit>
submit --list
```

주의: 2026-05-17에는 leaderboard가 `Maximum number of submissions for today exceeded`를 반환했다.

## 다음 TODO

1. `67cd09d` 이후 남은 low-confidence 4개를 조사한다.
   - 최신 HEAD는 2026-05-18 job `100`으로 제출했고 score는 `69.50`이다.
   - method-specific coverage gap은 닫혔지만 low-confidence trace는 4개 남아 있다.

2. Guidebook chunk index를 고도화한다.
   - 기본 index 도구는 추가됨.
   - 다음은 section title mapping, table row/column extraction, method UID/object UID metadata 품질 개선이다.

3. Rule coverage matrix를 고도화한다.
   - 기본 matrix 도구는 추가됨.
   - 행: method/command (`Properties`, `StartSession`, `EndSession`, `Get`, `Set`, `Activate`, `GenKey`, `Read`, `Write`)
   - 열: precondition, state effect, response status, return payload invariant, object identity, session/auth requirement
   - 각 cell: implemented / traced / spec-backed / tested 여부.
   - 현재 public coverage 기준 missing:
     - `Activate`: status_invariant
     - `Get`: precondition
     - `Properties`: object_identity, precondition, state_effect
     - `Read`: precondition, status_invariant
     - `Set`: precondition
     - `StartSession`: precondition, status_invariant, payload_invariant

4. Trace-driven gap detector를 만든다.
   - 기본 low-confidence 출력은 추가됨.
   - 다음은 low-confidence reason을 더 세분화한다.
   - rule_id가 `DEFAULT_PASS`로 끝나는 케이스, spec hit가 없는 케이스, state read/write가 빈 케이스를 우선 조사한다.

5. Spec-grounded rule extraction을 서버에서만 실험한다.
   - Qwen/Gemma는 로컬에 다운로드하지 않는다.
   - 서버 shared cache 모델만 사용한다.
   - LLM output은 바로 solver에 넣지 않고, 사람이 검토 가능한 rule proposal로 저장한다.

6. Synthetic protocol mutation을 확장한다.
   - 기본 mutation 도구는 추가됨.
   - 다음은 `Properties`, `Get`, `Read/Write`, `Locking`, `MBRControl`, `Authority.Enabled` field 중심으로 확장한다.
   - filename-based memorization이 아니라 rule-specific regression tests로 사용한다.

7. Regression tests를 추가한다.
   - public 20개 전체.
   - synthetic positives/negatives.
   - DATA_COMMAND after `GenKey`.
   - invalid SP UID `Activate`.
   - malformed `HostChallenge`.
   - C_PIN known/wrong secret StartSession.
   - duplicate Set RowValues column.
   - EndSession as final method.

8. 제출 로그를 남긴다.
   - 현재 best submitted commit: `67cd09d`
   - 현재 latest validated commit: `67cd09d`
   - public score: `100.00`
   - leaderboard score: `69.50`
   - hidden sample-level label 추정은 금지.

## 다음 연구 질문

- 처음 보는 log trajectory에서 어떤 순서로 guidebook을 봐야 rule gap을 빨리 찾을 수 있는가?
- RESTler/StateAFL/ChatAFL/StatePre/MultiFuzz류는 coverage gap을 어떻게 줄였는가?
- 우리 문제에서 “coverage”를 code coverage가 아니라 rule/state/spec coverage로 어떻게 정의할 것인가?
