<!-- Changed: add an archive record for the 2026-05-27 06:44:13 KST server metric poll and scoped doc sync. -->
<!-- Why: active docs now contain the latest queue pid/current job, e20 plain/retrieved metrics, eval_loss nan boundary, and no-package/no-submission status. -->

# 2026-05-27 06:44 KST server metric doc sync

## 기록 범위

- [Original Text/Data] `Poll 2026-05-27 06:44:13 KST 기준 queue pid 318407 alive, current job retrieved_seed29_e20 running.` → [Exact Interpretation] active 0.9B full FT official TRL public20 `10 train / 10 val` queue는 살아 있고, e20 block의 retrieved seed29 job까지 진행됐다. → [Detailed Explanation/Example] 이전 문서의 current job `plain_seed47_e20` running 기록은 stale이므로 `retrieved_seed29_e20` running으로 갱신했다. queue 전체는 아직 완료되지 않았다.

- [Original Text/Data] `plain e20 3 seeds done: seed11 0.90/0.89899/fail recall 0.80/pass 1.00; seed29 0.70/0.67033/fail 0.40/pass 1.00; seed47 0.60/0.52381/fail 0.20/pass 1.00. generation/logprob 동일.` → [Exact Interpretation] plain e20은 3개 seed가 모두 완료됐고 generation evaluator와 logprob evaluator가 같은 metric을 냈다. → [Detailed Explanation/Example] seed11은 가장 높지만 seed29와 seed47의 fail recall이 각각 `0.40`, `0.20`으로 낮다. 따라서 plain e20 block만으로 package/submission candidate를 만들 수 없다.

- [Original Text/Data] `retrieved_seed11_e20 done: generation/logprob acc 0.70 macro-F1 0.69697 fail recall 0.80 pass recall 0.60 TP=4 TN=3 FP=2 FN=1 INVALID=0; p_fail finite but pass-gold mean p_fail 0.4473; plain seed11 대비 악화.` → [Exact Interpretation] retrieved context seed11은 완료됐지만 plain seed11보다 validation metric이 나빠졌다. → [Detailed Explanation/Example] acc는 plain seed11 `0.90`에서 retrieved seed11 `0.70`으로 떨어졌고, pass recall은 `1.00`에서 `0.60`으로 떨어졌다. `p_fail`은 finite지만 pass-gold 평균 `p_fail=0.4473`이라 calibration 판단은 보류해야 한다.

- [Original Text/Data] `eval_loss: nan repeated; loss based early stopping/calibration no-go, generation/logprob finite metrics만 provisional validation signal.` → [Exact Interpretation] 현재 queue에서 loss 값은 판단 신호로 사용할 수 없다. → [Detailed Explanation/Example] early stopping이나 calibration을 loss 감소 기준으로 결정하지 않는다. generation/logprob evaluator의 finite accuracy, macro-F1, recall, confusion matrix만 임시 validation signal로 기록한다.

- [Original Text/Data] `submission/package no-go; queue 전체 완료 전 판단 금지.` → [Exact Interpretation] 현재 시점에는 제출 후보나 package 후보가 없다. → [Detailed Explanation/Example] retrieved variants와 이후 epoch blocks가 끝나기 전에는 모델 선택, package `<12GB`, runtime smoke, leaderboard 제출 판단을 진행하지 않는다.

- [Original Text/Data] `sample.md 생성 금지; data generation still provider-key blocked.` → [Exact Interpretation] Self-Instruct accepted sample 공개 상태는 변하지 않았다. → [Detailed Explanation/Example] provider key 부재로 real raw generation이 없고 Gate A/B/C/D 및 Self-Instruct quality 검증을 통과한 candidate도 없으므로 `docs/samples/self_instruct_sample.md`를 만들지 않는다.

## 문서 반영

- [Original Text/Data] `PROGRESS.md`, `docs/current_task.md`, `docs/server_operations_current.md` → [Exact Interpretation] 이번 worker의 write scope 안에서 active progress/current/server 운영 문서와 archive note를 갱신했다. → [Detailed Explanation/Example] `README.md`, `docs/agent_handoff.md`, `docs/current_self_instruct_data_plan.md`, `docs/samples/README.md`는 이번 요청의 write scope 밖이므로 수정하지 않았다.
