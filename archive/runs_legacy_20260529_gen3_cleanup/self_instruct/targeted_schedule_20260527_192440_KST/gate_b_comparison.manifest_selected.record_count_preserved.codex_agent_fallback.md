# Gate B Dimension Comparison

- public profile: `runs/self_instruct/public20_baseline/gate_b/public20.profile.json`
- generated profile: `runs/self_instruct/targeted_schedule_20260527_192440_KST/candidate_profile.manifest_selected.record_count_preserved.codex_agent_fallback.json`
- public20 label aggregate: local eval/distribution only; generation, judge, manifest, training input 사용 금지

## Row Count

| side | rows | declared_count |
|---|---:|---:|
| public20 | 20 | 20 |
| generated | 20 | 20 |

## Numeric Stats

| metric | public min/mean/max | generated min/mean/max | generated-public mean diff |
|---|---|---|---:|
| record_count | 1/16.4/39 | 1/16.4/39 | 0 |
| method_sequence_length | 1/16.4/39 | 1/16.4/39 | 0 |
| input_json_chars | 429/6911.3/15256 | 1093/18159.5/42912 | 11248.2 |
| total_return_value_count | 0/23.55/51 | 0/18.75/45 | -4.8 |
| final_return_value_count | 0/0.95/2 | 0/0.4/1 | -0.55 |

## Distribution Counts

- public record_count bins: 1-32=18, 33-64=2
- generated record_count bins: 1-32=18, 33-64=2
- public final_method: Activate=1, Get=6, Properties=2, Read=2, Set=2, StartSession=7
- generated final_method: Activate=2, Authenticate=1, Get=8, Revert=1, Set=5, StartSession=3
- public final_status: 8E=1, FAIL=1, INVALID_PARAMETER=3, NOT_AUTHORIZED=3, RANDOM DATA=1, SUCCESS=11
- generated final_status: FAIL=1, INVALID_PARAMETER=5, NOT_AUTHORIZED=3, NO_SESSIONS_AVAILABLE=1, SUCCESS=10

## Label Distribution

- public local aggregate: fail=10, pass=10
- generated labels: fail=10, pass=10

## No-Go Warnings

- 없음
