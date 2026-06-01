# Changed: TCG/Opal 검증용 FSM 신규 생성 (Category 1-2: R01-R14).
# Why: LLM-only 아키텍처의 보조 검증 엔진으로, trajectory를 순차 스캔하여
#      세션/상태코드 규칙 위반 여부를 판정하는 유한 상태 기계.
"""TCG/Opal 프로토콜 준수 검증 FSM — 세션 및 상태코드 규칙 (R01–R14).

FSM 정형화 (2510.26197v1-2 스타일):
    M = (Q, Sigma, delta, q0, F)
    - Q: SessionStatusState dataclass의 모든 가능한 값 조합
    - Sigma: JSON 레코드에서 파싱한 이벤트 (method_name, output_status, invoking_id 등)
    - delta: update_session_status() — 레코드 1개 읽고 상태 갱신
    - q0: SessionStatusState() 기본값 (세션 없음, 인증 없음)
    - F: check_final_verdict_session_status() — 최종 레코드의 응답이 규칙에 부합하는지 판정

핵심 설계 원칙:
    이 FSM은 "올바른 TPer가 어떤 상태코드를 반환해야 하는가"를 추적한다.
    중간 레코드의 (input, output) 쌍에서 프로토콜 상태를 재구성하고,
    최종 레코드에서 output_status가 기대와 일치하는지 판정한다.

    verify_trajectory()에서는 최종 레코드를 제외한 N-1개로 상태를 구성하고,
    최종 레코드의 input으로 기대 상태코드를 결정하여 실제 output_status와 비교한다.

사용법:
    from src.fsm_session_status import verify_trajectory
    verdict, violated, state = verify_trajectory(records)
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# 알려진 UID 상수 — TCG/Opal 스펙에서 정의된 고정 UID
# ---------------------------------------------------------------------------

# SP UID (SPID 파라미터에서 사용)
ADMIN_SP_UID = "0000020500000001"    # AdminSP
LOCKING_SP_UID = "0000020500000002"  # LockingSP

# Authority UID (HostSigningAuthority 파라미터에서 사용)
SID_AUTHORITY_UID = "0000000900000006"       # SID (AdminSP)
ADMIN1_AUTHORITY_UID = "0000000900010001"     # Admin1 (LockingSP)

# C_PIN UID (Invoking ID — 공백 포함 raw 형태)
CPIN_SID_UID = "00 00 00 0B 00 00 00 01"            # C_PIN_SID
CPIN_MSID_UID = "00 00 00 0B 00 00 84 02"            # C_PIN_MSID
CPIN_ADMIN1_LOCKING_UID = "00 00 00 0B 00 03 00 01"  # C_PIN_Admin1 (LockingSP)

# SP 객체 UID (Activate/Revert의 invoking_id)
SP_ADMIN_OBJ_UID = "00 00 02 05 00 00 00 01"   # AdminSP의 SP 객체
SP_LOCKING_OBJ_UID = "00 00 02 05 00 00 00 02"  # LockingSP의 SP 객체

# Session Manager
SESSION_MANAGER_UID = "00 00 00 00 00 00 00 FF"

# Changed: 클래스 권한 UID를 opal_record_builder.py의 canonical 값으로 통일.
# Why: FSM1과 FSM4에서 Admins/Users 클래스 UID가 불일치했음.
#      opal_record_builder.py의 HSA_ADMINS_CLASS="0000000900000005"이 정확한 값.
#      Anybody(0000000900000001)는 개별 authority이므로 클래스가 아님 — R35에서 별도 처리.
CLASS_AUTHORITY_UIDS: Set[str] = {
    "0000000900000005",  # Admins 클래스 (AdminSP/LockingSP)
    "0000000900000004",  # Users 클래스 (LockingSP)
}

# MaxSessions 기본값
DEFAULT_MAX_SESSIONS = 1

# C_PIN UID 접두사에서 파티션(SP) 추출용
# Changed: C_PIN UID의 바이트 4-5가 파티션 ID를 나타냄.
# Why: 00 00 00 0B [00 00] XX XX → 파티션 0000 = AdminSP, 0003 = LockingSP, 8402 = MSID 등.
CPIN_TABLE_PREFIX = "0000000b"  # C_PIN 테이블 UID 접두사 (정규화)

# Authority UID에서 파티션 추출: 00 00 00 09 [00 XX] YY YY
# 파티션 00 = AdminSP, 01 = LockingSP (Admin1-Admin4), 03 = LockingSP (User/기타)
# HSA UID에서 C_PIN UID 매핑을 위한 규칙:
#   HSA 0000000900000006 (SID) → C_PIN 000000000b00000001 (C_PIN_SID)
#   HSA 0000000900010001 (Admin1) → C_PIN 000000000b00030001 (C_PIN_Admin1 in LockingSP)
#   HSA 0000000900030001 (Auth in LockingSP) → C_PIN 000000000b00030001 (같은 파티션)

# Authority UID ↔ C_PIN UID 매핑 (알려진 것만)
# Changed: StartSession에서 인증된 HSA와 C_PIN Set의 invoking_id를 연결.
# Why: PIN이 Set으로 변경되면 해당 authority의 known_pin을 갱신해야 함.
AUTHORITY_TO_CPIN: Dict[str, str] = {
    # HSA UID (공백 없음) → C_PIN invoking_id UID (정규화)
    SID_AUTHORITY_UID: "000000000b00000001",           # SID → C_PIN_SID
    ADMIN1_AUTHORITY_UID: "000000000b00030001",        # Admin1 → C_PIN_Admin1 (LockingSP)
}

# 역방향: C_PIN UID → Authority UID
CPIN_TO_AUTHORITY: Dict[str, str] = {v: k for k, v in AUTHORITY_TO_CPIN.items()}


# ---------------------------------------------------------------------------
# 상태 데이터클래스 — FSM의 Q (상태 공간)
# ---------------------------------------------------------------------------

@dataclass
class SessionStatusState:
    """검증 FSM 상태 — 세션 및 상태코드 규칙 (R01–R14) 추적.

    Changed: trajectory를 순차 스캔하며 갱신되는 검증 컨텍스트.
    Why: 최종 레코드의 기대 상태코드를 결정하기 위해 이전 레코드들의 효과를 누적.
    """

    # --- 세션 상태 (R04, R10, R11, R12) ---
    session_open: bool = False                           # 현재 세션 열림 여부
    session_type: Literal["RW", "RO", "NONE"] = "NONE"  # 현재 세션 유형
    target_sp: str = ""                                  # 현재 세션 대상 SP (SPID)
    write_param: Optional[int] = None                    # StartSession의 Write 값

    # --- 인증 상태 (R02, R03) ---
    authenticated_authority: Optional[str] = None  # 현재 세션에서 인증된 HSA UID (공백 없음)

    # --- PIN 추적 (R03) ---
    # Changed: authority UID별 알려진 PIN.
    # Why: HostChallenge가 올바른 PIN인지 비교하여 R03 판정.
    known_pins: Dict[str, str] = field(default_factory=dict)
    # key: authority UID (HSA, 공백 없음), value: 최신 PIN 값

    # --- MSID PIN (SID 초기 PIN) ---
    msid_pin: Optional[str] = None

    # --- SID PIN 현재값 ---
    sid_pin_current: Optional[str] = None

    # --- Properties 추적 (R01, R06) ---
    properties_queried: bool = False
    max_sessions: int = DEFAULT_MAX_SESSIONS
    max_session_timeout: Optional[int] = None
    max_trans_timeout: Optional[int] = None
    min_session_timeout: Optional[int] = None
    min_trans_timeout: Optional[int] = None

    # --- SP 라이프사이클 (R05) ---
    locking_sp_activated: bool = False

    # --- C_PIN UID → Authority UID 동적 매핑 ---
    # Changed: C_PIN Set을 관찰하여 C_PIN과 Authority의 관계를 동적으로 학습.
    # Why: 정적 매핑에 없는 C_PIN도 Set 직후 StartSession에서 사용되면 매핑 가능.
    cpin_to_authority_dynamic: Dict[str, str] = field(default_factory=dict)

    # --- 성공 작업 기록 (consistency check용) ---
    # Changed: 이전 레코드에서 성공한 작업을 두 수준으로 추적.
    # Why: (1) 정확히 같은 작업이 이전에 SUCCESS → 상태코드 mutation 감지.
    #      (2) 같은 (method, target)이 SUCCESS → 유사 작업의 상태코드 mutation 감지.
    successful_operations: Set[str] = field(default_factory=set)
    # key: "method:invoking_uid:args_hash" 형태

    # Changed: 같은 method+target 조합의 성공 이력 (args 무관).
    # Why: tc16처럼 동일 세션에서 첫 Set이지만, 같은 target에 이전 세션에서
    #      유사한 작업이 성공한 경우를 감지하기 위함.
    successful_method_targets: Set[str] = field(default_factory=set)
    # key: "method:invoking_uid" 형태

    # Changed: 세션별 성공/실패 패턴 추적.
    # Why: 같은 (SP, auth_level)의 이전 세션에서 특정 method가 성공했으면,
    #      같은 컨텍스트의 현재 세션에서도 성공해야 함.
    session_success_context: Set[str] = field(default_factory=set)
    # key: "sp:auth:method:target_table" 형태

    # --- 위반 누적 ---
    violations: List[str] = field(default_factory=list)

    # --- 레코드 카운터 ---
    record_count: int = 0


# ---------------------------------------------------------------------------
# 이벤트 파싱 — Sigma 변환
# ---------------------------------------------------------------------------

def _normalize_uid(uid: Optional[str]) -> str:
    """UID 문자열을 공백 제거 + 소문자로 정규화.

    Changed: "00 00 00 0B 00 00 00 01" → "000000000b00000001".
    Why: 데이터에서 공백 포함/미포함 형태가 혼재.
    """
    if uid is None:
        return ""
    return uid.replace(" ", "").lower()


def _make_operation_key(method: str, inv_uid: str, args_req: dict, args_opt: dict) -> str:
    """작업의 고유 키를 생성 (consistency check용).

    Changed: method + invoking_uid + 핵심 args의 해시를 결합.
    Why: 같은 작업이 이전에 SUCCESS했는지 빠르게 조회하기 위함.
    """
    # Cellblock/Values 정보를 포함하여 동일 작업 식별
    args_sig = ""
    if method in ("Get", "Set"):
        cellblock = args_req.get("Cellblock", "")
        if cellblock:
            args_sig = json.dumps(cellblock, sort_keys=True)
        values = args_opt.get("Values", args_req.get("Values", ""))
        if values:
            args_sig += "|" + json.dumps(values, sort_keys=True)
    return f"{method}:{inv_uid}:{args_sig}"


def _parse_event(record: dict) -> dict:
    """JSON 레코드에서 FSM 이벤트를 추출.

    Changed: input/output에서 method_name, status, invoking_id, args를 추출.
    Why: FSM의 Sigma 알파벳 변환.
    """
    inp = record.get("input", {})
    out = record.get("output", {})

    # DATA_COMMAND (Read/Write — 디스크 I/O)
    data_cmd = inp.get("command", "")
    if data_cmd and "method" not in inp:
        return {
            "method_name": "",
            "data_command": data_cmd,
            "input_status": "",
            "output_status": "",
            "invoking_id_name": "",
            "invoking_id_uid": "",
            "args_required": inp.get("args", {}),
            "args_optional": {},
            "output_return_values": out.get("args", {}).get("result", ""),
            "output_method_name": "",
            "index": record.get("index", 0),
        }

    method_obj = inp.get("method", {})
    method_name = method_obj.get("name", "") if isinstance(method_obj, dict) else str(method_obj)
    method_args = method_obj.get("args", {}) if isinstance(method_obj, dict) else {}

    inv_obj = inp.get("invoking_id", {})
    inv_name = inv_obj.get("name", "") if isinstance(inv_obj, dict) else str(inv_obj)
    inv_uid_raw = inv_obj.get("uid", "") if isinstance(inv_obj, dict) else ""

    input_status = inp.get("status_codes", "")
    output_status = out.get("status_codes", "")
    if isinstance(output_status, dict):
        output_status = output_status.get("Name", output_status.get("name", str(output_status)))

    args_req = {}
    args_opt = {}
    if isinstance(method_args, dict):
        if "required" in method_args or "optional" in method_args:
            args_req = method_args.get("required", {})
            args_opt = method_args.get("optional", {})
        else:
            args_req = method_args
    elif isinstance(method_args, list):
        args_req = {"_list_args": method_args}

    out_method_name = ""
    out_method = out.get("method", {})
    if isinstance(out_method, dict):
        out_method_name = out_method.get("name", "")

    return {
        "method_name": method_name or "",
        "data_command": "",
        "input_status": str(input_status),
        "output_status": str(output_status),
        "invoking_id_name": inv_name or "",
        "invoking_id_uid": _normalize_uid(inv_uid_raw),
        "args_required": args_req if isinstance(args_req, dict) else {},
        "args_optional": args_opt if isinstance(args_opt, dict) else {},
        "output_return_values": out.get("return_values", None),
        "output_method_name": out_method_name,
        "index": record.get("index", 0),
    }


# ---------------------------------------------------------------------------
# delta — 상태 전이 함수
# ---------------------------------------------------------------------------

def update_session_status(state: SessionStatusState, record: dict) -> SessionStatusState:
    """레코드 1개를 처리하고 FSM 상태를 갱신.

    Changed: R01-R14 관련 상태 전이 구현. SUCCESS 응답인 레코드만 상태를 갱신.
    Why: SUCCESS가 아닌 응답은 TPer가 작업을 거부한 것이므로 상태 변경 없음.
         단, 중간 레코드의 상태코드 자체는 검증하지 않음 (최종 레코드만 판정).

    Args:
        state: 현재 FSM 상태
        record: trajectory 레코드 1개

    Returns:
        갱신된 FSM 상태 (새 인스턴스)
    """
    s = copy.deepcopy(state)
    s.record_count += 1

    event = _parse_event(record)
    method = event["method_name"]
    data_cmd = event["data_command"]
    out_status = event["output_status"]
    inv_uid = event["invoking_id_uid"]
    inv_name = event["invoking_id_name"]
    args_req = event["args_required"]
    args_opt = event["args_optional"]
    return_values = event["output_return_values"]
    out_method = event["output_method_name"]

    # --- DATA_COMMAND --- 상태 변경 없음
    if data_cmd:
        return s

    # --- Properties ---
    if method == "Properties":
        s.properties_queried = True
        if out_status == "SUCCESS" and isinstance(return_values, list):
            # Changed: Properties 응답에서 TPer 속성 추출.
            # Why: MaxSessions 등은 R06 판정에 필요.
            for rv in return_values:
                if isinstance(rv, dict):
                    props = rv.get("Properties", rv)
                    if isinstance(props, dict):
                        for key in ("MaxSessions", "MaxSessionTimeout", "MaxTransTimeout",
                                    "MinSessionTimeout", "MinTransTimeout"):
                            if key in props:
                                try:
                                    val = int(props[key])
                                    if key == "MaxSessions":
                                        s.max_sessions = val
                                    elif key == "MaxSessionTimeout":
                                        s.max_session_timeout = val
                                    elif key == "MaxTransTimeout":
                                        s.max_trans_timeout = val
                                    elif key == "MinSessionTimeout":
                                        s.min_session_timeout = val
                                    elif key == "MinTransTimeout":
                                        s.min_trans_timeout = val
                                except (ValueError, TypeError):
                                    pass
            # Changed: SUCCESS인 Properties를 성공 작업으로 기록.
            # Why: consistency check용.
            op_key = _make_operation_key(method, inv_uid, args_req, args_opt)
            s.successful_operations.add(op_key)
            s.successful_method_targets.add(f"{method}:{inv_uid}")
        return s

    # --- StartSession ---
    if method == "StartSession":
        spid = args_req.get("SPID", "")
        write_val = args_req.get("Write", None)
        hsa = args_opt.get("HostSigningAuthority", "")
        host_challenge = args_opt.get("HostChallenge", "")

        if out_status == "SUCCESS" and out_method == "SyncSession":
            # Changed: 세션 열림 성공 — 세션 상태와 인증 정보 갱신.
            # Why: 이후 메서드 호출의 컨텍스트 (세션 유형, 인증 권한) 결정.
            session_type = "RW" if (write_val == 1 or write_val is True) else "RO"

            s.session_open = True
            s.session_type = session_type
            s.target_sp = spid
            s.write_param = write_val if write_val is not None else None

            if hsa:
                s.authenticated_authority = hsa
            else:
                s.authenticated_authority = None

            # Changed: 성공한 인증 → HostChallenge가 올바른 PIN임을 확인.
            # Why: 이 값을 known_pins에 기록하여 이후 R03 검증에 사용.
            if hsa and host_challenge:
                s.known_pins[hsa] = host_challenge
        # 실패한 StartSession은 세션 상태 변경 없음
        return s

    # --- EndSession ---
    if method == "EndSession":
        # Changed: 세션 종료 — 세션 상태 초기화.
        # Why: 세션 닫히면 인증 상태도 무효화.
        s.session_open = False
        s.session_type = "NONE"
        s.target_sp = ""
        s.write_param = None
        s.authenticated_authority = None
        return s

    # --- Get ---
    if method == "Get":
        if out_status == "SUCCESS":
            # Changed: C_PIN_MSID에서 PIN 읽기 추적.
            # Why: MSID PIN = SID의 초기 비밀번호 (OFS 상태).
            cpin_msid_norm = _normalize_uid(CPIN_MSID_UID)
            if inv_uid == cpin_msid_norm:
                pin_val = _extract_pin_from_return_values(return_values)
                if pin_val is not None:
                    s.msid_pin = pin_val
                    if s.sid_pin_current is None:
                        s.sid_pin_current = pin_val
                        s.known_pins[SID_AUTHORITY_UID] = pin_val

            # Changed: 성공 작업 기록 (exact + target level).
            # Why: consistency check 2단계.
            op_key = _make_operation_key(method, inv_uid, args_req, args_opt)
            s.successful_operations.add(op_key)
            s.successful_method_targets.add(f"{method}:{inv_uid}")
            # Changed: 세션 컨텍스트별 성공 기록.
            # Why: 같은 (SP, auth)에서 같은 method+target_table이 성공한 이력.
            if s.target_sp and s.authenticated_authority:
                target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid
                ctx_key = f"{s.target_sp}:{s.authenticated_authority}:{method}:{target_table}"
                s.session_success_context.add(ctx_key)
        return s

    # --- Set ---
    if method == "Set":
        if out_status == "SUCCESS":
            # Changed: C_PIN PIN 변경 추적 + 성공 작업 기록.
            # Why: PIN 변경 → known_pins 갱신 (R03).
            #      성공 작업 기록 → consistency check.
            cpin_sid_norm = _normalize_uid(CPIN_SID_UID)
            cpin_admin1_norm = _normalize_uid(CPIN_ADMIN1_LOCKING_UID)

            if inv_uid == cpin_sid_norm:
                new_pin = _extract_pin_from_set_values(args_opt, args_req)
                if new_pin is not None:
                    s.sid_pin_current = new_pin
                    s.known_pins[SID_AUTHORITY_UID] = new_pin

            elif inv_uid == cpin_admin1_norm:
                new_pin = _extract_pin_from_set_values(args_opt, args_req)
                if new_pin is not None:
                    s.known_pins[ADMIN1_AUTHORITY_UID] = new_pin

            # Changed: 임의의 C_PIN Set → 해당 authority의 PIN 갱신.
            # Why: C_PIN 테이블의 다른 행도 PIN이 설정될 수 있음 (User1 등).
            if inv_uid.startswith(CPIN_TABLE_PREFIX):
                new_pin = _extract_pin_from_set_values(args_opt, args_req)
                if new_pin is not None:
                    auth_uid = CPIN_TO_AUTHORITY.get(inv_uid, None)
                    if auth_uid:
                        s.known_pins[auth_uid] = new_pin
                    else:
                        s.cpin_to_authority_dynamic[inv_uid] = new_pin

            op_key = _make_operation_key(method, inv_uid, args_req, args_opt)
            s.successful_operations.add(op_key)
            s.successful_method_targets.add(f"{method}:{inv_uid}")
            if s.target_sp and s.authenticated_authority:
                target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid
                ctx_key = f"{s.target_sp}:{s.authenticated_authority}:{method}:{target_table}"
                s.session_success_context.add(ctx_key)
        return s

    # --- Activate ---
    if method == "Activate":
        if out_status == "SUCCESS":
            sp_locking_norm = _normalize_uid(SP_LOCKING_OBJ_UID)
            if inv_uid == sp_locking_norm:
                s.locking_sp_activated = True
                # Changed: R52 — Activate 시 SID PIN이 Admin1 C_PIN으로 복사.
                # Why: LockingSP Admin1의 초기 PIN = 현재 SID PIN.
                if s.sid_pin_current:
                    s.known_pins[ADMIN1_AUTHORITY_UID] = s.sid_pin_current

            op_key = _make_operation_key(method, inv_uid, args_req, args_opt)
            s.successful_operations.add(op_key)
            s.successful_method_targets.add(f"{method}:{inv_uid}")
            if s.target_sp and s.authenticated_authority:
                target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid
                ctx_key = f"{s.target_sp}:{s.authenticated_authority}:{method}:{target_table}"
                s.session_success_context.add(ctx_key)
        return s

    # 기타 메서드 (GenKey 등) — 세션 상태 변경 최소
    if out_status == "SUCCESS":
        op_key = _make_operation_key(method, inv_uid, args_req, args_opt)
        s.successful_operations.add(op_key)
        s.successful_method_targets.add(f"{method}:{inv_uid}")
        if s.target_sp and s.authenticated_authority:
            target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid
            ctx_key = f"{s.target_sp}:{s.authenticated_authority}:{method}:{target_table}"
            s.session_success_context.add(ctx_key)

    return s


# ---------------------------------------------------------------------------
# PIN 추출 헬퍼
# ---------------------------------------------------------------------------

def _extract_pin_from_return_values(return_values: Any) -> Optional[str]:
    """Get의 return_values에서 column 3 (PIN) 값 추출.

    Changed: 다양한 return_values 구조 처리.
    Why: [[{"3": "VALUE"}]] 또는 [{"3": "VALUE"}] 등.
    """
    if return_values is None:
        return None
    if isinstance(return_values, list):
        for item in return_values:
            if isinstance(item, list):
                for sub in item:
                    if isinstance(sub, dict) and "3" in sub:
                        return str(sub["3"])
            elif isinstance(item, dict):
                if "3" in item:
                    return str(item["3"])
    if isinstance(return_values, dict) and "3" in return_values:
        return str(return_values["3"])
    return None


def _extract_pin_from_set_values(args_opt: dict, args_req: dict) -> Optional[str]:
    """Set의 Values에서 column 3 (PIN) 값 추출.

    Changed: optional.Values 또는 required.Values에서 추출.
    Why: Set C_PIN의 Values는 [{"3": "NEW_PIN"}] 형태.
    """
    values = args_opt.get("Values", args_req.get("Values", None))
    if values is None:
        return None
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict) and "3" in item:
                return str(item["3"])
    if isinstance(values, dict) and "3" in values:
        return str(values["3"])
    return None


# ---------------------------------------------------------------------------
# ACL 인지 판정 헬퍼 — Set이 성공해야 하는지 판단
# ---------------------------------------------------------------------------

# Changed: Authority 테이블 UID 접두사 (정규화).
# Why: Authority 테이블의 Enabled(column 5) Set은 Admin1이 허용됨.
AUTHORITY_TABLE_PREFIX = "00000009"

# LockingSP에서 Admin1이 Set 가능한 (table_prefix, column_set) 조합
# Changed: 스펙에서 정의된 ACE 규칙 기반.
# Why: Admin1은 Authority.Enabled, C_PIN.PIN, Locking.* 등에 접근 가능.
ADMIN1_ALLOWED_SET_PATTERNS: List[Tuple[str, Optional[Set[str]]]] = [
    # (table_prefix, allowed_columns or None=any)
    (AUTHORITY_TABLE_PREFIX, {"5"}),         # Authority.Enabled
    (CPIN_TABLE_PREFIX, {"3"}),              # C_PIN.PIN
    ("00000802", None),                       # Locking 테이블 — 모든 Set 가능 컬럼
    ("00000803", None),                       # MBRControl 테이블
]

# SID가 AdminSP에서 Set 가능한 패턴
SID_ALLOWED_SET_PATTERNS: List[Tuple[str, Optional[Set[str]]]] = [
    (CPIN_TABLE_PREFIX, {"3"}),              # C_PIN_SID.PIN
]


# Changed: Get이 성공해야 하는지 판단하는 ACL 인지 헬퍼.
# Why: 인증된 세션에서 유효한 테이블의 유효한 컬럼 범위 Get이면 SUCCESS 기대.

# Admin1이 LockingSP에서 Get 가능한 테이블 접두사
ADMIN1_ALLOWED_GET_TABLES: Set[str] = {
    AUTHORITY_TABLE_PREFIX,  # Authority
    CPIN_TABLE_PREFIX,       # C_PIN
    "00000802",              # Locking
    "00000803",              # MBRControl
    "00000801",              # LockingInfo
    "00000806",              # K_AES_256
}

# Anybody가 AdminSP에서 Get 가능한 테이블
ANYBODY_ADMIN_GET_TABLES: Set[str] = {
    CPIN_TABLE_PREFIX,       # C_PIN (MSID PIN만 — column 제한)
}


def _is_get_expected_to_succeed(
    state: SessionStatusState,
    inv_uid: str,
    inv_name: str,
    args_req: dict,
) -> bool:
    """Get이 현재 세션 컨텍스트에서 성공해야 하는지 판단.

    Changed: 세션 유형, 인증 수준, 대상 테이블을 기반으로 판단.
    Why: ACL 규칙에 따라 인증된 authority가 Get을 수행할 수 있는지 확인.

    Returns:
        True: Get이 SUCCESS여야 할 것으로 예상
        False: INVALID_PARAMETER/FAIL이 정당할 수 있음
    """
    if not state.session_open:
        return False

    target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid

    # LockingSP + Admin1 인증
    if state.target_sp == LOCKING_SP_UID and state.authenticated_authority == ADMIN1_AUTHORITY_UID:
        return target_table in ADMIN1_ALLOWED_GET_TABLES

    # LockingSP + 기타 인증된 authority
    if state.target_sp == LOCKING_SP_UID and state.authenticated_authority:
        # 인증된 authority는 기본적으로 Locking/Authority 테이블에 Get 가능
        return target_table in ADMIN1_ALLOWED_GET_TABLES

    # AdminSP + SID 인증
    if state.target_sp == ADMIN_SP_UID and state.authenticated_authority == SID_AUTHORITY_UID:
        return True  # SID는 AdminSP의 모든 객체에 접근 가능

    # AdminSP + Anybody (인증 없음)
    if state.target_sp == ADMIN_SP_UID and state.authenticated_authority is None:
        return target_table in ANYBODY_ADMIN_GET_TABLES

    return False


def _is_set_expected_to_succeed(
    state: SessionStatusState,
    inv_uid: str,
    inv_name: str,
    args_opt: dict,
    args_req: dict,
) -> bool:
    """Set이 현재 세션 컨텍스트에서 성공해야 하는지 판단.

    Changed: 세션 유형, 인증 수준, 대상 테이블/컬럼을 기반으로 판단.
    Why: ACL 규칙에 따라 인증된 authority가 Set을 수행할 수 있는지 확인.
         성공해야 하는 Set이 INVALID_PARAMETER를 반환하면 mutation 가능성 높음.

    Returns:
        True: Set이 SUCCESS여야 할 것으로 예상
        False: INVALID_PARAMETER/FAIL이 정당할 수 있음
    """
    # RO 세션이면 Set 자체가 불가 → INVALID_PARAMETER/NOT_AUTHORIZED 정당
    if state.session_type != "RW":
        return False

    # 세션이 열려 있지 않으면 판단 불가
    if not state.session_open:
        return False

    # Values에서 설정되는 컬럼 목록 추출
    values = args_opt.get("Values", args_req.get("Values", None))
    columns_set: Set[str] = set()
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                columns_set.update(str(k) for k in item.keys())
    elif isinstance(values, dict):
        columns_set.update(str(k) for k in values.keys())

    # 대상 테이블 접두사
    target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid

    # LockingSP + Admin1 인증
    if state.target_sp == LOCKING_SP_UID and state.authenticated_authority == ADMIN1_AUTHORITY_UID:
        for table_prefix, allowed_cols in ADMIN1_ALLOWED_SET_PATTERNS:
            if target_table == table_prefix:
                if allowed_cols is None:
                    return True
                if columns_set and columns_set.issubset(allowed_cols):
                    return True
        return False

    # AdminSP + SID 인증
    if state.target_sp == ADMIN_SP_UID and state.authenticated_authority == SID_AUTHORITY_UID:
        for table_prefix, allowed_cols in SID_ALLOWED_SET_PATTERNS:
            if target_table == table_prefix:
                if allowed_cols is None:
                    return True
                if columns_set and columns_set.issubset(allowed_cols):
                    return True
        return False

    return False


# ---------------------------------------------------------------------------
# 동적 C_PIN → Authority 매핑 해결
# ---------------------------------------------------------------------------

def _resolve_dynamic_cpin_mapping(state: SessionStatusState, hsa: str, host_challenge: str) -> None:
    """StartSession 성공 시 C_PIN ↔ Authority 동적 매핑을 완성.

    Changed: C_PIN Set에서 저장한 PIN이 StartSession의 HostChallenge와 일치하면 매핑.
    Why: 정적 매핑에 없는 authority-CPIN 관계를 런타임에 학습.
    """
    if not hsa or not host_challenge:
        return
    for cpin_uid, pin_val in state.cpin_to_authority_dynamic.items():
        if pin_val == host_challenge:
            # 이 C_PIN의 authority = hsa
            state.known_pins[hsa] = pin_val
            CPIN_TO_AUTHORITY[cpin_uid] = hsa
            AUTHORITY_TO_CPIN[hsa] = cpin_uid
            break


# ---------------------------------------------------------------------------
# F / V — 최종 판정 함수
# ---------------------------------------------------------------------------

def check_final_verdict_session_status(
    state: SessionStatusState,
    final_record: dict,
) -> Tuple[str, List[str]]:
    """최종 레코드의 output_status가 규칙에 부합하는지 판정.

    Changed: state는 최종 레코드를 처리하기 *전*의 상태 (N-1 레코드까지 반영).
    Why: 최종 레코드의 input으로 기대 상태코드를 결정하고, 실제 output_status와 비교.

    Args:
        state: 최종 레코드 직전까지의 FSM 상태
        final_record: trajectory의 마지막 레코드

    Returns:
        (verdict, violated_rules)
        verdict: "pass" | "fail" | "unknown"
        violated_rules: 위반된 규칙 ID 목록
    """
    event = _parse_event(final_record)
    method = event["method_name"]
    data_cmd = event["data_command"]
    out_status = event["output_status"]
    inv_uid = event["invoking_id_uid"]
    inv_name = event["invoking_id_name"]
    args_req = event["args_required"]
    args_opt = event["args_optional"]
    return_values = event["output_return_values"]
    out_method = event["output_method_name"]

    violated: List[str] = list(state.violations)

    # ===================================================================
    # DATA_COMMAND — 이 FSM 범위 밖
    # ===================================================================
    if data_cmd:
        return ("unknown", violated)

    # ===================================================================
    # 공통 consistency check: 이전에 같은/유사 작업이 SUCCESS했는데 지금 실패하면 위반
    # ===================================================================
    op_key = _make_operation_key(method, inv_uid, args_req, args_opt)
    # Changed: 3단계 consistency check.
    # Why: (1) exact match, (2) same method+target, (3) same session context.
    previously_succeeded_exact = op_key in state.successful_operations
    previously_succeeded_target = f"{method}:{inv_uid}" in state.successful_method_targets
    # Changed: 세션 컨텍스트 기반 일관성 — 같은 (SP, auth)에서 같은 method+table 성공 이력.
    # Why: tc16처럼 같은 세션 컨텍스트의 이전 세션에서 유사 작업이 성공한 경우.
    ctx_match = False
    if state.target_sp and state.authenticated_authority:
        target_table = inv_uid[:8] if len(inv_uid) >= 8 else inv_uid
        ctx_key = f"{state.target_sp}:{state.authenticated_authority}:{method}:{target_table}"
        ctx_match = ctx_key in state.session_success_context
    previously_succeeded = previously_succeeded_exact or previously_succeeded_target or ctx_match

    # ===================================================================
    # Properties (R01, R08)
    # ===================================================================
    if method == "Properties":
        if out_status == "SUCCESS":
            # R01: 정상 처리 → SUCCESS는 정당
            return ("pass", violated)
        elif out_status == "INVALID_PARAMETER":
            # Changed: Properties는 기본 호출이면 항상 SUCCESS여야 함.
            # Why: INVALID_PARAMETER는 잘못된 입력이 있을 때만 정당하지만,
            #      표준 Properties 호출에서는 발생하면 안 됨.
            violated.append("R01")
            return ("fail", violated)
        else:
            violated.append("R01")
            return ("fail", violated)

    # ===================================================================
    # StartSession (R01-R07, R10, R12-R14)
    # ===================================================================
    if method == "StartSession":
        spid = args_req.get("SPID", "")
        write_val = args_req.get("Write", None)
        hsa = args_opt.get("HostSigningAuthority", "")
        host_challenge = args_opt.get("HostChallenge", "")
        session_timeout_val = args_opt.get("SessionTimeout", args_req.get("SessionTimeout", None))
        trans_timeout_val = args_opt.get("TransTimeout", args_req.get("TransTimeout", None))

        # --- R07: 클래스 권한을 HSA로 사용 ---
        is_class_authority = hsa in CLASS_AUTHORITY_UIDS
        if is_class_authority:
            if out_status == "INVALID_PARAMETER":
                return ("pass", violated)
            elif out_status == "SUCCESS":
                violated.append("R07")
                return ("fail", violated)
            return ("unknown", violated)

        # --- R13: SessionTimeout 범위 초과 ---
        if session_timeout_val is not None:
            try:
                st_val = int(session_timeout_val)
                out_of_range = False
                if state.max_session_timeout is not None and st_val > state.max_session_timeout:
                    out_of_range = True
                if state.min_session_timeout is not None and st_val < state.min_session_timeout:
                    out_of_range = True
                if out_of_range:
                    if out_status == "INVALID_PARAMETER":
                        return ("pass", violated)
                    elif out_status == "SUCCESS":
                        violated.append("R13")
                        return ("fail", violated)
            except (ValueError, TypeError):
                pass

        # --- R14: TransTimeout 범위 초과 ---
        if trans_timeout_val is not None:
            try:
                tt_val = int(trans_timeout_val)
                out_of_range = False
                if state.max_trans_timeout is not None and tt_val > state.max_trans_timeout:
                    out_of_range = True
                if state.min_trans_timeout is not None and tt_val < state.min_trans_timeout:
                    out_of_range = True
                if out_of_range:
                    if out_status == "INVALID_PARAMETER":
                        return ("pass", violated)
                    elif out_status == "SUCCESS":
                        violated.append("R14")
                        return ("fail", violated)
            except (ValueError, TypeError):
                pass

        # --- R04/R10: 동시 세션 충돌 ---
        # Changed: 현재 state에 같은 SP의 열린 세션이 있는지 확인.
        # Why: state는 최종 레코드 직전 상태이므로, session_open과 target_sp로 확인.
        if state.session_open and state.target_sp == spid:
            existing_type = state.session_type
            requested_type = "RW" if (write_val == 1 or write_val is True) else "RO"

            should_be_busy = False
            if existing_type == "RW":
                should_be_busy = True
            elif existing_type == "RO" and requested_type == "RW":
                should_be_busy = True

            if should_be_busy:
                if out_status == "SP_BUSY":
                    return ("pass", violated)
                elif out_status == "SUCCESS":
                    violated.append("R04")
                    violated.append("R10")
                    return ("fail", violated)

        # --- R03: 비밀번호 불일치 ---
        if hsa and host_challenge:
            known_pin = state.known_pins.get(hsa, None)
            if known_pin is not None:
                if host_challenge != known_pin:
                    # 비밀번호 불일치 → NOT_AUTHORIZED 또는 AUTHORITY_LOCKED_OUT 기대
                    if out_status in ("NOT_AUTHORIZED", "AUTHORITY_LOCKED_OUT"):
                        return ("pass", violated)
                    elif out_status == "SUCCESS":
                        violated.append("R03")
                        return ("fail", violated)
                else:
                    # 비밀번호 일치 → SUCCESS 기대
                    if out_status == "SUCCESS":
                        return ("pass", violated)
                    elif out_status == "NOT_AUTHORIZED":
                        violated.append("R03")
                        return ("fail", violated)

        # --- R05: SP_FROZEN ---
        if out_status == "SP_FROZEN":
            return ("pass", violated)

        # --- R06: NO_SESSIONS_AVAILABLE ---
        if out_status == "NO_SESSIONS_AVAILABLE":
            return ("pass", violated)

        # --- R09: AUTHORITY_LOCKED_OUT ---
        if out_status == "AUTHORITY_LOCKED_OUT":
            return ("pass", violated)

        # --- 기본 판정 ---
        if out_status == "SUCCESS":
            return ("pass", violated)
        elif out_status == "NOT_AUTHORIZED":
            # Changed: PIN을 모르는 경우 NOT_AUTHORIZED를 단독으로 판정하기 어려움.
            # Why: known_pin이 없으면 비밀번호 일치 여부를 알 수 없음.
            if hsa and state.known_pins.get(hsa) is None:
                return ("unknown", violated)
            return ("pass", violated)
        elif out_status == "INVALID_PARAMETER":
            return ("pass", violated)

        return ("unknown", violated)

    # ===================================================================
    # EndSession (R01)
    # ===================================================================
    if method == "EndSession":
        if out_status == "SUCCESS":
            return ("pass", violated)
        violated.append("R01")
        return ("fail", violated)

    # ===================================================================
    # Get (R01, R02, R11 — consistency check + ACL 인지 포함)
    # ===================================================================
    if method == "Get":
        if out_status == "SUCCESS":
            # R01: 정상 처리
            return ("pass", violated)
        elif out_status == "NOT_AUTHORIZED":
            # R02: 인증 미충족. C_PIN_MSID는 Anybody 접근 가능 → NOT_AUTHORIZED면 위반.
            cpin_msid_norm = _normalize_uid(CPIN_MSID_UID)
            if inv_uid == cpin_msid_norm:
                violated.append("R02")
                return ("fail", violated)
            # Changed: 이전에 같은 Get이 SUCCESS했는데 지금 NOT_AUTHORIZED면 위반.
            # Why: 같은 세션 컨텍스트에서 같은 작업이 이전에 성공했으면 인증이 유효.
            if previously_succeeded:
                violated.append("R02")
                return ("fail", violated)
            return ("pass", violated)
        elif out_status in ("INVALID_PARAMETER", "FAIL"):
            # Changed: 이전 성공 기록이 있으면 mutation.
            # Why: 동일 (method, target, args) 또는 (method, target)가 이전에 성공.
            if previously_succeeded:
                violated.append("R01")
                return ("fail", violated)

            # Changed: ACL 인지 — 인증된 세션에서 일반적인 Get이 실패하면 의심.
            # Why: 인증된 RW 세션에서 유효한 테이블/컬럼 Get이 INVALID_PARAMETER면 위반.
            if _is_get_expected_to_succeed(state, inv_uid, inv_name, args_req):
                violated.append("R01")
                return ("fail", violated)

            return ("pass", violated)

        return ("unknown", violated)

    # ===================================================================
    # Set (R01, R02, R08, R11 — consistency check + ACL 인지 포함)
    # ===================================================================
    if method == "Set":
        if out_status == "SUCCESS":
            # R11: RO 세션에서 Set SUCCESS는 위반
            if state.session_type == "RO":
                violated.append("R11")
                return ("fail", violated)
            return ("pass", violated)
        elif out_status == "NOT_AUTHORIZED":
            if previously_succeeded:
                violated.append("R02")
                return ("fail", violated)
            return ("pass", violated)
        elif out_status in ("INVALID_PARAMETER", "FAIL"):
            if previously_succeeded:
                violated.append("R08")
                return ("fail", violated)

            # Changed: ACL 인지 판정 — 인증 수준이 충분하고 파라미터가 유효하면
            #          INVALID_PARAMETER는 정당하지 않음.
            # Why: tc16 — Admin1 인증 RW 세션에서 Authority.Enabled Set이
            #      INVALID_PARAMETER를 반환하면 위반 (스펙상 유효한 작업).
            if _is_set_expected_to_succeed(state, inv_uid, inv_name, args_opt, args_req):
                violated.append("R08")
                return ("fail", violated)

            return ("pass", violated)

        return ("unknown", violated)

    # ===================================================================
    # Activate (R01, R11, consistency check)
    # ===================================================================
    if method == "Activate":
        if out_status == "SUCCESS":
            if state.session_type == "RO":
                violated.append("R11")
                return ("fail", violated)

            # Changed: Activate 대상이 유효한 SP인지 확인.
            # Why: SP 테이블(0x0205)이 아닌 다른 테이블의 객체에 Activate하면 비정상.
            #      tc15에서 "00 00 01 05 00 00 00 04"는 SPTemplates(0x0105)이므로 위반.
            sp_locking_norm = _normalize_uid(SP_LOCKING_OBJ_UID)
            sp_admin_norm = _normalize_uid(SP_ADMIN_OBJ_UID)

            # SP 테이블 접두사: 0x0205 (정규화: "00000205")
            if inv_uid and not inv_uid.startswith("00000205"):
                # Changed: SP 테이블이 아닌 객체에 Activate → 에러여야 하는데 SUCCESS면 위반.
                # Why: Activate는 SP 테이블 객체에만 유효.
                violated.append("R08")
                return ("fail", violated)

            return ("pass", violated)
        elif out_status in ("NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL"):
            if previously_succeeded:
                violated.append("R01")
                return ("fail", violated)
            return ("pass", violated)

        return ("unknown", violated)

    # ===================================================================
    # GenKey (R01, R11)
    # ===================================================================
    if method == "GenKey":
        if out_status == "SUCCESS":
            if state.session_type == "RO":
                violated.append("R11")
                return ("fail", violated)
            return ("pass", violated)
        elif out_status in ("NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL"):
            if previously_succeeded:
                violated.append("R01")
                return ("fail", violated)
            return ("pass", violated)
        return ("unknown", violated)

    # ===================================================================
    # Authenticate (R01, R09)
    # ===================================================================
    if method == "Authenticate":
        if out_status in ("SUCCESS", "INVALID_PARAMETER", "AUTHORITY_LOCKED_OUT", "NOT_AUTHORIZED"):
            return ("pass", violated)
        return ("unknown", violated)

    # ===================================================================
    # 기타 메서드 — 범위 밖
    # ===================================================================
    if out_status == "SUCCESS":
        return ("pass", violated)
    if previously_succeeded and out_status in ("INVALID_PARAMETER", "FAIL", "NOT_AUTHORIZED"):
        violated.append("R01")
        return ("fail", violated)

    return ("unknown", violated)


# ---------------------------------------------------------------------------
# 편의 함수: trajectory 전체 검증
# ---------------------------------------------------------------------------

def verify_trajectory(records: List[dict]) -> Tuple[str, List[str], SessionStatusState]:
    """trajectory를 순차 스캔하여 pass/fail 판정.

    Changed: N-1개 레코드로 상태를 구성한 후, 최종 레코드에서 판정.
    Why: 최종 레코드의 기대 상태코드를 결정하려면 직전까지의 상태가 필요.
         최종 레코드 자체를 update에 포함하면 세션 충돌 오판이 발생.

    Args:
        records: trajectory의 레코드 리스트

    Returns:
        (verdict, violated_rules, final_state)
    """
    if not records:
        return ("unknown", [], SessionStatusState())

    state = SessionStatusState()

    # Changed: 최종 레코드를 제외한 N-1개로 상태 구성.
    # Why: check에서 최종 레코드의 input 컨텍스트를 pre-final 상태와 비교.
    for record in records[:-1]:
        state = update_session_status(state, record)

    # Changed: 동적 C_PIN→Authority 매핑 해결.
    # Why: C_PIN Set으로 PIN을 설정한 후, 다음 StartSession에서 사용되면 매핑 완성.
    final_event = _parse_event(records[-1])
    if final_event["method_name"] == "StartSession":
        hsa = final_event["args_optional"].get("HostSigningAuthority", "")
        hc = final_event["args_optional"].get("HostChallenge", "")
        _resolve_dynamic_cpin_mapping(state, hsa, hc)

    # Changed: 최종 레코드에 대해 판정.
    # Why: state는 최종 레코드 직전 상태이므로, 최종 레코드의 input과 비교 가능.
    verdict, violated = check_final_verdict_session_status(state, records[-1])

    return (verdict, violated, state)


# ---------------------------------------------------------------------------
# 자체 테스트 — public20 데이터 검증
# ---------------------------------------------------------------------------

def _run_public20_test() -> None:
    """public20 데이터 20건에 대해 FSM 판정 결과를 출력."""
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "data", "local", "public20", "public20_input.jsonl")
    label_path = os.path.join(base_dir, "data", "local", "public20", "public20_labels.local.jsonl")

    if not os.path.exists(input_path):
        print(f"데이터 파일 없음: {input_path}")
        return

    label_map: Dict[str, str] = {}
    if os.path.exists(label_path):
        with open(label_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                label_map[obj["sample_id"]] = obj["label"]

    correct = 0
    total = 0
    unknown_count = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            sid = obj["sample_id"]
            data = json.loads(obj["input"])
            records = data["records"]

            verdict, violated, final_state = verify_trajectory(records)
            true_label = label_map.get(sid, "?")

            total += 1
            if verdict == "unknown":
                unknown_count += 1
                match_str = "UNKNOWN"
            elif verdict == true_label:
                correct += 1
                match_str = "OK"
            else:
                match_str = "WRONG"

            last_record = records[-1]
            inp = last_record.get("input", {})
            last_method = inp.get("method", {}).get("name", inp.get("command", "?"))
            last_status = last_record.get("output", {}).get("status_codes", "")

            print(
                f"  {sid:5s}  true={true_label:4s}  fsm={verdict:7s}  "
                f"violated={violated}  last={last_method}({last_status})  "
                f"[{match_str}]"
            )

    print(f"\n결과: {correct}/{total} 정답, {unknown_count}개 unknown")
    decidable = total - unknown_count
    if decidable > 0:
        print(f"판정 가능한 {decidable}건 중 정답률: {correct}/{decidable} = {correct/decidable*100:.1f}%")


if __name__ == "__main__":
    _run_public20_test()
