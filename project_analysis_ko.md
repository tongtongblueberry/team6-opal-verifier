<!-- Changed: update project analysis after RAG+LLM hybrid solver implementation. -->
<!-- Why: architecture changed from pure rule engine to confidence-gated hybrid. -->

# Team 6 SSD TCG/Opal Verifier 현재 분석

작성일: 2026-05-18

## 현재 결론

이 프로젝트는 순수 AI classifier 문제라기보다 **spec-grounded state verifier** 문제다. 입력 trajectory 전체가 주어지므로, 마지막 command-response pair가 현재 SSD/TCG/Opal 상태에서 명세상 가능한 응답인지 판단하면 된다.

현재 제출 solver는 **confidence-gated hybrid** 방식을 사용한다:
- 확신이 높은 case: deterministic rule engine (`StatefulOpalVerifier`)이 직접 판정
- 확신이 낮은 case (DEFAULT_PASS): RAG (BM25 over spec chunks) + LLM (Qwen3.5-27B-FP8)이 판정

`src/solver.py`는 JSON command/response를 정규화하고, session/auth/SP/key/data/object-field 상태를 추적한 뒤, 마지막 record를 판정한다. Rule engine이 error status를 설명하지 못하면 (`DEFAULT_PASS`), spec 문서에서 관련 passage를 BM25로 검색하고 LLM에게 pass/fail을 묻는다.

[EXTERNAL KNOWLEDGE] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive Language Tasks*. NeurIPS 2020. https://arxiv.org/abs/2005.11401

## 현재 구현 상태

- GitHub repo: `https://github.com/tongtongblueberry/team6-opal-verifier`
- Main entrypoint: `src/solver.py::Solver.predict(dataset)`
- Architecture: **Confidence-Gated Hybrid** (Rule Engine + RAG/LLM)
- LLM: Qwen3.5-27B-FP8 (FP16, ~27GB VRAM FP8, 서버 전용)
- Retrieval: BM25 over 500+ spec .txt chunks (from `/dl2026/skeleton/artifacts/documents/`)
- Latest submitted commit: `2df1e71`
- Latest submitted job:
  - Job ID: `107`
  - Submission ID: `1871750633c343ccb8f2bc7af1fd0665`
  - Job Name: `team6-locking-2df1e71`
  - Score: `71.50`
- Current best leaderboard score: `71.50`
- Server diagnostics (latest code):
  - Public train/dev score on `/dl2026/dataset`: `100.00` (`20/20`)
  - Metamorphic/property diagnostics: `1891/1891`
  - Mutation score: `1.0000` (`11/11` mutants killed)
  - Rule coverage with synthetic cases: `low_confidence=0`

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

순수 rule engine의 한계(71.50 plateau)를 넘기 위해 **confidence-gated hybrid** 아키텍처로 전환했다.

현재 구조:

1. `StatefulOpalVerifier`가 모든 case를 trace mode로 판정한다.
2. 확신이 높은 case (specific rule fired): rule engine 결과를 그대로 사용한다.
3. 확신이 낮은 case (`DEFAULT_PASS`): `src/rag.py`의 RAG pipeline이 처리한다.
   - BM25로 spec chunk를 검색한다 (500+ guidebook .txt files).
   - Qwen3.5-27B-FP8 (FP16)가 trajectory + spec context를 보고 pass/fail을 판정한다.
4. 로컬에서는 RAG가 비활성화되고 순수 rule engine으로 동작한다 (torch/transformers 없음).

다음 개선:

1. 서버에서 hybrid solver 검증 후 leaderboard 제출
2. Prompt/retrieval 튜닝 (top_k, chunk_size, system prompt 강도)
3. Rule engine 자체 확장 (Authenticate, Byte table, Session type 등)

## 데이터 분리 원칙

- Public labeled data `/dl2026/dataset`은 train/dev 용도로만 사용한다.
- Leaderboard 결과는 점수와 commit 기록에만 사용한다.
- Hidden leaderboard/test sample label을 역추론해 rule에 직접 박지 않는다.
- 로컬과 GitHub에는 Qwen 같은 대형 모델을 받거나 커밋하지 않는다. 서버 캐시만 사용한다.
- 서버 비밀번호나 GitHub token은 파일, 커밋, 문서에 저장하지 않는다.
