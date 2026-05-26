# Public20 Reference Qualitative State-Transition Audit Pack

이 pack은 public20 trajectory를 실제 입력 구조 reference로 읽고 state transition을 직접 확인하기 위한 산출물이다.
정답 정보는 이 파일에 포함하지 않는다.
자동 판정기가 아니며 rule engine/runtime verifier/solver fallback이 아니다.

- 생성 시각(KST): 2026-05-26T15:59:18+09:00
- normalized JSONL: `runs/self_instruct/public20_baseline/gate_b/public20.normalized.jsonl`
- sample 수: 20

## Sample 1: tc1

- sample_id: `tc1`
- line_number: `1`
- record_count: 1
- final method/status: `Properties/SUCCESS`
- method/status sequence: `0:Properties/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `Properties` | `SUCCESS` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 2: tc2

- sample_id: `tc2`
- line_number: `2`
- record_count: 2
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 3: tc3

- sample_id: `tc3`
- line_number: `3`
- record_count: 7
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 4: tc4

- sample_id: `tc4`
- line_number: `4`
- record_count: 10
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Set/SUCCESS -> 8:EndSession/SUCCESS -> 9:StartSession/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 8 | 9 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 9 | 10 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 5: tc5

- sample_id: `tc5`
- line_number: `5`
- record_count: 11
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 6: tc6

- sample_id: `tc6`
- line_number: `6`
- record_count: 21
- final method/status: `Set/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Authority` | `Set` | `SUCCESS` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 7: tc7

- sample_id: `tc7`
- line_number: `7`
- record_count: 26
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Set/SUCCESS -> 24:EndSession/SUCCESS -> 25:StartSession/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Authority` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 21 | 22 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 22 | 23 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 23 | 24 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 24 | 25 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 25 | 26 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 8: tc8

- sample_id: `tc8`
- line_number: `8`
- record_count: 21
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Get/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 9: tc9

- sample_id: `tc9`
- line_number: `9`
- record_count: 27
- final method/status: `Get/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Set/SUCCESS -> 24:EndSession/SUCCESS -> 25:StartSession/SUCCESS -> 26:Get/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `MBRControl` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 21 | 22 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 22 | 23 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 23 | 24 | `MBRControl` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 24 | 25 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 25 | 26 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 26 | 27 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 10: tc10

- sample_id: `tc10`
- line_number: `10`
- record_count: 39
- final method/status: `Read/RANDOM DATA`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Get/SUCCESS -> 24:GenKey/SUCCESS -> 25:EndSession/SUCCESS -> 26:StartSession/SUCCESS -> 27:Set/SUCCESS -> 28:EndSession/SUCCESS -> 29:StartSession/SUCCESS -> 30:Set/SUCCESS -> 31:EndSession/SUCCESS -> 32:Write/PASS -> 33:Read/PATTERN 8E -> 34:StartSession/SUCCESS -> 35:Get/SUCCESS -> 36:GenKey/SUCCESS -> 37:EndSession/SUCCESS -> 38:Read/RANDOM DATA`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Locking` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 21 | 22 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 22 | 23 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 23 | 24 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 24 | 25 | `K_AES_256` | `GenKey` | `SUCCESS` | `SUCCESS` | 0 |
| 25 | 26 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 26 | 27 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 27 | 28 | `Locking` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 28 | 29 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 29 | 30 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 30 | 31 | `Locking` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 31 | 32 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 32 | 33 | `` | `Write` | `` | `PASS` | 0 |
| 33 | 34 | `` | `Read` | `` | `PATTERN 8E` | 0 |
| 34 | 35 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 35 | 36 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 36 | 37 | `K_AES_256` | `GenKey` | `SUCCESS` | `SUCCESS` | 0 |
| 37 | 38 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 38 | 39 | `` | `Read` | `` | `RANDOM DATA` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 11: tc11

- sample_id: `tc11`
- line_number: `11`
- record_count: 1
- final method/status: `Properties/INVALID_PARAMETER`
- method/status sequence: `0:Properties/INVALID_PARAMETER`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `Properties` | `SUCCESS` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 12: tc12

- sample_id: `tc12`
- line_number: `12`
- record_count: 2
- final method/status: `Get/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/NOT_AUTHORIZED`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `NOT_AUTHORIZED` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 13: tc13

- sample_id: `tc13`
- line_number: `13`
- record_count: 7
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `NOT_AUTHORIZED` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 14: tc14

- sample_id: `tc14`
- line_number: `14`
- record_count: 10
- final method/status: `StartSession/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Set/SUCCESS -> 8:EndSession/SUCCESS -> 9:StartSession/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 8 | 9 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 9 | 10 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 15: tc15

- sample_id: `tc15`
- line_number: `15`
- record_count: 9
- final method/status: `Activate/SUCCESS`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 16: tc16

