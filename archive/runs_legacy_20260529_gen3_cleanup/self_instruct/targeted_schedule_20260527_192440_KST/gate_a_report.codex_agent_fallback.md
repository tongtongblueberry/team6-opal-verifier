# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-27T20:43:10+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/targeted_schedule_20260527_192440_KST/judge_accepted.codex_agent_fallback.jsonl`
- 전체 candidate 수: 40
- hard invariant pass 수: 40
- hard invariant fail 수: 0
- 요청 sample 수: 200
- 실제 audit pack sample 수: 40
- seed: 20260527

## Label 분포

- Accepted pool: `{"fail": 20, "pass": 20}`
- Audit sample: `{"fail": 20, "pass": 20}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- line 28, sample_id `codex-agent-fallback-targeted-schedule-00027`, label `fail`, final `StartSession/INVALID_PARAMETER`
- line 39, sample_id `codex-agent-fallback-targeted-schedule-00038`, label `pass`, final `Get/SUCCESS`
- line 19, sample_id `codex-agent-fallback-targeted-schedule-00018`, label `pass`, final `Activate/SUCCESS`
- line 30, sample_id `codex-agent-fallback-targeted-schedule-00029`, label `fail`, final `Activate/FAIL`
- line 5, sample_id `codex-agent-fallback-targeted-schedule-00004`, label `pass`, final `Get/SUCCESS`
- line 22, sample_id `codex-agent-fallback-targeted-schedule-00021`, label `fail`, final `Set/INVALID_PARAMETER`
- line 21, sample_id `codex-agent-fallback-targeted-schedule-00020`, label `pass`, final `Revert/SUCCESS`
- line 8, sample_id `codex-agent-fallback-targeted-schedule-00007`, label `fail`, final `StartSession/SP_FROZEN`
- line 35, sample_id `codex-agent-fallback-targeted-schedule-00034`, label `pass`, final `Properties/SUCCESS`
- line 24, sample_id `codex-agent-fallback-targeted-schedule-00023`, label `fail`, final `Set/INVALID_PARAMETER`
- line 37, sample_id `codex-agent-fallback-targeted-schedule-00036`, label `pass`, final `Next/SUCCESS`
- line 16, sample_id `codex-agent-fallback-targeted-schedule-00015`, label `fail`, final `Get/INVALID_PARAMETER`
- line 15, sample_id `codex-agent-fallback-targeted-schedule-00014`, label `pass`, final `StartSession/SUCCESS`
- line 38, sample_id `codex-agent-fallback-targeted-schedule-00037`, label `fail`, final `Random/INVALID_PARAMETER`
- line 31, sample_id `codex-agent-fallback-targeted-schedule-00030`, label `pass`, final `Properties/SUCCESS`
- line 14, sample_id `codex-agent-fallback-targeted-schedule-00013`, label `fail`, final `Set/INVALID_PARAMETER`
- line 33, sample_id `codex-agent-fallback-targeted-schedule-00032`, label `pass`, final `Properties/SUCCESS`
- line 40, sample_id `codex-agent-fallback-targeted-schedule-00039`, label `fail`, final `Get/INVALID_PARAMETER`
- line 13, sample_id `codex-agent-fallback-targeted-schedule-00012`, label `pass`, final `Authenticate/SUCCESS`
- line 4, sample_id `codex-agent-fallback-targeted-schedule-00003`, label `fail`, final `StartSession/NOT_AUTHORIZED`
- line 27, sample_id `codex-agent-fallback-targeted-schedule-00026`, label `pass`, final `Get/SUCCESS`
- line 32, sample_id `codex-agent-fallback-targeted-schedule-00031`, label `fail`, final `Activate/NOT_AUTHORIZED`
- line 25, sample_id `codex-agent-fallback-targeted-schedule-00024`, label `pass`, final `Get/SUCCESS`
- line 34, sample_id `codex-agent-fallback-targeted-schedule-00033`, label `fail`, final `RevertSP/FAIL`
- line 29, sample_id `codex-agent-fallback-targeted-schedule-00028`, label `pass`, final `Get/SUCCESS`
- line 18, sample_id `codex-agent-fallback-targeted-schedule-00017`, label `fail`, final `Set/NOT_AUTHORIZED`
- line 7, sample_id `codex-agent-fallback-targeted-schedule-00006`, label `pass`, final `Get/SUCCESS`
- line 36, sample_id `codex-agent-fallback-targeted-schedule-00035`, label `fail`, final `Set/INVALID_PARAMETER`
- line 11, sample_id `codex-agent-fallback-targeted-schedule-00010`, label `pass`, final `Authenticate/SUCCESS`
- line 10, sample_id `codex-agent-fallback-targeted-schedule-00009`, label `fail`, final `StartSession/NO_SESSIONS_AVAILABLE`
- line 23, sample_id `codex-agent-fallback-targeted-schedule-00022`, label `pass`, final `Get/SUCCESS`
- line 6, sample_id `codex-agent-fallback-targeted-schedule-00005`, label `fail`, final `StartSession/SP_BUSY`
- line 17, sample_id `codex-agent-fallback-targeted-schedule-00016`, label `pass`, final `Activate/SUCCESS`
- line 26, sample_id `codex-agent-fallback-targeted-schedule-00025`, label `fail`, final `Authenticate/INVALID_PARAMETER`
- line 9, sample_id `codex-agent-fallback-targeted-schedule-00008`, label `pass`, final `Set/SUCCESS`
- line 2, sample_id `codex-agent-fallback-targeted-schedule-00001`, label `fail`, final `Set/NOT_AUTHORIZED`
- line 3, sample_id `codex-agent-fallback-targeted-schedule-00002`, label `pass`, final `Get/SUCCESS`
- line 20, sample_id `codex-agent-fallback-targeted-schedule-00019`, label `fail`, final `Set/INVALID_PARAMETER`
- line 1, sample_id `codex-agent-fallback-targeted-schedule-00000`, label `pass`, final `Properties/SUCCESS`
- line 12, sample_id `codex-agent-fallback-targeted-schedule-00011`, label `fail`, final `StartSession/INVALID_PARAMETER`
