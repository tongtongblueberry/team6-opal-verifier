# Changed: add a compact OPAL FSM shadow for the rule-only submission package.
# Why: the algorithm package should ensemble the proven rulebase with expected
# status checks derived from the project FSM without importing non-submission
# modules from tools/datagen.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


Json = dict[str, Any]


# Changed: keep a small vendored transition table instead of importing tools/datagen.
# Why: submit archives contain src/, setup.sh, pyproject.toml, uv.lock only.
INITIAL_STATES: set[str] = {
    "POWERED_ON",
    "PROPS_QUERIED",
}


@dataclass(frozen=True)
class CandidateAction:
    action: str
    confidence: float


@dataclass(frozen=True)
class Transition:
    next_state: str
    expected_status: str
    semantic: str = ""


@dataclass(frozen=True)
class FsmDecision:
    verdict: str
    confidence: float
    reason: str
    actions: tuple[str, ...] = ()
    expected_statuses: tuple[str, ...] = ()


@dataclass
class FsmShadow:
    # Changed: track a set of possible FSM states instead of one state.
    # Why: raw JSON records do not identify a unique abstract action in all cases.
    states: set[str] = field(default_factory=lambda: set(INITIAL_STATES))
    unknown_count: int = 0
    last_actions: list[str] = field(default_factory=list)

    def advance(self, record: Json, protocol_state: Any = None) -> None:
        candidates = infer_actions(record, protocol_state)
        observed = status_name(record.get("output", {}))
        next_states: set[str] = set()
        accepted_actions: list[str] = []

        for state in self.states:
            for candidate in candidates:
                transition = DELTA.get((state, candidate.action))
                if transition is None:
                    continue
                if statuses_equal(transition.expected_status, observed):
                    next_states.add(transition.next_state)
                    accepted_actions.append(candidate.action)

        if next_states:
            self.states = next_states
            self.last_actions = accepted_actions[-8:]
            return

        # Changed: failed matching lowers confidence but does not erase states.
        # Why: the rulebase must remain authoritative when FSM abstraction is unsure.
        self.unknown_count += 1

    def check_final(self, record: Json, protocol_state: Any = None) -> FsmDecision:
        candidates = infer_actions(record, protocol_state)
        observed = status_name(record.get("output", {}))
        possible: list[tuple[CandidateAction, Transition]] = []

        for state in self.states:
            for candidate in candidates:
                transition = DELTA.get((state, candidate.action))
                if transition is not None:
                    possible.append((candidate, transition))

        if not possible:
            return FsmDecision("unknown", self.confidence(0.0), "no_fsm_transition")

        expected_statuses = tuple(sorted({normalize_status(t.expected_status) for _, t in possible}))
        actions = tuple(sorted({c.action for c, _ in possible}))
        max_candidate_conf = max(c.confidence for c, _ in possible)
        confidence = self.confidence(max_candidate_conf)
        matching = [(c, t) for c, t in possible if statuses_equal(t.expected_status, observed)]

        if matching:
            if any(read_after_genkey_stale(record, protocol_state, t.semantic) for _, t in matching):
                return FsmDecision(
                    "inconsistent",
                    confidence,
                    "fsm_read_after_genkey_stale_payload",
                    actions,
                    expected_statuses,
                )
            return FsmDecision("consistent", confidence, "fsm_expected_status_match", actions, expected_statuses)

        high_conf = [item for item in possible if item[0].confidence >= 0.85]
        if high_conf and confidence >= 0.70:
            high_expected = tuple(sorted({normalize_status(t.expected_status) for _, t in high_conf}))
            return FsmDecision(
                "inconsistent",
                confidence,
                f"fsm_expected_status_mismatch:{normalize_status(observed)}",
                tuple(sorted({c.action for c, _ in high_conf})),
                high_expected,
            )

        return FsmDecision("unknown", confidence, "low_confidence_status_mismatch", actions, expected_statuses)

    def confidence(self, candidate_confidence: float) -> float:
        penalty = 0.65 ** min(self.unknown_count, 6)
        return candidate_confidence * penalty


