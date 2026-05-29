<!-- Changed: record the e30 retrieved complete docs-sync facts. -->
<!-- Why: active docs must preserve the completed retrieved e30 no-go evidence without inventing later e5/e10 metrics. -->

# e30 Retrieved Complete Doc Sync

- Timestamp: 2026-05-27 12:16:39 KST.
- e30 retrieved complete: acc `0.7667`, aggregate macro-F1 `0.7600`, mean seed macro-F1 `0.7601`, fail/pass recall `0.6/0.9333`, pooled confusion `TP=9 TN=14 FP=1 FN=6 INVALID=0`.
- e30 plain complete: acc `0.8`, aggregate macro-F1 `0.7963800905`, mean seed macro-F1 `0.7944444444`, fail/pass recall `0.6667/0.9333`, pooled confusion `TP=10 TN=14 FP=1 FN=5`.
- Retrieved e30 is worse than plain: acc `-0.0333`, macro-F1 `-0.0364`, fail recall `-0.0667`, FN `+1`. This is retrieval e30 no-go evidence.
- e30 plain is only a modest improvement over e20: acc `+0.0333`, macro-F1 `+0.0321`, pass recall `+0.0667`, fail recall unchanged.
- Queue later progressed to e5/e10; last known poll current job was `retrieved_seed11_e10` training. No e5/e10 metrics are recorded in this note.
- Package/submission remains no-go. Provider keys false/sample no-go remains unchanged.
