# TCG/Opal 통합 검증 FSM 감사 보고서

**작성일**: 2026-05-30 KST
**대상 파일**: `src/opal_verifier_fsm.py` (통합 검증기)
**부분 FSM**: 5개 (fsm_session_status, fsm_method_rules, fsm_cpin_lifecycle, fsm_acl_locking, fsm_properties_dataio)
**규칙 원본**: `docs/legacy_spec_rules.md` (86개 규칙)

---

## Task 1: 규칙 커버리지 감사 (R01-R86)

### 범주 1: 상태코드 규칙 (R01-R09)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R01 | SUCCESS = 정상 처리 완료 | FSM1 (session_status) | O | 모든 메서드에서 SUCCESS 일관성 검사. consistency check 3단계 (exact/target/context) 구현. |
| R02 | NOT_AUTHORIZED = ACL 미충족 | FSM1 (session_status) | O | C_PIN_MSID Anybody 접근 거부 시 위반 감지. 이전 성공 이력 기반 일관성 검사 포함. |
| R03 | NOT_AUTHORIZED = 잘못된 비밀번호 | FSM1 (session_status) | O | known_pins 기반 HostChallenge 비교. PIN이 알려지지 않으면 unknown 반환. |
| R04 | SP_BUSY = 동시 세션 충돌 | FSM1 (session_status) | O | session_open + target_sp로 기존 세션 존재 확인. RW-RW, RO-RW 충돌 감지. |
| R05 | SP_FROZEN = SP가 Frozen 상태 | FSM1 (session_status) | 부분 | SP_FROZEN 상태코드를 pass로 허용하지만, Frozen 상태 자체를 추적하지 않음. |
| R06 | NO_SESSIONS_AVAILABLE = 최대 세션 초과 | FSM1 (session_status) | 부분 | NO_SESSIONS_AVAILABLE 상태코드를 pass로 허용. 실제 세션 수를 세지는 않음. |
| R07 | INVALID_PARAMETER = 클래스 authority를 HSA로 사용 | FSM1 (session_status) | O | CLASS_AUTHORITY_UIDS 집합 기반 판별. |
| R08 | INVALID_PARAMETER = 잘못된 파라미터 | FSM1 (session_status), FSM2 (method_rules) | O | 넓은 범위 규칙. Set/Get 파라미터 유효성을 ACL 인지 헬퍼로 검증. |
| R09 | AUTHORITY_LOCKED_OUT = TryLimit 초과 | FSM1 (session_status) | 부분 | 상태코드를 pass로 허용하지만, TryLimit 추적은 FSM3에 위임. |

### 범주 2: 세션 규칙 (R10-R14)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R10 | RW 세션은 SP당 1개만 | FSM1 (session_status) | O | R04와 함께 검사. session_open + target_sp 기반. |
| R11 | RO 세션에서 영구 변경 불가 | FSM1 (session_status) | O | Set/Activate/GenKey가 RO 세션에서 SUCCESS이면 위반. |
| R12 | Write=True는 RW, False는 RO | FSM1 (session_status) | O | write_param 추적. 세션 유형 결정에 사용. |
| R13 | SessionTimeout 범위 초과 시 실패 | FSM1 (session_status) | O | MaxSessionTimeout/MinSessionTimeout 기반 범위 검사. |
| R14 | TransTimeout 범위 초과 시 실패 | FSM1 (session_status) | O | MaxTransTimeout/MinTransTimeout 기반 범위 검사. |

### 범주 3: Get 메서드 규칙 (R15-R20)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R15 | 존재하지 않는 테이블/오브젝트에 Get 실패 | FSM2 (method_rules) | O | obj_name/uid 없으면 expected_error. 이전 성공 이력 기반 일관성 검사. |
| R16 | Object Get에서 Cellblock에 row/table 값 포함 시 실패 | FSM2 (method_rules) | O | _cellblock_has_row_or_table_values() 검사. |
| R17 | Byte table Get에서 column 값 포함 시 실패 | FSM2 (method_rules) | O | _cellblock_has_column_values() + _is_byte_table() 조합. |
| R18 | Get은 인가된 컬럼만 반환 | FSM2 (method_rules), FSM4 (acl_locking) | O | C_PIN_SID의 PIN(col 3) 반환 시 위반. FSM4의 R62도 동일 검사. |
| R19 | Byte table Get에서 ACL 미충족 시 빈 결과 | FSM2 (method_rules) | O | Anybody 세션에서 비어있지 않은 결과 반환 시 위반. |
| R20 | Get 결과 컬럼 순서는 Column table 순서 | FSM2 (method_rules) | O | _check_column_order() 오름차순 검증. |

