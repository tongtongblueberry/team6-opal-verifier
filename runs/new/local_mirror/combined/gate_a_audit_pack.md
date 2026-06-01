# Gate A Qualitative State-Transition Audit Pack

이 pack은 사람이 또는 LLM judge가 records를 처음부터 끝까지 읽고 state transition을 직접 확인하기 위한 산출물이다.
자동 verdict를 확정하지 않으며, rule engine/runtime architecture/solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-30T07:50:53+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/new/local_mirror/combined/accepted.jsonl`
- sample 수: 40

## Sample 1: req_RULE_03_fail_003_c0

- sample_id: `req_RULE_03_fail_003_c0`
- line_number: `52`
- label: `fail`
- record_count: 4
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 2: req_RULE_22_pass_002_c0

- sample_id: `req_RULE_22_pass_002_c0`
- line_number: `178`
- label: `pass`
- record_count: 23
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:EndSession/SUCCESS -> 9:StartSession/SUCCESS -> 10:Get/SUCCESS -> 11:EndSession/SUCCESS -> 12:StartSession/SUCCESS -> 13:Get/SUCCESS -> 14:EndSession/SUCCESS -> 15:StartSession/SUCCESS -> 16:Get/SUCCESS -> 17:EndSession/SUCCESS -> 18:StartSession/SUCCESS -> 19:Get/SUCCESS -> 20:EndSession/SUCCESS -> 21:StartSession/SUCCESS -> 22:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Get` | `SUCCESS` | 1 |
| 8 | `EndSession` | `SUCCESS` | 2 |
| 9 | `StartSession` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `EndSession` | `SUCCESS` | 2 |
| 12 | `StartSession` | `SUCCESS` | 2 |
| 13 | `Get` | `SUCCESS` | 1 |
| 14 | `EndSession` | `SUCCESS` | 2 |
| 15 | `StartSession` | `SUCCESS` | 2 |
| 16 | `Get` | `SUCCESS` | 1 |
| 17 | `EndSession` | `SUCCESS` | 2 |
| 18 | `StartSession` | `SUCCESS` | 2 |
| 19 | `Get` | `SUCCESS` | 1 |
| 20 | `EndSession` | `SUCCESS` | 2 |
| 21 | `StartSession` | `SUCCESS` | 2 |
| 22 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 3: req_RULE_01_pass_002_c0

- sample_id: `req_RULE_01_pass_002_c0`
- line_number: `19`
- label: `pass`
- record_count: 5
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 4: req_RULE_15_pass_001_c0

- sample_id: `req_RULE_15_pass_001_c0`
- line_number: `137`
- label: `pass`
- record_count: 6
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:Set/SUCCESS -> 4:EndSession/SUCCESS -> 5:Get/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `Set` | `SUCCESS` | 0 |
| 4 | `EndSession` | `SUCCESS` | 2 |
| 5 | `Get` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 5: req_RULE_05_pass_001_c0

- sample_id: `req_RULE_05_pass_001_c0`
- line_number: `95`
- label: `pass`
- record_count: 6
- final method/status: `StartSession/SP_FROZEN`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:Set/SUCCESS -> 4:EndSession/SUCCESS -> 5:StartSession/SP_FROZEN`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `Set` | `SUCCESS` | 2 |
| 4 | `EndSession` | `SUCCESS` | 2 |
| 5 | `StartSession` | `SP_FROZEN` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 6: req_RULE_06_pass_000_c0

- sample_id: `req_RULE_06_pass_000_c0`
- line_number: `104`
- label: `pass`
- record_count: 16
- final method/status: `StartSession/NO_SESSIONS_AVAILABLE`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:EndSession/SUCCESS -> 9:StartSession/SUCCESS -> 10:Get/SUCCESS -> 11:EndSession/SUCCESS -> 12:StartSession/SUCCESS -> 13:Get/SUCCESS -> 14:EndSession/SUCCESS -> 15:StartSession/NO_SESSIONS_AVAILABLE`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Get` | `SUCCESS` | 1 |
| 8 | `EndSession` | `SUCCESS` | 2 |
| 9 | `StartSession` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `EndSession` | `SUCCESS` | 2 |
| 12 | `StartSession` | `SUCCESS` | 2 |
| 13 | `Get` | `SUCCESS` | 1 |
| 14 | `EndSession` | `SUCCESS` | 2 |
| 15 | `StartSession` | `NO_SESSIONS_AVAILABLE` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 7: req_RULE_17_pass_002_c0

- sample_id: `req_RULE_17_pass_002_c0`
- line_number: `148`
- label: `pass`
- record_count: 5
- final method/status: `Get/FAIL`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/FAIL`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `FAIL` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 8: req_RULE_26_pass_002_c0

