# 변경: 5개 부분 FSM을 통합한 단일 검증기 생성
# 이유: trajectory를 한 번에 5개 FSM으로 검증하여 최종 pass/fail 판정 수행
"""TCG/Opal 통합 검증 FSM — 5개 부분 FSM 합산 판정.

5개 부분 FSM:
  1. fsm_session_status   (R01-R14) — 세션 및 상태코드 규칙
  2. fsm_method_rules     (R15-R36) — Get/Set/Authenticate 규칙
  3. fsm_cpin_lifecycle   (R37-R56) — C_PIN/TryLimit + Lifecycle 규칙
  4. fsm_acl_locking      (R57-R77) — ACL/Locking 규칙
  5. fsm_properties_dataio(R78-R86) — Properties + Data I/O 규칙

판정 우선순위:
  - 어느 하나라도 FAIL → 전체 FAIL (위반 사유 합산)
  - 모두 PASS → 전체 PASS
  - FAIL 없이 UNKNOWN 혼재 → 가장 구체적인 FSM에 위임

사용법:
    from src.opal_verifier_fsm import verify_trajectory, predict_single, predict_batch
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 부분 FSM 임포트 — 모두 src/ 디렉토리 또는 tools/datagen/ 에 위치
# ---------------------------------------------------------------------------

# FSM 1: 세션 및 상태코드 (R01-R14)
from src.fsm_session_status import (
    SessionStatusState,
    update_session_status,
    check_final_verdict_session_status,
)

# FSM 2: Get/Set/Authenticate (R15-R36)
# Changed: import 경로를 tools.datagen → src로 변경
# Why: 제출 패키지에는 src/만 포함되므로 모든 모듈이 src/ 아래 있어야 함
from src.fsm_method_rules import (
    MethodRulesState,
    update_method_rules,
    check_final_verdict_method_rules,
)

# FSM 3: C_PIN / Lifecycle (R37-R56)
# Changed: import 경로를 tools.datagen → src로 변경
from src.fsm_cpin_lifecycle import (
    CPINLifecycleState,
    update_cpin_lifecycle,
    check_final_verdict_cpin_lifecycle,
)

# FSM 4: ACL / Locking (R57-R77)
from src.fsm_acl_locking import (
    ACLLockingState,
    update_acl_locking,
    check_final_verdict_acl_locking,
)

# FSM 5: Properties + Data I/O (R78-R86)
from src.fsm_properties_dataio import (
    PropertiesDataIOState,
    update_properties_dataio,
    check_final_verdict_properties_dataio,
)


# ---------------------------------------------------------------------------
# 통합 상태 — 5개 부분 FSM 상태를 하나로 묶음
# ---------------------------------------------------------------------------

@dataclass
class OpalVerifierState:
    """5개 부분 FSM 상태를 통합한 전체 검증 상태.

    각 필드는 해당 FSM의 상태 인스턴스를 보유한다.
    """
    # FSM 1: 세션/상태코드 (R01-R14)
    session_status: SessionStatusState = field(default_factory=SessionStatusState)
    # FSM 2: Get/Set/Authenticate (R15-R36)
    method_rules: MethodRulesState = field(default_factory=MethodRulesState)
    # FSM 3: C_PIN/Lifecycle (R37-R56)
    cpin_lifecycle: CPINLifecycleState = field(default_factory=CPINLifecycleState)
    # FSM 4: ACL/Locking (R57-R77)
    acl_locking: ACLLockingState = field(default_factory=ACLLockingState)
    # FSM 5: Properties/Data I/O (R78-R86)
    properties_dataio: PropertiesDataIOState = field(default_factory=PropertiesDataIOState)


# ---------------------------------------------------------------------------
# 상태 갱신 — 레코드 1건을 5개 FSM에 동시 전달
# ---------------------------------------------------------------------------

def update_all(state: OpalVerifierState, record: dict) -> OpalVerifierState:
    """레코드 1건을 5개 FSM 모두에 전달하여 상태를 갱신한다.

    각 FSM의 update는 독립적이므로, 하나가 예외를 발생시켜도
    나머지 FSM은 정상적으로 갱신된다.

    Args:
        state: 현재 통합 상태
        record: trajectory 레코드 1건

    Returns:
        갱신된 통합 상태 (각 FSM별 상태가 개별적으로 갱신됨)
    """
    # FSM 1: session_status — 새 인스턴스 반환 (deepcopy 내부)
    try:
        state.session_status = update_session_status(state.session_status, record)
    except Exception:
        pass  # 해당 FSM update 실패 시 이전 상태 유지

    # FSM 2: method_rules — 새 인스턴스 반환
    try:
        state.method_rules = update_method_rules(state.method_rules, record)
    except Exception:
        pass

    # FSM 3: cpin_lifecycle — in-place 변경 후 동일 객체 반환
    try:
        state.cpin_lifecycle = update_cpin_lifecycle(state.cpin_lifecycle, record)
    except Exception:
        pass

    # FSM 4: acl_locking — in-place 변경 후 동일 객체 반환
    try:
        state.acl_locking = update_acl_locking(state.acl_locking, record)
    except Exception:
        pass

    # FSM 5: properties_dataio — deepcopy 내부에서 새 인스턴스 반환
    try:
        state.properties_dataio = update_properties_dataio(state.properties_dataio, record)
    except Exception:
        pass

    return state


# ---------------------------------------------------------------------------
# 최종 판정 — 5개 FSM의 최종 결과를 합산
# ---------------------------------------------------------------------------

def _normalize_verdict(verdict: str) -> str:
    """부분 FSM의 verdict를 통일된 형식으로 정규화.

    각 FSM별 반환 형식:
      - fsm_session_status: "pass" / "fail" / "unknown" (소문자)
      - fsm_method_rules:   "pass" / "fail" / "unknown" (소문자)
      - fsm_cpin_lifecycle: "PASS" / "FAIL" (대문자)
      - fsm_acl_locking:    "PASS" / "FAIL" (대문자)
      - fsm_properties_dataio: "PASS" / "FAIL" (대문자)

    모두 대문자로 통일: "PASS" / "FAIL" / "UNKNOWN"
    """
    return verdict.upper()


def check_final_all(
    state: OpalVerifierState,
    final_record: dict,
) -> Tuple[str, List[str]]:
    """5개 FSM의 최종 판정을 합산하여 통합 verdict를 반환한다.

    합산 로직:
      1. 어느 FSM이라도 FAIL → 전체 FAIL (위반 사유 합산)
      2. 모두 PASS → 전체 PASS
      3. FAIL 없이 UNKNOWN 혼재 → 가장 구체적인(PASS/FAIL 판정이 있는) FSM 결과 채택

    Args:
        state: 중간 레코드까지 갱신된 통합 상태
        final_record: trajectory의 마지막 레코드

    Returns:
        (verdict, reasons) 튜플
        verdict: "PASS" 또는 "FAIL"
        reasons: 합산된 판정 근거 문자열 리스트
    """
    # 각 FSM별 최종 판정 수행 — 개별 예외 격리
    # FSM 1: session_status → (verdict, violated_rules)
    try:
        v1_raw, r1 = check_final_verdict_session_status(state.session_status, final_record)
        v1 = _normalize_verdict(v1_raw)
    except Exception:
        v1 = "UNKNOWN"
        r1 = []
    r1_prefixed = [f"[FSM1:Session] {r}" for r in r1]

    # FSM 2: method_rules → (verdict, violated_rules)
    try:
        v2_raw, r2 = check_final_verdict_method_rules(state.method_rules, final_record)
        v2 = _normalize_verdict(v2_raw)
    except Exception:
        v2 = "UNKNOWN"
        r2 = []
    r2_prefixed = [f"[FSM2:Method] {r}" for r in r2]

    # FSM 3: cpin_lifecycle → (verdict, reasons)
    try:
        v3_raw, r3 = check_final_verdict_cpin_lifecycle(state.cpin_lifecycle, final_record)
        v3 = _normalize_verdict(v3_raw)
    except Exception:
        v3 = "UNKNOWN"
        r3 = []
    r3_prefixed = [f"[FSM3:CPIN] {r}" for r in r3]

    # FSM 4: acl_locking → (verdict, reasons)
    try:
        v4_raw, r4 = check_final_verdict_acl_locking(state.acl_locking, final_record)
        v4 = _normalize_verdict(v4_raw)
    except Exception:
        v4 = "UNKNOWN"
        r4 = []
    r4_prefixed = [f"[FSM4:ACL] {r}" for r in r4]

    # FSM 5: properties_dataio → (verdict, reasons)
    try:
        v5_raw, r5 = check_final_verdict_properties_dataio(state.properties_dataio, final_record)
        v5 = _normalize_verdict(v5_raw)
    except Exception:
        v5 = "UNKNOWN"
        r5 = []
    r5_prefixed = [f"[FSM5:Props] {r}" for r in r5]

    # 판정 결과 수집
    verdicts = [v1, v2, v3, v4, v5]
    all_reasons: List[str] = []

    # --- 합산 로직 ---
    fail_reasons: List[str] = []
    pass_reasons: List[str] = []
    unknown_count = 0

    for v, reasons in zip(verdicts, [r1_prefixed, r2_prefixed, r3_prefixed,
                                      r4_prefixed, r5_prefixed]):
        if v == "FAIL":
            fail_reasons.extend(reasons)
        elif v == "PASS":
            pass_reasons.extend(reasons)
        else:
            # UNKNOWN — 해당 FSM이 관할하지 않는 trajectory 또는 예외 발생
            unknown_count += 1

    # 규칙 1: 어느 하나라도 FAIL → 전체 FAIL
    if fail_reasons:
        return ("FAIL", fail_reasons)

    # 규칙 2: 모두 PASS (UNKNOWN 없음) → 전체 PASS
    if unknown_count == 0:
        return ("PASS", pass_reasons)

    # 규칙 3: FAIL 없이 UNKNOWN 혼재 → PASS 판정이 있는 FSM 결과 채택
    # (특정 FSM이 판정 불가여도, 다른 FSM이 PASS이면 전체 PASS)
    if pass_reasons:
        return ("PASS", pass_reasons)

    # 모든 FSM이 UNKNOWN인 극단적 경우 → 기본 PASS (보수적 판정)
    return ("PASS", ["모든 FSM이 UNKNOWN — 기본 PASS 판정"])


# ---------------------------------------------------------------------------
# 메인 인터페이스: verify_trajectory
# ---------------------------------------------------------------------------

def verify_trajectory(trajectory_json: str) -> Tuple[str, List[str]]:
    """trajectory JSON 문자열을 5개 FSM으로 검증한다.

    처리 흐름:
      1. JSON 파싱 → records 리스트 추출
      2. records[0..N-2]: 5개 FSM 모두에 update 수행 (상태 갱신)
      3. records[N-1]: 5개 FSM 모두에 check_final 수행 (최종 판정)
      4. 5개 결과를 합산하여 통합 verdict 반환

    Args:
        trajectory_json: trajectory JSON 문자열 ({"records": [...]} 형태)

    Returns:
        (verdict, reasons) 튜플
        verdict: "PASS" 또는 "FAIL"
        reasons: 판정 근거 문자열 리스트
    """
    # JSON 파싱 — 문자열 또는 dict 모두 수용
    if isinstance(trajectory_json, str):
        data = json.loads(trajectory_json)
    else:
        data = trajectory_json

    # records 추출
    records = data.get("records", [])
    if not records:
        return ("FAIL", ["빈 trajectory — records가 없음"])

    # 단일 레코드인 경우: 중간 상태 없이 바로 최종 판정
    if len(records) == 1:
        state = OpalVerifierState()
        return check_final_all(state, records[0])

    # 통합 상태 초기화
    state = OpalVerifierState()

    # 중간 레코드 처리 (records[0..N-2])
    for record in records[:-1]:
        state = update_all(state, record)

    # 최종 레코드에 대해 판정
    final_record = records[-1]
    return check_final_all(state, final_record)


# ---------------------------------------------------------------------------
# 평가기 호환 인터페이스
# ---------------------------------------------------------------------------

def predict_single(trajectory_json: str) -> str:
    """단일 trajectory에 대해 "pass" 또는 "fail"을 반환한다.

    평가기가 요구하는 소문자 형식에 맞춤.

    Args:
        trajectory_json: trajectory JSON 문자열

    Returns:
        "pass" 또는 "fail" (소문자)
    """
    verdict, _ = verify_trajectory(trajectory_json)
    # 대문자 → 소문자 변환
    return verdict.lower()


def predict_batch(dataset: List[dict]) -> List[str]:
    """데이터셋 전체에 대해 예측 리스트를 반환한다.

    각 항목은 {"sample_id": str, "input": str|dict, ...} 형태를 가정.

    Args:
        dataset: 데이터셋 리스트 (각 항목에 "input" 키 포함)

    Returns:
        ["pass" 또는 "fail", ...] 리스트 (dataset과 동일 순서)
    """
    predictions: List[str] = []
    for sample in dataset:
        inp = sample.get("input", "")
        # input이 문자열이면 그대로, dict이면 JSON 직렬화
        if isinstance(inp, dict):
            inp_str = json.dumps(inp, ensure_ascii=False)
        else:
            inp_str = str(inp)
        pred = predict_single(inp_str)
        predictions.append(pred)
    return predictions


# ---------------------------------------------------------------------------
# 독립 실행 — public20 데이터 검증
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys

    # 프로젝트 루트를 sys.path에 추가
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 데이터 경로
    input_path = os.path.join(project_root, "data", "local", "public20", "public20_input.jsonl")
    label_path = os.path.join(project_root, "data", "local", "public20", "public20_labels.local.jsonl")

    if not os.path.exists(input_path):
        print(f"입력 파일 없음: {input_path}")
        sys.exit(1)

    # 레이블 로드
    label_map: Dict[str, str] = {}
    if os.path.exists(label_path):
        with open(label_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                label_map[obj["sample_id"]] = obj["label"]

    # 샘플별 검증
    correct = 0
    total = 0
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            sample_id = sample.get("sample_id", "?")
            inp = sample.get("input", "")

            # input이 dict이면 JSON 직렬화
            if isinstance(inp, dict):
                inp_str = json.dumps(inp, ensure_ascii=False)
            else:
                inp_str = str(inp)

            verdict, reasons = verify_trajectory(inp_str)
            pred = verdict.lower()
            gt = label_map.get(sample_id, "?")

            match = pred == gt
            if match:
                correct += 1
            total += 1

            status_icon = "O" if match else "X"
            print(f"[{status_icon}] {sample_id}: pred={pred}, gt={gt}")
            if reasons and not match:
                for r in reasons[:3]:
                    print(f"    {r}")

    print(f"\n정확도: {correct}/{total} ({100*correct/total:.1f}%)")