### 범주 4: Set 메서드 규칙 (R21-R28)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R21 | Set에서 ACL 미충족 시 NOT_AUTHORIZED (전체 실패) | FSM2 (method_rules) | O | Anybody 세션에서 Set 시도 시 expected_error. 이전 성공 이력 일관성 검사. |
| R22 | 동일 컬럼 중복 지정 시 INVALID_PARAMETER | FSM2 (method_rules) | O | _has_duplicate_columns() 검사. |
| R23 | Object.Set에서 Where 파라미터 포함 시 실패 | FSM2 (method_rules) | O | where_param 존재 + 비-byte 테이블이면 expected_error. |
| R24 | Table.Set에서 Where 없이 object table 시 실패 | FSM2 (method_rules) | X (미구현) | 코드 주석에 "현재 데이터에서 해당 없음"으로 스킵. |
| R25 | Object table Set에서 Bytes 타입 Values 사용 시 실패 | FSM2 (method_rules) | O | _is_values_bytes_type() 검사. |
| R26 | Byte table Set에서 RowValues 사용 시 실패 | FSM2 (method_rules) | O | byte 테이블인데 Bytes 타입 아니면 expected_error. |
| R27 | Values 없이 Set → SUCCESS (무효과) | FSM2 (method_rules) | 부분 | 코드에 로직 존재하나 보수적으로 pass 처리. 강제 검증 안 함. |
| R28 | UID/system 컬럼 변경 시도 시 실패 | FSM2 (method_rules) | O | _values_has_uid_column() 검사. |

### 범주 5: Authenticate 메서드 규칙 (R29-R36)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R29 | 존재하지 않는 authority → INVALID_PARAMETER | FSM2 (method_rules) | O | _is_valid_authority_uid() 기반. 알려진 UID 목록 대조. |
| R30 | 클래스 authority → INVALID_PARAMETER | FSM2 (method_rules) | O | CLASS_AUTHORITY_UIDS 대조. |
| R31 | 올바른 비밀번호 → SUCCESS/True | FSM2 (method_rules) | O | known_credentials 기반 PIN 비교. |
| R32 | 틀린 비밀번호 → SUCCESS/False | FSM2 (method_rules) | O | PIN 불일치 시 True 반환하면 위반. |
| R33 | 비활성 authority → SUCCESS/False | FSM2 (method_rules) | O | authority_enabled 추적. Enabled=False인 authority 인증 성공 시 위반. |
| R34 | Exchange authority → SUCCESS/False | FSM2 (method_rules) | X (미구현) | 코드 주석에 "보수적으로 처리"로 스킵. Exchange Operation 유형 추적 없음. |
| R35 | Anybody → 항상 SUCCESS/True | FSM2 (method_rules) | O | HSA_ANYBODY 대조. |
| R36 | MaxAuthentications 초과 → SUCCESS/False | FSM2 (method_rules) | O | auth_count_in_session >= max_authentications 검사. |

### 범주 6: C_PIN/TryLimit 규칙 (R37-R42)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R37 | 인증 실패 시 Tries 증가 | FSM3 (cpin_lifecycle) | 부분 | Tries 값 자체를 추적하지는 않음. 상태코드 패턴으로 간접 추론. |
| R38 | 인증 성공 시 Tries=0 리셋 | FSM3 (cpin_lifecycle) | 부분 | 동일. Tries 컬럼 값을 Get으로 관찰할 때만 검증 가능. |
| R39 | Tries는 TryLimit을 초과하지 않음 | FSM3 (cpin_lifecycle) | 부분 | TryLimit 값 추적 있으나, 실제 Tries 카운트 정밀 추적 제한적. |
| R40 | TryLimit=0이면 무제한, Tries=0 유지 | FSM3 (cpin_lifecycle) | 부분 | 동일. |
| R41 | PIN 변경 시 Tries=0 리셋 | FSM3 (cpin_lifecycle) | 부분 | C_PIN Set 감지 시 tries_reset 상태 갱신. |
| R42 | 전원 순환 + Persistence=False → Tries 리셋 | FSM3 (cpin_lifecycle) | X (미구현) | 전원 순환 이벤트 감지 메커니즘 없음. |

### 범주 7: Authority Operation 규칙 (R43-R45)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R43 | Password authority를 Exchange로 사용 시 에러 | FSM3 (cpin_lifecycle) | 부분 | Operation 유형 추적이 제한적. 알려진 authority만 검사. |
| R44 | Exchange authority는 Authenticate 불가 | FSM3 (cpin_lifecycle) | 부분 | R34와 동일 한계. Exchange 유형 식별 제한. |
| R45 | TPerSign authority는 SPSigningAuthority만 | FSM3 (cpin_lifecycle) | X (미구현) | TPerSign 유형 식별 로직 없음. |

