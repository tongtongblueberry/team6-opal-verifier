# Archived384 Adversarial Quality Audit

- raw rows: 384
- parsed/dedup/exported: 148/135/55
- labels: {"fail": 36, "pass": 19}
- hard gates: instruction_mismatch=0, input_null=0, bad_args=0, public_exact=0, public_skeleton=0, duplicate_export=0
- auth row rate export/public20: 0.0/0.8
- record-count label shortcut: 52/55 = 0.9455
- final-status label shortcut: 49/55 = 0.8909
- missing methods: ["GenKey", "Properties", "Write"]
- missing record counts: ["27", "39"]
- warnings: ["export_rows_below_200:55", "missing_public_methods:GenKey,Properties,Write", "missing_public_record_counts:27,39", "auth_session_row_rate_lower_than_public20:0.0<0.8", "dedup_candidates_auth_session_rows_zero", "record_count_label_shortcut_high:0.9455", "final_status_rule_more_predictive_than_public20:0.8909>0.85", "args_richness_lower_than_public20:1.7651<2.1031"]

Conclusion: this rebuild is acceptable only as an interim archived-raw export. It is not the corrected auth-strict generation pool.
