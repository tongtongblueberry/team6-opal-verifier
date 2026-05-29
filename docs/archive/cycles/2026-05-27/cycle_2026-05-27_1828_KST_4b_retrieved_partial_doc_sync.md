<!-- Changed: archive the 18:28:02 KST 4B retrieved-context partial result. -->
<!-- Why: future workers need the active queue target and below-best partial aggregate before making package or next-run decisions. -->

# 2026-05-27 18:28 KST 4B Retrieved Partial Doc Sync

## Scope

- Updated active docs: `PROGRESS.md`, `docs/current_task.md`, `docs/server_operations_current.md`, `docs/agent_handoff.md`.
- No model/package decision is allowed from this partial result.

## Queue State

- 4B retrieval run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1701_KST_public20_trl_10_10_4b_qlora_retrieved_maxlen8192`.
- Queue pid `370608`.
- At `2026-05-27 18:28:02 KST`, queue running, current job `retrieved_seed47_e30`, child pid `372408`, GPU L40S `32717/46068 MiB`, util `90%`.

## Seed29 Result

- `retrieved_seed29_e30` done at `2026-05-27 18:04:57 KST`.
- acc `0.8000`, macro-F1 `0.7917`, fail/pass `0.6000/1.0000`, TP=3 TN=5 FP=0 FN=2 INVALID=0.
- p_fail `0.000017/1.000000/0.300084`.

## Partial Aggregate

- e30 partial seed11+29 aggregate: acc `0.7000`, macro-F1 `0.7000`, fail/pass `0.7000/0.7000`, TP=7 TN=7 FP=3 FN=3 INVALID=0.
- Partial remains below 0.9B e30 plain best by acc `-0.1000`, macro-F1 `-0.0964`, pass recall `-0.2333`; fail recall `+0.0333`.
- Failure scan clean.
