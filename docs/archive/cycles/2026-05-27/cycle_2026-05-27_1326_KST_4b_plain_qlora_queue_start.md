<!-- Changed: archive the 4B plain QLoRA queue start. -->
<!-- Why: future workers need immutable evidence for queue root, pid, model id, preflight, and no-submit gates. -->

# 2026-05-27 13:26 KST 4B Plain QLoRA Queue Start

1. [Original Text/Data] 0.9B corrected queue `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0716_KST_public20_trl_10_10_09b_fullft_maxlen8192` reported `QUEUE_DONE 2026-05-27 12:38:12 KST`; 2026-05-27 13:17:28 KST server check showed pid `328009` dead, queue state `done`, and GPU `0 MiB / 0%`.
   → [Exact Interpretation] The corrected 0.9B queue is complete and the GPU slot was free before opening the next model slot.
   → [Detailed Explanation/Example] The retained best validation evidence is e30 plain aggregate acc `0.8000`, macro-F1 `0.7964`, fail/pass recall `0.6667/0.9333`, pooled confusion `TP=10 TN=14 FP=1 FN=5`.

2. [Original Text/Data] Final e10 retrieved generation/logprob aggregate was acc `0.4667`, aggregate macro-F1 `0.4570`, fail/pass recall `0.3333/0.6000`, pooled confusion `TP=5 TN=9 FP=6 FN=10`.
   → [Exact Interpretation] Retrieval remains no-go for the next queue.
   → [Detailed Explanation/Example] The new queue is plain-only and uses no retrieved dataset or rulebook/spec context.

3. [Original Text/Data] New active run root is `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1322_KST_public20_trl_10_10_4b_qlora_plain_maxlen8192`; queue pid `361733`; 2026-05-27 13:26:01 KST current job `plain_seed11_e30`; child train pid `361743`; GPU `4831 MiB / 46068 MiB`, util `7%`.
   → [Exact Interpretation] The 4B plain TRL+PEFT/QLoRA queue is running in the background.
   → [Detailed Explanation/Example] Poll `status/current_job.txt`, `status/plain_seed11_e30.status`, `queue.log`, and `logs/plain_seed11_e30.train.*` first.

4. [Original Text/Data] Model id `Qwen/Qwen3.5-4B` was found in previous 4B adapter configs and server HF check returned sha `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
   → [Exact Interpretation] The model choice is based on existing provenance plus a live server-side HF availability check, not an invented id.
   → [Detailed Explanation/Example] Do not switch model ids mid-queue unless this run fails and a new archived decision records the reason.

5. [Original Text/Data] Preflight recorded `trl==1.5.0`, `transformers==5.8.1`, `peft==0.19.1`, `bitsandbytes==0.49.2`, `SFTConfig_completion_only_loss=True`, `TRL_get_kbit_device_map=True`, `max_length=8192`, `peft_enabled=True`, `quantization_enabled=True`, and `min_shifted_valid_completion_label_count=1`.
   → [Exact Interpretation] The full queue uses the official TRL SFTTrainer + PEFT LoRA + bitsandbytes 4bit path and preserves completion labels at the configured token budget.
   → [Detailed Explanation/Example] `tools/training/run_trl_sft_public20.py` is the only trainer used. Train/eval batch size is `1`, gradient accumulation is `8`, generation/logprob eval pass `--max-length 8192`, and logprob creates `p_fail` sidecars.

6. [Original Text/Data] Package/submission gates are not run; data generation provider keys remain false; no accepted synthetic sample exists.
   → [Exact Interpretation] No leaderboard submission or package promotion is allowed from this queue start alone.
   → [Detailed Explanation/Example] Next decisions require completed 4B validation metrics plus package `<12GB`, `check_submit_package.py`, and offline first-forward smoke evidence.
