# Incremental Adversarial Quality Audit

- parsed candidates: 21
- parse rejects: 51
- instruction mismatches: 0
- parsed input null paths: 0
- parsed bad method args: 0
- exported rows: 1
- exported label counts: {"pass": 1}
- exported record count counts: {"7": 1}
- exported method counts: {"EndSession": 2, "Get": 3, "StartSession": 2}
- public20 sequence skeleton matches: 0
- public20 method sequence matches: 0
- public20 missing record counts: ["1", "10", "11", "2", "21", "26", "27", "39", "9"]
- public20 missing methods: ["Activate", "GenKey", "Properties", "Read", "Set", "Write"]
- args leaf avg export/public20: 1.5714/2.1031
- final-status rule rate export/public20: 1.0/0.85
- auth-session row rate export/public20: 1.0/0.8
- auth-session row rate parsed/combined: 0.8095/1.0
- public20 exact export matches: 0
- qualitative warnings: ["export_rows_below_200:1", "missing_public_record_counts:1,10,11,2,21,26,27,39,9", "missing_public_methods:Activate,GenKey,Properties,Read,Set,Write", "args_richness_lower_than_public20:1.5714<2.1031", "final_status_rule_more_predictive_than_public20:1.0>0.85", "record_count_label_shortcut_high:1.0"]

Adversarial conclusion: reject this incremental pool for final handoff unless instruction mismatches, parsed input nulls, bad method args, public20 exact export matches, and public20 sequence skeleton matches are all zero, coverage is broad enough, and exported rows reach the requested final count.
