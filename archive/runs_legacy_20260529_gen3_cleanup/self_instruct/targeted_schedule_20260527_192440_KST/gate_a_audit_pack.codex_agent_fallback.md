# Gate A Qualitative State-Transition Audit Pack

이 pack은 사람이 또는 LLM judge가 records를 처음부터 끝까지 읽고 state transition을 직접 확인하기 위한 산출물이다.
자동 verdict를 확정하지 않으며, rule engine/runtime architecture/solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-27T20:43:10+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/targeted_schedule_20260527_192440_KST/judge_accepted.codex_agent_fallback.jsonl`
- sample 수: 40

## Sample 1: codex-agent-fallback-targeted-schedule-00027

- sample_id: `codex-agent-fallback-targeted-schedule-00027`
- line_number: `28`
- label: `fail`
- record_count: 20
- final method/status: `StartSession/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:StartSession/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `StartSession` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 2: codex-agent-fallback-targeted-schedule-00038

- sample_id: `codex-agent-fallback-targeted-schedule-00038`
- line_number: `39`
- label: `pass`
- record_count: 39
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Set/SUCCESS -> 24:StartSession/SUCCESS -> 25:Authenticate/SUCCESS -> 26:Get/SUCCESS -> 27:Set/SUCCESS -> 28:Get/SUCCESS -> 29:Authenticate/SUCCESS -> 30:Get/SUCCESS -> 31:Set/SUCCESS -> 32:StartSession/SUCCESS -> 33:Authenticate/SUCCESS -> 34:Get/SUCCESS -> 35:Set/SUCCESS -> 36:Get/SUCCESS -> 37:Authenticate/SUCCESS -> 38:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `StartSession` | `SUCCESS` | 2 |
| 25 | `Authenticate` | `SUCCESS` | 2 |
| 26 | `Get` | `SUCCESS` | 1 |
| 27 | `Set` | `SUCCESS` | 0 |
| 28 | `Get` | `SUCCESS` | 1 |
| 29 | `Authenticate` | `SUCCESS` | 2 |
| 30 | `Get` | `SUCCESS` | 1 |
| 31 | `Set` | `SUCCESS` | 0 |
| 32 | `StartSession` | `SUCCESS` | 2 |
| 33 | `Authenticate` | `SUCCESS` | 2 |
| 34 | `Get` | `SUCCESS` | 1 |
| 35 | `Set` | `SUCCESS` | 0 |
| 36 | `Get` | `SUCCESS` | 1 |
| 37 | `Authenticate` | `SUCCESS` | 2 |
| 38 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 3: codex-agent-fallback-targeted-schedule-00018

- sample_id: `codex-agent-fallback-targeted-schedule-00018`
- line_number: `19`
- label: `pass`
- record_count: 16
- final method/status: `Activate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Activate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Activate` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 4: codex-agent-fallback-targeted-schedule-00029

- sample_id: `codex-agent-fallback-targeted-schedule-00029`
- line_number: `30`
- label: `fail`
- record_count: 20
- final method/status: `Activate/FAIL`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Activate/FAIL`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Activate` | `FAIL` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 5: codex-agent-fallback-targeted-schedule-00004

- sample_id: `codex-agent-fallback-targeted-schedule-00004`
- line_number: `5`
- label: `pass`
- record_count: 5
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 6: codex-agent-fallback-targeted-schedule-00021

- sample_id: `codex-agent-fallback-targeted-schedule-00021`
- line_number: `22`
- label: `fail`
- record_count: 17
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 7: codex-agent-fallback-targeted-schedule-00020

- sample_id: `codex-agent-fallback-targeted-schedule-00020`
- line_number: `21`
- label: `pass`
- record_count: 17
- final method/status: `Revert/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:Revert/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `Revert` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 8: codex-agent-fallback-targeted-schedule-00007

- sample_id: `codex-agent-fallback-targeted-schedule-00007`
- line_number: `8`
- label: `fail`
- record_count: 7
- final method/status: `StartSession/SP_FROZEN`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:StartSession/SP_FROZEN`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SP_FROZEN` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 9: codex-agent-fallback-targeted-schedule-00034

- sample_id: `codex-agent-fallback-targeted-schedule-00034`
- line_number: `35`
- label: `pass`
- record_count: 25
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Set/SUCCESS -> 24:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `Properties` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 10: codex-agent-fallback-targeted-schedule-00023

- sample_id: `codex-agent-fallback-targeted-schedule-00023`
- line_number: `24`
- label: `fail`
- record_count: 18
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 11: codex-agent-fallback-targeted-schedule-00036

- sample_id: `codex-agent-fallback-targeted-schedule-00036`
- line_number: `37`
- label: `pass`
- record_count: 28
- final method/status: `Next/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Set/SUCCESS -> 24:StartSession/SUCCESS -> 25:Authenticate/SUCCESS -> 26:Get/SUCCESS -> 27:Next/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `StartSession` | `SUCCESS` | 2 |
| 25 | `Authenticate` | `SUCCESS` | 2 |
| 26 | `Get` | `SUCCESS` | 1 |
| 27 | `Next` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 12: codex-agent-fallback-targeted-schedule-00015

