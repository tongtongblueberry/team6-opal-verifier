# Cycle 기록 - 제출 패키지 legacy helper solver guard

- 시각: 2026-05-26 12:15 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: 제출 패키지에 과거 rule-context helper solver가 들어가는 경로를 차단한다.

## 발견

[Original Text/Data] `tools/eval/prepare_submit.sh`와 `tools/eval/prepare_submission.sh`가 `src/lora_solver.py`를 제출 패키지에 복사하고 있었다.
→ [Exact Interpretation] 현재 `src/solver.py`는 LLM-only 인라인 구현이지만, package에 legacy helper solver가 함께 들어갈 수 있었다.
→ [Detailed Explanation/Example] `src/lora_solver.py`에는 과거 rule-context prompt와 `rule_id` 관련 코드가 남아 있으므로, architecture 원칙상 제출 패키지에 포함하지 않는 편이 안전하다.

## 변경

- `tools/eval/prepare_submit.sh`
  - `src/lora_solver.py` 복사를 제거했다.
  - 제출 패키지 안에 `src/lora_solver.py`가 있으면 error로 처리한다.
- `tools/eval/prepare_submission.sh`
  - `src/solver.py`만 복사하도록 바꿨다.
- `tools/eval/check_submit_package.py`
  - 기존 `src/solver.py` 검사에 더해 패키지의 모든 `src/*.py` 파일을 no-rule marker 대상으로 검사한다.
- `tests/test_submit_package_readiness.py`
  - helper source에 `rule_id`가 들어가면 readiness가 실패하는 테스트를 추가했다.

## 판단

- 현재 제출 entrypoint는 `src/solver.py` 단일 파일이어야 한다.
- `src/lora_solver.py`, `src/llm_solver.py`, `src/probe_solver.py` 등 과거 후보 solver는 제출 package에 포함하지 않는다.
- 이 변경만으로 leaderboard 제출 사유는 생기지 않는다. artifact/eval/smoke gate가 여전히 필요하다.
