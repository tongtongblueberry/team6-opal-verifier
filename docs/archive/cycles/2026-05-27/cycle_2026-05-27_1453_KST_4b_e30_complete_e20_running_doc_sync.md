<!-- Changed: archive the 14:53:08 KST 4B e30 completion and e20 running docs sync. -->
<!-- Why: active docs need a compact cycle note preserving the below-0.9B comparison and no-go gates. -->

# 2026-05-27 14:53 KST 4B e30 Complete / e20 Running Doc Sync

- 시각: 2026-05-27 14:53:08 KST
- run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1322_KST_public20_trl_10_10_4b_qlora_plain_maxlen8192`
- queue pid `361733` active, current job `plain_seed11_e20` running, e30 3-seed complete.
- model: `Qwen/Qwen3.5-4B`; TRL `SFTTrainer` + PEFT LoRA + bitsandbytes 4bit; trainable params `155,975,680 / 2,746,069,504 (5.68%)`.
- 4B e30 aggregate: acc `0.7667`, macro-F1 `0.7643`, fail/pass recall `0.6667/0.8667`, confusion `TP=10 TN=13 FP=2 FN=5 INVALID=0`.
- 0.9B best e30 plain: acc `0.8000`, macro-F1 `0.7964`, fail/pass recall `0.6667/0.9333`; 4B e30 delta는 acc `-0.0333`, macro-F1 `-0.0321`, pass recall `-0.0666`.
- 4B e20은 running/pending이다. package/submission no-go, data generation blocked, sample no-go를 유지한다.
