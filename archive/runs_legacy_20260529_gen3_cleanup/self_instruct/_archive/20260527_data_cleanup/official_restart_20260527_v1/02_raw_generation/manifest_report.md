# Clean Supervised Manifest 보고서

- 생성 시각(KST): 2026-05-27T18:36:04.803778+09:00
- 전체 게이트: 통과
- JSON 로드 파일 수: 1
- 비JSON/기타 skip 파일 수: 0
- 원본/선택/제외 record 수: 11 / 11 / 0
- group 수: 11
- blocklisted 포함 record 수: 0

## 게이트 상태

| 항목 | 기준 | 값 | 상태 |
| --- | --- | --- | --- |
| `selected_records_gt_0` | > 0 | 11 | 통과 |
| `group_leakage_0` | 0 | 0 | 통과 |
| `manifest_exact_duplicate_0` | 0 | 0 | 통과 |
| `template_entropy_gte_min` | 0.75 | 1.0 | 통과 |
| `top_template_share_lte_max` | 0.2 | 0.090909 | 통과 |
| `public_holdout_selected_0` | 0 | 0 | 통과 |
| `rule_context_selected_0` | 0 | 0 | 통과 |

## 핵심 지표

- normalized template entropy: 1.0
- top template share: 0.090909
- top template count: 1
- duplicate group/record 수: 0 / 0
- group leakage 수: 0

## 제외 사유

- 없음

## Label Counts

- `fail`: 3
- `pass`: 8

## Split Record Counts

- `calibration`: 1
- `hidden`: 2
- `train`: 8

## Split Group Counts

- `calibration`: 1
- `hidden`: 2
- `train`: 8

## Length Bins

- `0`: 0
- `1-32`: 11
- `33-64`: 0
- `65-128`: 0
- `129-256`: 0
- `257-512`: 0
- `513-1024`: 0
- `1025+`: 0

## Blocklisted Included By Term

- 없음
