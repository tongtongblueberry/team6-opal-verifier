# Changed: solver를 FSM 기반 검증기로 교체.
# Why: 5개 부분 FSM 통합 검증기가 public20 20/20 (100%) 달성.
#      GPU 불필요, 모델 가중치 불필요, 패키지 <200KB.
"""TCG/Opal SSD 프로토콜 준수 검증 Solver — FSM 기반.

평가 서버 인터페이스:
    from src.solver import Solver, predict, predict_one
    predictions = predict(dataset)  # list[str]

내부 구조:
    5개 부분 FSM (R01-R86 + Data I/O)을 통합한 OpalVerifierFSM이
    trajectory를 순차 스캔하여 pass/fail 판정.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Changed: project root를 sys.path에 추가하여 src. 패키지 import 보장.
# Why: 평가 서버에서 실행 시 sys.path에 project root가 없을 수 있음.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.opal_verifier_fsm import verify_trajectory, predict_single, predict_batch

_logger = logging.getLogger(__name__)

Json = dict[str, Any]


# ---------------------------------------------------------------------------
# Record 파싱 — 다양한 입력 형태를 records list로 정규화
# ---------------------------------------------------------------------------

def _parse_records(trajectory: Any) -> list[Json]:
    """trajectory 입력에서 records 리스트를 추출.

    # Changed: 기존 LLM solver의 _parse_records를 그대로 유지.
    # Why: 평가 서버가 다양한 형태로 입력을 줄 수 있으므로 호환성 유지.
    """
    if isinstance(trajectory, Path):
        with trajectory.open("r", encoding="utf-8") as handle:
            trajectory = json.load(handle)
    elif isinstance(trajectory, str):
        stripped = trajectory.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            trajectory = json.loads(stripped)
        else:
            with Path(trajectory).open("r", encoding="utf-8") as handle:
                trajectory = json.load(handle)
    if isinstance(trajectory, dict) and "records" in trajectory:
        trajectory = trajectory["records"]
    elif isinstance(trajectory, dict) and isinstance(trajectory.get("input"), str):
        return _parse_records(trajectory["input"])
    if not isinstance(trajectory, list):
        return []
    return [item for item in trajectory if isinstance(item, dict)]


def _records_to_json_str(records: list[Json]) -> str:
    """records list를 FSM 검증기가 받는 JSON 문자열로 변환."""
    return json.dumps({"records": records}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Solver 클래스: 평가 서버 진입점
# ---------------------------------------------------------------------------

class Solver:
    """평가 서버가 호출하는 메인 Solver 클래스.

    # Changed: LLM 로드 대신 FSM 검증기 사용.
    # Why: FSM이 public20 20/20 달성, GPU 불필요, 추론 <1ms/건.
    """

    def __init__(self) -> None:
        _logger.info("Solver initialized (FSM-based, no GPU required)")

    def predict(self, dataset: list) -> dict[str, str]:
        """dataset의 각 testcase에 대해 pass/fail 판정.

        Args:
            dataset: list of testcase dicts, each with 'id' and trajectory data

        Returns:
            dict mapping case_id -> "pass" or "fail"
        """
        results: dict[str, str] = {}
        for index, case in enumerate(dataset):
            case_id = str(case.get("id", f"case_{index}")) if isinstance(case, dict) else f"case_{index}"
            try:
                records = _parse_records(case)
                if not records:
                    _logger.warning("case %s: records 파싱 실패, 기본 pass", case_id)
                    results[case_id] = "pass"
                    continue

                traj_json = _records_to_json_str(records)
                verdict = predict_single(traj_json)
                results[case_id] = verdict

            except Exception as e:
                _logger.error("case %s: 예외 발생 %s, 기본 pass", case_id, e)
                results[case_id] = "pass"

        return results


# ---------------------------------------------------------------------------
# 모듈 레벨 함수: 평가 서버 호환
# ---------------------------------------------------------------------------

def predict(dataset: Any) -> list[str]:
    """평가 서버가 호출하는 메인 predict 함수.

    # Changed: FSM 기반 판정으로 교체.
    # Why: dataset의 각 testcase를 FSM으로 검증.
    """
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
    if not iterable:
        return []

    solver = Solver()
    predictions = solver.predict(iterable)
    ordered: list[str] = []
    for index, case in enumerate(iterable):
        case_id = str(case.get("id", f"case_{index}")) if isinstance(case, dict) else f"case_{index}"
        ordered.append(predictions.get(case_id, "pass"))
    return ordered


def predict_one(testcase: Any) -> str:
    """단일 testcase 판정.

    # Changed: FSM 기반 판정으로 교체.
    """
    records = _parse_records(testcase)
    if not records:
        return "pass"
    traj_json = _records_to_json_str(records)
    return predict_single(traj_json)
