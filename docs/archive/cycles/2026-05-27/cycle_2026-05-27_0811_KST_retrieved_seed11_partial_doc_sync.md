<!-- Changed: add a short archive note for the 08:11:34 KST retrieved_seed11_e20 partial docs sync. -->
<!-- Why: current docs now depend on this queue snapshot while package/submission remains no-go. -->

# 2026-05-27 08:11 KST retrieved seed11 partial docs sync

- corrected queue pid `328009` active.
- `retrieved_seed11_e20` train complete: `eval_loss=0.4172023832798004` finite, `train_loss=0.8842076048254967`.
- `retrieved_seed11_e20` generation: acc `0.70`, macro-F1 `0.6969696969696968`, fail/pass recall `0.80/0.60`, confusion `TP=4 TN=3 FP=2 FN=1 INVALID=0`.
- 2026-05-27 08:11:34 KST 기준 `retrieved_seed11_e20` logprob/`p_fail` pending.
- `plain_seed11_e20` generation/logprob metric은 retrieved seed11 generation metric과 같고, retrieved train `eval_loss`가 lower다.
- package/submission no-go. data generation provider keys false. sample no-go.
