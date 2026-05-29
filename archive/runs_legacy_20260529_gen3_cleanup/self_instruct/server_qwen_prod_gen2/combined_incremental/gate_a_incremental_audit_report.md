# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-29T12:04:02+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/server_qwen_prod_gen2/combined_incremental/dedup_candidates.combined.namespaced.jsonl`
- 전체 candidate 수: 0
- hard invariant pass 수: 0
- hard invariant fail 수: 0
- 요청 sample 수: 40
- 실제 audit pack sample 수: 0
- seed: 20260529

## Label 분포

- Accepted pool: `{}`
- Audit sample: `{}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- 없음
