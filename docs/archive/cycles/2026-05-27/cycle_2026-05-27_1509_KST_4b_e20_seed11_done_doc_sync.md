<!-- Changed: add short archive note for the 4B e20 seed11 docs sync. -->
<!-- Why: active docs need a compact 2026-05-27 15:09:26 KST record of the current 4B queue state and no-go conclusion. -->

# 4B e20 seed11 doc sync 2026-05-27 15:09:26 KST

- 4B queue pid `361733` active, current job `plain_seed29_e20` training.
- `plain_seed11_e20` done: generation/logprob acc `0.7000`, macro-F1 `0.6970`, fail/pass recall `0.8/0.6`, confusion `TP=4 TN=3 FP=2 FN=1 INVALID=0`, eval_loss `1.7118`, `p_fail` present.
- 4B e20 seed11 is worse than 4B e30 seed11 and worse than 0.9B best aggregate; saturated `p_fail` implies overconfidence risk.
- Failure scan clean: no `NaN`, `OOM`, `Traceback`, `Killed`, `RuntimeError`, `Exception`.
- package/submission no-go; sample no-go.
