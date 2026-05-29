<!-- Changed: add a short archive note for the 12:20:15 KST epoch-grid aggregate docs sync. -->
<!-- Why: active docs now depend on this poll as the latest queue/evidence boundary. -->

# 2026-05-27 12:20 KST Epoch-Grid Aggregate Docs Sync

- 기준 poll: 2026-05-27 12:20:15 KST.
- queue pid `328009` active, current job `retrieved_seed29_e10` generation running.
- e10 retrieved aggregate는 incomplete.
- current best validation evidence: e30 plain complete, acc `0.8000`, aggregate macro-F1 `0.7964`, fail/pass recall `0.6667/0.9333`, pooled `TP=10 TN=14 FP=1 FN=5`.
- e10 plain complete는 secondary evidence: acc `0.7667`, aggregate macro-F1 `0.7664`, fail/pass recall `0.7333/0.8000`, pooled `TP=11 TN=12 FP=3 FN=4`.
- Retrieval evidence so far: e5 plain acc `0.6667`, e5 retrieved acc `0.5000`; e20 retrieved no gain; e30 retrieved worse than plain; e10 retrieved partial seed11 acc `0.4000`, fail recall `0.0000`. Retrieval은 no-go evidence so far.
- Failure scan은 clean except lowercase config key.
- package/submission no-go. Data generation provider keys false이고 sample은 no-go.
