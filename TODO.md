<!-- Changed: refresh durable handoff after field-semantics submission and metric-saturation discussion. -->
<!-- Why: another Codex session should know the latest commit, score plateau, diagnostics, and next evaluation direction. -->

# TODO / Handoff

작성일: 2026-05-18

## 프로젝트 한 줄 요약

SSD TCG/Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 부합하는지 `pass`/`fail`로 판정하는 과제다. 현재 접근은 **deterministic state verifier + guidebook/RAG-assisted rule discovery**이다. 제출 runtime에는 LLM이나 Qwen을 넣지 않는다.

## 현재 저장소 상태

- Local path: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`
- GitHub: `https://github.com/tongtongblueberry/team6-opal-verifier`
- Main branch: `main`
- Server clone path used: `/workspace/team6/team6-opal-verifier`
- Clean submission paths used: `/workspace/team6/submission-<commit>`
- Server non-secret access memo: `server_access.md`
- 비밀번호와 token은 저장소에 저장하지 않는다.

## 현재 성능

- Latest code commit: `c613397`
- Latest submitted job:
  - Job ID: `102`
  - Submission ID: `3440cbdce03e48529eacb057a3c84b77`
  - Job Name: `team6-field-semantics-c613397`
  - Score: `69.50`
- Current best leaderboard score: `69.50`
- Server diagnostics for `c613397`:
  - Public train/dev: `100.00` (`20/20`)
  - Metamorphic/property diagnostics: `1821/1821`
  - Rule coverage with synthetic cases: `low_confidence=0`
  - Method-specific missing gaps: all `none`

이 제출은 `67cd09d`의 `69.50`을 넘기지는 못했다. 의미는 명확하다. known field semantics와 trace confidence는 개선됐지만, hidden score를 올리는 새 discriminative rule을 아직 찾지 못했다.

## 중요한 해석

public 100점, metamorphic 100%, coverage low-confidence 0은 모두 필요하지만 충분하지 않다.

- `public=100`: public 20개에 대한 sanity check다. 20개가 너무 작아서 hidden 일반화를 보장하지 않는다. public을 더 올릴 여지도 없고, public/leaderboard feedback에 맞춰 계속 고치면 holdout feedback에 적응하는 위험이 있다.
- `coverage low_confidence=0`: 우리가 정의한 coverage grid 안에서는 더 이상 generic/unsupported final trace가 없다는 뜻이다. 하지만 rule universe 자체가 빠져 있으면 100% coverage는 착시가 된다.
- `metamorphic=100`: 현재 생성한 property case를 모두 통과했다는 뜻이다. 논문 기준으로 더 중요한 값은 pass rate가 아니라 **mutation score**, 즉 rule을 삭제/약화한 mutant를 현재 테스트가 얼마나 잡는지다.

[EXTERNAL KNOWLEDGE] Roelofs, R., Shankar, V., Recht, B., Fridovich-Keil, S., Hardt, M., Miller, J., & Schmidt, L. (2019). *A meta-analysis of overfitting in machine learning*. Advances in Neural Information Processing Systems, 32. https://papers.nips.cc/paper/9117-a-meta-analysis

[EXTERNAL KNOWLEDGE] Blum, A., & Hardt, M. (2015). *The ladder: A reliable leaderboard for machine learning competitions*. Proceedings of Machine Learning Research, 37, 1006-1014. https://proceedings.mlr.press/v37/blum15.html

[EXTERNAL KNOWLEDGE] Chen, J., Wang, Y., Guo, Y., & Jiang, M. (2019). A metamorphic testing approach for event sequences. *PLOS ONE, 14*(2), e0212476. https://doi.org/10.1371/journal.pone.0212476

[EXTERNAL KNOWLEDGE] Saha, P., & Kanewala, U. (2019). *Fault detection effectiveness of metamorphic relations developed for testing supervised classifiers*. arXiv. https://doi.org/10.48550/arXiv.1904.07348