def _status_literal(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())
    aliases = {
        "notauthorized": "notauthorized",
        "notauthorised": "notauthorized",
        "invalidparameter": "invalidparameter",
        "successdata": "success",
        "nosessionsavailable": "nosessionsavailable",
        "spbusy": "spbusy",
    }
    return aliases.get(text, text)


def _t(state: str, action: str, next_state: str, status: str, semantic: str = "") -> None:
    DELTA[(state, action)] = Transition(next_state, _status_literal(status), semantic)


DELTA: dict[tuple[str, str], Transition] = {}

# Changed: vendored subset of tools/datagen/opal_fsm.py transitions used by the
# public20-like OPAL phase spine and common hidden-rule status checks.
# Why: this gives high-confidence expected-status evidence without replacing the
# existing procedural verifier.
_t("POWERED_ON", "PROPERTIES", "PROPS_QUERIED", "SUCCESS")
_t("PROPS_QUERIED", "PROPERTIES", "PROPS_QUERIED", "SUCCESS")
_t("PROPS_QUERIED", "START_RW_ADMIN_NOBODY", "ADMIN_RW_NOBODY", "SUCCESS")
_t("PROPS_QUERIED", "START_RW_ADMIN_SID", "ADMIN_RW_SID", "SUCCESS")
_t("PROPS_QUERIED", "START_RW_ADMIN_SID_WRONG_PW", "PROPS_QUERIED", "NOT_AUTHORIZED")
_t("PROPS_QUERIED", "START_RO_ADMIN_NOBODY", "ADMIN_RO_NOBODY", "SUCCESS")
_t("PROPS_QUERIED", "START_RO_ADMIN_SID", "ADMIN_RO_SID", "SUCCESS")
_t("PROPS_QUERIED", "START_SESSION_INACTIVE_SP", "LOCKING_INACTIVE", "INVALID_PARAMETER")
_t("PROPS_QUERIED", "START_RW_LOCKING_NOBODY", "LOCKING_INACTIVE", "INVALID_PARAMETER")

