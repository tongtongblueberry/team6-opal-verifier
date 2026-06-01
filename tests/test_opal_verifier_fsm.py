# 변경: 통합 FSM 검증기의 public20 정확도 테스트 스크립트 생성
# 이유: 5개 부분 FSM을 통합한 OpalVerifierFSM이 public20 20건에 대해 올바르게 판정하는지 확인
"""통합 FSM 검증기 테스트 — public20 데이터 20건 검증.

사용법:
    프로젝트 루트에서 실행:
    python -m tests.test_opal_verifier_fsm
    또는:
    python tests/test_opal_verifier_fsm.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# 프로젝트 루트를 sys.path에 추가 (독립 실행 시 필요)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 통합 검증기 임포트
from src.opal_verifier_fsm import (
    OpalVerifierState,
    verify_trajectory,
    predict_single,
    predict_batch,
)


# ---------------------------------------------------------------------------
# 데이터 로드 유틸리티
# ---------------------------------------------------------------------------

def _load_public20() -> Tuple[List[dict], Dict[str, str]]:
    """public20 데이터와 레이블을 로드한다.

    Returns:
        (samples, label_map)
        samples: 샘플 리스트 [{sample_id, input, source}, ...]
        label_map: {sample_id: "pass"|"fail"}
    """
    input_path = _PROJECT_ROOT / "data" / "local" / "public20" / "public20_input.jsonl"
    label_path = _PROJECT_ROOT / "data" / "local" / "public20" / "public20_labels.local.jsonl"

    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일 없음: {input_path}")

    # 샘플 로드
    samples: List[dict] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))

    # 레이블 로드
    label_map: Dict[str, str] = {}
    if label_path.exists():
        with open(label_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                label_map[obj["sample_id"]] = obj["label"]

    return samples, label_map


# ---------------------------------------------------------------------------
# 테스트 함수
# ---------------------------------------------------------------------------

def test_verify_trajectory_public20() -> None:
    """public20 20건에 대해 verify_trajectory를 실행하고 정확도를 출력한다."""
    samples, label_map = _load_public20()

    correct = 0
    total = 0
    errors: List[str] = []

    print("=" * 70)
    print("통합 FSM 검증기 (OpalVerifierFSM) — public20 테스트")
    print("=" * 70)

    for sample in samples:
        sample_id = sample.get("sample_id", "?")
        inp = sample.get("input", "")

        # input이 dict이면 JSON 직렬화
        if isinstance(inp, dict):
            inp_str = json.dumps(inp, ensure_ascii=False)
        else:
            inp_str = str(inp)

        # 검증 실행
        try:
            verdict, reasons = verify_trajectory(inp_str)
            pred = verdict.lower()
        except Exception as e:
            pred = "error"
            reasons = [f"예외 발생: {type(e).__name__}: {e}"]

        gt = label_map.get(sample_id, "?")
        match = pred == gt
        if match:
            correct += 1
        total += 1

        # 결과 출력
        status_icon = "O" if match else "X"
        print(f"  [{status_icon}] {sample_id:>5s}: pred={pred:>5s}  gt={gt:>5s}", end="")
        if not match:
            # 불일치 시 첫 번째 사유 출력
            if reasons:
                print(f"  | {reasons[0][:80]}", end="")
            errors.append(sample_id)
        print()

    # 요약 출력
    print("-" * 70)
    accuracy = 100 * correct / total if total > 0 else 0.0
    print(f"정확도: {correct}/{total} ({accuracy:.1f}%)")

    if errors:
        print(f"불일치 샘플: {', '.join(errors)}")

    print("=" * 70)

    # 정확도 검증 (최소 기대치 — 참고용, assert 아님)
    if accuracy < 50.0:
        print(f"[경고] 정확도 {accuracy:.1f}%가 50% 미만 — FSM 통합 로직 확인 필요")


def test_predict_single_format() -> None:
    """predict_single이 소문자 "pass"/"fail"만 반환하는지 확인한다."""
    samples, label_map = _load_public20()

    print("\n--- predict_single 포맷 검증 ---")
    for sample in samples[:5]:
        inp = sample.get("input", "")
        if isinstance(inp, dict):
            inp_str = json.dumps(inp, ensure_ascii=False)
        else:
            inp_str = str(inp)

        result = predict_single(inp_str)
        assert result in ("pass", "fail"), (
            f"predict_single 반환값이 'pass'/'fail'이 아님: {result}"
        )
        print(f"  {sample.get('sample_id', '?')}: {result} (OK)")

    print("  predict_single 포맷 검증 통과")


def test_predict_batch_length() -> None:
    """predict_batch가 입력과 동일한 길이의 리스트를 반환하는지 확인한다."""
    samples, _ = _load_public20()

    print("\n--- predict_batch 길이 검증 ---")
    results = predict_batch(samples)
    assert len(results) == len(samples), (
        f"predict_batch 결과 길이 불일치: {len(results)} != {len(samples)}"
    )
    print(f"  predict_batch: {len(results)}건 반환 (입력 {len(samples)}건과 일치)")

    # 모든 항목이 "pass"/"fail"인지 확인
    for i, r in enumerate(results):
        assert r in ("pass", "fail"), (
            f"predict_batch[{i}] 반환값이 'pass'/'fail'이 아님: {r}"
        )
    print("  predict_batch 포맷 검증 통과")


def test_verify_trajectory_detailed_reasons() -> None:
    """각 샘플에 대해 5개 FSM의 상세 사유를 출력한다 (디버깅용)."""
    samples, label_map = _load_public20()

    print("\n--- 상세 사유 출력 (불일치 샘플만) ---")
    for sample in samples:
        sample_id = sample.get("sample_id", "?")
        inp = sample.get("input", "")

        if isinstance(inp, dict):
            inp_str = json.dumps(inp, ensure_ascii=False)
        else:
            inp_str = str(inp)

        try:
            verdict, reasons = verify_trajectory(inp_str)
            pred = verdict.lower()
        except Exception as e:
            pred = "error"
            reasons = [f"예외: {e}"]

        gt = label_map.get(sample_id, "?")
        if pred != gt:
            print(f"\n  {sample_id}: pred={pred}, gt={gt}")
            for r in reasons:
                print(f"    -> {r}")


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_verify_trajectory_public20()
    test_predict_single_format()
    test_predict_batch_length()
    test_verify_trajectory_detailed_reasons()
