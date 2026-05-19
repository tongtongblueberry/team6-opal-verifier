# TCG/Opal SSD Specification Rules for Training Data Generation

Extracted from TCG Core Spec and Opal SSC v2.30 specification documents.
Each rule is a testable condition from "SHALL" requirements that can be used to generate pass/fail training data.

---

## CATEGORY 1: STATUS CODE RULES (core/5.1.5.*)

### RULE 01: SUCCESS on complete method processing
- SPEC: 5.1.5.1
- CONDITION: A method is processed completely and without error by the TPer
- EXPECTED_STATUS: SUCCESS (0x00)
- IF_VIOLATED: fail — if the TPer returns SUCCESS but the method was not processed correctly, the trajectory is non-compliant
- EXAMPLE_TRAJECTORY: Any well-formed Get/Set/Authenticate method with correct parameters and proper authorization returns SUCCESS

### RULE 02: NOT_AUTHORIZED when no AccessControl row exists
- SPEC: 5.1.5.2
- CONDITION: No row in AccessControl table for the InvokingID/MethodID combination, or the ACL has not been satisfied
- EXPECTED_STATUS: NOT_AUTHORIZED (0x01)
- IF_VIOLATED: fail — method should have been rejected
- EXAMPLE_TRAJECTORY: User attempts Set on a Locking range without authenticating an authority that satisfies the ACL

### RULE 03: NOT_AUTHORIZED on wrong password in SyncSession
- SPEC: 5.1.5.2
- CONDITION: HostSigningAuthority has Operation=Password in Authority table, and HostChallenge does not match the required password
- EXPECTED_STATUS: NOT_AUTHORIZED (as SyncSession status)
- IF_VIOLATED: fail — authentication should have been rejected
- EXAMPLE_TRAJECTORY: StartSession with HostSigningAuthority=SID and wrong HostChallenge value; SyncSession returns NOT_AUTHORIZED

### RULE 04: SP_BUSY on concurrent session conflict
- SPEC: 5.1.5.3
- CONDITION: Attempt to open Read-Write session to SP when any other session to that SP is open, or Read-Only session when Read-Write is open
- EXPECTED_STATUS: SP_BUSY (0x03) as SyncSession status
- IF_VIOLATED: fail — session concurrency violated
- EXAMPLE_TRAJECTORY: Open RW session to LockingSP, then attempt another RW session to LockingSP without closing the first

### RULE 05: SP_FROZEN when SP is in Frozen state
- SPEC: 5.1.5.6
- CONDITION: Host attempts to start session to SP in Issued-Frozen or Issued-Disabled-Frozen state
- EXPECTED_STATUS: SP_FROZEN (0x06) as SyncSession status
- IF_VIOLATED: fail — session should not be permitted
- EXAMPLE_TRAJECTORY: StartSession to SP that is in Frozen lifecycle state

### RULE 06: NO_SESSIONS_AVAILABLE when max sessions reached
- SPEC: 5.1.5.7
- CONDITION: Attempt to open session when maximum concurrent sessions are all in use
- EXPECTED_STATUS: NO_SESSIONS_AVAILABLE (0x07)
- IF_VIOLATED: fail — TPer should reject the session
- EXAMPLE_TRAJECTORY: Open MaxSessions sessions, then attempt one more

### RULE 07: INVALID_PARAMETER on class authority as HostSigningAuthority
- SPEC: 5.1.5.11
- CONDITION: StartSession's HostSigningAuthority parameter is a class authority
- EXPECTED_STATUS: INVALID_PARAMETER (0x0C) as SyncSession status
- IF_VIOLATED: fail — class authorities cannot be directly authenticated
- EXAMPLE_TRAJECTORY: StartSession with HostSigningAuthority = Admins (a class authority); SyncSession returns INVALID_PARAMETER

### RULE 08: INVALID_PARAMETER on bad parameter values
- SPEC: 5.1.5.11
- CONDITION: Method invocation has invalid parameters (wrong type, out of range, etc.)
- EXPECTED_STATUS: INVALID_PARAMETER (0x0C)
- IF_VIOLATED: fail — TPer should reject malformed invocations
- EXAMPLE_TRAJECTORY: Set method with value larger than column type allows

### RULE 09: AUTHORITY_LOCKED_OUT on exceeded TryLimit
- SPEC: 5.1.5.15
- CONDITION: C_PIN object's Tries equals TryLimit (and TryLimit != 0), or Uses reached Limit
- EXPECTED_STATUS: AUTHORITY_LOCKED_OUT (0x12) or SUCCESS with result=False
- IF_VIOLATED: fail — locked-out authority should not succeed
- EXAMPLE_TRAJECTORY: Authenticate with authority whose C_PIN Tries == TryLimit

---

## CATEGORY 2: SESSION RULES (core/3.3.7.1, core/5.2.3.1.*)

### RULE 10: Only one Read-Write session per SP at a time
- SPEC: 3.3.7.1
- CONDITION: For a specific SP, only one Read-Write session SHALL be open at a time; RO and RW are mutually exclusive
- EXPECTED_STATUS: SP_BUSY if violated
- IF_VIOLATED: fail — session exclusivity rule broken
- EXAMPLE_TRAJECTORY: Two concurrent RW sessions to the same SP