### 범주 8: Opal 세션 규칙 (R46-R47)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R46 | Write=True (RW 세션) 필수 지원 | FSM3 (cpin_lifecycle) | O | Write=True StartSession 성공 확인. |
| R47 | SessionTimeout 범위 초과 시 실패 | FSM3 (cpin_lifecycle), FSM1 (session_status) | O | R13과 중복 검사. FSM1이 더 정밀. |

### 범주 9: Lifecycle/Activate/Revert 규칙 (R48-R56)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R48 | Manufactured-Inactive SP에 Activate → Manufactured 전이 | FSM3 (cpin_lifecycle) | O | locking_sp_activated 추적. |
| R49 | 발행된(issued) SP에 Activate 금지 | FSM3 (cpin_lifecycle) | 부분 | issued SP 상태 추적이 제한적. |
| R50 | 이미 Manufactured SP에 Activate → 성공, 무효과 | FSM3 (cpin_lifecycle) | 부분 | 이중 Activate 검사 로직은 있으나 보수적. |
| R51 | Activate는 RW 세션 + Admin SP 필요 | FSM3 (cpin_lifecycle) | O | session_is_rw + current_sp 검사. |
| R52 | Activate 시 SID PIN → Admin1 C_PIN 복사 | FSM1 (session_status) | O | sid_pin_current → known_pins[ADMIN1] 복사. |
| R53 | Manufactured-Inactive SP에 Revert → 무효과 | FSM3 (cpin_lifecycle) | 부분 | lifecycle 상태 기반 판정이지만 추적 제한. |
| R54 | Admin SP에 Revert → 전체 TPer 초기화 | FSM3 (cpin_lifecycle) | 부분 | Admin SP Revert 감지하지만 전체 초기화 효과 검증은 제한. |
| R55 | Revert는 RW 세션 + Admin SP 필요 | FSM3 (cpin_lifecycle) | O | session_is_rw 검사. |
| R56 | Admin SP Revert 후 세션 즉시 중단 | FSM3 (cpin_lifecycle) | 부분 | 세션 종료 추적 있으나 "즉시" 여부 검증 제한. |

### 범주 10: RevertSP 규칙 (R57-R58)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R57 | KeepGlobalRangeKey=True + Global Range 양쪽 Locked → 실패 | FSM4 (acl_locking) | O | global_range_read_locked + write_locked 상태 추적. |
| R58 | RevertSP 후 세션 종료 필수 | FSM4 (acl_locking) | O | revert_sp_invoked + session_aborted_after_revert 추적. |

### 범주 11: Locking 테이블 규칙 (R59-R61)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R59 | RangeStart 정렬 위반 시 INVALID_PARAMETER | FSM4 (acl_locking) | 부분 | INVALID_PARAMETER 반환을 기록하지만, 실제 정렬 계산은 안 함. |
| R60 | RangeLength 정렬 위반 시 INVALID_PARAMETER | FSM4 (acl_locking) | 부분 | 동일. AlignmentGranularity 등 속성 미추적. |
| R61 | LockOnReset 값 지원 여부 검사 | FSM4 (acl_locking) | O | SUPPORTED_LOCK_ON_RESET 집합 대조. |

### 범주 12: ACL/ACE 규칙 (R62-R69)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R62 | C_PIN_SID Get에서 PIN 컬럼 제외 | FSM4 (acl_locking), FSM2 (method_rules) | O | 양쪽 FSM에서 이중 검사. CPIN_COL_PIN(=3) 반환 시 위반. |
| R63 | C_PIN_MSID Get에서 PIN 컬럼 포함 | FSM4 (acl_locking) | O | Cellblock 범위 내 PIN 요청 시 누락이면 위반. |
| R64 | C_PIN_SID Set PIN은 SID 필요 | FSM4 (acl_locking) | O | authenticated_authority != SID이면 위반. |
| R65 | Locking ReadLocked/WriteLocked Set은 Admin ACE 필요 | FSM4 (acl_locking) | O | _is_admin_authority() 검사. |
| R66 | GenKey는 Admin authority 필요 | FSM4 (acl_locking) | O | K_AES/Locking 오브젝트 GenKey 시 Admin 검사. |
| R67 | SP Activate는 SID 필요 | FSM4 (acl_locking) | O | _is_sid() 검사. |
| R68 | SP Revert는 SID 또는 Admins 필요 | FSM4 (acl_locking) | O | _is_sid() OR _is_admin_authority() 검사. |
| R69 | Admin SP에서 Authority Enabled 변경은 SID 필요 | FSM4 (acl_locking) | O | current_sp == UID_ADMIN_SP + _is_sid() 검사. |

