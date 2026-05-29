# 2026-05-27 16:08 KST 4B e20 Complete and e10 Advance Doc Sync

<!-- Changed: archive the 16:08:31 KST 4B e20 seed47 completion, full e20 aggregate, and e10 queue advance. -->
<!-- Why: active docs need a dated source for the completed e20 result and the next poll target. -->

## Scope

- Updated active docs: `PROGRESS.md`, `docs/current_task.md`, `docs/server_operations_current.md`, `docs/agent_handoff.md`.
- No training or code changes were run for this doc-sync subtask.

## Poll State

- Poll time `2026-05-27 16:08:31 KST`.
- Queue pid `361733`, queue_state=`running`, current_job=`plain_seed47_e10`.
- Child pid `368662`, NVIDIA L40S `31027/46068 MiB`, util `97%`.
- `plain_seed47_e20.status=done`.
- `plain_seed11_e10.status=done`.
- seed47 e10 was training at poll time.

## 4B e20 Seed47

- `plain_seed47_e20` generation/logprob: acc `0.8000`, macro-F1 `0.7917`, fail/pass recall `0.6000/1.0000`, TP=3 TN=5 FP=0 FN=2 INVALID=0.
- final eval_loss `1.0312834978103638`.
- p_fail sidecar count `10`, min `0.0000243024`, max `0.9999485473`, mean `0.3127848832`.

## 4B e20 Aggregate

- 3-seed e20 aggregate generation/logprob: acc `0.7667`, macro-F1 `0.7643`, fail/pass recall `0.6667/0.8667`, TP=10 TN=13 FP=2 FN=5 INVALID=0, n=30.
- e20 is identical to 4B e30 aggregate.
- Versus 0.9B e30 plain best: acc `-0.0333`, macro-F1 `-0.0321`, pass recall `-0.0667`; fail recall unchanged; confusion TN -1, FP +1.

## Gates

- Failure scan clean for NaN/OOM/Traceback/Killed/RuntimeError/Exception.
- DATA-GEN remains blocked by missing provider keys; `docs/samples/self_instruct_sample.md` remains no-go until all gates pass.
- Package/submission remains no-go until e10 evidence and package/runtime gates are recorded.
