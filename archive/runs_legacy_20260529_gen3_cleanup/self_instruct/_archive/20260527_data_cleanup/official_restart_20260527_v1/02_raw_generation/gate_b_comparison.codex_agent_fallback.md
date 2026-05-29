# Gate B Dimension Comparison

- public profile: `runs/self_instruct/public20_baseline/gate_b/public20.profile.json`
- generated profile: `runs/self_instruct/official_restart_20260527_v1/02_raw_generation/candidate_profile.judge_gate_a_accepted.codex_agent_fallback.json`
- public20 label aggregate: local eval/distribution only; generation, judge, manifest, training input 사용 금지

## Row Count

| side | rows | declared_count |
|---|---:|---:|
| public20 | 20 | 20 |
| generated | 11 | 11 |

## Numeric Stats

| metric | public min/mean/max | generated min/mean/max | generated-public mean diff |
|---|---|---|---:|
| record_count | 1/16.4/39 | 1/2.09091/3 | -14.3091 |
| method_sequence_length | 1/16.4/39 | 1/2.09091/3 | -14.3091 |
| input_json_chars | 429/6911.3/15256 | 325/614.818/888 | -6296.48 |
| total_return_value_count | 0/23.55/51 | 0/2.27273/4 | -21.2773 |
| final_return_value_count | 0/0.95/2 | 0/0.272727/2 | -0.677273 |

## Distribution Counts

- public record_count bins: 1-32=18, 33-64=2
- generated record_count bins: 1-32=11
- public final_method: Activate=1, Get=6, Properties=2, Read=2, Set=2, StartSession=7
- generated final_method: Get=4, Set=3, StartSession=4
- public final_status: 8E=1, FAIL=1, INVALID_PARAMETER=3, NOT_AUTHORIZED=3, RANDOM DATA=1, SUCCESS=11
- generated final_status: INVALID_PARAMETER=4, NOT_AUTHORIZED=3, SP_BUSY=1, SUCCESS=3

## Label Distribution

- public local aggregate: fail=10, pass=10
- generated labels: fail=3, pass=8

## No-Go Warnings

- `record_count_mean_difference`: public20와 generated의 평균 record_count가 다르므로 Gate B에서 질적 검토가 필요하다.