### 범주 13: Opal 메서드 제약 (R70-R73)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R70 | Random Count > 32 → INVALID_PARAMETER | FSM4 (acl_locking) | O | Count 값 직접 비교. |
| R71 | Random 미지원 파라미터 → INVALID_PARAMETER | FSM4 (acl_locking) | O | BufferOut, Padding 키 존재 검사. |
| R72 | ActiveDataRemovalMechanism 미지원 값 → INVALID_PARAMETER | FSM4 (acl_locking) | O | 값 >= 3이면 위반. |
| R73 | MBRControl DoneOnReset 지원 값 검사 | FSM4 (acl_locking) | O | SUPPORTED_LOCK_ON_RESET 집합 대조 (R61과 동일 로직). |

### 범주 14: Authority 사전 구성 규칙 (R74-R77)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R74 | Admin1은 OFS에서 Enabled=True | FSM4 (acl_locking) | O | LockingSP 활성화 + override 없는 Admin1의 Enabled 확인. |
| R75 | User1-8은 OFS에서 Enabled=False | FSM4 (acl_locking) | O | _is_user_authority() + authority_enabled_overrides 검사. |
| R76 | Users 클래스 authority 직접 인증 불가 | FSM4 (acl_locking) | O | _is_class_authority() + 인증 성공 시 위반. |
| R77 | ACE BooleanExpr 수정 제한 | FSM4 (acl_locking) | O | _is_valid_ace_boolean_expr() 패턴 매칭. |

### 범주 15: Manufactured-Inactive SP 세션 (R78)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R78 | Manufactured-Inactive SP에 세션 불가 | FSM5 (properties_dataio) | O | locking_sp_activated=False인 상태에서 LockingSP 세션 SUCCESS이면 위반. |

### 범주 16: Properties 제약 (R79-R81)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R79 | MaxComPacketSize >= 2048 | FSM5 (properties_dataio) | O | 16진수 파싱 포함. |
| R80 | MaxAuthentications >= 2 | FSM5 (properties_dataio) | O | 정수/16진수 모두 처리. |
| R81 | MaxSessions >= 1 | FSM5 (properties_dataio) | O | 동일. |

### 범주 17: Locking Range 동작 (R82-R84)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R82 | GlobalRange RangeStart/RangeLength 수정 불가 | FSM5 (properties_dataio) | O | is_global + col 3/4 Set SUCCESS 감지. |
| R83 | ReadLockEnabled=False일 때 ReadLocked=True 무효 | FSM5 (properties_dataio) | O | Set 후 상태 체크: read_locked=True + read_lock_enabled=False. |
| R84 | LockOnReset {0} → 전원 순환 시 잠금 복원 | FSM5 (properties_dataio) | X (사실상 미구현) | power_cycle_occurred 플래그가 True가 되는 경로가 없음. 코드 주석에도 "향후 확장" 명시. |

### 범주 18: Cellblock/Addressing 규칙 (R85-R86)

| 규칙 | 스펙 설명 (요약) | 구현 위치 | 정확? | 비고 |
|------|------------------|-----------|-------|------|
| R85 | Cellblock 범위 초과 시 Get 실패 | FSM2 (method_rules), FSM5 (properties_dataio) | 부분 | FSM2는 MAX_COLUMN_BY_OBJECT 기반 검사. FSM5는 보수적으로 스킵 (스키마 없음). |
| R86 | 빈 범위에 Next → 빈 결과 | FSM5 (properties_dataio) | X (사실상 미구현) | 코드 주석에 "범위 소진 추적 없이 보수적으로 스킵" 명시. |

### 커버리지 요약

- **완전 구현 (O)**: 55개 규칙
- **부분 구현**: 22개 규칙 (검사 로직 있으나 정밀도 제한)
- **미구현 (X)**: 9개 규칙 (R24, R34, R42, R45, R84, R86 + R37-R40의 정밀 Tries 추적)
- **미구현 목록 상세**:
  - **R24**: Table.Set에서 Where 없이 object table 접근 검사 (데이터에 해당 없다고 스킵)
  - **R34**: Exchange authority Authenticate 결과 검증 (Operation 유형 추적 없음)
  - **R42**: 전원 순환 후 Persistence=False인 C_PIN Tries 리셋 (전원 순환 이벤트 감지 없음)
  - **R45**: TPerSign authority 제약 (TPerSign 유형 식별 없음)
  - **R84**: LockOnReset 후 전원 순환 시 잠금 복원 (power_cycle_occurred 트리거 없음)
  - **R86**: Next on empty scope → 빈 결과 (범위 소진 추적 없음)

