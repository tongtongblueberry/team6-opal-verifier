# fsm_method_rules.py
# 변경: TCG/Opal 스펙 규칙 R15-R36 (Get/Set/Authenticate) 검증용 FSM 구현
# 목적: 주어진 trajectory의 마지막 레코드 응답이 프로토콜 준수인지 판정
"""TCG/Opal 메서드 규칙 검증 FSM (R15-R36).

카테고리 3: Get 메서드 규칙 (R15-R20)
카테고리 4: Set 메서드 규칙 (R21-R28)
카테고리 5: Authenticate 메서드 규칙 (R29-R36)

이 FSM은 trajectory 생성이 아닌 **검증**용.
주어진 trajectory X = ((c1,r1),...,(cn,rn))를 순차적으로 읽으며 상태를 갱신하고,
마지막 레코드에서 응답 rn의 프로토콜 준수 여부를 판정한다.

핵심 설계 원리:
  1. 이전 레코드에서 SUCCESS로 수행된 동일 조건의 작업이
     마지막 레코드에서 에러로 실패하면 → FAIL (일관성 위반)
  2. 스펙상 반드시 성공해야 하는 조건에서 에러 반환 → FAIL
  3. 스펙상 반드시 실패해야 하는 조건에서 SUCCESS 반환 → FAIL
  4. 에러 상태코드 자체가 정당한 사유 없이 발생 → FAIL

사용법:
    state = MethodRulesState()
    for record in trajectory[:-1]:
        state = update_method_rules(state, record)
    verdict, violations = check_final_verdict_method_rules(state, trajectory[-1])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ========================================================================
# 상수 — TCG/Opal UID 및 SPID 정의 (public20 데이터에서 추출)
# ========================================================================

# SP 식별자 (SPID, 공백 없이 hex 문자열)
ADMIN_SP = "0000020500000001"  # AdminSP SPID
LOCKING_SP = "0000020500000002"  # LockingSP SPID

# Authority UID (HostSigningAuthority 형식, 공백 없음)
HSA_SID = "0000000900000006"  # SID authority
HSA_ADMIN1 = "0000000900010001"  # Admin1 authority (LockingSP)
HSA_USER1 = "0000000900030001"  # User1 authority (LockingSP)
HSA_ANYBODY = "0000000900000001"  # Anybody authority (모든 SP)

# 클래스 authority UID (IsClass=True) — 직접 인증 불가
CLASS_AUTHORITY_UIDS = {
    "0000000900010000",  # Admins 클래스
    "0000000900030000",  # Users 클래스
}

# C_PIN 오브젝트 UID (공백 포함, invoking_id.uid 형식)
CPIN_MSID_UID = "00 00 00 0B 00 00 84 02"  # C_PIN_MSID
CPIN_SID_UID = "00 00 00 0B 00 00 00 01"  # C_PIN_SID
CPIN_ADMIN1_UID = "00 00 00 0B 00 01 00 01"  # C_PIN_Admin1 (LockingSP)
CPIN_USER1_UID = "00 00 00 0B 00 03 00 01"  # C_PIN_User1 (LockingSP)

# SP 오브젝트 UID (invoking_id.uid 형식)
SP_LOCKING_UID = "00 00 02 05 00 00 00 02"  # LockingSP 오브젝트
SP_ADMIN_UID = "00 00 01 05 00 00 00 04"  # AdminSP 오브젝트

# Locking 관련 UID
LOCKING_GLOBAL_UID = "00 00 08 02 00 00 00 01"  # Locking_GlobalRange
LOCKING_RANGE1_UID = "00 00 08 02 00 03 00 01"  # Locking_Range1
LOCKINGINFO_UID = "00 00 08 01 00 00 00 01"  # LockingInfo
MBRCONTROL_UID = "00 00 08 03 00 00 00 01"  # MBRControl

# Authority 오브젝트 UID
AUTHORITY_USER1_UID = "00 00 00 09 00 03 00 01"  # Authority_User1

# K_AES 키 UID
K_AES_256_UID = "00 00 08 06 00 03 00 01"

# 바이트 테이블 이름 (R17, R19, R25, R26)
BYTE_TABLE_NAMES = {"MBR", "DataStore"}

# 바이트 테이블 UID 접두사 — MBR(00 00 08 04), DataStore(00 00 10 01)
BYTE_TABLE_PREFIXES = ["00 00 08 04", "00 00 10 01"]

# C_PIN 컬럼 번호
CPIN_COL_UID = 0
CPIN_COL_PIN = 3

# Authority 컬럼 번호
AUTH_COL_ENABLED = 5

# UID(0번) 컬럼 — 변경 불가 (R28)
UID_COLUMN_KEY = "0"

# 오브젝트별 최대 유효 컬럼 번호 (R85: Cellblock 범위 초과 검사)
MAX_COLUMN_BY_OBJECT: Dict[str, int] = {
    "C_PIN": 7,
    "Authority": 10,
    "Locking": 9,
    "LockingInfo": 9,
    "MBRControl": 3,
    "SP": 7,
}


# ========================================================================
# 상태 클래스
# ========================================================================

@dataclass
class MethodRulesState:
    """Get/Set/Authenticate 규칙(R15-R36) 검증을 위한 상태 변수.

    trajectory를 순차적으로 처리하며 아래 상태를 추적한다:
    - 세션 정보: 어떤 SP에 어떤 authority로 인증했는지
    - 자격 증명: C_PIN 값 변화 추적 (StartSession 인증 검증용)
    - 인증 횟수: MaxAuthentications 초과 검출 (R36)
    - SP 라이프사이클: Activate 여부
    - Authority 활성화 상태: Enabled 컬럼 변경 추적
    - 성공 이력: 이전에 성공한 (오브젝트, 작업, 컬럼범위) 기록
    """

    # --- 세션 상태 ---
    # 현재 활성 세션의 SP (None이면 세션 없음)
    current_sp: Optional[str] = None
    # 현재 세션의 인증된 authority UID (HostSigningAuthority 값, None=Anybody)
    authenticated_authority: Optional[str] = None
    # 현재 세션이 Read-Write인지 (Write=1)
    is_rw_session: bool = False

    # --- 자격 증명 추적 (R31, R32) ---
    # {C_PIN UID(공백 포함) → 현재 PIN 값}
    known_credentials: Dict[str, str] = field(default_factory=dict)

    # --- 인증 횟수 추적 (R36) ---
    auth_count_in_session: int = 0
    # MaxAuthentications (Properties 응답에서 추출, 기본값 5)
    max_authentications: int = 5

    # --- SP 라이프사이클 (R15 관련) ---
    # Activate된 SP 집합 (SPID 문자열)
    activated_sps: Set[str] = field(default_factory=set)

    # --- Authority 활성화 상태 추적 (R33) ---
    # {Authority 오브젝트 UID(공백 포함) → Enabled(bool)}
    authority_enabled: Dict[str, bool] = field(default_factory=dict)

    # --- Properties 수신 여부 ---
    properties_received: bool = False

    # --- 성공 이력 추적 ---
    # 이전에 SUCCESS로 완료된 Get/Set 작업의 서명(fingerprint) 집합
    # 서명: (method_name, obj_uid, sp, auth_level, cellblock_or_values 해시)
    successful_operations: Set[str] = field(default_factory=set)

    # --- GenKey 이력 (Locking 범위별 마지막 GenKey 시점 추적) ---
    # {K_AES UID → GenKey가 수행된 레코드 index}
    genkey_history: Dict[str, int] = field(default_factory=dict)

    # --- 마지막 Write 패턴 (I/O 검증용) ---
    # {LBA → (pattern, record_index, genkey_after_write)}
    last_write_pattern: Dict[str, Tuple[str, int, bool]] = field(default_factory=dict)

    # --- GenKey 이후 여부 플래그 ---
    # 마지막 GenKey 이후 Write 없이 Read하면 Random Data 예상
    genkey_performed_since_last_write: bool = False

    # --- 직전 Get SP 대상 추적 (Activate 대상 일관성 검사) ---
    # 직전 Get으로 라이프사이클을 조회한 SP 오브젝트 UID
    last_get_sp_uid: Optional[str] = None

    # --- 누적 위반 (이전 레코드에서 감지된 것들, 참고용) ---
    prior_violations: List[str] = field(default_factory=list)


# ========================================================================
# UID 유틸리티 함수
# ========================================================================

def _normalize_uid(uid: Optional[str]) -> str:
    """UID 문자열을 공백 없이 소문자로 정규화."""
    if uid is None:
        return ""
    return uid.replace(" ", "").lower()


def _is_byte_table(obj_name: Optional[str], obj_uid: Optional[str]) -> bool:
    """오브젝트가 바이트 테이블인지 판별 (R17, R19, R25, R26)."""
    if obj_name and obj_name in BYTE_TABLE_NAMES:
        return True
    if obj_uid:
        for prefix in BYTE_TABLE_PREFIXES:
            if obj_uid.startswith(prefix):
                return True
    return False


def _is_class_authority(hsa_nospace: str) -> bool:
    """authority UID가 클래스 authority인지 판별 (R30)."""
    return hsa_nospace.lower() in {u.lower() for u in CLASS_AUTHORITY_UIDS}


# ========================================================================
# 레코드 파싱 헬퍼 함수
# ========================================================================

def _get_object_name(record: dict) -> Optional[str]:
    """레코드에서 invoking_id.name 추출."""
    inp = record.get("input", {})
    iid = inp.get("invoking_id", {})
    if isinstance(iid, dict):
        return iid.get("name")
    return None


def _get_object_uid(record: dict) -> Optional[str]:
    """레코드에서 invoking_id.uid 추출."""
    inp = record.get("input", {})
    iid = inp.get("invoking_id", {})
    if isinstance(iid, dict):
        return iid.get("uid")
    return None


def _get_method_name(record: dict) -> Optional[str]:
    """레코드에서 method.name 추출. Read/Write 커맨드도 처리.

    변경: method dict가 비어있으면 command 필드로 폴백.
    이유: Read/Write I/O 커맨드는 method 키가 없고 command 키를 사용.
    """
    inp = record.get("input", {})
    method = inp.get("method", {})
    if isinstance(method, dict):
        name = method.get("name")
        if name is not None:
            return name
    # Read/Write I/O 커맨드 형식: {"input": {"command": "Read", "args": {...}}}
    return inp.get("command")


def _get_method_args(record: dict) -> dict:
    """레코드에서 method.args 추출."""
    inp = record.get("input", {})
    method = inp.get("method", {})
    if isinstance(method, dict):
        args = method.get("args", {})
        if isinstance(args, list):
            return {"_list_args": args}  # Properties의 args는 리스트
        return args if isinstance(args, dict) else {}
    return {}


def _get_output_status(record: dict) -> str:
    """레코드에서 output.status_codes 추출."""
    out = record.get("output", {})
    return out.get("status_codes", "")


def _get_output_return_values(record: dict) -> Any:
    """레코드에서 output.return_values 추출."""
    out = record.get("output", {})
    return out.get("return_values")


def _get_cellblock(args: dict) -> Optional[List[dict]]:
    """args에서 Cellblock 파라미터 추출."""
    req = args.get("required", {})
    if isinstance(req, dict):
        cb = req.get("Cellblock")
        if isinstance(cb, list):
            return cb
    return None


def _get_cellblock_range(cellblock: List[dict]) -> Tuple[Optional[int], Optional[int]]:
    """Cellblock에서 startColumn, endColumn 추출."""
    start = None
    end = None
    for item in cellblock:
        if isinstance(item, dict):
            if "startColumn" in item:
                start = item["startColumn"]
            if "endColumn" in item:
                end = item["endColumn"]
    return start, end


def _cellblock_has_row_or_table_values(cellblock: List[dict]) -> bool:
    """Cellblock에 row/table 관련 파라미터가 있는지 확인 (R16)."""
    for item in cellblock:
        if isinstance(item, dict):
            for key in item:
                if key in ("startRow", "endRow", "Where", "where",
                           "startTable", "endTable"):
                    return True
    return False


def _cellblock_has_column_values(cellblock: List[dict]) -> bool:
    """Cellblock에 column 파라미터가 있는지 확인 (R17)."""
    for item in cellblock:
        if isinstance(item, dict):
            if "startColumn" in item or "endColumn" in item:
                return True
    return False


def _get_set_values(args: dict) -> Optional[List[dict]]:
    """Set 메서드의 Values 파라미터 추출."""
    opt = args.get("optional", {})
    if isinstance(opt, dict):
        vals = opt.get("Values")
        if isinstance(vals, list):
            return vals
    return None


def _get_where_param(args: dict) -> Any:
    """Set 메서드의 Where 파라미터 추출."""
    opt = args.get("optional", {})
    if isinstance(opt, dict):
        w = opt.get("Where")
        if w is not None:
            return w
    req = args.get("required", {})
    if isinstance(req, dict):
        return req.get("Where")
    return None


def _has_duplicate_columns(values: List[dict]) -> bool:
    """Values 리스트에 중복 컬럼이 있는지 확인 (R22)."""
    seen: Set[str] = set()
    for val_dict in values:
        if isinstance(val_dict, dict):
            for col_key in val_dict:
                if col_key in seen:
                    return True
                seen.add(col_key)
    return False


def _get_column_keys(values: List[dict]) -> List[str]:
    """Values에서 컬럼 키 목록 추출."""
    cols = []
    for val_dict in values:
        if isinstance(val_dict, dict):
            cols.extend(val_dict.keys())
    return cols


def _values_has_uid_column(values: List[dict]) -> bool:
    """Values에 UID 컬럼(0번) 변경 시도가 있는지 확인 (R28)."""
    for val_dict in values:
        if isinstance(val_dict, dict):
            if UID_COLUMN_KEY in val_dict or 0 in val_dict:
                return True
    return False


def _is_values_bytes_type(values: List[dict]) -> bool:
    """Values가 Bytes 타입인지 판별 (R25, R26).

    현재 데이터에서는 모든 Set이 RowValues(컬럼번호-값 쌍) 형식.
    """
    if len(values) == 1 and isinstance(values[0], (str, bytes)):
        return True
    return False


def _make_operation_fingerprint(method: str, obj_uid: Optional[str],
                                sp: Optional[str], auth: Optional[str],
                                detail: str) -> str:
    """작업 서명(fingerprint) 생성 — 동일 조건 작업 식별용."""
    # auth 수준을 정규화 (같은 authority면 같은 fingerprint)
    auth_norm = auth.lower() if auth else "anybody"
    return f"{method}|{obj_uid}|{sp}|{auth_norm}|{detail}"


def _check_column_order(return_values: Any) -> bool:
    """반환값의 컬럼 순서가 올바른지 확인 (R20).

    Column table 순서 = 컬럼 번호 오름차순이어야 함.
    """
    if not isinstance(return_values, list):
        return True

    for item in return_values:
        if isinstance(item, list):
            prev_col = -1
            for cell in item:
                if isinstance(cell, dict):
                    for key in cell:
                        try:
                            col_num = int(key)
                            if col_num < prev_col:
                                return False  # 순서 위반
                            prev_col = col_num
                        except (ValueError, TypeError):
                            pass
    return True


def _return_values_contain_restricted_cols(return_values: Any,
                                           restricted_cols: List[int]) -> bool:
    """반환값에 제한된 컬럼이 포함되어 있는지 확인 (R18)."""
    restricted_keys = {str(c) for c in restricted_cols}
    if isinstance(return_values, list):
        for item in return_values:
            if isinstance(item, list):
                for cell in item:
                    if isinstance(cell, dict):
                        for key in cell:
                            if str(key) in restricted_keys:
                                return True
            elif isinstance(item, dict):
                for key in item:
                    if str(key) in restricted_keys:
                        return True
    return False


# ========================================================================
# Authority/C_PIN 매핑
# ========================================================================

# HostSigningAuthority UID → C_PIN UID 매핑
# Authority 오브젝트와 C_PIN 오브젝트의 UID 관계:
#   Authority 00 00 00 09 XX XX XX XX → C_PIN 00 00 00 0B XX XX XX XX
#   (바이트 4가 09 → 0B로 변환)
HSA_TO_CPIN: Dict[str, str] = {
    _normalize_uid(HSA_SID): CPIN_SID_UID,          # SID → C_PIN_SID
    _normalize_uid(HSA_ADMIN1): CPIN_ADMIN1_UID,     # Admin1 → C_PIN_Admin1
    _normalize_uid(HSA_USER1): CPIN_USER1_UID,       # User1 → C_PIN_User1
}


def _hsa_to_cpin_uid(hsa: str) -> Optional[str]:
    """HostSigningAuthority UID → C_PIN UID 매핑."""
    norm = _normalize_uid(hsa)
    result = HSA_TO_CPIN.get(norm)
    if result:
        return result
    # 일반 매핑: Authority 00 00 00 09 → C_PIN 00 00 00 0B
    if len(norm) == 16 and norm[:8] == "00000009":
        cpin_norm = "0000000b" + norm[8:]
        return " ".join(cpin_norm[i:i+2] for i in range(0, 16, 2))
    return None


def _is_valid_authority_uid(norm_uid: str) -> bool:
    """Authority UID가 유효한(존재하는) authority인지 판별 (R29)."""
    known = {
        _normalize_uid(HSA_SID),
        _normalize_uid(HSA_ADMIN1),
        _normalize_uid(HSA_USER1),
        _normalize_uid(HSA_ANYBODY),
        "0000000900010002",  # Admin2
        "0000000900010003",  # Admin3
        "0000000900010004",  # Admin4
        "0000000900030002",  # User2
        "0000000900030003",  # User3
        "0000000900030004",  # User4
        "0000000900030005",  # User5
        "0000000900030006",  # User6
        "0000000900030007",  # User7
        "0000000900030008",  # User8
        "0000000900010000",  # Admins (클래스)
        "0000000900030000",  # Users (클래스)
    }
    return norm_uid in known


# ========================================================================
# 상태 갱신 함수
# ========================================================================

def update_method_rules(state: MethodRulesState, record: dict) -> MethodRulesState:
    """하나의 레코드를 처리하여 상태를 갱신한다.

    최종 레코드 이전의 모든 레코드를 순차적으로 처리.
    세션/자격증명/SP활성화/authority상태/성공이력을 추적.
    """
    # 변경: 원본 상태를 보존하기 위해 복사
    ns = MethodRulesState(
        current_sp=state.current_sp,
        authenticated_authority=state.authenticated_authority,
        is_rw_session=state.is_rw_session,
        known_credentials=dict(state.known_credentials),
        auth_count_in_session=state.auth_count_in_session,
        max_authentications=state.max_authentications,
        activated_sps=set(state.activated_sps),
        authority_enabled=dict(state.authority_enabled),
        properties_received=state.properties_received,
        successful_operations=set(state.successful_operations),
        genkey_history=dict(state.genkey_history),
        last_write_pattern=dict(state.last_write_pattern),
        genkey_performed_since_last_write=state.genkey_performed_since_last_write,
        last_get_sp_uid=state.last_get_sp_uid,
        prior_violations=list(state.prior_violations),
    )

    method_name = _get_method_name(record)
    output_status = _get_output_status(record)
    is_success = (output_status == "SUCCESS")

    # --- Properties ---
    if method_name == "Properties":
        ns.properties_received = True
        if is_success:
            rv = _get_output_return_values(record)
            if isinstance(rv, list):
                for item in rv:
                    if isinstance(item, dict) and "Properties" in item:
                        props = item["Properties"]
                        if isinstance(props, dict):
                            ma = props.get("MaxAuthentications")
                            if ma is not None:
                                ns.max_authentications = int(ma)

    # --- StartSession ---
    elif method_name == "StartSession":
        if is_success:
            args = _get_method_args(record)
            req = args.get("required", {})
            opt = args.get("optional", {})
            spid = req.get("SPID", "")
            write = req.get("Write", 0)
            hsa = opt.get("HostSigningAuthority")
            hc = opt.get("HostChallenge")

            ns.current_sp = spid
            ns.is_rw_session = (write == 1 or write is True)
            ns.authenticated_authority = hsa
            ns.auth_count_in_session = 1 if hsa else 0

            # 인증 성공 시 PIN 값 기록
            if hsa and hc:
                cpin_uid = _hsa_to_cpin_uid(hsa)
                if cpin_uid:
                    ns.known_credentials[cpin_uid] = str(hc)

    # --- EndSession ---
    elif method_name == "EndSession":
        ns.current_sp = None
        ns.authenticated_authority = None
        ns.is_rw_session = False
        ns.auth_count_in_session = 0

    # --- Authenticate (세션 내 추가 인증) ---
    elif method_name == "Authenticate":
        if is_success:
            ns.auth_count_in_session += 1
            rv = _get_output_return_values(record)
            if rv is True or rv == [True] or rv == 1:
                args = _get_method_args(record)
                req = args.get("required", {})
                authority = req.get("Authority")
                if authority:
                    ns.authenticated_authority = authority

    # --- Set (성공 시 상태 변경 추적) ---
    elif method_name == "Set" and is_success:
        obj_name = _get_object_name(record)
        obj_uid = _get_object_uid(record)
        args = _get_method_args(record)
        values = _get_set_values(args)

        if values:
            # C_PIN Set → PIN 값 갱신
            if obj_name == "C_PIN" and obj_uid:
                for val_dict in values:
                    if isinstance(val_dict, dict):
                        pin_val = val_dict.get("3") or val_dict.get(3)
                        if pin_val is not None:
                            ns.known_credentials[obj_uid] = str(pin_val)

            # Authority Set → Enabled 상태 갱신
            if obj_name == "Authority" and obj_uid:
                for val_dict in values:
                    if isinstance(val_dict, dict):
                        enabled_val = val_dict.get("5") or val_dict.get(5)
                        if enabled_val is not None:
                            ns.authority_enabled[obj_uid] = bool(enabled_val)

        # 성공 이력 기록
        fp = _make_operation_fingerprint(
            "Set", obj_uid, ns.current_sp, ns.authenticated_authority,
            str(sorted(_get_column_keys(values))) if values else "noval"
        )
        ns.successful_operations.add(fp)

    # --- Activate (성공 시 SP 활성화) ---
    elif method_name == "Activate" and is_success:
        obj_uid = _get_object_uid(record)
        if obj_uid:
            norm = _normalize_uid(obj_uid)
            if norm == _normalize_uid(SP_LOCKING_UID):
                ns.activated_sps.add(LOCKING_SP)
            elif norm == _normalize_uid(SP_ADMIN_UID):
                ns.activated_sps.add(ADMIN_SP)
            else:
                ns.activated_sps.add(norm)

    # --- GenKey (키 재생성 추적) ---
    elif method_name == "GenKey" and is_success:
        obj_uid = _get_object_uid(record)
        if obj_uid:
            record_idx = record.get("index", 0)
            ns.genkey_history[obj_uid] = record_idx
            ns.genkey_performed_since_last_write = True

    # --- Write I/O 커맨드 ---
    elif method_name == "Write":
        inp = record.get("input", {})
        lba = inp.get("args", {}).get("LBA", "")
        pattern = inp.get("args", {}).get("pattern", "")
        record_idx = record.get("index", 0)
        ns.last_write_pattern[lba] = (pattern, record_idx, False)
        ns.genkey_performed_since_last_write = False

    # --- Get (성공 시 값 학습 + 이력 기록) ---
    elif method_name == "Get" and is_success:
        obj_name = _get_object_name(record)
        obj_uid = _get_object_uid(record)
        rv = _get_output_return_values(record)

        # SP Get → 라이프사이클 조회 SP 기록 (Activate 일관성 검사용)
        if obj_name == "SP" and obj_uid:
            ns.last_get_sp_uid = obj_uid

        # C_PIN Get → PIN 값 학습 (MSID 등)
        if obj_name == "C_PIN" and rv and obj_uid:
            if isinstance(rv, list) and len(rv) > 0:
                row = rv[0] if isinstance(rv[0], list) else rv
                for cell in row:
                    if isinstance(cell, dict):
                        pin_val = cell.get("3") or cell.get(3)
                        if pin_val is not None:
                            ns.known_credentials[obj_uid] = str(pin_val)

        # 성공 이력 기록
        args = _get_method_args(record)
        cellblock = _get_cellblock(args)
        cb_detail = str(cellblock) if cellblock else "nocb"
        fp = _make_operation_fingerprint(
            "Get", obj_uid, ns.current_sp, ns.authenticated_authority, cb_detail
        )
        ns.successful_operations.add(fp)

    return ns


# ========================================================================
# 최종 판정 함수
# ========================================================================

def check_final_verdict_method_rules(
    state: MethodRulesState,
    final_record: dict
) -> Tuple[str, List[str]]:
    """마지막 레코드의 응답이 프로토콜 준수인지 판정한다.

    반환: (verdict, violated_rules)
        verdict: 'pass' | 'fail' | 'unknown'
        violated_rules: 위반된 규칙 ID 목록
    """
    method_name = _get_method_name(final_record)
    output_status = _get_output_status(final_record)
    args = _get_method_args(final_record)
    obj_name = _get_object_name(final_record)
    obj_uid = _get_object_uid(final_record)
    return_values = _get_output_return_values(final_record)

    violations: List[str] = []

    if method_name == "Get":
        violations = _check_get_rules(state, final_record, obj_name, obj_uid,
                                      args, output_status, return_values)
    elif method_name == "Set":
        violations = _check_set_rules(state, final_record, obj_name, obj_uid,
                                      args, output_status, return_values)
    elif method_name == "Authenticate":
        violations = _check_authenticate_rules(state, final_record, obj_name,
                                               obj_uid, args, output_status,
                                               return_values)
    elif method_name == "StartSession":
        violations = _check_start_session_auth_rules(state, final_record, args,
                                                     output_status, return_values)
    elif method_name == "Properties":
        violations = _check_properties_rules(state, final_record, args,
                                             output_status, return_values)
    elif method_name == "Activate":
        violations = _check_activate_rules(state, final_record, obj_name, obj_uid,
                                           args, output_status)
    elif method_name == "Read":
        violations = _check_read_io_rules(state, final_record)
    else:
        return ("unknown", [])

    if violations:
        return ("fail", violations)
    return ("pass", [])


# ========================================================================
# Get 규칙 검사 (R15-R20)
# ========================================================================

def _check_get_rules(
    state: MethodRulesState,
    record: dict,
    obj_name: Optional[str],
    obj_uid: Optional[str],
    args: dict,
    output_status: str,
    return_values: Any
) -> List[str]:
    """Get 메서드의 R15-R20 규칙 위반을 검사한다."""
    violations: List[str] = []
    cellblock = _get_cellblock(args)
    is_byte = _is_byte_table(obj_name, obj_uid)

    # --- 기대 결과 계산: 이 Get은 성공해야 하는가, 실패해야 하는가? ---
    expected_error = False  # True이면 에러 상태코드가 정당
    error_reasons: List[str] = []

    # R15: 존재하지 않는 오브젝트
    if obj_name is None and obj_uid is None:
        expected_error = True
        error_reasons.append("R15")

    # R16: Object.Get에서 Cellblock에 row/table 값
    if cellblock and not is_byte and _cellblock_has_row_or_table_values(cellblock):
        expected_error = True
        error_reasons.append("R16")

    # R17: Byte table Get에서 column 값
    if cellblock and is_byte and _cellblock_has_column_values(cellblock):
        expected_error = True
        error_reasons.append("R17")

    # R85: Cellblock 범위 초과
    if cellblock and obj_name:
        max_col = MAX_COLUMN_BY_OBJECT.get(obj_name)
        if max_col is not None:
            start_col, end_col = _get_cellblock_range(cellblock)
            if (start_col is not None and start_col > max_col) or \
               (end_col is not None and end_col > max_col):
                expected_error = True
                error_reasons.append("R85")

    # --- 정방향 검사: 에러 조건인데 SUCCESS → 위반 ---
    if expected_error and output_status == "SUCCESS":
        violations.extend(error_reasons)

    # --- 역방향 검사: 에러 사유 없는데 에러 반환 → 위반 ---
    if not expected_error and output_status in ("FAIL", "INVALID_PARAMETER", "NOT_AUTHORIZED"):
        # 동일 조건으로 이전에 성공한 적 있는지 확인 (일관성 검사)
        cb_detail = str(cellblock) if cellblock else "nocb"
        fp = _make_operation_fingerprint(
            "Get", obj_uid, state.current_sp, state.authenticated_authority, cb_detail
        )

        if fp in state.successful_operations:
            # 이전에 같은 조건으로 성공했는데 이제 실패 → 일관성 위반
            if output_status == "NOT_AUTHORIZED":
                violations.append("R18")  # 이전에 접근 가능했는데 이제 NOT_AUTHORIZED
            elif output_status == "INVALID_PARAMETER":
                violations.append("R15")  # 이전에 성공했는데 INVALID_PARAMETER
            elif output_status == "FAIL":
                violations.append("R15")  # 이전에 성공했는데 FAIL
        else:
            # 이전 이력이 없는 경우 — ACL/권한 기반 추론
            if output_status == "NOT_AUTHORIZED":
                # Anybody 세션에서 C_PIN_MSID Get → 반드시 성공 (ACE 허용)
                if state.authenticated_authority is None:
                    if obj_name == "C_PIN" and obj_uid:
                        norm = _normalize_uid(obj_uid)
                        if norm == _normalize_uid(CPIN_MSID_UID):
                            violations.append("R18")  # MSID는 Anybody 접근 가능
                # 인증된 authority가 해당 오브젝트 접근 가능한데 NOT_AUTHORIZED
                if state.authenticated_authority and _authority_should_access(
                    state, obj_name, obj_uid, "Get"
                ):
                    violations.append("R18")

            if output_status in ("FAIL", "INVALID_PARAMETER"):
                # 유효한 오브젝트, 유효한 Cellblock인데 에러
                if obj_name and obj_uid and not expected_error:
                    # Admin1이 LockingSP의 유효한 오브젝트에 접근
                    if state.authenticated_authority and _authority_should_access(
                        state, obj_name, obj_uid, "Get"
                    ):
                        violations.append("R15")  # 유효한 접근인데 에러

    # --- R18: 권한 없는 컬럼이 결과에 포함 ---
    if output_status == "SUCCESS" and return_values:
        # C_PIN_SID: SID도 PIN(col 3) 못 읽음
        if obj_name == "C_PIN" and obj_uid:
            norm = _normalize_uid(obj_uid)
            if norm == _normalize_uid(CPIN_SID_UID):
                if _return_values_contain_restricted_cols(return_values, [CPIN_COL_PIN]):
                    violations.append("R18")

    # --- R19: Byte table, ACL 미충족인데 데이터 반환 ---
    if is_byte and output_status == "SUCCESS" and state.authenticated_authority is None:
        if return_values and return_values != [] and return_values != [[]]:
            violations.append("R19")

    # --- R20: 컬럼 순서 위반 ---
    if output_status == "SUCCESS" and return_values:
        if not _check_column_order(return_values):
            violations.append("R20")

    return violations


# ========================================================================
# Set 규칙 검사 (R21-R28)
# ========================================================================

def _check_set_rules(
    state: MethodRulesState,
    record: dict,
    obj_name: Optional[str],
    obj_uid: Optional[str],
    args: dict,
    output_status: str,
    return_values: Any
) -> List[str]:
    """Set 메서드의 R21-R28 규칙 위반을 검사한다."""
    violations: List[str] = []
    values = _get_set_values(args)
    where_param = _get_where_param(args)
    is_byte = _is_byte_table(obj_name, obj_uid)

    # --- 기대 결과 계산 ---
    expected_error = False
    error_reasons: List[str] = []

    # R22: 동일 컬럼 중복
    if values and _has_duplicate_columns(values):
        expected_error = True
        error_reasons.append("R22")

    # R23: Object.Set에 Where 파라미터
    if where_param is not None and not is_byte and obj_uid:
        expected_error = True
        error_reasons.append("R23")

    # R25: Object table Set에서 Bytes 타입 Values
    if values and not is_byte and _is_values_bytes_type(values):
        expected_error = True
        error_reasons.append("R25")

    # R26: Byte table Set에서 RowValues 타입 Values
    if values and is_byte and not _is_values_bytes_type(values):
        expected_error = True
        error_reasons.append("R26")

    # R28: UID 컬럼 변경 시도
    if values and _values_has_uid_column(values):
        expected_error = True
        error_reasons.append("R28")

    # R21: ACL 미충족 (Anybody 세션에서 Set 시도)
    if state.authenticated_authority is None:
        expected_error = True
        error_reasons.append("R21")

    # --- 정방향: 에러 조건인데 SUCCESS → 위반 ---
    if expected_error and output_status == "SUCCESS":
        violations.extend(error_reasons)

    # --- 역방향: 에러 사유 없는데 에러 반환 → 위반 ---
    if not expected_error and output_status in ("FAIL", "INVALID_PARAMETER", "NOT_AUTHORIZED"):
        # 이전 성공 이력 확인
        val_detail = str(sorted(_get_column_keys(values))) if values else "noval"
        fp = _make_operation_fingerprint(
            "Set", obj_uid, state.current_sp, state.authenticated_authority, val_detail
        )

        if fp in state.successful_operations:
            # 이전에 동일 조건으로 성공 → 일관성 위반
            if output_status == "NOT_AUTHORIZED":
                violations.append("R21")
            elif output_status == "INVALID_PARAMETER":
                violations.append("R22")
            elif output_status == "FAIL":
                violations.append("R21")
        else:
            # 이전 이력 없음 — 권한 기반 추론
            if output_status == "NOT_AUTHORIZED":
                if state.authenticated_authority and _authority_should_access(
                    state, obj_name, obj_uid, "Set"
                ):
                    violations.append("R21")

            if output_status == "INVALID_PARAMETER":
                # 유효한 조건인데 INVALID_PARAMETER
                if state.authenticated_authority and values and not expected_error:
                    if _authority_should_access(state, obj_name, obj_uid, "Set"):
                        violations.append("R22")  # 컬럼 관련 에러

    # --- R24: Table.Set에서 Where 없이 object table → 에러 ---
    # (현재 데이터에서 Table.Set은 개별 UID로 접근하므로 해당 없음)

    # --- R27: Values 없이 Set → SUCCESS ---
    if (values is None or len(values) == 0) and output_status != "SUCCESS":
        if state.authenticated_authority and not expected_error:
            # Values 없는 Set은 SUCCESS 예상
            pass  # 보수적: 다른 사유가 있을 수 있음

    return violations


# ========================================================================
# Authenticate 규칙 검사 (R29-R36)
# ========================================================================

def _check_authenticate_rules(
    state: MethodRulesState,
    record: dict,
    obj_name: Optional[str],
    obj_uid: Optional[str],
    args: dict,
    output_status: str,
    return_values: Any
) -> List[str]:
    """Authenticate 메서드의 R29-R36 규칙 위반을 검사한다."""
    violations: List[str] = []

    req = args.get("required", {})
    authority_uid = req.get("Authority", "")
    proof = req.get("Proof") or req.get("Challenge") or ""
    auth_result = _parse_authenticate_result(return_values)

    # R29: 존재하지 않는 authority → INVALID_PARAMETER
    if authority_uid:
        norm = _normalize_uid(authority_uid)
        if not _is_valid_authority_uid(norm):
            if output_status != "INVALID_PARAMETER":
                violations.append("R29")
            return violations

    # R30: 클래스 authority → INVALID_PARAMETER
    if authority_uid:
        norm = _normalize_uid(authority_uid)
        if _is_class_authority(norm):
            if output_status != "INVALID_PARAMETER":
                violations.append("R30")
            return violations

    # R35: Anybody → 항상 SUCCESS/True
    if authority_uid:
        norm = _normalize_uid(authority_uid)
        if norm == _normalize_uid(HSA_ANYBODY):
            if output_status != "SUCCESS" or auth_result is not True:
                violations.append("R35")
            return violations

    # R36: MaxAuth 초과 → SUCCESS/False
    if state.auth_count_in_session >= state.max_authentications:
        if output_status == "SUCCESS" and auth_result is True:
            violations.append("R36")
        return violations

    # R33: 비활성 authority → SUCCESS/False
    if authority_uid and obj_uid:
        if obj_uid in state.authority_enabled:
            if not state.authority_enabled[obj_uid]:
                if output_status == "SUCCESS" and auth_result is True:
                    violations.append("R33")
                return violations

    # R34: Exchange authority → SUCCESS/False
    # (현재 데이터에서 Exchange authority는 거의 없으므로 보수적으로 처리)

    # R31/R32: 올바른/틀린 비밀번호
    if authority_uid and proof:
        cpin_uid = _authority_to_cpin_uid(authority_uid)
        if cpin_uid and cpin_uid in state.known_credentials:
            stored = state.known_credentials[cpin_uid]
            if str(proof) == str(stored):
                # R31: 맞는 PW → SUCCESS/True 예상
                if output_status == "SUCCESS" and auth_result is False:
                    violations.append("R31")
                elif output_status != "SUCCESS":
                    violations.append("R31")
            else:
                # R32: 틀린 PW → SUCCESS/False 예상
                if output_status == "SUCCESS" and auth_result is True:
                    violations.append("R32")

    return violations


def _check_start_session_auth_rules(
    state: MethodRulesState,
    record: dict,
    args: dict,
    output_status: str,
    return_values: Any
) -> List[str]:
    """StartSession의 인증 관련 규칙 검사 (R29-R36 중 해당 항목)."""
    violations: List[str] = []

    req = args.get("required", {})
    opt = args.get("optional", {})
    hsa = opt.get("HostSigningAuthority")
    hc = opt.get("HostChallenge")
    spid = req.get("SPID", "")

    # 인증 없는 StartSession (Anybody) — R35 적용
    if hsa is None:
        # Anybody 세션은 대부분 SUCCESS
        return violations

    norm_hsa = _normalize_uid(hsa)

    # R29: 존재하지 않는 authority
    if not _is_valid_authority_uid(norm_hsa):
        if output_status == "SUCCESS":
            violations.append("R29")
        return violations

    # R30: 클래스 authority → INVALID_PARAMETER
    if _is_class_authority(norm_hsa):
        if output_status != "INVALID_PARAMETER":
            violations.append("R30")
        return violations

    # R33: 비활성 authority
    # User1은 LockingSP에서 기본 비활성 (OFS)
    if norm_hsa == _normalize_uid(HSA_USER1) and spid == LOCKING_SP:
        # authority_enabled에서 확인
        if AUTHORITY_USER1_UID in state.authority_enabled:
            if not state.authority_enabled[AUTHORITY_USER1_UID]:
                # 비활성인데 SUCCESS → 위반 (R33)
                if output_status == "SUCCESS":
                    violations.append("R33")
                return violations
            # 활성화됨 — 계속 진행
        else:
            # 기록 없음 → OFS 기본값(False) 적용
            if output_status == "SUCCESS":
                violations.append("R33")
            return violations

    # R31/R32: 비밀번호 올바른/틀린 경우
    if hc:
        cpin_uid = _hsa_to_cpin_uid(hsa)
        if cpin_uid and cpin_uid in state.known_credentials:
            stored = state.known_credentials[cpin_uid]
            if str(hc) == str(stored):
                # R31: 맞는 PW → SUCCESS 예상
                if output_status in ("NOT_AUTHORIZED",):
                    violations.append("R31")
            else:
                # R32: 틀린 PW → NOT_AUTHORIZED 예상
                if output_status == "SUCCESS":
                    violations.append("R32")

    return violations


# ========================================================================
# 권한 접근 추론 헬퍼
# ========================================================================

def _authority_should_access(state: MethodRulesState, obj_name: Optional[str],
                             obj_uid: Optional[str], operation: str) -> bool:
    """현재 인증된 authority가 해당 오브젝트에 접근 가능해야 하는지 추론.

    보수적 추론: 확실히 접근 가능한 경우만 True 반환.
    """
    auth = state.authenticated_authority
    if auth is None:
        return False

    norm_auth = _normalize_uid(auth)
    sp = state.current_sp

    # SID는 AdminSP의 모든 오브젝트에 접근 가능
    if norm_auth == _normalize_uid(HSA_SID) and sp == ADMIN_SP:
        return True

    # Admin1은 LockingSP의 대부분 오브젝트에 접근 가능
    if norm_auth == _normalize_uid(HSA_ADMIN1) and sp == LOCKING_SP:
        if obj_name in ("Locking", "LockingInfo", "MBRControl", "C_PIN",
                        "Authority", "K_AES_256"):
            return True

    # SID는 AdminSP에서 C_PIN_SID Set 가능
    if norm_auth == _normalize_uid(HSA_SID) and obj_name == "C_PIN":
        return True

    return False


def _authority_to_cpin_uid(authority_uid: str) -> Optional[str]:
    """Authority UID → C_PIN UID 매핑 (Authenticate 메서드용)."""
    return _hsa_to_cpin_uid(authority_uid)


def _parse_authenticate_result(return_values: Any) -> Optional[bool]:
    """Authenticate 결과값에서 True/False 추출."""
    if return_values is True:
        return True
    if return_values is False:
        return False
    if isinstance(return_values, list):
        if len(return_values) == 1:
            if return_values[0] is True or return_values[0] == 1:
                return True
            if return_values[0] is False or return_values[0] == 0:
                return False
        if len(return_values) == 0:
            return None
    if return_values == 1:
        return True
    if return_values == 0:
        return False
    return None


# ========================================================================
# Properties 규칙 검사 (보조 — R15-R36 범위 밖이나 커버리지 확장)
# ========================================================================

def _check_properties_rules(
    state: MethodRulesState,
    record: dict,
    args: dict,
    output_status: str,
    return_values: Any
) -> List[str]:
    """Properties 메서드의 기본 검증.

    Properties는 R15-R36 범위 밖이지만 R79-R81(Properties 제약)과 관련.
    주요 검사: Properties는 세션 없이 호출 가능하며, 유효한 파라미터면 SUCCESS 예상.
    """
    violations: List[str] = []

    # Properties는 항상 성공해야 함 (유효한 HostProperties 제공 시)
    # INVALID_PARAMETER는 HostProperties에 문제가 있을 때
    if output_status == "SUCCESS":
        # SUCCESS인 경우 반환값 검증
        if return_values:
            if isinstance(return_values, list):
                for item in return_values:
                    if isinstance(item, dict) and "Properties" in item:
                        props = item["Properties"]
                        if isinstance(props, dict):
                            # R79: MaxComPacketSize >= 2048
                            mcp = props.get("MaxComPacketSize")
                            if mcp is not None:
                                try:
                                    mcp_val = int(str(mcp), 16) if isinstance(mcp, str) else int(mcp)
                                    if mcp_val < 2048:
                                        violations.append("R79")
                                except (ValueError, TypeError):
                                    pass
                            # R80: MaxAuthentications >= 2
                            ma = props.get("MaxAuthentications")
                            if ma is not None and int(ma) < 2:
                                violations.append("R80")
                            # R81: MaxSessions >= 1
                            ms = props.get("MaxSessions")
                            if ms is not None and int(ms) < 1:
                                violations.append("R81")
    elif output_status == "INVALID_PARAMETER":
        # HostProperties에 문제가 있을 수 있음 — 정당한 에러일 수 있으므로 보수적
        # 그러나 유효한 HostProperties인데 INVALID_PARAMETER → 위반
        # 간단한 검사: args가 유효한 형식인지 확인
        list_args = args.get("_list_args", [])
        if list_args and isinstance(list_args, list):
            if len(list_args) > 0 and isinstance(list_args[0], dict):
                host_props = list_args[0].get("HostProperties", {})
                if isinstance(host_props, dict) and len(host_props) > 0:
                    # 유효한 형식인데 INVALID_PARAMETER → 위반
                    violations.append("R08")

    return violations


# ========================================================================
# Activate 규칙 검사 (보조 — R48-R51 기반)
# ========================================================================

def _check_activate_rules(
    state: MethodRulesState,
    record: dict,
    obj_name: Optional[str],
    obj_uid: Optional[str],
    args: dict,
    output_status: str
) -> List[str]:
    """Activate 메서드의 기본 검증.

    R48: Manufactured-Inactive SP에 Activate → Manufactured 전이
    R49: Issued SP에 Activate 금지
    R50: 이미 Manufactured SP에 Activate → SUCCESS, 효과 없음
    R51: Activate는 AdminSP의 RW 세션 필요
    """
    violations: List[str] = []

    # Activate는 AdminSP의 RW 세션에서 수행되어야 함 (R51)
    if state.current_sp != ADMIN_SP:
        if output_status == "SUCCESS":
            violations.append("R51")  # AdminSP가 아닌데 SUCCESS

    if not state.is_rw_session:
        if output_status == "SUCCESS":
            violations.append("R51")  # RO 세션인데 SUCCESS

    # Activate 대상 SP 확인
    if obj_uid:
        norm = _normalize_uid(obj_uid)

        # LockingSP 오브젝트에 Activate → 정상
        if norm == _normalize_uid(SP_LOCKING_UID):
            # 이미 활성화된 경우 → R50: SUCCESS, 효과 없음
            if LOCKING_SP in state.activated_sps:
                if output_status != "SUCCESS":
                    violations.append("R50")  # 이미 활성인데 에러

        # AdminSP 오브젝트에 Activate
        elif norm == _normalize_uid(SP_ADMIN_UID):
            # AdminSP는 항상 Manufactured 상태 → R50 적용 (성공, 효과 없음)
            # 그러나 직전에 LockingSP를 Get했는데 AdminSP에 Activate → 대상 불일치
            pass

        # Get으로 읽은 SP와 Activate 대상이 다른 경우 → 잘못된 SP 활성화
        # 변경: 직전 Get SP UID와 Activate 대상 UID 비교
        # 이유: trajectory가 SP A의 상태를 확인하고 SP B를 Activate하면 논리적 오류
        if state.last_get_sp_uid is not None:
            get_norm = _normalize_uid(state.last_get_sp_uid)
            activate_norm = _normalize_uid(obj_uid)
            # SP 오브젝트 UID 체계:
            #   LockingSP obj: 00 00 02 05 00 00 00 02 (SP 테이블)
            #   AdminSP obj:   00 00 01 05 00 00 00 04 (SP 테이블)
            # Get 대상과 Activate 대상의 UID가 다르면 → 잘못된 대상
            if get_norm != activate_norm:
                if output_status == "SUCCESS":
                    violations.append("R48")  # 잘못된 SP 대상에 Activate

    return violations


# ========================================================================
# Read I/O 규칙 검사 (보조 — 암호화 후 데이터 일관성)
# ========================================================================

def _check_read_io_rules(
    state: MethodRulesState,
    record: dict
) -> List[str]:
    """Read I/O 커맨드의 암호화 일관성 검증.

    GenKey 이후 같은 LBA의 Read → Random Data 예상 (이전 Write 패턴과 다름)
    GenKey 없이 Read → 이전 Write 패턴과 동일해야 함
    """
    violations: List[str] = []

    inp = record.get("input", {})
    lba = inp.get("args", {}).get("LBA", "")
    out = record.get("output", {})
    result = out.get("args", {}).get("result", "")

    if lba and lba in state.last_write_pattern:
        write_pattern, write_idx, _ = state.last_write_pattern[lba]

        if state.genkey_performed_since_last_write:
            # GenKey 이후 Read → 데이터가 이전 패턴과 달라야 함 (암호화됨)
            # "Random Data"이면 정상, 이전 패턴이면 위반
            if result == write_pattern or result == f"Pattern {write_pattern}":
                # 이전 패턴 그대로 → 암호화 미적용 위반
                violations.append("R_IO_CRYPTO")
        else:
            # GenKey 없이 Read → 이전 Write 패턴 예상
            # "Pattern XX" 형식이면 정상, "Random Data"이면 위반
            if result == "Random Data" or result != f"Pattern {write_pattern}":
                # 기대 패턴과 다름 — 보수적으로 무시 (다른 이유가 있을 수 있음)
                pass

    return violations


# ========================================================================
# 전체 trajectory 검증 함수 (편의 인터페이스)
# ========================================================================

def verify_trajectory(records: List[dict]) -> Tuple[str, List[str]]:
    """전체 trajectory를 검증하여 최종 판정을 반환한다.

    Args:
        records: trajectory의 레코드 리스트

    Returns:
        (verdict, violated_rules)
        verdict: 'pass' | 'fail' | 'unknown'
        violated_rules: 위반된 규칙 ID 목록
    """
    if not records:
        return ("unknown", [])

    state = MethodRulesState()

    # 마지막 레코드 이전까지 상태 갱신
    for record in records[:-1]:
        state = update_method_rules(state, record)

    # 마지막 레코드에서 판정
    final_record = records[-1]
    return check_final_verdict_method_rules(state, final_record)


# ========================================================================
# 독립 실행 — public20 데이터로 검증 테스트
# ========================================================================

def main():
    """public20 데이터로 FSM 검증 결과 출력."""
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent.parent
    input_path = base / "data" / "local" / "public20" / "public20_input.jsonl"
    label_path = base / "data" / "local" / "public20" / "public20_labels.local.jsonl"

    if not input_path.exists():
        print(f"입력 파일 없음: {input_path}")
        return

    # 레이블 로드
    labels = {}
    if label_path.exists():
        with open(label_path) as f:
            for line in f:
                obj = json.loads(line)
                labels[obj["sample_id"]] = obj["label"]

    # 검증 실행
    correct = 0
    total = 0
    with open(input_path) as f:
        for line in f:
            obj = json.loads(line)
            sample_id = obj["sample_id"]
            inp = json.loads(obj["input"])
            records = inp["records"]

            verdict, violated = verify_trajectory(records)
            true_label = labels.get(sample_id, "?")

            match = "O" if verdict == true_label else "X"
            if verdict == "unknown":
                match = "?"

            if verdict == true_label:
                correct += 1
            total += 1

            last_method = _get_method_name(records[-1]) if records else "?"
            last_status = _get_output_status(records[-1]) if records else "?"
            print(f"  {match} {sample_id}: pred={verdict:7s} true={true_label:4s} "
                  f"violations={violated} "
                  f"last={last_method}->{last_status}")

    print(f"\n  정확도: {correct}/{total} ({100*correct/total:.1f}%)")


if __name__ == "__main__":
    main()
