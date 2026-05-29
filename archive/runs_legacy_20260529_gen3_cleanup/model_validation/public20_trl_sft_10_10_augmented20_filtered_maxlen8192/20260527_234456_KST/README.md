# RETRAIN-20 filtered maxlen8192 dataset

<!-- Changed: add a filtered augmented dataset that excludes two generated train rows too long for max_length=8192. -->
<!-- Why: exact train-24 augmented dataset cannot train because completion labels are fully truncated for rows 00038/00039. -->

- Created at: `2026-05-27 23:44:56 KST`
- Source root: `runs/model_validation/public20_trl_sft_10_10_augmented20/20260527_230901_KST`
- Output root: `runs/model_validation/public20_trl_sft_10_10_augmented20_filtered_maxlen8192/20260527_234456_KST`
- Train per seed: `22` = public20 train `10` + generated train `12`
- Validation per seed: public20-only baseline validation `10`, byte-equal required.
- This is not generated-20-full training. It is a max_length-compatible filtered experiment.
