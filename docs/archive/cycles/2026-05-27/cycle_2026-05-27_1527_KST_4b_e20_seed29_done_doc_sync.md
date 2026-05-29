<!-- Changed: add short archive note for the 4B e20 seed29 docs sync. -->
<!-- Why: active docs need a compact 2026-05-27 15:27:28 KST record of the current 4B queue state, seed29 result, and no-go conclusion. -->

# 4B e20 seed29 doc sync 2026-05-27 15:27:28 KST

- Queue root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1322_KST_public20_trl_10_10_4b_qlora_plain_maxlen8192`, pid `361733`, state `running` as of 2026-05-27 15:27:28 KST.
- Current job then: `plain_seed47_e20`, child pid `366413`, NVIDIA L40S `30895/46068 MiB`, util `100%`.
- `plain_seed29_e20` done at 15:26:04 KST. generation/logprob identical: acc `0.8000`, macro-F1 `0.7917`, fail/pass recall `0.6000/1.0000`, `TP=3 TN=5 FP=0 FN=2 INVALID=0`, eval_loss `1.4251`.
- `p_fail` sidecar present: min `2.41e-06`, max `~1.0`, mean `0.3001`.
- e20 partial aggregate seed11+29: acc `0.7500`, macro-F1 `0.7494`, fail/pass recall `0.7000/0.8000`, `TP=7 TN=8 FP=2 FN=3 INVALID=0`.
- Comparison: e20 partial remains below 4B e30 aggregate by acc `-0.0167`, macro-F1 `-0.0149`, pass recall `-0.0667`; fail recall `+0.0333`.
- Comparison: e20 partial remains below 0.9B best e30 plain by acc `-0.0500`, macro-F1 about `-0.0470`, pass recall `-0.1333`; fail recall `+0.0333`.
- Risk: failure scan clean for `NaN`/`OOM`/`Traceback`/`Killed`/`RuntimeError`/`Exception`; main risk is saturated `p_fail`/overconfidence and e20 partial still below 0.9B best; seed47 still running so e20 aggregate incomplete.
- DATA-GEN remains blocked by missing provider keys; `docs/samples/self_instruct_sample.md` remains no-go until all gates pass.