- sample_id: `codex-agent-fallback-targeted-schedule-00015`
- line_number: `16`
- label: `fail`
- record_count: 15
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 13: codex-agent-fallback-targeted-schedule-00014

- sample_id: `codex-agent-fallback-targeted-schedule-00014`
- line_number: `15`
- label: `pass`
- record_count: 15
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:StartSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `StartSession` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 14: codex-agent-fallback-targeted-schedule-00037

- sample_id: `codex-agent-fallback-targeted-schedule-00037`
- line_number: `38`
- label: `fail`
- record_count: 28
- final method/status: `Random/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Set/SUCCESS -> 24:StartSession/SUCCESS -> 25:Authenticate/SUCCESS -> 26:Get/SUCCESS -> 27:Random/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `StartSession` | `SUCCESS` | 2 |
| 25 | `Authenticate` | `SUCCESS` | 2 |
| 26 | `Get` | `SUCCESS` | 1 |
| 27 | `Random` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 15: codex-agent-fallback-targeted-schedule-00030

- sample_id: `codex-agent-fallback-targeted-schedule-00030`
- line_number: `31`
- label: `pass`
- record_count: 22
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Properties` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 16: codex-agent-fallback-targeted-schedule-00013

- sample_id: `codex-agent-fallback-targeted-schedule-00013`
- line_number: `14`
- label: `fail`
- record_count: 13
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 17: codex-agent-fallback-targeted-schedule-00032

- sample_id: `codex-agent-fallback-targeted-schedule-00032`
- line_number: `33`
- label: `pass`
- record_count: 24
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Properties` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 18: codex-agent-fallback-targeted-schedule-00039

- sample_id: `codex-agent-fallback-targeted-schedule-00039`
- line_number: `40`
- label: `fail`
- record_count: 39
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Set/SUCCESS -> 24:StartSession/SUCCESS -> 25:Authenticate/SUCCESS -> 26:Get/SUCCESS -> 27:Set/SUCCESS -> 28:Get/SUCCESS -> 29:Authenticate/SUCCESS -> 30:Get/SUCCESS -> 31:Set/SUCCESS -> 32:StartSession/SUCCESS -> 33:Authenticate/SUCCESS -> 34:Get/SUCCESS -> 35:Set/SUCCESS -> 36:Get/SUCCESS -> 37:Authenticate/SUCCESS -> 38:Get/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `StartSession` | `SUCCESS` | 2 |
| 25 | `Authenticate` | `SUCCESS` | 2 |
| 26 | `Get` | `SUCCESS` | 1 |
| 27 | `Set` | `SUCCESS` | 0 |
| 28 | `Get` | `SUCCESS` | 1 |
| 29 | `Authenticate` | `SUCCESS` | 2 |
| 30 | `Get` | `SUCCESS` | 1 |
| 31 | `Set` | `SUCCESS` | 0 |
| 32 | `StartSession` | `SUCCESS` | 2 |
| 33 | `Authenticate` | `SUCCESS` | 2 |
| 34 | `Get` | `SUCCESS` | 1 |
| 35 | `Set` | `SUCCESS` | 0 |
| 36 | `Get` | `SUCCESS` | 1 |
| 37 | `Authenticate` | `SUCCESS` | 2 |
| 38 | `Get` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 19: codex-agent-fallback-targeted-schedule-00012

- sample_id: `codex-agent-fallback-targeted-schedule-00012`
- line_number: `13`
- label: `pass`
- record_count: 13
- final method/status: `Authenticate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Authenticate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Authenticate` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 20: codex-agent-fallback-targeted-schedule-00003

- sample_id: `codex-agent-fallback-targeted-schedule-00003`
- line_number: `4`
- label: `fail`
- record_count: 3
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `StartSession` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 21: codex-agent-fallback-targeted-schedule-00026

- sample_id: `codex-agent-fallback-targeted-schedule-00026`
- line_number: `27`
- label: `pass`
- record_count: 20
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 22: codex-agent-fallback-targeted-schedule-00031

- sample_id: `codex-agent-fallback-targeted-schedule-00031`
- line_number: `32`
- label: `fail`
- record_count: 22
- final method/status: `Activate/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Activate/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Activate` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 23: codex-agent-fallback-targeted-schedule-00024

- sample_id: `codex-agent-fallback-targeted-schedule-00024`
- line_number: `25`
- label: `pass`
- record_count: 19
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 24: codex-agent-fallback-targeted-schedule-00033

- sample_id: `codex-agent-fallback-targeted-schedule-00033`
- line_number: `34`
- label: `fail`
- record_count: 24
- final method/status: `RevertSP/FAIL`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:RevertSP/FAIL`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `RevertSP` | `FAIL` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 25: codex-agent-fallback-targeted-schedule-00028

- sample_id: `codex-agent-fallback-targeted-schedule-00028`
- line_number: `29`
- label: `pass`
- record_count: 20
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 26: codex-agent-fallback-targeted-schedule-00017

