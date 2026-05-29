# 2026-05-27 16:43 KST 4B Plain QLoRA Complete No-Go

<!-- Changed: archive the final 4B QLoRA plain queue completion and e10/e20/e30 decision. -->
<!-- Why: active docs need a dated source for the completed plain queue, no-go primary verdict, and next verified-code GPU slot rule. -->

## Scope

- Updated active docs: `PROGRESS.md`, `docs/current_task.md`, `docs/server_operations_current.md`, `docs/agent_handoff.md`.
- No training or code changes were run for this doc-sync subtask.

## Poll State

- Poll time `2026-05-27 16:43:25 KST`.
- Queue root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1322_KST_public20_trl_10_10_4b_qlora_plain_maxlen8192`.
- Queue pid `361733`, alive `no`, queue_state `done`, current job `plain_seed47_e10`.
- Queue log says `plain_seed47_e10` done and `QUEUE_DONE` at `2026-05-27 16:17:05 KST`.
- GPU idle `0/46068 MiB`, util `0%`.

## 4B e10 Seed Metrics

- seed11: acc `0.6000`, macro-F1 `0.5833`, fail/pass `0.8000/0.4000`, TP=4 TN=2 FP=3 FN=1 INVALID=0, eval_loss `0.7727`, p_fail min/max/mean `0.0158/0.9996/0.6944`.
- seed29: acc `0.8000`, macro-F1 `0.7917`, fail/pass `0.6000/1.0000`, TP=3 TN=5 FP=0 FN=2 INVALID=0, eval_loss `0.3758`, p_fail `0.0374/0.8938/0.3274`.
- seed47: acc `0.8000`, macro-F1 `0.7917`, fail/pass `0.6000/1.0000`, TP=3 TN=5 FP=0 FN=2 INVALID=0, eval_loss `0.6132`, p_fail `0.0123/0.9975/0.3458`.

## Aggregates

- 4B e10 3-seed aggregate: acc `0.7333`, macro-F1 `0.7321`, fail/pass `0.6667/0.8000`, TP=10 TN=12 FP=3 FN=5 INVALID=0.
- 4B e20 aggregate and e30 aggregate were identical: acc `0.7667`, macro-F1 `0.7643`, fail/pass `0.6667/0.8667`, TP=10 TN=13 FP=2 FN=5.
- 0.9B e30 plain best remains better: acc `0.8000`, macro-F1 `0.7964`, fail/pass `0.6667/0.9333`, TP=10 TN=14 FP=1 FN=5.

## Decision

- Decision: 4B QLoRA plain is complete and becomes `no-go as primary / auxiliary evidence only` unless later packaging constraints force fallback; it does not beat 0.9B e30 plain best.
- Failure scan clean for NaN/OOM/Traceback/Killed/RuntimeError/Exception.
- DATA-GEN remains blocked by missing provider keys; sample remains no-go until all gates pass.
- Next GPU slot should be filled only by a verified-code candidate: 4B QLoRA+retrieval or RAFT-style if preflight/provenance passes; RAFT remains data-gated if synthetic data is required.
