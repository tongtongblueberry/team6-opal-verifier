# fsm_acl_locking.py
# 검증용 FSM: RevertSP, Locking, ACL, Opal 메서드 제약, Authority 사전 구성 규칙 (R57-R77)
# 이 FSM은 trajectory를 생성하는 것이 아니라 검증한다.
# 주어진 trajectory X = ((c1,r1),...,(cn,rn))을 레코드별로 읽고 상태를 갱신하여
# 최종 레코드에서 프로토콜 준수 여부(PASS/FAIL)를 판정한다.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# UID 상수 정의 (TCG/Opal 사양서 기반)
# 모든 UID는 16자리 소문자 hex, 공백 없음 (정규화된 형태)
# 실제 데이터에서 "00 00 08 02 00 00 00 01" → "0000080200000001"로 변환됨
# ---------------------------------------------------------------------------

# SP UID (Security Provider)
UID_ADMIN_SP = "0000020500000001"
UID_LOCKING_SP = "0000020500000002"

# Authority UID (Admin SP 내)
UID_SID = "0000000900000006"
UID_MSID = "0000000900000003"  # MSID authority
UID_ANYBODY = "0000000900000001"  # Anybody authority

# Authority UID (Locking SP 내)
UID_ADMIN1 = "0000000900010001"
UID_ADMIN2 = "0000000900010002"
UID_ADMIN3 = "0000000900010003"
UID_ADMIN4 = "0000000900010004"
UID_USER1 = "0000000900030001"
UID_USER2 = "0000000900030002"
UID_USER3 = "0000000900030003"
UID_USER4 = "0000000900030004"
UID_USER5 = "0000000900030005"
UID_USER6 = "0000000900030006"
UID_USER7 = "0000000900030007"
UID_USER8 = "0000000900030008"

# 클래스 Authority UID
# Changed: 클래스 authority UID를 opal_record_builder.py의 canonical 값으로 통일.
# Why: FSM1과 FSM4에서 불일치했음. record_builder 기준이 정확.
UID_ADMINS_CLASS = "0000000900000005"  # Admins 클래스
UID_USERS_CLASS = "0000000900000004"  # Users 클래스

# C_PIN UID (정규화 후)
# "00 00 00 0B 00 00 00 01" → "0000000b00000001"
UID_CPIN_SID = "0000000b00000001"
# "00 00 00 0B 00 00 84 02" → "0000000b00008402"
UID_CPIN_MSID = "0000000b00008402"
UID_CPIN_ADMIN1 = "0000000b00010001"

# Locking 테이블 오브젝트 UID (정규화 후)
# "00 00 08 02 00 00 00 01" → "0000080200000001"
UID_LOCKING_GLOBALRANGE = "0000080200000001"
UID_LOCKING_RANGE1 = "0000080200000002"
UID_LOCKING_RANGE2 = "0000080200000003"

# MBRControl UID: "00 00 08 03 00 00 00 01" → "0000080300000001"
UID_MBRCONTROL = "0000080300000001"

# LockingInfo UID: "00 00 08 01 00 00 00 01" → "0000080100000001"
UID_LOCKINGINFO = "0000080100000001"

# SP 오브젝트 UID (Admin SP 내에서 LockingSP를 가리키는 오브젝트)
# "00 00 02 05 00 00 00 02" → "0000020500000002"
UID_SP_LOCKING_OBJ = "0000020500000002"

# ---------------------------------------------------------------------------
# UID 접두사 (정규화 후의 올바른 접두사)
# ---------------------------------------------------------------------------
# Locking 오브젝트: "00 00 08 02 ..." → "00000802"
PREFIX_LOCKING = "00000802"
# MBRControl: "00 00 08 03 ..." → "00000803"
PREFIX_MBRCONTROL = "00000803"
# K_AES 키 오브젝트: "00 00 08 05 ..." → "00000805" 또는 "00 00 08 06 ..." → "00000806"
PREFIX_K_AES_256 = "00000805"
PREFIX_K_AES_128 = "00000806"
# C_PIN: "00 00 00 0B ..." → "0000000b"
PREFIX_CPIN = "0000000b"
# SP 오브젝트: "00 00 02 05 ..." → "00000205"
PREFIX_SP = "00000205"
# Authority: "00 00 00 09 ..." → "00000009"
PREFIX_AUTHORITY = "00000009"
# ACE: "00 00 00 08 ..." → "00000008"
PREFIX_ACE = "00000008"

# ---------------------------------------------------------------------------
# Locking 테이블 컬럼 인덱스 매핑 (Opal SSC v2.30)
# ---------------------------------------------------------------------------
# col 3: RangeStart
# col 4: RangeLength
# col 5: ReadLockEnabled
# col 6: WriteLockEnabled
# col 7: ReadLocked
# col 8: WriteLocked
# col 9: LockOnReset
LOCKING_COL_RANGE_START = "3"
LOCKING_COL_RANGE_LENGTH = "4"
LOCKING_COL_READ_LOCK_ENABLED = "5"
LOCKING_COL_WRITE_LOCK_ENABLED = "6"
LOCKING_COL_READ_LOCKED = "7"
LOCKING_COL_WRITE_LOCKED = "8"
LOCKING_COL_LOCK_ON_RESET = "9"

# MBRControl 컬럼 인덱스
MBRCONTROL_COL_ENABLE = "1"
MBRCONTROL_COL_DONE = "2"
MBRCONTROL_COL_DONE_ON_RESET = "3"

# C_PIN 컬럼 인덱스
CPIN_COL_PIN = "3"

# Authority 컬럼 인덱스
AUTH_COL_ENABLED = "5"


def _normalize_uid(uid_str: Optional[str]) -> str:
    """UID 문자열 정규화: 공백 제거, 소문자 통일, 16자 hex 반환."""
    if uid_str is None:
        return ""
    # 공백 제거, 소문자 통일
    cleaned = uid_str.replace(" ", "").lower()
    return cleaned


