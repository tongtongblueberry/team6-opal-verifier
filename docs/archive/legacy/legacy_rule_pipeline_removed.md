# Legacy Rule Pipeline 실행 코드 삭제 기록

- 작성: 2026-05-26 15:30 KST
- 결정: `tools/archive/legacy_rule_pipeline/` 전체 실행 코드를 active repo에서 삭제한다.

## 이유

<!-- Changed: preserve only the audit reason instead of keeping executable legacy code under tools/. -->
<!-- Why: active tools searches kept surfacing old rule-engine and rule-prompt paths even though the current architecture must remain LLM-only. -->

[Original Text/Data] `tools/archive/legacy_rule_pipeline/` 아래에는 과거 rule pipeline,
rule-prompt solver, public-label eval script, `/workspace/team6` 기반 script, legacy
training pipeline code가 실행 가능한 형태로 남아 있었다.
→ [Exact Interpretation] archive라는 이름이 붙어도 active `tools/` namespace 내부에
실행 코드가 남아 검색과 agent 판단을 오염시킬 수 있다.
→ [Detailed Explanation/Example] 현재 architecture에는 rule engine, rule fallback,
rule-id prompt, public label supervised 학습이 들어가면 안 되므로, 실행 코드는 삭제하고
폐기 근거만 문서로 남긴다.

## 삭제 범위

삭제 대상 root:

- `tools/archive/legacy_rule_pipeline/`

삭제 전 파일 수:

- 43개

대표 삭제 항목:

- `tools/archive/legacy_rule_pipeline/README.md`
- `tools/archive/legacy_rule_pipeline/src/llm_solver.py`
- `tools/archive/legacy_rule_pipeline/src/lora_solver.py`
- `tools/archive/legacy_rule_pipeline/src/probe_solver.py`
- `tools/archive/legacy_rule_pipeline/src/solver_27b.py`
- `tools/archive/legacy_rule_pipeline/src/spec_solver.py`
- `tools/archive/legacy_rule_pipeline/tools/analysis/*`
- `tools/archive/legacy_rule_pipeline/tools/datagen/*`
- `tools/archive/legacy_rule_pipeline/tools/eval/*`
- `tools/archive/legacy_rule_pipeline/tools/training/*`
- `tools/archive/legacy_rule_pipeline/training/*`

## 보존하는 근거

- 과거 Rule+LoRA diagram은 active `PROGRESS.md`에서 제거했다.
- LLM-only 금지 원칙은 active `README.md`, `PROGRESS.md`, `docs/current_task.md`,
  `docs/agent_handoff.md`, `docs/current_self_instruct_data_plan.md`에 유지한다.
- v4/v4.1 데이터 폐기 근거는
  `docs/archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md`에 유지한다.
- legacy datagen 삭제 근거는 `docs/archive/legacy_datagen/README.md`에 유지한다.

## 현재 기준

현재 active code는 LLM-only 제출/학습 경로와 Self-Instruct 데이터 gate만 포함해야 한다.
과거 rule pipeline을 복구하거나 실행 코드 형태로 다시 `tools/` 아래에 두는 변경은 no-go다.
