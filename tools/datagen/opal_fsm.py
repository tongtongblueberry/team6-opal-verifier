# Changed: create unified TCG/Opal FSM merging 7 partial FSMs from sub-agents.
# Why: single source of truth for trajectory generation covering all 86 spec rules.
"""Unified TCG/Opal Finite State Machine for training-data trajectory generation.

Merges 7 partial FSMs (Session, Auth/Credential, Get, Set, Lifecycle, Locking/ACL,
Properties/Other) into a single flattened product FSM with ~25 composite states
representing reachable protocol paths.

The global state encodes: (session_state, auth_level, sp_lifecycle, locking_state).

Usage:
    python -m tools.datagen.opal_fsm          # prints summary
    from tools.datagen.opal_fsm import DELTA, S, A, Q0, F, get_valid_actions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Q — composite states
# ---------------------------------------------------------------------------

class S(Enum):
    """Composite states encoding (session, auth, lifecycle, locking) dimensions.

    Naming convention:
        POWER_OFF            — device not powered
        POWERED_ON           — powered, no session
        PROPS_QUERIED        — Properties/Discovery done
        ADMIN_RW_NOBODY      — RW session to AdminSP, Anybody auth
        ADMIN_RW_SID         — RW session to AdminSP, SID authenticated
        ADMIN_RO_NOBODY      — RO session to AdminSP, Anybody auth
        ADMIN_RO_SID         — RO session to AdminSP, SID authenticated
        LOCKING_INACTIVE     — LockingSP in Manufactured-Inactive state (no session possible)
        ADMIN_RW_SID_ACTIVATED — RW AdminSP + SID auth + LockingSP just activated
        LOCKING_RW_NOBODY    — RW session to LockingSP, Anybody auth
        LOCKING_RW_ADMIN1    — RW session to LockingSP, Admin1 authenticated
        LOCKING_RW_USER1     — RW session to LockingSP, User1 authenticated
        LOCKING_RO_NOBODY    — RO session to LockingSP, Anybody auth
        LOCKING_RO_ADMIN1    — RO session to LockingSP, Admin1 (RO)
        LOCKING_RANGE_SET    — LockingSP + Admin1 + range configured
        LOCKING_RANGE_LOCKED — LockingSP + Admin1 + range locked
        LOCKING_KEY_SET      — LockingSP + Admin1 + AES key generated
        AUTH_FAILED_RETRY    — Authentication failed, can retry
        AUTH_LOCKED_OUT      — Authority locked out (TryLimit exceeded)
        MAX_SESSIONS         — Max sessions reached, cannot open more
        REVERTED             — TPer reverted to OFS
        SESSION_ABORTED      — Session aborted (after Revert/RevertSP)
        ERROR_RECOVERY       — Generic error state, return to POWERED_ON
        ADMIN_RW_SID_MSID_READ — RW AdminSP + SID + MSID PIN read (common flow)
        LOCKING_RW_ADMIN1_USER_ENABLED — Admin1 + User1 enabled
    """

    POWER_OFF = auto()
    POWERED_ON = auto()
    PROPS_QUERIED = auto()

    # AdminSP sessions
    ADMIN_RW_NOBODY = auto()
    ADMIN_RW_SID = auto()
    ADMIN_RW_SID_MSID_READ = auto()
    ADMIN_RO_NOBODY = auto()
    ADMIN_RO_SID = auto()

    # Lifecycle
    LOCKING_INACTIVE = auto()
    ADMIN_RW_SID_ACTIVATED = auto()

    # LockingSP sessions
    LOCKING_RW_NOBODY = auto()
    LOCKING_RW_ADMIN1 = auto()
    LOCKING_RW_USER1 = auto()
    LOCKING_RW_ADMIN1_USER_ENABLED = auto()
    LOCKING_RO_NOBODY = auto()
    LOCKING_RO_ADMIN1 = auto()

    # Locking range states
    LOCKING_RANGE_SET = auto()
    LOCKING_RANGE_LOCKED = auto()
    LOCKING_KEY_SET = auto()

    # Error / edge states
    AUTH_FAILED_RETRY = auto()
    AUTH_LOCKED_OUT = auto()
    MAX_SESSIONS = auto()
    REVERTED = auto()
    SESSION_ABORTED = auto()
    ERROR_RECOVERY = auto()


# ---------------------------------------------------------------------------
# Sigma — actions (protocol operations)
# ---------------------------------------------------------------------------

class A(Enum):
    """All protocol actions in TCG/Opal."""

    POWER_ON = auto()
    POWER_CYCLE = auto()
    PROPERTIES = auto()

    # Session management
    START_RW_ADMIN_NOBODY = auto()
    START_RW_ADMIN_SID = auto()
    START_RW_ADMIN_SID_WRONG_PW = auto()
    START_RO_ADMIN_NOBODY = auto()
    START_RO_ADMIN_SID = auto()
    START_RW_LOCKING_NOBODY = auto()
    START_RW_LOCKING_ADMIN1 = auto()
    START_RW_LOCKING_ADMIN1_WRONG_PW = auto()
    START_RW_LOCKING_USER1 = auto()
    START_RO_LOCKING_NOBODY = auto()
    START_RO_LOCKING_ADMIN1 = auto()
    START_SESSION_INACTIVE_SP = auto()
    START_SESSION_FROZEN_SP = auto()
    START_SESSION_CLASS_AUTH = auto()
    START_SESSION_BAD_TIMEOUT = auto()
    START_SESSION_EXCHANGE_AUTH = auto()
    START_SESSION_TPERSIGN_AUTH = auto()
    START_SESSION_CONCURRENT = auto()
    START_SESSION_MAX = auto()
    CLOSE_SESSION = auto()

    # Authentication (within session)
    AUTH_SID_CORRECT = auto()
    AUTH_SID_WRONG = auto()
    AUTH_ADMIN1_CORRECT = auto()
    AUTH_ADMIN1_WRONG = auto()
    AUTH_USER1_CORRECT = auto()
    AUTH_USER1_WRONG = auto()
    AUTH_ANYBODY = auto()
    AUTH_NONEXISTENT = auto()
    AUTH_CLASS_AUTHORITY = auto()
    AUTH_DISABLED_AUTHORITY = auto()
    AUTH_EXCHANGE_AUTHORITY = auto()
    AUTH_MAX_EXCEEDED = auto()
    AUTH_LOCKED_OUT_ATTEMPT = auto()

    # Get method variants
    GET_MSID_PIN = auto()
    GET_CPIN_SID = auto()
    GET_LOCKING_RANGE = auto()
    GET_AUTHORITY_TABLE = auto()
    GET_NONEXISTENT_OBJ = auto()
    GET_BAD_CELLBLOCK = auto()
    GET_BYTE_TABLE_COL = auto()
    GET_BYTE_TABLE_UNAUTH = auto()
    GET_OBJ_WITH_ROW_PARAM = auto()
    GET_COLUMN_ORDER_CHECK = auto()

    # Set method variants
    SET_SID_PIN = auto()
    SET_CPIN_ADMIN1 = auto()
    SET_LOCKING_RANGE_RW = auto()
    SET_LOCKING_READLOCKED = auto()
    SET_LOCKING_WRITELOCKED = auto()
    SET_AUTHORITY_ENABLED = auto()
    SET_USER_ENABLED = auto()
    SET_ACE_BOOLEXPR = auto()
    SET_DUPLICATE_COLUMN = auto()
    SET_WITH_WHERE_ON_OBJ = auto()
    SET_TABLE_NO_WHERE = auto()
    SET_BYTE_TABLE_ROWVALS = auto()
    SET_OBJ_TABLE_BYTES = auto()
    SET_NO_VALUES = auto()
    SET_UID_COLUMN = auto()
    SET_GLOBAL_RANGE_START = auto()
    SET_READLOCKED_NO_ENABLE = auto()
    SET_IN_RO_SESSION = auto()
    SET_LOCK_ON_RESET = auto()
    SET_LOCK_ON_RESET_BAD = auto()
    SET_DONE_ON_RESET_BAD = auto()
    SET_ACTIVE_DATA_REMOVAL_BAD = auto()

    # GenKey
    GENKEY_ADMIN = auto()
    GENKEY_NON_ADMIN = auto()

    # Lifecycle
    ACTIVATE_LOCKING_SP = auto()
    ACTIVATE_ISSUED_SP = auto()
    ACTIVATE_ALREADY_ACTIVE = auto()
    ACTIVATE_IN_RO = auto()
    ACTIVATE_NOT_SID = auto()
    REVERT_ADMIN_SP = auto()
    REVERT_IN_RO = auto()
    REVERT_NOT_SID = auto()
    REVERT_INACTIVE_SP = auto()
    REVERTSP_LOCKING = auto()
    REVERTSP_KEEP_KEY_LOCKED = auto()

    # Random
    RANDOM_VALID = auto()
    RANDOM_COUNT_TOO_LARGE = auto()
    RANDOM_BAD_PARAM = auto()

    # Next
    NEXT_EMPTY = auto()

    # Data I/O (Read/Write to locking ranges)  # Changed: added READ_DATA, WRITE_DATA for data I/O coverage
    READ_DATA = auto()
    WRITE_DATA = auto()

    # LockingInfo query  # Changed: added GET_LOCKINGINFO for locking table info coverage
    GET_LOCKINGINFO = auto()

    # Recovery
    RECOVER_FROM_ERROR = auto()


# ---------------------------------------------------------------------------
# Transition dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Transition:
    """A single FSM transition."""

    next_state: S
    expected_status: str
    rules: Tuple[str, ...]
    description: str


# ---------------------------------------------------------------------------
# delta — the transition function
# ---------------------------------------------------------------------------

DELTA: Dict[Tuple[S, A], Transition] = {}


def _t(state: S, action: A, next_state: S, status: str,
       rules: Tuple[str, ...], desc: str) -> None:
    """Register a transition in DELTA."""
    DELTA[(state, action)] = Transition(next_state, status, rules, desc)


# ===== POWER / BOOT =====

_t(S.POWER_OFF, A.POWER_ON, S.POWERED_ON, "SUCCESS",
   ("R01", "R42", "R84"),
   "Power on device. Tries reset if Persistence=False (R42). "
   "LockOnReset ranges re-lock (R84).")

_t(S.POWERED_ON, A.POWER_CYCLE, S.POWERED_ON, "SUCCESS",
   ("R42", "R84"),
   "Power cycle resets Tries (Persistence=False, R42) and re-locks "
   "ranges with LockOnReset containing PowerCycle (R84).")

# ===== PROPERTIES =====

_t(S.POWERED_ON, A.PROPERTIES, S.PROPS_QUERIED, "SUCCESS",
   ("R01", "R79", "R80", "R81"),
   "Properties/Discovery0. Verify MaxComPacketSize>=2048 (R79), "
   "MaxAuthentications>=2 (R80), MaxSessions>=1 (R81).")

_t(S.PROPS_QUERIED, A.PROPERTIES, S.PROPS_QUERIED, "SUCCESS",
   ("R01", "R79", "R80", "R81"),
   "Re-query Properties (idempotent).")

# ===== AdminSP SESSION OPEN =====

_t(S.PROPS_QUERIED, A.START_RW_ADMIN_NOBODY, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW session to AdminSP with Anybody auth. Write=True (R12, R46). "
   "Only one RW session per SP (R10).")

_t(S.PROPS_QUERIED, A.START_RW_ADMIN_SID, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW session to AdminSP with SID auth (correct password).")

_t(S.PROPS_QUERIED, A.START_RW_ADMIN_SID_WRONG_PW, S.AUTH_FAILED_RETRY, "NOT_AUTHORIZED",
   ("R03", "R37"),
   "Open RW session to AdminSP with wrong SID password. "
   "NOT_AUTHORIZED in SyncSession (R03). Tries incremented (R37).")

_t(S.PROPS_QUERIED, A.START_RO_ADMIN_NOBODY, S.ADMIN_RO_NOBODY, "SUCCESS",
   ("R01", "R10", "R12"),
   "Open RO session to AdminSP with Anybody auth. Write=False (R12).")

_t(S.PROPS_QUERIED, A.START_RO_ADMIN_SID, S.ADMIN_RO_SID, "SUCCESS",
   ("R01", "R10", "R12"),
   "Open RO session to AdminSP with SID auth.")

_t(S.POWERED_ON, A.START_RW_ADMIN_NOBODY, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW AdminSP session without prior Properties query.")

_t(S.POWERED_ON, A.START_RW_ADMIN_SID, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW AdminSP session with SID (skip Properties).")

# ===== AdminSP SESSION — ERROR PATHS =====

_t(S.PROPS_QUERIED, A.START_SESSION_CLASS_AUTH, S.ERROR_RECOVERY, "INVALID_PARAMETER",
   ("R07", "R30", "R76"),
   "StartSession with HostSigningAuthority = class authority. "
   "INVALID_PARAMETER (R07). Class auth rejected (R30, R76).")

_t(S.PROPS_QUERIED, A.START_SESSION_BAD_TIMEOUT, S.ERROR_RECOVERY, "INVALID_PARAMETER",
   ("R13", "R14", "R47"),
   "StartSession with SessionTimeout or TransTimeout out of range. "
   "R13 (SessionTimeout), R14 (TransTimeout), R47 (Opal timeout).")

_t(S.PROPS_QUERIED, A.START_SESSION_FROZEN_SP, S.ERROR_RECOVERY, "SP_FROZEN",
   ("R05",),
   "StartSession to SP in Frozen lifecycle state.")

_t(S.PROPS_QUERIED, A.START_SESSION_EXCHANGE_AUTH, S.ERROR_RECOVERY, "INVALID_PARAMETER",
   ("R43",),
   "StartSession with HostSigningAuthority = Password-type authority "
   "referenced as Exchange. Error (R43).")

_t(S.PROPS_QUERIED, A.START_SESSION_TPERSIGN_AUTH, S.ERROR_RECOVERY, "INVALID_PARAMETER",
   ("R45",),
   "StartSession with HostSigningAuthority = TPerSign authority. "
   "Only valid as SPSigningAuthority (R45).")

_t(S.PROPS_QUERIED, A.START_SESSION_INACTIVE_SP, S.LOCKING_INACTIVE, "INVALID_PARAMETER",
   ("R78",),
   "StartSession to LockingSP before Activate (Manufactured-Inactive). "
   "Session rejected (R78). Stays in Manufactured-Inactive awareness.")

_t(S.PROPS_QUERIED, A.START_SESSION_MAX, S.MAX_SESSIONS, "NO_SESSIONS_AVAILABLE",
   ("R06",),
   "StartSession when MaxSessions already open (R06).")

_t(S.PROPS_QUERIED, A.START_SESSION_CONCURRENT, S.ERROR_RECOVERY, "SP_BUSY",
   ("R04", "R10"),
   "Concurrent session conflict: RW already open to this SP (R04, R10).")

# ===== LOCKING_INACTIVE (pre-Activate) =====

_t(S.LOCKING_INACTIVE, A.RECOVER_FROM_ERROR, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Recover after session-to-inactive-SP rejection. "
   "Host must open AdminSP session and Activate first.")

# ===== AdminSP RW NOBODY — Get =====

_t(S.ADMIN_RW_NOBODY, A.GET_MSID_PIN, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R01", "R18", "R63"),
   "Get C_PIN_MSID.PIN with Anybody auth. PIN returned (R63). "
   "Authorized columns only (R18).")

_t(S.ADMIN_RW_NOBODY, A.GET_CPIN_SID, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R01", "R18", "R62"),
   "Get C_PIN_SID with Anybody — PIN column excluded (R62). "
   "Only non-PIN columns returned (R18).")

_t(S.ADMIN_RW_NOBODY, A.GET_NONEXISTENT_OBJ, S.ADMIN_RW_NOBODY, "FAIL",
   ("R15",),
   "Get on non-existent table/object (R15).")

_t(S.ADMIN_RW_NOBODY, A.GET_BAD_CELLBLOCK, S.ADMIN_RW_NOBODY, "INVALID_PARAMETER",
   ("R85",),
   "Get with out-of-bounds Cellblock (R85).")

_t(S.ADMIN_RW_NOBODY, A.GET_OBJ_WITH_ROW_PARAM, S.ADMIN_RW_NOBODY, "INVALID_PARAMETER",
   ("R16",),
   "Object Get with row/table values in Cellblock (R16).")

# Changed: moved GET_BYTE_TABLE_COL and GET_BYTE_TABLE_UNAUTH from AdminSP to LockingSP
# Why: MBRControl is a LockingSP table (opal/4.3.5.3), not AdminSP. Having it in
# AdminSP was a spec violation. Moved to LOCKING_RW_ADMIN1 where Admin1 has access.
_t(S.LOCKING_RW_ADMIN1, A.GET_BYTE_TABLE_COL, S.LOCKING_RW_ADMIN1, "INVALID_PARAMETER",
   ("R17",),
   "Get MBRControl byte table with column values — INVALID_PARAMETER (R17).")

_t(S.LOCKING_RW_ADMIN1, A.GET_BYTE_TABLE_UNAUTH, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R19"),
   "Get MBRControl byte table — SUCCESS with empty results if ACL not satisfied (R19).")

_t(S.ADMIN_RW_NOBODY, A.GET_COLUMN_ORDER_CHECK, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R01", "R20"),
   "Get verifying column ordering in result matches Column table order (R20).")

_t(S.ADMIN_RW_NOBODY, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close Anybody AdminSP session.")

# ===== AdminSP RW NOBODY — Set errors =====

_t(S.ADMIN_RW_NOBODY, A.SET_SID_PIN, S.ADMIN_RW_NOBODY, "NOT_AUTHORIZED",
   ("R02", "R21", "R64"),
   "Set C_PIN_SID.PIN without SID auth. NOT_AUTHORIZED (R02, R21). "
   "Requires SID authority (R64).")

# ===== AdminSP RW NOBODY — Auth within session =====

_t(S.ADMIN_RW_NOBODY, A.AUTH_SID_CORRECT, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R31", "R38"),
   "Authenticate SID with correct password. result=True (R31). "
   "Tries reset to 0 (R38).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_SID_WRONG, S.AUTH_FAILED_RETRY, "SUCCESS",
   ("R32", "R37"),
   "Authenticate SID with wrong password. result=False (R32). "
   "Tries incremented (R37).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_ANYBODY, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R01", "R35"),
   "Authenticate Anybody — always succeeds, result=True (R35).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_NONEXISTENT, S.ADMIN_RW_NOBODY, "INVALID_PARAMETER",
   ("R29",),
   "Authenticate with non-existent authority UID (R29).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_CLASS_AUTHORITY, S.ADMIN_RW_NOBODY, "INVALID_PARAMETER",
   ("R30", "R76"),
   "Authenticate with class authority (Admins/Users). "
   "INVALID_PARAMETER (R30, R76).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_DISABLED_AUTHORITY, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R33",),
   "Authenticate with disabled authority. result=False (R33).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_EXCHANGE_AUTHORITY, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R34", "R44"),
   "Authenticate with Exchange-operation authority. "
   "result=False (R34). Exchange cannot be authenticated (R44).")

_t(S.ADMIN_RW_NOBODY, A.AUTH_MAX_EXCEEDED, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R36",),
   "Authenticate exceeding MaxAuthentications. result=False (R36).")

# ===== AdminSP RW SID =====

_t(S.ADMIN_RW_SID, A.GET_MSID_PIN, S.ADMIN_RW_SID_MSID_READ, "SUCCESS",
   ("R01", "R18", "R63"),
   "Get C_PIN_MSID.PIN with SID auth. MSID PIN readable by Anybody (R63).")

_t(S.ADMIN_RW_SID, A.GET_CPIN_SID, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R18", "R62"),
   "Get C_PIN_SID with SID auth — PIN column still excluded (R62).")

_t(S.ADMIN_RW_SID, A.SET_SID_PIN, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R41", "R64"),
   "Set C_PIN_SID.PIN with SID auth. Tries reset on PIN change (R41). "
   "SID auth required (R64).")

_t(S.ADMIN_RW_SID, A.SET_AUTHORITY_ENABLED, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R69"),
   "Set Enabled column on Authority in AdminSP. Requires SID (R69).")

_t(S.ADMIN_RW_SID, A.ACTIVATE_LOCKING_SP, S.ADMIN_RW_SID_ACTIVATED, "SUCCESS",
   ("R01", "R48", "R52", "R67"),
   "Activate LockingSP from Manufactured-Inactive to Manufactured (R48). "
   "SID PIN copied to Admin1 C_PIN (R52). Requires SID auth (R67).")

_t(S.ADMIN_RW_SID, A.ACTIVATE_ISSUED_SP, S.ADMIN_RW_SID, "FAIL",
   ("R49",),
   "Activate on issued SP — prohibited (R49).")

_t(S.ADMIN_RW_SID, A.ACTIVATE_ALREADY_ACTIVE, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R50"),
   "Activate on already-Manufactured SP — SUCCESS, no effect (R50).")

_t(S.ADMIN_RW_SID, A.REVERT_ADMIN_SP, S.REVERTED, "SUCCESS",
   ("R01", "R54", "R56"),
   "Revert AdminSP — entire TPer reverts to OFS (R54). "
   "Session aborted after status report (R56).")

_t(S.ADMIN_RW_SID, A.REVERT_INACTIVE_SP, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R53"),
   "Revert on Manufactured-Inactive SP — SUCCESS, no effect (R53).")

_t(S.ADMIN_RW_SID, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close SID AdminSP session.")

_t(S.ADMIN_RW_SID, A.SET_DUPLICATE_COLUMN, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R22",),
   "Set with same column twice — INVALID_PARAMETER (R22).")

_t(S.ADMIN_RW_SID, A.SET_WITH_WHERE_ON_OBJ, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R23",),
   "Object.Set with Where parameter — INVALID_PARAMETER (R23).")

_t(S.ADMIN_RW_SID, A.SET_TABLE_NO_WHERE, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R24",),
   "Table.Set on object table without Where — INVALID_PARAMETER (R24).")

_t(S.ADMIN_RW_SID, A.SET_OBJ_TABLE_BYTES, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R25",),
   "Set on object table with Bytes instead of RowValues — INVALID_PARAMETER (R25).")

# Changed: moved SET_BYTE_TABLE_ROWVALS from AdminSP to LockingSP
# Why: MBRControl is a LockingSP table, not AdminSP
_t(S.LOCKING_RW_ADMIN1, A.SET_BYTE_TABLE_ROWVALS, S.LOCKING_RW_ADMIN1, "INVALID_PARAMETER",
   ("R26",),
   "Set MBRControl byte table with RowValues — INVALID_PARAMETER (R26).")

_t(S.ADMIN_RW_SID, A.SET_NO_VALUES, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R27"),
   "Set with no Values parameter — SUCCESS, no effect (R27).")

_t(S.ADMIN_RW_SID, A.SET_UID_COLUMN, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R28",),
   "Set attempting to change UID or system cell — INVALID_PARAMETER (R28).")

_t(S.ADMIN_RW_SID, A.RANDOM_VALID, S.ADMIN_RW_SID, "SUCCESS",
   ("R01",),
   "Random method with valid Count<=32.")

_t(S.ADMIN_RW_SID, A.RANDOM_COUNT_TOO_LARGE, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R70",),
   "Random with Count>32 — INVALID_PARAMETER (R70).")

_t(S.ADMIN_RW_SID, A.RANDOM_BAD_PARAM, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R71",),
   "Random with unsupported parameter (BufferOut) — INVALID_PARAMETER (R71).")

_t(S.ADMIN_RW_SID, A.SET_ACTIVE_DATA_REMOVAL_BAD, S.ADMIN_RW_SID, "INVALID_PARAMETER",
   ("R72",),
   "Set ActiveDataRemovalMechanism to unsupported value — INVALID_PARAMETER (R72).")

# Changed: moved SET_DONE_ON_RESET_BAD from AdminSP to LockingSP
# Why: MBRControl DoneOnReset is a LockingSP table column (opal/4.3.5.3.1)
_t(S.LOCKING_RW_ADMIN1, A.SET_DONE_ON_RESET_BAD, S.LOCKING_RW_ADMIN1, "INVALID_PARAMETER",
   ("R73",),
   "Set MBRControl DoneOnReset to unsupported value — INVALID_PARAMETER (R73).")

_t(S.ADMIN_RW_SID, A.NEXT_EMPTY, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R86"),
   "Next on empty scope — SUCCESS with empty result list (R86).")

# ===== AdminSP RW SID MSID_READ (typical flow node) =====

_t(S.ADMIN_RW_SID_MSID_READ, A.SET_SID_PIN, S.ADMIN_RW_SID_MSID_READ, "SUCCESS",
   ("R01", "R41", "R64"),
   "Set SID PIN (common: change from MSID to new PIN). "
   "Tries reset (R41). Requires SID (R64).")

_t(S.ADMIN_RW_SID_MSID_READ, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session after reading MSID.")

_t(S.ADMIN_RW_SID_MSID_READ, A.ACTIVATE_LOCKING_SP, S.ADMIN_RW_SID_ACTIVATED, "SUCCESS",
   ("R01", "R48", "R52", "R67"),
   "Activate LockingSP from MSID-read state.")

# ===== AdminSP RO sessions =====

_t(S.ADMIN_RO_NOBODY, A.GET_MSID_PIN, S.ADMIN_RO_NOBODY, "SUCCESS",
   ("R01", "R18", "R63"),
   "Get MSID PIN in RO session.")

_t(S.ADMIN_RO_NOBODY, A.SET_IN_RO_SESSION, S.ADMIN_RO_NOBODY, "NOT_AUTHORIZED",
   ("R02", "R11"),
   "Set in RO session — no permanent changes allowed (R11). "
   "NOT_AUTHORIZED (R02).")

_t(S.ADMIN_RO_NOBODY, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close RO AdminSP Anybody session.")

_t(S.ADMIN_RO_SID, A.GET_CPIN_SID, S.ADMIN_RO_SID, "SUCCESS",
   ("R01", "R18", "R62"),
   "Get C_PIN_SID in RO session — PIN excluded (R62).")

_t(S.ADMIN_RO_SID, A.SET_IN_RO_SESSION, S.ADMIN_RO_SID, "NOT_AUTHORIZED",
   ("R02", "R11"),
   "Set in RO session — not allowed (R11).")

_t(S.ADMIN_RO_SID, A.ACTIVATE_IN_RO, S.ADMIN_RO_SID, "FAIL",
   ("R51",),
   "Activate in RO session — requires RW (R51).")

_t(S.ADMIN_RO_SID, A.REVERT_IN_RO, S.ADMIN_RO_SID, "FAIL",
   ("R55",),
   "Revert in RO session — requires RW (R55).")

_t(S.ADMIN_RO_SID, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close RO AdminSP SID session.")

# ===== AdminSP RW SID ACTIVATED =====

_t(S.ADMIN_RW_SID_ACTIVATED, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session after Activate. LockingSP now Manufactured.")

_t(S.ADMIN_RW_SID_ACTIVATED, A.ACTIVATE_ALREADY_ACTIVE, S.ADMIN_RW_SID_ACTIVATED, "SUCCESS",
   ("R01", "R50"),
   "Re-Activate on already-active LockingSP — no effect (R50).")

# ===== LockingSP SESSION OPEN =====

_t(S.PROPS_QUERIED, A.START_RW_LOCKING_ADMIN1, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW session to LockingSP with Admin1 auth. "
   "Only after Activate. Write=True (R12, R46).")

_t(S.PROPS_QUERIED, A.START_RW_LOCKING_ADMIN1_WRONG_PW, S.AUTH_FAILED_RETRY, "NOT_AUTHORIZED",
   ("R03", "R37"),
   "Open RW LockingSP with wrong Admin1 password. NOT_AUTHORIZED (R03). "
   "Tries incremented (R37).")

_t(S.PROPS_QUERIED, A.START_RW_LOCKING_NOBODY, S.LOCKING_RW_NOBODY, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW session to LockingSP with Anybody auth.")

_t(S.PROPS_QUERIED, A.START_RW_LOCKING_USER1, S.LOCKING_RW_USER1, "SUCCESS",
   ("R01", "R10", "R12", "R46"),
   "Open RW session to LockingSP with User1 auth (must be enabled).")

_t(S.PROPS_QUERIED, A.START_RO_LOCKING_NOBODY, S.LOCKING_RO_NOBODY, "SUCCESS",
   ("R01", "R10", "R12"),
   "Open RO session to LockingSP with Anybody.")

_t(S.PROPS_QUERIED, A.START_RO_LOCKING_ADMIN1, S.LOCKING_RO_ADMIN1, "SUCCESS",
   ("R01", "R10", "R12"),
   "Open RO session to LockingSP with Admin1.")

# ===== LockingSP RW NOBODY =====

_t(S.LOCKING_RW_NOBODY, A.GET_LOCKING_RANGE, S.LOCKING_RW_NOBODY, "SUCCESS",
   ("R01", "R18", "R20"),
   "Get Locking range with Anybody — authorized columns only (R18), "
   "column order (R20).")

_t(S.LOCKING_RW_NOBODY, A.SET_LOCKING_RANGE_RW, S.LOCKING_RW_NOBODY, "NOT_AUTHORIZED",
   ("R02", "R21", "R65"),
   "Set Locking range without Admin auth — NOT_AUTHORIZED (R02, R21). "
   "Requires Admin ACE (R65).")

_t(S.LOCKING_RW_NOBODY, A.AUTH_ADMIN1_CORRECT, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R31", "R38"),
   "Authenticate Admin1 correct password. result=True (R31). "
   "Tries reset (R38).")

_t(S.LOCKING_RW_NOBODY, A.AUTH_ADMIN1_WRONG, S.AUTH_FAILED_RETRY, "SUCCESS",
   ("R32", "R37"),
   "Authenticate Admin1 wrong password. result=False (R32). "
   "Tries incremented (R37).")

_t(S.LOCKING_RW_NOBODY, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close Anybody LockingSP session.")

# ===== LockingSP RW ADMIN1 =====

_t(S.LOCKING_RW_ADMIN1, A.GET_LOCKING_RANGE, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R18", "R20"),
   "Get Locking range with Admin1 auth — full columns (R18, R20).")

_t(S.LOCKING_RW_ADMIN1, A.GET_AUTHORITY_TABLE, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R18", "R20", "R74", "R75"),
   "Get Authority table. Admin1 enabled by default (R74). "
   "Users disabled by default (R75).")

_t(S.LOCKING_RW_ADMIN1, A.SET_LOCKING_RANGE_RW, S.LOCKING_RANGE_SET, "SUCCESS",
   ("R01", "R08", "R65"),
   "Set Locking range RangeStart/RangeLength with Admin1 (R65). "
   "Valid parameters (R08).")

_t(S.LOCKING_RW_ADMIN1, A.SET_LOCKING_READLOCKED, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R65"),
   "Set ReadLocked on Locking range with Admin1 (R65).")

_t(S.LOCKING_RW_ADMIN1, A.SET_LOCKING_WRITELOCKED, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R65"),
   "Set WriteLocked on Locking range with Admin1 (R65).")

_t(S.LOCKING_RW_ADMIN1, A.SET_USER_ENABLED, S.LOCKING_RW_ADMIN1_USER_ENABLED, "SUCCESS",
   ("R01", "R74", "R75"),
   "Set User1 Enabled=True via Admin1. Default was False (R75). "
   "Admin1 is enabled by default (R74).")

_t(S.LOCKING_RW_ADMIN1, A.SET_ACE_BOOLEXPR, S.LOCKING_RW_ADMIN1, "INVALID_PARAMETER",
   ("R77",),
   "Set ACE BooleanExpr to unsupported value — INVALID_PARAMETER (R77).")

_t(S.LOCKING_RW_ADMIN1, A.SET_GLOBAL_RANGE_START, S.LOCKING_RW_ADMIN1, "INVALID_PARAMETER",
   ("R82",),
   "Set RangeStart/RangeLength on GlobalRange — not modifiable (R82).")

_t(S.LOCKING_RW_ADMIN1, A.SET_READLOCKED_NO_ENABLE, S.LOCKING_RW_ADMIN1, "FAIL",
   ("R83",),
   "Set ReadLocked=True when ReadLockEnabled=False — ineffective/fails (R83).")

_t(S.LOCKING_RW_ADMIN1, A.SET_LOCK_ON_RESET, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R84"),
   "Set LockOnReset to supported value {0} or {0,3} (R84).")

_t(S.LOCKING_RW_ADMIN1, A.SET_LOCK_ON_RESET_BAD, S.LOCKING_RW_ADMIN1, "INVALID_PARAMETER",
   ("R61",),
   "Set LockOnReset to unsupported value — INVALID_PARAMETER (R61).")

_t(S.LOCKING_RW_ADMIN1, A.GENKEY_ADMIN, S.LOCKING_KEY_SET, "SUCCESS",
   ("R01", "R41", "R66"),
   "GenKey on K_AES range key with Admin auth (R66). "
   "Tries reset on PIN/key change (R41).")

_t(S.LOCKING_RW_ADMIN1, A.SET_CPIN_ADMIN1, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R41"),
   "Set C_PIN_Admin1 PIN. Tries reset (R41).")

_t(S.LOCKING_RW_ADMIN1, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close Admin1 LockingSP session.")

_t(S.LOCKING_RW_ADMIN1, A.REVERTSP_LOCKING, S.SESSION_ABORTED, "SUCCESS",
   ("R01", "R58"),
   "RevertSP on LockingSP. Session aborted after (R58).")

_t(S.LOCKING_RW_ADMIN1, A.REVERTSP_KEEP_KEY_LOCKED, S.LOCKING_RW_ADMIN1, "FAIL",
   ("R57",),
   "RevertSP with KeepGlobalRangeKey=True while GlobalRange is locked — "
   "FAIL (R57).")

_t(S.LOCKING_RW_ADMIN1, A.ACTIVATE_NOT_SID, S.LOCKING_RW_ADMIN1, "NOT_AUTHORIZED",
   ("R02", "R67"),
   "Activate invoked by Admin1 (not SID) — NOT_AUTHORIZED (R67).")

_t(S.LOCKING_RW_ADMIN1, A.REVERT_NOT_SID, S.LOCKING_RW_ADMIN1, "NOT_AUTHORIZED",
   ("R02", "R68"),
   "Revert invoked without SID/Admins — NOT_AUTHORIZED (R68).")

# Changed: added READ_DATA, WRITE_DATA for LOCKING_RW_ADMIN1
# Why: public20 has Read/Write data commands; FSM needs coverage.
_t(S.LOCKING_RW_ADMIN1, A.READ_DATA, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R65"),
   "Read data from locking range with Admin1 auth (R65).")

_t(S.LOCKING_RW_ADMIN1, A.WRITE_DATA, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R65"),
   "Write data to locking range with Admin1 auth (R65).")

# Changed: added GET_LOCKINGINFO for LOCKING_RW_ADMIN1
# Why: GFlowNet rarely picks GET_LOCKINGINFO; add to more states.
_t(S.LOCKING_RW_ADMIN1, A.GET_LOCKINGINFO, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01",),
   "Get LockingInfo table with Admin1 auth.")

# ===== LockingSP RW ADMIN1 — Set range alignment errors =====

_t(S.LOCKING_RW_ADMIN1, A.SET_LOCKING_RANGE_RW, S.LOCKING_RANGE_SET, "SUCCESS",
   ("R01", "R08", "R65"),
   "Set range parameters with valid alignment.")

# Alignment errors — registered from LOCKING_RANGE_SET to stay in same state
_t(S.LOCKING_RANGE_SET, A.SET_LOCKING_RANGE_RW, S.LOCKING_RANGE_SET, "INVALID_PARAMETER",
   ("R08", "R59", "R60"),
   "Set range with misaligned RangeStart (R59) or RangeLength (R60). "
   "INVALID_PARAMETER on bad parameter (R08).")

# ===== LockingSP RW ADMIN1 — USER_ENABLED =====

_t(S.LOCKING_RW_ADMIN1_USER_ENABLED, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session after enabling User1.")

_t(S.LOCKING_RW_ADMIN1_USER_ENABLED, A.GET_AUTHORITY_TABLE, S.LOCKING_RW_ADMIN1_USER_ENABLED, "SUCCESS",
   ("R01", "R18", "R20", "R74", "R75"),
   "Get Authority table to verify User1 is now enabled.")

# ===== LockingSP RW USER1 =====

_t(S.LOCKING_RW_USER1, A.GET_LOCKING_RANGE, S.LOCKING_RW_USER1, "SUCCESS",
   ("R01", "R18", "R20"),
   "Get Locking range as User1.")

_t(S.LOCKING_RW_USER1, A.SET_LOCKING_READLOCKED, S.LOCKING_RW_USER1, "NOT_AUTHORIZED",
   ("R02", "R21", "R65"),
   "Set ReadLocked as User1 (default ACE requires Admins) — "
   "NOT_AUTHORIZED (R02, R21, R65).")

_t(S.LOCKING_RW_USER1, A.GENKEY_NON_ADMIN, S.LOCKING_RW_USER1, "NOT_AUTHORIZED",
   ("R02", "R66"),
   "GenKey as User1 — NOT_AUTHORIZED, requires Admin (R66).")

_t(S.LOCKING_RW_USER1, A.SET_AUTHORITY_ENABLED, S.LOCKING_RW_USER1, "NOT_AUTHORIZED",
   ("R02", "R69"),
   "Set Authority Enabled as User1 in LockingSP — NOT_AUTHORIZED (R69).")

# Changed: added READ_DATA, WRITE_DATA for LOCKING_RW_USER1
# Why: User1 lacks admin ACE, so data I/O is NOT_AUTHORIZED.
_t(S.LOCKING_RW_USER1, A.READ_DATA, S.LOCKING_RW_USER1, "NOT_AUTHORIZED",
   ("R02", "R65"),
   "Read data as User1 — NOT_AUTHORIZED, requires Admin ACE (R65).")

_t(S.LOCKING_RW_USER1, A.WRITE_DATA, S.LOCKING_RW_USER1, "NOT_AUTHORIZED",
   ("R02", "R65"),
   "Write data as User1 — NOT_AUTHORIZED, requires Admin ACE (R65).")

_t(S.LOCKING_RW_USER1, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close User1 LockingSP session.")

# ===== LockingSP RO sessions =====

_t(S.LOCKING_RO_NOBODY, A.GET_LOCKING_RANGE, S.LOCKING_RO_NOBODY, "SUCCESS",
   ("R01", "R18", "R20"),
   "Get Locking range in RO session, Anybody.")

_t(S.LOCKING_RO_NOBODY, A.SET_IN_RO_SESSION, S.LOCKING_RO_NOBODY, "NOT_AUTHORIZED",
   ("R02", "R11", "R12"),
   "Set in RO session — no permanent changes (R11). Write=False (R12).")

_t(S.LOCKING_RO_NOBODY, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close RO LockingSP Anybody session.")

_t(S.LOCKING_RO_ADMIN1, A.GET_LOCKING_RANGE, S.LOCKING_RO_ADMIN1, "SUCCESS",
   ("R01", "R18", "R20"),
   "Get Locking range in RO session with Admin1.")

_t(S.LOCKING_RO_ADMIN1, A.SET_IN_RO_SESSION, S.LOCKING_RO_ADMIN1, "NOT_AUTHORIZED",
   ("R02", "R11", "R12"),
   "Set in RO session — not allowed (R11, R12).")

# Changed: added READ_DATA, WRITE_DATA for LOCKING_RO_ADMIN1
# Why: RO session allows read but blocks write (R11).
_t(S.LOCKING_RO_ADMIN1, A.READ_DATA, S.LOCKING_RO_ADMIN1, "SUCCESS",
   ("R01", "R11", "R65"),
   "Read data in RO session with Admin1 — read succeeds (R65), "
   "session is read-only (R11).")

_t(S.LOCKING_RO_ADMIN1, A.WRITE_DATA, S.LOCKING_RO_ADMIN1, "NOT_AUTHORIZED",
   ("R02", "R11"),
   "Write data in RO session — NOT_AUTHORIZED, no permanent changes (R11).")

_t(S.LOCKING_RO_ADMIN1, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close RO LockingSP Admin1 session.")

# ===== LOCKING_RANGE_SET =====

_t(S.LOCKING_RANGE_SET, A.SET_LOCKING_READLOCKED, S.LOCKING_RANGE_LOCKED, "SUCCESS",
   ("R01", "R65"),
   "Set ReadLocked=True on configured range.")

_t(S.LOCKING_RANGE_SET, A.SET_LOCKING_WRITELOCKED, S.LOCKING_RANGE_LOCKED, "SUCCESS",
   ("R01", "R65"),
   "Set WriteLocked=True on configured range.")

_t(S.LOCKING_RANGE_SET, A.GENKEY_ADMIN, S.LOCKING_KEY_SET, "SUCCESS",
   ("R01", "R41", "R66"),
   "GenKey on configured range.")

# Changed: added READ_DATA, WRITE_DATA, GET_LOCKINGINFO for LOCKING_RANGE_SET
# Why: range configured but unlocked — data I/O succeeds; GET_LOCKINGINFO boosts coverage.
_t(S.LOCKING_RANGE_SET, A.READ_DATA, S.LOCKING_RANGE_SET, "SUCCESS",
   ("R01", "R65"),
   "Read data from configured (unlocked) range.")

_t(S.LOCKING_RANGE_SET, A.WRITE_DATA, S.LOCKING_RANGE_SET, "SUCCESS",
   ("R01", "R65"),
   "Write data to configured (unlocked) range.")

_t(S.LOCKING_RANGE_SET, A.GET_LOCKINGINFO, S.LOCKING_RANGE_SET, "SUCCESS",
   ("R01",),
   "Get LockingInfo table with range configured.")

_t(S.LOCKING_RANGE_SET, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session with range configured.")

# ===== LOCKING_RANGE_LOCKED =====

_t(S.LOCKING_RANGE_LOCKED, A.SET_LOCKING_READLOCKED, S.LOCKING_RANGE_SET, "SUCCESS",
   ("R01", "R65"),
   "Set ReadLocked=False — unlock the range.")

_t(S.LOCKING_RANGE_LOCKED, A.REVERTSP_KEEP_KEY_LOCKED, S.LOCKING_RANGE_LOCKED, "FAIL",
   ("R57",),
   "RevertSP with KeepGlobalRangeKey=True while range is locked — FAIL (R57).")

# Changed: added READ_DATA, WRITE_DATA, GET_LOCKINGINFO for LOCKING_RANGE_LOCKED
# Why: range locked — data I/O fails (R83); GET_LOCKINGINFO still succeeds.
_t(S.LOCKING_RANGE_LOCKED, A.READ_DATA, S.LOCKING_RANGE_LOCKED, "FAIL",
   ("R01", "R83"),
   "Read data from locked range — FAIL, ReadLockEnabled blocks access (R83).")

_t(S.LOCKING_RANGE_LOCKED, A.WRITE_DATA, S.LOCKING_RANGE_LOCKED, "FAIL",
   ("R01", "R83"),
   "Write data to locked range — FAIL, WriteLockEnabled blocks access (R83).")

_t(S.LOCKING_RANGE_LOCKED, A.GET_LOCKINGINFO, S.LOCKING_RANGE_LOCKED, "SUCCESS",
   ("R01",),
   "Get LockingInfo table with range locked.")

_t(S.LOCKING_RANGE_LOCKED, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session with range locked.")

# ===== LOCKING_KEY_SET =====

_t(S.LOCKING_KEY_SET, A.SET_LOCKING_READLOCKED, S.LOCKING_RANGE_LOCKED, "SUCCESS",
   ("R01", "R65"),
   "Lock range after key generation.")

_t(S.LOCKING_KEY_SET, A.SET_LOCKING_WRITELOCKED, S.LOCKING_RANGE_LOCKED, "SUCCESS",
   ("R01", "R65"),
   "Write-lock range after key generation.")

# Changed: added READ_DATA, WRITE_DATA, GET_LOCKINGINFO for LOCKING_KEY_SET
# Why: key set but unlocked — data I/O succeeds; GET_LOCKINGINFO boosts coverage.
_t(S.LOCKING_KEY_SET, A.READ_DATA, S.LOCKING_KEY_SET, "SUCCESS",
   ("R01", "R65"),
   "Read data from range with AES key set (unlocked).")

_t(S.LOCKING_KEY_SET, A.WRITE_DATA, S.LOCKING_KEY_SET, "SUCCESS",
   ("R01", "R65"),
   "Write data to range with AES key set (unlocked).")

_t(S.LOCKING_KEY_SET, A.GET_LOCKINGINFO, S.LOCKING_KEY_SET, "SUCCESS",
   ("R01",),
   "Get LockingInfo table after key generation.")

_t(S.LOCKING_KEY_SET, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session after key generation.")

# ===== AUTH_FAILED_RETRY =====

_t(S.AUTH_FAILED_RETRY, A.AUTH_SID_CORRECT, S.ADMIN_RW_SID, "SUCCESS",
   ("R01", "R31", "R38"),
   "Retry SID auth with correct password after prior failure. "
   "Tries reset (R38).")

_t(S.AUTH_FAILED_RETRY, A.AUTH_ADMIN1_CORRECT, S.LOCKING_RW_ADMIN1, "SUCCESS",
   ("R01", "R31", "R38"),
   "Retry Admin1 auth with correct password after failure.")

_t(S.AUTH_FAILED_RETRY, A.AUTH_SID_WRONG, S.AUTH_FAILED_RETRY, "SUCCESS",
   ("R32", "R37"),
   "Repeated wrong password — Tries incremented again (R37).")

_t(S.AUTH_FAILED_RETRY, A.AUTH_LOCKED_OUT_ATTEMPT, S.AUTH_LOCKED_OUT, "SUCCESS",
   ("R09", "R39"),
   "Auth attempt when Tries==TryLimit. result=False or AUTHORITY_LOCKED_OUT (R09). "
   "Tries SHALL NOT exceed TryLimit (R39).")

_t(S.AUTH_FAILED_RETRY, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session after auth failure.")

_t(S.AUTH_FAILED_RETRY, A.RECOVER_FROM_ERROR, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Recover from auth failure by returning to idle state.")

# ===== AUTH_LOCKED_OUT =====

_t(S.AUTH_LOCKED_OUT, A.AUTH_LOCKED_OUT_ATTEMPT, S.AUTH_LOCKED_OUT, "AUTHORITY_LOCKED_OUT",
   ("R09", "R39", "R40"),
   "Further auth attempts while locked out. Tries stays at TryLimit (R39). "
   "TryLimit=0 means unlimited (R40 — tested in pass scenario).")

_t(S.AUTH_LOCKED_OUT, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close session when locked out.")

_t(S.AUTH_LOCKED_OUT, A.POWER_CYCLE, S.POWERED_ON, "SUCCESS",
   ("R42",),
   "Power cycle to reset Tries if Persistence=False (R42).")

# ===== MAX_SESSIONS =====

_t(S.MAX_SESSIONS, A.CLOSE_SESSION, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Close one session to free up capacity.")

_t(S.MAX_SESSIONS, A.START_SESSION_MAX, S.MAX_SESSIONS, "NO_SESSIONS_AVAILABLE",
   ("R06",),
   "Another session attempt while at max — still NO_SESSIONS_AVAILABLE (R06).")

# ===== REVERTED / SESSION_ABORTED =====

_t(S.SESSION_ABORTED, A.RECOVER_FROM_ERROR, S.POWERED_ON, "SUCCESS",
   ("R01",),
   "After Revert/RevertSP session abort, host returns to powered-on state.")

_t(S.SESSION_ABORTED, A.POWER_CYCLE, S.POWERED_ON, "SUCCESS",
   ("R42", "R84"),
   "Power cycle after session abort.")

_t(S.REVERTED, A.POWER_CYCLE, S.POWERED_ON, "SUCCESS",
   ("R42", "R84"),
   "Power cycle after full TPer revert.")

_t(S.REVERTED, A.RECOVER_FROM_ERROR, S.POWERED_ON, "SUCCESS",
   ("R01",),
   "Recover from reverted state.")

# ===== ERROR_RECOVERY =====

_t(S.ERROR_RECOVERY, A.RECOVER_FROM_ERROR, S.PROPS_QUERIED, "SUCCESS",
   ("R01",),
   "Recover from error — return to idle post-Properties state.")

_t(S.ERROR_RECOVERY, A.POWER_CYCLE, S.POWERED_ON, "SUCCESS",
   ("R42", "R84"),
   "Power cycle from error recovery.")

# ===== POWER_OFF from any reachable state (model shutdown) =====

for _s in S:
    if _s != S.POWER_OFF:
        if (S.POWER_OFF, A.POWER_ON) != (_s, A.POWER_ON):
            # Only add POWER_CYCLE if not already defined for this state
            if (_s, A.POWER_CYCLE) not in DELTA:
                _t(_s, A.POWER_CYCLE, S.POWERED_ON, "SUCCESS",
                   ("R42", "R84"),
                   f"Power cycle from {_s.name}. Tries reset (R42), ranges re-lock (R84).")

# ===== R40 explicit coverage: TryLimit=0 means unlimited =====
# Already covered via AUTH_LOCKED_OUT description, but add explicit transition
# from ADMIN_RW_NOBODY for the TryLimit=0 scenario.
_t(S.ADMIN_RW_NOBODY, A.AUTH_LOCKED_OUT_ATTEMPT, S.ADMIN_RW_NOBODY, "SUCCESS",
   ("R09", "R40"),
   "Auth attempt with TryLimit=0 — unlimited tries, Tries stays 0 (R40). "
   "Or AUTHORITY_LOCKED_OUT if TryLimit>0 and reached (R09).")


# ---------------------------------------------------------------------------
# Q0 — initial state
# ---------------------------------------------------------------------------

Q0: S = S.POWER_OFF

# ---------------------------------------------------------------------------
# F — terminal / absorbing states
# ---------------------------------------------------------------------------

F: FrozenSet[S] = frozenset({
    S.POWER_OFF,
    S.REVERTED,
    S.AUTH_LOCKED_OUT,
})


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_valid_actions(state: S) -> List[A]:
    """Return the list of valid actions from *state*."""
    return [action for (s, action) in DELTA if s == state]


def get_transition(state: S, action: A) -> Optional[Transition]:
    """Return the transition for (state, action), or None."""
    return DELTA.get((state, action))


def all_rules_covered() -> Tuple[Set[str], Set[str]]:
    """Return (covered_rules, missing_rules) across all transitions."""
    covered: Set[str] = set()
    for t in DELTA.values():
        covered.update(t.rules)
    expected = {f"R{i:02d}" for i in range(1, 87)}
    missing = expected - covered
    return covered, missing


def reachable_states(start: S = Q0) -> Set[S]:
    """BFS from *start* to find all reachable states."""
    visited: Set[S] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        if current in visited:
            continue
        visited.add(current)
        for action in get_valid_actions(current):
            t = DELTA[(current, action)]
            if t.next_state not in visited:
                frontier.append(t.next_state)
    return visited


def print_fsm_summary() -> None:
    """Print comprehensive FSM statistics."""
    print("=" * 72)
    print("  TCG/Opal Unified FSM Summary")
    print("=" * 72)

    print(f"\n  States  |Q|     = {len(S)}")
    print(f"  Actions |Sigma| = {len(A)}")
    print(f"  Transitions |delta| = {len(DELTA)}")
    print(f"  Initial state q0    = {Q0.name}")
    print(f"  Terminal states |F| = {len(F)}")
    for f_state in sorted(F, key=lambda s: s.value):
        print(f"    - {f_state.name}")

    # Reachability
    reached = reachable_states()
    unreachable = set(S) - reached
    print(f"\n  Reachable states    = {len(reached)}")
    if unreachable:
        print(f"  Unreachable states  = {len(unreachable)}")
        for u in sorted(unreachable, key=lambda s: s.value):
            print(f"    ! {u.name}")

    # Rule coverage
    covered, missing = all_rules_covered()
    print(f"\n  Rules covered       = {len(covered)} / 86")
    if missing:
        print(f"  MISSING rules       = {sorted(missing)}")
    else:
        print("  All 86 rules covered.")

    # Per-state action counts
    print(f"\n  Actions per state:")
    for state in S:
        actions = get_valid_actions(state)
        if actions:
            print(f"    {state.name:40s} : {len(actions):3d} actions")

    # Status distribution
    status_counts: Dict[str, int] = {}
    for t in DELTA.values():
        status_counts[t.expected_status] = status_counts.get(t.expected_status, 0) + 1
    print(f"\n  Status code distribution:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"    {status:30s} : {count:3d} transitions")

    # Rule frequency
    rule_freq: Dict[str, int] = {}
    for t in DELTA.values():
        for r in t.rules:
            rule_freq[r] = rule_freq.get(r, 0) + 1
    print(f"\n  Top 10 most-referenced rules:")
    for rule, count in sorted(rule_freq.items(), key=lambda x: -x[1])[:10]:
        print(f"    {rule} : {count} transitions")

    least_referenced = sorted(rule_freq.items(), key=lambda x: x[1])[:10]
    print(f"\n  10 least-referenced rules:")
    for rule, count in least_referenced:
        print(f"    {rule} : {count} transitions")

    print("\n" + "=" * 72)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_fsm_summary()

    # Verify all 86 rules are covered
    covered, missing = all_rules_covered()
    if missing:
        print(f"\nERROR: Missing rules: {sorted(missing)}")
        raise SystemExit(1)
    else:
        print("\nOK: All 86 rules (R01-R86) are covered by at least one transition.")

    # Verify reachability
    reached = reachable_states()
    unreachable = set(S) - reached
    if unreachable:
        print(f"WARNING: Unreachable states: {sorted(u.name for u in unreachable)}")
    else:
        print("OK: All states are reachable from Q0.")

    # Verify typical flow path
    typical_path = [
        (S.POWER_OFF, A.POWER_ON, S.POWERED_ON),
        (S.POWERED_ON, A.PROPERTIES, S.PROPS_QUERIED),
        (S.PROPS_QUERIED, A.START_RW_ADMIN_NOBODY, S.ADMIN_RW_NOBODY),
        (S.ADMIN_RW_NOBODY, A.GET_MSID_PIN, S.ADMIN_RW_NOBODY),
        (S.ADMIN_RW_NOBODY, A.CLOSE_SESSION, S.PROPS_QUERIED),
        (S.PROPS_QUERIED, A.START_RW_ADMIN_SID, S.ADMIN_RW_SID),
        (S.ADMIN_RW_SID, A.SET_SID_PIN, S.ADMIN_RW_SID),
        (S.ADMIN_RW_SID, A.ACTIVATE_LOCKING_SP, S.ADMIN_RW_SID_ACTIVATED),
        (S.ADMIN_RW_SID_ACTIVATED, A.CLOSE_SESSION, S.PROPS_QUERIED),
        (S.PROPS_QUERIED, A.START_RW_LOCKING_ADMIN1, S.LOCKING_RW_ADMIN1),
        (S.LOCKING_RW_ADMIN1, A.SET_LOCKING_RANGE_RW, S.LOCKING_RANGE_SET),
        (S.LOCKING_RANGE_SET, A.GENKEY_ADMIN, S.LOCKING_KEY_SET),
        (S.LOCKING_KEY_SET, A.SET_LOCKING_READLOCKED, S.LOCKING_RANGE_LOCKED),
        (S.LOCKING_RANGE_LOCKED, A.SET_LOCKING_READLOCKED, S.LOCKING_RANGE_SET),
        (S.LOCKING_RANGE_SET, A.CLOSE_SESSION, S.PROPS_QUERIED),
    ]
    print("\nVerifying typical Opal setup flow:")
    for state, action, expected_next in typical_path:
        t = DELTA.get((state, action))
        if t is None:
            print(f"  FAIL: No transition for ({state.name}, {action.name})")
            raise SystemExit(1)
        if t.next_state != expected_next:
            print(f"  FAIL: ({state.name}, {action.name}) -> {t.next_state.name} "
                  f"(expected {expected_next.name})")
            raise SystemExit(1)
        print(f"  OK: {state.name} --[{action.name}]--> {t.next_state.name} "
              f"({t.expected_status})")
    print("OK: Typical flow path verified.")