---

## Task 2: 통합 버그 점검

### 2.1 보고된 버그: `fsm_cpin_lifecycle._extract_args()` 크래시

**위치**: `tools/datagen/fsm_cpin_lifecycle.py`, 251-259행

```python
def _extract_args(record: dict) -> dict:
    """레코드에서 메서드 인자 추출 (required + optional 병합)."""
    inp = record.get("input", {})
    method = inp.get("method", {})
    args = method.get("args", {})       # <-- args가 list일 수 있음
    merged = {}
    merged.update(args.get("required", {}))  # <-- list.get() → AttributeError
    merged.update(args.get("optional", {}))  # <-- 동일
    return merged
```

**원인**: Properties 메서드의 `args`는 `dict`가 아니라 `list` 형태이다. 예시:
```json
{
  "method": {
    "name": "Properties",
    "args": [{"HostProperties": {"MaxComPacketSize": "0800", ...}}]
  }
}
```

`list` 객체에는 `.get()` 메서드가 없으므로 `AttributeError: 'list' object has no attribute 'get'`이 발생한다.

**수정 제안**:
```python
def _extract_args(record: dict) -> dict:
    inp = record.get("input", {})
    method = inp.get("method", {})
    args = method.get("args", {})
    if isinstance(args, list):
        return {"_list_args": args}  # Properties 등 리스트 형태 대응
    merged = {}
    merged.update(args.get("required", {}))
    merged.update(args.get("optional", {}))
    return merged
```

### 2.2 동일 버그 존재 여부 (다른 FSM)

| FSM | 파일 | list 처리 | 안전? |
|-----|------|-----------|-------|
| FSM1 (session_status) | `src/fsm_session_status.py` L252 | `isinstance(method_args, list)` 분기 있음 | O |
| FSM2 (method_rules) | `tools/datagen/fsm_method_rules.py` L244 | `isinstance(args, list)` 분기 있음 | O |
| FSM3 (cpin_lifecycle) | `tools/datagen/fsm_cpin_lifecycle.py` L255 | **list 처리 없음** | **X (버그)** |
| FSM4 (acl_locking) | `src/fsm_acl_locking.py` L250-255 | args에 직접 `.get()` 호출. args가 dict가 아닌 경우 `merged.update(args.get("required", {}))`에서 같은 크래시 가능 | **잠재적 위험** |
| FSM5 (properties_dataio) | `src/fsm_properties_dataio.py` L210-222 | `_extract_spid_from_start_session()`에서 `isinstance(required, dict)` 검사 있으나, 메인 경로는 `_get_method_name()`만 사용 | O (간접 안전) |

**결론**: FSM3에 확정 버그. FSM4에도 동일 패턴 존재 (`_get_method_args()` L250-255), `args`가 list인 경우에 대한 방어 코드 없음. 단, FSM4의 `_get_method_args()`도 동일 구조:

```python
def _get_method_args(record: dict) -> dict:
    inp = record.get("input", {})
    method = inp.get("method", {})
    args = method.get("args", {})
    merged = {}
    merged.update(args.get("required", {}))
    merged.update(args.get("optional", {}))
    return merged
```

FSM4도 Properties 레코드에서 동일하게 크래시한다.

### 2.3 통합 검증기의 예외 격리

`opal_verifier_fsm.py`의 `update_all()` (L107-134)과 `check_final_all()` (L180-222)은 각 FSM 호출을 `try/except Exception: pass`로 감싸고 있다. 따라서 FSM3/FSM4의 크래시는 해당 FSM의 상태가 갱신되지 않을 뿐, 전체 검증기가 중단되지는 않는다. 다만, **크래시한 FSM의 판정이 UNKNOWN으로 처리**되므로, 해당 FSM이 검출해야 할 위반을 놓칠 수 있다.

---

## Task 3: 충돌 감지

### 3.1 판정 우선순위 분석

통합 검증기의 합산 로직 (`check_final_all()`, L228-257):

1. 어느 FSM이라도 FAIL → 전체 FAIL (위반 사유 합산)
2. 모두 PASS → 전체 PASS
3. FAIL 없이 UNKNOWN 혼재 → PASS 판정 있는 FSM 결과 채택
4. 모든 FSM이 UNKNOWN → 기본 PASS

### 3.2 잠재적 모순

**문제 1: FSM1과 FSM4의 R62 중복**

