# fsm_cpin_lifecycle.py
# 변경: C_PIN/TryLimit(R37-R42), Authority Operation(R43-R45),
#       Opal Session(R46-R47), Lifecycle/Activate/Revert(R48-R56) 검증 FSM 생성
# 이유: trajectory 검증용 상태머신. 레코드를 순차 읽어 최종 verdict 판정.
"""검증용 FSM — C_PIN / Authority / Opal Session / Lifecycle 규칙 (R37-R56).

주어진 trajectory X = ((c₁,r₁),...,(cₙ,rₙ))를 레코드 단위로 읽어
상태를 갱신하고, 최종 레코드에서 응답 rₙ의 프로토콜 준수 여부를 판정한다.

사용법:
    from tools.datagen.fsm_cpin_lifecycle import (
        CPINLifecycleState,
        update_cpin_lifecycle,
        check_final_verdict_cpin_lifecycle,
    )
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# UID 상수 — space-separated 형식 (레코드의 invoking_id.uid 형식)
# ---------------------------------------------------------------------------
# 변경: space-separated UID와 no-space UID 모두 지원
# 이유: 레코드 내 invoking_id.uid는 space-separated, args 내 SPID/HostSigningAuthority는 no-space

# SP UID (space-separated)
_UID_SP_ADMIN_SPACED = "00 00 02 05 00 00 00 01"
_UID_SP_LOCKING_SPACED = "00 00 02 05 00 00 00 02"
# SP UID (no-space) — StartSession args에서 사용
_SPID_ADMIN = "0000020500000001"
_SPID_LOCKING = "0000020500000002"

# C_PIN UID (space-separated)
_UID_CPIN_SID_SPACED = "00 00 00 0B 00 00 00 01"
_UID_CPIN_MSID_SPACED = "00 00 00 0B 00 00 84 02"
_UID_CPIN_ADMIN1_SPACED = "00 00 00 0B 00 01 00 01"

# Authority UID (no-space) — HostSigningAuthority에서 사용
_AUTH_SID = "0000000900000006"
_AUTH_ADMIN1 = "0000000900010001"
_AUTH_ADMIN1_LOCKING = "0000000900010001"
_AUTH_USER1 = "0000000900030001"
_AUTH_ANYBODY = "0000000900000001"
# Authority class UID
_AUTH_ADMINS_CLASS = "0000000900000005"
_AUTH_USERS_CLASS = "0000000900000004"

# Session Manager
_UID_SESSION_MGR_SPACED = "00 00 00 00 00 00 00 FF"

# C_PIN 테이블 UID 패턴 (prefix)
_CPIN_TABLE_PREFIX_SPACED = "00 00 00 0B"
_CPIN_TABLE_PREFIX = "0000000B"

# SP 테이블 UID 패턴 (prefix)
_SP_TABLE_PREFIX_SPACED = "00 00 02 05"
_SP_TABLE_PREFIX = "00000205"

# 알려진 SP UID 목록 (Opal에서 유효한 SP)
_KNOWN_SP_UIDS_SPACED = {
    _UID_SP_ADMIN_SPACED,
    _UID_SP_LOCKING_SPACED,
}

# Lifecycle 상수 값 (column 6 값)
_LIFECYCLE_MANUFACTURED_INACTIVE = 8  # Manufactured-Inactive
_LIFECYCLE_MANUFACTURED = 9           # Manufactured (활성화 완료)


def _normalize_uid(uid: Optional[str]) -> Optional[str]:
    """UID를 no-space 형식으로 정규화."""
    if uid is None:
        return None
    return uid.replace(" ", "").upper()


def _uid_to_authority_key(uid_nospace: str) -> str:
    """Authority UID를 딕셔너리 키로 변환."""
    return uid_nospace.lower()


def _is_cpin_uid(uid: Optional[str]) -> bool:
    """주어진 UID가 C_PIN 테이블 객체인지 확인."""
    if uid is None:
        return False
    normalized = _normalize_uid(uid)
    return normalized.startswith(_CPIN_TABLE_PREFIX)


def _is_sp_uid(uid: Optional[str]) -> bool:
    """주어진 UID가 SP 테이블 객체인지 확인."""
    if uid is None:
        return False
    normalized = _normalize_uid(uid)
    return normalized.startswith(_SP_TABLE_PREFIX)


# ---------------------------------------------------------------------------
# 상태 정의
# ---------------------------------------------------------------------------

@dataclass
class CPINLifecycleState:
    """검증 상태 — C_PIN, Authority, Opal Session, Lifecycle 규칙 (R37-R56).

    Attributes:
        tries: authority_uid별 현재 시도 횟수
        try_limit: authority_uid별 TryLimit 값 (0 = 무제한)
        persistence: authority_uid별 Persistence 플래그
        locking_sp_lifecycle: LockingSP 생명주기 상태
        admin_sp_lifecycle: AdminSP 생명주기 상태 (항상 "manufactured")
        power_cycle_count: 전원 순환 횟수
        sid_pin_copied_to_admin1: Activate 후 SID PIN 복사 여부 (R52)
        session_aborted: Revert 후 세션 중단 여부 (R56)
        # 내부 추적용 추가 필드
        current_session_sp: 현재 세션이 연결된 SP (SPID)
        current_session_write: 현재 세션의 Write 파라미터 (True=RW, False=RO)
        current_session_auth: 현재 세션에서 인증된 authority UID
        session_active: 세션 활성 여부
        auth_results: 인증 시도 결과 기록 [(authority_uid, success_bool)]
        violations: 감지된 위반 목록
        sid_pin_value: 현재 SID PIN 값 (Activate 시 복사 추적용)
        admin1_pin_value: Admin1 PIN 값 (Activate 후 SID PIN이 복사됨)
        pin_values: C_PIN 객체별 현재 PIN 값
        activate_invoked: Activate가 호출된 적 있는지
        revert_invoked: Revert가 호출된 적 있는지
        records_processed: 처리된 레코드 수
        last_method: 마지막 호출된 메서드 이름
        session_timeout_value: 세션 타임아웃 값
        auth_operation_type: authority별 operation 타입 (Password/Exchange/TPerSign)
    """
    # R37-R42: C_PIN / TryLimit 상태
    tries: Dict[str, int] = field(default_factory=dict)
    try_limit: Dict[str, int] = field(default_factory=dict)
    persistence: Dict[str, bool] = field(default_factory=dict)

    # R48-R56: Lifecycle 상태
    locking_sp_lifecycle: str = "manufactured_inactive"
    admin_sp_lifecycle: str = "manufactured"

    # 전원 순환
    power_cycle_count: int = 0

    # R52: Activate 시 SID PIN -> Admin1 복사
    sid_pin_copied_to_admin1: bool = False

    # R56: Revert 후 세션 중단
    session_aborted: bool = False

    # 내부 추적 — 세션 상태
    current_session_sp: Optional[str] = None
    current_session_write: Optional[bool] = None
    current_session_auth: Optional[str] = None
    session_active: bool = False

    # 내부 추적 — 인증 이력
    auth_results: List[Tuple[str, bool]] = field(default_factory=list)

    # 내부 추적 — 위반 기록
    violations: List[str] = field(default_factory=list)

    # 내부 추적 — PIN 값
    sid_pin_value: Optional[str] = None
    admin1_pin_value: Optional[str] = None
    pin_values: Dict[str, str] = field(default_factory=dict)

    # 내부 추적 — Activate/Revert 이력
    activate_invoked: bool = False
    revert_invoked: bool = False

    # 내부 추적 — 메서드/레코드 카운터
    records_processed: int = 0
    last_method: Optional[str] = None

    # R47: SessionTimeout
    session_timeout_value: Optional[int] = None

    # R43-R45: Authority operation type
    auth_operation_type: Dict[str, str] = field(default_factory=dict)

    # Activate 대상 SP UID (최종 레코드에서 확인용)
    last_activate_target: Optional[str] = None

    # Revert 대상 SP UID
    last_revert_target: Optional[str] = None

    # StartSession에서 HostExchangeAuthority 사용 여부 (R43)
    host_exchange_authority_used: Optional[str] = None

    # StartSession에서 HostSigningAuthority 사용 여부 (R45)
    host_signing_authority_used: Optional[str] = None

    # 세션 시작 시 인증 성공 여부 (SyncSession 결과로 판단)
    session_auth_success: Optional[bool] = None

    # LockingSP lifecycle 값을 Get으로 읽은 경우 캐시
    observed_lifecycle_value: Optional[int] = None

    # 현재까지 처리한 레코드의 status_codes 기록
    status_history: List[str] = field(default_factory=list)

    # Activate 호출 이전 lifecycle 상태
    lifecycle_before_activate: Optional[str] = None

    # 최종 레코드 정보 (verdict 판정용)
    final_record: Optional[dict] = None


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def _extract_method_name(record: dict) -> Optional[str]:
    """레코드에서 메서드 이름 추출."""
    inp = record.get("input", {})
    method = inp.get("method", {})
    return method.get("name")


def _extract_invoking_uid(record: dict) -> Optional[str]:
    """레코드에서 invoking_id의 UID 추출 (space-separated)."""
    inp = record.get("input", {})
    invoking = inp.get("invoking_id", {})
    return invoking.get("uid")


def _extract_invoking_name(record: dict) -> Optional[str]:
    """레코드에서 invoking_id의 name 추출."""
    inp = record.get("input", {})
    invoking = inp.get("invoking_id", {})
    return invoking.get("name")


def _extract_input_status(record: dict) -> Optional[str]:
    """레코드에서 input side의 status_codes 추출."""
    inp = record.get("input", {})
    return inp.get("status_codes")


def _extract_output_status(record: dict) -> Optional[str]:
    """레코드에서 output side의 status_codes 추출."""
    out = record.get("output", {})
    return out.get("status_codes")


def _extract_args(record: dict) -> dict:
    """레코드에서 메서드 인자 추출 (required + optional 병합).
    # Changed: args가 list인 경우 (Properties 등) 방어 처리 추가.
    # Why: Properties 메서드의 args는 dict가 아니라 list 형태이므로
    #      .get() 호출 시 AttributeError가 발생했음.
    """
    inp = record.get("input", {})
    method = inp.get("method", {})
    args = method.get("args", {})
    if isinstance(args, list):
        return {"_list_args": args}
    if not isinstance(args, dict):
        return {}
    merged = {}
    merged.update(args.get("required", {}))
    merged.update(args.get("optional", {}))
    return merged


def _extract_output_return_values(record: dict) -> object:
    """레코드에서 output의 return_values 추출."""
    out = record.get("output", {})
    return out.get("return_values")


def _extract_spid_from_args(args: dict) -> Optional[str]:
    """StartSession args에서 SPID 추출."""
    return args.get("SPID")


def _extract_write_from_args(args: dict) -> Optional[bool]:
    """StartSession args에서 Write 파라미터 추출."""
    w = args.get("Write")
    if w is None:
        return None
    # Write=1 → True, Write=0 → False
    if isinstance(w, bool):
        return w
    return bool(int(w))


def _extract_host_signing_authority(args: dict) -> Optional[str]:
    """StartSession args에서 HostSigningAuthority 추출."""
    return args.get("HostSigningAuthority")


def _extract_host_exchange_authority(args: dict) -> Optional[str]:
    """StartSession args에서 HostExchangeAuthority 추출."""
    return args.get("HostExchangeAuthority")


def _extract_host_challenge(args: dict) -> Optional[str]:
    """StartSession args에서 HostChallenge 추출."""
    return args.get("HostChallenge")


def _extract_session_timeout(args: dict) -> Optional[int]:
    """StartSession args에서 SessionTimeout 추출."""
    val = args.get("SessionTimeout")
    if val is not None:
        return int(val)
    return None


def _extract_cellblock_column(args: dict) -> Optional[int]:
    """Get/Set args의 Cellblock에서 대상 컬럼 번호 추출."""
    cellblock = args.get("Cellblock", [])
    if isinstance(cellblock, list) and len(cellblock) > 0:
        first = cellblock[0]
        if isinstance(first, dict):
            return first.get("startColumn")
    return None


def _extract_set_values(args: dict) -> Optional[list]:
    """Set args에서 Values 추출."""
    return args.get("Values")


def _extract_pin_from_values(values: Optional[list]) -> Optional[str]:
    """Set Values에서 PIN 값(컬럼 3) 추출."""
    if values is None:
        return None
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict) and "3" in item:
                return str(item["3"])
    return None


def _extract_pin_from_get_result(return_values: object) -> Optional[str]:
    """Get return_values에서 PIN 값(컬럼 3) 추출."""
    # 형식: [[{"3": "PIN_VALUE"}]]
    if isinstance(return_values, list) and len(return_values) > 0:
        row = return_values[0]
        if isinstance(row, list) and len(row) > 0:
            cell = row[0]
            if isinstance(cell, dict) and "3" in cell:
                return str(cell["3"])
    return None


def _extract_lifecycle_from_get_result(return_values: object) -> Optional[int]:
    """Get return_values에서 LifeCycleState 값(컬럼 6) 추출."""
    # 형식: [[{"6": 8}]]
    if isinstance(return_values, list) and len(return_values) > 0:
        row = return_values[0]
        if isinstance(row, list) and len(row) > 0:
            cell = row[0]
            if isinstance(cell, dict) and "6" in cell:
                return int(cell["6"])
    return None


# ---------------------------------------------------------------------------
# 상태 전이 함수
# ---------------------------------------------------------------------------

def update_cpin_lifecycle(state: CPINLifecycleState, record: dict) -> CPINLifecycleState:
    """레코드 하나를 처리하여 상태를 갱신한다.

    Args:
        state: 현재 검증 상태 (in-place 변경됨)
        record: 하나의 trajectory 레코드 (input + output 포함)

    Returns:
        갱신된 상태 (동일 객체 반환)
    """
    state.records_processed += 1
    state.final_record = record

    method_name = _extract_method_name(record)
    invoking_uid = _extract_invoking_uid(record)
    output_status = _extract_output_status(record)
    input_status = _extract_input_status(record)
    args = _extract_args(record)
    return_values = _extract_output_return_values(record)

    state.last_method = method_name
    if output_status:
        state.status_history.append(output_status)

    # -----------------------------------------------------------------------
    # StartSession 처리
    # -----------------------------------------------------------------------
    if method_name == "StartSession":
        spid = _extract_spid_from_args(args)
        write = _extract_write_from_args(args)
        host_signing = _extract_host_signing_authority(args)
        host_exchange = _extract_host_exchange_authority(args)
        host_challenge = _extract_host_challenge(args)
        session_timeout = _extract_session_timeout(args)

        # R46: Write=True 지원 여부 추적
        state.current_session_write = write

        # R47: SessionTimeout 추적
        if session_timeout is not None:
            state.session_timeout_value = session_timeout

        # R43: HostExchangeAuthority에 Password authority 사용 감지
        if host_exchange is not None:
            state.host_exchange_authority_used = host_exchange

        # R45: HostSigningAuthority에 TPerSign authority 사용 감지
        if host_signing is not None:
            state.host_signing_authority_used = host_signing

        # SyncSession 성공 시 세션 활성화
        out = record.get("output", {})
        sync_name = out.get("method", {}).get("name") if isinstance(out.get("method"), dict) else None

        if output_status == "SUCCESS" and sync_name == "SyncSession":
            state.session_active = True
            state.current_session_sp = spid
            state.session_aborted = False  # 새 세션 시작 시 중단 플래그 초기화

            # 인증 성공 추적 (HostSigningAuthority가 있으면 세션 인증)
            if host_signing is not None and host_challenge is not None:
                auth_key = _uid_to_authority_key(host_signing)
                state.session_auth_success = True
                state.current_session_auth = host_signing

                # R38: 성공적 인증 시 Tries를 0으로 리셋
                if auth_key in state.tries:
                    state.tries[auth_key] = 0
            else:
                state.current_session_auth = None
                state.session_auth_success = None
        elif output_status == "NOT_AUTHORIZED":
            # R37: 인증 실패 시 Tries 증가
            if host_signing is not None:
                auth_key = _uid_to_authority_key(host_signing)
                tl = state.try_limit.get(auth_key, 0)
                if tl != 0:
                    current = state.tries.get(auth_key, 0)
                    # R39: Tries는 TryLimit을 초과하지 않음
                    if current < tl:
                        state.tries[auth_key] = current + 1
                else:
                    # R40: TryLimit=0이면 Tries는 항상 0
                    state.tries[auth_key] = 0

    # -----------------------------------------------------------------------
    # SyncSession 처리 (별도 레코드로 올 수도 있음)
    # -----------------------------------------------------------------------
    elif method_name == "SyncSession":
        # SyncSession은 보통 StartSession의 output에 포함되지만,
        # 별도 레코드로 올 경우에도 처리
        if output_status == "SUCCESS":
            state.session_active = True

    # -----------------------------------------------------------------------
    # Authenticate 처리 (R37-R42, R44)
    # -----------------------------------------------------------------------
    elif method_name == "Authenticate":
        # Authority UID 추출 (args에서)
        authority_uid = args.get("Authority")
        proof = args.get("Proof") or args.get("HostChallenge")

        if authority_uid is not None:
            auth_key = _uid_to_authority_key(authority_uid)

            # R44: Exchange authority는 Authenticate로 인증 불가
            op_type = state.auth_operation_type.get(auth_key)

            # 결과 확인
            if output_status == "SUCCESS":
                # return_values에서 True/False 확인
                result_bool = None
                if isinstance(return_values, bool):
                    result_bool = return_values
                elif isinstance(return_values, list) and len(return_values) > 0:
                    if isinstance(return_values[0], bool):
                        result_bool = return_values[0]
                elif isinstance(return_values, dict):
                    result_bool = return_values.get("result")

                if result_bool is True:
                    # R38: 인증 성공 → Tries = 0
                    state.tries[auth_key] = 0
                    state.auth_results.append((auth_key, True))
                    state.current_session_auth = authority_uid
                elif result_bool is False:
                    # R37: 인증 실패 → Tries 증가
                    tl = state.try_limit.get(auth_key, 0)
                    if tl != 0:
                        current = state.tries.get(auth_key, 0)
                        # R39: Tries는 TryLimit을 넘지 않음
                        if current < tl:
                            state.tries[auth_key] = current + 1
                    else:
                        # R40: TryLimit=0 → Tries = 0
                        state.tries[auth_key] = 0
                    state.auth_results.append((auth_key, False))
            elif output_status in ("INVALID_PARAMETER", "AUTHORITY_LOCKED_OUT"):
                state.auth_results.append((auth_key, False))

    # -----------------------------------------------------------------------
    # EndSession 처리
    # -----------------------------------------------------------------------
    elif method_name == "EndSession":
        if output_status == "SUCCESS":
            state.session_active = False
            state.current_session_sp = None
            state.current_session_write = None
            state.current_session_auth = None
            state.session_auth_success = None

    # -----------------------------------------------------------------------
    # Get 처리 — C_PIN PIN 읽기, SP LifeCycleState 읽기
    # -----------------------------------------------------------------------
    elif method_name == "Get":
        invoking_normalized = _normalize_uid(invoking_uid) if invoking_uid else None

        if output_status == "SUCCESS":
            # C_PIN 객체에서 PIN(컬럼 3) 읽기
            if invoking_normalized and invoking_normalized.startswith(_CPIN_TABLE_PREFIX):
                pin_val = _extract_pin_from_get_result(return_values)
                if pin_val is not None:
                    cpin_key = invoking_normalized.lower()
                    state.pin_values[cpin_key] = pin_val

                    # MSID PIN 읽기 추적
                    if invoking_normalized == _normalize_uid(_UID_CPIN_MSID_SPACED):
                        # MSID PIN → 초기 SID PIN과 동일
                        if state.sid_pin_value is None:
                            state.sid_pin_value = pin_val

                    # SID PIN 읽기 추적
                    if invoking_normalized == _normalize_uid(_UID_CPIN_SID_SPACED):
                        state.sid_pin_value = pin_val

            # SP 객체에서 LifeCycleState(컬럼 6) 읽기
            if invoking_normalized and invoking_normalized.startswith(_SP_TABLE_PREFIX):
                lifecycle_val = _extract_lifecycle_from_get_result(return_values)
                if lifecycle_val is not None:
                    state.observed_lifecycle_value = lifecycle_val
                    # SP UID에 따라 lifecycle 상태 갱신
                    if invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
                        if lifecycle_val == _LIFECYCLE_MANUFACTURED_INACTIVE:
                            state.locking_sp_lifecycle = "manufactured_inactive"
                        elif lifecycle_val == _LIFECYCLE_MANUFACTURED:
                            state.locking_sp_lifecycle = "manufactured"

    # -----------------------------------------------------------------------
    # Set 처리 — C_PIN PIN 변경 (R41)
    # -----------------------------------------------------------------------
    elif method_name == "Set":
        invoking_normalized = _normalize_uid(invoking_uid) if invoking_uid else None

        if output_status == "SUCCESS":
            # C_PIN 객체의 PIN(컬럼 3) 변경 감지
            if invoking_normalized and invoking_normalized.startswith(_CPIN_TABLE_PREFIX):
                values = _extract_set_values(args)
                new_pin = _extract_pin_from_values(values)
                if new_pin is not None:
                    cpin_key = invoking_normalized.lower()
                    state.pin_values[cpin_key] = new_pin

                    # R41: PIN 변경 시 Tries → 0
                    # C_PIN UID에서 대응하는 authority 추정
                    # C_PIN_SID (0B 00 00 00 01) → SID PIN 갱신
                    if invoking_normalized == _normalize_uid(_UID_CPIN_SID_SPACED):
                        state.sid_pin_value = new_pin
                        sid_key = _uid_to_authority_key(_AUTH_SID)
                        state.tries[sid_key] = 0

                    # C_PIN_Admin1 → Admin1 PIN 갱신
                    if invoking_normalized == _normalize_uid(_UID_CPIN_ADMIN1_SPACED):
                        state.admin1_pin_value = new_pin
                        admin1_key = _uid_to_authority_key(_AUTH_ADMIN1)
                        state.tries[admin1_key] = 0

    # -----------------------------------------------------------------------
    # GenKey 처리 — PIN 변경과 동일하게 Tries 리셋 (R41)
    # -----------------------------------------------------------------------
    elif method_name == "GenKey":
        if output_status == "SUCCESS":
            # GenKey는 C_PIN 객체가 아닌 키 객체에 적용되지만,
            # 키 변경도 Tries 리셋 트리거 가능 (spec에 따라)
            pass

    # -----------------------------------------------------------------------
    # Activate 처리 (R48-R52)
    # -----------------------------------------------------------------------
    elif method_name == "Activate":
        invoking_normalized = _normalize_uid(invoking_uid) if invoking_uid else None
        state.activate_invoked = True

        if invoking_normalized:
            state.last_activate_target = invoking_normalized

        # R51: Activate는 Admin SP에 대한 RW 세션에서만 유효
        if state.current_session_sp != _SPID_ADMIN:
            state.violations.append(
                "R51: Activate가 Admin SP가 아닌 세션에서 호출됨"
            )
        if state.current_session_write is not True:
            state.violations.append(
                "R51: Activate가 Read-Only 세션에서 호출됨"
            )

        if output_status == "SUCCESS":
            state.lifecycle_before_activate = state.locking_sp_lifecycle

            # R48: Manufactured-Inactive → Manufactured 전이
            if invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
                if state.locking_sp_lifecycle == "manufactured_inactive":
                    state.locking_sp_lifecycle = "manufactured"
                    # R52: SID PIN → Admin1 C_PIN 복사
                    if state.sid_pin_value is not None:
                        state.admin1_pin_value = state.sid_pin_value
                        state.sid_pin_copied_to_admin1 = True
                        admin1_cpin_key = _normalize_uid(_UID_CPIN_ADMIN1_SPACED).lower()
                        state.pin_values[admin1_cpin_key] = state.sid_pin_value
                # R50: 이미 Manufactured인 SP에 Activate → 성공, 변경 없음
                # (별도 처리 불필요 — 이미 manufactured이면 변경 안 함)

            # R49: issued SP에 대한 Activate는 금지
            # → output이 SUCCESS이면 위반 아님 (TPer가 허용했으므로)
            # → 하지만 issued SP를 판별하기 어려우므로 알려진 SP만 처리

    # -----------------------------------------------------------------------
    # Revert 처리 (R53-R56)
    # -----------------------------------------------------------------------
    elif method_name == "Revert":
        invoking_normalized = _normalize_uid(invoking_uid) if invoking_uid else None
        state.revert_invoked = True

        if invoking_normalized:
            state.last_revert_target = invoking_normalized

        # R55: Revert는 Admin SP에 대한 RW 세션 필요
        if state.current_session_sp != _SPID_ADMIN:
            state.violations.append(
                "R55: Revert가 Admin SP가 아닌 세션에서 호출됨"
            )
        if state.current_session_write is not True:
            state.violations.append(
                "R55: Revert가 Read-Only 세션에서 호출됨"
            )

        if output_status == "SUCCESS":
            # R54: Admin SP에 대한 Revert → 전체 TPer 리버트
            if invoking_normalized == _normalize_uid(_UID_SP_ADMIN_SPACED):
                state.locking_sp_lifecycle = "manufactured_inactive"
                state.sid_pin_copied_to_admin1 = False
                state.admin1_pin_value = None
                state.pin_values.clear()
                state.tries.clear()
                # R56: Admin SP Revert 후 세션 중단
                state.session_aborted = True
                state.session_active = False

            # R53: Manufactured-Inactive SP에 Revert → 효과 없음
            elif invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
                if state.locking_sp_lifecycle == "manufactured_inactive":
                    pass  # 효과 없음
                elif state.locking_sp_lifecycle == "manufactured":
                    # LockingSP Revert → Manufactured-Inactive로 복귀
                    state.locking_sp_lifecycle = "manufactured_inactive"
                    state.sid_pin_copied_to_admin1 = False

    # -----------------------------------------------------------------------
    # RevertSP 처리 (범위 외이지만 session_aborted 추적)
    # -----------------------------------------------------------------------
    elif method_name == "RevertSP":
        if output_status == "SUCCESS":
            invoking_normalized = _normalize_uid(invoking_uid) if invoking_uid else None
            if invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
                state.locking_sp_lifecycle = "manufactured_inactive"
                state.sid_pin_copied_to_admin1 = False
            state.session_aborted = True
            state.session_active = False

    # -----------------------------------------------------------------------
    # PowerCycle 처리 (R42)
    # -----------------------------------------------------------------------
    elif method_name == "PowerCycle" or method_name == "power_cycle":
        state.power_cycle_count += 1
        # R42: Persistence=False인 authority의 Tries → 0
        for auth_key, persistent in state.persistence.items():
            if not persistent:
                state.tries[auth_key] = 0
        # 세션 종료
        state.session_active = False
        state.current_session_sp = None
        state.current_session_write = None
        state.current_session_auth = None
        state.session_aborted = False

    # -----------------------------------------------------------------------
    # CloseSession 처리 (R56 확인용)
    # -----------------------------------------------------------------------
    elif method_name == "CloseSession":
        state.session_active = False
        state.current_session_sp = None

    return state


# ---------------------------------------------------------------------------
# 최종 verdict 판정 함수
# ---------------------------------------------------------------------------

def check_final_verdict_cpin_lifecycle(
    state: CPINLifecycleState,
    final_record: dict,
) -> Tuple[str, List[str]]:
    """최종 레코드를 기반으로 trajectory의 PASS/FAIL verdict를 판정한다.

    Args:
        state: update_cpin_lifecycle을 통해 모든 레코드를 처리한 후의 상태
        final_record: trajectory의 마지막 레코드

    Returns:
        (verdict, reasons) 튜플.
        verdict: "PASS" 또는 "FAIL"
        reasons: 판정 근거 문자열 리스트
    """
    reasons: List[str] = []
    violations: List[str] = []

    method_name = _extract_method_name(final_record)
    invoking_uid = _extract_invoking_uid(final_record)
    output_status = _extract_output_status(final_record)
    input_status = _extract_input_status(final_record)
    args = _extract_args(final_record)
    return_values = _extract_output_return_values(final_record)
    invoking_normalized = _normalize_uid(invoking_uid) if invoking_uid else None

    # -----------------------------------------------------------------------
    # 누적 위반 확인
    # -----------------------------------------------------------------------
    if state.violations:
        violations.extend(state.violations)

    # -----------------------------------------------------------------------
    # R37: 인증 실패 시 Tries 증가 확인
    # -----------------------------------------------------------------------
    # 최종 레코드가 인증 실패이고 TryLimit > 0인데 Tries가 증가하지 않았다면 위반
    if method_name == "Authenticate" and output_status == "SUCCESS":
        authority_uid = args.get("Authority")
        if authority_uid:
            auth_key = _uid_to_authority_key(authority_uid)
            result_bool = None
            if isinstance(return_values, bool):
                result_bool = return_values
            elif isinstance(return_values, list) and len(return_values) > 0:
                if isinstance(return_values[0], bool):
                    result_bool = return_values[0]

            if result_bool is False:
                # R37 검증: Tries가 적절히 증가했는지
                tl = state.try_limit.get(auth_key, 0)
                if tl != 0:
                    current_tries = state.tries.get(auth_key, 0)
                    if current_tries == 0:
                        violations.append(
                            f"R37: 인증 실패 후 Tries가 증가하지 않음 "
                            f"(authority={authority_uid})"
                        )

    # -----------------------------------------------------------------------
    # R39: Tries가 TryLimit을 초과하는지 확인
    # -----------------------------------------------------------------------
    for auth_key, tries_val in state.tries.items():
        tl = state.try_limit.get(auth_key, 0)
        if tl != 0 and tries_val > tl:
            violations.append(
                f"R39: Tries({tries_val})가 TryLimit({tl})을 초과 "
                f"(authority={auth_key})"
            )

    # -----------------------------------------------------------------------
    # R40: TryLimit=0인데 Tries가 0이 아닌 경우
    # -----------------------------------------------------------------------
    for auth_key, tl in state.try_limit.items():
        if tl == 0:
            current_tries = state.tries.get(auth_key, 0)
            if current_tries != 0:
                violations.append(
                    f"R40: TryLimit=0인데 Tries={current_tries} "
                    f"(authority={auth_key})"
                )

    # -----------------------------------------------------------------------
    # R43: Password authority를 Exchange로 사용한 경우
    # -----------------------------------------------------------------------
    if state.host_exchange_authority_used is not None:
        exch_key = _uid_to_authority_key(state.host_exchange_authority_used)
        op_type = state.auth_operation_type.get(exch_key, "Password")
        if op_type == "Password":
            if method_name == "StartSession" and output_status == "SUCCESS":
                violations.append(
                    f"R43: Password authority({state.host_exchange_authority_used})가 "
                    f"Exchange로 사용되었으나 SUCCESS 반환"
                )

    # -----------------------------------------------------------------------
    # R44: Exchange authority를 Authenticate로 사용한 경우
    # -----------------------------------------------------------------------
    if method_name == "Authenticate":
        authority_uid = args.get("Authority")
        if authority_uid:
            auth_key = _uid_to_authority_key(authority_uid)
            op_type = state.auth_operation_type.get(auth_key)
            if op_type == "Exchange":
                result_bool = None
                if isinstance(return_values, bool):
                    result_bool = return_values
                elif isinstance(return_values, list) and len(return_values) > 0:
                    if isinstance(return_values[0], bool):
                        result_bool = return_values[0]
                if result_bool is True:
                    violations.append(
                        f"R44: Exchange authority({authority_uid})의 "
                        f"Authenticate가 True를 반환"
                    )

    # -----------------------------------------------------------------------
    # R45: TPerSign authority를 HostSigningAuthority로 사용한 경우
    # -----------------------------------------------------------------------
    if state.host_signing_authority_used is not None:
        sign_key = _uid_to_authority_key(state.host_signing_authority_used)
        op_type = state.auth_operation_type.get(sign_key)
        if op_type == "TPerSign":
            if method_name == "StartSession" and output_status == "SUCCESS":
                violations.append(
                    f"R45: TPerSign authority({state.host_signing_authority_used})가 "
                    f"HostSigningAuthority로 사용되었으나 SUCCESS 반환"
                )

    # -----------------------------------------------------------------------
    # R46: Write=True StartSession이 지원되어야 함
    # -----------------------------------------------------------------------
    if method_name == "StartSession":
        write = _extract_write_from_args(args)
        if write is True and output_status != "SUCCESS":
            # Write=True가 지원되지 않음 → 다른 이유(잘못된 자격증명 등)이 아닌 한 위반
            # 단, NOT_AUTHORIZED 등은 R46이 아니라 인증 실패이므로 제외
            out = final_record.get("output", {})
            sync_status = out.get("status_codes")
            if sync_status not in ("NOT_AUTHORIZED", "AUTHORITY_LOCKED_OUT",
                                   "SP_BUSY", "SP_FROZEN",
                                   "NO_SESSIONS_AVAILABLE"):
                reasons.append(
                    "R46: Write=True StartSession이 실패 — 지원 필수"
                )

    # -----------------------------------------------------------------------
    # R47: SessionTimeout 범위 확인
    # -----------------------------------------------------------------------
    if method_name == "StartSession" and state.session_timeout_value is not None:
        # SessionTimeout이 유효 범위 외인데 SUCCESS인 경우 위반
        # 범위 정보가 없으므로 극단적 값만 감지 (0 이하 또는 매우 큰 값)
        timeout = state.session_timeout_value
        if timeout < 0 and output_status == "SUCCESS":
            violations.append(
                f"R47: 유효하지 않은 SessionTimeout({timeout})인데 SUCCESS 반환"
            )

    # -----------------------------------------------------------------------
    # R48: Activate 전이 검증 — Manufactured-Inactive → Manufactured
    # -----------------------------------------------------------------------
    if method_name == "Activate":
        if invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
            if output_status == "SUCCESS":
                # Activate 성공 후 lifecycle이 manufactured여야 함
                if state.locking_sp_lifecycle != "manufactured":
                    violations.append(
                        "R48: Activate 성공 후 LockingSP lifecycle이 "
                        f"manufactured가 아님 ({state.locking_sp_lifecycle})"
                    )
                reasons.append("R48: LockingSP Activate 전이 확인")

    # -----------------------------------------------------------------------
    # R49: issued SP에 대한 Activate 금지
    # -----------------------------------------------------------------------
    if method_name == "Activate":
        if invoking_normalized is not None:
            # 알려진 SP가 아닌 UID에 Activate 시도
            if invoking_normalized not in {
                _normalize_uid(uid) for uid in _KNOWN_SP_UIDS_SPACED
            }:
                if output_status == "SUCCESS":
                    violations.append(
                        f"R49: 알 수 없는/issued SP({invoking_normalized})에 대한 "
                        f"Activate가 SUCCESS 반환"
                    )

    # -----------------------------------------------------------------------
    # R50: 이미 Manufactured인 SP에 Activate → 성공, 효과 없음
    # -----------------------------------------------------------------------
    if method_name == "Activate":
        if invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
            if (state.lifecycle_before_activate == "manufactured"
                    and output_status != "SUCCESS"):
                violations.append(
                    "R50: 이미 Manufactured인 SP에 Activate 시 "
                    f"SUCCESS가 아닌 {output_status} 반환"
                )
        # AdminSP에 Activate → 항상 성공(이미 Manufactured)
        if invoking_normalized == _normalize_uid(_UID_SP_ADMIN_SPACED):
            if output_status != "SUCCESS":
                violations.append(
                    f"R50: AdminSP(이미 Manufactured)에 Activate 시 "
                    f"SUCCESS가 아닌 {output_status} 반환"
                )

    # -----------------------------------------------------------------------
    # R51: Activate는 Admin SP RW 세션 필요
    # -----------------------------------------------------------------------
    # (위반은 update에서 이미 기록됨)

    # -----------------------------------------------------------------------
    # R52: Activate 후 SID PIN → Admin1 C_PIN 복사 확인
    # -----------------------------------------------------------------------
    if state.activate_invoked and state.lifecycle_before_activate == "manufactured_inactive":
        if state.locking_sp_lifecycle == "manufactured":
            if state.sid_pin_value is not None and not state.sid_pin_copied_to_admin1:
                violations.append(
                    "R52: Activate 후 SID PIN이 Admin1 C_PIN에 복사되지 않음"
                )

    # -----------------------------------------------------------------------
    # R53: Manufactured-Inactive SP에 Revert → 효과 없음
    # -----------------------------------------------------------------------
    if method_name == "Revert":
        if invoking_normalized == _normalize_uid(_UID_SP_LOCKING_SPACED):
            if state.locking_sp_lifecycle == "manufactured_inactive":
                if output_status != "SUCCESS":
                    violations.append(
                        "R53: Manufactured-Inactive SP에 Revert 시 "
                        f"SUCCESS가 아닌 {output_status} 반환"
                    )

    # -----------------------------------------------------------------------
    # R54: Admin SP Revert → 전체 TPer 리버트
    # -----------------------------------------------------------------------
    if method_name == "Revert":
        if invoking_normalized == _normalize_uid(_UID_SP_ADMIN_SPACED):
            if output_status == "SUCCESS":
                if state.locking_sp_lifecycle != "manufactured_inactive":
                    violations.append(
                        "R54: Admin SP Revert 성공 후 LockingSP가 "
                        "manufactured_inactive로 복귀하지 않음"
                    )
                reasons.append("R54: Admin SP Revert → 전체 TPer 리버트")

    # -----------------------------------------------------------------------
    # R55: Revert는 Admin SP RW 세션 필요
    # -----------------------------------------------------------------------
    # (위반은 update에서 이미 기록됨)

    # -----------------------------------------------------------------------
    # R56: Admin SP Revert 후 세션 중단 확인
    # -----------------------------------------------------------------------
    if state.revert_invoked and state.last_revert_target == _normalize_uid(_UID_SP_ADMIN_SPACED):
        if not state.session_aborted:
            violations.append(
                "R56: Admin SP Revert 후 세션이 중단되지 않음"
            )

    # -----------------------------------------------------------------------
    # 최종 verdict 결정
    # -----------------------------------------------------------------------
    # 위반이 있으면 FAIL
    if violations:
        return ("FAIL", violations)

    # 위반이 없고 최종 레코드의 status가 정상이면 PASS
    reasons.append("모든 R37-R56 규칙 충족")
    return ("PASS", reasons)


# ---------------------------------------------------------------------------
# 전체 trajectory 검증 편의 함수
# ---------------------------------------------------------------------------

def verify_trajectory(trajectory_json: str) -> Tuple[str, List[str]]:
    """JSON 문자열 형태의 전체 trajectory를 검증한다.

    Args:
        trajectory_json: {"records": [{...}, ...]} 형태의 JSON 문자열

    Returns:
        (verdict, reasons) 튜플
    """
    data = json.loads(trajectory_json) if isinstance(trajectory_json, str) else trajectory_json
    records = data.get("records", [])
    if not records:
        return ("FAIL", ["레코드가 없음"])

    state = CPINLifecycleState()

    # 모든 레코드를 순차 처리
    for record in records:
        state = update_cpin_lifecycle(state, record)

    # 최종 레코드로 verdict 판정
    final_record = records[-1]
    return check_final_verdict_cpin_lifecycle(state, final_record)


# ---------------------------------------------------------------------------
# 직접 실행 시 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # tc5 분석 예시 (Activate flow — PASS 기대)
    tc5_input = {
        "records": [
            # record 1: StartSession to AdminSP (Anybody, RW)
            {
                "index": 1,
                "input": {
                    "invoking_id": {"name": "Session Manager UID", "type": None,
                                    "uid": "00 00 00 00 00 00 00 FF"},
                    "method": {
                        "args": {"optional": {},
                                 "required": {"HostSessionID": 1,
                                              "SPID": "0000020500000001",
                                              "Write": 1}},
                        "name": "StartSession",
                        "uid": "00 00 00 00 00 00 FF 02"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "method": {
                        "args": {"optional": {},
                                 "required": {"HostSessionID": "00000001",
                                              "SPSessionID": "00006314"}},
                        "name": "SyncSession",
                        "uid": "00 00 00 00 00 00 FF 03"},
                    "return_values": {"optional": {},
                                      "required": {"HostSessionID": "00000001",
                                                    "SPSessionID": "00006314"}},
                    "status_codes": "SUCCESS"}
            },
            # record 2: Get MSID PIN (C_PIN_MSID, column 3)
            {
                "index": 2,
                "input": {
                    "invoking_id": {"name": "C_PIN", "type": None,
                                    "uid": "00 00 00 0B 00 00 84 02"},
                    "method": {
                        "args": {"optional": {},
                                 "required": {"Cellblock": [{"startColumn": 3},
                                                            {"endColumn": 3}]}},
                        "name": "Get",
                        "uid": "00 00 00 06 00 00 00 16"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": [[{"3": "MJDL5TDSXBZ7NW3TE2PCESSNTLGYSBOW"}]],
                    "status_codes": "SUCCESS"}
            },
            # record 3: EndSession
            {
                "index": 3,
                "input": {
                    "invoking_id": {"name": None, "type": None, "uid": None},
                    "method": {"args": {"optional": {}, "required": {}},
                               "name": "EndSession", "uid": None},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": {"optional": {}, "required": {}},
                    "status_codes": "SUCCESS"}
            },
            # record 4: StartSession to AdminSP with SID auth
            {
                "index": 4,
                "input": {
                    "invoking_id": {"name": "Session Manager UID", "type": None,
                                    "uid": "00 00 00 00 00 00 00 FF"},
                    "method": {
                        "args": {
                            "optional": {
                                "HostChallenge": "3P5ADJBHFA4JJN57CZYR3FW1AEMDKF8J",
                                "HostSigningAuthority": "0000000900000006"},
                            "required": {"HostSessionID": 1,
                                         "SPID": "0000020500000001",
                                         "Write": 1}},
                        "name": "StartSession",
                        "uid": "00 00 00 00 00 00 FF 02"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "method": {
                        "args": {"optional": {},
                                 "required": {"HostSessionID": "00000001",
                                              "SPSessionID": "00006315"}},
                        "name": "SyncSession",
                        "uid": "00 00 00 00 00 00 FF 03"},
                    "return_values": {"optional": {},
                                      "required": {"HostSessionID": "00000001",
                                                    "SPSessionID": "00006315"}},
                    "status_codes": "SUCCESS"}
            },
            # record 5: Set SID PIN (C_PIN_SID, column 3)
            {
                "index": 5,
                "input": {
                    "invoking_id": {"name": "C_PIN", "type": None,
                                    "uid": "00 00 00 0B 00 00 00 01"},
                    "method": {
                        "args": {
                            "optional": {"Values": [
                                {"3": "3e06061d942f8b3cdb5058fdc9252d8d878010ecb205a0e2c2d26881fcb0b860"}]},
                            "required": {}},
                        "name": "Set",
                        "uid": "00 00 00 06 00 00 00 17"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": [],
                    "status_codes": "SUCCESS"}
            },
            # record 6: EndSession
            {
                "index": 6,
                "input": {
                    "invoking_id": {"name": None, "type": None, "uid": None},
                    "method": {"args": {"optional": {}, "required": {}},
                               "name": "EndSession", "uid": None},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": {"optional": {}, "required": {}},
                    "status_codes": "SUCCESS"}
            },
            # record 7: StartSession to AdminSP with SID auth (new PIN)
            {
                "index": 7,
                "input": {
                    "invoking_id": {"name": "Session Manager UID", "type": None,
                                    "uid": "00 00 00 00 00 00 00 FF"},
                    "method": {
                        "args": {
                            "optional": {
                                "HostChallenge": "3e06061d942f8b3cdb5058fdc9252d8d878010ecb205a0e2c2d26881fcb0b860",
                                "HostSigningAuthority": "0000000900000006"},
                            "required": {"HostSessionID": 1,
                                         "SPID": "0000020500000001",
                                         "Write": 1}},
                        "name": "StartSession",
                        "uid": "00 00 00 00 00 00 FF 02"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "method": {
                        "args": {"optional": {},
                                 "required": {"HostSessionID": "00000001",
                                              "SPSessionID": "00006316"}},
                        "name": "SyncSession",
                        "uid": "00 00 00 00 00 00 FF 03"},
                    "return_values": {"optional": {},
                                      "required": {"HostSessionID": "00000001",
                                                    "SPSessionID": "00006316"}},
                    "status_codes": "SUCCESS"}
            },
            # record 8: Get LockingSP LifeCycleState (column 6)
            {
                "index": 8,
                "input": {
                    "invoking_id": {"name": "SP", "type": None,
                                    "uid": "00 00 02 05 00 00 00 02"},
                    "method": {
                        "args": {"optional": {},
                                 "required": {"Cellblock": [{"startColumn": 6},
                                                            {"endColumn": 6}]}},
                        "name": "Get",
                        "uid": "00 00 00 06 00 00 00 16"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": [[{"6": 8}]],
                    "status_codes": "SUCCESS"}
            },
            # record 9: Activate LockingSP
            {
                "index": 9,
                "input": {
                    "invoking_id": {"name": "SP", "type": None,
                                    "uid": "00 00 02 05 00 00 00 02"},
                    "method": {
                        "args": {"optional": {}, "required": {}},
                        "name": "Activate",
                        "uid": "00 00 00 06 00 00 02 03"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": [],
                    "status_codes": "SUCCESS"}
            },
            # record 10: EndSession
            {
                "index": 10,
                "input": {
                    "invoking_id": {"name": None, "type": None, "uid": None},
                    "method": {"args": {"optional": {}, "required": {}},
                               "name": "EndSession", "uid": None},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": {"optional": {}, "required": {}},
                    "status_codes": "SUCCESS"}
            },
            # record 11: StartSession to LockingSP with Admin1 (using SID PIN)
            {
                "index": 11,
                "input": {
                    "invoking_id": {"name": "Session Manager UID", "type": None,
                                    "uid": "00 00 00 00 00 00 00 FF"},
                    "method": {
                        "args": {
                            "optional": {
                                "HostChallenge": "3e06061d942f8b3cdb5058fdc9252d8d878010ecb205a0e2c2d26881fcb0b860",
                                "HostSigningAuthority": "0000000900010001"},
                            "required": {"HostSessionID": 1,
                                         "SPID": "0000020500000002",
                                         "Write": 1}},
                        "name": "StartSession",
                        "uid": "00 00 00 00 00 00 FF 02"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "method": {
                        "args": {"optional": {},
                                 "required": {"HostSessionID": "00000001",
                                              "SPSessionID": "00006317"}},
                        "name": "SyncSession",
                        "uid": "00 00 00 00 00 00 FF 03"},
                    "return_values": {"optional": {},
                                      "required": {"HostSessionID": "00000001",
                                                    "SPSessionID": "00006317"}},
                    "status_codes": "SUCCESS"}
            },
        ]
    }

    print("=" * 60)
    print("tc5 검증 (Activate flow — PASS 기대)")
    print("=" * 60)
    verdict, reasons = verify_trajectory(tc5_input)
    print(f"Verdict: {verdict}")
    for r in reasons:
        print(f"  - {r}")

    print()

    # tc15 분석 예시 (잘못된 SP에 Activate — FAIL 기대)
    tc15_input = {
        "records": [
            # record 1-8: tc5와 동일 (생략 불가이므로 전체 포함)
            tc5_input["records"][0],
            tc5_input["records"][1],
            tc5_input["records"][2],
            tc5_input["records"][3],
            tc5_input["records"][4],
            tc5_input["records"][5],
            tc5_input["records"][6],
            tc5_input["records"][7],
            # record 9: Activate on WRONG SP (00 00 01 05 00 00 00 04)
            {
                "index": 9,
                "input": {
                    "invoking_id": {"name": "SP", "type": None,
                                    "uid": "00 00 01 05 00 00 00 04"},
                    "method": {
                        "args": {"optional": {}, "required": {}},
                        "name": "Activate",
                        "uid": "00 00 00 06 00 00 02 03"},
                    "status_codes": "SUCCESS"},
                "output": {
                    "return_values": [],
                    "status_codes": "SUCCESS"}
            },
        ]
    }

    print("=" * 60)
    print("tc15 검증 (잘못된 SP에 Activate — FAIL 기대)")
    print("=" * 60)
    verdict, reasons = verify_trajectory(tc15_input)
    print(f"Verdict: {verdict}")
    for r in reasons:
        print(f"  - {r}")
