# Cycle 기록 - PROGRESS 및 문서 hygiene 정리

- 시각: 2026-05-26 13:35 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: 현재 문서가 rule engine + LoRA override를 현재 architecture로 오해시키지 않도록 정리한다.

## 결론

- `PROGRESS.md`의 현재 architecture 설명을 LLM-only 기준으로 교체했다.
- 과거 `Rule Engine -> UNEXPECTED_ERROR_STATUS -> LoRA override` 구조는 현재 기준으로 틀린 과거 접근이라고 명시했다.
<!-- Changed: remove obsolete setup-doc filename from archived cycle note. Why: server_access is now the server access authority. -->
- 과거 서버 setup 문서, `docs/sweep_plan.md`는 active docs root에서 `docs/archive/legacy/`로 이동했다.
- `docs/archive/`는 `cycles`, `handoff`, `legacy`, `research`, `submissions`로 세분화했다.
- `docs/current_task.md`를 active handoff 문서로 올리고, archive 내부 handoff는 과거 기록으로 분리했다.
- `configs/train_manifest.cycle7.json`, `configs/wandb_sweep.yaml`은 active 참조가 없고 `wandb_sweep.yaml`은 존재하지 않는 `tools/run_optional_sweep.py`를 가리켜 삭제했다.
- 현재 `wandb`는 사용하지 않는다.
- `tools/training/deploy_and_train.sh`는 비활성 legacy stub라 삭제했다.
- `tools/training/brier_trainer.py`는 active 학습 코드에서 import되지 않는 독립 실험 파일이라 삭제했다.
- `src`, `tools`, `tests`의 `__pycache__` 생성 산출물은 삭제했다.
- `tools/eval/prepare_submit.sh`의 다른 workspace fallback을 제거하고 repo-local 파일만 복사하게 했다.
- `tools/datagen/generate_gap_data.py`의 missing `generate_uncertainty_data.py` 안내를 현재 manifest builder 경로로 수정했다.
- `tools/eval/merge_adapters.py`는 active 호출/테스트 경로가 없는 adapter-soup 실험 도구라 삭제했다.
- `tests/test_generate_gap_data_defaults.py`를 추가해 gap datagen 기본 경로 회귀를 막았다.
- `docs/server_operations_current.md`의 GitHub/bundle fast-forward 절차에 `FETCH_HEAD` 검증과 base commit 검증을 추가했다.
- 2026-05-26 13:20:28~13:23:43 KST에 SSH 10회 재시도했으나 모두 `Operation timed out`이었다.

## 사용자 질문에 대한 판정

[Original Text/Data] `PROGRESS.md`에는 `StatefulOpalVerifier.verify_with_trace`가 먼저 판정하고 `UNEXPECTED_ERROR_STATUS`일 때 LoRA가 override한다는 구조가 있었다.
→ [Exact Interpretation] 이것은 현재 LLM-only architecture가 아니라 과거 hybrid 접근이다.
→ [Detailed Explanation/Example] 현재 제출 구조는 `src/solver.py`가 package-local LLM artifact를 직접 로드하고, rule engine fallback 없이 `pass`/`fail`을 반환해야 한다.

## Leaderboard 판단

- 제출은 여전히 no-go다.
- 서버 sync, v4.1 strict reference validation, 실제 artifact 평가, package `<12GB`, offline first-forward smoke가 아직 없다.
