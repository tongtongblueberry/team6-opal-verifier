# Incremental Adversarial Quality Audit

- parsed candidates: 8
- parse rejects: 64
- instruction mismatches: 0
- parsed input null paths: 0
- parsed bad method args: 0
- exported rows: 0
- exported label counts: {}
- exported record count counts: {}
- exported method counts: {}
- public20 sequence skeleton matches: 0
- public20 method sequence matches: 0
- public20 missing record counts: ["1", "10", "11", "2", "21", "26", "27", "39", "7", "9"]
- public20 missing methods: ["Activate", "EndSession", "GenKey", "Get", "Properties", "Read", "Set", "StartSession", "Write"]
- args leaf avg export/public20: 0.0/2.1031
- final-status rule rate export/public20: 0.0/0.85
- auth-session row rate export/public20: 0.0/0.8
- auth-session row rate parsed/combined: 0.0/0.0
- public20 exact export matches: 0
- qualitative warnings: ["export_rows_below_200:0", "missing_public_record_counts:1,10,11,2,21,26,27,39,7,9", "missing_public_methods:Activate,EndSession,GenKey,Get,Properties,Read,Set,StartSession,Write", "args_richness_lower_than_public20:0.0<2.1031", "auth_session_row_rate_lower_than_public20:0.0<0.8"]

Adversarial conclusion: reject this incremental pool for final handoff unless instruction mismatches, parsed input nulls, bad method args, public20 exact export matches, and public20 sequence skeleton matches are all zero, coverage is broad enough, and exported rows reach the requested final count.
