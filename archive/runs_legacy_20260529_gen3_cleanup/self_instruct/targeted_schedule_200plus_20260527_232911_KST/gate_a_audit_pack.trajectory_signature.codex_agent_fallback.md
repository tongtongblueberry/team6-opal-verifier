# Gate A Qualitative State-Transition Audit Pack

이 pack은 사람이 또는 LLM judge가 records를 처음부터 끝까지 읽고 state transition을 직접 확인하기 위한 산출물이다.
자동 verdict를 확정하지 않으며, rule engine/runtime architecture/solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-27T23:39:10+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST/judge_accepted.trajectory_signature.codex_agent_fallback.jsonl`
- sample 수: 25

## Sample 1: codex-agent-fallback-targeted-schedule-200plus-00007

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00007`
- line_number: `8`
- label: `fail`
- record_count: 7
- final method/status: `StartSession/SP_FROZEN`
- method/status sequence: `0:Authenticate/SUCCESS -> 1:Get/SUCCESS -> 2:Set/SUCCESS -> 3:Properties/SUCCESS -> 4:Activate/SUCCESS -> 5:Revert/SUCCESS -> 6:StartSession/SP_FROZEN`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Authenticate` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 2 |
| 2 | `Set` | `SUCCESS` | 2 |
| 3 | `Properties` | `SUCCESS` | 2 |
| 4 | `Activate` | `SUCCESS` | 2 |
| 5 | `Revert` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SP_FROZEN` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 2: codex-agent-fallback-targeted-schedule-200plus-00014

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00014`
- line_number: `15`
- label: `pass`
- record_count: 15
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:Get/SUCCESS -> 1:Set/SUCCESS -> 2:Properties/SUCCESS -> 3:Activate/SUCCESS -> 4:Revert/SUCCESS -> 5:Random/SUCCESS -> 6:Next/SUCCESS -> 7:EndSession/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Properties/SUCCESS -> 13:Activate/SUCCESS -> 14:StartSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Get` | `SUCCESS` | 2 |
| 1 | `Set` | `SUCCESS` | 2 |
| 2 | `Properties` | `SUCCESS` | 2 |
| 3 | `Activate` | `SUCCESS` | 2 |
| 4 | `Revert` | `SUCCESS` | 2 |
| 5 | `Random` | `SUCCESS` | 2 |
| 6 | `Next` | `SUCCESS` | 2 |
| 7 | `EndSession` | `SUCCESS` | 2 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 2 |
| 11 | `Set` | `SUCCESS` | 2 |
| 12 | `Properties` | `SUCCESS` | 2 |
| 13 | `Activate` | `SUCCESS` | 2 |
| 14 | `StartSession` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 3: codex-agent-fallback-targeted-schedule-200plus-00009

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00009`
- line_number: `10`
- label: `fail`
- record_count: 9
- final method/status: `StartSession/NO_SESSIONS_AVAILABLE`
- method/status sequence: `0:Random/SUCCESS -> 1:Next/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Authenticate/SUCCESS -> 5:Get/SUCCESS -> 6:Set/SUCCESS -> 7:Properties/SUCCESS -> 8:StartSession/NO_SESSIONS_AVAILABLE`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Random` | `SUCCESS` | 2 |
| 1 | `Next` | `SUCCESS` | 2 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Authenticate` | `SUCCESS` | 2 |
| 5 | `Get` | `SUCCESS` | 2 |
| 6 | `Set` | `SUCCESS` | 2 |
| 7 | `Properties` | `SUCCESS` | 2 |
| 8 | `StartSession` | `NO_SESSIONS_AVAILABLE` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 4: codex-agent-fallback-targeted-schedule-200plus-00030

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00030`
- line_number: `21`
- label: `pass`
- record_count: 22
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Properties/SUCCESS -> 5:Activate/SUCCESS -> 6:Revert/SUCCESS -> 7:Random/SUCCESS -> 8:Next/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Authenticate/SUCCESS -> 12:Get/SUCCESS -> 13:Set/SUCCESS -> 14:Properties/SUCCESS -> 15:Activate/SUCCESS -> 16:Revert/SUCCESS -> 17:Random/SUCCESS -> 18:Next/SUCCESS -> 19:EndSession/SUCCESS -> 20:StartSession/SUCCESS -> 21:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 2 |
| 3 | `Set` | `SUCCESS` | 2 |
| 4 | `Properties` | `SUCCESS` | 2 |
| 5 | `Activate` | `SUCCESS` | 2 |
| 6 | `Revert` | `SUCCESS` | 2 |
| 7 | `Random` | `SUCCESS` | 2 |
| 8 | `Next` | `SUCCESS` | 2 |
| 9 | `EndSession` | `SUCCESS` | 2 |
| 10 | `StartSession` | `SUCCESS` | 2 |
| 11 | `Authenticate` | `SUCCESS` | 2 |
| 12 | `Get` | `SUCCESS` | 2 |
| 13 | `Set` | `SUCCESS` | 2 |
| 14 | `Properties` | `SUCCESS` | 2 |
| 15 | `Activate` | `SUCCESS` | 2 |
| 16 | `Revert` | `SUCCESS` | 2 |
| 17 | `Random` | `SUCCESS` | 2 |
| 18 | `Next` | `SUCCESS` | 2 |
| 19 | `EndSession` | `SUCCESS` | 2 |
| 20 | `StartSession` | `SUCCESS` | 2 |
| 21 | `Properties` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 5: codex-agent-fallback-targeted-schedule-200plus-00001

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00001`
- line_number: `2`
- label: `fail`
- record_count: 1
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Set` | `NOT_AUTHORIZED` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 6: codex-agent-fallback-targeted-schedule-200plus-00006

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00006`
- line_number: `7`
- label: `pass`
- record_count: 7
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:Next/SUCCESS -> 1:EndSession/SUCCESS -> 2:StartSession/SUCCESS -> 3:Authenticate/SUCCESS -> 4:Get/SUCCESS -> 5:Set/SUCCESS -> 6:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Next` | `SUCCESS` | 2 |
| 1 | `EndSession` | `SUCCESS` | 2 |
| 2 | `StartSession` | `SUCCESS` | 2 |
| 3 | `Authenticate` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 2 |
| 5 | `Set` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 7: codex-agent-fallback-targeted-schedule-200plus-00039

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00039`
- line_number: `25`
- label: `fail`
- record_count: 39
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:Random/SUCCESS -> 1:Next/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Authenticate/SUCCESS -> 5:Get/SUCCESS -> 6:Set/SUCCESS -> 7:Properties/SUCCESS -> 8:Activate/SUCCESS -> 9:Revert/SUCCESS -> 10:Random/SUCCESS -> 11:Next/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Authenticate/SUCCESS -> 15:Get/SUCCESS -> 16:Set/SUCCESS -> 17:Properties/SUCCESS -> 18:Activate/SUCCESS -> 19:Revert/SUCCESS -> 20:Random/SUCCESS -> 21:Next/SUCCESS -> 22:EndSession/SUCCESS -> 23:StartSession/SUCCESS -> 24:Authenticate/SUCCESS -> 25:Get/SUCCESS -> 26:Set/SUCCESS -> 27:Properties/SUCCESS -> 28:Activate/SUCCESS -> 29:Revert/SUCCESS -> 30:Random/SUCCESS -> 31:Next/SUCCESS -> 32:EndSession/SUCCESS -> 33:StartSession/SUCCESS -> 34:Authenticate/SUCCESS -> 35:Get/SUCCESS -> 36:Set/SUCCESS -> 37:Properties/SUCCESS -> 38:Get/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Random` | `SUCCESS` | 2 |
| 1 | `Next` | `SUCCESS` | 2 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Authenticate` | `SUCCESS` | 2 |
| 5 | `Get` | `SUCCESS` | 2 |
| 6 | `Set` | `SUCCESS` | 2 |
| 7 | `Properties` | `SUCCESS` | 2 |
| 8 | `Activate` | `SUCCESS` | 2 |
| 9 | `Revert` | `SUCCESS` | 2 |
| 10 | `Random` | `SUCCESS` | 2 |
| 11 | `Next` | `SUCCESS` | 2 |
| 12 | `EndSession` | `SUCCESS` | 2 |
| 13 | `StartSession` | `SUCCESS` | 2 |
| 14 | `Authenticate` | `SUCCESS` | 2 |
| 15 | `Get` | `SUCCESS` | 2 |
| 16 | `Set` | `SUCCESS` | 2 |
| 17 | `Properties` | `SUCCESS` | 2 |
| 18 | `Activate` | `SUCCESS` | 2 |
| 19 | `Revert` | `SUCCESS` | 2 |
| 20 | `Random` | `SUCCESS` | 2 |
| 21 | `Next` | `SUCCESS` | 2 |
| 22 | `EndSession` | `SUCCESS` | 2 |
| 23 | `StartSession` | `SUCCESS` | 2 |
| 24 | `Authenticate` | `SUCCESS` | 2 |
| 25 | `Get` | `SUCCESS` | 2 |
| 26 | `Set` | `SUCCESS` | 2 |
| 27 | `Properties` | `SUCCESS` | 2 |
| 28 | `Activate` | `SUCCESS` | 2 |
| 29 | `Revert` | `SUCCESS` | 2 |
| 30 | `Random` | `SUCCESS` | 2 |
| 31 | `Next` | `SUCCESS` | 2 |
| 32 | `EndSession` | `SUCCESS` | 2 |
| 33 | `StartSession` | `SUCCESS` | 2 |
| 34 | `Authenticate` | `SUCCESS` | 2 |
| 35 | `Get` | `SUCCESS` | 2 |
| 36 | `Set` | `SUCCESS` | 2 |
| 37 | `Properties` | `SUCCESS` | 2 |
| 38 | `Get` | `INVALID_PARAMETER` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 8: codex-agent-fallback-targeted-schedule-200plus-00016

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00016`
- line_number: `17`
- label: `pass`
- record_count: 16
- final method/status: `Activate/SUCCESS`
- method/status sequence: `0:Next/SUCCESS -> 1:EndSession/SUCCESS -> 2:StartSession/SUCCESS -> 3:Authenticate/SUCCESS -> 4:Get/SUCCESS -> 5:Set/SUCCESS -> 6:Properties/SUCCESS -> 7:Activate/SUCCESS -> 8:Revert/SUCCESS -> 9:Random/SUCCESS -> 10:Next/SUCCESS -> 11:EndSession/SUCCESS -> 12:StartSession/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Activate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Next` | `SUCCESS` | 2 |
| 1 | `EndSession` | `SUCCESS` | 2 |
| 2 | `StartSession` | `SUCCESS` | 2 |
| 3 | `Authenticate` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 2 |
| 5 | `Set` | `SUCCESS` | 2 |
| 6 | `Properties` | `SUCCESS` | 2 |
| 7 | `Activate` | `SUCCESS` | 2 |
| 8 | `Revert` | `SUCCESS` | 2 |
| 9 | `Random` | `SUCCESS` | 2 |
| 10 | `Next` | `SUCCESS` | 2 |
| 11 | `EndSession` | `SUCCESS` | 2 |
| 12 | `StartSession` | `SUCCESS` | 2 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 2 |
| 15 | `Activate` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 9: codex-agent-fallback-targeted-schedule-200plus-00003

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00003`
- line_number: `4`
- label: `fail`
- record_count: 3
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:EndSession/SUCCESS -> 1:StartSession/SUCCESS -> 2:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `EndSession` | `SUCCESS` | 2 |
| 1 | `StartSession` | `SUCCESS` | 2 |
| 2 | `StartSession` | `NOT_AUTHORIZED` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 10: codex-agent-fallback-targeted-schedule-200plus-00012

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00012`
- line_number: `13`
- label: `pass`
- record_count: 13
- final method/status: `Authenticate/SUCCESS`
- method/status sequence: `0:Revert/SUCCESS -> 1:Random/SUCCESS -> 2:Next/SUCCESS -> 3:EndSession/SUCCESS -> 4:StartSession/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:Properties/SUCCESS -> 9:Activate/SUCCESS -> 10:Revert/SUCCESS -> 11:Random/SUCCESS -> 12:Authenticate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Revert` | `SUCCESS` | 2 |
| 1 | `Random` | `SUCCESS` | 2 |
| 2 | `Next` | `SUCCESS` | 2 |
| 3 | `EndSession` | `SUCCESS` | 2 |
| 4 | `StartSession` | `SUCCESS` | 2 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 2 |
| 7 | `Set` | `SUCCESS` | 2 |
| 8 | `Properties` | `SUCCESS` | 2 |
| 9 | `Activate` | `SUCCESS` | 2 |
| 10 | `Revert` | `SUCCESS` | 2 |
| 11 | `Random` | `SUCCESS` | 2 |
| 12 | `Authenticate` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 11: codex-agent-fallback-targeted-schedule-200plus-00031

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00031`
- line_number: `22`
- label: `fail`
- record_count: 22
- final method/status: `Activate/NOT_AUTHORIZED`
- method/status sequence: `0:Set/SUCCESS -> 1:Properties/SUCCESS -> 2:Activate/SUCCESS -> 3:Revert/SUCCESS -> 4:Random/SUCCESS -> 5:Next/SUCCESS -> 6:EndSession/SUCCESS -> 7:StartSession/SUCCESS -> 8:Authenticate/SUCCESS -> 9:Get/SUCCESS -> 10:Set/SUCCESS -> 11:Properties/SUCCESS -> 12:Activate/SUCCESS -> 13:Revert/SUCCESS -> 14:Random/SUCCESS -> 15:Next/SUCCESS -> 16:EndSession/SUCCESS -> 17:StartSession/SUCCESS -> 18:Authenticate/SUCCESS -> 19:Get/SUCCESS -> 20:Set/SUCCESS -> 21:Activate/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Set` | `SUCCESS` | 2 |
| 1 | `Properties` | `SUCCESS` | 2 |
| 2 | `Activate` | `SUCCESS` | 2 |
| 3 | `Revert` | `SUCCESS` | 2 |
| 4 | `Random` | `SUCCESS` | 2 |
| 5 | `Next` | `SUCCESS` | 2 |
| 6 | `EndSession` | `SUCCESS` | 2 |
| 7 | `StartSession` | `SUCCESS` | 2 |
| 8 | `Authenticate` | `SUCCESS` | 2 |
| 9 | `Get` | `SUCCESS` | 2 |
| 10 | `Set` | `SUCCESS` | 2 |
| 11 | `Properties` | `SUCCESS` | 2 |
| 12 | `Activate` | `SUCCESS` | 2 |
| 13 | `Revert` | `SUCCESS` | 2 |
| 14 | `Random` | `SUCCESS` | 2 |
| 15 | `Next` | `SUCCESS` | 2 |
| 16 | `EndSession` | `SUCCESS` | 2 |
| 17 | `StartSession` | `SUCCESS` | 2 |
| 18 | `Authenticate` | `SUCCESS` | 2 |
| 19 | `Get` | `SUCCESS` | 2 |
| 20 | `Set` | `SUCCESS` | 2 |
| 21 | `Activate` | `NOT_AUTHORIZED` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 12: codex-agent-fallback-targeted-schedule-200plus-00002

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00002`
- line_number: `3`
- label: `pass`
- record_count: 3
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:Revert/SUCCESS -> 1:Random/SUCCESS -> 2:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Revert` | `SUCCESS` | 2 |
| 1 | `Random` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 13: codex-agent-fallback-targeted-schedule-200plus-00019

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00019`
- line_number: `19`
- label: `fail`
- record_count: 16
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:Random/SUCCESS -> 1:Next/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Authenticate/SUCCESS -> 5:Get/SUCCESS -> 6:Set/SUCCESS -> 7:Properties/SUCCESS -> 8:Activate/SUCCESS -> 9:Revert/SUCCESS -> 10:Random/SUCCESS -> 11:Next/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Authenticate/SUCCESS -> 15:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Random` | `SUCCESS` | 2 |
| 1 | `Next` | `SUCCESS` | 2 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Authenticate` | `SUCCESS` | 2 |
| 5 | `Get` | `SUCCESS` | 2 |
| 6 | `Set` | `SUCCESS` | 2 |
| 7 | `Properties` | `SUCCESS` | 2 |
| 8 | `Activate` | `SUCCESS` | 2 |
| 9 | `Revert` | `SUCCESS` | 2 |
| 10 | `Random` | `SUCCESS` | 2 |
| 11 | `Next` | `SUCCESS` | 2 |
| 12 | `EndSession` | `SUCCESS` | 2 |
| 13 | `StartSession` | `SUCCESS` | 2 |
| 14 | `Authenticate` | `SUCCESS` | 2 |
| 15 | `Set` | `INVALID_PARAMETER` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 14: codex-agent-fallback-targeted-schedule-200plus-00028

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00028`
- line_number: `20`
- label: `pass`
- record_count: 20
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS -> 1:Activate/SUCCESS -> 2:Revert/SUCCESS -> 3:Random/SUCCESS -> 4:Next/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Authenticate/SUCCESS -> 8:Get/SUCCESS -> 9:Set/SUCCESS -> 10:Properties/SUCCESS -> 11:Activate/SUCCESS -> 12:Revert/SUCCESS -> 13:Random/SUCCESS -> 14:Next/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 2 |
| 1 | `Activate` | `SUCCESS` | 2 |
| 2 | `Revert` | `SUCCESS` | 2 |
| 3 | `Random` | `SUCCESS` | 2 |
| 4 | `Next` | `SUCCESS` | 2 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Authenticate` | `SUCCESS` | 2 |
| 8 | `Get` | `SUCCESS` | 2 |
| 9 | `Set` | `SUCCESS` | 2 |
| 10 | `Properties` | `SUCCESS` | 2 |
| 11 | `Activate` | `SUCCESS` | 2 |
| 12 | `Revert` | `SUCCESS` | 2 |
| 13 | `Random` | `SUCCESS` | 2 |
| 14 | `Next` | `SUCCESS` | 2 |
| 15 | `EndSession` | `SUCCESS` | 2 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 2 |
| 19 | `Get` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 15: codex-agent-fallback-targeted-schedule-200plus-00015

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00015`
- line_number: `16`
- label: `fail`
- record_count: 15
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:Activate/SUCCESS -> 1:Revert/SUCCESS -> 2:Random/SUCCESS -> 3:Next/SUCCESS -> 4:EndSession/SUCCESS -> 5:StartSession/SUCCESS -> 6:Authenticate/SUCCESS -> 7:Get/SUCCESS -> 8:Set/SUCCESS -> 9:Properties/SUCCESS -> 10:Activate/SUCCESS -> 11:Revert/SUCCESS -> 12:Random/SUCCESS -> 13:Next/SUCCESS -> 14:Get/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Activate` | `SUCCESS` | 2 |
| 1 | `Revert` | `SUCCESS` | 2 |
| 2 | `Random` | `SUCCESS` | 2 |
| 3 | `Next` | `SUCCESS` | 2 |
| 4 | `EndSession` | `SUCCESS` | 2 |
| 5 | `StartSession` | `SUCCESS` | 2 |
| 6 | `Authenticate` | `SUCCESS` | 2 |
| 7 | `Get` | `SUCCESS` | 2 |
| 8 | `Set` | `SUCCESS` | 2 |
| 9 | `Properties` | `SUCCESS` | 2 |
| 10 | `Activate` | `SUCCESS` | 2 |
| 11 | `Revert` | `SUCCESS` | 2 |
| 12 | `Random` | `SUCCESS` | 2 |
| 13 | `Next` | `SUCCESS` | 2 |
| 14 | `Get` | `INVALID_PARAMETER` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 16: codex-agent-fallback-targeted-schedule-200plus-00010

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00010`
- line_number: `11`
- label: `pass`
- record_count: 11
- final method/status: `Authenticate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Properties/SUCCESS -> 5:Activate/SUCCESS -> 6:Revert/SUCCESS -> 7:Random/SUCCESS -> 8:Next/SUCCESS -> 9:EndSession/SUCCESS -> 10:Authenticate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 2 |
| 3 | `Set` | `SUCCESS` | 2 |
| 4 | `Properties` | `SUCCESS` | 2 |
| 5 | `Activate` | `SUCCESS` | 2 |
| 6 | `Revert` | `SUCCESS` | 2 |
| 7 | `Random` | `SUCCESS` | 2 |
| 8 | `Next` | `SUCCESS` | 2 |
| 9 | `EndSession` | `SUCCESS` | 2 |
| 10 | `Authenticate` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 17: codex-agent-fallback-targeted-schedule-200plus-00005

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00005`
- line_number: `6`
- label: `fail`
- record_count: 5
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:Activate/SUCCESS -> 1:Revert/SUCCESS -> 2:Random/SUCCESS -> 3:Next/SUCCESS -> 4:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Activate` | `SUCCESS` | 2 |
| 1 | `Revert` | `SUCCESS` | 2 |
| 2 | `Random` | `SUCCESS` | 2 |
| 3 | `Next` | `SUCCESS` | 2 |
| 4 | `StartSession` | `SP_BUSY` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 18: codex-agent-fallback-targeted-schedule-200plus-00008

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00008`
- line_number: `9`
- label: `pass`
- record_count: 9
- final method/status: `Set/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS -> 1:Activate/SUCCESS -> 2:Revert/SUCCESS -> 3:Random/SUCCESS -> 4:Next/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Authenticate/SUCCESS -> 8:Set/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 2 |
| 1 | `Activate` | `SUCCESS` | 2 |
| 2 | `Revert` | `SUCCESS` | 2 |
| 3 | `Random` | `SUCCESS` | 2 |
| 4 | `Next` | `SUCCESS` | 2 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Authenticate` | `SUCCESS` | 2 |
| 8 | `Set` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 19: codex-agent-fallback-targeted-schedule-200plus-00011

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00011`
- line_number: `12`
- label: `fail`
- record_count: 11
- final method/status: `StartSession/INVALID_PARAMETER`
- method/status sequence: `0:Set/SUCCESS -> 1:Properties/SUCCESS -> 2:Activate/SUCCESS -> 3:Revert/SUCCESS -> 4:Random/SUCCESS -> 5:Next/SUCCESS -> 6:EndSession/SUCCESS -> 7:StartSession/SUCCESS -> 8:Authenticate/SUCCESS -> 9:Get/SUCCESS -> 10:StartSession/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Set` | `SUCCESS` | 2 |
| 1 | `Properties` | `SUCCESS` | 2 |
| 2 | `Activate` | `SUCCESS` | 2 |
| 3 | `Revert` | `SUCCESS` | 2 |
| 4 | `Random` | `SUCCESS` | 2 |
| 5 | `Next` | `SUCCESS` | 2 |
| 6 | `EndSession` | `SUCCESS` | 2 |
| 7 | `StartSession` | `SUCCESS` | 2 |
| 8 | `Authenticate` | `SUCCESS` | 2 |
| 9 | `Get` | `SUCCESS` | 2 |
| 10 | `StartSession` | `INVALID_PARAMETER` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 20: codex-agent-fallback-targeted-schedule-200plus-00004

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00004`
- line_number: `5`
- label: `pass`
- record_count: 5
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:Get/SUCCESS -> 1:Set/SUCCESS -> 2:Properties/SUCCESS -> 3:Activate/SUCCESS -> 4:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Get` | `SUCCESS` | 2 |
| 1 | `Set` | `SUCCESS` | 2 |
| 2 | `Properties` | `SUCCESS` | 2 |
| 3 | `Activate` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 21: codex-agent-fallback-targeted-schedule-200plus-00033

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00033`
- line_number: `23`
- label: `fail`
- record_count: 24
- final method/status: `RevertSP/FAIL`
- method/status sequence: `0:EndSession/SUCCESS -> 1:StartSession/SUCCESS -> 2:Authenticate/SUCCESS -> 3:Get/SUCCESS -> 4:Set/SUCCESS -> 5:Properties/SUCCESS -> 6:Activate/SUCCESS -> 7:Revert/SUCCESS -> 8:Random/SUCCESS -> 9:Next/SUCCESS -> 10:EndSession/SUCCESS -> 11:StartSession/SUCCESS -> 12:Authenticate/SUCCESS -> 13:Get/SUCCESS -> 14:Set/SUCCESS -> 15:Properties/SUCCESS -> 16:Activate/SUCCESS -> 17:Revert/SUCCESS -> 18:Random/SUCCESS -> 19:Next/SUCCESS -> 20:EndSession/SUCCESS -> 21:StartSession/SUCCESS -> 22:Authenticate/SUCCESS -> 23:RevertSP/FAIL`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `EndSession` | `SUCCESS` | 2 |
| 1 | `StartSession` | `SUCCESS` | 2 |
| 2 | `Authenticate` | `SUCCESS` | 2 |
| 3 | `Get` | `SUCCESS` | 2 |
| 4 | `Set` | `SUCCESS` | 2 |
| 5 | `Properties` | `SUCCESS` | 2 |
| 6 | `Activate` | `SUCCESS` | 2 |
| 7 | `Revert` | `SUCCESS` | 2 |
| 8 | `Random` | `SUCCESS` | 2 |
| 9 | `Next` | `SUCCESS` | 2 |
| 10 | `EndSession` | `SUCCESS` | 2 |
| 11 | `StartSession` | `SUCCESS` | 2 |
| 12 | `Authenticate` | `SUCCESS` | 2 |
| 13 | `Get` | `SUCCESS` | 2 |
| 14 | `Set` | `SUCCESS` | 2 |
| 15 | `Properties` | `SUCCESS` | 2 |
| 16 | `Activate` | `SUCCESS` | 2 |
| 17 | `Revert` | `SUCCESS` | 2 |
| 18 | `Random` | `SUCCESS` | 2 |
| 19 | `Next` | `SUCCESS` | 2 |
| 20 | `EndSession` | `SUCCESS` | 2 |
| 21 | `StartSession` | `SUCCESS` | 2 |
| 22 | `Authenticate` | `SUCCESS` | 2 |
| 23 | `RevertSP` | `FAIL` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 22: codex-agent-fallback-targeted-schedule-200plus-00038

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00038`
- line_number: `24`
- label: `pass`
- record_count: 39
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS -> 1:Activate/SUCCESS -> 2:Revert/SUCCESS -> 3:Random/SUCCESS -> 4:Next/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Authenticate/SUCCESS -> 8:Get/SUCCESS -> 9:Set/SUCCESS -> 10:Properties/SUCCESS -> 11:Activate/SUCCESS -> 12:Revert/SUCCESS -> 13:Random/SUCCESS -> 14:Next/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Properties/SUCCESS -> 21:Activate/SUCCESS -> 22:Revert/SUCCESS -> 23:Random/SUCCESS -> 24:Next/SUCCESS -> 25:EndSession/SUCCESS -> 26:StartSession/SUCCESS -> 27:Authenticate/SUCCESS -> 28:Get/SUCCESS -> 29:Set/SUCCESS -> 30:Properties/SUCCESS -> 31:Activate/SUCCESS -> 32:Revert/SUCCESS -> 33:Random/SUCCESS -> 34:Next/SUCCESS -> 35:EndSession/SUCCESS -> 36:StartSession/SUCCESS -> 37:Authenticate/SUCCESS -> 38:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 2 |
| 1 | `Activate` | `SUCCESS` | 2 |
| 2 | `Revert` | `SUCCESS` | 2 |
| 3 | `Random` | `SUCCESS` | 2 |
| 4 | `Next` | `SUCCESS` | 2 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Authenticate` | `SUCCESS` | 2 |
| 8 | `Get` | `SUCCESS` | 2 |
| 9 | `Set` | `SUCCESS` | 2 |
| 10 | `Properties` | `SUCCESS` | 2 |
| 11 | `Activate` | `SUCCESS` | 2 |
| 12 | `Revert` | `SUCCESS` | 2 |
| 13 | `Random` | `SUCCESS` | 2 |
| 14 | `Next` | `SUCCESS` | 2 |
| 15 | `EndSession` | `SUCCESS` | 2 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 2 |
| 19 | `Set` | `SUCCESS` | 2 |
| 20 | `Properties` | `SUCCESS` | 2 |
| 21 | `Activate` | `SUCCESS` | 2 |
| 22 | `Revert` | `SUCCESS` | 2 |
| 23 | `Random` | `SUCCESS` | 2 |
| 24 | `Next` | `SUCCESS` | 2 |
| 25 | `EndSession` | `SUCCESS` | 2 |
| 26 | `StartSession` | `SUCCESS` | 2 |
| 27 | `Authenticate` | `SUCCESS` | 2 |
| 28 | `Get` | `SUCCESS` | 2 |
| 29 | `Set` | `SUCCESS` | 2 |
| 30 | `Properties` | `SUCCESS` | 2 |
| 31 | `Activate` | `SUCCESS` | 2 |
| 32 | `Revert` | `SUCCESS` | 2 |
| 33 | `Random` | `SUCCESS` | 2 |
| 34 | `Next` | `SUCCESS` | 2 |
| 35 | `EndSession` | `SUCCESS` | 2 |
| 36 | `StartSession` | `SUCCESS` | 2 |
| 37 | `Authenticate` | `SUCCESS` | 2 |
| 38 | `Get` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 23: codex-agent-fallback-targeted-schedule-200plus-00017

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00017`
- line_number: `18`
- label: `fail`
- record_count: 16
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:Authenticate/SUCCESS -> 1:Get/SUCCESS -> 2:Set/SUCCESS -> 3:Properties/SUCCESS -> 4:Activate/SUCCESS -> 5:Revert/SUCCESS -> 6:Random/SUCCESS -> 7:Next/SUCCESS -> 8:EndSession/SUCCESS -> 9:StartSession/SUCCESS -> 10:Authenticate/SUCCESS -> 11:Get/SUCCESS -> 12:Set/SUCCESS -> 13:Properties/SUCCESS -> 14:Activate/SUCCESS -> 15:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Authenticate` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 2 |
| 2 | `Set` | `SUCCESS` | 2 |
| 3 | `Properties` | `SUCCESS` | 2 |
| 4 | `Activate` | `SUCCESS` | 2 |
| 5 | `Revert` | `SUCCESS` | 2 |
| 6 | `Random` | `SUCCESS` | 2 |
| 7 | `Next` | `SUCCESS` | 2 |
| 8 | `EndSession` | `SUCCESS` | 2 |
| 9 | `StartSession` | `SUCCESS` | 2 |
| 10 | `Authenticate` | `SUCCESS` | 2 |
| 11 | `Get` | `SUCCESS` | 2 |
| 12 | `Set` | `SUCCESS` | 2 |
| 13 | `Properties` | `SUCCESS` | 2 |
| 14 | `Activate` | `SUCCESS` | 2 |
| 15 | `Set` | `NOT_AUTHORIZED` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 24: codex-agent-fallback-targeted-schedule-200plus-00000

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00000`
- line_number: `1`
- label: `pass`
- record_count: 1
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 25: codex-agent-fallback-targeted-schedule-200plus-00013