- sample_id: `codex-agent-fallback-targeted-schedule-00017`
- line_number: `18`
- label: `fail`
- record_count: 16
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 27: codex-agent-fallback-targeted-schedule-00006

- sample_id: `codex-agent-fallback-targeted-schedule-00006`
- line_number: `7`
- label: `pass`
- record_count: 7
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 28: codex-agent-fallback-targeted-schedule-00035

- sample_id: `codex-agent-fallback-targeted-schedule-00035`
- line_number: `36`
- label: `fail`
- record_count: 25
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Get/SUCCESS -> 19:Set/SUCCESS -> 20:Get/SUCCESS -> 21:Authenticate/SUCCESS -> 22:Get/SUCCESS -> 23:Set/SUCCESS -> 24:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Get` | `SUCCESS` | 1 |
| 19 | `Set` | `SUCCESS` | 0 |
| 20 | `Get` | `SUCCESS` | 1 |
| 21 | `Authenticate` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 29: codex-agent-fallback-targeted-schedule-00010

- sample_id: `codex-agent-fallback-targeted-schedule-00010`
- line_number: `11`
- label: `pass`
- record_count: 11
- final method/status: `Authenticate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Authenticate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Authenticate` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 30: codex-agent-fallback-targeted-schedule-00009

- sample_id: `codex-agent-fallback-targeted-schedule-00009`
- line_number: `10`
- label: `fail`
- record_count: 9
- final method/status: `StartSession/NO_SESSIONS_AVAILABLE`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/NO_SESSIONS_AVAILABLE`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `NO_SESSIONS_AVAILABLE` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 31: codex-agent-fallback-targeted-schedule-00022

- sample_id: `codex-agent-fallback-targeted-schedule-00022`
- line_number: `23`
- label: `pass`
- record_count: 18
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 32: codex-agent-fallback-targeted-schedule-00005

- sample_id: `codex-agent-fallback-targeted-schedule-00005`
- line_number: `6`
- label: `fail`
- record_count: 5
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `StartSession` | `SP_BUSY` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 33: codex-agent-fallback-targeted-schedule-00016

- sample_id: `codex-agent-fallback-targeted-schedule-00016`
- line_number: `17`
- label: `pass`
- record_count: 16
- final method/status: `Activate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Activate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Activate` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 34: codex-agent-fallback-targeted-schedule-00025

- sample_id: `codex-agent-fallback-targeted-schedule-00025`
- line_number: `26`
- label: `fail`
- record_count: 19
- final method/status: `Authenticate/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/SUCCESS -> 16:StartSession/SUCCESS -> 17:Authenticate/SUCCESS -> 18:Authenticate/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 2 |
| 17 | `Authenticate` | `SUCCESS` | 2 |
| 18 | `Authenticate` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 35: codex-agent-fallback-targeted-schedule-00008

- sample_id: `codex-agent-fallback-targeted-schedule-00008`
- line_number: `9`
- label: `pass`
- record_count: 9
- final method/status: `Set/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:Set/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `Set` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 36: codex-agent-fallback-targeted-schedule-00001

- sample_id: `codex-agent-fallback-targeted-schedule-00001`
- line_number: `2`
- label: `fail`
- record_count: 1
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Set` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 37: codex-agent-fallback-targeted-schedule-00002

- sample_id: `codex-agent-fallback-targeted-schedule-00002`
- line_number: `3`
- label: `pass`
- record_count: 3
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 38: codex-agent-fallback-targeted-schedule-00019

- sample_id: `codex-agent-fallback-targeted-schedule-00019`
- line_number: `20`
- label: `fail`
- record_count: 16
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:Get/SUCCESS -> 11:Set/SUCCESS -> 12:Get/SUCCESS -> 13:Authenticate/SUCCESS -> 14:Get/SUCCESS -> 15:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `Set` | `SUCCESS` | 0 |
| 12 | `Get` | `SUCCESS` | 1 |
| 13 | `Authenticate` | `SUCCESS` | 2 |
| 14 | `Get` | `SUCCESS` | 1 |
| 15 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 39: codex-agent-fallback-targeted-schedule-00000

- sample_id: `codex-agent-fallback-targeted-schedule-00000`
- line_number: `1`
- label: `pass`
- record_count: 1
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 40: codex-agent-fallback-targeted-schedule-00011

- sample_id: `codex-agent-fallback-targeted-schedule-00011`
- line_number: `12`
- label: `fail`
- record_count: 11
- final method/status: `StartSession/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Authenticate/SUCCESS -> 2:Get/SUCCESS -> 3:Set/SUCCESS -> 4:Get/SUCCESS -> 5:Authenticate/SUCCESS -> 6:Get/SUCCESS -> 7:Set/SUCCESS -> 8:StartSession/SUCCESS -> 9:Authenticate/SUCCESS -> 10:StartSession/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Authenticate` | `SUCCESS` | 2 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Authenticate` | `SUCCESS` | 2 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `StartSession` | `SUCCESS` | 2 |
| 9 | `Authenticate` | `SUCCESS` | 2 |
| 10 | `StartSession` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale
