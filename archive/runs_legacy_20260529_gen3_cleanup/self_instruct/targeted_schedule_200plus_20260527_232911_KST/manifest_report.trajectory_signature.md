# Clean Supervised Manifest 보고서

- 생성 시각(KST): 2026-05-27T23:40:20.296200+09:00
- 전체 게이트: 실패
- JSON 로드 파일 수: 1
- 비JSON/기타 skip 파일 수: 0
- 원본/선택/제외 record 수: 25 / 25 / 0
- group 수: 25
- blocklisted 포함 record 수: 0

## 게이트 상태

| 항목 | 기준 | 값 | 상태 |
| --- | --- | --- | --- |
| `selected_records_gt_0` | > 0 | 25 | 통과 |
| `group_leakage_0` | 0 | 0 | 통과 |
| `manifest_exact_duplicate_0` | 0 | 0 | 통과 |
| `template_entropy_gte_min` | 0.75 | 1.0 | 통과 |
| `top_template_share_lte_max` | 0.2 | 0.04 | 통과 |
| `public_holdout_selected_0` | 0 | 0 | 통과 |
| `rule_context_selected_0` | 0 | 0 | 통과 |
| `length_balance_reference_errors_0` | 0 | 0 | 통과 |
| `length_balance_reference_records_gt_0` | > 0 | 20 | 통과 |
| `length_balance_jsd_lte_target` | 0.08 | 0.4356 | 실패 |

## 핵심 지표

- normalized template entropy: 1.0
- top template share: 0.04
- top template count: 1
- duplicate group/record 수: 0 / 0
- group leakage 수: 0

## 제외 사유

- 없음

## Label Counts

- `fail`: 13
- `pass`: 12

## Split Record Counts

- `calibration`: 2
- `hidden`: 5
- `train`: 18

## Split Group Counts

- `calibration`: 2
- `hidden`: 5
- `train`: 18

## Length Bins

- `0`: 0
- `1-32`: 19
- `33-64`: 6
- `65-128`: 0
- `129-256`: 0
- `257-512`: 0
- `513-1024`: 0
- `1025+`: 0

## Blocklisted Included By Term

- 없음

## Length Balance

- applied: False
- reason: target_not_reached_within_constraints
- before/after JSD: 0.4356 / 0.4356
- dropped groups/records: 0 / 0
- reference eligible records: 20
- reference skipped files/records: 0 / 0
- reference errors: 0
- record_count preservation applied: False
- record_count preservation reason: no_length_valid_record_count_candidate
- record_count mean before/reference/after: 13.68 / 16.4 / None
- record_count mean abs gap: None
- record_count selector states: 58347