- sample_id: `codex-agent-fallback-targeted-schedule-200plus-00013`
- line_number: `14`
- label: `fail`
- record_count: 13
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:EndSession/SUCCESS -> 1:StartSession/SUCCESS -> 2:Authenticate/SUCCESS -> 3:Get/SUCCESS -> 4:Set/SUCCESS -> 5:Properties/SUCCESS -> 6:Activate/SUCCESS -> 7:Revert/SUCCESS -> 8:Random/SUCCESS -> 9:Next/SUCCESS -> 10:EndSession/SUCCESS -> 11:StartSession/SUCCESS -> 12:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `EndSession` | `SUCCESS` | 2 |
| 1 | `StartSession` | `SUCCESS` | 2 |
| 2 | `Authenticate` | `SUCCESS` | 2 |
| 3 | `Get` | `SUCCESS` | 2 |
| 4 | `Set` | `SUCCESS` | 2 |
| 5 | `Properties` | `SUCCESS` | 2 |
| 6 | `Activate` | `SUCCESS` | 2 |
| 7 | `Revert` | `SUCCESS` | 2 |
| 8 | `Random` | `SUCCESS` | 2 |
| 9 | `Next` | `SUCCESS` | 2 |
| 10 | `EndSession` | `SUCCESS` | 2 |
| 11 | `StartSession` | `SUCCESS` | 2 |
| 12 | `Set` | `INVALID_PARAMETER` | 3 |

### state_trace

### observed_state_summary

### audit_decision

### rationale
