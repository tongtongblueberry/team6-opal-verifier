<!-- Changed: add a short archive note for the 09:21:35 KST plain_seed29_e30 completion docs sync. -->
<!-- Why: active docs now point to seed29 completed metrics, partial e30 aggregate evidence, and the continuing no-go gates. -->

# 2026-05-27 09:21 KST plain_seed29_e30 Complete Docs Sync

- 2026-05-27 09:21:35 KST 기준 corrected queue pid `328009`는 active이고 current job은 `plain_seed47_e30` running이다.
- `plain_seed29_e30`은 done이다. generation/logprob metric은 acc `0.8`, macro-F1 `0.7916666667`, fail/pass recall `0.6/1.0`, confusion `TP=3 TN=5 FP=0 FN=2 INVALID=0`이며 `p_fail` sidecar가 있다.
- `plain_seed29_e30` loss는 final eval_loss `3.6281256675720215`, best epoch `1` eval_loss `0.392`로 strong overfit risk가 있다.
- e30 plain partial seed11+29 aggregate는 acc `0.8`, aggregate macro-F1 `0.7979797980`, fail/pass recall `0.7/0.9`다.
- e20 plain aggregate 기준은 acc `0.7667`, macro-F1 `0.7643`, fail/pass recall `0.6667/0.8667`이다.
- corrected queue에서는 `NaN`, `OOM`, `Traceback`, `Killed`가 발견되지 않았다.
- package/submission은 no-go이며 sample도 no-go다.
