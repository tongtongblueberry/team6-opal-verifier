# Changed: create Record Builder to convert FSM (state, action) pairs to Opal JSON records
# Why: GFlowNet produces abstract (state, action) trajectories; we need concrete JSON for training
"""
Opal Record Builder
====================
Converts FSM (state, action, output_status) triples into concrete
TCG/Opal JSON records matching the public20 schema.

Each action in Σ maps to a specific JSON record structure with
randomized but realistic values (session IDs, credentials, etc.).
"""

import hashlib
import json
import random
from typing import Optional


# ── UIDs ──
# Changed: split UID format per field type to match public20 exactly
# Why: public20 uses space-separated for invoking_id.uid and method.uid,
#      but no-space for SPID and HostSigningAuthority.
#      Previous fix made everything no-space, which broke invoking_id.uid/method.uid.

# invoking_id.uid — SPACE-SEPARATED (matches public20)
UID_SESSION_MGR = "00 00 00 00 00 00 00 FF"
UID_CPIN_SID = "00 00 00 0B 00 00 00 01"
UID_CPIN_MSID = "00 00 00 0B 00 00 84 02"
UID_CPIN_ADMIN1 = "00 00 00 0B 00 01 00 01"
UID_CPIN_USER1 = "00 00 00 0B 00 03 00 01"
UID_SP_LOCKING = "00 00 02 05 00 00 00 02"
UID_SP_ADMIN = "00 00 02 05 00 00 00 01"
UID_LOCKING_GLOBAL = "00 00 08 02 00 00 00 01"
UID_LOCKING_RANGE1 = "00 00 08 02 00 03 00 01"
UID_LOCKING_INFO = "00 00 08 01 00 00 00 01"
UID_MBRCONTROL = "00 00 08 03 00 00 00 01"
UID_AUTHORITY_ADMIN1 = "00 00 00 09 00 01 00 01"
UID_KAES_RANGE1 = "00 00 08 06 00 03 00 01"
UID_ANYBODY = "00 00 00 09 00 00 00 01"
UID_USER1 = "00 00 00 09 00 03 00 01"  # invoking_id.uid for Authority.Set(User1.Enabled)

# HostSigningAuthority — NO-SPACE (matches public20)
HSA_SID = "0000000900000006"
HSA_ADMIN1 = "0000000900010001"
HSA_USER1 = "0000000900030001"
HSA_ADMINS_CLASS = "0000000900000005"

# SPID — NO-SPACE (matches public20)
ADMIN_SP = "0000020500000001"
LOCKING_SP = "0000020500000002"

# method.uid — SPACE-SEPARATED (matches public20)
METHOD_PROPERTIES = "00 00 00 00 00 00 FF 01"
METHOD_STARTSESSION = "00 00 00 00 00 00 FF 02"
METHOD_SYNCSESSION = "00 00 00 00 00 00 FF 03"
METHOD_GET = "00 00 00 06 00 00 00 16"
METHOD_SET = "00 00 00 06 00 00 00 17"
METHOD_ACTIVATE = "00 00 00 06 00 00 02 03"
METHOD_GENKEY = "00 00 00 06 00 00 00 10"
METHOD_READ = "00 00 00 06 00 00 00 16"
METHOD_WRITE = "00 00 00 06 00 00 00 17"


