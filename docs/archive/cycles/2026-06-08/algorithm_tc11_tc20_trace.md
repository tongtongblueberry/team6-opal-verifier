<!-- Changed: archive public20 fail-case pipeline traces for the FSM-shadow algorithm package. -->
<!-- Why: tc11-tc20 need concrete data-to-function-to-prediction provenance, not only architectural summary. -->

# Algorithm Trace Archive - public20 tc11-tc20

작성일: 2026-06-08 KST

## Structural Skeleton

[Original Text/Data] Files analyzed:

```text
data/local/public20/public20_input.jsonl
  - 20 JSONL rows.
  - Each row has sample_id, input, source.
  - input is a JSON string containing {"records": [...]}.

data/local/public20/public20_labels.local.jsonl
  - 20 JSONL rows.
  - Each row has label, sample_id, source.

runs/algorithm/submit/src/solver.py
  - parser helpers
  - ProtocolState
  - StatefulOpalVerifier
  - _run
  - _records
  - _advance_state
  - _final_is_inconsistent
  - _expected_error_for_state
  - _start_session_inconsistent
  - predict / predict_one / Solver.predict

runs/algorithm/submit/src/fsm_shadow.py
  - CandidateAction / Transition / FsmDecision
  - FsmShadow.advance
  - FsmShadow.check_final
  - infer_actions
  - method-specific action candidate builders
  - compact vendored DELTA transition table
```

-> [Exact Interpretation] public20 tc11-tc20 are ten fail-labeled rows, each evaluated as one trajectory whose final record is the only prediction target.
-> [Detailed Explanation/Example] Prefix records build `ProtocolState` and FSM shadow state. The final record goes through existing rulebase final checks and then the FSM-shadow ensemble.

## Shared Function Pipeline

[Original Text/Data] The submit package entrypoints are `predict_one()` and `Solver.predict()`. `predict_one()` calls `StatefulOpalVerifier().verify(testcase)`, while `Solver.predict()` calls `verify_with_trace(steps)`.

References:
- `runs/algorithm/submit/src/solver.py:1202`
- `runs/algorithm/submit/src/solver.py:1213`

-> [Exact Interpretation] local single-case checks and leaderboard-style batch checks enter the same verifier.
-> [Detailed Explanation/Example] The only practical difference is that `Solver.predict()` uses trace mode internally while returning only `{case_id: prediction}`.

[Original Text/Data] `_run()` parses records, updates `ProtocolState` on `records[:-1]`, advances `FsmShadow` on the same prefix records, then checks `records[-1]`.

References:
- `runs/algorithm/submit/src/solver.py:526`
- `runs/algorithm/submit/src/solver.py:651`
- `runs/algorithm/submit/src/solver.py:669`
- `runs/algorithm/submit/src/solver.py:797`
- `runs/algorithm/submit/src/solver.py:548`

-> [Exact Interpretation] The trajectory is the input unit, but the label applies to the final command-response pair.
-> [Detailed Explanation/Example] If a prefix `Set C_PIN` succeeds, later final `StartSession` can be judged against the updated secret. If a prefix `Write` then `GenKey` succeeds, later final `Read` can be judged as stale or fresh.

[Original Text/Data] `FsmShadow.check_final()` maps the final record to abstract action candidates with `infer_actions()`, looks up expected statuses in `DELTA`, and returns `consistent`, `inconsistent`, or `unknown`.

References:
- `runs/algorithm/submit/src/fsm_shadow.py:47`
- `runs/algorithm/submit/src/fsm_shadow.py:78`
- `runs/algorithm/submit/src/fsm_shadow.py:255`

-> [Exact Interpretation] FSM shadow is an expected-status cross-check, not a replacement parser.
-> [Detailed Explanation/Example] If the original rulebase says `fail` and FSM says `unknown`, the final output remains `fail`. If FSM is high-confidence consistent only for selected status-level rules, it can rescue.

## Case Traces

### tc11

[Original Text/Data] `tc11` is line 11 in both public20 files. Label is `fail`. Final record summary:

```text
records=1
final method=Properties
final status=INVALID_PARAMETER
final invoking=Session Manager UID
final return_values=[]
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:11`
- `data/local/public20/public20_labels.local.jsonl:11`

-> [Exact Interpretation] `Properties` was invoked on the correct Session Manager object shape, but it returned an error and no properties payload.
-> [Detailed Explanation/Example] `_final_is_inconsistent()` first records `PROPERTIES_TARGET` as not inconsistent, then `PROPERTIES_PAYLOAD` marks `inconsistent=True` because Properties should return `SUCCESS` with properties. FSM shadow agrees: `expected=['success']`, `actions=['PROPERTIES']`, observed `INVALID_PARAMETER`, final `fail`.

### tc12

[Original Text/Data] `tc12` is line 12 in both public20 files. Label is `fail`. Final record summary:

