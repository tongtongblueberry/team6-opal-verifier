#!/usr/bin/env python3
"""OPAL State Machine Simulator + Counterfactual Mutation Generator.

Generates structurally valid OPAL trajectories with deterministic pass/fail labels.
Based on public20 Phase Progression analysis (Agent 2) and EFSM literature (Agent 1).

Architecture:
  1. OpalState: tracks session/auth/credential/SP/locking state
  2. Phase generators: P0-P6 build valid trajectories incrementally
  3. Mutation engine: creates fail variants by minimal counterfactual edits
  4. Value randomizer: diversifies UIDs, PINs, session IDs
  5. Exporter: outputs in public20 schema format
"""

import json
import copy
import random
import hashlib
import argparse
import os
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

# ========================================================================
# Constants — UIDs, methods, SPIDs from public20 analysis
# ========================================================================

SESSION_MANAGER_UID = "00 00 00 00 00 00 00 FF"
PROPERTIES_METHOD_UID = "00 00 00 00 00 00 FF 01"
STARTSESSION_METHOD_UID = "00 00 00 00 00 00 FF 02"
SYNCSESSION_METHOD_UID = "00 00 00 00 00 00 FF 03"
GET_METHOD_UID = "00 00 00 06 00 00 00 16"
SET_METHOD_UID = "00 00 00 06 00 00 00 17"
ACTIVATE_METHOD_UID = "00 00 00 06 00 00 02 03"
GENKEY_METHOD_UID = "00 00 00 06 00 00 00 10"

ADMIN_SP = "0000020500000001"
LOCKING_SP = "0000020500000002"

CPIN_MSID_UID = "00 00 00 0B 00 00 84 02"
CPIN_SID_UID = "00 00 00 0B 00 00 00 01"
CPIN_ADMIN1_UID = "00 00 00 0B 00 03 00 01"
SP_LOCKING_UID = "00 00 02 05 00 00 00 02"
SP_ADMIN_UID = "00 00 01 05 00 00 00 04"
AUTHORITY_USER1_UID = "00 00 00 09 00 03 00 01"
LOCKING_GLOBAL_UID = "00 00 08 02 00 00 00 01"
LOCKING_RANGE1_UID = "00 00 08 02 00 03 00 01"
LOCKINGINFO_UID = "00 00 08 01 00 00 00 01"
MBRCONTROL_UID = "00 00 08 03 00 00 00 01"
K_AES_256_UID = "00 00 08 06 00 03 00 01"

HSA_SID = "0000000900000006"
HSA_ADMIN1 = "0000000900010001"
HSA_USER1 = "0000000900030001"


# ========================================================================
# Value generators
# ========================================================================

class ValueGen:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self._hsid_counter = 0

    def hex_str(self, length=64):
        return "".join(self.rng.choices("0123456789abcdef", k=length))

    def pin_b32(self, length=32):
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        return "".join(self.rng.choices(chars, k=length))

    def host_session_id(self):
        self._hsid_counter += 1
        return self._hsid_counter

    def sp_session_id(self):
        return self.hex_str(8)

    def fake_challenge(self):
        return self.rng.choice(["a" * 33, "0" * 33, "b" * 33, "1" * 33])


# ========================================================================
# Record builders — produce public20-compatible JSON records
# ========================================================================

def _record(index, invoking_name, invoking_uid, method_name, method_uid,
            args, status_in, output, status_out):
    """Build a single record in public20 format."""
    rec = {
        "index": index,
        "input": {
            "invoking_id": {"name": invoking_name, "type": None, "uid": invoking_uid},
            "method": {"name": method_name, "uid": method_uid, "args": args},
            "status_codes": status_in,
        },
        "output": {"return_values": output, "status_codes": status_out},
    }
    return rec


