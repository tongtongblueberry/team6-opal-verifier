<!-- Changed: summarize the selected method in Korean for report preparation. -->
<!-- Why: the project argument should explain why AI is auxiliary, not the runtime core. -->
# 접근 방식 요약

## 결론

이 문제는 전체 trajectory가 주어지므로 순수 분류 AI가 필수인 문제는 아니다. 핵심은 TCG/Opal 명령이
상태 의존적이라는 점이다. 같은 마지막 응답이라도 이전 `StartSession`, `Set`, `Activate`, `GenKey`,
`Write` 이력에 따라 맞을 수도 있고 틀릴 수도 있다.

따라서 Team 6의 기본 접근은 deterministic state verifier다. AI는 필요한 경우 명세 문서 검색, 규칙 추출,
보고서 작성, low-confidence fallback에만 보조적으로 둔다.

## 런타임 구조

`src/solver.py`는 다음 단계를 수행한다.

1. command와 response JSON에서 method, invoking UID, status, session id, challenge, payload를 추출한다.
2. 마지막 record 이전까지 protocol state를 갱신한다.
3. 마지막 record에서 expected error와 actual status/payload를 비교한다.
4. 모순이 발견되면 `fail`, 아니면 `pass`를 반환한다.

## 왜 이 방식인가

공개 라벨은 매우 작다. 따라서 LLM fine-tuning이나 W&B sweep으로 classifier를 만드는 것은 데이터 누수와
과적합 위험이 크다. 반대로 상태 기반 verifier는 public/train 데이터 크기와 무관하게 hidden case에도
일관된 판단 기준을 제공한다.
