# Gate B Dimension Comparison

- public profile: `runs/self_instruct/public20_baseline/gate_b/public20.profile.json`
- generated profile: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST/candidate_profile.gate_a_accepted.trajectory_signature.codex_agent_fallback.json`
- public20 label aggregate: local eval/distribution only; generation, judge, manifest, training input 사용 금지

## Row Count

| side | rows | declared_count |
|---|---:|---:|
| public20 | 20 | 20 |
| generated | 25 | 25 |

## Numeric Stats

| metric | public min/mean/max | generated min/mean/max | generated-public mean diff |
|---|---|---|---:|
| record_count | 1/16.4/39 | 1/13.68/39 | -2.72 |
| method_sequence_length | 1/16.4/39 | 1/13.68/39 | -2.72 |
| input_json_chars | 429/6911.3/15256 | 1789/8065.36/20940 | 1154.06 |
| total_return_value_count | 0/23.55/51 | 3/28.36/79 | 4.81 |
| final_return_value_count | 0/0.95/2 | 3/3/3 | 2.05 |

## Distribution Counts

- public record_count bins: 1-32=18, 33-64=2
- generated record_count bins: 1-32=23, 33-64=2
- public final_method: Activate=1, Get=6, Properties=2, Read=2, Set=2, StartSession=7
- generated final_method: Activate=2, Authenticate=2, Get=7, Properties=2, RevertSP=1, Set=5, StartSession=6
- public final_status: 8E=1, FAIL=1, INVALID_PARAMETER=3, NOT_AUTHORIZED=3, RANDOM DATA=1, SUCCESS=11
- generated final_status: FAIL=1, INVALID_PARAMETER=5, NOT_AUTHORIZED=4, NO_SESSIONS_AVAILABLE=1, SP_BUSY=1, SP_FROZEN=1, SUCCESS=12

## Label Distribution

- public local aggregate: fail=10, pass=10
- generated labels: fail=13, pass=12

## No-Go Warnings

- `record_count_mean_difference`: public20와 generated의 평균 record_count가 다르므로 Gate B에서 질적 검토가 필요하다.
