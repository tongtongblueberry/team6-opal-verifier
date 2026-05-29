<!-- Changed: add the 09:03:30 KST plain_seed11_e30 doc-sync note. -->
<!-- Why: preserve the first corrected e30 seed result, active queue state, and no-go gates without modifying runtime code. -->

# 2026-05-27 09:03 KST Plain Seed11 E30 Doc Sync

- At 2026-05-27 09:03:30 KST, corrected queue pid `328009` was active; `plain_seed11_e30` was done; current job was `plain_seed29_e30` running.
- `plain_seed11_e30` generation/logprob metric: acc `0.8`, macro-F1 `0.8`, fail/pass recall `0.8/0.8`, confusion `TP=4 TN=4 FP=1 FN=1 INVALID=0`; `p_fail` sidecar present.
- e30 seed11 improved over e20 seed11: acc `+0.1`, macro-F1 `+0.10303`, pass recall `+0.2`, FP `2->1`.
- `plain_seed11_e30` loss: final eval_loss `1.1875575781`, best epoch `10` eval_loss `0.2761`; overfit risk remains.
- Corrected queue had no `NaN`, `OOM`, `Traceback`, or `Killed` evidence.
- package/submission remains no-go. Data sample remains no-go.
