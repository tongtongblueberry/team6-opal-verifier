<!-- Changed: archive the server-side public20 10/10 TRL full fine-tuning queue restart. -->
<!-- Why: the active docs/code are intentionally untouched while preserving run root, queue, dataset, and initial GPU evidence. -->

# public20 10/10 TRL 0.9B Full FT Queue Restart

- 작성 시각: 2026-05-27 05:50 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 서버 run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft`
- 서버 repo snapshot: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft/repo`
- queue pid: `318407`
- queue log: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft/queue.log`
- queue script: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft/run_queue.sh`
- queue plan: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft/queue_plan.md`
- job manifest: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft/job_manifest.tsv`

## Structural Skeleton

- `queue_plan.md`: server-only plan, forbidden inputs, dataset dirs, epoch grid, eval policy.
- `job_manifest.tsv`: `variant`, `seed`, `epochs` rows.
- `run_queue.sh`: TRL full FT training, generation eval, logprob eval, p_fail sidecar writer.
- `logs/`: queue/train/eval stdout and stderr logs.
- `plans/`: per-job TRL dry/dependency plan JSON/Markdown from the training runner.
- `models/`: per-job final full model directories.
- `eval/`: generation/logprob metric JSON/Markdown and derived p_fail sidecars.
- `status/`: per-job status marker.

## Queue Inputs

[Original Text/Data] `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_11`, `plain_seed_29`, `plain_seed_47`, `retrieved_seed_11`, `retrieved_seed_29`, `retrieved_seed_47`
-> [Exact Interpretation] Active public20 10/10 TRL prompt-completion datasets are the only training inputs.
-> [Detailed Explanation/Example] Each dataset has `train.jsonl` and `validation.jsonl`, with `10` rows per split and label balance `pass=5`, `fail=5`. No generated synthetic data, old 16/4 split, public20 test split, or interrupted 4B queue output is used.

[Original Text/Data] model `Qwen/Qwen3.5-0.8B`; trainer command omits `--use-peft`.
-> [Exact Interpretation] The queue is the requested 0.9B-class full fine-tuning lane with PEFT/LoRA disabled.
-> [Detailed Explanation/Example] `tools/training/run_trl_sft_public20.py` verifies full trainable mode after TRL `SFTTrainer` constructs the model. Per-job plan files are written under `plans/`.

## Epoch Grid

[Original Text/Data] `job_manifest.tsv` order: plain seeds `11/29/47` e20, retrieved seeds `11/29/47` e20, plain e30, retrieved e30, plain e5, retrieved e5, plain e10, retrieved e10.
-> [Exact Interpretation] The queue starts with the required high-priority e20/e30 plain/retrieved matched runs, then fills the e5/e10 grid if time allows.
-> [Detailed Explanation/Example] All run dirs are separated as `models/{plain|retrieved}_seed{seed}_e{epochs}`.

## Initial Server Status

[Original Text/Data] Pre-start GPU check: `0, NVIDIA L40S, 0 MiB, 46068 MiB, 0 %`; compute-app list empty.
-> [Exact Interpretation] No existing GPU job was running before queue start.
-> [Detailed Explanation/Example] The queue was started only after this check, satisfying the no-overlap requirement.

[Original Text/Data] Queue head after start: `QUEUE_START 2026-05-27 05:46:35 KST`, `JOB_START plain_seed11_e20 2026-05-27 05:46:35 KST`.
-> [Exact Interpretation] Background queue started and began the first high-priority plain e20 job.
-> [Detailed Explanation/Example] Queue PID was recorded in `queue.pid` as `318407`.

[Original Text/Data] First training check: `plain_seed11_e20` loaded train/validation splits, began `40` train steps, and GPU reported `27307 MiB / 46068 MiB`, `82 %`.
-> [Exact Interpretation] The process entered real GPU training.
-> [Detailed Explanation/Example] Compute app PID `318415` was `/workspace/sinjeongmin_opal_verifier/ops/venvs/trl_sft/bin/python`.

## Eval Policy

[Original Text/Data] `eval_trl_sft_public20_generation.py` runs on `validation.jsonl` and `eval_trl_sft_public20_logprob.py` runs with `--max-length 8192`.
-> [Exact Interpretation] Each completed training job gets both generation metrics and conditional pass/fail logprob metrics on the 10 validation rows.
-> [Detailed Explanation/Example] The logprob evaluator has no threshold/calibration CLI. The queue writes a sidecar `*.logprob_pfail.json` deriving `p_fail_from_mean_logprob_softmax` from raw saved pass/fail candidate mean logprobs.