[EXTERNAL KNOWLEDGE] Ba, J., Jiang, Y., & Rigger, M. (2025). *Metamorphic coverage*. arXiv. https://doi.org/10.48550/arXiv.2508.16307

논문 기준 요약:

- Roelofs et al.은 public leaderboard와 private/final 평가 사이의 적응 문제를 Kaggle 대회 다수에서 분석했다.
- Blum and Hardt는 반복 제출 feedback이 holdout 추정치를 편향시킬 수 있음을 이론화했다.
- Chen et al.의 event-sequence metamorphic testing에서는 전체 MR 조합이 한 실험에서 mutant의 `39.23%`를 잡았고, 개별 MR은 `0.91%`부터 `16.79%`까지 크게 갈렸다. 다른 시나리오에서는 강한 MR이 `80-90%` 근처까지 갔지만 약한 MR은 훨씬 낮았다.
- Saha and Kanewala는 supervised classifier용 기존 MR들이 reachable mutant `709`개 중 `14.8%`만 잡았다고 보고했다.
- Ba et al.은 일반 code coverage가 metamorphic test의 실제 검증 정도를 잘 못 재며, pairwise/differential 관점의 metamorphic coverage가 더 유효할 수 있다고 본다.

따라서 다음 개선은 `metamorphic 1821 -> 5000`처럼 case 수만 늘리는 것이 아니다. **solver mutant를 만들고 현재 public/synthetic suite가 mutant를 잡는지 보는 mutation-style adequacy 평가**가 우선이다.

## 주요 파일

- `src/solver.py`: 제출 solver. `Solver.predict(dataset)`가 공식 entrypoint다.
- `tools/intermediate_eval.py`: public train/dev 중간평가 도구.
- `tools/build_spec_index.py`: 서버 guidebook chunk index 생성.
- `tools/rule_coverage.py`: trace 기반 rule/state/spec coverage matrix 생성.
- `tools/metamorphic_eval.py`: public seed에서 생성한 synthetic positive/negative property tests.
- `tools/metamorphic_coverage.py`: Ba et al. 2025 Metamorphic Coverage를 solver trace feature에 이식한 differential coverage 도구.
- `docs/submission_log.md`: commit-level leaderboard 기록. hidden sample label 추정은 기록하지 않는다.
- `docs/rule_coverage_research_ko.md`: 관련 방법론 조사와 rule coverage 확장 계획.
- `docs/metamorphic_coverage_application_ko.md`: 선택 논문의 metric/architecture/loss 부재와 프로젝트 적용 방식.
- `docs/methodology_survey_ko.md`: 초기 관련 방법론 조사.
- `docs/data_protocol.md`: train/leaderboard/test 분리 원칙.
- `project_analysis_ko.md`: 프로젝트 상태 요약.

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
- `tools/metamorphic_eval.py` 추가.
- `GenKey`, `Set`, `EndSession`, `Activate` 성공 response의 empty-result invariant 추가.
- `Set(C_PIN.Values[3])`를 `known_secrets`로 추적하고 `StartSession.HostChallenge`와 연결.
- `Set` duplicate RowValues column을 `INVALID_PARAMETER`로 검증.
- structured empty result인 `{"required": {}, "optional": {}}`를 정상 empty payload로 정규화.
- synthetic-inclusive rule coverage를 추가하고 method-specific applicable columns로 false gap을 줄임.
- `StartSession` success response가 `SyncSession`, `HostSessionID` echo, `SPSessionID`를 만족하는지 검증.
- `Properties` target을 Session Manager로 제한하고 `Get` no-session precondition synthetic tests 추가.
- DATA_COMMAND `Read/Write` response command identity와 payload presence invariant 추가.
- `Locking`, `MBRControl`, `Authority.Enabled`, `C_PIN`의 known field access/value semantics를 추가해 low-confidence 4개를 제거.

## 제출 이력 요약

