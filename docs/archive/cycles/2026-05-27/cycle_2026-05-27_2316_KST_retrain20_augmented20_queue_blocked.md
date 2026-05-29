<!-- Changed: add RETRAIN-20 augmented-data queue attempt evidence. -->
<!-- Why: the worker prepared the experimental augmented train datasets and attempted the required e30 full-FT comparison, but GPU was already occupied by another process. -->

# 2026-05-27 23:16 KST RETRAIN-20 augmented20 queue blocked

- [Original Text/Data] Local dataset root `runs/model_validation/public20_trl_sft_10_10_augmented20/20260527_230901_KST/datasets/plain_seed_{11,29,47}` was created from public20 converted TRL datasets plus `runs/self_instruct/targeted_schedule_20260527_192440_KST/manifest.record_count_preserved.codex_agent_fallback.jsonl`.
  -> [Exact Interpretation] RETRAIN-20 has an experimental train-only augmented dataset for each public20 seed.
  -> [Detailed Explanation/Example] Each seed has `train.jsonl=24` rows: public20 train `10` plus generated manifest `split=train` `14`; train labels are `fail=12/pass=12`. Each seed keeps `validation.jsonl=10` rows copied from the public20-only baseline and validated byte-equal to the baseline validation file.

- [Original Text/Data] Generated non-train splits were written as `generated_hidden.jsonl=4` and `generated_calibration.jsonl=2` under each seed dataset directory.
  -> [Exact Interpretation] Generated hidden/calibration rows were preserved for optional diagnostics but excluded from `train.jsonl`.
  -> [Detailed Explanation/Example] The training loader only receives `train.jsonl` and `validation.jsonl`; hidden/calibration files are not named in the TRL training command.

- [Original Text/Data] Local and server dry-run plans use `Qwen/Qwen3.5-0.8B`, `--max-length 8192`, `--num-train-epochs 30`, `--learning-rate 1e-5`, batch size `1`, gradient accumulation `8`, `--bf16`, `--save-strategy no`, PEFT disabled, and 4bit quantization disabled.
  -> [Exact Interpretation] The prepared e30 comparison matches the corrected 0.9B full-FT baseline settings rather than the tool default learning rate.
  -> [Detailed Explanation/Example] Baseline run script evidence showed `--learning-rate 1e-5`; initial local dry-run plans were regenerated with `1e-5` before queue creation.

- [Original Text/Data] Server queue root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_2316_KST_retrain20_augmented20_09b_fullft_maxlen8192` was created and launched from `run_queue.sh`; queue log recorded `QUEUE_START 2026-05-27 23:16:36 KST`, then `BLOCKED existing GPU compute process detected before queue start` with process `431281, python, 17742 MiB`.
  -> [Exact Interpretation] No RETRAIN-20 training job started; the queue exited before `plain_seed11_e30` because another GPU compute job was active.
  -> [Detailed Explanation/Example] A follow-up process check identified PID `431281` as `python gen_eval_dataset_v2.py`, which was not started by this worker. The worker did not kill or modify it.

- [Original Text/Data] Re-run command after GPU is idle: `cd /workspace/sinjeongmin_opal_verifier/ops/runs/20260527_2316_KST_retrain20_augmented20_09b_fullft_maxlen8192 && nohup ./run_queue.sh >/dev/null 2>&1 &`.
  -> [Exact Interpretation] The prepared queue is runnable without overwriting baseline artifacts.
  -> [Detailed Explanation/Example] The run root contains an immutable snapshot under `repo/`, `job_manifest.tsv` with seeds `11/29/47` at epoch `30`, and `run_queue.sh` that writes models, logs, plans, eval JSON/Markdown, status, and `p_fail` sidecars under the same run root.

- [Original Text/Data] A later poll still showed GPU occupied by `python gen_eval_dataset_v2.py`, now as PID `432760` with `17742 MiB`.
  -> [Exact Interpretation] The blocker persisted after the first PID exited, likely through a parent process launching another evaluation job.
  -> [Detailed Explanation/Example] RETRAIN-20 should not be restarted until `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader` returns no compute process.

- [Original Text/Data] GPU was idle at 2026-05-27 23:35:47 KST; retry marker `status/retry_20260527_233602_KST.txt` was written; `./run_queue.sh` was relaunched at 2026-05-27 23:36:02 KST.
  -> [Exact Interpretation] The prior GPU blocker was cleared and the exact e30 RETRAIN-20 queue was retried without overwriting baseline artifacts.
  -> [Detailed Explanation/Example] The retry used the same run root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_2316_KST_retrain20_augmented20_09b_fullft_maxlen8192`, same job manifest seeds `11/29/47`, full FT, PEFT/4bit disabled, `max_length=8192`, public20 validation unchanged.

- [Original Text/Data] Retry queue log recorded `JOB_TRAIN_FAIL plain_seed11_e30 rc=2`, `JOB_TRAIN_FAIL plain_seed29_e30 rc=2`, and `JOB_TRAIN_FAIL plain_seed47_e30 rc=2`, then `QUEUE_DONE 2026-05-27 23:36:31 KST`.
  -> [Exact Interpretation] No model checkpoint or eval metric was produced; all jobs failed before model load/training.
  -> [Detailed Explanation/Example] Training stderr shows `Completion label truncation preflight failed` for `generated20_codex-agent-fallback-targeted-schedule-00038`. A follow-up tokenizer scan found two failing train rows: `00038` with prompt token length `12357` and `00039` with prompt token length `12342`; both have zero shifted valid completion-label tokens under `max_length=8192`. Validation rows have `bad_count=0`.

- [Original Text/Data] Server marker `status/data_blocker_20260527_233835_KST.txt` records `reason=max_length_8192_completion_label_preflight_failed` and bad sample ids `generated20_codex-agent-fallback-targeted-schedule-00038,generated20_codex-agent-fallback-targeted-schedule-00039`.
  -> [Exact Interpretation] Exact RETRAIN-20 e30/e10 cannot run on this dataset under the baseline `max_length=8192` setting without changing the dataset or max length.
  -> [Detailed Explanation/Example] A follow-up worker must get an explicit decision before dropping/truncating those generated rows or changing max length, because any such change would make the comparison different from the requested exact augmented train set or from the baseline settings.
