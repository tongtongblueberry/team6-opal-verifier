# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-27T18:20:07+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/official_restart_20260527_v1/02_raw_generation/dedup_candidates.codex_agent_fallback.jsonl`
- 전체 candidate 수: 12
- hard invariant pass 수: 12
- hard invariant fail 수: 0
- 요청 sample 수: 12
- 실제 audit pack sample 수: 12
- seed: 20260527

## Label 분포

- Accepted pool: `{"fail": 4, "pass": 8}`
- Audit sample: `{"fail": 4, "pass": 8}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- line 2, sample_id `codex-agent-fallback-self-instruct-gen-00000-02`, label `fail`, final `Set/INVALID_PARAMETER`
- line 9, sample_id `codex-agent-fallback-self-instruct-gen-00002-03`, label `pass`, final `Get/SUCCESS`
- line 6, sample_id `codex-agent-fallback-self-instruct-gen-00001-03`, label `pass`, final `Set/NOT_AUTHORIZED`
- line 7, sample_id `codex-agent-fallback-self-instruct-gen-00002-01`, label `pass`, final `StartSession/INVALID_PARAMETER`
- line 4, sample_id `codex-agent-fallback-self-instruct-gen-00001-01`, label `pass`, final `StartSession/INVALID_PARAMETER`
- line 3, sample_id `codex-agent-fallback-self-instruct-gen-00000-03`, label `pass`, final `StartSession/SP_BUSY`
- line 12, sample_id `codex-agent-fallback-self-instruct-gen-00003-03`, label `pass`, final `Set/INVALID_PARAMETER`
- line 8, sample_id `codex-agent-fallback-self-instruct-gen-00002-02`, label `fail`, final `Get/NOT_AUTHORIZED`
- line 10, sample_id `codex-agent-fallback-self-instruct-gen-00003-01`, label `pass`, final `Get/SUCCESS`
- line 11, sample_id `codex-agent-fallback-self-instruct-gen-00003-02`, label `fail`, final `Set/INVALID_PARAMETER`
- line 1, sample_id `codex-agent-fallback-self-instruct-gen-00000-01`, label `pass`, final `Get/SUCCESS`
- line 5, sample_id `codex-agent-fallback-self-instruct-gen-00001-02`, label `fail`, final `StartSession/NOT_AUTHORIZED`