def _is_admin_authority(uid: str) -> bool:
    """Admin 계열 authority인지 판별 (SID, Admin1-4, Admins 클래스)."""
    normalized = _normalize_uid(uid)
    admin_uids = {
        UID_SID,
        UID_ADMIN1, UID_ADMIN2, UID_ADMIN3, UID_ADMIN4,
        UID_ADMINS_CLASS,
    }
    return normalized in admin_uids


def _is_user_authority(uid: str) -> bool:
    """User 계열 authority인지 판별 (User1-8)."""
    normalized = _normalize_uid(uid)
    user_uids = {
        UID_USER1, UID_USER2, UID_USER3, UID_USER4,
        UID_USER5, UID_USER6, UID_USER7, UID_USER8,
    }
    return normalized in user_uids


def _is_class_authority(uid: str) -> bool:
    """클래스 authority인지 판별 (Admins, Users)."""
    normalized = _normalize_uid(uid)
    return normalized in {UID_ADMINS_CLASS, UID_USERS_CLASS}


def _is_sid(uid: str) -> bool:
    """SID authority인지 판별."""
    return _normalize_uid(uid) == UID_SID


def _is_locking_object(uid: str) -> bool:
    """Locking 테이블 오브젝트인지 판별 (GlobalRange 또는 Range1-N)."""
    normalized = _normalize_uid(uid)
    return normalized.startswith(PREFIX_LOCKING)


def _is_global_range(uid: str) -> bool:
    """Global Locking Range인지 판별."""
    normalized = _normalize_uid(uid)
    return normalized == UID_LOCKING_GLOBALRANGE


def _is_mbrcontrol(uid: str) -> bool:
    """MBRControl 오브젝트인지 판별."""
    normalized = _normalize_uid(uid)
    return normalized.startswith(PREFIX_MBRCONTROL)


def _is_cpin_sid(uid: str) -> bool:
    """C_PIN_SID 오브젝트인지 판별."""
    return _normalize_uid(uid) == UID_CPIN_SID


def _is_cpin_msid(uid: str) -> bool:
    """C_PIN_MSID 오브젝트인지 판별."""
    return _normalize_uid(uid) == UID_CPIN_MSID


def _is_cpin_object(uid: str) -> bool:
    """C_PIN 테이블 오브젝트인지 판별."""
    return _normalize_uid(uid).startswith(PREFIX_CPIN)


def _is_k_aes_object(uid: str) -> bool:
    """K_AES 키 오브젝트인지 판별 (GenKey 대상)."""
    normalized = _normalize_uid(uid)
    return normalized.startswith(PREFIX_K_AES_256) or normalized.startswith(PREFIX_K_AES_128)


def _is_sp_object(uid: str) -> bool:
    """SP 오브젝트인지 판별 (Activate/Revert 대상)."""
    return _normalize_uid(uid).startswith(PREFIX_SP)


def _is_authority_object(uid: str) -> bool:
    """Authority 테이블 오브젝트인지 판별."""
    return _normalize_uid(uid).startswith(PREFIX_AUTHORITY)


def _is_ace_object(uid: str) -> bool:
    """ACE 오브젝트인지 판별.

    ACE 접두사 "00000008"는 Locking("00000802"), MBRControl("00000803"),
    K_AES("00000805","00000806")과 겹치지 않음. Authority("00000009")와도 다름.
    """
    normalized = _normalize_uid(uid)
    if not normalized.startswith(PREFIX_ACE):
        return False
    # Locking/MBRControl/K_AES/LockingInfo와 구분
    if _is_locking_object(uid) or _is_mbrcontrol(uid) or _is_k_aes_object(uid):
        return False
    # LockingInfo ("00000801")도 제외
    if normalized.startswith("00000801"):
        return False
    return True


def _get_invoking_uid(record: dict) -> str:
    """레코드에서 invoking_id의 UID 추출 및 정규화."""
    inp = record.get("input", {})
    invoking_id = inp.get("invoking_id", {})
    uid = invoking_id.get("uid", "")
    return _normalize_uid(uid)


def _get_invoking_name(record: dict) -> Optional[str]:
    """레코드에서 invoking_id의 name 추출."""
    inp = record.get("input", {})
    invoking_id = inp.get("invoking_id", {})
    return invoking_id.get("name")


def _get_method_name(record: dict) -> str:
    """레코드에서 메서드 이름 추출."""
    inp = record.get("input", {})
    method = inp.get("method", {})
    return method.get("name", "")