```text
records=2
prefix: StartSession SUCCESS, no HostChallenge -> active session, auth=False, write=True
final method=Get
final invoking=C_PIN, uid=00 00 00 0B 00 00 84 02
final Cellblock=startColumn 3, endColumn 3
final status=NOT_AUTHORIZED
final return_values=[]
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:12`
- `data/local/public20/public20_labels.local.jsonl:12`

-> [Exact Interpretation] This is treated as a known C_PIN/MSID field read that should succeed; returning `NOT_AUTHORIZED` is inconsistent.
-> [Detailed Explanation/Example] `_final_is_inconsistent()` reaches `KNOWN_FIELD_EXPECTED_SUCCESS` with `expected_success=cpin:3, actual=notauthorized`. FSM shadow maps the final command to `GET_MSID_PIN` and expects `SUCCESS`; observed `NOT_AUTHORIZED` keeps final `fail`.

### tc13

[Original Text/Data] `tc13` is line 13 in both public20 files. Label is `fail`. Key trajectory summary:

```text
records=7
record 5: Set C_PIN SUCCESS, Values[3]=a5a1c7fc3824...
final method=StartSession
final HostChallenge=a5a1c7fc3824...
final status=NOT_AUTHORIZED
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:13`
- `data/local/public20/public20_labels.local.jsonl:13`

-> [Exact Interpretation] The final HostChallenge equals a known secret created by a successful prefix `Set C_PIN`, so final StartSession should succeed, not return `NOT_AUTHORIZED`.
-> [Detailed Explanation/Example] `_advance_state()` stores the new C_PIN in `known_secrets`. `_start_session_inconsistent()` sees `challenge in state.known_secrets and status != success`, so it returns `True`. FSM shadow maps the final command to `START_RW_ADMIN_SID`, expects `SUCCESS`, sees `NOT_AUTHORIZED`, and keeps final `fail`.

### tc14

[Original Text/Data] `tc14` is line 14 in both public20 files. Label is `fail`. Key trajectory summary:

```text
records=10
record 5: Set C_PIN SUCCESS, Values[3]=3e06061d...
record 8: Set C_PIN SUCCESS, Values[3]=f620e538...
final method=StartSession
final HostChallenge=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
final status=SUCCESS
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:14`
- `data/local/public20/public20_labels.local.jsonl:14`

-> [Exact Interpretation] The final HostChallenge is not one of the known C_PIN secrets, so `SUCCESS` is a false success.
-> [Detailed Explanation/Example] `_start_session_inconsistent()` sees `challenge not in state.known_secrets` and expects `NOT_AUTHORIZED`; actual `SUCCESS` makes `inconsistent=True`. FSM shadow maps the final command to `START_RW_ADMIN_SID_WRONG_PW`, expects `NOT_AUTHORIZED`, sees `SUCCESS`, and keeps final `fail`.

### tc15

[Original Text/Data] `tc15` is line 15 in both public20 files. Label is `fail`. Final record summary:

```text
records=9
prefix includes: Set C_PIN SUCCESS, then authenticated StartSession
final method=Activate
final invoking=SP, uid=00 00 01 05 00 00 00 04
final status=SUCCESS
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:15`
- `data/local/public20/public20_labels.local.jsonl:15`

-> [Exact Interpretation] The final Activate target is an invalid SP UID shape for this rulebase; expected status is `INVALID_PARAMETER`, not `SUCCESS`.
-> [Detailed Explanation/Example] `_expected_error_for_state()` calls `_activate_target_invalid()`. Because the UID does not start with `00000205`, expected error becomes `invalidparameter`. `_final_is_inconsistent()` records `PRECONDITION_EXPECTED_ERROR expected=invalidparameter, actual=success`, so final is `fail`. FSM shadow has low-confidence/unknown evidence here and does not override.

### tc16

[Original Text/Data] `tc16` is line 16 in both public20 files. Label is `fail`. Final record summary:

```text
records=21
prefix includes: Locking SP activated
final method=Set
final invoking=Authority, uid=00 00 00 09 00 03 00 01
final Values=[{"5": 1}]
final status=INVALID_PARAMETER
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:16`
- `data/local/public20/public20_labels.local.jsonl:16`

-> [Exact Interpretation] The final Authority column update is a known field operation expected to succeed; returning `INVALID_PARAMETER` is inconsistent.
-> [Detailed Explanation/Example] `_final_is_inconsistent()` reaches `KNOWN_FIELD_EXPECTED_SUCCESS` with `expected_success=authority:5, actual=invalidparameter`. FSM shadow sees possible `SET_AUTHORITY_ENABLED` / `SET_USER_ENABLED` expected `SUCCESS`, but confidence is low after prior abstraction drift, so it stays `unknown` and does not override the base `fail`.

### tc17

[Original Text/Data] `tc17` is line 17 in both public20 files. Label is `fail`. Key trajectory summary:

```text
records=26
prefix includes: Activate Locking SP, Set Authority/User state, Set C_PIN for user/admin authority
final method=StartSession
final SPID=0000020500000002
final HostSigningAuthority=0000000900030001
final HostChallenge=9dd74dd6adfe9be82a1f1204ec8444cda547c2a6cffab3f54871aea6e36ea59f
final status=NOT_AUTHORIZED
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:17`
- `data/local/public20/public20_labels.local.jsonl:17`