FSM1의 check_final에서 C_PIN_SID Get SUCCESS 시 PIN 컬럼 반환 여부를 직접 검사하지는 않지만, FSM2(`_check_get_rules`)의 R18에서 C_PIN_SID의 PIN 컬럼 반환을 검사하고, FSM4도 R62로 동일 검사를 수행한다. 이들은 **같은 방향**(둘 다 FAIL)이므로 모순은 아니나, 동일 위반에 대해 **중복 사유**가 보고된다.

**문제 2: UNKNOWN 기본 PASS 위험**

Properties 레코드가 첫 레코드(args=list)인 경우, FSM3과 FSM4가 모두 크래시하여 UNKNOWN을 반환한다. FSM1/FSM2/FSM5가 PASS이면 전체 PASS가 된다. 이는 **올바른 동작이지만**, FSM3/FSM4의 검증이 완전히 누락되는 것이므로 위험하다.

**문제 3: FSM 간 상태 독립성으로 인한 비일관**

각 FSM이 독립적으로 세션/인증 상태를 추적하므로, **하나의 FSM이 세션을 인식하지 못하는 상황**이 발생할 수 있다. 예를 들어, FSM3이 Properties 레코드에서 크래시하면, 그 이후의 StartSession도 FSM3의 상태에 반영되지 않아 세션 없는 상태로 나머지 trajectory를 처리한다.

### 3.3 False Positive 위험 (ANY FAIL → FAIL)

FSM 중 하나라도 FAIL이면 전체 FAIL이 되므로, **과도한 FAIL 편향**이 존재한다. 특히:

- FSM1의 consistency check가 너무 공격적인 경우 (이전 세션에서 같은 target에 다른 args로 성공했는데, 현재 args가 유효하지 않아 정당하게 실패하는 경우를 위반으로 오판)
- FSM4의 R62/R63에서 Cellblock 범위 해석 오류 시 오판
- FSM5의 R83에서 Set 순서에 따른 일시적 상태 불일치 (ReadLocked=True를 먼저 Set하고 ReadLockEnabled=True를 나중에 Set하는 경우, 중간 상태에서 위반으로 기록)

---

## Task 4: 엣지 케이스 분석

### 4.1 Revert/RevertSP가 최종 명령인 경우

**Revert (최종)**:
- FSM1: method=="Revert"이면 기타 메서드 분기로 진입. SUCCESS이면 pass, 이전 성공 이력 있는데 실패하면 fail.
- FSM3: Revert 처리 로직 있음. Admin SP Revert 후 세션 종료 검사 (R56). 최종 레코드가 Revert 자체이면 세션 종료 확인 불가 → 보수적 판정.
- FSM4: Revert 메서드 분기에서 SID/Admins authority 검사 (R68). 권한 미충족이면 위반.
- **위험**: FSM3의 R56 "Revert 후 세션 즉시 중단" 검증이 최종 레코드가 Revert일 때 세션 종료 레코드가 없으므로 위반으로 판정할 수 있음. 그러나 FSM3 코드를 확인하면 이 검사는 중간 레코드에서만 수행되므로 문제 없음.

**RevertSP (최종)**:
- FSM4: R57 검사 (KeepGlobalRangeKey + Locked). R58 검사에서 "RevertSP 후 세션 미종료"를 판정하나, 최종 레코드가 RevertSP 자체이면 `check_final` 시점에서 `revert_sp_invoked=True` + `session_aborted_after_revert=False` → `method_name not in (EndSession, CloseSession)` → **FAIL 반환**. 이는 **정확한 판정**이다 (RevertSP 후 세션 종료가 없으므로 위반).

### 4.2 Random 메서드가 최종 명령인 경우

- FSM4: Count > 32이면 R70, 미지원 파라미터면 R71 검사. 정상 범위이면 PASS.
- FSM1/FSM2: Random에 대한 구체적 규칙 없음 → SUCCESS이면 pass, 기타 상태코드도 unknown/pass.
- **결론**: 정상 동작.

### 4.3 Next 메서드가 최종 명령인 경우

- FSM5: `_check_next_empty_scope()` 호출되나, 코드 내부에서 범위 소진 여부를 판단하지 못하므로 사실상 아무 검사도 하지 않음.
- FSM1/FSM2: Next에 대한 구체적 규칙 없음. SUCCESS이면 pass.
- **위험**: R86 검증이 사실상 불가능. 하지만 Next 관련 테스트 케이스가 실제로 존재하는지는 데이터에 따라 다름.

### 4.4 동일 세션에서 다중 Authenticate