| Commit | Key change | Server diagnostics | Leaderboard |
|---|---|---|---|
| `872f31d` | initial state verifier | public 20/20 | 60.50 |
| `fd43bd5` | spec index, coverage, Get field/data rules | public 20/20 | 68.00 |
| `0c5e6d8` | metamorphic/property diagnostics, GenKey empty result | public 20/20, metamorphic 174/174 | 68.00 |
| `bf6c40b` | C_PIN secret tracking for StartSession | public 20/20, metamorphic 474/474 | 69.00 |
| `bcfdc94` | Set duplicate column and empty result | public 20/20, metamorphic 576/576 | 69.00 |
| `fc0289e` | latest submitted docs/code after daily limit | public 20/20, metamorphic 970/970 | 69.00 |
| `67cd09d` | method-specific coverage gaps closed | public 20/20, metamorphic 1453/1453 | 69.50 |
| `c613397` | known field semantics and low-confidence removal | public 20/20, metamorphic 1821/1821, low_confidence 0 | 69.50 |

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
  --include-synthetic \
  --out reports/rule_coverage_<commit>.json
```

서버 metamorphic/property diagnostics:

```bash
python3 tools/metamorphic_eval.py \
  --dataset-root /dl2026/dataset \
  --jsonl-out reports/metamorphic_<commit>.jsonl
```

서버 Metamorphic Coverage diagnostics:

```bash
python3 tools/metamorphic_coverage.py \
  --dataset-root /dl2026/dataset \
  --out reports/metamorphic_coverage_<commit>.json \
  --jsonl-out reports/metamorphic_coverage_<commit>.jsonl
```

제출:

```bash
mkdir -p /workspace/team6/submission-<commit>
git archive -o /workspace/team6/submission-<commit>.tar HEAD
tar -xf /workspace/team6/submission-<commit>.tar -C /workspace/team6/submission-<commit>
submit -d /workspace/team6/submission-<commit> -n team6-state-verifier-<commit>
submit --list
```

## 다음 TODO

1. Mutation-style adequacy 평가를 추가한다.
   - 목적: public/metamorphic/coverage 100이 hidden gap 탐지력을 잃었는지 확인한다.
   - 방식: solver rule을 삭제/약화한 mutant들을 만들고, 현재 public/synthetic suite가 그 mutant를 잡는지 본다.
   - 예시 mutant:
     - `STARTSESSION_FINAL` response-shape check 제거
     - `KNOWN_FIELD_EXPECTED_SUCCESS` 제거
     - `GET_PAYLOAD` requested-column subset check 제거
     - `READ_PAYLOAD` old-pattern check 제거
     - `PRECONDITION_EXPECTED_ERROR` no-session check 제거
   - 결과 지표: killed mutants / total non-equivalent mutants.

2. Metamorphic case 수가 아니라 MR diversity를 늘린다.
   - 현재 1821/1821은 pass rate saturated 상태다.
   - 다음 case는 기존 rule의 같은 형태를 반복하지 말고, 서로 다른 event sequence, state producer-consumer path, object/table field를 겨냥한다.

3. Guidebook rule universe를 재정의한다.
   - 현재 coverage grid 밖의 rule category가 빠졌는지 확인한다.
   - 우선순위:
     - `Locking` range and read/write lock semantics
     - `MBRControl.Enable/Done`
     - `Authority.Enabled`
     - SP lifecycle and activation state
     - `GenKey`가 data visibility에 미치는 범위

4. LLM/RAG는 서버에서만 rule proposal 생성기로 쓴다.
   - Qwen/Gemma는 로컬에 다운로드하지 않는다.
   - LLM output은 바로 solver에 넣지 않고, 사람이 검토 가능한 rule proposal로 저장한다.
   - 최종 solver는 deterministic rule만 포함한다.

5. 제출 로그 원칙을 유지한다.
   - leaderboard 결과는 commit-level 점수만 기록한다.
   - hidden sample-level label을 역추론하거나 rule에 직접 반영하지 않는다.
