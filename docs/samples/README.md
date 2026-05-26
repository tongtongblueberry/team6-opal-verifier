# Sample 공개 정책

- 최종 갱신: 2026-05-26 16:26 KST

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

<!-- Changed: clarify the role of the public20 sample in sample.md. -->
<!-- Why: public20 is a provided reference, while generated synthetic data is the validation target. -->
`self_instruct_sample.md`의 public20 raw sample은 비교 기준 구조를 보여주기 위한 reference다.
public20 자체를 검증했다는 의미가 아니며, public20-only 모델 검증에서도 `train`/`val`만
사용한다. 여기서 `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는
leaderboard hidden 평가로 둔다.

현재 상태: Gate A/B/C를 모두 통과한 Self-Instruct synthetic dataset이 아직 없으므로
`self_instruct_sample.md`는 작성하지 않는다.

ad-hoc fixture/smoke generated data is not accepted synthetic data.
논문 기반 생성 방법과 Gate A/B/C를 거치지 않은 임의 synthetic 산출물은
`self_instruct_sample.md`에 합격 sample로 공개하지 않는다.
