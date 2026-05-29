# Supervised Manifest 검증 보고서

- 생성 시각(KST): 2026-05-27T23:40:45.793919+09:00
- 전체 hard gate: 실패
- manifest: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST/manifest.trajectory_signature.record_count_preserved.codex_agent_fallback.jsonl`
- reference: `data/local/public20/public20_input.jsonl`
- 레코드 수: 25
- labeled coverage: 1.0
- unknown label records: 0
- invalid label records: 0

## Hard Gates

| 게이트 | 기준 | 값 | 상태 |
| --- | ---: | ---: | --- |
| `manifest_jsonl_parse_errors_0` | 0 | 0 | 통과 |
| `manifest_records_gt_0` | >0 | 25 | 통과 |
| `required_fields_present` | 0 | 0 | 통과 |
| `labeled_coverage_100pct` | 1.0 | 1.0 | 통과 |
| `unknown_label_0` | 0 | 0 | 통과 |
| `labels_only_pass_fail` | 0 | 0 | 통과 |
| `exact_duplicate_content_hash_0` | 0 | 0 | 통과 |
| `group_leakage_0` | 0 | 0 | 통과 |
| `template_entropy_gte_threshold` | 0.75 | 1.0 | 통과 |
| `top_template_share_lte_threshold` | 0.2 | 0.04 | 통과 |
| `split_label_counts_nonzero_where_possible` | 0 | 0 | 통과 |
| `artifact_exclusion` | 0 | 0 | 통과 |
| `public_holdout_metadata_absent` | 0 | 0 | 통과 |
| `rule_context_text_absent` | 0 | 0 | 통과 |
| `rule_context_metadata_or_input_absent` | 0 | 0 | 통과 |
| `reference_parse_errors_0` | 0 | 0 | 통과 |
| `reference_records_gt_0` | >0 | 20 | 통과 |
| `length_jsd_lte_threshold` | 0.08 | 0.4356 | 실패 |
| `char_length_mean_ratio_gte_threshold` | 0.6 | 1.154828 | 통과 |
| `char_length_median_ratio_gte_threshold` | 0.6 | 1.082728 | 통과 |
| `min_record_count_gap_lte_threshold` | 1 | 0 | 통과 |

## 핵심 지표

- normalized template entropy: 1.0
- top template share: 0.04 (1 records)
- length JSD: 0.4356
- char length mean ratio: 1.154828
- char length median ratio: 1.082728
- min record_count gap: 0
- manifest char stats: {'count': 25, 'min': 1705, 'median': 7375.0, 'mean': 7981.36, 'max': 20856}
- reference char stats: {'count': 20, 'min': 429, 'median': 6811.5, 'mean': 6911.3, 'max': 15256}
- manifest record_count stats: {'count': 25, 'min': 1, 'median': 13.0, 'mean': 13.68, 'max': 39}
- reference record_count stats: {'count': 20, 'min': 1, 'median': 16.0, 'mean': 16.4, 'max': 39}
- duplicate content_hash groups: 0
- group leakage groups: 0

## Label Counts

- `pass`: 12
- `fail`: 13

## Split Label Counts

- `calibration`: {'fail': 1, 'pass': 1}
- `hidden`: {'fail': 2, 'pass': 3}
- `train`: {'fail': 10, 'pass': 8}