def _start_session(index, spid, write, hsid, spsid, hc=None, hsa=None):
    """Build a StartSession record."""
    req = {"HostSessionID": hsid, "SPID": spid, "Write": write}
    opt = {}
    if hc is not None:
        opt["HostChallenge"] = hc
    if hsa is not None:
        opt["HostSigningAuthority"] = hsa
    args = {"required": req, "optional": opt}

    out_req = {"HostSessionID": f"{hsid:08x}", "SPSessionID": spsid}
    output = {"optional": {}, "required": out_req}

    rec = _record(index, "Session Manager UID", SESSION_MANAGER_UID,
                  "StartSession", STARTSESSION_METHOD_UID, args, "SUCCESS", output, "SUCCESS")
    # Add SyncSession method in output
    rec["output"]["method"] = {
        "name": "SyncSession", "uid": SYNCSESSION_METHOD_UID,
        "args": {"required": out_req, "optional": {}},
    }
    return rec


def _end_session(index):
    """Build an EndSession record."""
    return {
        "index": index,
        "input": {
            "invoking_id": {"name": None, "type": None, "uid": None},
            "method": {"name": "EndSession", "uid": None,
                       "args": {"required": {}, "optional": {}}},
            "status_codes": "SUCCESS",
        },
        "output": {
            "return_values": {"optional": {}, "required": {}},
            "status_codes": "SUCCESS",
        },
    }


def _get(index, obj_name, obj_uid, cellblock, return_values):
    """Build a Get record."""
    args = {"required": {"Cellblock": cellblock}, "optional": {}}
    return _record(index, obj_name, obj_uid, "Get", GET_METHOD_UID,
                   args, "SUCCESS", return_values, "SUCCESS")


def _set(index, obj_name, obj_uid, values):
    """Build a Set record."""
    args = {"required": {}, "optional": {"Values": values}}
    return _record(index, obj_name, obj_uid, "Set", SET_METHOD_UID,
                   args, "SUCCESS", [], "SUCCESS")


def _activate(index, sp_uid):
    """Build an Activate record."""
    args = {"required": {}, "optional": {}}
    return _record(index, "SP", sp_uid, "Activate", ACTIVATE_METHOD_UID,
                   args, "SUCCESS", [], "SUCCESS")


def _genkey(index, key_uid):
    """Build a GenKey record."""
    args = {"required": {}, "optional": {}}
    return _record(index, "K_AES_256", key_uid, "GenKey", GENKEY_METHOD_UID,
                   args, "SUCCESS", [], "SUCCESS")


def _properties(index, vg: ValueGen):
    """Build a Properties record."""
    host_props = {
        "MaxComPacketSize": vg.hex_str(4),
        "MaxIndTokenSize": vg.hex_str(4),
        "MaxMethods": 1,
        "MaxPacketSize": vg.hex_str(4),
        "MaxPackets": 1,
        "MaxSubpackets": 1,
    }
    drive_props = {
        "DefSessionTimeout": 0,
        "MaxAuthentications": vg.rng.randint(2, 8),
        "MaxComPacketSize": vg.hex_str(6),
        "MaxIndTokenSize": vg.hex_str(6),
        "MaxMethods": 1,
        "MaxPacketSize": vg.hex_str(6),
        "MaxPackets": 1,
        "MaxSessions": vg.rng.randint(1, 4),
        "MaxSubpackets": 1,
        "MaxTransactionLimit": 1,
    }
    return {
        "index": index,
        "input": {
            "invoking_id": {"name": "Session Manager UID", "type": None, "uid": SESSION_MANAGER_UID},
            "method": {"args": [{"HostProperties": host_props}],
                       "name": "Properties", "uid": PROPERTIES_METHOD_UID},
            "status_codes": "SUCCESS",
        },
        "output": {
            "return_values": [{"Properties": drive_props}, {"HostProperties": host_props}],
            "status_codes": "SUCCESS",
        },
    }


def _read_command(index, lba, result):
    """Build a Read I/O command record (non-method format)."""
    return {
        "index": index,
        "input": {"args": {"LBA": lba}, "command": "Read"},
        "output": {"args": {"result": result}, "command": "Read"},
    }


def _write_command(index, lba, pattern):
    """Build a Write I/O command record."""
    return {
        "index": index,
        "input": {"args": {"LBA": lba, "pattern": pattern}, "command": "Write"},
        "output": {"args": {"result": "OK"}, "command": "Write"},
    }


