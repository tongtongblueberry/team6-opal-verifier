# 2026-05-27 09:58 KST retrieved_seed11_e30 docs sync

<!-- Changed: record retrieved_seed11_e30 completion and current retrieved_seed29_e30 training status. -->
<!-- Why: active docs need the latest retrieved e30 seed11 comparison before package/submission decisions. -->

- 2026-05-27 09:58:28 KST 기준 corrected queue pid `328009`는 active이고 current job은 `retrieved_seed29_e30` training이다.
- `retrieved_seed11_e30`은 done이다. generation/logprob metric은 acc `0.7`, macro-F1 `0.69696969697`, fail/pass recall `0.6/0.8`, confusion `TP=3 TN=4 FP=1 FN=2 INVALID=0`이며 `p_fail` present다.
- retrieved seed11 e30은 plain seed11 e30 대비 acc `-0.1`, macro-F1 `-0.10303`, fail recall `-0.2`, FN `1->2`로 악화됐다.
- `retrieved_seed11_e30` final eval_loss는 `1.2593557834625244`, best eval_loss는 `0.3124` epoch `19`라 overfit risk가 남아 있다.
- corrected queue에서 `NaN`, `OOM`, `Traceback`, `Killed`는 발견되지 않았다.
- package/submission은 no-go이며 sample도 no-go다.
