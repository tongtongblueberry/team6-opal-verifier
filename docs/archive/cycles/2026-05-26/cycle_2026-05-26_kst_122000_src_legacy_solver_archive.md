# Cycle 기록 - src legacy helper solver archive

- 시각: 2026-05-26 12:20 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: active 제출 `src` 경로에서 과거 rule-context helper solver를 분리한다.

## 발견

[Original Text/Data] `src/lora_solver.py`, `src/llm_solver.py`, `src/probe_solver.py`에는 과거 rule-context 또는 low-confidence rule engine 연동 설명/코드가 남아 있었다.
→ [Exact Interpretation] 현재 `src/solver.py`가 LLM-only entrypoint이더라도, 같은 `src` root에 legacy helper solver가 남으면 architecture 상태가 혼동된다.
→ [Detailed Explanation/Example] package script는 이미 `src/solver.py`만 복사하도록 바꿨지만, repository 구조도 active path와 legacy path를 분리하는 것이 안전하다.

## 이동한 파일

- `src/lora_solver.py` → `tools/archive/legacy_rule_pipeline/src/lora_solver.py`
- `src/llm_solver.py` → `tools/archive/legacy_rule_pipeline/src/llm_solver.py`
- `src/probe_solver.py` → `tools/archive/legacy_rule_pipeline/src/probe_solver.py`
- `tools/datagen/filter_data.py` → `tools/archive/legacy_rule_pipeline/tools/datagen/filter_data.py`
- `tools/eval/eval_checkpoints.py` → `tools/archive/legacy_rule_pipeline/tools/eval/eval_checkpoints.py`
- `tools/training/train_probe.py` → `tools/archive/legacy_rule_pipeline/tools/training/train_probe.py`

## 남긴 active src

- `src/solver.py`
- `src/solver_27b.py`
- `src/spec_solver.py`
- `src/__init__.py`

## 판단

- 제출 package는 `src/solver.py`를 기준으로 만들고, helper solver는 포함하지 않는다.
- `solver_27b.py`와 `spec_solver.py`는 독립 LLM-only 후보로 남긴다.
- 이번 이동은 active manifest 학습/평가 tests에 영향을 주지 않는 구조 정리다.
- leaderboard 제출 사유는 아니다. artifact/eval/package smoke gate가 필요하다.