-> [Exact Interpretation] The final Locking SP StartSession uses a known credential path that the rulebase expects to succeed; `NOT_AUTHORIZED` is treated as wrong.
-> [Detailed Explanation/Example] Prefix `Set C_PIN` updates `known_secrets`; final `_start_session_inconsistent()` sees a known HostChallenge with non-success status and returns `True`. FSM shadow sees a possible `START_RW_LOCKING_ADMIN1` success path but is low-confidence/unknown, so it does not change the base `fail`.

### tc18

[Original Text/Data] `tc18` is line 18 in both public20 files. Label is `fail`. Final record summary:

```text
records=21
prefix includes: Locking SP activated
final method=Get
final invoking=Locking, uid=00 00 08 02 00 00 00 01
final Cellblock=startColumn 3, endColumn 8
final status=INVALID_PARAMETER
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:18`
- `data/local/public20/public20_labels.local.jsonl:18`

-> [Exact Interpretation] The final Locking table field read is expected to succeed; `INVALID_PARAMETER` is an unexpected error.
-> [Detailed Explanation/Example] `_final_is_inconsistent()` records `KNOWN_FIELD_EXPECTED_SUCCESS expected_success=locking:3,4,5,6,7,8, actual=invalidparameter`. FSM shadow has possible success actions `GET_COLUMN_ORDER_CHECK` and `GET_LOCKING_RANGE`, but confidence is low/unknown, so base `fail` remains.

### tc19

[Original Text/Data] `tc19` is line 19 in both public20 files. Label is `fail`. Final record summary:

```text
records=27
prefix includes: Locking SP activated, MBRControl fields written
final method=Get
final invoking=MBRControl, uid=00 00 08 03 00 00 00 01
final Cellblock=startColumn 1, endColumn 2
final status=FAIL
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:19`
- `data/local/public20/public20_labels.local.jsonl:19`

-> [Exact Interpretation] The final MBRControl field read is expected to succeed; returning `FAIL` is inconsistent.
-> [Detailed Explanation/Example] Prefix `Set` operations update object fields for MBRControl columns. `_final_is_inconsistent()` records `KNOWN_FIELD_EXPECTED_SUCCESS expected_success=mbrcontrol:1,2, actual=fail`. FSM shadow returns `unknown` with no expected status, so base `fail` remains.

### tc20

[Original Text/Data] `tc20` is line 20 in both public20 files. Label is `fail`. Key trajectory summary:

```text
records=39
record 33: DATA Write LBA="80 ~ 87", pattern="8E", result="pass"
record 34: DATA Read LBA="80 ~ 87", result="Pattern 8E"
record 37: GenKey SUCCESS
final record 39: DATA Read LBA="80 ~ 87", result="8E"
prediction=fail
```

References:
- `data/local/public20/public20_input.jsonl:20`
- `data/local/public20/public20_labels.local.jsonl:20`

-> [Exact Interpretation] After a successful GenKey following a write, returning the old written pattern on final Read is stale payload behavior.
-> [Detailed Explanation/Example] `_advance_state()` records `WRITE_PAYLOAD_EFFECT address=80 ~ 87` at record 33. Later `GENKEY_EFFECT after_write=True` at record 37 marks the media key changed after a write. Final `_read_payload_inconsistent()` sees final Read returning the old payload pattern and records `READ_PAYLOAD inconsistent=True`. FSM shadow is `unknown` here and does not override the base `fail`.

## Summary

[Original Text/Data] All tc11-tc20 rows have `label=fail` and the FSM-shadow submit package predicts `fail`.

```text
tc11 fail: Properties returned INVALID_PARAMETER instead of SUCCESS + payload.
tc12 fail: C_PIN/MSID Get returned NOT_AUTHORIZED instead of SUCCESS.
tc13 fail: known C_PIN StartSession returned NOT_AUTHORIZED instead of SUCCESS.
tc14 fail: wrong C_PIN StartSession returned SUCCESS instead of NOT_AUTHORIZED.
tc15 fail: invalid Activate SP target returned SUCCESS instead of INVALID_PARAMETER.
tc16 fail: Authority Set returned INVALID_PARAMETER instead of SUCCESS.
tc17 fail: known Locking SP StartSession returned NOT_AUTHORIZED instead of SUCCESS.
tc18 fail: Locking Get returned INVALID_PARAMETER instead of SUCCESS.
tc19 fail: MBRControl Get returned FAIL instead of SUCCESS.
tc20 fail: Read after GenKey returned stale written payload.
```

-> [Exact Interpretation] The public20 fail half is mostly final-response inconsistency, not prefix-error failure.
-> [Detailed Explanation/Example] Prefix records create state: known C_PINs, active/authenticated sessions, activated SPs, object field values, written payloads, and GenKey-after-write flags. The final record then contradicts one of those state-derived expectations.