- sample_id: `req_RULE_26_pass_002_c0`
- line_number: `195`
- label: `pass`
- record_count: 5
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 9: req_RULE_20_pass_001_c0

- sample_id: `req_RULE_20_pass_001_c0`
- line_number: `172`
- label: `pass`
- record_count: 3
- final method/status: `EndSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 10: req_RULE_09_pass_001_c0

- sample_id: `req_RULE_09_pass_001_c0`
- line_number: `121`
- label: `pass`
- record_count: 15
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS -> 1:Properties/SUCCESS -> 2:Properties/SUCCESS -> 3:Properties/SUCCESS -> 4:Properties/SUCCESS -> 5:Properties/SUCCESS -> 6:Properties/SUCCESS -> 7:Properties/SUCCESS -> 8:Properties/SUCCESS -> 9:Properties/SUCCESS -> 10:Properties/SUCCESS -> 11:Properties/SUCCESS -> 12:Properties/SUCCESS -> 13:Properties/SUCCESS -> 14:Properties/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `SUCCESS` | 0 |
| 1 | `Properties` | `SUCCESS` | 0 |
| 2 | `Properties` | `SUCCESS` | 0 |
| 3 | `Properties` | `SUCCESS` | 0 |
| 4 | `Properties` | `SUCCESS` | 0 |
| 5 | `Properties` | `SUCCESS` | 0 |
| 6 | `Properties` | `SUCCESS` | 0 |
| 7 | `Properties` | `SUCCESS` | 0 |
| 8 | `Properties` | `SUCCESS` | 0 |
| 9 | `Properties` | `SUCCESS` | 0 |
| 10 | `Properties` | `SUCCESS` | 0 |
| 11 | `Properties` | `SUCCESS` | 0 |
| 12 | `Properties` | `SUCCESS` | 0 |
| 13 | `Properties` | `SUCCESS` | 0 |
| 14 | `Properties` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 11: req_RULE_02_pass_003_c0

- sample_id: `req_RULE_02_pass_003_c0`
- line_number: `37`
- label: `pass`
- record_count: 5
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 12: req_RULE_04_pass_000_c0

- sample_id: `req_RULE_04_pass_000_c0`
- line_number: `81`
- label: `pass`
- record_count: 4
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SP_BUSY` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 13: req_RULE_03_pass_001_c0

- sample_id: `req_RULE_03_pass_001_c0`
- line_number: `62`
- label: `pass`
- record_count: 7
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:Get/SUCCESS -> 3:Get/SUCCESS -> 4:Get/SUCCESS -> 5:Get/SUCCESS -> 6:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `Get` | `SUCCESS` | 1 |
| 3 | `Get` | `SUCCESS` | 1 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Get` | `SUCCESS` | 1 |
| 6 | `StartSession` | `NOT_AUTHORIZED` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 14: req_RULE_22_pass_001_c0

- sample_id: `req_RULE_22_pass_001_c0`
- line_number: `177`
- label: `pass`
- record_count: 6
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:Activate/SUCCESS -> 4:StartSession/SUCCESS -> 5:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `Activate` | `SUCCESS` | 0 |
| 4 | `StartSession` | `SUCCESS` | 2 |
| 5 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 15: req_RULE_02_pass_000_c0

- sample_id: `req_RULE_02_pass_000_c0`
- line_number: `30`
- label: `pass`
- record_count: 5
- final method/status: `Set/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 16: req_RULE_01_pass_000_c0