- sample_id: `tc16`
- line_number: `16`
- record_count: 21
- final method/status: `Set/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/INVALID_PARAMETER`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Authority` | `Set` | `SUCCESS` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 17: tc17

- sample_id: `tc17`
- line_number: `17`
- record_count: 26
- final method/status: `StartSession/NOT_AUTHORIZED`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Set/SUCCESS -> 24:EndSession/SUCCESS -> 25:StartSession/NOT_AUTHORIZED`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Authority` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 21 | 22 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 22 | 23 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 23 | 24 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 24 | 25 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 25 | 26 | `Session Manager UID` | `StartSession` | `SUCCESS` | `NOT_AUTHORIZED` | 2 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 18: tc18

- sample_id: `tc18`
- line_number: `18`
- record_count: 21
- final method/status: `Get/INVALID_PARAMETER`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Get/INVALID_PARAMETER`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Locking` | `Get` | `SUCCESS` | `INVALID_PARAMETER` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 19: tc19

- sample_id: `tc19`
- line_number: `19`
- record_count: 27
- final method/status: `Get/FAIL`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Set/SUCCESS -> 24:EndSession/SUCCESS -> 25:StartSession/SUCCESS -> 26:Get/FAIL`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `MBRControl` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 21 | 22 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 22 | 23 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 23 | 24 | `MBRControl` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 24 | 25 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 25 | 26 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 26 | 27 | `MBRControl` | `Get` | `SUCCESS` | `FAIL` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale

## Sample 20: tc20

- sample_id: `tc20`
- line_number: `20`
- record_count: 39
- final method/status: `Read/8E`
- method/status sequence: `0:StartSession/SUCCESS -> 1:Get/SUCCESS -> 2:EndSession/SUCCESS -> 3:StartSession/SUCCESS -> 4:Set/SUCCESS -> 5:EndSession/SUCCESS -> 6:StartSession/SUCCESS -> 7:Get/SUCCESS -> 8:Activate/SUCCESS -> 9:EndSession/SUCCESS -> 10:StartSession/SUCCESS -> 11:Get/SUCCESS -> 12:EndSession/SUCCESS -> 13:StartSession/SUCCESS -> 14:Get/SUCCESS -> 15:EndSession/SUCCESS -> 16:StartSession/SUCCESS -> 17:Get/SUCCESS -> 18:EndSession/SUCCESS -> 19:StartSession/SUCCESS -> 20:Set/SUCCESS -> 21:EndSession/SUCCESS -> 22:StartSession/SUCCESS -> 23:Get/SUCCESS -> 24:GenKey/SUCCESS -> 25:EndSession/SUCCESS -> 26:StartSession/SUCCESS -> 27:Set/SUCCESS -> 28:EndSession/SUCCESS -> 29:StartSession/SUCCESS -> 30:Set/SUCCESS -> 31:EndSession/SUCCESS -> 32:Write/PASS -> 33:Read/PATTERN 8E -> 34:StartSession/SUCCESS -> 35:Get/SUCCESS -> 36:GenKey/SUCCESS -> 37:EndSession/SUCCESS -> 38:Read/8E`

### Record Summary

| index | source_index | invoking_name | method | input_status | output_status | return_value_count |
|---:|---:|---|---|---|---|---:|
| 0 | 1 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 1 | 2 | `C_PIN` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 2 | 3 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 3 | 4 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 4 | 5 | `C_PIN` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 5 | 6 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 6 | 7 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 7 | 8 | `SP` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 8 | 9 | `SP` | `Activate` | `SUCCESS` | `SUCCESS` | 0 |
| 9 | 10 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 10 | 11 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 11 | 12 | `LockingInfo` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 12 | 13 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 13 | 14 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 14 | 15 | `MBRControl` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 15 | 16 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 16 | 17 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 17 | 18 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 18 | 19 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 19 | 20 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 20 | 21 | `Locking` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 21 | 22 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 22 | 23 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 23 | 24 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 24 | 25 | `K_AES_256` | `GenKey` | `SUCCESS` | `SUCCESS` | 0 |
| 25 | 26 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 26 | 27 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 27 | 28 | `Locking` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 28 | 29 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 29 | 30 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 30 | 31 | `Locking` | `Set` | `SUCCESS` | `SUCCESS` | 0 |
| 31 | 32 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 32 | 33 | `` | `Write` | `` | `PASS` | 0 |
| 33 | 34 | `` | `Read` | `` | `PATTERN 8E` | 0 |
| 34 | 35 | `Session Manager UID` | `StartSession` | `SUCCESS` | `SUCCESS` | 2 |
| 35 | 36 | `Locking` | `Get` | `SUCCESS` | `SUCCESS` | 1 |
| 36 | 37 | `K_AES_256` | `GenKey` | `SUCCESS` | `SUCCESS` | 0 |
| 37 | 38 | `` | `EndSession` | `SUCCESS` | `SUCCESS` | 2 |
| 38 | 39 | `` | `Read` | `` | `8E` | 0 |

### state_trace

### observed_state_summary

### shape_notes

### audit_decision

### rationale
