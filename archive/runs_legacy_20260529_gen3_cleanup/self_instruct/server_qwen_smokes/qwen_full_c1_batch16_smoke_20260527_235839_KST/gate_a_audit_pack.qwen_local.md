# Gate A Qualitative State-Transition Audit Pack

이 pack은 사람이 또는 LLM judge가 records를 처음부터 끝까지 읽고 state transition을 직접 확인하기 위한 산출물이다.
자동 verdict를 확정하지 않으며, rule engine/runtime architecture/solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-28T09:11:41+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/qwen_full_c1_batch16_smoke_20260527_235839_KST/judge_accepted_candidates.qwen_local.jsonl`
- sample 수: 5

## Sample 1: self-instruct-gen-00013-cand-00

- sample_id: `self-instruct-gen-00013-cand-00`
- line_number: `6`
- label: `fail`
- record_count: 10
- final method/status: `EndSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Set/SUCCESS -> 8:Authenticate/INVALID_PARAMETER -> 9:EndSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 0 |
| 1 | `Get` | `SUCCESS` | 0 |
| 2 | `EndSession` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 0 |
| 4 | `Set` | `SUCCESS` | 0 |
| 5 | `EndSession` | `SUCCESS` | 0 |
| 6 | `StartSession` | `SUCCESS` | 0 |
| 7 | `Set` | `SUCCESS` | 0 |
| 8 | `Authenticate` | `INVALID_PARAMETER` | 0 |
| 9 | `EndSession` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 2: self-instruct-gen-00012-cand-00

- sample_id: `self-instruct-gen-00012-cand-00`
- line_number: `5`
- label: `pass`
- record_count: 7
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 0 |
| 1 | `Get` | `SUCCESS` | 0 |
| 2 | `EndSession` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 0 |
| 4 | `Set` | `SUCCESS` | 0 |
| 5 | `EndSession` | `SUCCESS` | 0 |
| 6 | `StartSession` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 3: self-instruct-gen-00006-cand-00

- sample_id: `self-instruct-gen-00006-cand-00`
- line_number: `3`
- label: `pass`
- record_count: 26
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Set/SUCCESS -> 24:EndSession/SUCCESS -> 25:StartSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 0 |
| 1 | `Get` | `SUCCESS` | 0 |
| 2 | `EndSession` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 0 |
| 4 | `Set` | `SUCCESS` | 0 |
| 5 | `EndSession` | `SUCCESS` | 0 |
| 6 | `StartSession` | `SUCCESS` | 0 |
| 7 | `Get` | `SUCCESS` | 0 |
| 8 | `Activate` | `SUCCESS` | 0 |
| 9 | `EndSession` | `SUCCESS` | 0 |
| 10 | `StartSession` | `SUCCESS` | 0 |
| 11 | `Get` | `SUCCESS` | 0 |
| 12 | `EndSession` | `SUCCESS` | 0 |
| 13 | `StartSession` | `SUCCESS` | 0 |
| 14 | `Get` | `SUCCESS` | 0 |
| 15 | `EndSession` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 0 |
| 17 | `Get` | `SUCCESS` | 0 |
| 18 | `EndSession` | `SUCCESS` | 0 |
| 19 | `StartSession` | `SUCCESS` | 0 |
| 20 | `Set` | `SUCCESS` | 0 |
| 21 | `EndSession` | `SUCCESS` | 0 |
| 22 | `StartSession` | `SUCCESS` | 0 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `EndSession` | `SUCCESS` | 0 |
| 25 | `StartSession` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 4: self-instruct-gen-00014-cand-00

- sample_id: `self-instruct-gen-00014-cand-00`
- line_number: `7`
- label: `pass`
- record_count: 9
- final method/status: `Activate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 0 |
| 1 | `Get` | `SUCCESS` | 0 |
| 2 | `EndSession` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 0 |
| 4 | `Set` | `SUCCESS` | 0 |
| 5 | `EndSession` | `SUCCESS` | 0 |
| 6 | `StartSession` | `SUCCESS` | 0 |
| 7 | `Get` | `SUCCESS` | 0 |
| 8 | `Activate` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 5: self-instruct-gen-00016-cand-00

- sample_id: `self-instruct-gen-00016-cand-00`
- line_number: `8`
- label: `pass`
- record_count: 26
- final method/status: `EndSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Set/SUCCESS -> 24:EndSession/SUCCESS -> 25:EndSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 0 |
| 1 | `Get` | `SUCCESS` | 2 |
| 2 | `EndSession` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 0 |
| 4 | `Set` | `SUCCESS` | 0 |
| 5 | `EndSession` | `SUCCESS` | 0 |
| 6 | `StartSession` | `SUCCESS` | 0 |
| 7 | `Get` | `SUCCESS` | 2 |
| 8 | `Activate` | `SUCCESS` | 0 |
| 9 | `EndSession` | `SUCCESS` | 0 |
| 10 | `StartSession` | `SUCCESS` | 0 |
| 11 | `Get` | `SUCCESS` | 2 |
| 12 | `EndSession` | `SUCCESS` | 0 |
| 13 | `StartSession` | `SUCCESS` | 0 |
| 14 | `Get` | `SUCCESS` | 2 |
| 15 | `EndSession` | `SUCCESS` | 0 |
| 16 | `StartSession` | `SUCCESS` | 0 |
| 17 | `Get` | `SUCCESS` | 2 |
| 18 | `EndSession` | `SUCCESS` | 0 |
| 19 | `StartSession` | `SUCCESS` | 0 |
| 20 | `Set` | `SUCCESS` | 0 |
| 21 | `EndSession` | `SUCCESS` | 0 |
| 22 | `StartSession` | `SUCCESS` | 0 |
| 23 | `Set` | `SUCCESS` | 0 |
| 24 | `EndSession` | `SUCCESS` | 0 |
| 25 | `EndSession` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale
