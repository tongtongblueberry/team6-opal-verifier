# Changed: implement a deterministic SSD TCG/Opal trajectory verifier.
# Why: the task input contains the full command/response trajectory, so the core
# decision should track protocol state instead of training on the tiny public set.

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


Json = dict[str, Any]


# Changed: keep rule-to-spec search keys explicit for trace-mode evaluation.
# Why: intermediate checks need evidence candidates without putting an LLM in the submission path.
RULE_SPEC_QUERIES: dict[str, list[str]] = {
    "OBSERVE_ERROR": ["status code error response"],
    "STARTSESSION_EFFECT": ["StartSession HostSessionID SPSessionID HostChallenge"],
    "ENDSESSION_EFFECT": ["EndSession session close"],
    "SET_CPIN_SECRET": ["C_PIN Set PIN credential"],
    "ACTIVATE_SP_EFFECT": ["Activate SP"],
    "WRITE_PAYLOAD_EFFECT": ["Data Write LBA payload"],
    "GENKEY_EFFECT": ["GenKey media encryption key"],
    "PARSE_FINAL_COMMAND": ["method command status parsing"],
    "PROPERTIES_PAYLOAD": ["Properties MaxMethods MaxSessions MaxPacketSize"],
    "STARTSESSION_FINAL": ["StartSession HostChallenge HostSigningAuthority"],
    "PRECONDITION_EXPECTED_ERROR": ["method precondition NOT_AUTHORIZED INVALID_PARAMETER"],
    "UNEXPECTED_ERROR_STATUS": ["method status code SUCCESS FAIL NOT_AUTHORIZED"],
    "ACTIVATE_TARGET": ["Activate SP UID"],
    "READ_PAYLOAD": ["Read LBA result GenKey"],
    "DEFAULT_PASS": ["method response status compliance"],
}


