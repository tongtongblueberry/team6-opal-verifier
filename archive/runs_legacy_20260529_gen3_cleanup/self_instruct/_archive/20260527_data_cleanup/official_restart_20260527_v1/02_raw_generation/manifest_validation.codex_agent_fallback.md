# Supervised Manifest 검증 보고서

- 생성 시각(KST): 2026-05-27T18:36:44.824795+09:00
- 전체 hard gate: 실패
- manifest: `runs/self_instruct/official_restart_20260527_v1/02_raw_generation/manifest.codex_agent_fallback.jsonl`
- reference: `None`
- 레코드 수: 11
- labeled coverage: 1.0
- unknown label records: 0
- invalid label records: 0

## Hard Gates

| 게이트 | 기준 | 값 | 상태 |
| --- | ---: | ---: | --- |
| `manifest_jsonl_parse_errors_0` | 0 | 0 | 통과 |
| `manifest_records_gt_0` | >0 | 11 | 통과 |
| `required_fields_present` | 0 | 0 | 통과 |
| `labeled_coverage_100pct` | 1.0 | 1.0 | 통과 |
| `unknown_label_0` | 0 | 0 | 통과 |
| `labels_only_pass_fail` | 0 | 0 | 통과 |
| `exact_duplicate_content_hash_0` | 0 | 0 | 통과 |
| `group_leakage_0` | 0 | 0 | 통과 |
| `template_entropy_gte_threshold` | 0.75 | 1.0 | 통과 |
| `top_template_share_lte_threshold` | 0.2 | 0.090909 | 통과 |
| `split_label_counts_nonzero_where_possible` | 0 | 2 | 실패 |
| `artifact_exclusion` | 0 | 0 | 통과 |
| `public_holdout_metadata_absent` | 0 | 0 | 통과 |
| `rule_context_text_absent` | 0 | 0 | 통과 |
| `rule_context_metadata_or_input_absent` | 0 | 0 | 통과 |
| `length_jsd_lte_threshold` | 0.08 | None | 실패(건너뜀) |
| `char_length_mean_ratio_gte_threshold` | 0.6 | None | 건너뜀 |
| `char_length_median_ratio_gte_threshold` | 0.6 | None | 건너뜀 |
| `min_record_count_gap_lte_threshold` | 1 | None | 건너뜀 |

## 핵심 지표

- normalized template entropy: 1.0
- top template share: 0.090909 (1 records)
- length JSD: None
- char length mean ratio: None
- char length median ratio: None
- min record_count gap: None
- manifest char stats: {'count': 11, 'min': 215, 'median': 480.0, 'mean': 504.818182, 'max': 778}
- reference char stats: {'count': 0, 'min': None, 'median': None, 'mean': None, 'max': None}
- manifest record_count stats: {'count': 11, 'min': 1, 'median': 2.0, 'mean': 2.090909, 'max': 3}
- reference record_count stats: {'count': 0, 'min': None, 'median': None, 'mean': None, 'max': None}
- duplicate content_hash groups: 0
- group leakage groups: 0

## Label Counts

- `pass`: 8
- `fail`: 3

## Split Label Counts

- `calibration`: {'pass': 1}
- `hidden`: {'pass': 2}
- `train`: {'fail': 3, 'pass': 5}