class ValueGen:
    """Generate realistic random values."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        # Persistent credential state across a trajectory
        self.sid_pin = self._make_pin()
        self.msid_pin = self._make_msid()
        self.new_sid_pin = self._make_pin()
        self._session_counter = 0

    def _make_pin(self) -> str:
        return hashlib.sha256(self.rng.randbytes(16)).hexdigest()

    def _make_msid(self) -> str:
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        return "".join(self.rng.choice(chars) for _ in range(32))

    def session_id(self) -> str:
        self._session_counter += 1
        base = self.rng.randint(0x6000, 0x6fff)
        return f"{base + self._session_counter:08x}"

    def wrong_challenge(self) -> str:
        # Changed: generate a random hex string each time instead of hardcoded "b" * 64
        # Why: hardcoded value caused 32% of HostChallenges to be identical
        return hashlib.sha256(self.rng.randbytes(16)).hexdigest()

    def host_session_id(self) -> str:
        return "00000001"


class OpalRecordBuilder:
    """Build Opal JSON records from FSM action names."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.vg = ValueGen(self.rng)

    def reset_trajectory(self):
        """Reset value generator for a new trajectory."""
        self.vg = ValueGen(self.rng)

    def build(self, action_name: str, output_status: str, index: int) -> dict:
        """Build a JSON record for the given FSM action.

        Args:
            action_name: FSM action enum name (e.g., 'START_RW_ADMIN_SID')
            output_status: status code for output (e.g., 'SUCCESS', 'NOT_AUTHORIZED')
            index: record index in trajectory (1-based)

        Returns:
            dict matching public20 record schema
        """
        builder_map = {
            # Power/Properties
            'POWER_ON': self._power_on,
            'POWER_CYCLE': self._power_cycle,
            'PROPERTIES': self._properties,

            # StartSession
            'START_RW_ADMIN_NOBODY': lambda s, i: self._start_session(ADMIN_SP, None, None, s, i),
            'START_RW_ADMIN_SID': lambda s, i: self._start_session(ADMIN_SP, HSA_SID, self.vg.sid_pin, s, i),
            'START_RW_ADMIN_SID_WRONG_PW': lambda s, i: self._start_session(ADMIN_SP, HSA_SID, self.vg.wrong_challenge(), s, i),
            'START_RO_ADMIN_NOBODY': lambda s, i: self._start_session_ro(ADMIN_SP, None, None, s, i),
            'START_RO_ADMIN_SID': lambda s, i: self._start_session_ro(ADMIN_SP, HSA_SID, self.vg.sid_pin, s, i),
            'START_RW_LOCKING_NOBODY': lambda s, i: self._start_session(LOCKING_SP, None, None, s, i),
            'START_RW_LOCKING_ADMIN1': lambda s, i: self._start_session(LOCKING_SP, HSA_ADMIN1, self.vg.sid_pin, s, i),
            'START_RW_LOCKING_ADMIN1_WRONG_PW': lambda s, i: self._start_session(LOCKING_SP, HSA_ADMIN1, self.vg.wrong_challenge(), s, i),
            'START_RW_LOCKING_USER1': lambda s, i: self._start_session(LOCKING_SP, HSA_USER1, self.vg.sid_pin, s, i),
            'START_RO_LOCKING_NOBODY': lambda s, i: self._start_session_ro(LOCKING_SP, None, None, s, i),
            'START_RO_LOCKING_ADMIN1': lambda s, i: self._start_session_ro(LOCKING_SP, HSA_ADMIN1, self.vg.sid_pin, s, i),
            'START_SESSION_INACTIVE_SP': lambda s, i: self._start_session(LOCKING_SP, None, None, s, i),
            'START_SESSION_FROZEN_SP': lambda s, i: self._start_session(LOCKING_SP, None, None, s, i),
            'START_SESSION_CLASS_AUTH': lambda s, i: self._start_session(ADMIN_SP, HSA_ADMINS_CLASS, self.vg.wrong_challenge(), s, i),
            'START_SESSION_BAD_TIMEOUT': lambda s, i: self._start_session(ADMIN_SP, None, None, s, i),
            'START_SESSION_EXCHANGE_AUTH': lambda s, i: self._start_session(ADMIN_SP, HSA_SID, self.vg.sid_pin, s, i),
            'START_SESSION_TPERSIGN_AUTH': lambda s, i: self._start_session(ADMIN_SP, HSA_SID, self.vg.sid_pin, s, i),
            'START_SESSION_CONCURRENT': lambda s, i: self._start_session(ADMIN_SP, None, None, s, i),
            'START_SESSION_MAX': lambda s, i: self._start_session(ADMIN_SP, None, None, s, i),

            # EndSession
            'CLOSE_SESSION': self._end_session,

            # Auth (in-session)
            'AUTH_SID_CORRECT': lambda s, i: self._auth(HSA_SID, self.vg.sid_pin, s, i),
            'AUTH_SID_WRONG': lambda s, i: self._auth(HSA_SID, self.vg.wrong_challenge(), s, i),
            'AUTH_ADMIN1_CORRECT': lambda s, i: self._auth(HSA_ADMIN1, self.vg.sid_pin, s, i),
            'AUTH_ADMIN1_WRONG': lambda s, i: self._auth(HSA_ADMIN1, self.vg.wrong_challenge(), s, i),
            'AUTH_USER1_CORRECT': lambda s, i: self._auth(HSA_USER1, self.vg.sid_pin, s, i),
            'AUTH_USER1_WRONG': lambda s, i: self._auth(HSA_USER1, self.vg.wrong_challenge(), s, i),
            'AUTH_ANYBODY': lambda s, i: self._auth("0000000900000001", None, s, i),
            'AUTH_NONEXISTENT': lambda s, i: self._auth("0000000900FF00FF", None, s, i),
            'AUTH_CLASS_AUTHORITY': lambda s, i: self._auth(HSA_ADMINS_CLASS, None, s, i),
            'AUTH_DISABLED_AUTHORITY': lambda s, i: self._auth(HSA_USER1, self.vg.sid_pin, s, i),
            'AUTH_EXCHANGE_AUTHORITY': lambda s, i: self._auth(HSA_SID, None, s, i),
            'AUTH_MAX_EXCEEDED': lambda s, i: self._auth(HSA_SID, self.vg.sid_pin, s, i),
            'AUTH_LOCKED_OUT_ATTEMPT': lambda s, i: self._auth(HSA_SID, self.vg.wrong_challenge(), s, i),

            # Get
            'GET_MSID_PIN': lambda s, i: self._get("C_PIN", UID_CPIN_MSID, [{"startColumn": 3}, {"endColumn": 3}], [[{"3": self.vg.msid_pin}]], s, i),
            'GET_CPIN_SID': lambda s, i: self._get("C_PIN", UID_CPIN_SID, [{"startColumn": 3}, {"endColumn": 3}], [[{"3": self.vg.sid_pin}]], s, i),
            'GET_LOCKING_RANGE': lambda s, i: self._get("Locking", UID_LOCKING_RANGE1, [{"startColumn": 3}, {"endColumn": 8}], [[{"3": 0}, {"4": 0}, {"5": False}, {"6": False}, {"7": False}, {"8": False}]], s, i),
            'GET_AUTHORITY_TABLE': lambda s, i: self._get("Authority", UID_AUTHORITY_ADMIN1, [{"startColumn": 5}, {"endColumn": 5}], [[{"5": True}]], s, i),
            'GET_NONEXISTENT_OBJ': lambda s, i: self._get("Unknown", "0000FFFF00000001", [{"startColumn": 1}], [], s, i),
            'GET_BAD_CELLBLOCK': lambda s, i: self._get("C_PIN", UID_CPIN_SID, [{"startColumn": 255}, {"endColumn": 255}], [], s, i),
            'GET_BYTE_TABLE_COL': lambda s, i: self._get("MBRControl", UID_MBRCONTROL, [{"startColumn": 1}], [], s, i),
            'GET_BYTE_TABLE_UNAUTH': lambda s, i: self._get("MBRControl", UID_MBRCONTROL, [{"startColumn": 1}, {"endColumn": 2}], [], s, i),
            'GET_OBJ_WITH_ROW_PARAM': lambda s, i: self._get("C_PIN", UID_CPIN_SID, [{"startColumn": 3}, {"endColumn": 3}, {"startRow": 1}], [], s, i),
            'GET_COLUMN_ORDER_CHECK': lambda s, i: self._get("Locking", UID_LOCKING_RANGE1, [{"startColumn": 3}, {"endColumn": 8}], [[{"3": 0}, {"4": 0}, {"5": False}, {"6": False}, {"7": False}, {"8": False}]], s, i),
            # Changed: add GET_LOCKINGINFO — was missing, fell through to _fallback (Properties)
            # Why: LockingInfo records were 0% in gen_gflownet despite FSM having 4 transitions
            'GET_LOCKINGINFO': lambda s, i: self._get("LockingInfo", UID_LOCKING_INFO, [{"startColumn": 1}, {"endColumn": 3}], [[{"1": 0}, {"2": 0}, {"3": 0}]] if s == "SUCCESS" else [], s, i),

            # Set
            'SET_SID_PIN': lambda s, i: self._set("C_PIN", UID_CPIN_SID, [{"3": self.vg.new_sid_pin}], s, i),
            'SET_CPIN_ADMIN1': lambda s, i: self._set("C_PIN", UID_CPIN_ADMIN1, [{"3": self.vg._make_pin()}], s, i),
            'SET_LOCKING_RANGE_RW': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"3": 0}, {"4": 0}], s, i),
            'SET_LOCKING_READLOCKED': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"7": True}], s, i),
            'SET_LOCKING_WRITELOCKED': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"8": True}], s, i),
            'SET_AUTHORITY_ENABLED': lambda s, i: self._set("Authority", UID_AUTHORITY_ADMIN1, [{"5": 1}], s, i),
            'SET_USER_ENABLED': lambda s, i: self._set("Authority", UID_USER1, [{"5": 1}], s, i),
            'SET_ACE_BOOLEXPR': lambda s, i: self._set("ACE", "0000000D00010001", [{"3": "User1"}], s, i),
            'SET_DUPLICATE_COLUMN': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"7": True}, {"7": False}], s, i),
            'SET_WITH_WHERE_ON_OBJ': lambda s, i: self._set("C_PIN", UID_CPIN_SID, [{"3": self.vg.sid_pin}], s, i),
            'SET_TABLE_NO_WHERE': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"7": True}], s, i),
            'SET_BYTE_TABLE_ROWVALS': lambda s, i: self._set("MBRControl", UID_MBRCONTROL, [{"1": True}], s, i),
            'SET_OBJ_TABLE_BYTES': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"data": "0000"}], s, i),
            'SET_NO_VALUES': lambda s, i: self._set("C_PIN", UID_CPIN_SID, None, s, i),
            'SET_UID_COLUMN': lambda s, i: self._set("Authority", UID_AUTHORITY_ADMIN1, [{"0": "0000000900FF0001"}], s, i),
            'SET_GLOBAL_RANGE_START': lambda s, i: self._set("Locking", UID_LOCKING_GLOBAL, [{"3": 100}], s, i),
            'SET_READLOCKED_NO_ENABLE': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"7": True}], s, i),
            'SET_IN_RO_SESSION': lambda s, i: self._set("C_PIN", UID_CPIN_SID, [{"3": self.vg.sid_pin}], s, i),
            'SET_LOCK_ON_RESET': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"9": [0, 3]}], s, i),
            'SET_LOCK_ON_RESET_BAD': lambda s, i: self._set("Locking", UID_LOCKING_RANGE1, [{"9": [2]}], s, i),
            'SET_DONE_ON_RESET_BAD': lambda s, i: self._set("MBRControl", UID_MBRCONTROL, [{"2": [2]}], s, i),
            'SET_ACTIVE_DATA_REMOVAL_BAD': lambda s, i: self._set("SP", UID_SP_ADMIN, [{"10": 3}], s, i),

            # GenKey
            'GENKEY_ADMIN': lambda s, i: self._genkey("K_AES_256", UID_KAES_RANGE1, s, i),
            'GENKEY_NON_ADMIN': lambda s, i: self._genkey("K_AES_256", UID_KAES_RANGE1, s, i),

            # Changed: add READ_DATA and WRITE_DATA record builders
            # Why: these actions were missing from builder_map, falling through to _fallback
            'READ_DATA': lambda s, i: self._read_data("Locking", UID_LOCKING_RANGE1, s, i),
            'WRITE_DATA': lambda s, i: self._write_data("Locking", UID_LOCKING_RANGE1, s, i),

            # Lifecycle
            'ACTIVATE_LOCKING_SP': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'ACTIVATE_ISSUED_SP': lambda s, i: self._activate("SP", UID_SP_ADMIN, s, i),
            'ACTIVATE_ALREADY_ACTIVE': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'ACTIVATE_IN_RO': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'ACTIVATE_NOT_SID': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'REVERT_ADMIN_SP': lambda s, i: self._activate("SP", UID_SP_ADMIN, s, i),
            'REVERT_IN_RO': lambda s, i: self._activate("SP", UID_SP_ADMIN, s, i),
            'REVERT_NOT_SID': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'REVERT_INACTIVE_SP': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'REVERTSP_LOCKING': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),
            'REVERTSP_KEEP_KEY_LOCKED': lambda s, i: self._activate("SP", UID_SP_LOCKING, s, i),

            # Random
            'RANDOM_VALID': lambda s, i: self._properties(s, i),
            'RANDOM_COUNT_TOO_LARGE': lambda s, i: self._properties(s, i),
            'RANDOM_BAD_PARAM': lambda s, i: self._properties(s, i),

            # Next
            'NEXT_EMPTY': lambda s, i: self._get("Authority", UID_AUTHORITY_ADMIN1, [{"startColumn": 0}], [], s, i),

            # Recovery
            'RECOVER_FROM_ERROR': self._end_session,
        }

        fn = builder_map.get(action_name)
        if fn is None:
            return self._fallback(action_name, output_status, index)
        # Changed: builders may return None (e.g., POWER_ON, POWER_CYCLE) to signal
        # that the action produces no visible protocol record; caller must skip None
        result = fn(output_status, index)
        return result

    # ── Record builders ──

    def _properties(self, status: str, index: int) -> dict:
        if status == "SUCCESS":
            rv = [
                {"Properties": {
                    "MaxComPacketSize": "010200", "MaxIndTokenSize": "010004",
                    "MaxMethods": 1, "MaxPacketSize": "0101ec", "MaxPackets": 1,
                    "MaxResponseComPacketSize": "010200", "MaxSessions": self.rng.randint(1, 4),
                    "MaxSubpackets": 1, "MaxTransactionLimit": 1,
                    "MaxAuthentications": self.rng.randint(2, 8), "DefSessionTimeout": 0,
                }},
                {"HostProperties": {
                    "MaxComPacketSize": "0800", "MaxIndTokenSize": "07c8",
                    "MaxMethods": 1, "MaxPacketSize": "07ec", "MaxPackets": 1,
                    "MaxResponseComPacketSize": "0800", "MaxSubpackets": 1,
                }},
            ]
        else:
            rv = []
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": "Session Manager UID", "type": None, "uid": UID_SESSION_MGR},
                "method": {"args": [{"HostProperties": {"MaxComPacketSize": "0800", "MaxIndTokenSize": "07c8", "MaxMethods": 1, "MaxPacketSize": "07ec", "MaxPackets": 1, "MaxSubpackets": 1}}], "name": "Properties", "uid": METHOD_PROPERTIES},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": rv, "status_codes": status},
        }

    def _power_on(self, status: str, index: int) -> dict:
        # Changed: return None instead of a Properties record
        # Why: POWER_ON is an internal state transition, not a protocol record
        return None

    def _power_cycle(self, status: str, index: int) -> dict:
        # Changed: return None instead of a Properties record
        # Why: POWER_CYCLE is an internal state transition, not a protocol record;
        # routing to _properties() caused Properties to be 30x overrepresented
        return None

    def _start_session(self, spid, hsa, hc, status, index) -> dict:
        args_req = {"HostSessionID": 1, "SPID": spid, "Write": 1}
        args_opt = {}
        if hsa:
            args_opt["HostSigningAuthority"] = hsa
        if hc:
            args_opt["HostChallenge"] = hc

        if status == "SUCCESS":
            ssid = self.vg.session_id()
            hsid = self.vg.host_session_id()
            output = {
                "method": {"args": {"optional": {}, "required": {"HostSessionID": hsid, "SPSessionID": ssid}}, "name": "SyncSession", "uid": METHOD_SYNCSESSION},
                "return_values": {"optional": {}, "required": {"HostSessionID": hsid, "SPSessionID": ssid}},
                "status_codes": "SUCCESS",
            }
        else:
            output = {
                "method": {"args": {"optional": {}, "required": {}}, "name": "SyncSession", "uid": METHOD_SYNCSESSION},
                "return_values": {"optional": {}, "required": {}},
                "status_codes": status,
            }
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": "Session Manager UID", "type": None, "uid": UID_SESSION_MGR},
                "method": {"args": {"optional": args_opt, "required": args_req}, "name": "StartSession", "uid": METHOD_STARTSESSION},
                "status_codes": "SUCCESS",
            },
            "output": output,
        }

    def _start_session_ro(self, spid, hsa, hc, status, index) -> dict:
        r = self._start_session(spid, hsa, hc, status, index)
        r["input"]["method"]["args"]["required"]["Write"] = 0
        return r

    def _end_session(self, status: str, index: int) -> dict:
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": None, "type": None, "uid": None},
                "method": {"args": {"optional": {}, "required": {}}, "name": "EndSession", "uid": None},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": {"optional": {}, "required": {}}, "status_codes": status},
        }

    def _auth(self, authority_uid, proof, status, index) -> dict:
        # Changed: generate proper Authenticate record instead of StartSession
        # Why: _auth() was calling _start_session(), making all Auth actions appear
        # as StartSession records → "consecutive StartSession" problem (4262 cases)
        args_optional = {"Authority": authority_uid}
        if proof:
            args_optional["Proof"] = proof
        if status == "SUCCESS":
            # Authenticate returns SUCCESS with result=True or False
            rv = [{"result": True}]
        else:
            rv = []
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": "Session Manager UID", "type": None, "uid": UID_SESSION_MGR},
                "method": {
                    "args": {"optional": args_optional, "required": {}},
                    "name": "Authenticate",
                    "uid": "0000000600000017",
                },
                "status_codes": "SUCCESS",
            },
            "output": {
                "return_values": rv,
                "status_codes": status,
            },
        }

    def _get(self, inv_name, inv_uid, cellblock, rv, status, index) -> dict:
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": inv_name, "type": None, "uid": inv_uid},
                "method": {"args": {"optional": {}, "required": {"Cellblock": cellblock}}, "name": "Get", "uid": METHOD_GET},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": rv if status == "SUCCESS" else [], "status_codes": status},
        }

    def _set(self, inv_name, inv_uid, values, status, index) -> dict:
        args_opt = {}
        if values is not None:
            args_opt["Values"] = values
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": inv_name, "type": None, "uid": inv_uid},
                "method": {"args": {"optional": args_opt, "required": {}}, "name": "Set", "uid": METHOD_SET},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": [], "status_codes": status},
        }

    def _genkey(self, inv_name, inv_uid, status, index) -> dict:
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": inv_name, "type": None, "uid": inv_uid},
                "method": {"args": {"optional": {}, "required": {}}, "name": "GenKey", "uid": METHOD_GENKEY},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": [], "status_codes": status},
        }

    def _activate(self, inv_name, inv_uid, status, index) -> dict:
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": inv_name, "type": None, "uid": inv_uid},
                "method": {"args": {"optional": {}, "required": {}}, "name": "Activate", "uid": METHOD_ACTIVATE},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": [], "status_codes": status},
        }

    # Changed: add _read_data and _write_data methods for READ_DATA/WRITE_DATA actions
    # Why: these are byte-table read/write operations on locking ranges (data I/O)

    def _read_data(self, inv_name, inv_uid, status, index) -> dict:
        """Read method on locking range - returns data bytes."""
        data_len = self.rng.randint(1, 512)
        data_hex = self.rng.randbytes(data_len).hex()
        if status == "SUCCESS":
            rv = [data_hex]
        else:
            rv = []
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": inv_name, "type": None, "uid": inv_uid},
                "method": {"args": {"optional": {}, "required": {"StartByte": 0, "Length": data_len}}, "name": "Read", "uid": METHOD_READ},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": rv, "status_codes": status},
        }

    def _write_data(self, inv_name, inv_uid, status, index) -> dict:
        """Write method on locking range - writes data bytes."""
        data_len = self.rng.randint(1, 512)
        data_hex = self.rng.randbytes(data_len).hex()
        return {
            "index": index,
            "input": {
                "invoking_id": {"name": inv_name, "type": None, "uid": inv_uid},
                "method": {"args": {"optional": {}, "required": {"StartByte": 0, "Length": data_len, "Data": data_hex}}, "name": "Write", "uid": METHOD_WRITE},
                "status_codes": "SUCCESS",
            },
            "output": {"return_values": [], "status_codes": status},
        }

    def _fallback(self, action_name, status, index) -> dict:
        return self._properties(status, index)