_t("ADMIN_RW_NOBODY", "GET_MSID_PIN", "ADMIN_RW_SID_MSID_READ", "SUCCESS")
_t("ADMIN_RW_NOBODY", "GET_CPIN_SID", "ADMIN_RW_NOBODY", "SUCCESS")
_t("ADMIN_RW_NOBODY", "SET_SID_PIN", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("ADMIN_RW_NOBODY", "AUTH_SID_CORRECT", "ADMIN_RW_SID", "SUCCESS")
_t("ADMIN_RW_NOBODY", "AUTH_SID_WRONG", "AUTH_FAILED_RETRY", "SUCCESS")
_t("ADMIN_RW_NOBODY", "CLOSE_SESSION", "PROPS_QUERIED", "SUCCESS")
_t("ADMIN_RW_SID_MSID_READ", "CLOSE_SESSION", "PROPS_QUERIED", "SUCCESS")
_t("ADMIN_RW_SID_MSID_READ", "AUTH_SID_CORRECT", "ADMIN_RW_SID", "SUCCESS")
_t("ADMIN_RW_SID", "GET_MSID_PIN", "ADMIN_RW_SID_MSID_READ", "SUCCESS")
_t("ADMIN_RW_SID", "GET_CPIN_SID", "ADMIN_RW_SID", "SUCCESS")
_t("ADMIN_RW_SID", "SET_SID_PIN", "ADMIN_RW_SID", "SUCCESS")
_t("ADMIN_RW_SID", "SET_AUTHORITY_ENABLED", "ADMIN_RW_SID", "SUCCESS")
_t("ADMIN_RW_SID", "ACTIVATE_LOCKING_SP", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")
_t("ADMIN_RW_SID", "ACTIVATE_ISSUED_SP", "ERROR_RECOVERY", "FAIL")
_t("ADMIN_RW_SID", "CLOSE_SESSION", "PROPS_QUERIED", "SUCCESS")

_t("ADMIN_RO_NOBODY", "GET_MSID_PIN", "ADMIN_RO_NOBODY", "SUCCESS")
_t("ADMIN_RO_NOBODY", "AUTH_SID_CORRECT", "ADMIN_RO_SID", "SUCCESS")
_t("ADMIN_RO_NOBODY", "SET_IN_RO_SESSION", "ADMIN_RO_NOBODY", "NOT_AUTHORIZED")
_t("ADMIN_RO_NOBODY", "CLOSE_SESSION", "PROPS_QUERIED", "SUCCESS")
_t("ADMIN_RO_SID", "GET_CPIN_SID", "ADMIN_RO_SID", "SUCCESS")
_t("ADMIN_RO_SID", "SET_IN_RO_SESSION", "ADMIN_RO_SID", "NOT_AUTHORIZED")
_t("ADMIN_RO_SID", "ACTIVATE_IN_RO", "ADMIN_RO_SID", "FAIL")
_t("ADMIN_RO_SID", "CLOSE_SESSION", "PROPS_QUERIED", "SUCCESS")

_t("ADMIN_RW_SID_ACTIVATED", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")
_t("ADMIN_RW_SID_ACTIVATED", "ACTIVATE_ALREADY_ACTIVE", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")
_t("ADMIN_RW_SID_ACTIVATED", "START_RW_LOCKING_ADMIN1", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("ADMIN_RW_SID_ACTIVATED", "START_RW_LOCKING_ADMIN1_WRONG_PW", "ADMIN_RW_SID_ACTIVATED", "NOT_AUTHORIZED")
_t("ADMIN_RW_SID_ACTIVATED", "START_RW_LOCKING_NOBODY", "LOCKING_RW_NOBODY", "SUCCESS")
_t("ADMIN_RW_SID_ACTIVATED", "START_RO_LOCKING_NOBODY", "LOCKING_RO_NOBODY", "SUCCESS")
_t("ADMIN_RW_SID_ACTIVATED", "START_RO_LOCKING_ADMIN1", "LOCKING_RO_ADMIN1", "SUCCESS")

_t("LOCKING_RW_NOBODY", "GET_BYTE_TABLE_UNAUTH", "LOCKING_RW_NOBODY", "SUCCESS")
_t("LOCKING_RW_NOBODY", "SET_LOCKING_READLOCKED", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("LOCKING_RW_NOBODY", "GENKEY_NON_ADMIN", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("LOCKING_RW_NOBODY", "AUTH_ADMIN1_CORRECT", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("LOCKING_RW_NOBODY", "AUTH_ADMIN1_WRONG", "AUTH_FAILED_RETRY", "SUCCESS")
_t("LOCKING_RW_NOBODY", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_RW_ADMIN1", "GET_LOCKINGINFO", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "GET_LOCKING_RANGE", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "GET_AUTHORITY_TABLE", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "GET_COLUMN_ORDER_CHECK", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "GET_NONEXISTENT_OBJ", "ERROR_RECOVERY", "INVALID_PARAMETER")
_t("LOCKING_RW_ADMIN1", "GET_BAD_CELLBLOCK", "ERROR_RECOVERY", "INVALID_PARAMETER")
_t("LOCKING_RW_ADMIN1", "SET_USER_ENABLED", "LOCKING_RW_ADMIN1_USER_ENABLED", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "SET_AUTHORITY_ENABLED", "LOCKING_RW_ADMIN1_USER_ENABLED", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "SET_CPIN_ADMIN1", "LOCKING_RW_ADMIN1", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "SET_LOCKING_RANGE_RW", "LOCKING_RANGE_SET", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "SET_LOCKING_READLOCKED", "LOCKING_RANGE_LOCKED", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "SET_LOCKING_WRITELOCKED", "LOCKING_RANGE_LOCKED", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "SET_DUPLICATE_COLUMN", "ERROR_RECOVERY", "INVALID_PARAMETER")
_t("LOCKING_RW_ADMIN1", "SET_GLOBAL_RANGE_START", "ERROR_RECOVERY", "INVALID_PARAMETER")
_t("LOCKING_RW_ADMIN1", "GENKEY_ADMIN", "LOCKING_KEY_SET", "SUCCESS")
_t("LOCKING_RW_ADMIN1", "GENKEY_NON_ADMIN", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("LOCKING_RW_ADMIN1", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_RW_ADMIN1_USER_ENABLED", "SET_CPIN_ADMIN1", "LOCKING_RW_ADMIN1_USER_ENABLED", "SUCCESS")
_t("LOCKING_RW_ADMIN1_USER_ENABLED", "START_RW_LOCKING_USER1", "LOCKING_RW_USER1", "SUCCESS")
_t("LOCKING_RW_ADMIN1_USER_ENABLED", "AUTH_USER1_CORRECT", "LOCKING_RW_USER1", "SUCCESS")
_t("LOCKING_RW_ADMIN1_USER_ENABLED", "AUTH_USER1_WRONG", "AUTH_FAILED_RETRY", "SUCCESS")
_t("LOCKING_RW_ADMIN1_USER_ENABLED", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_RW_USER1", "GET_LOCKING_RANGE", "LOCKING_RW_USER1", "SUCCESS")
_t("LOCKING_RW_USER1", "SET_LOCKING_READLOCKED", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("LOCKING_RW_USER1", "GENKEY_NON_ADMIN", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("LOCKING_RW_USER1", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_RO_NOBODY", "GET_LOCKING_RANGE", "LOCKING_RO_NOBODY", "SUCCESS")
_t("LOCKING_RO_NOBODY", "SET_IN_RO_SESSION", "LOCKING_RO_NOBODY", "NOT_AUTHORIZED")
_t("LOCKING_RO_NOBODY", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")
_t("LOCKING_RO_ADMIN1", "GET_LOCKING_RANGE", "LOCKING_RO_ADMIN1", "SUCCESS")
_t("LOCKING_RO_ADMIN1", "SET_IN_RO_SESSION", "LOCKING_RO_ADMIN1", "NOT_AUTHORIZED")
_t("LOCKING_RO_ADMIN1", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_RANGE_SET", "SET_LOCKING_READLOCKED", "LOCKING_RANGE_LOCKED", "SUCCESS")
_t("LOCKING_RANGE_SET", "SET_LOCKING_WRITELOCKED", "LOCKING_RANGE_LOCKED", "SUCCESS")
_t("LOCKING_RANGE_SET", "SET_LOCKING_RANGE_RW", "ERROR_RECOVERY", "INVALID_PARAMETER")
_t("LOCKING_RANGE_SET", "GENKEY_ADMIN", "LOCKING_KEY_SET", "SUCCESS")
_t("LOCKING_RANGE_SET", "WRITE_DATA", "LOCKING_RANGE_SET", "SUCCESS")
_t("LOCKING_RANGE_SET", "READ_DATA", "LOCKING_RANGE_SET", "SUCCESS")
_t("LOCKING_RANGE_SET", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_RANGE_LOCKED", "READ_DATA", "ERROR_RECOVERY", "NOT_AUTHORIZED")
_t("LOCKING_RANGE_LOCKED", "GENKEY_ADMIN", "LOCKING_KEY_SET", "SUCCESS")
_t("LOCKING_RANGE_LOCKED", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")

_t("LOCKING_KEY_SET", "WRITE_DATA", "LOCKING_KEY_SET", "SUCCESS")
_t("LOCKING_KEY_SET", "READ_DATA", "LOCKING_KEY_SET", "SUCCESS", "read_random_after_genkey")
_t("LOCKING_KEY_SET", "GENKEY_ADMIN", "LOCKING_KEY_SET", "SUCCESS")
_t("LOCKING_KEY_SET", "SET_LOCKING_READLOCKED", "LOCKING_RANGE_LOCKED", "SUCCESS")
_t("LOCKING_KEY_SET", "CLOSE_SESSION", "ADMIN_RW_SID_ACTIVATED", "SUCCESS")


def infer_actions(record: Json, protocol_state: Any = None) -> list[CandidateAction]:
    # Changed: infer abstract action candidates from raw JSON fields.
    # Why: an exact record-to-action map is not available at evaluation time.
    command = record.get("input", {}) if isinstance(record, dict) else {}
    if not isinstance(command, dict):
        return []
    method = compact(method_name(command))
    invoking = compact(invoking_name(command))
    invoking_uid = compact(invoking_uid_text(command))
    status = status_name(record.get("output", {}) if isinstance(record, dict) else {})

    if method == "properties":
        return [CandidateAction("PROPERTIES", 1.0)]
    if method == "endsession":
        return [CandidateAction("CLOSE_SESSION", 1.0)]
    if method == "startsession":
        return start_session_candidates(command, protocol_state)
    if method == "authenticate":
        return authenticate_candidates(command, protocol_state)
    if method == "get":
        return get_candidates(command, invoking, invoking_uid)
    if method == "set":
        return set_candidates(command, invoking, invoking_uid, protocol_state)
    if method == "activate":
        return activate_candidates(invoking_uid, status)
    if method == "genkey":
        authenticated = bool(getattr(protocol_state, "authenticated", False))
        return [CandidateAction("GENKEY_ADMIN" if authenticated else "GENKEY_NON_ADMIN", 0.9)]
    if method == "read":
        return [CandidateAction("READ_DATA", 0.95)]
    if method == "write":
        return [CandidateAction("WRITE_DATA", 0.95)]
    return []


def start_session_candidates(command: Json, protocol_state: Any = None) -> list[CandidateAction]:
    spid = compact(field_text(command, "SPID"))
    write_value = find_first_key(command, {"write"})
    write = bool_truthy(write_value) if write_value is not None else True
    challenge = host_challenge(command)
    known = set(getattr(protocol_state, "known_secrets", set()) or set())
    hsa = compact(field_text(command, "HostSigningAuthority"))
    candidates: list[CandidateAction] = []

    admin_sp = spid.endswith("0001") or "admin" in spid
    locking_sp = spid.endswith("0002") or "locking" in spid
    if not admin_sp and not locking_sp:
        admin_sp = True

    if challenge and known and challenge not in known:
        if admin_sp:
            candidates.append(CandidateAction("START_RW_ADMIN_SID_WRONG_PW", 0.95))
        if locking_sp:
            candidates.append(CandidateAction("START_RW_LOCKING_ADMIN1_WRONG_PW", 0.90))
        return candidates

    if admin_sp:
        if challenge or "sid" in hsa or hsa.endswith("0006"):
            candidates.append(CandidateAction("START_RW_ADMIN_SID" if write else "START_RO_ADMIN_SID", 0.90))
        else:
            candidates.append(CandidateAction("START_RW_ADMIN_NOBODY" if write else "START_RO_ADMIN_NOBODY", 0.90))
    if locking_sp:
        if challenge or "admin1" in hsa or hsa.endswith("00010001"):
            candidates.append(CandidateAction("START_RW_LOCKING_ADMIN1" if write else "START_RO_LOCKING_ADMIN1", 0.86))
        else:
            candidates.append(CandidateAction("START_RW_LOCKING_NOBODY" if write else "START_RO_LOCKING_NOBODY", 0.84))
            candidates.append(CandidateAction("START_SESSION_INACTIVE_SP", 0.60))
    return candidates


def authenticate_candidates(command: Json, protocol_state: Any = None) -> list[CandidateAction]:
    text = compact(command)
    if "admin1" in text or "00010001" in text:
        return [CandidateAction("AUTH_ADMIN1_CORRECT", 0.75), CandidateAction("AUTH_ADMIN1_WRONG", 0.55)]
    if "user1" in text or "00030001" in text:
        return [CandidateAction("AUTH_USER1_CORRECT", 0.75), CandidateAction("AUTH_USER1_WRONG", 0.55)]
    return [CandidateAction("AUTH_SID_CORRECT", 0.75), CandidateAction("AUTH_SID_WRONG", 0.55)]


def get_candidates(command: Json, invoking: str, invoking_uid: str) -> list[CandidateAction]:
    if cellblock_invalid(command):
        return [CandidateAction("GET_BAD_CELLBLOCK", 0.92)]
    if "lockinginfo" in invoking or invoking_uid.startswith("00000801"):
        return [CandidateAction("GET_LOCKINGINFO", 0.95)]
    if "locking" in invoking or invoking_uid.startswith("00000802"):
        return [
            CandidateAction("GET_LOCKING_RANGE", 0.95),
            CandidateAction("GET_COLUMN_ORDER_CHECK", 0.70),
        ]
    if "authority" in invoking or invoking_uid.startswith("00000009"):
        return [CandidateAction("GET_AUTHORITY_TABLE", 0.92)]
    if "mbrcontrol" in invoking or invoking_uid.startswith("00000803"):
        return [CandidateAction("GET_BYTE_TABLE_UNAUTH", 0.90)]
    if "cpin" in invoking or invoking_uid.startswith("0000000b"):
        if "8402" in invoking_uid:
            return [CandidateAction("GET_MSID_PIN", 0.95)]
        return [CandidateAction("GET_CPIN_SID", 0.88), CandidateAction("GET_MSID_PIN", 0.55)]
    return [CandidateAction("GET_NONEXISTENT_OBJ", 0.70)]


def set_candidates(
    command: Json,
    invoking: str,
    invoking_uid: str,
    protocol_state: Any = None,
) -> list[CandidateAction]:
    if set_values_invalid(command):
        return [CandidateAction("SET_DUPLICATE_COLUMN", 0.95)]
    fields = set(column_values(command))
    in_ro = not bool(getattr(protocol_state, "session_write", True))
    if in_ro:
        return [CandidateAction("SET_IN_RO_SESSION", 0.95)]
    if "cpin" in invoking or invoking_uid.startswith("0000000b"):
        if "00010001" in invoking_uid or "00030001" in invoking_uid:
            return [CandidateAction("SET_CPIN_ADMIN1", 0.90)]
        return [CandidateAction("SET_SID_PIN", 0.90)]
    if "authority" in invoking or invoking_uid.startswith("00000009"):
        return [CandidateAction("SET_AUTHORITY_ENABLED", 0.88), CandidateAction("SET_USER_ENABLED", 0.80)]
    if "locking" in invoking or invoking_uid.startswith("00000802"):
        out: list[CandidateAction] = []
        if {"3", "4"} & fields:
            out.append(CandidateAction("SET_LOCKING_RANGE_RW", 0.90))
        if "7" in fields:
            out.append(CandidateAction("SET_LOCKING_READLOCKED", 0.86))
        if "8" in fields:
            out.append(CandidateAction("SET_LOCKING_WRITELOCKED", 0.86))
        if not out:
            out.append(CandidateAction("SET_LOCKING_RANGE_RW", 0.60))
        return out
    return [CandidateAction("SET_GLOBAL_RANGE_START", 0.55)]


def activate_candidates(invoking_uid: str, status: str) -> list[CandidateAction]:
    if invoking_uid.startswith("00000205"):
        return [
            CandidateAction("ACTIVATE_LOCKING_SP", 0.88),
            CandidateAction("ACTIVATE_ALREADY_ACTIVE", 0.70),
        ]
    return [CandidateAction("ACTIVATE_ISSUED_SP", 0.88)]


def read_after_genkey_stale(record: Json, protocol_state: Any, semantic: str) -> bool:
    if semantic != "read_random_after_genkey":
        return False
    if not bool(getattr(protocol_state, "generated_key_after_write", False)):
        return False
    command = record.get("input", {}) if isinstance(record, dict) else {}
    output = record.get("output", {}) if isinstance(record, dict) else {}
    address = address_of(command)
    expected = getattr(protocol_state, "written_payloads", {}).get(address)
    actual = payload_of(output)
    return bool(expected and actual and payloads_equivalent(actual, expected))


def normalize_status(value: Any) -> str:
    text = compact(value)
    aliases = {
        "notauthorized": "notauthorized",
        "notauthorised": "notauthorized",
        "invalidparameter": "invalidparameter",
        "successdata": "success",
        "nosessionsavailable": "nosessionsavailable",
        "spbusy": "spbusy",
    }
    return aliases.get(text, text)


def statuses_equal(left: Any, right: Any) -> bool:
    return normalize_status(left) == normalize_status(right)


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", norm(value).lower())


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def find_first_key(value: Any, key_names: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if compact(key) in key_names:
                return item
        for item in value.values():
            found = find_first_key(item, key_names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_first_key(item, key_names)
            if found is not None:
                return found
    return None


def method_name(command: Json) -> str:
    method = find_first_key(command, {"method", "methodname"})
    if isinstance(method, dict):
        name = find_first_key(method, {"name"})
        if name is not None:
            return norm(name)
    if isinstance(method, str):
        return norm(method)
    command_name = find_first_key(command, {"command"})
    return norm(command_name)


def status_name(output: Json) -> str:
    status = find_first_key(output, {"status", "statuscodes"})
    if isinstance(status, dict):
        name = find_first_key(status, {"name"})
        if name is not None:
            return normalize_status(name)
    if isinstance(status, str):
        return normalize_status(status)
    if find_first_key(output, {"command"}) is not None or find_first_key(output, {"result"}) is not None:
        return "success"
    return ""


def invoking_name(command: Json) -> str:
    invoking = find_first_key(command, {"invokinguid", "invokingid", "invoking"})
    if isinstance(invoking, dict):
        name = find_first_key(invoking, {"name"})
        if name is not None:
            return norm(name)
        uid = find_first_key(invoking, {"uid"})
        if uid is not None:
            return norm(uid)
    return norm(invoking)


def invoking_uid_text(command: Json) -> str:
    invoking = find_first_key(command, {"invokinguid", "invokingid", "invoking"})
    if isinstance(invoking, dict):
        uid = find_first_key(invoking, {"uid"})
        if uid is not None:
            return norm(uid)
    if isinstance(invoking, str):
        return norm(invoking)
    return ""


def field_text(value: Any, key_name: str) -> str:
    found = find_first_key(value, {compact(key_name)})
    return norm(found) if found is not None else ""


def host_challenge(command: Json) -> str:
    return field_text(command, "HostChallenge") or field_text(command, "Challenge")


def bool_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    return compact(value) in {"1", "t", "true"}


def column_values(value: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            ckey = compact(key)
            if ckey.isdigit():
                values[ckey] = item
            else:
                values.update(column_values(item))
    elif isinstance(value, list):
        for item in value:
            values.update(column_values(item))
    return values


def cellblock_invalid(command: Json) -> bool:
    for item in walk(command):
        if not isinstance(item, dict):
            continue
        if "startColumn" in item and "endColumn" in item:
            try:
                return int(item["endColumn"]) < int(item["startColumn"])
            except (TypeError, ValueError):
                return True
    return False


def set_values_invalid(command: Json) -> bool:
    values = find_first_key(command, {"values", "rowvalues"})
    if not isinstance(values, list):
        return False
    seen: set[str] = set()
    for row in values:
        if not isinstance(row, dict):
            continue
        for key in row:
            ckey = compact(key)
            if not ckey.isdigit():
                continue
            if ckey in seen:
                return True
            seen.add(ckey)
    return False


def payload_of(value: Any) -> str:
    for key in ("data", "payload", "bytes", "value", "pattern", "result"):
        found = find_first_key(value, {compact(key)})
        if isinstance(found, str) and found.strip():
            return norm(found)
    return ""


def address_of(value: Any) -> str:
    for key in ("lba", "startlba", "address", "offset"):
        found = find_first_key(value, {compact(key)})
        if found is not None:
            return norm(found)
    return "default"


def payloads_equivalent(actual: Any, expected: Any) -> bool:
    actual_text = compact(actual)
    expected_text = compact(expected)
    if not actual_text or not expected_text:
        return False
    return actual_text == expected_text or actual_text == f"pattern{expected_text}"
