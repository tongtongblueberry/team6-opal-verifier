<!-- Changed: update project analysis after c613397 field-semantics submission and metric interpretation. -->
<!-- Why: previous analysis still treated low-confidence traces as the next gap; that is now resolved but leaderboard remains flat. -->

# Team 6 SSD TCG/Opal Verifier 현재 분석

작성일: 2026-05-18

## 현재 결론

이 프로젝트는 순수 AI classifier 문제라기보다 **spec-grounded state verifier** 문제다. 입력 trajectory 전체가 주어지므로, 마지막 command-response pair가 현재 SSD/TCG/Opal 상태에서 명세상 가능한 응답인지 판단하면 된다.

현재 제출 solver는 LLM이나 Qwen을 런타임에 사용하지 않는다. `src/solver.py`는 JSON command/response를 정규화하고, session/auth/SP/key/data/object-field 상태를 추적한 뒤 마지막 record를 `pass` 또는 `fail`로 판정한다.

## 현재 구현 상태

- GitHub repo: `https://github.com/tongtongblueberry/team6-opal-verifier`
- Main entrypoint: `src/solver.py::Solver.predict(dataset)`
- Latest submitted commit: `c613397`
- Latest submitted job:
  - Job ID: `102`
  - Submission ID: `3440cbdce03e48529eacb057a3c84b77`
  - Job Name: `team6-field-semantics-c613397`
  - Score: `69.50`
- Current best leaderboard score: `69.50`
- Server diagnostics:
  - Public train/dev score on `/dl2026/dataset`: `100.00` (`20/20`)
  - Metamorphic/property diagnostics: `1821/1821`
  - Rule coverage with synthetic cases: `low_confidence=0`
  - Method-specific missing gaps: all `none`

## 55점이 낮게 나온 이유

초기 낮은 점수는 모델 크기나 fine-tuning 부족 때문이 아니었다. 원인은 parser/rule coverage 부족이었다.

- `HostSessionID`, `SPSessionID`를 session id로 인식하지 못했다.
- `HostChallenge`를 PIN 원문과 동일 비교하는 잘못된 가정이 있었다.
- `command: Read/Write` DATA_COMMAND를 TCG method session precondition과 섞어 처리했다.
- `Write` 입력의 `pattern` payload를 읽지 못했다.
- `Activate`에서 SP UID identity 검증이 부족했다.

이 문제들을 수정한 뒤 public train/dev는 100점이 됐다. guidebook 기반 `Get` field consistency, DATA_COMMAND read/write, invalid Cellblock rule을 추가한 뒤 leaderboard는 68.00이 됐다. 이후 `Set(C_PIN)` column 3을 secret state로 추적해 StartSession authentication에 연결하면서 69.00이 됐고, method-specific coverage gap을 닫는 해결 사이클 후 69.50까지 올랐다.

## 최근 개선: field semantics

[Original Text/Data] → `67cd09d`에서 public `20/20`, metamorphic `1453/1453`, method-specific coverage gap `none`이었지만 low-confidence trace가 4개 남아 있었다. 해당 trace는 `C_PIN`, `Authority.Enabled`, `Locking`, `MBRControl` final error를 generic `UNEXPECTED_ERROR_STATUS`로 설명했다.

[Exact Interpretation] → solver는 pass/fail 자체는 맞췄지만, 왜 그 error가 이상한지 object/table field semantics로 설명하지 못했다. 이것은 hidden score를 직접 올리는 문제라기보다 rule explanation/coverage quality 문제였다.

[Detailed Explanation/Example] → `Locking`의 column `3-8`, `MBRControl`의 column `1-2`, `Authority.Enabled` column `5`, `C_PIN` column `3`처럼 guidebook에서 확인되는 known field access는 정상 세션/인증 상태에서 generic error가 아니라 success여야 한다. 또한 boolean field에 `2` 같은 값이 들어가면 `INVALID_PARAMETER`가 expected error가 된다. `c613397`은 이를 `KNOWN_FIELD_EXPECTED_SUCCESS`, `KNOWN_FIELD_INVALID_VALUE` rule과 synthetic mutation으로 추가했다.

결과:

- Public: `20/20`
- Metamorphic/property: `1821/1821`
- Synthetic-inclusive rule coverage: `low_confidence=0`
- Leaderboard: `69.50`

## 지표 해석

