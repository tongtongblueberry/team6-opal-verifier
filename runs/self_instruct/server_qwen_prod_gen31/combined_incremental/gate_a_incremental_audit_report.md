# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-29T14:12:34+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/server_qwen_prod_gen31/combined_incremental/adversarial_rulebook_accepted.incremental.jsonl`
- 전체 candidate 수: 1
- hard invariant pass 수: 1
- hard invariant fail 수: 0
- 요청 sample 수: 40
- 실제 audit pack sample 수: 1
- seed: 20260529

## Label 분포

- Accepted pool: `{"pass": 1}`
- Audit sample: `{"pass": 1}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- line 1, sample_id `active::self-instruct-gen-00006-cand-00`, label `pass`, final `Get/SUCCESS`