# ========================================================================
# Phase generators — build valid trajectories incrementally
# ========================================================================

def phase_p0(vg: ValueGen) -> List[Dict]:
    """P0: Properties exchange (1 record)."""
    return [_properties(1, vg)]


def phase_p1(vg: ValueGen) -> List[Dict]:
    """P1: Admin SP no-auth → Read MSID (2 records)."""
    recs = []
    hsid = vg.host_session_id()
    spsid = vg.sp_session_id()
    recs.append(_start_session(1, ADMIN_SP, 1, hsid, spsid))
    msid = vg.pin_b32()
    recs.append(_get(2, "C_PIN", CPIN_MSID_UID,
                     [{"startColumn": 3}, {"endColumn": 3}],
                     [[{"3": msid}]]))
    return recs


def phase_p2(vg: ValueGen) -> List[Dict]:
    """P2: Read MSID + SID auth + Set SID password (7 records)."""
    recs = []
    idx = 1
    # S1: Read MSID
    hsid1 = vg.host_session_id()
    spsid1 = vg.sp_session_id()
    recs.append(_start_session(idx, ADMIN_SP, 1, hsid1, spsid1)); idx += 1
    msid = vg.pin_b32()
    recs.append(_get(idx, "C_PIN", CPIN_MSID_UID,
                     [{"startColumn": 3}, {"endColumn": 3}],
                     [[{"3": msid}]])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S2: SID auth + Set new password
    new_pwd = vg.hex_str(64)
    hsid2 = vg.host_session_id()
    spsid2 = vg.sp_session_id()
    recs.append(_start_session(idx, ADMIN_SP, 1, hsid2, spsid2,
                               hc=msid, hsa=HSA_SID)); idx += 1
    recs.append(_set(idx, "C_PIN", CPIN_SID_UID, [{"3": new_pwd}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S3: SID auth with new password
    hsid3 = vg.host_session_id()
    spsid3 = vg.sp_session_id()
    recs.append(_start_session(idx, ADMIN_SP, 1, hsid3, spsid3,
                               hc=new_pwd, hsa=HSA_SID)); idx += 1
    return recs, new_pwd


def phase_p3(vg: ValueGen) -> List[Dict]:
    """P3: Full setup through Activate Locking SP (11 records)."""
    recs_p2, pwd = phase_p2(vg)
    recs = recs_p2[:-1]  # Remove last StartSession, we'll add Get+Activate+ES+SS
    idx = len(recs) + 1
    # S3: Get SP lifecycle + Activate
    hsid3 = vg.host_session_id()
    spsid3 = vg.sp_session_id()
    recs.append(_start_session(idx, ADMIN_SP, 1, hsid3, spsid3,
                               hc=pwd, hsa=HSA_SID)); idx += 1
    recs.append(_get(idx, "SP", SP_LOCKING_UID,
                     [{"startColumn": 6}, {"endColumn": 6}],
                     [[{"6": 8}]])); idx += 1
    recs.append(_activate(idx, SP_LOCKING_UID)); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S4: Locking SP, Admin1 auth
    hsid4 = vg.host_session_id()
    spsid4 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid4, spsid4,
                               hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    return recs, pwd


def phase_p4(vg: ValueGen) -> List[Dict]:
    """P4: Setup + read initial locking state (21 records)."""
    recs_p3, pwd = phase_p3(vg)
    recs = recs_p3
    idx = len(recs) + 1
    # Read LockingInfo
    recs.append(_get(idx, "LockingInfo", LOCKINGINFO_UID,
                     [{"startColumn": 0}, {"endColumn": 9}],
                     [[{"0": 128}]])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S5: MBRControl read
    hsid5 = vg.host_session_id()
    spsid5 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid5, spsid5,
                               hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_get(idx + 0, "MBRControl", MBRCONTROL_UID,
                     [{"startColumn": 1}, {"endColumn": 2}],
                     [[{"1": 0}, {"2": 0}]])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S6: Locking range read
    hsid6 = vg.host_session_id()
    spsid6 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid6, spsid6,
                               hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    zeros = "0000000000000000"
    recs.append(_get(idx, "Locking", LOCKING_GLOBAL_UID,
                     [{"startColumn": 3}, {"endColumn": 8}],
                     [[{"3": zeros}, {"4": zeros}, {"5": 0}, {"6": 0}, {"7": 0}, {"8": 0}]])); idx += 1
    return recs, pwd


def phase_p5(vg: ValueGen) -> List[Dict]:
    """P5: Setup + configure Authority, C_PIN, MBR (27 records)."""
    recs_p4, pwd = phase_p4(vg)
    recs = recs_p4
    idx = len(recs) + 1
    # S7: Authority.Set (enable User1)
    recs.append(_end_session(idx)); idx += 1
    hsid7 = vg.host_session_id()
    spsid7 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid7, spsid7,
                               hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "Authority", AUTHORITY_USER1_UID, [{"5": 1}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S8: MBRControl.Set (enable MBR)
    hsid8 = vg.host_session_id()
    spsid8 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid8, spsid8,
                               hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "MBRControl", MBRCONTROL_UID, [{"1": 1}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # S9: MBRControl.Get (verify)
    hsid9 = vg.host_session_id()
    spsid9 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid9, spsid9,
                               hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_get(idx, "MBRControl", MBRCONTROL_UID,
                     [{"startColumn": 1}, {"endColumn": 2}],
                     [[{"1": 1}, {"2": 0}]])); idx += 1
    return recs, pwd


# ========================================================================
# Mutation engine — counterfactual fail generation
# ========================================================================

def mutate_status_code(recs: List[Dict], error_status: str) -> List[Dict]:
    """Type A: Change last record's output status to error, clear return values."""
    mutated = copy.deepcopy(recs)
    last = mutated[-1]
    last["output"]["status_codes"] = error_status
    rv = last["output"].get("return_values")
    if isinstance(rv, list):
        last["output"]["return_values"] = []
    elif isinstance(rv, dict):
        if "required" in rv:
            rv["required"] = {}
    return mutated


def mutate_fake_challenge(recs: List[Dict], vg: ValueGen) -> Optional[List[Dict]]:
    """Type B: Replace HostChallenge in last StartSession with fake value."""
    mutated = copy.deepcopy(recs)
    last = mutated[-1]
    inp = last.get("input", {})
    if not isinstance(inp, dict) or "method" not in inp:
        return None
    if inp["method"]["name"] != "StartSession":
        return None
    args = inp["method"].get("args", {})
    if not isinstance(args, dict):
        return None
    opt = args.get("optional", {})
    if "HostChallenge" not in opt:
        return None
    opt["HostChallenge"] = vg.fake_challenge()
    return mutated


def mutate_truncation(recs: List[Dict], n_remove: int = 2) -> Optional[List[Dict]]:
    """Type C: Remove last N records (truncate trajectory)."""
    if len(recs) <= n_remove + 1:
        return None
    mutated = copy.deepcopy(recs[:-n_remove])
    for i, rec in enumerate(mutated):
        rec["index"] = i + 1
    return mutated


def mutate_wrong_uid(recs: List[Dict]) -> Optional[List[Dict]]:
    """Type C: Change invoking_id UID in last method record to wrong value."""
    mutated = copy.deepcopy(recs)
    last = mutated[-1]
    inp = last.get("input", {})
    if not isinstance(inp, dict) or "invoking_id" not in inp:
        return None
    iid = inp.get("invoking_id", {})
    if not isinstance(iid, dict) or not iid.get("uid"):
        return None
    # Swap to a wrong UID
    iid["uid"] = SP_ADMIN_UID  # Wrong SP
    return mutated


# ========================================================================
# Trajectory generator — combines phases + mutations
# ========================================================================

def phase_p4_authority_final(vg: ValueGen) -> Tuple[List[Dict], str]:
    """P4 variant: ends with Authority.Set (like tc6/tc16)."""
    recs_p3, pwd = phase_p3(vg)
    recs = recs_p3
    idx = len(recs) + 1
    # Read LockingInfo + MBRControl + Locking (like P4)
    recs.append(_get(idx, "LockingInfo", LOCKINGINFO_UID,
                     [{"startColumn": 0}, {"endColumn": 9}], [[{"0": 128}]])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    hsid = vg.host_session_id(); spsid = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid, spsid, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_get(idx, "MBRControl", MBRCONTROL_UID,
                     [{"startColumn": 1}, {"endColumn": 2}], [[{"1": 0}, {"2": 0}]])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    hsid2 = vg.host_session_id(); spsid2 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid2, spsid2, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    zeros = "0000000000000000"
    recs.append(_get(idx, "Locking", LOCKING_GLOBAL_UID,
                     [{"startColumn": 3}, {"endColumn": 8}],
                     [[{"3": zeros}, {"4": zeros}, {"5": 0}, {"6": 0}, {"7": 0}, {"8": 0}]])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # Final: Authority.Set
    hsid3 = vg.host_session_id(); spsid3 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid3, spsid3, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "Authority", AUTHORITY_USER1_UID, [{"5": 1}])); idx += 1
    return recs, pwd


def phase_p5_user_auth(vg: ValueGen) -> Tuple[List[Dict], str]:
    """P5 variant: ends with User1 auth StartSession (like tc7/tc17, 26 records)."""
    recs_p4a, pwd = phase_p4_authority_final(vg)
    recs = recs_p4a
    idx = len(recs) + 1
    recs.append(_end_session(idx)); idx += 1
    # Set User1 password
    user_pwd = vg.hex_str(64)
    hsid = vg.host_session_id(); spsid = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid, spsid, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "C_PIN", CPIN_ADMIN1_UID, [{"3": user_pwd}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # Final: User1 auth
    hsid2 = vg.host_session_id(); spsid2 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid2, spsid2, hc=user_pwd, hsa=HSA_USER1)); idx += 1
    return recs, user_pwd


def phase_p6_genkey(vg: ValueGen) -> Tuple[List[Dict], str]:
    """P6: Full setup + Locking.Set + GenKey (like tc10, ~35 records)."""
    recs_p5, pwd = phase_p5(vg)
    recs = recs_p5
    idx = len(recs) + 1
    recs.append(_end_session(idx)); idx += 1
    # Locking.Set — configure range
    hsid = vg.host_session_id(); spsid = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid, spsid, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "Locking", LOCKING_RANGE1_UID,
                     [{"3": "0000000000000000"}, {"4": "00000000000003ff"}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # GenKey
    hsid2 = vg.host_session_id(); spsid2 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid2, spsid2, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_genkey(idx, K_AES_256_UID)); idx += 1
    return recs, pwd


def phase_p6_io(vg: ValueGen) -> Tuple[List[Dict], str]:
    """P6 variant: Full setup + GenKey + Write + Read (like tc10, ~39 records)."""
    recs_p6g, pwd = phase_p6_genkey(vg)
    recs = recs_p6g
    idx = len(recs) + 1
    # Enable locking
    recs.append(_end_session(idx)); idx += 1
    hsid = vg.host_session_id(); spsid = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid, spsid, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "Locking", LOCKING_RANGE1_UID, [{"5": 1}, {"6": 1}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # Unlock for I/O
    hsid2 = vg.host_session_id(); spsid2 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid2, spsid2, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_set(idx, "Locking", LOCKING_RANGE1_UID, [{"7": 0}, {"8": 0}])); idx += 1
    recs.append(_end_session(idx)); idx += 1
    # Write + Read
    recs.append(_write_command(idx, "80 ~ 87", "8E")); idx += 1
    recs.append(_read_command(idx, "80 ~ 87", "Pattern 8E")); idx += 1
    # Re-key + Read (should be random)
    hsid3 = vg.host_session_id(); spsid3 = vg.sp_session_id()
    recs.append(_start_session(idx, LOCKING_SP, 1, hsid3, spsid3, hc=pwd, hsa=HSA_ADMIN1)); idx += 1
    recs.append(_genkey(idx, K_AES_256_UID)); idx += 1
    recs.append(_end_session(idx)); idx += 1
    recs.append(_read_command(idx, "80 ~ 87", "Random Data")); idx += 1
    return recs, pwd


def mutate_read_plaintext(recs: List[Dict]) -> Optional[List[Dict]]:
    """Type B: Read returns plaintext after GenKey (like tc20)."""
    mutated = copy.deepcopy(recs)
    last = mutated[-1]
    inp = last.get("input", {})
    if isinstance(inp, dict) and inp.get("command") == "Read":
        last["output"]["args"]["result"] = "8E"
        return mutated
    return None


def generate_all(vg: ValueGen, variants_per_phase: int = 5) -> List[Tuple[List[Dict], str, str]]:
    """Generate pass/fail trajectory pairs for all phases.

    Changed: added P4_authority, P5_user_auth, P6_genkey, P6_io phases for
    diversity, GenKey coverage, Authority.Set final, and longer trajectories.
    Also added SP_BUSY, SP_FROZEN, NO_SESSIONS_AVAILABLE error statuses.
    """
    results = []

    for var_idx in range(variants_per_phase):
        # --- P0: Properties (1 record) ---
        recs_p0 = phase_p0(vg)
        results.append((recs_p0, "pass", f"P0_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p0, "INVALID_PARAMETER"), "fail", f"P0_invparam_v{var_idx}"))

        # --- P1: Read MSID (2 records) ---
        recs_p1 = phase_p1(vg)
        results.append((recs_p1, "pass", f"P1_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p1, "NOT_AUTHORIZED"), "fail", f"P1_notauth_v{var_idx}"))

        # --- P2: SID auth (7 records) ---
        recs_p2, _ = phase_p2(vg)
        results.append((recs_p2, "pass", f"P2_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p2, "NOT_AUTHORIZED"), "fail", f"P2_notauth_v{var_idx}"))
        results.append((mutate_status_code(recs_p2, "SP_BUSY"), "fail", f"P2_spbusy_v{var_idx}"))
        mutb = mutate_fake_challenge(recs_p2, vg)
        if mutb:
            results.append((mutb, "fail", f"P2_fakehc_v{var_idx}"))

        # --- P3: Activate (11 records) ---
        recs_p3, _ = phase_p3(vg)
        results.append((recs_p3, "pass", f"P3_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p3, "NOT_AUTHORIZED"), "fail", f"P3_notauth_v{var_idx}"))
        results.append((mutate_status_code(recs_p3, "SP_FROZEN"), "fail", f"P3_spfrozen_v{var_idx}"))
        mutc = mutate_wrong_uid(recs_p3)
        if mutc:
            results.append((mutc, "fail", f"P3_wronguid_v{var_idx}"))
        mutt = mutate_truncation(recs_p3)
        if mutt:
            results.append((mutt, "fail", f"P3_trunc_v{var_idx}"))

        # --- P4: Read locking state (18 records) ---
        recs_p4, _ = phase_p4(vg)
        results.append((recs_p4, "pass", f"P4_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p4, "INVALID_PARAMETER"), "fail", f"P4_invparam_v{var_idx}"))
        results.append((mutate_status_code(recs_p4, "FAIL"), "fail", f"P4_fail_v{var_idx}"))

        # --- P4a: Authority.Set final (21 records, like tc6/tc16) ---
        recs_p4a, _ = phase_p4_authority_final(vg)
        results.append((recs_p4a, "pass", f"P4a_authset_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p4a, "INVALID_PARAMETER"), "fail", f"P4a_invparam_v{var_idx}"))
        results.append((mutate_status_code(recs_p4a, "NOT_AUTHORIZED"), "fail", f"P4a_notauth_v{var_idx}"))

        # --- P5: MBR config + verify (27 records) ---
        recs_p5, _ = phase_p5(vg)
        results.append((recs_p5, "pass", f"P5_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p5, "FAIL"), "fail", f"P5_fail_v{var_idx}"))

        # --- P5a: User1 auth (26 records, like tc7/tc17) ---
        recs_p5a, _ = phase_p5_user_auth(vg)
        results.append((recs_p5a, "pass", f"P5a_userauth_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p5a, "NOT_AUTHORIZED"), "fail", f"P5a_notauth_v{var_idx}"))
        results.append((mutate_status_code(recs_p5a, "NO_SESSIONS_AVAILABLE"), "fail", f"P5a_nosess_v{var_idx}"))
        mutb2 = mutate_fake_challenge(recs_p5a, vg)
        if mutb2:
            results.append((mutb2, "fail", f"P5a_fakehc_v{var_idx}"))

        # --- P6: GenKey (33 records) ---
        recs_p6g, _ = phase_p6_genkey(vg)
        results.append((recs_p6g, "pass", f"P6g_genkey_pass_v{var_idx}"))
        results.append((mutate_status_code(recs_p6g, "NOT_AUTHORIZED"), "fail", f"P6g_notauth_v{var_idx}"))

        # --- P6io: Full I/O (39 records, like tc10/tc20) ---
        recs_p6io, _ = phase_p6_io(vg)
        results.append((recs_p6io, "pass", f"P6io_pass_v{var_idx}"))
        mut_plain = mutate_read_plaintext(recs_p6io)
        if mut_plain:
            results.append((mut_plain, "fail", f"P6io_plaintext_v{var_idx}"))

    # Balance pass:fail to ~50:50
    pass_results = [(r, l, d) for r, l, d in results if l == "pass"]
    fail_results = [(r, l, d) for r, l, d in results if l == "fail"]
    target = min(len(pass_results), len(fail_results))
    vg.rng.shuffle(fail_results)
    balanced = pass_results + fail_results[:target]
    vg.rng.shuffle(balanced)
    return balanced


# ========================================================================
# Export in public20 schema format
# ========================================================================

def export(results: List[Tuple[List[Dict], str, str]], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    inp_path = os.path.join(output_dir, "gen_input.jsonl")
    lbl_path = os.path.join(output_dir, "gen_labels.local.jsonl")
    rpt_path = os.path.join(output_dir, "generation_report.json")

    label_counts = Counter()
    rc_dist = Counter()

    with open(inp_path, "w") as fi, open(lbl_path, "w") as fl:
        for idx, (recs, label, desc) in enumerate(results):
            sid = f"sm{idx + 1:04d}"
            input_row = {
                "sample_id": sid,
                "source": "opal_state_machine_v1",
                "input": json.dumps({"records": recs}, ensure_ascii=False),
            }
            label_row = {
                "label": label,
                "sample_id": sid,
                "source": "opal_state_machine_v1.deterministic",
            }
            fi.write(json.dumps(input_row, ensure_ascii=False) + "\n")
            fl.write(json.dumps(label_row, ensure_ascii=False) + "\n")
            label_counts[label] += 1
            rc_dist[len(recs)] += 1

    report = {
        "total": len(results),
        "label_distribution": dict(label_counts),
        "record_count_distribution": dict(sorted(rc_dist.items())),
        "generator": "opal_state_machine_v1",
        "label_method": "deterministic_counterfactual",
    }
    with open(rpt_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


# ========================================================================
# Main
# ========================================================================

def main():
    ap = argparse.ArgumentParser(description="OPAL State Machine Trajectory Generator")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--variants", type=int, default=10,
                    help="Value variants per phase (default 10)")
    ap.add_argument("--output-dir", type=str,
                    default=str(Path(__file__).parent / "output"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    vg = ValueGen(rng)

    print(f"=== OPAL State Machine Generator ===")
    print(f"  seed={args.seed}  variants={args.variants}")

    results = generate_all(vg, variants_per_phase=args.variants)

    print(f"\n  Generated: {len(results)} trajectories")
    label_ct = Counter(l for _, l, _ in results)
    print(f"  Labels: {dict(label_ct)}")

    report = export(results, args.output_dir)
    print(f"  Record counts: {report['record_count_distribution']}")
    print(f"  Output: {args.output_dir}/")


if __name__ == "__main__":
    main()
