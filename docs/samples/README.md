# Sample 공개 정책

- 최종 갱신: 2026-05-26 15:52 KST

<!-- Changed: add a stable location for raw sample disclosure rules. -->
<!-- Why: raw generated data should be shown only after the agreed quality gates, not while it is still unverified. -->

Self-Instruct synthetic data가 Gate A/B/C를 모두 통과하면
`docs/samples/self_instruct_sample.md`를 작성한다.

필수 포함 항목:

- generated raw trajectory 전체
- label
- target
- primary evidence
- profile
- public20 raw sample 1개 전체
- Gate A audit summary
- Gate B comparison summary
- Gate C manifest/model-input summary

Gate A/B/C 전에는 raw synthetic sample을 "합격 데이터"로 제시하지 않는다. 통과 전
sample은 검수 대기, 실패 분석, 또는 no-go evidence로만 표시한다.

현재 상태: Gate A/B/C를 모두 통과한 Self-Instruct synthetic dataset이 아직 없으므로
`self_instruct_sample.md`는 작성하지 않는다.