# Changed: centralize string normalization for noisy JSON fields.
# Why: public and hidden cases can vary in capitalization, spacing, and nesting.
def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _lower(value: Any) -> str:
    return _norm(value).lower()


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _lower(value))


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _find_first_key(value: Any, key_names: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if _compact(key) in key_names:
                return item
        for item in value.values():
            found = _find_first_key(item, key_names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_key(item, key_names)
            if found is not None:
                return found
    return None


def _collect_strings(value: Any) -> list[str]:
    strings: list[str] = []
    for item in _walk(value):
        if isinstance(item, dict):
            strings.extend(_norm(key) for key in item.keys())
        if isinstance(item, str):
            strings.append(_norm(item))
    return strings


def _contains_text(value: Any, needle: str) -> bool:
    target = _compact(needle)
    return any(target in _compact(item) for item in _collect_strings(value))


def _status_name(output: Json) -> str:
    status = _find_first_key(output, {"status"})
    if isinstance(status, dict):
        name = _find_first_key(status, {"name"})
        if name is not None:
            return _compact(name)
    if isinstance(status, str):
        return _compact(status)
    for text in _collect_strings(output):
        compact = _compact(text)
        if compact in {"success", "fail", "notauthorized", "invalidparameter"}:
            return compact
    if _find_first_key(output, {"command"}) is not None or _find_first_key(output, {"result"}) is not None:
        return "success"
    return ""


def _method_name(command: Json) -> str:
    method = _find_first_key(command, {"method", "methodname"})
    if isinstance(method, dict):
        name = _find_first_key(method, {"name"})
        if name is not None:
            return _norm(name)
    if isinstance(method, str):
        return _norm(method)
    command_name = _find_first_key(command, {"command"})
    if isinstance(command_name, str):
        return _norm(command_name)
    for text in _collect_strings(command):
        compact = _compact(text)
        if compact in {
            "propertiess",
            "properties",
            "startsession",
            "endsession",
            "get",
            "set",
            "activate",
            "genkey",
            "read",
            "write",
        }:
            return _norm(text)
    return ""


def _is_data_command(command: Json) -> bool:
    # Changed: distinguish DATA_COMMAND Read/Write from TCG method calls.
    # Why: public traces perform media Read after EndSession, so session preconditions differ.
    command_name = _find_first_key(command, {"command"})
    return isinstance(command_name, str) and _compact(command_name) in {"read", "write"}


def _invoking_name(command: Json) -> str:
    invoking = _find_first_key(command, {"invokinguid", "invokingid", "invoking"})
    if isinstance(invoking, dict):
        name = _find_first_key(invoking, {"name"})
        if name is not None:
            return _norm(name)
        uid = _find_first_key(invoking, {"uid"})
        if uid is not None:
            return _norm(uid)
    if invoking is not None:
        return _norm(invoking)
    return ""


def _invoking_uid(command: Json) -> str:
    # Changed: expose the raw invoking UID for target-specific legality checks.
    # Why: name-only checks cannot distinguish valid Locking SP activation from wrong SP objects.
    invoking = _find_first_key(command, {"invokinguid", "invokingid", "invoking"})
    if isinstance(invoking, dict):
        uid = _find_first_key(invoking, {"uid"})
        if uid is not None:
            return _norm(uid)
    if isinstance(invoking, str):
        return _norm(invoking)
    return ""


def _session_id(value: Any) -> str:
    sid = _find_first_key(
        value,
        {
            "hsn",
            "tsn",
            "sessionid",
            "hostsessionid",
            "spsessionid",
            "hostsessionnumber",
            "tpersessionnumber",
        },
    )
    if sid is None:
        return ""
    return _norm(sid)


def _host_challenge(command: Json) -> str:
    challenge = _find_first_key(command, {"hostchallenge", "hostchallange", "challenge"})
    if challenge is None:
        return ""
    return _norm(challenge)


def _challenge_malformed(command: Json) -> bool:
    # Changed: validate HostChallenge as a challenge token, not as the stored PIN itself.
    # Why: StartSession authentication compares cryptographic proof material, not plaintext equality.
    challenge = _host_challenge(command)
    if not challenge:
        return False
    compact = re.sub(r"\s+", "", challenge)
    return re.fullmatch(r"[0-9a-fA-F]{64}", compact) is None


def _candidate_secret(command: Json) -> str:
    for key in ("pin", "newpin", "password", "credential", "hostchallenge", "challenge"):
        found = _find_first_key(command, {_compact(key)})
        if isinstance(found, str) and found.strip():
            return _norm(found)
    strings = [item for item in _collect_strings(command) if len(item) >= 4]
    for item in strings:
        compact = _compact(item)
        if compact not in {"cpin", "authority", "locking", "admin1", "sid", "anybody"}:
            return item
    return ""


@dataclass
class ProtocolState:
    # Changed: track only state needed for command legality and response validation.
    # Why: this is robust to tiny public labels and keeps hidden-data behavior spec-like.
    active_sessions: set[str] = field(default_factory=set)
    authenticated: bool = False
    activated_sps: set[str] = field(default_factory=set)
    known_secrets: set[str] = field(default_factory=set)
    written_payloads: dict[str, str] = field(default_factory=dict)
    generated_key_after_write: bool = False
    last_error: str = ""
    trace: list[Json] = field(default_factory=list)


class StatefulOpalVerifier:
    # Changed: make rule behavior explicit and conservative.
    # Why: PASS means final response is protocol-compliant, including compliant errors.
    success_status = "success"

    def __init__(self, trace: bool = False) -> None:
        # Changed: make tracing opt-in so official prediction stays lightweight.
        # Why: intermediate evaluation needs evidence, but leaderboard runtime should stay fast.
        self.trace = trace

    def verify(self, trajectory: Any) -> str:
        return self._run(trajectory)["prediction"]

    def verify_with_trace(self, trajectory: Any) -> Json:
        # Changed: expose compact rule/state evidence for intermediate evaluation only.
        # Why: this acts as a deterministic "receptive field" for rule debugging.
        original_trace = self.trace
        self.trace = True
        try:
            return self._run(trajectory)
        finally:
            self.trace = original_trace

    def _run(self, trajectory: Any) -> Json:
        records = self._records(trajectory)
        if not records:
            return {"prediction": "fail", "trace": [{"rule_id": "PARSE_FINAL_COMMAND"}]}

        state = ProtocolState()
        for step_index, record in enumerate(records[:-1]):
            self._advance_state(state, record, step_index)

        final_record = records[-1]
        inconsistent = self._final_is_inconsistent(state, final_record, len(records) - 1)
        return {"prediction": "fail" if inconsistent else "pass", "trace": state.trace}

    def _add_trace(
        self,
        state: ProtocolState,
        step: int,
        rule_id: str,
        reads: list[str] | None = None,
        writes: list[str] | None = None,
        detail: str = "",
    ) -> None:
        if not self.trace:
            return
        state.trace.append(
            {
                "step": step,
                "rule_id": rule_id,
                "state_reads": reads or [],
                "state_writes": writes or [],
                "spec_ref_candidates": RULE_SPEC_QUERIES.get(rule_id, []),
                "detail": detail,
            }
        )

    def _records(self, trajectory: Any) -> list[Json]:
        if isinstance(trajectory, (str, Path)):
            with Path(trajectory).open("r", encoding="utf-8") as handle:
                trajectory = json.load(handle)
        if isinstance(trajectory, dict) and "records" in trajectory:
            trajectory = trajectory["records"]
        if not isinstance(trajectory, list):
            return []
        return [item for item in trajectory if isinstance(item, dict)]

    def _input(self, record: Json) -> Json:
        item = record.get("input", {})
        return item if isinstance(item, dict) else {}

    def _output(self, record: Json) -> Json:
        item = record.get("output", {})
        return item if isinstance(item, dict) else {}

    def _advance_state(self, state: ProtocolState, record: Json, step_index: int = -1) -> None:
        command = self._input(record)
        output = self._output(record)
        method = _compact(_method_name(command))
        status = _status_name(output)
        invoking = _compact(_invoking_name(command))
        invoking_uid = _compact(_invoking_uid(command))

        if status != self.success_status:
            state.last_error = status
            self._add_trace(
                state,
                step_index,
                "OBSERVE_ERROR",
                writes=["last_error"],
                detail=f"{method}->{status}",
            )
            return

        if method == "startsession":
            sid = _session_id(output) or _session_id(command) or str(len(state.active_sessions) + 1)
            state.active_sessions.add(sid)
            state.authenticated = not _challenge_malformed(command)
            self._add_trace(
                state,
                step_index,
                "STARTSESSION_EFFECT",
                reads=["HostChallenge"],
                writes=["active_sessions", "authenticated"],
                detail=f"sid={sid}",
            )
            return

        if method == "endsession":
            sid = _session_id(command)
            if sid:
                state.active_sessions.discard(sid)
            else:
                state.active_sessions.clear()
            state.authenticated = bool(state.active_sessions) and state.authenticated
            self._add_trace(
                state,
                step_index,
                "ENDSESSION_EFFECT",
                reads=["active_sessions"],
                writes=["active_sessions", "authenticated"],
                detail=f"sid={sid or 'all'}",
            )
            return

        if method == "set":
            secret = _candidate_secret(command)
            if _contains_text(command, "C_PIN") and secret:
                state.known_secrets.add(secret)
                self._add_trace(
                    state,
                    step_index,
                    "SET_CPIN_SECRET",
                    reads=["C_PIN"],
                    writes=["known_secrets"],
                    detail="C_PIN updated",
                )
            return

        if method == "activate":
            if "sp" in invoking:
                state.activated_sps.add(invoking)
                self._add_trace(
                    state,
                    step_index,
                    "ACTIVATE_SP_EFFECT",
                    reads=["invoking_uid"],
                    writes=["activated_sps"],
                    detail=invoking_uid,
                )
            return

        if method == "write":
            payload = self._payload(command)
            address = self._address(command)
            if payload:
                state.written_payloads[address] = payload
            state.generated_key_after_write = False
            self._add_trace(
                state,
                step_index,
                "WRITE_PAYLOAD_EFFECT",
                reads=["LBA", "payload"],
                writes=["written_payloads", "generated_key_after_write"],
                detail=f"address={address}",
            )
            return

        if method == "genkey":
            state.generated_key_after_write = bool(state.written_payloads)
            self._add_trace(
                state,
                step_index,
                "GENKEY_EFFECT",
                reads=["written_payloads"],
                writes=["generated_key_after_write"],
                detail=f"after_write={state.generated_key_after_write}",
            )

    def _final_is_inconsistent(self, state: ProtocolState, record: Json, step_index: int = -1) -> bool:
        command = self._input(record)
        output = self._output(record)
        method = _compact(_method_name(command))
        status = _status_name(output)
        invoking = _compact(_invoking_name(command))
        invoking_uid = _compact(_invoking_uid(command))

        if not method or not status:
            self._add_trace(state, step_index, "PARSE_FINAL_COMMAND", detail="missing method/status")
            return True

        if method == "properties":
            inconsistent = status != self.success_status or not self._has_properties_payload(output)
            self._add_trace(
                state,
                step_index,
                "PROPERTIES_PAYLOAD",
                reads=["status", "return_values"],
                detail=f"inconsistent={inconsistent}",
            )
            return inconsistent

        if method == "startsession":
            inconsistent = self._start_session_inconsistent(state, command, output, status)
            self._add_trace(
                state,
                step_index,
                "STARTSESSION_FINAL",
                reads=["HostChallenge", "HostSessionID", "SPSessionID", "status"],
                detail=f"inconsistent={inconsistent}",
            )
            return inconsistent

        if method in {"get", "set", "activate", "genkey", "read", "write"}:
            expected_error = self._expected_error_for_state(
                state,
                command,
                method,
                invoking,
                invoking_uid,
            )
            if expected_error:
                self._add_trace(
                    state,
                    step_index,
                    "PRECONDITION_EXPECTED_ERROR",
                    reads=["active_sessions", "authenticated", "invoking_uid"],
                    detail=f"expected={expected_error}, actual={status}",
                )
                return status == self.success_status
            if status != self.success_status:
                self._add_trace(
                    state,
                    step_index,
                    "UNEXPECTED_ERROR_STATUS",
                    reads=["status"],
                    detail=status,
                )
                return True

        if method == "activate":
            inconsistent = self._activate_target_invalid(invoking, invoking_uid)
            self._add_trace(
                state,
                step_index,
                "ACTIVATE_TARGET",
                reads=["invoking_name", "invoking_uid"],
                detail=f"uid={invoking_uid}, inconsistent={inconsistent}",
            )
            return inconsistent

        if method == "read" and status == self.success_status:
            inconsistent = self._read_payload_inconsistent(state, command, output)
            self._add_trace(
                state,
                step_index,
                "READ_PAYLOAD",
                reads=["written_payloads", "generated_key_after_write", "result"],
                detail=f"inconsistent={inconsistent}",
            )
            return inconsistent

        self._add_trace(state, step_index, "DEFAULT_PASS", reads=["status"], detail=method)
        return False

    def _expected_error_for_state(
        self,
        state: ProtocolState,
        command: Json,
        method: str,
        invoking: str,
        invoking_uid: str,
    ) -> str:
        data_command = _is_data_command(command)
        if (
            method in {"get", "set", "activate", "genkey", "read", "write"}
            and not data_command
            and not state.active_sessions
        ):
            return "notauthorized"
        if method in {"set", "activate", "genkey", "write"} and not data_command and not state.authenticated:
            return "notauthorized"
        if method == "activate" and self._activate_target_invalid(invoking, invoking_uid):
            return "invalidparameter"
        return ""

    def _activate_target_invalid(self, invoking: str, invoking_uid: str) -> bool:
        # Changed: require Activate to target the Locking SP object shape seen in Opal flows.
        # Why: public counterexamples show SUCCESS on a different SP UID must be rejected.
        if "sp" not in invoking:
            return True
        return bool(invoking_uid) and not invoking_uid.startswith("00000205")

    def _start_session_inconsistent(
        self,
        state: ProtocolState,
        command: Json,
        output: Json,
        status: str,
    ) -> bool:
        if _challenge_malformed(command):
            return status == self.success_status
        if status != self.success_status:
            return True
        return not (_session_id(output) or _session_id(command))

    def _has_properties_payload(self, output: Json) -> bool:
        strings = [_compact(item) for item in _collect_strings(output)]
        property_markers = {
            "maxmethods",
            "maxsessions",
            "maxpacketcomsize",
            "maxindtokenpacketssize",
            "continuedtokens",
        }
        return any(any(marker in item for marker in property_markers) for item in strings)

    def _payload(self, value: Any) -> str:
        for key in ("data", "payload", "bytes", "value", "pattern", "result"):
            found = _find_first_key(value, {_compact(key)})
            if isinstance(found, str) and found.strip():
                return _norm(found)
        return ""

    def _address(self, value: Any) -> str:
        for key in ("lba", "startlba", "address", "offset"):
            found = _find_first_key(value, {_compact(key)})
            if found is not None:
                return _norm(found)
        return "default"

    def _read_payload_inconsistent(self, state: ProtocolState, command: Json, output: Json) -> bool:
        actual = self._payload(output)
        address = self._address(command)
        expected = state.written_payloads.get(address)
        if state.generated_key_after_write and actual:
            compact = _compact(actual)
            return len(compact) <= 2
        if expected:
            return bool(actual) and actual != expected
        return False


def predict(dataset: Any) -> list[str]:
    # Changed: keep a batch helper while avoiding any model loading.
    # Why: some local scripts call module-level predict, while the official evaluator uses Solver.
    verifier = StatefulOpalVerifier()
    if isinstance(dataset, dict):
        cases = dataset.get("testcases") or dataset.get("cases") or dataset.get("data") or []
    else:
        cases = dataset
    if isinstance(cases, dict):
        iterable = [cases[key] for key in sorted(cases)]
    elif isinstance(cases, list):
        iterable = cases
    else:
        iterable = []
    return [verifier.verify(case) for case in iterable]


def predict_one(testcase: Any) -> str:
    # Changed: add a small helper for local scripts and smoke tests.
    # Why: it keeps batch API behavior unchanged while making unit checks simple.
    return StatefulOpalVerifier().verify(testcase)


class Solver:
    # Changed: add the official course skeleton interface.
    # Why: /dl2026/skeleton/evaluate.py imports Solver and expects predict() to return id->label.
    def __init__(self) -> None:
        self.verifier = StatefulOpalVerifier()

    def predict(self, dataset: Any) -> dict[str, str]:
        if not isinstance(dataset, list):
            return {}

        predictions: dict[str, str] = {}
        for index, item in enumerate(dataset):
            if isinstance(item, dict):
                case_id = str(item.get("id", f"case_{index}"))
                steps = item.get("steps", item)
            else:
                case_id = f"case_{index}"
                steps = item
            predictions[case_id] = self.verifier.verify(steps)
        return predictions
