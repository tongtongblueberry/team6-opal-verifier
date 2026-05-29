# Gate A Qualitative State-Transition Audit Pack

이 pack은 사람이 또는 LLM judge가 records를 처음부터 끝까지 읽고 state transition을 직접 확인하기 위한 산출물이다.
자동 verdict를 확정하지 않으며, rule engine/runtime architecture/solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-27T18:20:07+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/official_restart_20260527_v1/02_raw_generation/dedup_candidates.codex_agent_fallback.jsonl`
- sample 수: 12

## Sample 1: codex-agent-fallback-self-instruct-gen-00000-02

- sample_id: `codex-agent-fallback-self-instruct-gen-00000-02`
- line_number: `2`
- label: `fail`
- record_count: 3
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 2: codex-agent-fallback-self-instruct-gen-00002-03

- sample_id: `codex-agent-fallback-self-instruct-gen-00002-03`
- line_number: `9`
- label: `pass`
- record_count: 2
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 3: codex-agent-fallback-self-instruct-gen-00001-03

- sample_id: `codex-agent-fallback-self-instruct-gen-00001-03`
- line_number: `6`
- label: `pass`
- record_count: 2
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Set` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 4: codex-agent-fallback-self-instruct-gen-00002-01

- sample_id: `codex-agent-fallback-self-instruct-gen-00002-01`
- line_number: `7`
- label: `pass`
- record_count: 2
- final method/status: `StartSession/INVALID_PARAMETER`
- method/status sequence: `0:Properties/SUCCESS -> 1:StartSession/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 2 |
| 1 | `StartSession` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 5: codex-agent-fallback-self-instruct-gen-00001-01

- sample_id: `codex-agent-fallback-self-instruct-gen-00001-01`
- line_number: `4`
- label: `pass`
- record_count: 1
- final method/status: `StartSession/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 6: codex-agent-fallback-self-instruct-gen-00000-03

- sample_id: `codex-agent-fallback-self-instruct-gen-00000-03`
- line_number: `3`
- label: `pass`
- record_count: 2
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:StartSession/SUCCESS -> 1:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `StartSession` | `SP_BUSY` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 7: codex-agent-fallback-self-instruct-gen-00003-03

- sample_id: `codex-agent-fallback-self-instruct-gen-00003-03`
- line_number: `12`
- label: `pass`
- record_count: 2
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 8: codex-agent-fallback-self-instruct-gen-00002-02

- sample_id: `codex-agent-fallback-self-instruct-gen-00002-02`
- line_number: `8`
- label: `fail`
- record_count: 2
- final method/status: `Get/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 9: codex-agent-fallback-self-instruct-gen-00003-01

- sample_id: `codex-agent-fallback-self-instruct-gen-00003-01`
- line_number: `10`
- label: `pass`
- record_count: 2
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 10: codex-agent-fallback-self-instruct-gen-00003-02

- sample_id: `codex-agent-fallback-self-instruct-gen-00003-02`
- line_number: `11`
- label: `fail`
- record_count: 2
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 11: codex-agent-fallback-self-instruct-gen-00000-01

- sample_id: `codex-agent-fallback-self-instruct-gen-00000-01`
- line_number: `1`
- label: `pass`
- record_count: 3
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 1 |
| 2 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 12: codex-agent-fallback-self-instruct-gen-00001-02

- sample_id: `codex-agent-fallback-self-instruct-gen-00001-02`
- line_number: `5`
- label: `fail`
- record_count: 2
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `StartSession` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale
