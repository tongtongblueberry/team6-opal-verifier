#!/usr/bin/env python3
"""Knowledge distillation 학습 데이터 생성 스크립트.

Changed: rule engine의 HIGH confidence 규칙만을 사용하여 LLM 학습 데이터를 생성.
Why: LLM이 rule engine의 확실한 판단을 학습하도록 knowledge distillation 적용.
     LOW confidence 규칙(UNEXPECTED_ERROR_STATUS, DEFAULT_PASS)은 제외하여 노이즈 방지.

3가지 데이터 소스:
  1. Spec expansion — gen_all() 기반 + benign prefix padding으로 길이 다양화
  2. Template mutations — public 20 기반 mutation (status flip, truncation, challenge)
  3. Compositional scenarios — 규칙별 프로그래밍 방식 trajectory 생성

모든 케이스는 StatefulOpalVerifier로 재검증하여 HIGH confidence 규칙에 해당하는 것만 유지.

Usage:
  python tools/datagen/generate_distillation.py \
      --output /workspace/team6/training_data/distillation_data.json \
      --target-count 5000 \
      --dataset-root /dl2026/dataset
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

# Changed: 서버 환경에서 프로젝트 루트를 sys.path에 추가.
# Why: src.solver, tools.datagen 모듈 import를 위해 필요.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))
# Changed: 서버 환경 호환 — /workspace 경로도 추가.
# Why: 서버에서 실행 시 로컬 경로가 아닌 서버 경로 사용.
if Path("/workspace/team6/team6-opal-verifier").exists():
    sys.path.insert(0, "/workspace/team6/team6-opal-verifier")

Json = dict[str, Any]
random.seed(42)

# ═══════════════════════════════════════════════════════════════
# HIGH CONFIDENCE 규칙 목록 — solver.py의 HIGH_CONFIDENCE_RULES와 동일
# ═══════════════════════════════════════════════════════════════
# Changed: solver.py에서 직접 import하지 않고 여기에 복사.
# Why: 독립 실행 가능성 보장 + import 순서 문제 방지.
HIGH_CONFIDENCE_RULES = {
    "PARSE_FINAL_COMMAND", "PROPERTIES_TARGET", "PROPERTIES_PAYLOAD",
    "STARTSESSION_FINAL", "PRECONDITION_EXPECTED_ERROR", "KNOWN_FIELD_INVALID_VALUE",
    "LOCKING_DATA_ACCESS", "ACTIVATE_TARGET",
    # Changed: 추가 규칙 — method-specific payload 검증도 HIGH confidence.
    # Why: SUCCESS + 잘못된 payload는 확실한 fail 케이스.
    "STARTSESSION_EFFECT", "ENDSESSION_EFFECT", "SET_CPIN_SECRET",
    "ACTIVATE_SP_EFFECT", "WRITE_PAYLOAD_EFFECT", "GENKEY_EFFECT",
    "OBSERVE_ERROR",
    "ACTIVATE_PAYLOAD", "ENDSESSION_PAYLOAD", "SET_PAYLOAD",
    "READ_PAYLOAD", "WRITE_RESPONSE", "GENKEY_PAYLOAD", "GET_PAYLOAD",
    "AUTHENTICATE_NO_SESSION", "AUTHENTICATE_SUCCESS",
    "SET_OBJECT_FIELDS",
    "KNOWN_FIELD_EXPECTED_SUCCESS",
}

# Changed: 제외할 LOW confidence 규칙.
# Why: 이 규칙들은 노이즈가 많아 학습에 해로움.
LOW_CONFIDENCE_RULES = {
    "UNEXPECTED_ERROR_STATUS", "DEFAULT_PASS",
}


# ═══════════════════════════════════════════════════════════════
# VERIFIER 래퍼
# ═══════════════════════════════════════════════════════════════

def _get_verifier():
    """StatefulOpalVerifier 인스턴스를 생성하여 반환."""
    from src.solver import StatefulOpalVerifier
    return StatefulOpalVerifier(trace=True)


def label_with_verifier(verifier, records: list[Json]) -> dict | None:
    """records를 verifier로 검증하고 HIGH confidence 규칙에 해당하면 결과 반환.

    Changed: verify_with_trace()를 사용하여 rule_id까지 추출.
    Why: HIGH confidence 규칙에 해당하는 케이스만 유지하기 위해 trace 필요.

    Returns:
        {"prediction": "pass"|"fail", "rule_id": str} 또는 None (LOW confidence 규칙)
    """
    try:
        result = verifier.verify_with_trace(records)
    except Exception:
        return None

    prediction = result.get("prediction", "")
    trace = result.get("trace", [])

    if not prediction:
        return None

    # Changed: trace에서 마지막 규칙 ID를 추출.
    # Why: 최종 판단에 사용된 규칙이 HIGH confidence인지 확인.
    rule_id = ""
    if trace:
        # Changed: 마지막 trace entry의 rule_id 사용.
        # Why: _final_is_inconsistent()에서 마지막으로 추가된 trace가 최종 판단 규칙.
        rule_id = trace[-1].get("rule_id", "")

    # Changed: LOW confidence 규칙 필터링.
    # Why: UNEXPECTED_ERROR_STATUS, DEFAULT_PASS 케이스는 노이즈.
    if rule_id in LOW_CONFIDENCE_RULES:
        return None

    return {"prediction": prediction, "rule_id": rule_id}


# ═══════════════════════════════════════════════════════════════
# 소스 1: SPEC EXPANSION (gen_all + benign prefix padding)
# ═══════════════════════════════════════════════════════════════

def _benign_step_get_success() -> Json:
    """benign prefix용: Get SUCCESS 스텝 생성."""
    return {
        "input": {
            "method": {"name": "Get"},
            "invoking_id": {"uid": "00 00 00 0B 00 00 84 02", "name": "C_PIN_MSID"},
            "args": {"required": {"Cellblock": [{"startColumn": 3}, {"endColumn": 3}]}, "optional": {}},
        },
        "output": {
            "return_values": [{"3": "default_msid_pin"}],
            "status_codes": "SUCCESS",
        },
    }


def _benign_step_properties() -> Json:
    """benign prefix용: Properties SUCCESS 스텝 생성."""
    return {
        "input": {
            "method": {"name": "Properties"},
            "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager UID"},
            "args": {"required": {}, "optional": {}},
        },
        "output": {
            "return_values": [{"Properties": {"MaxMethods": 1, "MaxSessions": 1}}],
            "status_codes": "SUCCESS",
        },
    }


def _benign_step_set_success() -> Json:
    """benign prefix용: Set SUCCESS 스텝 (인증된 세션 내에서)."""
    return {
        "input": {
            "method": {"name": "Set"},
            "invoking_id": {"uid": "00 00 00 0B 00 01 00 01", "name": "C_PIN_Admin1"},
            "args": {"required": {"Values": [{"3": "new_pin_value"}]}, "optional": {}},
        },
        "output": {
            "return_values": [],
            "status_codes": "SUCCESS",
        },
    }


def _benign_step_get_locking() -> Json:
    """benign prefix용: Locking 테이블 Get SUCCESS 스텝."""
    return {
        "input": {
            "method": {"name": "Get"},
            "invoking_id": {"uid": "00 00 08 02 00 00 00 01", "name": "Locking_GR"},
            "args": {"required": {"Cellblock": [{"startColumn": 3}, {"endColumn": 8}]}, "optional": {}},
        },
        "output": {
            "return_values": [{"3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0}],
            "status_codes": "SUCCESS",
        },
    }


# Changed: session 내에서 사용할 수 있는 benign 스텝 목록.
# Why: prefix padding 시 세션 컨텍스트에 맞는 스텝만 사용해야 검증 통과.
BENIGN_STEPS_NO_SESSION = [_benign_step_properties]
BENIGN_STEPS_IN_SESSION = [
    _benign_step_get_success,
    _benign_step_set_success,
    _benign_step_get_locking,
]


def _has_session_start(steps: list[Json]) -> bool:
    """steps 내에 StartSession SUCCESS가 있는지 확인."""
    for step in steps:
        method = step.get("input", {}).get("method", {})
        if isinstance(method, dict):
            name = method.get("name", "").lower()
        else:
            name = str(method).lower()
        status = step.get("output", {}).get("status_codes", "")
        if isinstance(status, dict):
            status = status.get("Name", status.get("name", ""))
        if name == "startsession" and str(status).upper() == "SUCCESS":
            return True
    return False


def generate_spec_expansion(verifier, target_lengths: list[int] | None = None) -> list[dict]:
    """gen_all()의 결과를 benign prefix padding으로 길이를 확장.

    Changed: 짧은 케이스(len < 10)에 대해 다양한 target 길이로 확장.
    Why: 학습 데이터의 길이 분포를 실제 테스트 케이스와 맞추기 위함.
    """
    from tools.datagen.generate_spec_data import gen_all

    if target_lengths is None:
        target_lengths = [10, 15, 20, 25, 30]

    print("[소스1] gen_all()로 기본 케이스 생성 중...")
    base_cases = gen_all()
    print(f"  기본 케이스: {len(base_cases)}개")

    results: list[dict] = []
    padded_count = 0

    for case in base_cases:
        steps = case["steps"]
        label = case["label"]
        rule = case.get("spec_rule", "")
        desc = case.get("description", "")

        # Changed: 원본도 verifier로 재검증.
        # Why: gen_all()의 라벨이 verifier와 일치하는지 확인.
        vresult = label_with_verifier(verifier, steps)
        if vresult is not None:
            results.append({
                "records": steps,
                "label": vresult["prediction"],
                "source": f"spec:{rule}",
                "rule_id": vresult["rule_id"],
                "description": desc,
                "length": len(steps),
            })

        # Changed: 짧은 케이스만 padding 대상.
        # Why: 이미 긴 케이스는 padding 불필요.
        if len(steps) >= 10:
            continue

        has_session = _has_session_start(steps)

        for target_len in target_lengths:
            if target_len <= len(steps):
                continue

            pad_count = target_len - len(steps)
            padded_steps = []

            # Changed: 세션 유무에 따라 적절한 benign 스텝 선택.
            # Why: 세션 없이 Get/Set를 하면 verifier가 다른 규칙 적용.
            if has_session:
                # Changed: 세션이 있는 경우 StartSession 이후에 benign 스텝 삽입.
                # Why: StartSession 이전에 session 내 스텝을 넣으면 규칙 위반.
                ss_idx = -1
                for idx, s in enumerate(steps):
                    m = s.get("input", {}).get("method", {})
                    if isinstance(m, dict):
                        mn = m.get("name", "").lower()
                    else:
                        mn = str(m).lower()
                    if mn == "startsession":
                        ss_idx = idx
                        break

                if ss_idx >= 0:
                    # StartSession까지 복사
                    padded_steps = copy.deepcopy(steps[:ss_idx + 1])
                    # benign 스텝 추가 (세션 내)
                    for _ in range(pad_count):
                        factory = random.choice(BENIGN_STEPS_IN_SESSION)
                        padded_steps.append(copy.deepcopy(factory()))
                    # 나머지 원본 스텝 추가
                    padded_steps.extend(copy.deepcopy(steps[ss_idx + 1:]))
                else:
                    # StartSession을 못 찾은 경우 — 앞에 Properties 추가
                    for _ in range(pad_count):
                        padded_steps.append(copy.deepcopy(_benign_step_properties()))
                    padded_steps.extend(copy.deepcopy(steps))
            else:
                # Changed: 세션 없는 경우 앞에 Properties 스텝만 추가.
                # Why: Properties는 세션 없이도 호출 가능.
                for _ in range(pad_count):
                    padded_steps.append(copy.deepcopy(_benign_step_properties()))
                padded_steps.extend(copy.deepcopy(steps))

            # Changed: padding된 케이스를 verifier로 재검증.
            # Why: padding이 label을 바꿀 수 있으므로 반드시 재검증.
            vresult = label_with_verifier(verifier, padded_steps)
            if vresult is not None:
                results.append({
                    "records": padded_steps,
                    "label": vresult["prediction"],
                    "source": f"spec_padded:{rule}:len={target_len}",
                    "rule_id": vresult["rule_id"],
                    "description": f"{desc} (padded to {target_len})",
                    "length": len(padded_steps),
                })
                padded_count += 1

    print(f"  Spec expansion 결과: {len(results)}개 (원본 + padded {padded_count}개)")
    return results


# ═══════════════════════════════════════════════════════════════
# 소스 2: TEMPLATE MUTATIONS (public 20 기반)
# ═══════════════════════════════════════════════════════════════

def _load_public_cases(dataset_root: str) -> list[dict]:
    """public 20 테스트 케이스 로드.

    Changed: generate_mutations.py의 load_public_cases()와 유사하지만 경로 파라미터화.
    Why: CLI로 dataset_root를 지정할 수 있어야 함.
    """
    testcase_dir = Path(dataset_root) / "testcases"
    label_path = Path(dataset_root) / "label.jsonl"

    if not testcase_dir.exists() or not label_path.exists():
        print(f"  경고: public 데이터 경로 없음: {testcase_dir} 또는 {label_path}")
        return []

    labels: dict[str, str] = {}
    with label_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            labels[rec["filename"]] = str(rec["label"]).strip().lower()

    cases = []
    for path in sorted(testcase_dir.glob("tc*.json")):
        if path.name not in labels:
            continue
        with path.open() as f:
            data = json.load(f)
        if isinstance(data, dict) and "records" in data:
            records = data["records"]
        elif isinstance(data, list):
            records = data
        else:
            continue
        records = [item for item in records if isinstance(item, dict)]
        if records:
            cases.append({
                "filename": path.name,
                "records": records,
                "label": labels[path.name],
            })

    return cases


def generate_template_mutations(verifier, dataset_root: str) -> list[dict]:
    """public 20 케이스에서 mutation 생성 후 verifier로 필터링.

    Changed: generate_mutations.py의 mutation 함수를 직접 호출.
    Why: 이미 구현된 mutation 로직을 재사용하여 중복 방지.
    """
    from tools.datagen.generate_mutations import (
        mutate_status_flip,
        mutate_truncation,
        mutate_host_challenge,
        mutate_step_removal,
        mutate_return_values,
        mutate_challenge_format,
        mutate_data_read_result,
        mutate_activate_target,
    )

    print("[소스2] Public 20 기반 mutation 생성 중...")
    cases = _load_public_cases(dataset_root)
    if not cases:
        print("  경고: public 케이스를 로드할 수 없음 — mutation 건너뜀")
        return []
    print(f"  Public 케이스: {len(cases)}개")

    # Changed: 각 mutation 타입별 생성.
    # Why: 다양한 mutation 타입을 모두 사용하여 데이터 다양성 확보.
    all_mutations: list[dict] = []

    mutation_fns = [
        ("status_flip", mutate_status_flip),
        ("truncation", mutate_truncation),
        ("challenge", mutate_host_challenge),
        ("step_removal", mutate_step_removal),
        ("return_values", mutate_return_values),
        ("challenge_format", mutate_challenge_format),
        ("read_result", mutate_data_read_result),
        ("activate_target", mutate_activate_target),
    ]

    for name, fn in mutation_fns:
        try:
            mutations = fn(cases)
            print(f"  {name}: {len(mutations)}개 생성")
            all_mutations.extend(mutations)
        except Exception as e:
            print(f"  {name}: 오류 — {e}")

    # Changed: 원본 케이스도 포함.
    # Why: anchor point로 사용.
    for case in cases:
        all_mutations.append({
            "records": case["records"],
            "label": case["label"],
            "source": f"original:{case['filename']}",
            "length": len(case["records"]),
        })

    # Changed: verifier로 재검증 + HIGH confidence 필터링.
    # Why: mutation이 올바른 label을 갖는지 확인하고 LOW confidence 제외.
    results: list[dict] = []
    for mut in all_mutations:
        vresult = label_with_verifier(verifier, mut["records"])
        if vresult is not None:
            results.append({
                "records": mut["records"],
                "label": vresult["prediction"],
                "source": mut.get("source", "mutation"),
                "rule_id": vresult["rule_id"],
                "description": mut.get("source", ""),
                "length": len(mut["records"]),
            })

    print(f"  Mutation 결과 (HIGH confidence): {len(results)}개 / {len(all_mutations)}개")
    return results


# ═══════════════════════════════════════════════════════════════
# 소스 3: COMPOSITIONAL SCENARIOS
# ═══════════════════════════════════════════════════════════════

# Changed: generate_spec_data.py의 step builder를 재사용.
# Why: 동일한 step 생성 로직을 중복 구현하지 않기 위해.
from tools.datagen.generate_spec_data import (
    _ss, _m, _auth, _data,
    OBJECTS_KNOWN, OBJECTS_UNKNOWN, CLASS_AUTHORITIES, INDIV_AUTHORITIES,
    ERRORS, COL_RANGES, LBAS, SPIDS,
)


def _endsession(status: str = "SUCCESS") -> Json:
    """EndSession 스텝 생성."""
    return {
        "input": {
            "method": {"name": "EndSession"},
            "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager UID"},
            "args": {"required": {}, "optional": {}},
        },
        "output": {
            "return_values": [],
            "status_codes": status,
        },
    }


def generate_compositional_scenarios(verifier) -> list[dict]:
    """규칙별 프로그래밍 방식 trajectory 생성.

    Changed: 다양한 시나리오를 프로그래밍 방식으로 생성.
    Why: spec expansion과 mutation만으로는 커버하지 못하는 복잡한 시나리오 커버.
    """
    print("[소스3] Compositional scenario 생성 중...")
    scenarios: list[dict] = []

    ALL_OBJECTS = OBJECTS_KNOWN + OBJECTS_UNKNOWN

    # ── 시나리오 1: No-session method call (R1) ──
    # Changed: 세션 없이 Get/Set/Activate/GenKey 호출 → 에러 기대.
    # Why: 세션 없이 메서드 호출 시 NOT_AUTHORIZED 또는 다른 에러가 나와야 정상.
    print("  시나리오 1: No-session method call...")
    for method in ["Get", "Set", "Activate", "GenKey"]:
        for name, uid, _ in random.sample(ALL_OBJECTS, min(8, len(ALL_OBJECTS))):
            # 에러 응답 → pass (올바른 거부)
            for err in ERRORS:
                steps = [_m(method, name, uid, err, cols="3-3")]
                scenarios.append({"steps": steps, "desc": f"nosess_{method}_{name}_{err}"})
            # SUCCESS 응답 → fail (세션 없이 성공 = 위반)
            steps = [_m(method, name, uid, "SUCCESS", cols="3-3")]
            scenarios.append({"steps": steps, "desc": f"nosess_{method}_{name}_SUCCESS"})

    # ── 시나리오 2: Auth flow (StartSession → Authenticate → Get/Set) ──
    # Changed: 인증 흐름의 다양한 변형.
    # Why: 인증 성공/실패에 따른 후속 작업의 pass/fail을 학습.
    print("  시나리오 2: Auth flow...")
    for an, au in INDIV_AUTHORITIES[:4]:
        for n, u, _ in OBJECTS_KNOWN[:6]:
            # 정상 흐름: StartSession(auth) → Get → SUCCESS
            steps = [
                _ss(auth=True, auth_uid=au),
                _auth(an, au, "SUCCESS", True),
                _m("Get", n, u, "SUCCESS", cols="3-3"),
            ]
            scenarios.append({"steps": steps, "desc": f"auth_flow_get_ok_{an}_{n}"})

            # 정상 흐름: StartSession(auth) → Set → SUCCESS
            steps = [
                _ss(auth=True, auth_uid=au),
                _auth(an, au, "SUCCESS", True),
                _m("Set", n, u, "SUCCESS"),
            ]
            scenarios.append({"steps": steps, "desc": f"auth_flow_set_ok_{an}_{n}"})

            # 인증 실패 후 Get → NOT_AUTHORIZED (정상)
            steps = [
                _ss(auth=True, auth_uid=au),
                _auth(an, au, "SUCCESS", False),
                _m("Get", n, u, "NOT_AUTHORIZED", cols="3-3"),
            ]
            scenarios.append({"steps": steps, "desc": f"auth_fail_get_na_{an}_{n}"})

    # ── 시나리오 3: RO session write blocking ──
    # Changed: Read-Only 세션에서 write 메서드 호출 시 NOT_AUTHORIZED 기대.
    # Why: spec 3.3.7.1 — RO 세션은 영구 변경을 허용하지 않음.
    print("  시나리오 3: RO session write blocking...")
    for method in ["Set", "GenKey", "Activate"]:
        for n, u, _ in random.sample(ALL_OBJECTS, min(8, len(ALL_OBJECTS))):
            # RO + write → NOT_AUTHORIZED (정상)
            steps = [
                _ss(write=False, auth=True),
                _m(method, n, u, "NOT_AUTHORIZED"),
            ]
            scenarios.append({"steps": steps, "desc": f"ro_write_{method}_{n}_NA"})

            # RO + write → SUCCESS (위반)
            steps = [
                _ss(write=False, auth=True),
                _m(method, n, u, "SUCCESS"),
            ]
            scenarios.append({"steps": steps, "desc": f"ro_write_{method}_{n}_OK"})

    # ── 시나리오 4: Class authority mismatch ──
    # Changed: class authority로 StartSession 시도 → INVALID_PARAMETER 기대.
    # Why: spec 5.1.5.11 — class authority는 StartSession에 사용 불가.
    print("  시나리오 4: Class authority mismatch...")
    for an, au in CLASS_AUTHORITIES:
        for spid in SPIDS:
            # IP 응답 (정상)
            steps = [_ss(auth=True, auth_uid=au, spid=spid, status="INVALID_PARAMETER")]
            scenarios.append({"steps": steps, "desc": f"class_auth_{an}_{spid}_IP"})

            # SUCCESS 응답 (위반)
            steps = [_ss(auth=True, auth_uid=au, spid=spid, status="SUCCESS")]
            scenarios.append({"steps": steps, "desc": f"class_auth_{an}_{spid}_OK"})

            # 긴 버전: class auth → IP 후 individual auth로 재시도 성공
            for ian, iau in INDIV_AUTHORITIES[:2]:
                steps = [
                    _ss(auth=True, auth_uid=au, spid=spid, status="INVALID_PARAMETER"),
                    _ss(auth=True, auth_uid=iau, spid=spid, status="SUCCESS"),
                    _m("Get", "C_PIN_Admin1", "00 00 00 0B 00 01 00 01", "SUCCESS", cols="3-3"),
                ]
                scenarios.append({"steps": steps, "desc": f"class_retry_{an}_{ian}"})

    # ── 시나리오 5: Locking scenarios ──
    # Changed: Locking 테이블 설정 후 데이터 접근.
    # Why: ReadLocked/WriteLocked 상태에서 데이터 접근 시 에러 기대.
    print("  시나리오 5: Locking scenarios...")
    for lba in LBAS[:4]:
        # ReadLockEnabled=True, ReadLocked=True → Read 실패 (정상)
        steps = [
            _ss(auth=True),
            _m("Set", "Locking_GR", "00 00 08 02 00 00 00 01", "SUCCESS",
               vals=[{"5": True, "7": True}]),
            _endsession(),
            _data("Read", lba, "FAIL"),
        ]
        scenarios.append({"steps": steps, "desc": f"locked_read_fail_{lba}"})

        # ReadLockEnabled=True, ReadLocked=True → Read 성공 (위반)
        steps = [
            _ss(auth=True),
            _m("Set", "Locking_GR", "00 00 08 02 00 00 00 01", "SUCCESS",
               vals=[{"5": True, "7": True}]),
            _endsession(),
            _data("Read", lba, "Success", result="data"),
        ]
        scenarios.append({"steps": steps, "desc": f"locked_read_ok_{lba}"})

        # WriteLockEnabled=True, WriteLocked=True → Write 실패 (정상)
        steps = [
            _ss(auth=True),
            _m("Set", "Locking_GR", "00 00 08 02 00 00 00 01", "SUCCESS",
               vals=[{"6": True, "8": True}]),
            _endsession(),
            _data("Write", lba, "FAIL", payload="0xAA"),
        ]
        scenarios.append({"steps": steps, "desc": f"locked_write_fail_{lba}"})

        # WriteLockEnabled=True, WriteLocked=True → Write 성공 (위반)
        steps = [
            _ss(auth=True),
            _m("Set", "Locking_GR", "00 00 08 02 00 00 00 01", "SUCCESS",
               vals=[{"6": True, "8": True}]),
            _endsession(),
            _data("Write", lba, "Success", payload="0xAA"),
        ]
        scenarios.append({"steps": steps, "desc": f"locked_write_ok_{lba}"})

    # ── 시나리오 6: Multi-session scenarios ──
    # Changed: 여러 세션을 순차적으로 열고 닫는 시나리오.
    # Why: 세션 관리의 복잡한 상태 전이를 학습.
    print("  시나리오 6: Multi-session scenarios...")
    for an, au in INDIV_AUTHORITIES[:3]:
        for n, u, _ in OBJECTS_KNOWN[:4]:
            # 세션1 → Get → EndSession → 세션2 → Set → EndSession
            steps = [
                _ss(auth=True, auth_uid=au),
                _m("Get", n, u, "SUCCESS", cols="3-3"),
                _endsession(),
                _ss(auth=True, auth_uid=au),
                _m("Set", n, u, "SUCCESS"),
                _endsession(),
            ]
            scenarios.append({"steps": steps, "desc": f"multi_sess_{an}_{n}_ok"})

            # 세션1 → EndSession → 세션 없이 Set → 에러 (정상)
            steps = [
                _ss(auth=True, auth_uid=au),
                _m("Get", n, u, "SUCCESS", cols="3-3"),
                _endsession(),
                _m("Set", n, u, "NOT_AUTHORIZED"),
            ]
            scenarios.append({"steps": steps, "desc": f"multi_sess_{an}_{n}_nosess"})

    # ── 시나리오 7: Data consistency (Write → GenKey → Read) ──
    # Changed: GenKey 후 Read 결과가 이전 Write 데이터와 달라야 정상.
    # Why: GenKey는 암호화 키를 재생성하여 기존 데이터를 읽을 수 없게 만듦.
    print("  시나리오 7: Data consistency (Write → GenKey → Read)...")
    for lba in LBAS[:4]:
        for pat in ["0xAA", "0xBB"]:
            # Write → GenKey → Read (random data) → pass
            steps = [
                _ss(auth=True),
                _data("Write", lba, "Success", payload=pat),
                _m("GenKey", "K_AES_256", "00 00 08 06 00 03 00 01", "SUCCESS"),
                _endsession(),
                _data("Read", lba, "Success", result="Random Data"),
            ]
            scenarios.append({"steps": steps, "desc": f"genkey_read_random_{lba}_{pat}"})

            # Write → GenKey → Read (old pattern) → fail
            steps = [
                _ss(auth=True),
                _data("Write", lba, "Success", payload=pat),
                _m("GenKey", "K_AES_256", "00 00 08 06 00 03 00 01", "SUCCESS"),
                _endsession(),
                _data("Read", lba, "Success", result=pat),
            ]
            scenarios.append({"steps": steps, "desc": f"genkey_read_old_{lba}_{pat}"})

    # ── 시나리오 8: Properties + StartSession 긴 흐름 ──
    # Changed: Properties → StartSession → 여러 Get/Set → EndSession.
    # Why: 실제 테스트 케이스와 유사한 긴 trajectory 생성.
    print("  시나리오 8: Long auth flows...")
    for an, au in INDIV_AUTHORITIES[:3]:
        objects_sample = random.sample(OBJECTS_KNOWN, min(4, len(OBJECTS_KNOWN)))
        for final_status in ["SUCCESS", "NOT_AUTHORIZED", "INVALID_PARAMETER"]:
            steps = [
                _benign_step_properties(),
                _ss(auth=True, auth_uid=au),
            ]
            for n, u, _ in objects_sample[:-1]:
                steps.append(_m("Get", n, u, "SUCCESS", cols="3-3"))
            # 마지막 스텝에 final_status 적용
            fn, fu, _ = objects_sample[-1]
            steps.append(_m("Get", fn, fu, final_status, cols="3-3"))
            scenarios.append({"steps": steps, "desc": f"long_auth_{an}_{final_status}"})

    # ── 시나리오 9: Authenticate 관련 ──
    # Changed: Authenticate 메서드의 다양한 변형.
    # Why: Authenticate SUCCESS/False, class authority 등의 케이스 커버.
    print("  시나리오 9: Authenticate scenarios...")
    for an, au in CLASS_AUTHORITIES:
        steps = [
            _ss(auth=True),
            _auth(an, au, "INVALID_PARAMETER", None),
        ]
        scenarios.append({"steps": steps, "desc": f"auth_class_{an}_IP"})

        steps = [
            _ss(auth=True),
            _auth(an, au, "SUCCESS", True),
        ]
        scenarios.append({"steps": steps, "desc": f"auth_class_{an}_OK"})

    # Authenticate without session
    for an, au in INDIV_AUTHORITIES[:3]:
        steps = [_auth(an, au, "SUCCESS", True)]
        scenarios.append({"steps": steps, "desc": f"auth_no_session_{an}"})

    # Anybody authority
    steps = [
        _ss(auth=True),
        _auth("Anybody", "00 00 00 09 00 00 00 01", "SUCCESS", True),
    ]
    scenarios.append({"steps": steps, "desc": "auth_anybody_true"})
    steps = [
        _ss(auth=True),
        _auth("Anybody", "00 00 00 09 00 00 00 01", "SUCCESS", False),
    ]
    scenarios.append({"steps": steps, "desc": "auth_anybody_false"})

    # ── 시나리오 10: 다양한 길이의 Properties-only 흐름 ──
    # Changed: Properties만으로 구성된 다양한 길이 trajectory.
    # Why: 간단한 pass 케이스의 길이 분포를 채우기 위해.
    print("  시나리오 10: Various length Properties flows...")
    for length in [5, 8, 12, 18, 25]:
        steps = []
        for _ in range(length - 1):
            steps.append(copy.deepcopy(_benign_step_properties()))
        # 마지막 Properties
        steps.append(copy.deepcopy(_benign_step_properties()))
        scenarios.append({"steps": steps, "desc": f"props_only_len{length}"})

        # 마지막에 잘못된 Properties
        steps2 = []
        for _ in range(length - 1):
            steps2.append(copy.deepcopy(_benign_step_properties()))
        bad_props = copy.deepcopy(_benign_step_properties())
        bad_props["output"]["return_values"] = []
        steps2.append(bad_props)
        scenarios.append({"steps": steps2, "desc": f"props_bad_last_len{length}"})

    # Changed: 모든 시나리오를 verifier로 검증하고 HIGH confidence만 유지.
    # Why: 프로그래밍 방식으로 생성한 label이 verifier와 다를 수 있음.
    print(f"  총 시나리오: {len(scenarios)}개 — verifier로 검증 중...")
    results: list[dict] = []
    for sc in scenarios:
        vresult = label_with_verifier(verifier, sc["steps"])
        if vresult is not None:
            results.append({
                "records": sc["steps"],
                "label": vresult["prediction"],
                "source": f"compositional:{sc['desc']}",
                "rule_id": vresult["rule_id"],
                "description": sc["desc"],
                "length": len(sc["steps"]),
            })

    print(f"  Compositional 결과 (HIGH confidence): {len(results)}개 / {len(scenarios)}개")
    return results


# ═══════════════════════════════════════════════════════════════
# BALANCING + OUTPUT
# ═══════════════════════════════════════════════════════════════

def balance_data(
    data: list[dict],
    target_count: int,
) -> list[dict]:
    """pass/fail 50:50 밸런싱 + 길이 분포 보정.

    Changed: target 길이 분포에 맞추어 데이터 샘플링.
    Why: 테스트 셋과 유사한 길이 분포를 유지해야 LLM이 올바르게 학습.

    길이 분포 목표:
      1-5:  ~10%
      6-10: ~20%
      11-20: ~20%
      21-30: ~30%
      31+:  ~20%
    """
    LENGTH_BINS = [
        (1, 5, 0.10),
        (6, 10, 0.20),
        (11, 20, 0.20),
        (21, 30, 0.30),
        (31, 999, 0.20),
    ]

    # Changed: pass/fail 분리.
    pass_data = [d for d in data if d["label"] == "pass"]
    fail_data = [d for d in data if d["label"] == "fail"]

    print(f"\n[밸런싱] 입력: pass={len(pass_data)}, fail={len(fail_data)}, 합계={len(data)}")
    print(f"  목표: {target_count}개 (pass:fail = 50:50)")

    target_per_label = target_count // 2
    balanced: list[dict] = []

    for label_name, pool in [("pass", pass_data), ("fail", fail_data)]:
        # Changed: 길이 분포별 할당량 계산.
        random.shuffle(pool)

        # Changed: 각 bin에 해당하는 데이터 분류.
        binned: list[list[dict]] = [[] for _ in LENGTH_BINS]
        for d in pool:
            length = d["length"]
            for i, (lo, hi, _) in enumerate(LENGTH_BINS):
                if lo <= length <= hi:
                    binned[i].append(d)
                    break

        # Changed: 각 bin에서 목표 비율만큼 샘플링.
        selected: list[dict] = []
        remaining_target = target_per_label

        for i, (lo, hi, ratio) in enumerate(LENGTH_BINS):
            bin_target = int(target_per_label * ratio)
            available = binned[i]

            if len(available) >= bin_target:
                selected.extend(random.sample(available, bin_target))
            else:
                # Changed: 부족하면 전체 사용.
                selected.extend(available)
                # Changed: 부족분은 다른 bin에서 채우기.
                remaining_target = target_per_label - len(selected)

            bin_actual = min(len(available), bin_target)
            print(f"  {label_name} bin [{lo}-{hi}]: 목표={bin_target}, 가용={len(available)}, 선택={bin_actual}")

        # Changed: 목표 미달 시 나머지 bin에서 추가 샘플링.
        if len(selected) < target_per_label:
            already = set(id(d) for d in selected)
            extras = [d for d in pool if id(d) not in already]
            need = target_per_label - len(selected)
            if extras:
                selected.extend(random.sample(extras, min(need, len(extras))))

        # Changed: 초과 시 잘라냄.
        if len(selected) > target_per_label:
            selected = selected[:target_per_label]

        balanced.extend(selected)

    random.shuffle(balanced)

    # Changed: 최종 통계 출력.
    n_pass = sum(1 for d in balanced if d["label"] == "pass")
    n_fail = sum(1 for d in balanced if d["label"] == "fail")
    print(f"\n[밸런싱 결과] pass={n_pass}, fail={n_fail}, 합계={len(balanced)}")

    # Changed: 길이 분포 확인.
    for lo, hi, target_ratio in LENGTH_BINS:
        count = sum(1 for d in balanced if lo <= d["length"] <= hi)
        actual_ratio = count / len(balanced) if balanced else 0
        print(f"  len [{lo:>2}-{hi:>3}]: {count:>5}개 ({actual_ratio:.1%}, 목표={target_ratio:.0%})")

    return balanced


def save_results(data: list[dict], output_path: str) -> None:
    """결과를 JSON으로 저장.

    Changed: 학습에 필요한 필드만 포함하여 파일 크기 최소화.
    Why: records, label, source만 필요. rule_id, description은 디버깅용.
    """
    output = []
    for d in data:
        output.append({
            "records": d["records"],
            "label": d["label"],
            "source": d.get("source", "unknown"),
            "rule_id": d.get("rule_id", ""),
            "length": d.get("length", len(d["records"])),
        })

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"\n저장 완료: {out_path} ({len(output)}개, {size_kb:.1f} KB)")


def save_checkpoint(data: list[dict], checkpoint_path: str, source_name: str) -> None:
    """중간 결과를 체크포인트로 저장 (재개 가능).

    Changed: 소스별 중간 결과를 개별 파일로 저장.
    Why: 장시간 실행 시 중단되더라도 재개 가능.
    """
    out_path = Path(checkpoint_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "source": source_name,
        "count": len(data),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": [{
            "records": d["records"],
            "label": d["label"],
            "source": d.get("source", ""),
            "rule_id": d.get("rule_id", ""),
            "length": d.get("length", len(d["records"])),
        } for d in data],
    }
    out_path.write_text(json.dumps(checkpoint, indent=2, default=str), encoding="utf-8")
    print(f"  체크포인트 저장: {out_path} ({len(data)}개)")


def load_checkpoint(checkpoint_path: str) -> list[dict] | None:
    """체크포인트에서 중간 결과 로드.

    Returns:
        데이터 리스트 또는 None (파일 없음).
    """
    path = Path(checkpoint_path)
    if not path.exists():
        return None
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        data = checkpoint.get("data", [])
        print(f"  체크포인트 로드: {path} ({len(data)}개, {checkpoint.get('source', '?')})")
        return data
    except Exception as e:
        print(f"  체크포인트 로드 실패: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge distillation 학습 데이터 생성"
    )
    parser.add_argument(
        "--output", type=str,
        default="/workspace/team6/training_data/distillation_data.json",
        help="출력 JSON 파일 경로",
    )
    parser.add_argument(
        "--target-count", type=int, default=5000,
        help="목표 데이터 수 (기본값: 5000)",
    )
    parser.add_argument(
        "--dataset-root", type=str, default="/dl2026/dataset",
        help="public 데이터셋 루트 경로 (기본값: /dl2026/dataset)",
    )
    parser.add_argument(
        "--checkpoint-dir", type=str, default=None,
        help="체크포인트 디렉토리 (기본값: output 파일과 같은 디렉토리)",
    )
    parser.add_argument(
        "--skip-spec", action="store_true",
        help="Spec expansion 단계 건너뛰기",
    )
    parser.add_argument(
        "--skip-mutations", action="store_true",
        help="Template mutations 단계 건너뛰기",
    )
    parser.add_argument(
        "--skip-compositional", action="store_true",
        help="Compositional scenarios 단계 건너뛰기",
    )

    args = parser.parse_args()

    checkpoint_dir = args.checkpoint_dir or str(Path(args.output).parent)

    print("=" * 60)
    print("Knowledge Distillation 데이터 생성")
    print("=" * 60)
    print(f"  출력: {args.output}")
    print(f"  목표: {args.target_count}개")
    print(f"  데이터셋 루트: {args.dataset_root}")
    print(f"  체크포인트: {checkpoint_dir}")
    print()

    # Changed: verifier 초기화.
    # Why: 모든 소스에서 공유하는 단일 verifier 인스턴스.
    print("StatefulOpalVerifier 초기화 중...")
    verifier = _get_verifier()
    print("  완료")
    print()

    all_data: list[dict] = []
    t0 = time.time()

    # ── 소스 1: Spec expansion ──
    if not args.skip_spec:
        ckpt_path = Path(checkpoint_dir) / "ckpt_spec.json"
        cached = load_checkpoint(str(ckpt_path))
        if cached is not None:
            spec_data = cached
            print(f"  Spec expansion: 체크포인트에서 {len(spec_data)}개 로드됨")
        else:
            spec_data = generate_spec_expansion(verifier)
            save_checkpoint(spec_data, str(ckpt_path), "spec_expansion")
        all_data.extend(spec_data)
        print(f"  누적: {len(all_data)}개 ({time.time() - t0:.1f}초)")
        print()

    # ── 소스 2: Template mutations ──
    if not args.skip_mutations:
        ckpt_path = Path(checkpoint_dir) / "ckpt_mutations.json"
        cached = load_checkpoint(str(ckpt_path))
        if cached is not None:
            mutation_data = cached
            print(f"  Template mutations: 체크포인트에서 {len(mutation_data)}개 로드됨")
        else:
            mutation_data = generate_template_mutations(verifier, args.dataset_root)
            save_checkpoint(mutation_data, str(ckpt_path), "template_mutations")
        all_data.extend(mutation_data)
        print(f"  누적: {len(all_data)}개 ({time.time() - t0:.1f}초)")
        print()

    # ── 소스 3: Compositional scenarios ──
    if not args.skip_compositional:
        ckpt_path = Path(checkpoint_dir) / "ckpt_compositional.json"
        cached = load_checkpoint(str(ckpt_path))
        if cached is not None:
            comp_data = cached
            print(f"  Compositional scenarios: 체크포인트에서 {len(comp_data)}개 로드됨")
        else:
            comp_data = generate_compositional_scenarios(verifier)
            save_checkpoint(comp_data, str(ckpt_path), "compositional_scenarios")
        all_data.extend(comp_data)
        print(f"  누적: {len(all_data)}개 ({time.time() - t0:.1f}초)")
        print()

    # ── 통계 ──
    print("=" * 60)
    print("밸런싱 전 통계")
    print("=" * 60)

    n_pass = sum(1 for d in all_data if d["label"] == "pass")
    n_fail = sum(1 for d in all_data if d["label"] == "fail")
    print(f"  총 데이터: {len(all_data)}개 (pass={n_pass}, fail={n_fail})")

    # Changed: 소스별 통계.
    source_types = Counter()
    for d in all_data:
        src = d.get("source", "unknown").split(":")[0]
        source_types[src] += 1
    print("  소스별:")
    for src, count in source_types.most_common():
        print(f"    {src}: {count}개")

    # Changed: 규칙별 통계.
    rule_types = Counter(d.get("rule_id", "unknown") for d in all_data)
    print("  규칙별 (상위 15):")
    for rule, count in rule_types.most_common(15):
        print(f"    {rule}: {count}개")

    # Changed: 길이 분포.
    lengths = [d["length"] for d in all_data]
    if lengths:
        print(f"  길이: min={min(lengths)}, max={max(lengths)}, "
              f"mean={sum(lengths)/len(lengths):.1f}")

    # ── 밸런싱 ──
    print()
    balanced = balance_data(all_data, args.target_count)

    # ── 저장 ──
    save_results(balanced, args.output)

    # ── 최종 통계 ──
    elapsed = time.time() - t0
    print(f"\n총 소요 시간: {elapsed:.1f}초")
    print("완료.")


if __name__ == "__main__":
    main()