### RULE 11: Read-Only sessions SHALL NOT make permanent changes
- SPEC: 3.3.7.1
- CONDITION: Explicit changes made during Read-Only session SHALL NOT be made permanent (exceptions: PIN blocking, log updates)
- EXPECTED_STATUS: Method succeeds but changes are not persistent; or NOT_AUTHORIZED for Set
- IF_VIOLATED: fail — if Set method permanently modifies data in a RO session
- EXAMPLE_TRAJECTORY: Open RO session to LockingSP, attempt Set on Locking table column

### RULE 12: Write parameter TRUE for Read-Write session
- SPEC: 5.2.3.1.3
- CONDITION: Write parameter SHALL be True for Read-Write session, False for Read-Only
- EXPECTED_STATUS: Session type matches Write parameter
- IF_VIOLATED: fail — session type misidentified
- EXAMPLE_TRAJECTORY: StartSession with Write=False, then attempt Set method (should fail or changes not persist)

### RULE 13: SessionTimeout out of range causes failure
- SPEC: 5.2.3.1.9
- CONDITION: SessionTimeout value is outside MinSessionTimeout to MaxSessionTimeout/SPSessionTimeout limits
- EXPECTED_STATUS: Method invocation SHALL fail (INVALID_PARAMETER)
- IF_VIOLATED: fail — out-of-range timeout should be rejected
- EXAMPLE_TRAJECTORY: StartSession with SessionTimeout larger than MaxSessionTimeout property

### RULE 14: TransTimeout out of range causes failure
- SPEC: 5.2.3.1.10
- CONDITION: TransTimeout value is outside MinTransTimeout to MaxTransTimeout limits
- EXPECTED_STATUS: Method invocation SHALL fail (INVALID_PARAMETER)
- IF_VIOLATED: fail — out-of-range timeout should be rejected
- EXAMPLE_TRAJECTORY: StartSession with TransTimeout larger than MaxTransTimeout property

---

## CATEGORY 3: GET METHOD RULES (core/5.3.3.6.*, 5.3.4.2.2)

### RULE 15: Get fails if table/object doesn't exist
- SPEC: 5.3.3.6.3(a)
- CONDITION: Get invoked on non-existent table or object
- EXPECTED_STATUS: FAIL or INVALID_PARAMETER
- IF_VIOLATED: fail — non-existent objects should cause method failure
- EXAMPLE_TRAJECTORY: Get on UID that doesn't exist in SP

### RULE 16: Object Get fails if Cellblock contains row or table values
- SPEC: 5.3.3.6.3(b)
- CONDITION: Object method's Cellblock parameter contains row values or a table value
- EXPECTED_STATUS: FAIL or INVALID_PARAMETER
- IF_VIOLATED: fail — Cellblock mismatch
- EXAMPLE_TRAJECTORY: ObjectUID.Get with Where parameter containing row specification

### RULE 17: Byte table Get fails with column values in Cellblock
- SPEC: 5.3.3.6.3(c)
- CONDITION: Get on byte table with column values in Cellblock parameter
- EXPECTED_STATUS: FAIL or INVALID_PARAMETER
- IF_VIOLATED: fail — byte tables don't have columns
- EXAMPLE_TRAJECTORY: MBR.Get with column numbers in Cellblock

### RULE 18: Get returns only authorized columns (non-error omission)
- SPEC: 5.3.4.2.2
- CONDITION: Get is invoked; cells not permitted by ACL are omitted from results (not an error)
- EXPECTED_STATUS: SUCCESS, but restricted columns are omitted from result
- IF_VIOLATED: pass if columns are omitted; fail if unauthorized columns are returned
- EXAMPLE_TRAJECTORY: Anybody-authenticated Get on C_PIN_SID object — PIN column should be omitted

### RULE 19: Byte table Get returns empty list if ACL not satisfied
- SPEC: 5.3.4.2.2
- CONDITION: Get on byte table when authenticated authorities don't satisfy access control
- EXPECTED_STATUS: SUCCESS with empty results list
- IF_VIOLATED: fail if non-empty data returned without authorization
- EXAMPLE_TRAJECTORY: Anybody session attempts Get on DataStore table without Admin authentication

### RULE 20: Get RowValues returned in Column table order
- SPEC: 5.3.3.6.2.2
- CONDITION: Column name-value pairs SHALL be returned in the order listed in the Column table
- EXPECTED_STATUS: SUCCESS with properly ordered result
- IF_VIOLATED: fail — response format violation
- EXAMPLE_TRAJECTORY: Get on Locking range object; verify column ordering in response

---

## CATEGORY 4: SET METHOD RULES (core/5.3.3.7.*, 5.3.4.2.6)

### RULE 21: Set fails entirely if any cell is not authorized (NOT_AUTHORIZED)
- SPEC: 5.3.4.2.6
- CONDITION: Set invoked but ACL does not permit some cell to be changed
- EXPECTED_STATUS: NOT_AUTHORIZED — entire method fails
- IF_VIOLATED: fail — partial writes should not be possible
- EXAMPLE_TRAJECTORY: Admin-auth session tries Set on Locking range, includes column not in ACE's Columns list

### RULE 22: Same column multiple times in Set causes INVALID_PARAMETER
- SPEC: 5.3.4.2.6
- CONDITION: Including the same column multiple times in a single Set method invocation
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — duplicate columns should be rejected
- EXAMPLE_TRAJECTORY: Set on Locking range with ReadLocked=True, ReadLocked=False in same invocation