- FSM2: `auth_count_in_session`을 추적하여 R36 (MaxAuthentications 초과) 검사.
- FSM1: Authenticate 메서드에 대해 SUCCESS/INVALID_PARAMETER/AUTHORITY_LOCKED_OUT/NOT_AUTHORIZED 모두 pass 반환. MaxAuthentications 관련 검사는 FSM2에 위임.
- FSM4: Authenticate 처리에서 인증된 authority를 갱신. 클래스 authority 검사 (R76).
- **결론**: 정상 동작. 다중 Authenticate는 FSM2의 R36 검사로 커버됨.

### 4.5 EndSession이 최종 명령인 경우

- FSM1: EndSession + SUCCESS → pass. SUCCESS 아니면 R01 위반.
- FSM4: EndSession 처리에서 세션 상태 초기화. RevertSP 후 EndSession이면 session_aborted_after_revert=True.
- **결론**: 정상 동작.

### 4.6 전원 순환이 trajectory 중간에 발생

- 현재 **어떤 FSM도 전원 순환 이벤트를 감지하지 못함**. FSM5에 `power_cycle_occurred` 플래그가 있으나 True로 설정되는 경로 없음.
- trajectory 데이터에서 전원 순환이 어떤 형식으로 표현되는지 불명확 (별도 레코드? 세션 강제 종료?).
- **위험**: R42 (Persistence=False), R84 (LockOnReset) 규칙이 완전히 미검증.

### 4.7 매우 짧은 trajectory (레코드 1개)

- `verify_trajectory()` L293-295: 단일 레코드 시 빈 `OpalVerifierState()`로 즉시 `check_final_all()` 호출.
- 대부분의 FSM에서 초기 상태 + 단일 레코드로 판정. 세션이 열리지 않은 상태에서의 판정이므로, Properties/StartSession 외의 메서드는 UNKNOWN 또는 기본 PASS로 처리될 가능성.
- **위험**: 단일 Properties 레코드는 정상 처리 가능. 단일 Set 레코드 등은 세션 컨텍스트 없이 판정해야 하므로 부정확할 수 있으나, 실제 trajectory에서 단일 Set은 비현실적.

### 4.8 매우 긴 trajectory (30+ 레코드)

- 성능 문제: FSM1은 매 레코드마다 `copy.deepcopy(state)`를 수행. State에 `Set[str]` 필드가 여러 개 있으므로, 30+ 레코드에서 `successful_operations` 등이 커질수록 deepcopy 비용이 선형 증가.
- 정확도 문제: 없음. 로직 자체는 레코드 수에 무관.
- **위험**: 성능만 문제. 수천 레코드 수준에서는 심각할 수 있으나, 30개 수준에서는 무시 가능.

---

## Task 5: 알려진 약점, 갭, 위험

### 1. 치명적 약점

**(a) FSM3/FSM4의 list args 크래시 (확정 버그)**
- `_extract_args()` 및 `_get_method_args()`가 Properties 메서드(args=list)에서 `AttributeError` 발생.
- 통합 검증기의 try/except로 중단은 방지되나, 해당 FSM의 검증이 완전히 누락됨.
- **영향**: R37-R56 (FSM3), R57-R77 (FSM4)의 검증이 Properties 레코드가 첫 번째인 trajectory에서 불안정.

**(b) 전원 순환 이벤트 미지원 (R42, R84)**
- 전원 순환을 표현하는 레코드 형식이 정의되지 않아, 관련 규칙 검증 불가.
- hidden 테스트에 전원 순환 시나리오가 포함될 경우 오판 위험.

**(c) FSM5의 R83 false positive (Set 순서 의존)**
- `ReadLocked=True`와 `ReadLockEnabled=True`를 같은 Set 호출에서 동시에 설정하면 정상이지만, FSM5는 Values 리스트를 순차 처리하여 중간 상태에서 위반을 감지할 수 있음.
- 단, `_apply_locking_column()`이 모든 값을 한 번에 적용한 후 검사하므로, 같은 Set 내의 순서 문제는 발생하지 않음. **별도 Set 호출**에서 ReadLocked를 먼저 설정하고 ReadLockEnabled를 나중에 설정하는 시나리오에서만 문제.

### 2. 구조적 약점

**(d) 5개 FSM 간 상태 불공유**
- 각 FSM이 독립적으로 세션/인증 상태를 추적하므로, UID 정규화 방식 차이 등으로 인한 불일치 가능.
- 예: FSM3은 space-separated UID(`_UID_SP_ADMIN_SPACED`)와 no-space UID(`_SPID_ADMIN`)를 별도로 정의하고 내부에서 정규화하지만, FSM4는 처음부터 no-space UID만 사용. 레코드에서 UID가 space-separated로 오면 FSM4의 `_normalize_uid()`가 처리하므로 문제 없으나, 매핑 테이블 간 불일치 위험은 존재.

