<!-- Changed: add a short archive note for the seed29 partial corrected queue state. -->
<!-- Why: active docs now reference seed29 train/generation completion while logprob and p_fail remain pending. -->

# 2026-05-27 07:43 KST corrected queue seed29 partial

- corrected queue pid `328009` active.
- `plain_seed11_e20` done: finite `eval_loss=1.7947536706924438`, generation/logprob acc `0.70`, macro-F1 `0.69697`, fail/pass recall `0.80/0.60`, `p_fail` present.
- `plain_seed29_e20` train done: finite `eval_loss=1.275506615638733`, generation acc `0.80`, macro-F1 `0.7916666666666665`, fail/pass recall `0.60/1.00`.
- `plain_seed29_e20` logprob/p_fail pending at 2026-05-27 07:43:55 KST.
- package/submission remains no-go. data generation remains provider-key blocked and sample remains no-go.