### RULE 23: Object Set fails if Where parameter included
- SPEC: 5.3.3.7.1.1
- CONDITION: For Object.Set, if a value for the Where parameter is included, method SHALL fail
- EXPECTED_STATUS: Error status code (INVALID_PARAMETER)
- IF_VIOLATED: fail — Object.Set doesn't take Where
- EXAMPLE_TRAJECTORY: ObjectUID.Set with Where parameter specified

### RULE 24: Table.Set on object table without Where fails
- SPEC: 5.3.3.7.1.1
- CONDITION: Table.Set on object table without a value for Where parameter SHALL fail
- EXPECTED_STATUS: Error status code (INVALID_PARAMETER)
- IF_VIOLATED: fail — must specify which row
- EXAMPLE_TRAJECTORY: LockingTable.Set with RowValues but no Where=UID parameter

### RULE 25: Set on object table requires Values as RowValues
- SPEC: 5.3.3.7.2
- CONDITION: Set on object/object table requires Values as RowValues option; Bytes option SHALL fail
- EXPECTED_STATUS: Error status code (INVALID_PARAMETER)
- IF_VIOLATED: fail — wrong Values type
- EXAMPLE_TRAJECTORY: Locking object Set with Bytes parameter instead of RowValues

### RULE 26: Set on byte table requires Values as Bytes
- SPEC: 5.3.3.7.2
- CONDITION: Set on byte table requires Values as Bytes option; RowValues SHALL fail
- EXPECTED_STATUS: Error status code (INVALID_PARAMETER)
- IF_VIOLATED: fail — wrong Values type
- EXAMPLE_TRAJECTORY: MBR table Set with RowValues instead of Bytes

### RULE 27: Set with no Values parameter succeeds with no effect
- SPEC: 5.3.3.7.2
- CONDITION: Set method invoked without Values parameter
- EXPECTED_STATUS: SUCCESS (no effect)
- IF_VIOLATED: fail if method fails when Values is omitted
- EXAMPLE_TRAJECTORY: Locking object Set with Where but no Values — should succeed doing nothing

### RULE 28: Set fails when attempting to change UID or system cell
- SPEC: 5.3.3.7.4(b)
- CONDITION: Attempt to change UID column or other system cell
- EXPECTED_STATUS: Error status (INVALID_PARAMETER)
- IF_VIOLATED: fail — system cells are immutable
- EXAMPLE_TRAJECTORY: Set on Authority object trying to change UID column

---

## CATEGORY 5: AUTHENTICATE METHOD RULES (core/5.3.3.12.*, 5.3.4.1.14.1)