- sample_id: `req_RULE_01_pass_000_c0`
- line_number: `16`
- label: `pass`
- record_count: 5
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 17: req_RULE_04_pass_001_c0

- sample_id: `req_RULE_04_pass_001_c0`
- line_number: `83`
- label: `pass`
- record_count: 2
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:StartSession/SUCCESS -> 1:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `StartSession` | `SP_BUSY` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 18: req_RULE_08_pass_001_c0

- sample_id: `req_RULE_08_pass_001_c0`
- line_number: `116`
- label: `pass`
- record_count: 5
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 19: req_RULE_30_pass_000_c0

- sample_id: `req_RULE_30_pass_000_c0`
- line_number: `200`
- label: `pass`
- record_count: 15
- final method/status: `Properties/INVALID_PARAMETER`
- method/status sequence: `0:Properties/INVALID_PARAMETER -> 1:Properties/INVALID_PARAMETER -> 2:Properties/INVALID_PARAMETER -> 3:Properties/INVALID_PARAMETER -> 4:Properties/INVALID_PARAMETER -> 5:Properties/INVALID_PARAMETER -> 6:Properties/INVALID_PARAMETER -> 7:Properties/INVALID_PARAMETER -> 8:Properties/INVALID_PARAMETER -> 9:Properties/INVALID_PARAMETER -> 10:Properties/INVALID_PARAMETER -> 11:Properties/INVALID_PARAMETER -> 12:Properties/INVALID_PARAMETER -> 13:Properties/INVALID_PARAMETER -> 14:Properties/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `Properties` | `INVALID_PARAMETER` | 0 |
| 1 | `Properties` | `INVALID_PARAMETER` | 0 |
| 2 | `Properties` | `INVALID_PARAMETER` | 0 |
| 3 | `Properties` | `INVALID_PARAMETER` | 0 |
| 4 | `Properties` | `INVALID_PARAMETER` | 0 |
| 5 | `Properties` | `INVALID_PARAMETER` | 0 |
| 6 | `Properties` | `INVALID_PARAMETER` | 0 |
| 7 | `Properties` | `INVALID_PARAMETER` | 0 |
| 8 | `Properties` | `INVALID_PARAMETER` | 0 |
| 9 | `Properties` | `INVALID_PARAMETER` | 0 |
| 10 | `Properties` | `INVALID_PARAMETER` | 0 |
| 11 | `Properties` | `INVALID_PARAMETER` | 0 |
| 12 | `Properties` | `INVALID_PARAMETER` | 0 |
| 13 | `Properties` | `INVALID_PARAMETER` | 0 |
| 14 | `Properties` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 20: req_RULE_07_pass_002_c0

- sample_id: `req_RULE_07_pass_002_c0`
- line_number: `110`
- label: `pass`
- record_count: 7
- final method/status: `StartSession/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:StartSession/SUCCESS -> 3:Get/SUCCESS -> 4:StartSession/SUCCESS -> 5:Get/SUCCESS -> 6:StartSession/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `StartSession` | `SUCCESS` | 2 |
| 3 | `Get` | `SUCCESS` | 1 |
| 4 | `StartSession` | `SUCCESS` | 2 |
| 5 | `Get` | `SUCCESS` | 1 |
| 6 | `StartSession` | `INVALID_PARAMETER` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 21: req_RULE_08_pass_006_c0

- sample_id: `req_RULE_08_pass_006_c0`
- line_number: `120`
- label: `pass`
- record_count: 7
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:Set/SUCCESS -> 3:StartSession/SUCCESS -> 4:StartSession/SUCCESS -> 5:Get/SUCCESS -> 6:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `Set` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `StartSession` | `SUCCESS` | 2 |
| 5 | `Get` | `SUCCESS` | 1 |
| 6 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 22: req_RULE_25_pass_003_c0

