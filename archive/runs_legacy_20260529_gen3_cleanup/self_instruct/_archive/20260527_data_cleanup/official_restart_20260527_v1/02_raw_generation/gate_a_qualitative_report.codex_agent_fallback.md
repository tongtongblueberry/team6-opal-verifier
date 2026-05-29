# Gate A Codex-Agent Fallback Qualitative Review

- audit_provider: `codex_agent_fallback_qualitative_audit`
- audit_model: `codex_agent_fallback_qualitative_audit`
- note: offline fallback review, not Gemini, not a runtime rule engine, not package inference logic
- reviewed_count: 11
- accepted_count: 11
- rejected_count: 0
- status: `pass`

## codex-agent-fallback-self-instruct-gen-00000-01

[Original Text/Data] final={"return_values": [{"MaxComPacketSize": 2048, "MaxSessions": 8, "uid": "LockingSP.Properties"}], "status_codes": "SUCCESS"}; spans=['docs/legacy_spec_rules.md:10-16']
-> [Exact Interpretation] The final response is the Get SUCCESS at records[-1].output, not the earlier StartSession or Authenticate responses.
-> [Detailed Explanation/Example] StartSession opens rw-admin-01 for AdminSP with Write=True; Authenticate marks SID authenticated on rw-admin-01; final Get requests MaxSessions and MaxComPacketSize from LockingSP.Properties and returns SUCCESS with those values. RULE 01 states that a method processed completely and without error returns SUCCESS. The trajectory presents a successful authenticated setup and a final Get returning requested properties, so the generated pass label is supported for the final response.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00000-02

[Original Text/Data] final={"return_values": [], "status_codes": "INVALID_PARAMETER"}; spans=['docs/legacy_spec_rules.md:17-23']
-> [Exact Interpretation] The final response is the Set INVALID_PARAMETER at records[-1].output.
-> [Detailed Explanation/Example] StartSession opens ro-locking-02 for LockingSP with HostSigningAuthority=Anybody and Write=False; a Get on ReadLocked succeeds; final Set tries to write ReadLocked=True in that read-only/unauthenticated write context and returns INVALID_PARAMETER. RULE 02 expects NOT_AUTHORIZED when ACL is not satisfied. The final response uses INVALID_PARAMETER for the authorization failure context, so the generated fail label is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00000-03

[Original Text/Data] final={"return_values": [], "status_codes": "SP_BUSY"}; spans=['docs/legacy_spec_rules.md:31-37']
-> [Exact Interpretation] The final response is the second StartSession SP_BUSY.
-> [Detailed Explanation/Example] Record 0 opens a read-write LockingSP session and no close/end record appears; final StartSession requests another read-write LockingSP session and receives SP_BUSY. RULE 04 expects SP_BUSY when opening a read-write session to an SP that already has an open session. The final response matches that condition, so pass is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00001-01

[Original Text/Data] final={"return_values": [], "status_codes": "INVALID_PARAMETER"}; spans=['docs/legacy_spec_rules.md:52-58']
-> [Exact Interpretation] The final response is the StartSession INVALID_PARAMETER.
-> [Detailed Explanation/Example] The only record is the final StartSession with HostSigningAuthority=Admins and output INVALID_PARAMETER. RULE 07 explicitly names HostSigningAuthority=Admins as a class-authority example requiring INVALID_PARAMETER. The generated pass label is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00001-02

[Original Text/Data] final={"return_values": [], "status_codes": "NOT_AUTHORIZED"}; spans=['docs/legacy_spec_rules.md:77-83']
-> [Exact Interpretation] The final response is the second StartSession NOT_AUTHORIZED.
-> [Detailed Explanation/Example] Record 0 opens a read-write AdminSP session and leaves it open; final StartSession requests another read-write AdminSP session and returns NOT_AUTHORIZED. RULE 10 expects SP_BUSY for a second concurrent read-write session to the same SP. The final NOT_AUTHORIZED response is the wrong status for the cited state, so fail is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00001-03

[Original Text/Data] final={"return_values": [], "status_codes": "NOT_AUTHORIZED"}; spans=['docs/legacy_spec_rules.md:84-90', 'docs/legacy_spec_rules.md:91-97']
-> [Exact Interpretation] The final response is the Set NOT_AUTHORIZED.
-> [Detailed Explanation/Example] StartSession opens ro-locking-06 for LockingSP with Write=False; final Set tries to set ReadLocked=True and returns NOT_AUTHORIZED. RULE 12 identifies Write=False as read-only session state, and RULE 11 allows NOT_AUTHORIZED for Set in a read-only session. The generated pass label is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00002-01

[Original Text/Data] final={"return_values": [], "status_codes": "INVALID_PARAMETER"}; spans=['docs/legacy_spec_rules.md:98-104']
-> [Exact Interpretation] The final response is the StartSession INVALID_PARAMETER.
-> [Detailed Explanation/Example] Properties returns MinSessionTimeout=1000 and MaxSessionTimeout=60000; final StartSession requests session_timeout=999999 and returns INVALID_PARAMETER. RULE 13 expects INVALID_PARAMETER when SessionTimeout is outside the allowed range. The generated pass label is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00002-02

[Original Text/Data] final={"return_values": [], "status_codes": "NOT_AUTHORIZED"}; spans=['docs/legacy_spec_rules.md:116-122']
-> [Exact Interpretation] The final response is the Get NOT_AUTHORIZED.
-> [Detailed Explanation/Example] StartSession opens rw-locking-08; final Get targets LockingRange.DoesNotExist and returns NOT_AUTHORIZED. RULE 15 expects FAIL or INVALID_PARAMETER for a Get on a non-existent object. The final NOT_AUTHORIZED status is inconsistent with the cited expected status, so fail is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00002-03

[Original Text/Data] final={"return_values": [{"column": "UID", "value": "C_PIN.SID"}, {"column": "CommonName", "value": "SID"}], "status_codes": "SUCCESS"}; spans=['docs/legacy_spec_rules.md:137-143']
-> [Exact Interpretation] The final response is the Get SUCCESS with PIN omitted.
-> [Detailed Explanation/Example] StartSession opens ro-admin-09 as Anybody; final Get requests UID, CommonName, and PIN on C_PIN.SID, but returns only UID and CommonName with SUCCESS. RULE 18 expects SUCCESS with unauthorized cells omitted from the result. The final response omits PIN rather than returning it, so pass is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00003-01

[Original Text/Data] final={"return_values": [], "status_codes": "SUCCESS"}; spans=['docs/legacy_spec_rules.md:144-150']
-> [Exact Interpretation] The final response is the byte-table Get SUCCESS with no returned data.
-> [Detailed Explanation/Example] StartSession opens ro-locking-10 as Anybody; final Get requests a byte range from DataStore.ByteTable and returns SUCCESS with an empty result list. RULE 19 expects SUCCESS with empty results when byte-table ACL access is not satisfied. The final response matches that shape, so pass is supported.
-> [Audit Decision] accept

## codex-agent-fallback-self-instruct-gen-00003-03

[Original Text/Data] final={"return_values": [], "status_codes": "INVALID_PARAMETER"}; spans=['docs/legacy_spec_rules.md:169-175']
-> [Exact Interpretation] The final response is the Set INVALID_PARAMETER.
-> [Detailed Explanation/Example] StartSession opens rw-locking-12; final Set on LockingRange.GlobalRange includes ReadLocked twice with different values and returns INVALID_PARAMETER. RULE 22 expects INVALID_PARAMETER when the same column appears multiple times in one Set invocation. The generated pass label is supported.
-> [Audit Decision] accept
