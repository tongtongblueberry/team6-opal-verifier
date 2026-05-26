# 완료 결과 Archive - epoch5, external probe, batch_v2

<!-- Changed: 완료된 실험 결과만 별도 archive note로 고정한다. -->
<!-- Why: Gate v2 final conditional 결과까지 확정해 sample no-go와 batch v3 필요성을 남기기 위해서다. -->

- 기준 시각: 2026-05-26 20:39 KST
- 원칙: LLM-only Opal verifier. runtime rule engine 금지.
- public20 역할: train/val 기준 및 reference. hidden leaderboard가 test.
- `sample.md`: Gate A/B/C 통과 전 생성 금지. 현재 생성 no-go.
- 서버 접근 기준: `docs/archive/legacy/server_access.md` 유지. legacy setup record는 폐기 완료.
- 로컬 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
<!-- Changed: pin the archive to the active document/git lane. -->
<!-- Why: adjacent local folders must not be confused with the current worktree. -->
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team` 폴더는 현재 작업 repo가 아니며 수정/검증/commit/push하지 않는다.
- 직전 push 기준: `68393fd` pushed.

## Structural Skeleton

- 이 문서 섹션: `완료 결과 Archive`, `Structural Skeleton`, `0.9B full FT epoch 5`, `external_llm_probe`, `gemini_batch_v2`, `Git 처리 판단`, `Next Action`
- 관련 active 문서: `PROGRESS.md`, `docs/agent_handoff.md`, `docs/current_task.md`
- 관련 산출물 root:
  - `runs/self_instruct/external_llm_probe/`
  - `runs/self_instruct/gemini_batch_v2/`

## 0.9B full FT epoch 5

[Original Text/Data] 서버 run 성공. 0.9B full FT epoch 5 결과: val accuracy `0.25`, fail recall `0.0`, pass recall `0.5`, confusion `TP=0 TN=1 FP=1 FN=2`. OOM 1회 후 `label_smoothing=0`으로 성공.
→ [Exact Interpretation] epoch 5 checkpoint는 fail class를 전혀 회수하지 못했으므로 leaderboard 또는 추가 epoch 확장의 근거가 아니다.
→ [Detailed Explanation/Example] public20 train/val 기준 내부 validation에서 fail recall `0.0`이면 fail trajectory를 pass로 놓치는 문제가 남아 있다. epoch 10/20 확장은 no-go로 기록한다.

## external_llm_probe

[Original Text/Data] `runs/self_instruct/external_llm_probe/`: judge accepted `1`, Gate A `pass`, Gate B `insufficient`, Gate C `no_go`, `sample.md` no-go.
→ [Exact Interpretation] 단일 accepted probe는 schema와 질적 검토의 작은 확인만 제공하며 public20-like 분포 검증을 통과하지 못했다.
→ [Detailed Explanation/Example] Gate B report는 generated count `1` 대 public20 count `20`이므로 record_count/input length/method/status/pass-fail 분포를 입증할 수 없다고 판정했다. Gate B가 pass가 아니므로 manifest 생성과 Gate C equivalence 실행은 하지 않는 것이 맞다.

- archive에 기록한 경로:
  - `runs/self_instruct/external_llm_probe/gate_b/gate_b_probe_verdict.md`
  - `runs/self_instruct/external_llm_probe/gate_c/gate_c_no_go_report.md`
- raw/judge 원문은 길 수 있으므로 commit 후보에서 제외한다.

## gemini_batch_v2

[Original Text/Data] `runs/self_instruct/gemini_batch_v2/batch_v2_counts_summary.json`: raw `12`, parser accepted `9`, parser rejected `3`, dedup accepted `9`, dedup rejected `0`, judge accepted `9`, judge rejected `0`, label `pass=6/fail=3`, record_count min/mean/max `8/13.0/18`. `runs/self_instruct/gemini_batch_v2/gate_abc_verdict.json`: Gate A `pass`, Gate B `conditional_pass`, Gate C `pass`, final verdict `conditional`, sample eligibility `no_under_strict_full_pass_rule`.
→ [Exact Interpretation] batch_v2는 parser/dedup/judge와 Gate A/C를 통과했지만 Gate B가 conditional이므로 strict full-pass 기준의 training-ready/public sample 데이터가 아니다.
→ [Detailed Explanation/Example] parser reject 이유는 `fail_label_final_response_success_compatible=3`이다. judge accepted 9개는 final-response label과 manifest/model input equivalence 측면에서는 usable하지만, `n=9`, generated record_count mean `13` vs public20 `16.4`, long-tail `>32` step 부재, generated label `pass=6/fail=3` vs public20 aggregate `pass=10/fail=10` 때문에 Gate B가 full pass가 아니다. accepted-data `sample.md`는 no-go이며 larger/balanced batch v3가 필요하다.

- archive에 기록한 경로:
  - `runs/self_instruct/gemini_batch_v2/batch_v2_counts_summary.json`
  - `runs/self_instruct/gemini_batch_v2/parse_report.json`
  - `runs/self_instruct/gemini_batch_v2/dedup_report.json`
  - `runs/self_instruct/gemini_batch_v2/judge_report_gemini.json`
  - `runs/self_instruct/gemini_batch_v2/gate_a/gate_a_state_transition_audit.md`
  - `runs/self_instruct/gemini_batch_v2/gate_abc_verdict.json`
  - `runs/self_instruct/gemini_batch_v2/gate_abc_verdict.md`
- raw/judge 원문, accepted candidate JSONL, Gate 산출물 JSON/MD는 큰 파일 또는 원문 포함 가능성이 있으므로 commit 후보에서 제외한다. 이 archive에는 경로와 counts만 남긴다.

## Git 처리 판단

[Original Text/Data] Gate v2 검증 결과가 final `conditional`로 완료됐다. 관련 raw run 산출물은 `runs/self_instruct/gemini_batch_v2/` 아래에 있으며 원문/큰 파일을 포함할 수 있다.
→ [Exact Interpretation] 관련 문서만 commit/push하고 raw run 산출물은 제외한다.
→ [Detailed Explanation/Example] commit 범위는 `PROGRESS.md`, `docs/agent_handoff.md`, `docs/current_task.md`, 이 archive note로 제한한다. raw JSONL, judge 원문, Gate report 산출물은 경로와 counts만 문서화한다.

## Next Action

- larger/balanced batch v3로 Gate B full pass를 목표로 한다.
- strict full-pass 전까지 `sample.md`는 생성하지 않는다.
- 0.9B epoch 10/20은 현재 epoch5 fail recall `0.0` 근거로 중단 상태를 유지한다.
