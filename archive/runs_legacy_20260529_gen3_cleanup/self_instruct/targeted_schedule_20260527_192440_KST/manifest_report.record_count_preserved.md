# Clean Supervised Manifest 보고서

- 생성 시각(KST): 2026-05-27T21:16:19.670808+09:00
- 전체 게이트: 통과
- JSON 로드 파일 수: 1
- 비JSON/기타 skip 파일 수: 0
- 원본/선택/제외 record 수: 40 / 20 / 0
- group 수: 20
- blocklisted 포함 record 수: 0

## 게이트 상태

| 항목 | 기준 | 값 | 상태 |
| --- | --- | --- | --- |
| `selected_records_gt_0` | > 0 | 20 | 통과 |
| `group_leakage_0` | 0 | 0 | 통과 |
| `manifest_exact_duplicate_0` | 0 | 0 | 통과 |
| `template_entropy_gte_min` | 0.75 | 1.0 | 통과 |
| `top_template_share_lte_max` | 0.2 | 0.05 | 통과 |
| `public_holdout_selected_0` | 0 | 0 | 통과 |
| `rule_context_selected_0` | 0 | 0 | 통과 |
| `length_balance_reference_errors_0` | 0 | 0 | 통과 |
| `length_balance_reference_records_gt_0` | > 0 | 20 | 통과 |
| `length_balance_jsd_lte_target` | 0.08 | 0.078355 | 통과 |

## 핵심 지표

- normalized template entropy: 1.0
- top template share: 0.05
- top template count: 1
- duplicate group/record 수: 0 / 0
- group leakage 수: 0

## 제외 사유

- 없음

## Label Counts

- `fail`: 10
- `pass`: 10

## Split Record Counts

- `calibration`: 2
- `hidden`: 4
- `train`: 14

## Split Group Counts

- `calibration`: 2
- `hidden`: 4
- `train`: 14

## Length Bins

- `0`: 0
- `1-32`: 1
- `33-64`: 0
- `65-128`: 3
- `129-256`: 2
- `257-512`: 12
- `513-1024`: 2
- `1025+`: 0

## Blocklisted Included By Term

- 없음

## Length Balance

- applied: True
- reason: record_count_preserving_target_reached
- before/after JSD: 0.132488 / 0.078355
- dropped groups/records: 20 / 20
- reference eligible records: 20
- reference skipped files/records: 0 / 0
- reference errors: 0
- record_count preservation applied: True
- record_count preservation reason: record_count_preserving_target_reached
- record_count mean before/reference/after: 16.4 / 16.4 / 16.4
- record_count mean abs gap: 0.0
- record_count selector states: 4990998
