# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-27T23:39:10+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST/judge_accepted.trajectory_signature.codex_agent_fallback.jsonl`
- 전체 candidate 수: 25
- hard invariant pass 수: 25
- hard invariant fail 수: 0
- 요청 sample 수: 25
- 실제 audit pack sample 수: 25
- seed: 20260527

## Label 분포

- Accepted pool: `{"fail": 13, "pass": 12}`
- Audit sample: `{"fail": 13, "pass": 12}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- line 8, sample_id `codex-agent-fallback-targeted-schedule-200plus-00007`, label `fail`, final `StartSession/SP_FROZEN`
- line 15, sample_id `codex-agent-fallback-targeted-schedule-200plus-00014`, label `pass`, final `StartSession/SUCCESS`
- line 10, sample_id `codex-agent-fallback-targeted-schedule-200plus-00009`, label `fail`, final `StartSession/NO_SESSIONS_AVAILABLE`
- line 21, sample_id `codex-agent-fallback-targeted-schedule-200plus-00030`, label `pass`, final `Properties/SUCCESS`
- line 2, sample_id `codex-agent-fallback-targeted-schedule-200plus-00001`, label `fail`, final `Set/NOT_AUTHORIZED`
- line 7, sample_id `codex-agent-fallback-targeted-schedule-200plus-00006`, label `pass`, final `Get/SUCCESS`
- line 25, sample_id `codex-agent-fallback-targeted-schedule-200plus-00039`, label `fail`, final `Get/INVALID_PARAMETER`
- line 17, sample_id `codex-agent-fallback-targeted-schedule-200plus-00016`, label `pass`, final `Activate/SUCCESS`
- line 4, sample_id `codex-agent-fallback-targeted-schedule-200plus-00003`, label `fail`, final `StartSession/NOT_AUTHORIZED`
- line 13, sample_id `codex-agent-fallback-targeted-schedule-200plus-00012`, label `pass`, final `Authenticate/SUCCESS`
- line 22, sample_id `codex-agent-fallback-targeted-schedule-200plus-00031`, label `fail`, final `Activate/NOT_AUTHORIZED`
- line 3, sample_id `codex-agent-fallback-targeted-schedule-200plus-00002`, label `pass`, final `Get/SUCCESS`
- line 19, sample_id `codex-agent-fallback-targeted-schedule-200plus-00019`, label `fail`, final `Set/INVALID_PARAMETER`
- line 20, sample_id `codex-agent-fallback-targeted-schedule-200plus-00028`, label `pass`, final `Get/SUCCESS`
- line 16, sample_id `codex-agent-fallback-targeted-schedule-200plus-00015`, label `fail`, final `Get/INVALID_PARAMETER`
- line 11, sample_id `codex-agent-fallback-targeted-schedule-200plus-00010`, label `pass`, final `Authenticate/SUCCESS`
- line 6, sample_id `codex-agent-fallback-targeted-schedule-200plus-00005`, label `fail`, final `StartSession/SP_BUSY`
- line 9, sample_id `codex-agent-fallback-targeted-schedule-200plus-00008`, label `pass`, final `Set/SUCCESS`
- line 12, sample_id `codex-agent-fallback-targeted-schedule-200plus-00011`, label `fail`, final `StartSession/INVALID_PARAMETER`
- line 5, sample_id `codex-agent-fallback-targeted-schedule-200plus-00004`, label `pass`, final `Get/SUCCESS`
- line 23, sample_id `codex-agent-fallback-targeted-schedule-200plus-00033`, label `fail`, final `RevertSP/FAIL`
- line 24, sample_id `codex-agent-fallback-targeted-schedule-200plus-00038`, label `pass`, final `Get/SUCCESS`
- line 18, sample_id `codex-agent-fallback-targeted-schedule-200plus-00017`, label `fail`, final `Set/NOT_AUTHORIZED`
- line 1, sample_id `codex-agent-fallback-targeted-schedule-200plus-00000`, label `pass`, final `Properties/SUCCESS`
- line 14, sample_id `codex-agent-fallback-targeted-schedule-200plus-00013`, label `fail`, final `Set/INVALID_PARAMETER`
