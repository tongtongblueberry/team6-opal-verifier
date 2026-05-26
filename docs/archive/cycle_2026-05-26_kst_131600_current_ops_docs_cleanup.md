# Cycle 기록 - 현재 운영 문서 정리

- 시각: 2026-05-26 13:16 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: active 문서가 legacy rule-engine, `/workspace/team6`, `sshpass` 운영 절차를 현재 지침처럼 보이지 않게 정리한다.

## 결론

- `README.md`를 LLM-only 현재 구조 중심으로 교체했다.
- `docs/server_operations_current.md`를 추가해 현재 서버 접속, sync, 평가, 제출 판단 절차를 한글로 기록했다.
- `docs/server_setup.md`와 `docs/sweep_plan.md`에는 legacy 경고를 추가했다.
- 2026-05-26 13:11:56~13:15:11 KST에 SSH 10회 재시도했으나 모두 `Operation timed out`이었다.
- leaderboard 제출은 여전히 no-go다.

## 근거

[Original Text/Data] 기존 `README.md`는 “Rule Engine + LoRA Hybrid”를 현재 architecture처럼 설명했고, `/workspace/team6` 배포/학습/제출 명령을 포함했다.
→ [Exact Interpretation] 루트 문서를 따르는 운영자가 현재 LLM-only 원칙을 위반하거나 남의/legacy workspace를 건드릴 수 있었다.
→ [Detailed Explanation/Example] README를 현재 제출 entrypoint `src/solver.py`, package-local LLM artifact, no-rule fallback, `/workspace/sinjeongmin_opal_verifier` root 기준으로 교체했다.

[Original Text/Data] `docs/server_setup.md`, `docs/sweep_plan.md`에는 과거 `sshpass`와 `/workspace/team6` 명령이 남아 있었다.
→ [Exact Interpretation] 과거 기록으로는 보존할 수 있지만 현재 실행 절차로 쓰면 안 된다.
→ [Detailed Explanation/Example] 두 문서 상단에 legacy 경고를 추가하고, 현재 실행 기준을 `docs/server_operations_current.md`와 `docs/archive/current_task.md`로 지정했다.

## 검증

- `python3 -m unittest discover -s tests -v`: 61 tests OK
- `git diff --check`: OK
- 비밀값 prefix scan: absent