### RULE 29: Authenticate with non-existent authority returns INVALID_PARAMETER
- SPEC: 5.3.4.1.14.1 (Awaiting Challenge state, condition 1a)
- CONDITION: Invalid authority (doesn't exist in Authority table) supplied to Authenticate
- EXPECTED_STATUS: INVALID_PARAMETER with empty result list
- IF_VIOLATED: fail — non-existent authority should be rejected
- EXAMPLE_TRAJECTORY: Authenticate with Authority=0x0000000900FF0001 (non-existent UID)

### RULE 30: Authenticate with class authority returns INVALID_PARAMETER
- SPEC: 5.3.4.1.14.1 (Awaiting Challenge state, condition 1b)
- CONDITION: Class authority supplied to Authenticate method
- EXPECTED_STATUS: INVALID_PARAMETER with empty result list
- IF_VIOLATED: fail — class authorities cannot be directly authenticated
- EXAMPLE_TRAJECTORY: Authenticate with Authority=Admins (IsClass=True)

### RULE 31: Authenticate Password authority returns SUCCESS/True on correct password
- SPEC: 5.3.4.1.14.1 (Awaiting Challenge state, condition 3)
- CONDITION: Valid individual authority with Operation=Password, correct password, authority enabled
- EXPECTED_STATUS: SUCCESS with result=True
- IF_VIOLATED: fail — correct credentials should succeed
- EXAMPLE_TRAJECTORY: Authenticate with Authority=Admin1, Proof=correct_password; returns True

### RULE 32: Authenticate Password authority returns SUCCESS/False on wrong password
- SPEC: 5.3.4.1.14.1 (Awaiting Challenge state, condition 5b)
- CONDITION: Valid authority, Operation=Password, but incorrect password submitted
- EXPECTED_STATUS: SUCCESS with result=False
- IF_VIOLATED: fail — wrong password should return False, not error
- EXAMPLE_TRAJECTORY: Authenticate with Authority=Admin1, Proof=wrong_password; returns False

### RULE 33: Authenticate with disabled authority returns SUCCESS/False
- SPEC: 5.3.4.1.14.1 (Awaiting Challenge state, condition 5a)
- CONDITION: Authority is valid but disabled (Enabled=False)
- EXPECTED_STATUS: SUCCESS with result=False
- IF_VIOLATED: fail — disabled authority should fail authentication
- EXAMPLE_TRAJECTORY: Authenticate with Authority=User1 (Enabled=False by default in OFS); returns False

### RULE 34: Authenticate with Exchange-operation authority returns SUCCESS/False
- SPEC: 5.3.4.1.14.1 (Awaiting Challenge state, condition 5a)
- CONDITION: Authority with Operation=Exchange invoked in Authenticate
- EXPECTED_STATUS: SUCCESS with result=False
- IF_VIOLATED: fail — Exchange authorities SHALL NOT be authenticated explicitly
- EXAMPLE_TRAJECTORY: Authenticate with an Exchange-type authority; returns False

### RULE 35: Authenticate Anybody always succeeds
- SPEC: 5.3.4.1.2.1
- CONDITION: Authenticate method invoked with Anybody authority
- EXPECTED_STATUS: SUCCESS with result=True (always)
- IF_VIOLATED: fail — Anybody always succeeds
- EXAMPLE_TRAJECTORY: Authenticate with Authority=Anybody; returns True regardless of Proof

### RULE 36: MaxAuthentications exceeded causes SUCCESS/False
- SPEC: 5.3.4.1.14
- CONDITION: Authentication attempt would exceed MaxAuthentications limit for the session
- EXPECTED_STATUS: SUCCESS with result=False
- IF_VIOLATED: fail — should not exceed max authentications
- EXAMPLE_TRAJECTORY: Authenticate MaxAuthentications+1 authorities in one session; last returns False

---

## CATEGORY 6: C_PIN / TRY LIMIT RULES (core/5.3.4.1.1.2)

### RULE 37: Tries incremented on failed authentication
- SPEC: 5.3.4.1.1.2
- CONDITION: TryLimit is not 0; authentication fails
- EXPECTED_STATUS: Tries column incremented by 1
- IF_VIOLATED: fail if Tries not incremented
- EXAMPLE_TRAJECTORY: Wrong password attempt; check that Tries column increased

### RULE 38: Tries reset to 0 on successful authentication
- SPEC: 5.3.4.1.1.2
- CONDITION: Successful authentication (Authenticate or session startup) of authority
- EXPECTED_STATUS: Tries column set to 0
- IF_VIOLATED: fail if Tries not reset
- EXAMPLE_TRAJECTORY: After successful Authenticate, Get C_PIN object and verify Tries=0

### RULE 39: Tries SHALL NOT increment beyond TryLimit
- SPEC: 5.3.4.1.1.2
- CONDITION: Tries already equals TryLimit; another failed attempt
- EXPECTED_STATUS: Tries remains at TryLimit (does not exceed)
- IF_VIOLATED: fail if Tries > TryLimit
- EXAMPLE_TRAJECTORY: After TryLimit failures, attempt one more; Tries should remain at TryLimit

### RULE 40: TryLimit=0 means unlimited tries; Tries stays 0
- SPEC: 5.3.4.1.1.2
- CONDITION: TryLimit is 0
- EXPECTED_STATUS: No limit on Tries; Tries SHALL remain 0
- IF_VIOLATED: fail if Tries changes when TryLimit=0
- EXAMPLE_TRAJECTORY: Multiple failed auths with TryLimit=0; Tries stays 0

### RULE 41: Tries reset to 0 on PIN column modification (GenKey/Set/SetPackage)
- SPEC: 5.3.4.1.1.2
- CONDITION: Successful Set/GenKey/SetPackage modifying PIN column of C_PIN object
- EXPECTED_STATUS: Tries set to 0
- IF_VIOLATED: fail — PIN change should reset Tries
- EXAMPLE_TRAJECTORY: Set C_PIN PIN value; verify Tries becomes 0

### RULE 42: Tries reset to 0 after power cycle if Persistence=False
- SPEC: 5.3.4.1.1.2
- CONDITION: Power cycle occurs and C_PIN Persistence column is False
- EXPECTED_STATUS: Tries reset to 0
- IF_VIOLATED: fail — Persistence=False means non-persistent
- EXAMPLE_TRAJECTORY: Fail auth, power cycle, check Tries=0

---

## CATEGORY 7: AUTHORITY OPERATION TYPE RULES (core/5.3.4.1.3)

### RULE 43: Password authority used as Exchange results in error
- SPEC: 5.3.4.1.3(b)
- CONDITION: Authority with Operation=Password referenced as Exchange authority during session startup
- EXPECTED_STATUS: Error (INVALID_PARAMETER)
- IF_VIOLATED: fail — wrong operation type for role
- EXAMPLE_TRAJECTORY: StartSession with HostExchangeAuthority pointing to a Password-type authority

### RULE 44: Exchange authority cannot be authenticated via Authenticate method
- SPEC: 5.3.4.1.3(d)
- CONDITION: Authority with Operation=Exchange invoked in Authenticate method
- EXPECTED_STATUS: Exchange authority SHALL NOT be authenticatable explicitly
- IF_VIOLATED: fail — Exchange-only authorities cannot use Authenticate
- EXAMPLE_TRAJECTORY: Authenticate with authority whose Operation=Exchange

### RULE 45: TPerSign authority SHALL only be SPSigningAuthority
- SPEC: 5.3.4.1.3(g)
- CONDITION: Authority with Operation=TPerSign referenced in non-SPSigningAuthority parameter
- EXPECTED_STATUS: Error
- IF_VIOLATED: fail — TPerSign is SP-signing only
- EXAMPLE_TRAJECTORY: StartSession with HostSigningAuthority=TPerSign authority

---

## CATEGORY 8: OPAL SESSION RULES (opal/4.1.1.2)

### RULE 46: Opal Write=True is mandatory; Write=False may or may not be supported
- SPEC: opal/4.1.1.2
- CONDITION: StartSession with Write=True SHALL be supported
- EXPECTED_STATUS: SUCCESS (SyncSession)
- IF_VIOLATED: fail — RW session support is mandatory
- EXAMPLE_TRAJECTORY: StartSession to AdminSP/LockingSP with Write=True and valid credentials

### RULE 47: SessionTimeout outside valid range causes failure
- SPEC: opal/4.1.1.2
- CONDITION: SessionTimeout not satisfying: (a) <= MaxSessionTimeout, (b) <= SPSessionTimeout, (c) >= MinSessionTimeout
- EXPECTED_STATUS: StartSession SHALL fail (INVALID_PARAMETER)
- IF_VIOLATED: fail — invalid SessionTimeout must be rejected
- EXAMPLE_TRAJECTORY: StartSession with SessionTimeout=999999999 (above MaxSessionTimeout)

---

## CATEGORY 9: OPAL LIFECYCLE / ACTIVATE / REVERT RULES (opal/5.1.*)

### RULE 48: Activate on Manufactured-Inactive SP transitions to Manufactured
- SPEC: opal/5.1.1
- CONDITION: Activate invoked on SP in Manufactured-Inactive state
- EXPECTED_STATUS: SUCCESS; LifeCycleState changes to Manufactured
- IF_VIOLATED: fail if Activate doesn't transition state
- EXAMPLE_TRAJECTORY: Activate LockingSP; verify LifeCycleState=Manufactured in SP table

### RULE 49: Activate on issued SP is prohibited
- SPEC: opal/5.1.1
- CONDITION: TPer SHALL NOT permit Activate on SP objects of issued SPs
- EXPECTED_STATUS: Error status
- IF_VIOLATED: fail — issued SPs cannot be activated
- EXAMPLE_TRAJECTORY: Attempt Activate on an issued SP

### RULE 50: Activate on already-Manufactured SP succeeds with no effect
- SPEC: opal/5.1.1
- CONDITION: Activate on SP in any non-Manufactured-Inactive state SHALL succeed (if ACL satisfied) with no effect
- EXPECTED_STATUS: SUCCESS (no state change)
- IF_VIOLATED: fail if error returned or state changes
- EXAMPLE_TRAJECTORY: Activate on AdminSP (already Manufactured); should succeed harmlessly

### RULE 51: Activate requires Read-Write session to Admin SP
- SPEC: opal/5.1.1
- CONDITION: Activate operates within a Read-Write session to the Admin SP
- EXPECTED_STATUS: Fails if invoked in RO session or non-Admin SP session
- IF_VIOLATED: fail — wrong session type
- EXAMPLE_TRAJECTORY: Open RO session to AdminSP, invoke Activate on LockingSP object

### RULE 52: Activate copies SID PIN to LockingSP Admin1 C_PIN
- SPEC: opal/5.1.1.2
- CONDITION: On successful activation from Manufactured-Inactive, current C_PIN_SID PIN is copied to C_PIN_Admin1 in activated SP
- EXPECTED_STATUS: C_PIN_Admin1.PIN = C_PIN_SID.PIN
- IF_VIOLATED: fail — credential not properly initialized
- EXAMPLE_TRAJECTORY: After Activate, authenticate to LockingSP with Admin1 using SID PIN

### RULE 53: Revert on Manufactured-Inactive SP has no effect
- SPEC: opal/5.1.2
- CONDITION: Revert on Manufactured SP in Manufactured-Inactive state
- EXPECTED_STATUS: SUCCESS, no effect
- IF_VIOLATED: fail if state or data changes
- EXAMPLE_TRAJECTORY: Revert on LockingSP that is already in Manufactured-Inactive state

### RULE 54: Revert on Admin SP reverts entire TPer
- SPEC: opal/5.1.2.2
- CONDITION: Revert invoked on Admin SP's SP object
- EXPECTED_STATUS: Entire TPer reverts to OFS (except C_PIN_SID under certain conditions); session aborted
- IF_VIOLATED: fail if partial revert
- EXAMPLE_TRAJECTORY: Revert on Admin SP; verify all SPs revert

### RULE 55: Revert requires Read-Write session to Admin SP
- SPEC: opal/5.1.2
- CONDITION: Revert operates within a Read-Write session to the Admin SP
- EXPECTED_STATUS: Fails in RO session
- IF_VIOLATED: fail — modification operation in RO session
- EXAMPLE_TRAJECTORY: Open RO session to Admin SP, invoke Revert

### RULE 56: Revert on Admin SP aborts session after reporting status
- SPEC: opal/5.1.2
- CONDITION: If Revert on Admin SP's own object, TPer SHALL abort session immediately after reporting status
- EXPECTED_STATUS: SUCCESS followed by session abort (CloseSession)
- IF_VIOLATED: fail if session continues after Revert
- EXAMPLE_TRAJECTORY: Revert Admin SP; observe session closure

---

## CATEGORY 10: RevertSP RULES (opal/5.1.3.*)

### RULE 57: RevertSP with KeepGlobalRangeKey=True fails if Global Range is Read+Write Locked
- SPEC: opal/5.1.3.2
- CONDITION: Global Range is both ReadLocked and WriteLocked when RevertSP is invoked with KeepGlobalRangeKey=True
- EXPECTED_STATUS: FAIL status; SP SHALL NOT change lifecycle states
- IF_VIOLATED: fail — locked data cannot be preserved
- EXAMPLE_TRAJECTORY: Lock GlobalRange, then RevertSP with KeepGlobalRangeKey=True; should fail

### RULE 58: RevertSP aborts session after reverting
- SPEC: opal/5.1.3
- CONDITION: After RevertSP completes, TPer SHALL abort the session
- EXPECTED_STATUS: CloseSession after status report
- IF_VIOLATED: fail — session should not continue
- EXAMPLE_TRAJECTORY: RevertSP on LockingSP; session ends after status

---

## CATEGORY 11: LOCKING TABLE RULES (opal/4.3.5.2.*)

### RULE 59: RangeStart alignment check — INVALID_PARAMETER if misaligned
- SPEC: opal/4.3.5.2.1.1
- CONDITION: AlignmentRequired=True AND RangeStart non-zero AND (RangeStart - LowestAlignedLBA) mod AlignmentGranularity != 0
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — misaligned range start should be rejected
- EXAMPLE_TRAJECTORY: Set RangeStart to value not aligned to AlignmentGranularity

### RULE 60: RangeLength alignment check — INVALID_PARAMETER if misaligned
- SPEC: opal/4.3.5.2.1.2
- CONDITION: AlignmentRequired=True AND RangeLength non-zero AND LengthAlignment != 0
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — misaligned range length should be rejected
- EXAMPLE_TRAJECTORY: Set RangeLength to value not aligned to AlignmentGranularity

### RULE 61: LockOnReset must be supported value
- SPEC: opal/4.3.5.2.2
- CONDITION: LockOnReset set to value not in {0}, {0,3}, or optionally {0,1}, {0,1,3}
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — unsupported LockOnReset value
- EXAMPLE_TRAJECTORY: Set LockOnReset to {2} (unsupported value)

---

## CATEGORY 12: ACCESS CONTROL (ACE/ACL) RULES (opal/4.3.1.6, 4.3.1.7)

### RULE 62: C_PIN Get for SID excludes PIN column (ACE_C_PIN_SID_Get_NOPIN)
- SPEC: opal/4.2.1.5, 4.2.1.6
- CONDITION: Get on C_PIN_SID with Admins OR SID authority
- EXPECTED_STATUS: SUCCESS but only UID, CharSet, TryLimit, Tries, Persistence columns returned (NOT PIN)
- IF_VIOLATED: fail if PIN column is returned
- EXAMPLE_TRAJECTORY: Authenticate as SID, Get C_PIN_SID; PIN should be absent from result

### RULE 63: C_PIN_MSID Get returns PIN (ACE_C_PIN_MSID_Get_PIN)
- SPEC: opal/4.2.1.5, 4.2.1.6
- CONDITION: Get on C_PIN_MSID with Anybody authority
- EXPECTED_STATUS: SUCCESS with UID and PIN columns returned
- IF_VIOLATED: fail if PIN not returned or MSID is not readable by Anybody
- EXAMPLE_TRAJECTORY: Anybody session Get on C_PIN_MSID object; PIN is returned

### RULE 64: Set PIN on C_PIN_SID requires SID authority
- SPEC: opal/4.2.1.5, 4.2.1.6 (ACE_C_PIN_SID_Set_PIN)
- CONDITION: Set PIN column on C_PIN_SID object
- EXPECTED_STATUS: SUCCESS only if SID is authenticated; NOT_AUTHORIZED otherwise
- IF_VIOLATED: fail if unauthorized entity can change SID PIN
- EXAMPLE_TRAJECTORY: Authenticate as SID, Set C_PIN_SID.PIN = new_value; should succeed

### RULE 65: Locking range ReadLocked/WriteLocked Set requires proper ACE
- SPEC: opal/4.3.1.6, 4.3.1.7
- CONDITION: Set ReadLocked on Locking_Range1 requires ACE_Locking_Range1_Set_RdLocked (Admins by default)
- EXPECTED_STATUS: NOT_AUTHORIZED if non-Admin authority; SUCCESS if Admin
- IF_VIOLATED: fail if unauthorized user can lock/unlock
- EXAMPLE_TRAJECTORY: Authenticate as User1, Set ReadLocked on Range1 — should fail unless ACE modified

### RULE 66: GenKey requires Admin authority for Locking range keys
- SPEC: opal/4.3.1.7 (ACE_K_AES_*_Range*_GenKey)
- CONDITION: GenKey on K_AES key object requires Admins authority
- EXPECTED_STATUS: NOT_AUTHORIZED if not Admin; SUCCESS if Admin
- IF_VIOLATED: fail if non-Admin can generate keys
- EXAMPLE_TRAJECTORY: Authenticate as User1, invoke GenKey on K_AES_256_Range1_Key

### RULE 67: Activate on LockingSP requires SID (ACE_SP_SID)
- SPEC: opal/4.2.1.5
- CONDITION: Activate method on SP object requires SID authority
- EXPECTED_STATUS: NOT_AUTHORIZED if not SID
- IF_VIOLATED: fail — only SID can activate
- EXAMPLE_TRAJECTORY: Authenticate as Admin1, invoke Activate on LockingSP; should return NOT_AUTHORIZED

### RULE 68: Revert on SP requires SID or Admins (ACE_SP_SID, ACE_Admin)
- SPEC: opal/4.2.1.5
- CONDITION: Revert on SP object requires SID or Admins authority
- EXPECTED_STATUS: NOT_AUTHORIZED if neither SID nor Admins authenticated
- IF_VIOLATED: fail — unauthorized revert
- EXAMPLE_TRAJECTORY: Anybody session, invoke Revert on LockingSP; NOT_AUTHORIZED

### RULE 69: Authority Enabled column modifiable only by SID (Admin SP)
- SPEC: opal/4.2.1.5, 4.2.1.6 (ACE_Set_Enabled)
- CONDITION: Set Enabled column on Authority objects in Admin SP requires SID
- EXPECTED_STATUS: NOT_AUTHORIZED if not SID
- IF_VIOLATED: fail — enabling/disabling authorities requires SID
- EXAMPLE_TRAJECTORY: Authenticate as Admin1, try to Set Authority.Enabled on Admin SP; should fail

---

## CATEGORY 13: OPAL SPECIFIC METHOD CONSTRAINTS

### RULE 70: Random Count must be <= 32
- SPEC: opal/4.2.9.1
- CONDITION: Random method Count parameter > 32
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — Count too large
- EXAMPLE_TRAJECTORY: Invoke Random with Count=64; should return INVALID_PARAMETER

### RULE 71: Random with unsupported parameters fails with INVALID_PARAMETER
- SPEC: opal/4.2.9.1
- CONDITION: Random invoked with unsupported parameters (e.g., BufferOut)
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — unsupported params rejected
- EXAMPLE_TRAJECTORY: Random with BufferOut parameter; INVALID_PARAMETER

### RULE 72: ActiveDataRemovalMechanism Set to unsupported value fails
- SPEC: opal/4.2.6.1.2
- CONDITION: Set ActiveDataRemovalMechanism to value not supported in data_removal_mechanism type
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — unsupported data removal mechanism
- EXAMPLE_TRAJECTORY: Set ActiveDataRemovalMechanism=3 (Reserved); INVALID_PARAMETER

### RULE 73: MBRControl DoneOnReset must be supported value set
- SPEC: opal/4.3.5.3.1
- CONDITION: DoneOnReset set to unsupported value (not {0}, {0,3}, or optionally {0,1}, {0,1,3})
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — unsupported DoneOnReset
- EXAMPLE_TRAJECTORY: Set DoneOnReset to {2}; INVALID_PARAMETER

---

## CATEGORY 14: Locking SP AUTHORITY PRECONFIGURATION RULES (opal/4.3.1.8)

### RULE 74: Admin1 is Enabled by default in Locking SP; Admin2-4 are disabled
- SPEC: opal/4.3.1.8
- CONDITION: In OFS, Admin1.Enabled=True; Admin2/3/4.Enabled=False
- EXPECTED_STATUS: Get on Authority table confirms these values
- IF_VIOLATED: fail if defaults don't match OFS
- EXAMPLE_TRAJECTORY: After Activate, Get Admin1 authority; Enabled should be True

### RULE 75: User1-User8 are disabled by default
- SPEC: opal/4.3.1.8
- CONDITION: In OFS, User1-User8 all have Enabled=False
- EXPECTED_STATUS: Get confirms Enabled=False for all Users
- IF_VIOLATED: fail if any User is enabled in OFS
- EXAMPLE_TRAJECTORY: After Activate, Get User1; Enabled should be False

### RULE 76: Users class authority cannot be directly authenticated
- SPEC: opal/4.3.1.8, core/5.3.4.1.2
- CONDITION: Users is a class authority (IsClass=True); cannot be directly authenticated
- EXPECTED_STATUS: INVALID_PARAMETER
- IF_VIOLATED: fail — class authority authentication rejected
- EXAMPLE_TRAJECTORY: Authenticate with Authority=Users; INVALID_PARAMETER

### RULE 77: ACE_C_PIN_UserMMMM_Set_PIN BooleanExpr modification limited
- SPEC: opal/4.3.1.7 (*ACE1)
- CONDITION: TPer SHALL support "Admins" and "Admins OR UserMMMM" in BooleanExpr; other values cause INVALID_PARAMETER on Set
- EXPECTED_STATUS: INVALID_PARAMETER if unsupported BooleanExpr set
- IF_VIOLATED: fail — unsupported ACE expression
- EXAMPLE_TRAJECTORY: Set ACE_C_PIN_User1_Set_PIN BooleanExpr to "User1" (without Admins); INVALID_PARAMETER

---

## CATEGORY 15: SESSION TO MANUFACTURED-INACTIVE SP (opal/5.2.2.1)

### RULE 78: Cannot open session to SP in Manufactured-Inactive state
- SPEC: opal/5.2.2.1
- CONDITION: Sessions cannot be opened to SPs in Manufactured-Inactive state
- EXPECTED_STATUS: Session startup fails (INVALID_PARAMETER or similar)
- IF_VIOLATED: fail — inactive SP should not accept sessions
- EXAMPLE_TRAJECTORY: StartSession to LockingSP before Activate; should fail

---

## CATEGORY 16: OPAL PROPERTIES CONSTRAINTS (opal/4.1.1.1)

### RULE 79: MaxComPacketSize minimum 2048
- SPEC: opal/4.1.1.1
- CONDITION: TPer SHALL report MaxComPacketSize >= 2048
- EXPECTED_STATUS: Properties method returns value >= 2048
- IF_VIOLATED: fail — below spec minimum
- EXAMPLE_TRAJECTORY: Properties method; verify MaxComPacketSize >= 2048

### RULE 80: MaxAuthentications minimum 2
- SPEC: opal/4.1.1.1
- CONDITION: TPer SHALL report MaxAuthentications >= 2
- EXPECTED_STATUS: Properties method returns >= 2
- IF_VIOLATED: fail — must support at least 2 concurrent authentications
- EXAMPLE_TRAJECTORY: Properties method; verify MaxAuthentications >= 2

### RULE 81: MaxSessions minimum 1
- SPEC: opal/4.1.1.1
- CONDITION: TPer SHALL report MaxSessions >= 1
- EXPECTED_STATUS: Properties returns >= 1
- IF_VIOLATED: fail — must support at least 1 session
- EXAMPLE_TRAJECTORY: Properties method; verify MaxSessions >= 1

---

## CATEGORY 17: Locking Range Behavior

### RULE 82: GlobalRange RangeStart and RangeLength SHALL NOT be modifiable
- SPEC: opal/4.3.5.2, core Locking template
- CONDITION: GlobalRange RangeStart=0, RangeLength=0 (represents entire disk); these are not modifiable
- EXPECTED_STATUS: Set on GlobalRange RangeStart/RangeLength should fail (INVALID_PARAMETER or NOT_AUTHORIZED)
- IF_VIOLATED: fail — GlobalRange boundaries are fixed
- EXAMPLE_TRAJECTORY: Set RangeStart=100 on Locking_GlobalRange; should fail

### RULE 83: ReadLocked=True when ReadLockEnabled=False is ineffective or fails
- SPEC: core Locking template (implied by lock enable mechanism)
- CONDITION: ReadLocked can only be effective when ReadLockEnabled=True
- EXPECTED_STATUS: If ReadLockEnabled=False, setting ReadLocked=True may fail or have no effect
- IF_VIOLATED: fail if read locking activates without enable
- EXAMPLE_TRAJECTORY: Set ReadLocked=True on range where ReadLockEnabled=False

### RULE 84: LockOnReset {0} means range locks on power cycle
- SPEC: opal/4.3.5.2.2
- CONDITION: LockOnReset contains Power Cycle (0); after power cycle, ReadLocked/WriteLocked return to True (if enabled)
- EXPECTED_STATUS: After power cycle, range is locked
- IF_VIOLATED: fail if range remains unlocked after power cycle when LockOnReset includes Power Cycle
- EXAMPLE_TRAJECTORY: Unlock range, power cycle, verify range is locked again

---

## CATEGORY 18: CELLBLOCK / ADDRESSING RULES

### RULE 85: Cellblock out of bounds causes Get failure
- SPEC: 5.3.3.6.3(d)
- CONDITION: Any Cellblock parameter values are out of bounds for the table
- EXPECTED_STATUS: Error (INVALID_PARAMETER or FAIL)
- IF_VIOLATED: fail — out-of-bounds access
- EXAMPLE_TRAJECTORY: Get on Locking table with startColumn=0xFF (beyond defined columns)

### RULE 86: Next method on empty scope returns empty list
- SPEC: 5.3.4.2.7
- CONDITION: Next invoked with Where pointing past last row, or on empty table
- EXPECTED_STATUS: SUCCESS with empty result list
- IF_VIOLATED: fail if non-empty result for exhausted iteration
- EXAMPLE_TRAJECTORY: Next on Authority table with Where=last_authority_UID; should return empty list

---

## SUMMARY

Total rules extracted: 86

Key categories for training data generation:
1. Status code determination (rules 1-9): 9 rules
2. Session management (rules 10-14): 5 rules
3. Get method behavior (rules 15-20): 6 rules
4. Set method behavior (rules 21-28): 8 rules
5. Authenticate method (rules 29-36): 8 rules
6. C_PIN / TryLimit (rules 37-42): 6 rules
7. Authority operation types (rules 43-45): 3 rules
8. Opal session rules (rules 46-47): 2 rules
9. Lifecycle / Activate / Revert (rules 48-56): 9 rules
10. RevertSP (rules 57-58): 2 rules
11. Locking table (rules 59-61): 3 rules
12. Access control / ACE (rules 62-69): 8 rules
13. Opal method constraints (rules 70-73): 4 rules
14. Authority preconfiguration (rules 74-77): 4 rules
15. Manufactured-Inactive session (rule 78): 1 rule
16. Properties constraints (rules 79-81): 3 rules
17. Locking range behavior (rules 82-84): 3 rules
18. Cellblock / addressing (rules 85-86): 2 rules

Most actionable for test data generation (highest confidence, most testable):
- Rules 2, 3, 7, 21, 22, 29, 30, 31, 32, 33, 35, 57, 62, 63, 64, 65, 67, 70, 72, 78