- sample_id: `req_RULE_25_pass_003_c0`
- line_number: `192`
- label: `pass`
- record_count: 6
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:Activate/SUCCESS -> 4:StartSession/SUCCESS -> 5:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `Activate` | `SUCCESS` | 2 |
| 4 | `StartSession` | `SUCCESS` | 2 |
| 5 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 23: req_RULE_25_pass_002_c0

- sample_id: `req_RULE_25_pass_002_c0`
- line_number: `191`
- label: `pass`
- record_count: 5
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 24: req_RULE_13_pass_000_c0

- sample_id: `req_RULE_13_pass_000_c0`
- line_number: `135`
- label: `pass`
- record_count: 7
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:EndSession/SUCCESS -> 4:EndSession/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `EndSession` | `SUCCESS` | 2 |
| 4 | `EndSession` | `SUCCESS` | 2 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 25: req_RULE_03_pass_003_c0

- sample_id: `req_RULE_03_pass_003_c0`
- line_number: `70`
- label: `pass`
- record_count: 5
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:/ -> 4:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `` | `` | 0 |
| 4 | `StartSession` | `NOT_AUTHORIZED` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 26: req_RULE_03_pass_003_c0

- sample_id: `req_RULE_03_pass_003_c0`
- line_number: `71`
- label: `pass`
- record_count: 5
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `StartSession` | `NOT_AUTHORIZED` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 27: req_RULE_22_pass_003_c0

- sample_id: `req_RULE_22_pass_003_c0`
- line_number: `179`
- label: `pass`
- record_count: 5
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 28: req_RULE_01_pass_002_c0

- sample_id: `req_RULE_01_pass_002_c0`
- line_number: `20`
- label: `pass`
- record_count: 8
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 29: req_RULE_15_pass_002_c0

- sample_id: `req_RULE_15_pass_002_c0`
- line_number: `138`
- label: `pass`
- record_count: 5
- final method/status: `Get/FAIL`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/FAIL`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `FAIL` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 30: req_RULE_19_pass_004_c0

- sample_id: `req_RULE_19_pass_004_c0`
- line_number: `169`
- label: `pass`
- record_count: 6
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:/ -> 4:StartSession/SUCCESS -> 5:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `` | `` | 0 |
| 4 | `StartSession` | `SUCCESS` | 2 |
| 5 | `Get` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 31: req_RULE_18_pass_002_c0

- sample_id: `req_RULE_18_pass_002_c0`
- line_number: `159`
- label: `pass`
- record_count: 2
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 32: req_RULE_11_pass_001_c0

- sample_id: `req_RULE_11_pass_001_c0`
- line_number: `124`
- label: `pass`
- record_count: 5
- final method/status: `Set/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:Set/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `Set` | `SUCCESS` | 0 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Set` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 33: req_RULE_05_pass_004_c0

- sample_id: `req_RULE_05_pass_004_c0`
- line_number: `100`
- label: `pass`
- record_count: 5
- final method/status: `StartSession/SP_FROZEN`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:/ -> 4:StartSession/SP_FROZEN`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `` | `` | 0 |
| 4 | `StartSession` | `SP_FROZEN` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 34: req_RULE_04_pass_002_c0

- sample_id: `req_RULE_04_pass_002_c0`
- line_number: `84`
- label: `pass`
- record_count: 7
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SP_BUSY` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 35: req_RULE_38_pass_001_c0

- sample_id: `req_RULE_38_pass_001_c0`
- line_number: `207`
- label: `pass`
- record_count: 9
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:Get/NOT_AUTHORIZED -> 3:Get/SUCCESS -> 4:Get/SUCCESS -> 5:Get/SUCCESS -> 6:Get/SUCCESS -> 7:Get/SUCCESS -> 8:Get/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `Get` | `NOT_AUTHORIZED` | 0 |
| 3 | `Get` | `SUCCESS` | 1 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Get` | `SUCCESS` | 1 |
| 6 | `Get` | `SUCCESS` | 1 |
| 7 | `Get` | `SUCCESS` | 1 |
| 8 | `Get` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 36: req_RULE_16_pass_001_c0

