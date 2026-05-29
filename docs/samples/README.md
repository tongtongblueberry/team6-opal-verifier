# Sample 공개 정책

- 최종 갱신: 2026-05-29 14:13:39 KST

<!-- Changed: add a stable location for raw sample disclosure rules. -->
<!-- Why: raw generated data should be shown only after the agreed quality gates, not while it is still unverified. -->

<!-- Changed: require complete real-generation and Gate A/B/C/D/Self-Instruct quality pass before public sample creation. -->
<!-- Why: sample 1개도 accepted data로 공개되려면 raw generation부터 parser, dedup, judge, quality gates를 모두 통과해야 한다. -->
Self-Instruct synthetic data 1개는 real raw generation, parse, dedup, judge, Gate A/B/C/D,
Self-Instruct quality 검증을 모두 통과한 뒤에만 `docs/samples/self_instruct_sample.md`에
공개한다.

<!-- Changed: record cleanup classification relevant to sample publication. -->
<!-- Why: remove-candidate/generated run files must not be treated as sample evidence or deleted by this sync. -->
docs/runs cleanup은 pending이다. active docs, research/spec docs, `runs/self_instruct/public20_baseline`,
<!-- Changed: update sample-policy cleanup classification to the active public20 10/10 split path. -->
<!-- Why: sample evidence must not rely on archived 16/4 model-validation artifacts. -->
`runs/model_validation/public20_10_10_splits`는 keep이다. `runs/model_validation/public20_splits`는 16/4 archive-only evidence다. `server_access.md`는 secret-sensitive로 취급한다.
`public20_trl_sft` derived JSONL은 remove-candidate pending이며 삭제하지 않는다. reports/plans는 archive 분류다.

필수 포함 항목:

- generated raw trajectory 전체
- label
- target
- primary evidence
- spec grounding source span
- profile
- public20 raw sample 1개 전체
- Gate A audit summary
- Gate B comparison summary
- Gate C manifest/model-input summary
- Gate D leaderboard submission/no-go summary
- Self-Instruct quality verification summary

Gate A/B/C/D와 Self-Instruct quality 검증 전에는 raw synthetic sample을 "합격 데이터"로 제시하지 않는다. 통과 전
sample은 검수 대기, 실패 분석, 또는 no-go evidence로만 표시한다.

<!-- Changed: clarify the role of the public20 sample in sample.md. -->
<!-- Why: public20 is a provided reference, while generated synthetic data is the validation target. -->
`self_instruct_sample.md`의 public20 raw sample은 비교 기준 구조를 보여주기 위한 reference다.
public20 자체를 검증했다는 의미가 아니며, public20-only 모델 검증에서도 `train`/`val`만
사용한다. 여기서 `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는
leaderboard hidden 평가로 둔다.

<!-- Changed: update sample publication status after gen3.1 stop. -->
<!-- Why: one pending accepted row from the local watcher is not canonical sample evidence. -->
현재 상태: gen3.1 generation은 server raw `72/1000`에서 중단됐고 local watcher도 중단됐다. Local pending export는 `data/local/gen3_pending`에 1 row가 있지만, server canonical final export가 아니며 Gate B/C/D도 통과하지 않았다. 따라서 `self_instruct_sample.md`는 작성하지 않는다.
<!-- Changed: keep sample no-go aligned with latest Self-Instruct and public20 artifact status. -->
<!-- Why: implemented dry-run/schema artifacts and 10/10 public20 splits are not accepted raw synthetic samples. -->
공식 Self-Instruct dry-run/schema mapping은 instruction generation artifact, classification detection audited no-op artifact,
output-first instance artifact, prepare/finetuning candidate artifact까지 구현됐고, gen3.1 real Qwen raw output도 `72`개 생성됐다.
하지만 canonical generated dataset은 없고 Gate A/B/C/D pass artifact도 없으므로 `self_instruct_sample.md` 작성은 no-go다.
public20 10/10 split builder 산출물 `runs/model_validation/public20_10_10_splits`는 모델 검증용이며,
accepted synthetic sample 근거가 아니다.
<!-- Changed: record worker-reported focused verification without relaxing sample no-go. -->
<!-- Why: passing split/Self-Instruct tests do not replace real raw output and Gate A/B/C/D sample evidence. -->
worker-reported verification은 split builder `6 tests OK`, self_instruct `23 tests OK`,
worker `git diff --check OK`다. 이 검증 결과는 sample 공개 조건을 충족하지 않는다.

<!-- Changed: make sample publication depend on spec-grounded candidate provenance. -->
<!-- Why: source-span 없는 generated text는 accepted synthetic sample로 공개하면 안 된다. -->
`spec_grounding` source span이 없는 raw output은 `self_instruct_sample.md` 공개 대상이
아니며, Gate A/B/C/D와 Self-Instruct quality 검증 통과 전 no-go 상태로 둔다.

ad-hoc fixture/smoke generated data is not accepted synthetic data.
논문 기반 생성 방법과 Gate A/B/C/D 및 Self-Instruct quality 검증을 거치지 않은 임의 synthetic 산출물은
`self_instruct_sample.md`에 합격 sample로 공개하지 않는다.

Self-Instruct synthetic generation은 공식 논문과 `yizhongw/self-instruct` 공식 코드
기준을 따른 후보만 대상으로 한다. LLM 호출 없는 parser, dedup/filter, Gate C
equivalence가 먼저 구현되고, 그 뒤 생성 wrapper와 Gate A/B/C/D 및 Self-Instruct quality
검증을 통과한 sample만 공개한다.