**(e) deepcopy 오버헤드 (FSM1, FSM5)**
- FSM1은 매 레코드마다 전체 상태를 deepcopy. 30+ 레코드 trajectory에서 성능 저하 가능.
- FSM4는 in-place 변경으로 이 문제 없음.

**(f) ANY FAIL → FAIL 정책의 false positive 위험**
- 5개 FSM 중 하나라도 오판하면 전체 FAIL. 각 FSM의 정확도가 독립적으로 높아야 전체 정확도가 보장됨.
- 특히 FSM1의 `_is_set_expected_to_succeed()` / `_is_get_expected_to_succeed()` ACL 인지 헬퍼가 불완전하면 정당한 실패를 위반으로 오판할 수 있음.

### 3. 데이터 호환성 약점

**(g) CLASS_AUTHORITY_UIDS 불일치**
- FSM1: `CLASS_AUTHORITY_UIDS = {"0000000900000001" (Anybody), "0000000900000002" (Admins), "0000000900030002" (Users)}`
- FSM4: `UID_ADMINS_CLASS = "0000000900010000"`, `UID_USERS_CLASS = "0000000900030000"`
- **충돌**: FSM1은 Anybody를 클래스 authority로 분류하고, Admins 클래스를 `0000000900000002`로 정의. FSM4는 Admins를 `0000000900010000`으로 정의. 이 불일치는 **심각한 오류**이다. Admins 클래스의 올바른 UID가 어떤 것인지에 따라 R07, R30, R76 판정이 달라진다.
- 또한 FSM1이 Anybody(`0000000900000001`)를 클래스 authority로 분류하는 것은 **스펙 해석에 따라 다를 수 있음**. TCG 스펙에서 Anybody는 특수 authority이나 반드시 클래스인 것은 아님.

**(h) HSA_TO_CPIN 매핑의 MSID 위치 불일치**
- FSM1: `CPIN_MSID_UID = "00 00 00 0B 00 00 84 02"` (space-separated)
- FSM4: `UID_CPIN_MSID = "0000000b00008402"` (no-space, 소문자)
- 정규화 후 동일하므로 기능적 문제는 없으나, 코드 유지보수 시 혼란 소지.

### 4. 검증 범위 갭

**(i) Data I/O (Read/Write) 검증은 FSM5만 담당**
- GenKey 후 Read 결과가 이전 Write 패턴과 동일하면 FAIL. 이는 스펙 규칙이 아닌 **추론적 검증**이다.
- FSM2도 Read I/O 규칙을 검사하지만, 중복 가능.

**(j) Revert 후 전체 TPer 상태 초기화 미구현 (R54)**
- Admin SP Revert 시 모든 SP가 OFS로 돌아가야 하지만, 현재 FSM들은 Revert 감지만 하고 실제로 상태를 초기화하지 않음.
- Revert 후 속행되는 trajectory에서 이전 세션/인증 상태가 남아있어 오판 가능.

**(k) R59/R60 정렬 검사의 불완전성**
- AlignmentGranularity, LowestAlignedLBA 등의 속성을 추적하지 않으므로, 정렬 위반 여부를 실제로 판정할 수 없음.
- INVALID_PARAMETER 반환 시 "올바른 거부"로 기록할 뿐, SUCCESS 반환 시 정렬 위반 여부를 알 수 없음.

### 5. 종합 위험 평가

| 위험 등급 | 항목 | 영향 |
|-----------|------|------|
| **높음** | FSM3/FSM4 list args 크래시 | Properties 레코드 포함 trajectory에서 R37-R77 검증 누락 |
| **높음** | CLASS_AUTHORITY_UIDS FSM 간 불일치 | R07/R30/R76 판정 불일치 가능 |
| **중간** | 전원 순환 미지원 | R42/R84 완전 미검증 |
| **중간** | ANY FAIL 정책의 false positive | 단일 FSM 오판이 전체 결과에 전파 |
| **낮음** | R24/R34/R45 미구현 | 해당 시나리오의 테스트 케이스 빈도 낮을 것으로 추정 |
| **낮음** | deepcopy 성능 | 30+ 레코드에서만 체감 |

---

## 부록: 즉시 수정 권장 항목

1. **FSM3 `_extract_args()` 버그 수정** — `isinstance(args, list)` 분기 추가
2. **FSM4 `_get_method_args()` 버그 수정** — 동일 패턴 적용
3. **CLASS_AUTHORITY_UIDS 통일** — 5개 FSM 간 Admins/Users 클래스 UID를 하나의 공유 상수 모듈로 통합
4. **FSM5 `power_cycle_occurred` 트리거 구현** — Data I/O 레코드에서 전원 순환 이벤트 형식 정의 및 감지