public, metamorphic, coverage 지표는 모두 필요하지만 hidden 성능을 보장하지 않는다.

[Original Text/Data] → 현재 public `100.00`, metamorphic `1821/1821`, coverage `low_confidence=0`이지만 leaderboard는 `69.50`에서 오르지 않았다.

[Exact Interpretation] → 우리가 만든 진단 체계 안에서는 발견되는 문제가 줄었지만, hidden 평가에서 필요한 rule universe가 아직 진단 체계 밖에 있을 가능성이 높다. 즉 “점검한 항목은 모두 통과”와 “문제가 모두 해결”은 다르다.

[Detailed Explanation/Example] → `metamorphic_eval.py`의 case 수를 1821개에서 5000개로 늘려도 같은 종류의 rule을 반복하면 hidden gap 탐지력은 늘지 않는다. 더 의미 있는 다음 평가는 solver rule을 삭제/약화한 mutant를 만들고 현재 suite가 그 mutant를 잡는지 보는 mutation-style adequacy다.

[EXTERNAL KNOWLEDGE] Roelofs, R., Shankar, V., Recht, B., Fridovich-Keil, S., Hardt, M., Miller, J., & Schmidt, L. (2019). *A meta-analysis of overfitting in machine learning*. Advances in Neural Information Processing Systems, 32. https://papers.nips.cc/paper/9117-a-meta-analysis

[EXTERNAL KNOWLEDGE] Blum, A., & Hardt, M. (2015). *The ladder: A reliable leaderboard for machine learning competitions*. Proceedings of Machine Learning Research, 37, 1006-1014. https://proceedings.mlr.press/v37/blum15.html

[EXTERNAL KNOWLEDGE] Chen, J., Wang, Y., Guo, Y., & Jiang, M. (2019). A metamorphic testing approach for event sequences. *PLOS ONE, 14*(2), e0212476. https://doi.org/10.1371/journal.pone.0212476

[EXTERNAL KNOWLEDGE] Saha, P., & Kanewala, U. (2019). *Fault detection effectiveness of metamorphic relations developed for testing supervised classifiers*. arXiv. https://doi.org/10.48550/arXiv.1904.07348

[EXTERNAL KNOWLEDGE] Ba, J., Jiang, Y., & Rigger, M. (2025). *Metamorphic coverage*. arXiv. https://doi.org/10.48550/arXiv.2508.16307

논문 기준:

- public leaderboard feedback은 반복 제출 과정에서 holdout 적응 위험을 만든다.
- coverage 100은 정의된 coverage grid 안에서만 의미가 있다.
- metamorphic pass rate 100은 현재 MR 집합이 깨지지 않았다는 뜻이지 fault-detection capability가 충분하다는 뜻이 아니다.
- Chen et al. 2019의 event-sequence MT는 전체 MR 조합이 한 실험에서 mutant의 `39.23%`만 잡았고, 개별 MR은 `0.91%`부터 `16.79%`까지 크게 갈렸다.
- Saha and Kanewala 2019는 supervised classifier용 기존 MR들이 reachable mutant `709`개 중 `14.8%`만 잡았다고 보고했다.

## 현재 방향

다음 개선은 leaderboard hidden label을 역추론하는 것이 아니라, guidebook 기반 rule universe와 mutation-style adequacy를 확장하는 것이다.

권장 구조:

1. `StatefulOpalVerifier`의 trace mode로 final rule과 state read/write를 확인한다.
2. `tools/metamorphic_eval.py` pass rate만 보지 말고 solver mutant를 만들어 mutation score를 측정한다.
3. `/dl2026/skeleton/artifacts/documents`의 core/opal chunk를 lightweight index로 검색한다.
4. 서버에서만 Qwen/Gemma 등 LLM을 사용해 rule 후보와 spec reference 후보를 추출한다.
5. 제출 solver runtime은 deterministic rule engine으로 유지한다.

## 데이터 분리 원칙

- Public labeled data `/dl2026/dataset`은 train/dev 용도로만 사용한다.
- Leaderboard 결과는 점수와 commit 기록에만 사용한다.
- Hidden leaderboard/test sample label을 역추론해 rule에 직접 박지 않는다.
- 로컬과 GitHub에는 Qwen 같은 대형 모델을 받거나 커밋하지 않는다.
- 서버 비밀번호나 GitHub token은 파일, 커밋, 문서에 저장하지 않는다.
