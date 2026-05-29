# Incremental Adversarial Quality Audit

- parsed candidates: 148
- parse rejects: 236
- instruction mismatches: 0
- parsed input null paths: 0
- parsed bad method args: 0
- exported rows: 47
- exported label counts: {"fail": 31, "pass": 16}
- exported record count counts: {"1": 2, "10": 10, "11": 2, "2": 7, "21": 16, "26": 2, "7": 7, "9": 1}
- exported method counts: {"Activate": 26, "EndSession": 141, "Get": 161, "Read": 1, "Set": 76, "StartSession": 179}
- public20 sequence skeleton matches: 0
- public20 method sequence matches: 11
- public20 missing record counts: ["27", "39"]
- public20 missing methods: ["GenKey", "Properties", "Write"]
- args leaf avg export/public20: 1.6106/2.1031
- final-status rule rate export/public20: 0.8936/0.85
- public20 exact export matches: 0
- qualitative warnings: ["export_rows_below_200:47", "public20_method_sequence_matches:11", "missing_public_record_counts:27,39", "missing_public_methods:GenKey,Properties,Write", "args_richness_lower_than_public20:1.6106<2.1031", "final_status_rule_more_predictive_than_public20:0.8936>0.85", "record_count_label_shortcut_high:0.9574"]

Adversarial conclusion: reject this incremental pool for final handoff unless instruction mismatches, parsed input nulls, bad method args, public20 exact export matches, and public20 sequence skeleton matches are all zero, coverage is broad enough, and exported rows reach the requested final count.
