# 2026-05-27 07:59 KST corrected e20 plain aggregate docs sync

<!-- Changed: archive the corrected e20 plain queue doc-sync facts. -->
<!-- Why: active docs now depend on seed11/seed29 completed gen-logprob metrics and seed47 logprob pending state before aggregate/final candidate. -->

- 2026-05-27 07:59:06 KST 기준 corrected queue pid `328009`는 active이고 current job은 `plain_seed47_e20` logprob running이다.
- `plain_seed11_e20` done: `eval_loss=1.7947536706924438`, generation/logprob acc `0.70`, macro-F1 `0.69697`, fail/pass recall `0.80/0.60`.
- `plain_seed29_e20` done: `eval_loss=1.275506615638733`, generation/logprob acc `0.80`, macro-F1 `0.79167`, fail/pass recall `0.60/1.00`, `p_fail` present.
- `plain_seed47_e20` train+generation done, logprob pending/running at 2026-05-27 07:59:06 KST: `eval_loss=1.5093908309936523`, generation acc `0.80`, macro-F1 `0.79167`, fail/pass recall `0.60/1.00`.
- Corrected queue에서는 현재까지 `NaN`, `OOM`, `Traceback`이 발견되지 않았다.
- Data generation은 provider key absent 상태이고 sample은 no-go다.
- Corrected queue aggregate와 final candidate가 나오기 전까지 package/submission은 no-go다.
