<!-- Changed: add an archive record for the 20260527_0545_KST public20 TRL 10/10 queue metric doc sync. -->
<!-- Why: active docs now contain completed seed11/seed29 e20 metrics, current seed47 running state, and the no-go boundary for weak fail recall evidence. -->

# 2026-05-27 06:14 KST server metric doc sync

## 기록 범위

- [Original Text/Data] `run root: /workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft` → [Exact Interpretation] 현재 문서 동기화 대상 서버 run은 0.9B full FT official TRL public20 `10 train / 10 val` queue다. → [Detailed Explanation/Example] active docs의 서버/학습 상태는 이 run root를 기준으로 갱신했다. 다른 run root, 특히 이전 4B QLoRA interrupted run은 package/submission candidate 근거로 쓰지 않는다.

- [Original Text/Data] `plain_seed11_e20 done: generation/logprob both acc 0.90, macro-F1 0.89899, fail recall 0.80, pass recall 1.00, confusion TP=4 TN=5 FP=0 FN=1 INVALID=0, p_fail sidecar exists.` → [Exact Interpretation] `plain_seed11_e20`은 generation evaluator와 logprob evaluator가 같은 metric을 낸 완료 job이며, fail 5개 중 4개를 맞추고 pass 5개를 모두 맞췄다. → [Detailed Explanation/Example] confusion 기준으로 fail-positive를 `TP`, pass-negative를 `TN`으로 읽으면 `TP=4`, `FN=1`이라 fail recall은 `4/(4+1)=0.80`이고, `TN=5`, `FP=0`이라 pass recall은 `5/(5+0)=1.00`이다. `p_fail` sidecar가 있으므로 후속 calibration/threshold 검토 입력은 존재한다.

- [Original Text/Data] `plain_seed29_e20 done: generation/logprob both acc 0.70, macro-F1 0.67033, fail recall 0.40, pass recall 1.00, confusion TP=2 TN=5 FP=0 FN=3 INVALID=0, p_fail sidecar exists. This is weak/no-go candidate evidence due fail recall 0.40.` → [Exact Interpretation] `plain_seed29_e20`은 완료됐지만 fail recall이 낮아 제출 후보 근거가 아니라 weak/no-go evidence다. → [Detailed Explanation/Example] confusion 기준으로 fail 5개 중 `TP=2`, `FN=3`이므로 fail recall은 `2/(2+3)=0.40`이다. pass recall은 `TN=5`, `FP=0`으로 `1.00`이지만, fail 검출 누락이 3개라 pass 쪽 안정성만으로 package/submission candidate를 만들 수 없다.

- [Original Text/Data] `current job plain_seed47_e20 running.` → [Exact Interpretation] queue는 아직 완료되지 않았고 현재 plain seed47 epoch20 job이 실행 중이다. → [Detailed Explanation/Example] active docs에서는 seed11/seed29 완료와 seed47 running을 함께 기록했다. remaining queue 결과는 seed47 이후 block과 retrieved variants까지 포함해 아직 pending이다.

- [Original Text/Data] `Results pending for remaining queue; no package/submission candidate yet.` → [Exact Interpretation] 완료된 두 job이 있더라도 현재 시점에는 제출 후보가 없다. → [Detailed Explanation/Example] remaining queue metric, calibration 판단, package `<12GB`, submit package check, offline first-forward smoke가 완료되지 않았으므로 leaderboard 제출 판단은 no-go로 유지한다.

- [Original Text/Data] `sample.md no-go/data real generation blocked unchanged.` → [Exact Interpretation] Self-Instruct accepted sample 공개 상태는 이번 metric sync로 바뀌지 않았다. → [Detailed Explanation/Example] real raw generation, parser/dedup/judge, Gate A/B/C/D, Self-Instruct quality 검증을 모두 통과한 generated candidate가 없으므로 `docs/samples/self_instruct_sample.md` 생성은 계속 no-go다.

## 문서 반영

- [Original Text/Data] `docs/agent_handoff.md`, `PROGRESS.md`, `README.md`, `docs/current_task.md`, `docs/server_operations_current.md` → [Exact Interpretation] 활성 문서 5개에 같은 run root, 완료 metric, current job, pending/no-go boundary를 반영했다. → [Detailed Explanation/Example] 모든 문서는 `plain_seed11_e20` 수치, `plain_seed29_e20` 수치, `plain_seed47_e20 running`, remaining queue pending, package/submission candidate 없음, sample no-go 불변 상태를 동일한 판단으로 기록한다.
