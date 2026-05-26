# 문서 구조

최종 갱신: 2026-05-26 14:13 KST

## Active 문서

- [current_task.md](current_task.md): 현재 handoff와 다음 실행 순서.
- [server_operations_current.md](server_operations_current.md): 서버 접속, sync, 제출 판단 절차.

## Archive 구조

- [archive/cycles/](archive/cycles/): 날짜별 cycle 실행 기록.
- [archive/handoff/](archive/handoff/): 과거 handoff/TODO 상태 기록.
- [archive/legacy/](archive/legacy/): 현재 실행하면 안 되는 과거 운영/규칙/문서.
- [archive/research/](archive/research/): 조사/방법론 요약 기록.
- [archive/submissions/](archive/submissions/): 과거 제출 시도와 제출 로그.

Archive 파일은 현재 실행 기준이 아니다. 현재 기준은 `README.md`, `PROGRESS.md`, `docs/current_task.md`, `docs/server_operations_current.md`다.

## 현재 정리 기준

- 날짜가 붙은 실행 기록과 폐기 판단은 `archive/cycles/<YYYY-MM-DD>/` 아래에 둔다.
- v4/v4.1 데이터 폐기 판단은 [archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md](archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md)에 둔다.
- active 문서에는 다음 실행 기준만 남긴다. 오래된 pending/evidence는 archive 문서를 링크한다.
