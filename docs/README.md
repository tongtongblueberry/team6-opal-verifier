# 문서 구조

최종 갱신: 2026-05-26 14:37 KST

## Active 문서

- [current_task.md](current_task.md): 현재 handoff와 다음 실행 순서.
- [agent_handoff.md](agent_handoff.md): worker agent가 반드시 공유해야 할 공통 맥락, 금지사항, context block.
- [server_operations_current.md](server_operations_current.md): 서버 접속, sync, 제출 판단 절차.
- [current_self_instruct_data_plan.md](current_self_instruct_data_plan.md): Self-Instruct 생성 데이터 검증 Gate A-D와 docs/tools 정리 기준.

## Archive 구조

- [archive/cycles/](archive/cycles/): 날짜별 cycle 실행 기록.
- [archive/handoff/](archive/handoff/): 과거 handoff/TODO 상태 기록.
- [archive/legacy/](archive/legacy/): 현재 실행하면 안 되는 과거 운영/규칙/문서.
- [archive/research/](archive/research/): 조사/방법론 요약 기록.
- [archive/submissions/](archive/submissions/): 과거 제출 시도와 제출 로그.

Archive 파일은 현재 실행 기준이 아니다. 현재 기준은 `README.md`, `PROGRESS.md`, `docs/current_task.md`, `docs/agent_handoff.md`, `docs/server_operations_current.md`, `docs/current_self_instruct_data_plan.md`다.

## 현재 정리 기준

<!-- Changed: clarify active/archive/delete criteria for docs and tools. -->
<!-- Why: failed data generators must remain audit-only and must not re-enter default execution. -->

- 날짜가 붙은 실행 기록과 폐기 판단은 `archive/cycles/<YYYY-MM-DD>/` 아래에 둔다.
- v4/v4.1 데이터 폐기 판단은 [archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md](archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md)에 둔다.
- active 문서와 active tools에는 다음 실행 기준, 현재 default 실행 경로, 통과해야 할 gate만 남긴다.
- 오래된 pending/evidence, 실패 분석, 제출 시도 기록은 archive 문서를 링크한다.
- v4/v4.1 같은 실패 코드는 audit evidence만 남기고 default execution은 차단한다. active 위치에 남아 있더라도 명시적 opt-in flag 없이는 실행되면 안 된다.
- secret, token, password가 들어간 파일은 archive하지 않고 삭제 대상으로 본다.
- 재현 가능한 tmp output, partial generated data, 중복 stale docs는 no-go 근거가 아니면 삭제 대상으로 본다.
