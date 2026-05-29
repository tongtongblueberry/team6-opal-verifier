# Incremental Adversarial Quality Audit

- parsed candidates: 44
- parse rejects: 76
- instruction mismatches: 0
- parsed input null paths: 0
- parsed bad method args: 0
- exported rows: 29
- exported label counts: {"fail": 10, "pass": 19}
- exported record count counts: {"10": 8, "11": 1, "12": 1, "2": 5, "20": 2, "3": 1, "4": 2, "6": 6, "7": 1, "8": 1, "9": 1}
- exported method counts: {"Activate": 8, "EndSession": 52, "GenKey": 3, "Get": 54, "Properties": 5, "Read": 1, "Set": 29, "StartSession": 72}
- public20 sequence skeleton matches: 0
- public20 method sequence matches: 0
- public20 missing record counts: ["1", "21", "26", "27", "39"]
- public20 missing methods: ["Write"]
- args leaf avg export/public20: 1.7385/2.1031
- final-status rule rate export/public20: 0.7931/0.85
- auth-session row rate export/public20: 0.1034/0.8
- auth-session row rate parsed/combined: 0.0909/0.0952
- public20 exact export matches: 0
- qualitative warnings: ["export_rows_below_200:29", "missing_public_record_counts:1,21,26,27,39", "missing_public_methods:Write", "args_richness_lower_than_public20:1.7385<2.1031", "auth_session_row_rate_lower_than_public20:0.1034<0.8"]

Adversarial conclusion: reject this incremental pool for final handoff unless instruction mismatches, parsed input nulls, bad method args, public20 exact export matches, and public20 sequence skeleton matches are all zero, coverage is broad enough, and exported rows reach the requested final count.