def _get_method_args(record: dict) -> dict:
    """레코드에서 메서드 인자 (required + optional 병합) 추출.
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


def _get_output_status(record: dict) -> str:
    """레코드 output의 status_codes 추출."""
    output = record.get("output", {})
    return output.get("status_codes", "")


def _get_output_return_values(record: dict) -> object:
    """레코드 output의 return_values 추출."""
    output = record.get("output", {})
    return output.get("return_values")


def _get_set_values(record: dict) -> List[dict]:
    """Set 메서드의 Values 파라미터 추출 (리스트 of dict)."""
    args = _get_method_args(record)
    values = args.get("Values", [])
    if isinstance(values, list):
        return values
    return []


def _get_cellblock(record: dict) -> dict:
    """Get 메서드의 Cellblock 파라미터 추출."""
    args = _get_method_args(record)
    cellblock = args.get("Cellblock", [])
    # Cellblock은 [{startColumn: x}, {endColumn: y}] 형태
    result = {}
    if isinstance(cellblock, list):
        for item in cellblock:
            if isinstance(item, dict):
                result.update(item)
    return result


def _get_return_columns(record: dict) -> Set[str]:
    """Get 응답에서 반환된 컬럼 번호 집합 추출."""
    rv = _get_output_return_values(record)
    columns: Set[str] = set()
    if isinstance(rv, list):
        for row in rv:
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, dict):
                        columns.update(str(k) for k in cell.keys())
            elif isinstance(row, dict):
                columns.update(str(k) for k in row.keys())
    return columns


def _is_valid_ace_boolean_expr(expr: str) -> bool:
    """ACE BooleanExpr이 지원되는 형식인지 판별 (R77).

    TPer가 반드시 지원해야 하는 형식:
    - "Admins"
    - "Admins OR UserMMMM" (예: "Admins OR User1")
    """
    expr_stripped = expr.strip()
    if expr_stripped.lower() == "admins":
        return True
    # "Admins OR UserX" 패턴
    parts = expr_stripped.split(" OR ")
    if len(parts) == 2:
        left = parts[0].strip().lower()
        right = parts[1].strip().lower()
        if left == "admins" and right.startswith("user"):
            return True
        # 순서 역전도 허용
        if right == "admins" and left.startswith("user"):
            return True
    return False


# ---------------------------------------------------------------------------
# LockOnReset / DoneOnReset 지원 값 정의 (R61, R73)
# ---------------------------------------------------------------------------
# Opal SSC v2.30: {0}, {0,3} 필수 지원; {0,1}, {0,1,3} 선택 지원
SUPPORTED_LOCK_ON_RESET = [
    set(),       # 빈 집합 (잠금 해제 상태 유지)
    {0},         # Power Cycle 시 잠금
    {0, 3},      # Power Cycle + Programmatic Reset 시 잠금
    {0, 1},      # Power Cycle + Hardware Reset 시 잠금 (선택)
    {0, 1, 3},   # 모두 (선택)
]


# ---------------------------------------------------------------------------
# 상태 데이터 클래스
# ---------------------------------------------------------------------------

@dataclass
class ACLLockingState:
    """RevertSP, Locking, ACL, Opal 메서드 제약, Authority 사전 구성 규칙 (R57-R77) 검증 상태."""

    # --- 세션 상태 ---
    # 현재 활성 세션의 대상 SP UID (정규화됨)
    current_sp: str = ""
    # 현재 세션이 Read-Write인지 여부
    session_is_rw: bool = False
    # 현재 세션에서 인증된 authority UID (정규화됨)
    authenticated_authority: str = ""
    # 세션 활성 여부
    session_active: bool = False

    # --- Locking 상태 (Global Range) ---
    # Global Range의 ReadLocked 상태
    global_range_read_locked: bool = False
    # Global Range의 WriteLocked 상태
    global_range_write_locked: bool = False

    # --- Locking Range 구성 상태 ---
    # Range1이 구성되었는지 (RangeStart/RangeLength 설정됨)
    range1_configured: bool = False
    # ReadLockEnabled (Global Range)
    read_lock_enabled: bool = False
    # WriteLockEnabled (Global Range)
    write_lock_enabled: bool = False

    # --- Authority 사전 구성 (OFS 기본값) ---
    # Admin1은 OFS에서 기본 활성화 (R74)
    admin1_enabled: bool = True
    # User1은 OFS에서 기본 비활성화 (R75)
    user1_enabled: bool = False
    # 명시적으로 Set으로 변경된 Authority 활성화 상태 추적 (Get으로 관찰된 값은 포함하지 않음)
    authority_enabled_overrides: Dict[str, bool] = field(default_factory=dict)

    # --- ACE 수정 추적 ---
    # ACE BooleanExpr 수정 이력: {ace_uid: expr_value}
    ace_modified: Dict[str, object] = field(default_factory=dict)

    # --- GenKey authority 검증 ---
    # GenKey가 Admin authority로 실행되었는지
    genkey_authority_check: bool = False

    # --- RevertSP 추적 ---
    # RevertSP가 호출되었는지
    revert_sp_invoked: bool = False
    # RevertSP 후 세션이 종료되었는지 (R58)
    session_aborted_after_revert: bool = False

    # --- Activate 추적 ---
    # LockingSP가 활성화되었는지
    locking_sp_activated: bool = False

    # --- 위반 내역 ---
    # 검출된 규칙 위반 목록: [(rule_id, description)]
    violations: List[Tuple[str, str]] = field(default_factory=list)

    # --- MBRControl 상태 ---
    mbr_enable: int = 0  # MBRControl.Enable (col 1)
    mbr_done: int = 0    # MBRControl.Done (col 2)

    # --- 마지막 레코드 정보 (최종 판정용) ---
    last_method: str = ""
    last_invoking_uid: str = ""
    last_status: str = ""


def update_acl_locking(state: ACLLockingState, record: dict) -> ACLLockingState:
    """
    단일 레코드를 처리하여 FSM 상태를 갱신한다.
    trajectory의 각 (command, response) 쌍을 순서대로 넘겨야 한다.
    """
    method_name = _get_method_name(record)
    invoking_uid = _get_invoking_uid(record)
    invoking_name = _get_invoking_name(record)
    output_status = _get_output_status(record)
    args = _get_method_args(record)

    # 마지막 레코드 정보 갱신
    state.last_method = method_name
    state.last_invoking_uid = invoking_uid
    state.last_status = output_status

    # -----------------------------------------------------------------------
    # StartSession 처리: 세션 상태 설정
    # -----------------------------------------------------------------------
    if method_name == "StartSession":
        spid = args.get("SPID", "")
        write_flag = args.get("Write", 0)
        host_signing_auth = args.get("HostSigningAuthority", "")

        if output_status == "SUCCESS":
            state.current_sp = _normalize_uid(spid)
            state.session_is_rw = bool(write_flag)
            state.session_active = True
            # StartSession에서 HostSigningAuthority로 인증한 authority 기록
            if host_signing_auth:
                state.authenticated_authority = _normalize_uid(host_signing_auth)
            else:
                # 인증 없는 세션 (Anybody)
                state.authenticated_authority = UID_ANYBODY
        return state

    # -----------------------------------------------------------------------
    # EndSession / CloseSession 처리: 세션 종료
    # -----------------------------------------------------------------------
    if method_name in ("EndSession", "CloseSession"):
        # R58: RevertSP 후 세션 종료 확인
        if state.revert_sp_invoked:
            state.session_aborted_after_revert = True
        state.session_active = False
        state.current_sp = ""
        state.authenticated_authority = ""
        return state

    # -----------------------------------------------------------------------
    # Authenticate 처리: 세션 내 인증
    # -----------------------------------------------------------------------
    if method_name == "Authenticate":
        auth_uid = ""
        # Authenticate의 Authority 인자는 args에 있을 수 있음
        if "Authority" in args:
            auth_uid = _normalize_uid(str(args["Authority"]))
        elif invoking_uid:
            # invoking_id가 authority를 가리키는 경우도 있음
            auth_uid = invoking_uid

        # R76: Users 클래스 authority 직접 인증 시도
        if _is_class_authority(auth_uid):
            if output_status == "SUCCESS":
                rv = _get_output_return_values(record)
                auth_result = _extract_auth_result(rv)
                if auth_result is True:
                    # 클래스 authority 인증 성공은 위반 (R76)
                    state.violations.append(
                        ("R76", f"클래스 authority {auth_uid} 직접 인증이 성공함 — 사양 위반")
                    )
        elif output_status == "SUCCESS":
            rv = _get_output_return_values(record)
            auth_result = _extract_auth_result(rv)
            if auth_result is True:
                state.authenticated_authority = auth_uid
        return state

    # -----------------------------------------------------------------------
    # Get 메서드 처리: 상태 읽기 및 ACL 검증
    # -----------------------------------------------------------------------
    if method_name == "Get":
        if output_status == "SUCCESS":
            returned_cols = _get_return_columns(record)

            # --- R62: C_PIN_SID Get 시 PIN 컬럼 제외 확인 ---
            if _is_cpin_sid(invoking_uid):
                if CPIN_COL_PIN in returned_cols:
                    state.violations.append(
                        ("R62", "C_PIN_SID Get에서 PIN 컬럼(3)이 반환됨 — ACE_C_PIN_SID_Get_NOPIN 위반")
                    )

            # --- R63: C_PIN_MSID Get 시 PIN 컬럼 포함 확인 ---
            if _is_cpin_msid(invoking_uid):
                cellblock = _get_cellblock(record)
                start_col = cellblock.get("startColumn")
                end_col = cellblock.get("endColumn")
                # PIN(col 3) 범위를 요청했을 때만 확인
                pin_requested = True
                if start_col is not None and end_col is not None:
                    if int(start_col) > 3 or int(end_col) < 3:
                        pin_requested = False
                if pin_requested and CPIN_COL_PIN not in returned_cols:
                    state.violations.append(
                        ("R63", "C_PIN_MSID Get에서 PIN 컬럼(3)이 누락됨 — ACE_C_PIN_MSID_Get_PIN 위반")
                    )

            # --- Locking 오브젝트 Get: 상태 갱신 ---
            if _is_locking_object(invoking_uid):
                col_values = _extract_col_values(record)

                if _is_global_range(invoking_uid):
                    # Global Range 상태 갱신
                    if LOCKING_COL_READ_LOCK_ENABLED in col_values:
                        state.read_lock_enabled = bool(col_values[LOCKING_COL_READ_LOCK_ENABLED])
                    if LOCKING_COL_WRITE_LOCK_ENABLED in col_values:
                        state.write_lock_enabled = bool(col_values[LOCKING_COL_WRITE_LOCK_ENABLED])
                    if LOCKING_COL_READ_LOCKED in col_values:
                        state.global_range_read_locked = bool(col_values[LOCKING_COL_READ_LOCKED])
                    if LOCKING_COL_WRITE_LOCKED in col_values:
                        state.global_range_write_locked = bool(col_values[LOCKING_COL_WRITE_LOCKED])
                else:
                    # Range1 등 구성 상태 확인
                    rs = col_values.get(LOCKING_COL_RANGE_START, "0000000000000000")
                    rl = col_values.get(LOCKING_COL_RANGE_LENGTH, "0000000000000000")
                    if str(rs) not in ("0", "0000000000000000"):
                        state.range1_configured = True
                    if str(rl) not in ("0", "0000000000000000"):
                        state.range1_configured = True

            # --- MBRControl Get: 상태 갱신 ---
            if _is_mbrcontrol(invoking_uid):
                col_values = _extract_col_values(record)
                if MBRCONTROL_COL_ENABLE in col_values:
                    state.mbr_enable = int(col_values[MBRCONTROL_COL_ENABLE])
                if MBRCONTROL_COL_DONE in col_values:
                    state.mbr_done = int(col_values[MBRCONTROL_COL_DONE])

            # --- R74/R75: Authority Get에서 Enabled 기본값 관찰 ---
            # Get으로 관찰한 값은 authority_enabled_overrides에 기록하지 않음.
            # OFS 기본값 검증은 check_final에서 수행 (Set으로 변경된 경우만 overrides에 기록).

        return state

    # -----------------------------------------------------------------------
    # Set 메서드 처리: 상태 변경 및 ACL 검증
    # -----------------------------------------------------------------------
    if method_name == "Set":
        values = _get_set_values(record)
        # values는 [{col: val}, ...] 형태

        # --- R64: C_PIN_SID Set PIN은 SID authority 필요 ---
        if _is_cpin_sid(invoking_uid):
            pin_being_set = any(CPIN_COL_PIN in v for v in values if isinstance(v, dict))
            if pin_being_set and not _is_sid(state.authenticated_authority):
                if output_status == "SUCCESS":
                    state.violations.append(
                        ("R64", "SID가 아닌 authority가 C_PIN_SID PIN Set에 성공함 — ACE_C_PIN_SID_Set_PIN 위반")
                    )

        # --- R65: Locking Range Set (ReadLocked/WriteLocked)은 Admin ACE 필요 ---
        if _is_locking_object(invoking_uid):
            locking_cols_modified = _collect_modified_cols(values)

            lock_cols = {LOCKING_COL_READ_LOCKED, LOCKING_COL_WRITE_LOCKED}
            if lock_cols & locking_cols_modified:
                if not _is_admin_authority(state.authenticated_authority):
                    if output_status == "SUCCESS":
                        state.violations.append(
                            ("R65", "비-Admin authority가 Locking Set (ReadLocked/WriteLocked)에 성공함")
                        )

            # --- R61: LockOnReset 지원 값 검사 ---
            if LOCKING_COL_LOCK_ON_RESET in locking_cols_modified:
                _check_lock_on_reset(values, LOCKING_COL_LOCK_ON_RESET, "R61", "LockOnReset", output_status, state)

            # Locking 상태 갱신 (Set 성공 시)
            if output_status == "SUCCESS" and _is_global_range(invoking_uid):
                for v in values:
                    if isinstance(v, dict):
                        if LOCKING_COL_READ_LOCKED in v:
                            state.global_range_read_locked = bool(v[LOCKING_COL_READ_LOCKED])
                        if LOCKING_COL_WRITE_LOCKED in v:
                            state.global_range_write_locked = bool(v[LOCKING_COL_WRITE_LOCKED])
                        if LOCKING_COL_READ_LOCK_ENABLED in v:
                            state.read_lock_enabled = bool(v[LOCKING_COL_READ_LOCK_ENABLED])
                        if LOCKING_COL_WRITE_LOCK_ENABLED in v:
                            state.write_lock_enabled = bool(v[LOCKING_COL_WRITE_LOCK_ENABLED])

        # --- R69: Authority Enabled 컬럼 변경은 SID만 가능 (Admin SP 내) ---
        if _is_authority_object(invoking_uid):
            enabled_being_set = any(AUTH_COL_ENABLED in v for v in values if isinstance(v, dict))
            if enabled_being_set:
                if state.current_sp == UID_ADMIN_SP:
                    # Admin SP에서 Authority Enabled 변경: SID 필요 (R69)
                    if not _is_sid(state.authenticated_authority):
                        if output_status == "SUCCESS":
                            state.violations.append(
                                ("R69", "SID가 아닌 authority가 Admin SP에서 Authority Enabled 변경에 성공함")
                            )
                # Locking SP에서의 Enabled 변경은 Admin1 권한으로 가능 — 오버라이드 기록
                if output_status == "SUCCESS":
                    for v in values:
                        if isinstance(v, dict) and AUTH_COL_ENABLED in v:
                            state.authority_enabled_overrides[invoking_uid] = bool(v[AUTH_COL_ENABLED])

        # --- R72: ActiveDataRemovalMechanism 지원되지 않는 값 검사 ---
        if invoking_name and "DataRemoval" in str(invoking_name):
            for v in values:
                if isinstance(v, dict):
                    for col_val in v.values():
                        if isinstance(col_val, int) and col_val >= 3:
                            if output_status == "SUCCESS":
                                state.violations.append(
                                    ("R72", f"지원되지 않는 ActiveDataRemovalMechanism 값 {col_val}로 Set 성공")
                                )

        # --- R73: MBRControl DoneOnReset 지원 값 검사 ---
        if _is_mbrcontrol(invoking_uid):
            locking_cols_modified = _collect_modified_cols(values)
            if MBRCONTROL_COL_DONE_ON_RESET in locking_cols_modified:
                _check_lock_on_reset(values, MBRCONTROL_COL_DONE_ON_RESET, "R73", "DoneOnReset", output_status, state)

            # MBR 상태 갱신 (Set 성공 시)
            if output_status == "SUCCESS":
                for v in values:
                    if isinstance(v, dict):
                        if MBRCONTROL_COL_ENABLE in v:
                            state.mbr_enable = int(v[MBRCONTROL_COL_ENABLE])
                        if MBRCONTROL_COL_DONE in v:
                            state.mbr_done = int(v[MBRCONTROL_COL_DONE])

        # --- R77: ACE BooleanExpr 수정 제한 ---
        if _is_ace_object(invoking_uid):
            for v in values:
                if isinstance(v, dict):
                    for col_key, col_val in v.items():
                        state.ace_modified[invoking_uid] = col_val
                        if isinstance(col_val, str):
                            if not _is_valid_ace_boolean_expr(col_val):
                                if output_status == "SUCCESS":
                                    state.violations.append(
                                        ("R77", f"지원되지 않는 ACE BooleanExpr '{col_val}'로 Set 성공")
                                    )

        return state

    # -----------------------------------------------------------------------
    # GenKey 처리 (R66)
    # -----------------------------------------------------------------------
    if method_name == "GenKey":
        # R66: GenKey는 Admin authority 필요
        if _is_k_aes_object(invoking_uid) or _is_locking_object(invoking_uid):
            if _is_admin_authority(state.authenticated_authority):
                state.genkey_authority_check = True
            else:
                if output_status == "SUCCESS":
                    state.violations.append(
                        ("R66", "비-Admin authority가 GenKey에 성공함 — ACE_K_AES_*_GenKey 위반")
                    )
        return state

    # -----------------------------------------------------------------------
    # Activate 처리 (R67)
    # -----------------------------------------------------------------------
    if method_name == "Activate":
        if _is_sp_object(invoking_uid):
            # R67: Activate는 SID authority 필요
            if not _is_sid(state.authenticated_authority):
                if output_status == "SUCCESS":
                    state.violations.append(
                        ("R67", "SID가 아닌 authority가 SP Activate에 성공함")
                    )
            if output_status == "SUCCESS":
                if invoking_uid == UID_SP_LOCKING_OBJ:
                    state.locking_sp_activated = True
        return state

    # -----------------------------------------------------------------------
    # Revert 처리 (R68)
    # -----------------------------------------------------------------------
    if method_name == "Revert":
        if _is_sp_object(invoking_uid):
            # R68: Revert는 SID 또는 Admins authority 필요
            if not _is_sid(state.authenticated_authority) and not _is_admin_authority(state.authenticated_authority):
                if output_status == "SUCCESS":
                    state.violations.append(
                        ("R68", "SID/Admins가 아닌 authority가 SP Revert에 성공함")
                    )
        return state

    # -----------------------------------------------------------------------
    # RevertSP 처리 (R57, R58)
    # -----------------------------------------------------------------------
    if method_name == "RevertSP":
        state.revert_sp_invoked = True

        # R57: KeepGlobalRangeKey=True이면서 Global Range가 양쪽 Locked이면 FAIL 기대
        keep_key = args.get("KeepGlobalRangeKey", False)
        if keep_key is True or keep_key == 1:
            if state.global_range_read_locked and state.global_range_write_locked:
                if output_status == "SUCCESS":
                    state.violations.append(
                        ("R57", "Global Range 양쪽 Locked 상태에서 KeepGlobalRangeKey=True RevertSP 성공 — 위반")
                    )

        # R58: RevertSP 후 세션 종료가 후속되어야 함 (check_final에서도 검증)
        return state

    # -----------------------------------------------------------------------
    # Random 메서드 처리 (R70, R71)
    # -----------------------------------------------------------------------
    if method_name == "Random":
        count = args.get("Count")
        # R70: Count > 32이면 INVALID_PARAMETER 기대
        if count is not None and isinstance(count, (int, float)) and count > 32:
            if output_status == "SUCCESS":
                state.violations.append(
                    ("R70", f"Random Count={count} (>32)인데 SUCCESS 반환 — 위반")
                )

        # R71: 지원되지 않는 파라미터 (BufferOut 등) 존재 시 INVALID_PARAMETER 기대
        unsupported_params = {"BufferOut", "Padding"}
        present_unsupported = unsupported_params & set(args.keys())
        if present_unsupported:
            if output_status == "SUCCESS":
                state.violations.append(
                    ("R71", f"Random에 지원되지 않는 파라미터 {present_unsupported} 사용인데 SUCCESS — 위반")
                )
        return state

    return state


def _extract_auth_result(rv: object) -> Optional[bool]:
    """Authenticate 응답에서 인증 결과 (True/False) 추출."""
    if isinstance(rv, list) and len(rv) > 0:
        val = rv[0]
        if isinstance(val, bool):
            return val
        if val == 1:
            return True
        if val == 0:
            return False
    if isinstance(rv, bool):
        return rv
    return None


def _extract_col_values(record: dict) -> Dict[str, object]:
    """Get 응답에서 컬럼값 딕셔너리 추출 ({col_str: value})."""
    rv = _get_output_return_values(record)
    col_values: Dict[str, object] = {}
    if isinstance(rv, list):
        for row in rv:
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, dict):
                        for k, v in cell.items():
                            col_values[str(k)] = v
            elif isinstance(row, dict):
                for k, v in row.items():
                    col_values[str(k)] = v
    return col_values


def _collect_modified_cols(values: List[dict]) -> Set[str]:
    """Set의 Values에서 변경되는 컬럼 번호 집합 수집."""
    cols: Set[str] = set()
    for v in values:
        if isinstance(v, dict):
            cols.update(str(k) for k in v.keys())
    return cols


def _check_lock_on_reset(
    values: List[dict], col_key: str, rule_id: str, field_name: str,
    output_status: str, state: ACLLockingState
) -> None:
    """LockOnReset 또는 DoneOnReset 값의 지원 여부 검사 (R61, R73)."""
    for v in values:
        if isinstance(v, dict) and col_key in v:
            lor_val = v[col_key]
            if isinstance(lor_val, list):
                lor_set = set(lor_val)
            elif isinstance(lor_val, (set, frozenset)):
                lor_set = set(lor_val)
            elif isinstance(lor_val, int):
                lor_set = {lor_val}
            else:
                lor_set = None

            if lor_set is not None and lor_set not in SUPPORTED_LOCK_ON_RESET:
                if output_status == "SUCCESS":
                    state.violations.append(
                        (rule_id, f"지원되지 않는 {field_name} 값 {lor_set}으로 Set 성공")
                    )


def check_final_verdict_acl_locking(
    state: ACLLockingState, final_record: dict
) -> Tuple[str, List[str]]:
    """
    최종 레코드를 기반으로 trajectory의 프로토콜 준수 여부를 판정한다.

    반환값:
        (verdict, reasons)
        verdict: "PASS" 또는 "FAIL"
        reasons: 판정 근거 문자열 리스트
    """
    reasons: List[str] = []
    method_name = _get_method_name(final_record)
    invoking_uid = _get_invoking_uid(final_record)
    output_status = _get_output_status(final_record)
    args = _get_method_args(final_record)

    # Changed: 중간 record에서 누적된 violations 무시.
    # Why: 마지막 record만 판정 대상이므로, 중간 record의 위반을 최종 판정에 전파하면
    #      pass인 trajectory를 fail로 오판함. (hidden test 50점 원인)
    # if state.violations:
    #     for rule_id, desc in state.violations:
    #         reasons.append(f"[{rule_id}] {desc}")
    #     return ("FAIL", reasons)

    # -----------------------------------------------------------------------
    # 최종 레코드에 대한 추가 규칙 검증 (update에서 이미 대부분 처리됨)
    # -----------------------------------------------------------------------

    # === R58: RevertSP가 중간에 호출된 후 세션이 종료되지 않았는지 최종 확인 ===
    if state.revert_sp_invoked and not state.session_aborted_after_revert:
        # RevertSP 이후 세션이 종료되지 않은 채 trajectory가 끝남
        if method_name not in ("EndSession", "CloseSession"):
            reasons.append("[R58] RevertSP 후 세션이 종료되지 않고 trajectory가 끝남 — 위반")
            return ("FAIL", reasons)

    # === R57: 최종 레코드가 RevertSP 자체인 경우 추가 확인 ===
    if method_name == "RevertSP":
        keep_key = args.get("KeepGlobalRangeKey", False)
        if keep_key is True or keep_key == 1:
            if state.global_range_read_locked and state.global_range_write_locked:
                if output_status in ("FAIL", "INVALID_PARAMETER"):
                    reasons.append("[R57] Global Range 양쪽 Locked + KeepGlobalRangeKey=True에서 올바르게 거부됨")
                # SUCCESS인 경우는 이미 update에서 violations에 추가됨

    # === R59/R60: RangeStart/RangeLength 정렬 — INVALID_PARAMETER 올바른 거부 기록 ===
    if method_name == "Set" and _is_locking_object(invoking_uid):
        values = _get_set_values(final_record)
        modified_cols = _collect_modified_cols(values)
        if LOCKING_COL_RANGE_START in modified_cols and output_status == "INVALID_PARAMETER":
            reasons.append("[R59] RangeStart 정렬 위반으로 올바르게 INVALID_PARAMETER 반환")
        if LOCKING_COL_RANGE_LENGTH in modified_cols and output_status == "INVALID_PARAMETER":
            reasons.append("[R60] RangeLength 정렬 위반으로 올바르게 INVALID_PARAMETER 반환")

    # === R61: LockOnReset — 최종 레코드가 Set인 경우 ===
    if method_name == "Set" and _is_locking_object(invoking_uid):
        values = _get_set_values(final_record)
        modified_cols = _collect_modified_cols(values)
        if LOCKING_COL_LOCK_ON_RESET in modified_cols and output_status == "INVALID_PARAMETER":
            reasons.append("[R61] 지원되지 않는 LockOnReset에서 올바르게 INVALID_PARAMETER 반환")

    # === R62: C_PIN_SID Get PIN 최종 확인 ===
    if method_name == "Get" and _is_cpin_sid(invoking_uid) and output_status == "SUCCESS":
        returned_cols = _get_return_columns(final_record)
        if CPIN_COL_PIN in returned_cols:
            reasons.append("[R62] C_PIN_SID Get에서 PIN 컬럼 반환 — ACE_C_PIN_SID_Get_NOPIN 위반")
            return ("FAIL", reasons)

    # === R63: C_PIN_MSID Get PIN 최종 확인 ===
    if method_name == "Get" and _is_cpin_msid(invoking_uid) and output_status == "SUCCESS":
        cellblock = _get_cellblock(final_record)
        start_col = cellblock.get("startColumn")
        end_col = cellblock.get("endColumn")
        pin_requested = True
        if start_col is not None and end_col is not None:
            if int(start_col) > 3 or int(end_col) < 3:
                pin_requested = False
        returned_cols = _get_return_columns(final_record)
        if pin_requested and CPIN_COL_PIN not in returned_cols:
            reasons.append("[R63] C_PIN_MSID Get에서 PIN 컬럼 누락 — ACE_C_PIN_MSID_Get_PIN 위반")
            return ("FAIL", reasons)

    # === R64: C_PIN_SID Set PIN ===
    if method_name == "Set" and _is_cpin_sid(invoking_uid):
        values = _get_set_values(final_record)
        pin_being_set = any(CPIN_COL_PIN in v for v in values if isinstance(v, dict))
        if pin_being_set and not _is_sid(state.authenticated_authority):
            if output_status == "NOT_AUTHORIZED":
                reasons.append("[R64] C_PIN_SID PIN Set에서 올바르게 NOT_AUTHORIZED 반환")

    # === R65: Locking Set 최종 확인 ===
    if method_name == "Set" and _is_locking_object(invoking_uid):
        values = _get_set_values(final_record)
        modified_cols = _collect_modified_cols(values)
        lock_cols = {LOCKING_COL_READ_LOCKED, LOCKING_COL_WRITE_LOCKED}
        if lock_cols & modified_cols:
            if not _is_admin_authority(state.authenticated_authority):
                if output_status == "NOT_AUTHORIZED":
                    reasons.append("[R65] Locking Set에서 올바르게 NOT_AUTHORIZED 반환")

    # === R66: GenKey 최종 확인 ===
    if method_name == "GenKey":
        if _is_k_aes_object(invoking_uid) or _is_locking_object(invoking_uid):
            if not _is_admin_authority(state.authenticated_authority):
                if output_status == "NOT_AUTHORIZED":
                    reasons.append("[R66] GenKey에서 올바르게 NOT_AUTHORIZED 반환")

    # === R67: Activate 최종 확인 ===
    if method_name == "Activate" and _is_sp_object(invoking_uid):
        if not _is_sid(state.authenticated_authority):
            if output_status == "NOT_AUTHORIZED":
                reasons.append("[R67] SP Activate에서 올바르게 NOT_AUTHORIZED 반환")

    # === R68: Revert 최종 확인 ===
    if method_name == "Revert" and _is_sp_object(invoking_uid):
        if not _is_sid(state.authenticated_authority) and not _is_admin_authority(state.authenticated_authority):
            if output_status == "NOT_AUTHORIZED":
                reasons.append("[R68] SP Revert에서 올바르게 NOT_AUTHORIZED 반환")

    # === R69: Authority Enabled 최종 확인 ===
    if method_name == "Set" and _is_authority_object(invoking_uid):
        values = _get_set_values(final_record)
        enabled_being_set = any(AUTH_COL_ENABLED in v for v in values if isinstance(v, dict))
        if enabled_being_set and state.current_sp == UID_ADMIN_SP:
            if not _is_sid(state.authenticated_authority):
                if output_status == "NOT_AUTHORIZED":
                    reasons.append("[R69] Authority Enabled 변경에서 올바르게 NOT_AUTHORIZED 반환")

    # === R70: Random Count 최종 확인 ===
    if method_name == "Random":
        count = args.get("Count")
        if count is not None and isinstance(count, (int, float)) and count > 32:
            if output_status == "INVALID_PARAMETER":
                reasons.append("[R70] Random Count 초과에서 올바르게 INVALID_PARAMETER 반환")

    # === R71: Random 지원되지 않는 파라미터 최종 확인 ===
    if method_name == "Random":
        unsupported_params = {"BufferOut", "Padding"}
        present_unsupported = unsupported_params & set(args.keys())
        if present_unsupported:
            if output_status == "INVALID_PARAMETER":
                reasons.append("[R71] Random 지원되지 않는 파라미터에서 올바르게 INVALID_PARAMETER 반환")

    # === R72: ActiveDataRemovalMechanism 최종 확인 ===
    inv_name = _get_invoking_name(final_record)
    if method_name == "Set" and inv_name and "DataRemoval" in str(inv_name):
        values = _get_set_values(final_record)
        for v in values:
            if isinstance(v, dict):
                for col_val in v.values():
                    if isinstance(col_val, int) and col_val >= 3:
                        if output_status == "INVALID_PARAMETER":
                            reasons.append("[R72] 지원되지 않는 ActiveDataRemovalMechanism에서 올바르게 INVALID_PARAMETER 반환")

    # === R73: MBRControl DoneOnReset 최종 확인 ===
    if method_name == "Set" and _is_mbrcontrol(invoking_uid):
        values = _get_set_values(final_record)
        modified_cols = _collect_modified_cols(values)
        if MBRCONTROL_COL_DONE_ON_RESET in modified_cols and output_status == "INVALID_PARAMETER":
            reasons.append("[R73] 지원되지 않는 DoneOnReset에서 올바르게 INVALID_PARAMETER 반환")

    # === R74: Admin1 OFS 기본 활성화 확인 ===
    if method_name == "Get" and _is_authority_object(invoking_uid) and output_status == "SUCCESS":
        returned_cols = _get_return_columns(final_record)
        if AUTH_COL_ENABLED in returned_cols:
            col_values = _extract_col_values(final_record)
            if AUTH_COL_ENABLED in col_values:
                enabled_val = bool(col_values[AUTH_COL_ENABLED])
                # Admin1 확인
                if invoking_uid == UID_ADMIN1:
                    if state.locking_sp_activated and invoking_uid not in state.authority_enabled_overrides:
                        if not enabled_val:
                            reasons.append("[R74] Admin1이 OFS에서 비활성화 상태 — 기본값 True 위반")
                            return ("FAIL", reasons)

    # === R75: User1-8 OFS 기본 비활성화 확인 ===
    if method_name == "Get" and _is_authority_object(invoking_uid) and output_status == "SUCCESS":
        returned_cols = _get_return_columns(final_record)
        if AUTH_COL_ENABLED in returned_cols:
            col_values = _extract_col_values(final_record)
            if AUTH_COL_ENABLED in col_values:
                enabled_val = bool(col_values[AUTH_COL_ENABLED])
                if _is_user_authority(invoking_uid):
                    if invoking_uid not in state.authority_enabled_overrides:
                        if enabled_val:
                            reasons.append(f"[R75] User authority가 OFS에서 활성화 상태 — 기본값 False 위반")
                            return ("FAIL", reasons)

    # === R76: Users 클래스 authority 직접 인증 최종 확인 ===
    if method_name == "Authenticate":
        auth_uid = ""
        if "Authority" in args:
            auth_uid = _normalize_uid(str(args["Authority"]))
        elif invoking_uid and _is_authority_object(invoking_uid):
            auth_uid = invoking_uid
        if _is_class_authority(auth_uid):
            if output_status == "INVALID_PARAMETER":
                reasons.append("[R76] 클래스 authority 인증에서 올바르게 INVALID_PARAMETER 반환")

    # === R77: ACE BooleanExpr 최종 확인 ===
    if method_name == "Set" and _is_ace_object(invoking_uid):
        values = _get_set_values(final_record)
        for v in values:
            if isinstance(v, dict):
                for col_val in v.values():
                    if isinstance(col_val, str):
                        if not _is_valid_ace_boolean_expr(col_val):
                            if output_status == "INVALID_PARAMETER":
                                reasons.append("[R77] 지원되지 않는 ACE BooleanExpr에서 올바르게 INVALID_PARAMETER 반환")

    # -----------------------------------------------------------------------
    # 모든 규칙 통과: PASS 판정
    # -----------------------------------------------------------------------
    if not reasons:
        reasons.append("R57-R77 범위 내 위반 없음")

    return ("PASS", reasons)


# ---------------------------------------------------------------------------
# Trajectory 전체 검증 편의 함수
# ---------------------------------------------------------------------------

def verify_trajectory(records: List[dict]) -> Tuple[str, List[str]]:
    """
    전체 trajectory를 검증하여 최종 verdict를 반환한다.

    Args:
        records: trajectory 레코드 리스트 (시간순)

    Returns:
        (verdict, reasons) — verdict는 "PASS" 또는 "FAIL"
    """
    if not records:
        return ("FAIL", ["빈 trajectory"])

    state = ACLLockingState()

    # 마지막 레코드 직전까지 상태 갱신
    for record in records[:-1]:
        state = update_acl_locking(state, record)

    # 마지막 레코드로 상태 갱신 + 최종 판정
    final_record = records[-1]
    state = update_acl_locking(state, final_record)

    return check_final_verdict_acl_locking(state, final_record)
