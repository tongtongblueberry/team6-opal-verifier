# Gate B Dimension Comparison

- public profile: `runs/self_instruct/public20_baseline/gate_b/public20.profile.json`
- generated profile: `runs/self_instruct/targeted_schedule_20260527_192440_KST/candidate_profile.manifest_selected.codex_agent_fallback.json`
- public20 label aggregate: local eval/distribution only; generation, judge, manifest, training input 사용 금지

## Row Count

| side | rows | declared_count |
|---|---:|---:|
| public20 | 20 | 20 |
| generated | 33 | 33 |

## Numeric Stats

| metric | public min/mean/max | generated min/mean/max | generated-public mean diff |
|---|---|---|---:|
| record_count | 1/16.4/39 | 1/13.7576/28 | -2.64242 |
| method_sequence_length | 1/16.4/39 | 1/13.7576/28 | -2.64242 |
| input_json_chars | 429/6911.3/15256 | 1093/15287.4/30869 | 8376.06 |
| total_return_value_count | 0/23.55/51 | 0/15.9394/32 | -7.61061 |
| final_return_value_count | 0/0.95/2 | 0/0.575758/2 | -0.374242 |

## Distribution Counts

- public record_count bins: 1-32=18, 33-64=2
- generated record_count bins: 1-32=33
- public final_method: Activate=1, Get=6, Properties=2, Read=2, Set=2, StartSession=7
- generated final_method: Activate=3, Authenticate=3, Get=8, Next=1, Properties=2, Revert=1, RevertSP=1, Set=7, StartSession=7
- public final_status: 8E=1, FAIL=1, INVALID_PARAMETER=3, NOT_AUTHORIZED=3, RANDOM DATA=1, SUCCESS=11
- generated final_status: FAIL=2, INVALID_PARAMETER=8, NOT_AUTHORIZED=3, NO_SESSIONS_AVAILABLE=1, SP_BUSY=1, SP_FROZEN=1, SUCCESS=17

## Label Distribution

- public local aggregate: fail=10, pass=10
- generated labels: fail=16, pass=17

## No-Go Warnings

- `record_count_mean_difference`: public20와 generated의 평균 record_count가 다르므로 Gate B에서 질적 검토가 필요하다.
