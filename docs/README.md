# 문서 구조

최종 갱신: 2026-05-26 16:26 KST

## Active 문서

- [current_task.md](current_task.md): 현재 handoff와 다음 실행 순서.
- [agent_handoff.md](agent_handoff.md): worker agent가 반드시 공유해야 할 공통 맥락, 금지사항, context block.
- [server_operations_current.md](server_operations_current.md): 서버 접속, sync, 제출 판단 절차.
- [current_self_instruct_data_plan.md](current_self_instruct_data_plan.md): Self-Instruct 생성 데이터 검증 Gate A-D와 docs/tools 정리 기준.
- [samples/README.md](samples/README.md): Gate A/B/C 통과 전후 raw sample 공개 정책.

## Archive 구조

- [archive/cycles/](archive/cycles/): 날짜별 cycle 실행 기록.
- [archive/handoff/](archive/handoff/): 과거 handoff/TODO 상태 기록.
- [archive/legacy/](archive/legacy/): 현재 실행하면 안 되는 과거 운영/규칙/문서.
- [archive/legacy_datagen/](archive/legacy_datagen/): active datagen에서 제거한 synthetic generator 정리 기록.
- [archive/research/](archive/research/): 조사/방법론 요약 기록.
- [archive/submissions/](archive/submissions/): 과거 제출 시도와 제출 로그.

Archive 파일은 현재 실행 기준이 아니다. 현재 기준은 `README.md`, `PROGRESS.md`, `docs/README.md`, `docs/current_task.md`, `docs/agent_handoff.md`, `docs/server_operations_current.md`, `docs/current_self_instruct_data_plan.md`, `docs/samples/README.md`다.

<!-- Changed: define the active docs update set that every cleanup or pipeline worker must keep synchronized. -->
<!-- Why: agent_handoff.md must move with README/PROGRESS/current docs instead of becoming stale context. -->
Active docs update set은 `README.md`, `PROGRESS.md`, `docs/README.md`, `docs/current_task.md`, `docs/current_self_instruct_data_plan.md`, `docs/agent_handoff.md`, `docs/samples/README.md`다. 데이터 생성/검증/학습/제출/sample 공개 기준을 바꾸는 agent는 이 묶음을 함께 점검한다.

## 현재 정리 기준

<!-- Changed: clarify active/archive/delete criteria for docs and tools. -->
<!-- Why: failed data generators must remain audit-only and must not re-enter default execution. -->

- 날짜가 붙은 실행 기록과 폐기 판단은 `archive/cycles/<YYYY-MM-DD>/` 아래에 둔다.
- v4/v4.1 데이터 폐기 판단은 [archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md](archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md)에 둔다.
- active 문서와 active tools에는 다음 실행 기준, 현재 default 실행 경로, 통과해야 할 gate만 남긴다.
- 오래된 pending/evidence, 실패 분석, 제출 시도 기록은 archive 문서를 링크한다.
- v4/v4.1 같은 실패 코드와 spec/gap synthetic generator는 audit evidence만 남기고 active `tools/datagen/`에서 제거한다.
- Gate A/B/C 통과 후 generated synthetic 데이터는 `train`, `val`, `test`로 분리하고 public20은 `public20_reference`로 따로 둔다.
- public20-only 모델 후보 검증은 public20 20개를 `train`/`val`로만 나누며 public20 `test` split은 만들지 않는다. test는 leaderboard hidden 평가다.
- 이때 `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는 공개되지 않은 leaderboard hidden 평가다.
- 기본 split은 stratified `16 train / 4 val`이고, val은 `pass 2 / fail 2`를 목표로 한다.
- 모델 후보는 Prompt-only/few-shot, Frozen RAG classifier, 0.9B full FT, 4B QLoRA/LoRA selective FT, RAFT-style RAG+SFT/QLoRA다.
- public20 local reference facts는 rows `20`, record_count min/mean/max `1/16.4/39`, label distribution `fail=10`, `pass=10`이다.
- Gate B dimension comparison 도구는 `tools/analysis/compare_public20_dimensions.py`이며, public20 label은 local aggregate distribution으로만 사용한다.
- `tools/datagen/generate_self_instruct_candidates.py --fixture-smoke`는 Gate A/B smoke용 fixture만 만든다. 최종 학습 데이터가 아니며 no-go evidence로만 다룬다.
- Self-Instruct synthetic data가 Gate A/B/C를 통과하면 `docs/samples/self_instruct_sample.md`에 generated raw trajectory 전체, label, target, primary evidence, profile, public20 raw sample 1개 전체, Gate A audit summary, Gate B comparison summary, Gate C manifest/model-input summary를 기록한다.
- public20 reference audit pack은 public20 검증 결과가 아니라 reference structure/profile 확인용 산출물로 표현한다.
- Gate A/B/C 전에는 raw synthetic sample을 "합격 데이터"로 제시하지 않는다.
- secret, token, password가 들어간 파일은 archive하지 않고 삭제 대상으로 본다.
- 재현 가능한 tmp output, partial generated data, 중복 stale docs는 no-go 근거가 아니면 삭제 대상으로 본다.