- sample_id: `req_RULE_16_pass_001_c0`
- line_number: `141`
- label: `pass`
- record_count: 5
- final method/status: `Get/FAIL`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/FAIL`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `FAIL` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 37: req_RULE_04_pass_003_c0

- sample_id: `req_RULE_04_pass_003_c0`
- line_number: `86`
- label: `pass`
- record_count: 4
- final method/status: `StartSession/SP_BUSY`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SP_BUSY`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SP_BUSY` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 38: req_RULE_20_pass_003_c0

- sample_id: `req_RULE_20_pass_003_c0`
- line_number: `174`
- label: `pass`
- record_count: 27
- final method/status: `EndSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:EndSession/SUCCESS -> 9:StartSession/SUCCESS -> 10:Get/SUCCESS -> 11:EndSession/SUCCESS -> 12:StartSession/SUCCESS -> 13:Get/SUCCESS -> 14:EndSession/SUCCESS -> 15:StartSession/SUCCESS -> 16:Get/SUCCESS -> 17:EndSession/SUCCESS -> 18:StartSession/SUCCESS -> 19:Get/SUCCESS -> 20:EndSession/SUCCESS -> 21:StartSession/SUCCESS -> 22:Get/SUCCESS -> 23:EndSession/SUCCESS -> 24:StartSession/SUCCESS -> 25:Get/SUCCESS -> 26:EndSession/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `EndSession` | `SUCCESS` | 2 |
| 6 | `StartSession` | `SUCCESS` | 2 |
| 7 | `Get` | `SUCCESS` | 1 |
| 8 | `EndSession` | `SUCCESS` | 2 |
| 9 | `StartSession` | `SUCCESS` | 2 |
| 10 | `Get` | `SUCCESS` | 1 |
| 11 | `EndSession` | `SUCCESS` | 2 |
| 12 | `StartSession` | `SUCCESS` | 2 |
| 13 | `Get` | `SUCCESS` | 1 |
| 14 | `EndSession` | `SUCCESS` | 2 |
| 15 | `StartSession` | `SUCCESS` | 2 |
| 16 | `Get` | `SUCCESS` | 1 |
| 17 | `EndSession` | `SUCCESS` | 2 |
| 18 | `StartSession` | `SUCCESS` | 2 |
| 19 | `Get` | `SUCCESS` | 1 |
| 20 | `EndSession` | `SUCCESS` | 2 |
| 21 | `StartSession` | `SUCCESS` | 2 |
| 22 | `Get` | `SUCCESS` | 1 |
| 23 | `EndSession` | `SUCCESS` | 2 |
| 24 | `StartSession` | `SUCCESS` | 2 |
| 25 | `Get` | `SUCCESS` | 1 |
| 26 | `EndSession` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 39: req_RULE_15_pass_004_c0

- sample_id: `req_RULE_15_pass_004_c0`
- line_number: `139`
- label: `pass`
- record_count: 5
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/FAIL -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/INVALID_PARAMETER`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `FAIL` | 0 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale

## Sample 40: req_RULE_01_pass_003_c0

- sample_id: `req_RULE_01_pass_003_c0`
- line_number: `22`
- label: `pass`
- record_count: 6
- final method/status: `Set/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Get/SUCCESS -> 5:Set/SUCCESS`

### Record Summary

| index | method | status | return_value_count |
|---:|---|---|---:|
| 0 | `StartSession` | `SUCCESS` | 2 |
| 1 | `Get` | `SUCCESS` | 1 |
| 2 | `EndSession` | `SUCCESS` | 2 |
| 3 | `StartSession` | `SUCCESS` | 2 |
| 4 | `Get` | `SUCCESS` | 1 |
| 5 | `Set` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### audit_decision

### rationale
