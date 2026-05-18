<!-- Changed: update approach after RAG+LLM hybrid solver implementation. -->
<!-- Why: architecture evolved from pure rule engine to confidence-gated hybrid. -->
# 접근 방식 요약

## 결론

이 문제는 전체 trajectory가 주어지므로 순수 분류 AI가 필수인 문제는 아니다. 핵심은 TCG/Opal 명령이
상태 의존적이라는 점이다. 같은 마지막 응답이라도 이전 `StartSession`, `Set`, `Activate`, `GenKey`,
`Write` 이력에 따라 맞을 수도 있고 틀릴 수도 있다.

Team 6의 접근은 **confidence-gated hybrid solver**다:
- **확신이 높은 case**: deterministic rule engine이 직접 판정 (빠르고 정확)
- **확신이 낮은 case**: RAG (BM25 spec retrieval) + LLM (Qwen3.5-27B-FP8)이 판정

## 런타임 구조

`src/solver.py::Solver.predict(dataset)`는 다음 단계를 수행한다.

1. `StatefulOpalVerifier.verify_with_trace(steps)`로 rule engine을 실행한다.
   - command와 response JSON에서 method, invoking UID, status, session id, challenge, payload를 추출한다.
   - 마지막 record 이전까지 protocol state를 갱신한다.
   - 마지막 record에서 expected error와 actual status/payload를 비교한다.
   - trace에 어떤 rule이 적용되었는지 기록한다.
2. 마지막 trace의 `rule_id`를 확인한다.
   - specific rule (e.g., `STARTSESSION_FINAL`, `GET_PAYLOAD`): 그 판정을 그대로 사용한다.
   - `DEFAULT_PASS` (unmodeled error): RAG+LLM fallback으로 넘긴다.
3. RAG fallback (`src/rag.py`):
   - trajectory에서 BM25 검색 query를 추출한다 (method, object, status, error context).
   - 500+ TCG/Opal spec chunk에서 top-5 관련 passage를 검색한다.
   - Qwen3.5-27B-FP8에게 trajectory + spec context를 주고 pass/fail을 묻는다.
4. 최종 prediction을 반환한다.

[EXTERNAL KNOWLEDGE] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive Language Tasks*. NeurIPS 2020. https://arxiv.org/abs/2005.11401

## 왜 이 방식인가

1. **Rule engine alone**: 순수 rule engine은 public 20/20, leaderboard 71.50까지 도달했지만 plateau.
   규칙을 수동으로 작성하는 것은 500+ spec 문서의 모든 edge case를 커버하기 어렵다.

2. **LLM alone**: LLM fine-tuning은 공개 라벨 20개로는 과적합 위험이 크다. 또한 200 case 전부를
   LLM으로 처리하면 속도가 느려진다.

3. **Hybrid**: 확실한 case는 rule engine (빠르고 정확), 불확실한 case만 LLM (spec을 직접 참조).
   이렇게 하면 regression을 최소화하면서 unmodeled case를 처리할 수 있다.

## 서버 요구사항

- GPU: NVIDIA L40S 46GB VRAM (27B FP8 = ~27GB, 여유 충분)
- 모델: Qwen3.5-27B-FP8 (사전 다운로드: `python3 tools/download_model.py`)
- Spec 문서: `/dl2026/skeleton/artifacts/documents/` (500+ .txt files)
- 로컬에서는 RAG 비활성화, 순수 rule engine으로 동작
