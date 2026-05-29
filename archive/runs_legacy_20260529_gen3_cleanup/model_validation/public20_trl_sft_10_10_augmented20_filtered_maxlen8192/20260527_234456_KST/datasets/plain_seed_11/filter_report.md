# RETRAIN-20 filtered dataset report seed 11

<!-- Changed: record max_length-compatible filtered augmented dataset construction. -->
<!-- Why: exact generated train-14 augmented dataset failed max_length=8192 completion-label preflight on two long rows. -->

- Source train: `runs/model_validation/public20_trl_sft_10_10_augmented20/20260527_230901_KST/datasets/plain_seed_11/train.jsonl`
- Output train: `runs/model_validation/public20_trl_sft_10_10_augmented20_filtered_maxlen8192/20260527_234456_KST/datasets/plain_seed_11/train.jsonl`
- Train rows: `22` = public20 train `10` + generated train `12`
- Excluded rows: `generated20_codex-agent-fallback-targeted-schedule-00038`, `generated20_codex-agent-fallback-targeted-schedule-00039`
- Validation: copied from source augmented dataset and must remain byte-equal to public20-only baseline validation.
