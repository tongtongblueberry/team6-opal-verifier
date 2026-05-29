<!-- Changed: add final leaderboard submission record for the 0.9B e30 plain full-FT package. -->
<!-- Why: the submission worker needs an immutable archive note with artifact, package, gate, and submit IDs. -->

# 2026-05-27 23:41 KST Leaderboard Submission

## Summary

- Worker: LEADERBOARD-SUBMISSION.
- Result: submit server accepted the package.
- Job ID: `668`.
- Submission ID: `5bcc1bdda5e347d499aa99adbb2ba2ee`.
- Job Name: `09b-e30-plain-seed11-fullft-20260527`.

## Selected Checkpoint

- Run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0716_KST_public20_trl_10_10_09b_fullft_maxlen8192`.
- Selected full-model checkpoint: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0716_KST_public20_trl_10_10_09b_fullft_maxlen8192/models/plain_seed11_e30`.
- Selection rationale: e30 plain aggregate was the current best validation evidence with acc `0.8000`, aggregate macro-F1 `0.7964`, fail/pass recall `0.6667/0.9333`, pooled `TP=10 TN=14 FP=1 FN=5`.
- Single-seed rationale: `plain_seed11_e30` had acc `0.8000`, macro-F1 `0.8000`, fail/pass recall `0.8000/0.8000`, confusion `TP=4 TN=4 FP=1 FN=1`. `plain_seed29_e30` and `plain_seed47_e30` had acc `0.8000`, macro-F1 `0.7917`, fail/pass recall `0.6000/1.0000`, confusion `TP=3 TN=5 FP=0 FN=2`.

## Package

- Package path: `/workspace/sinjeongmin_opal_verifier/ops/submission_worker_20260527_2317_KST_leaderboard_seed11_e30/submissions/submit-plain_seed11_e30`.
- Package artifact layout: `artifacts/merged_model/`.
- Full FT package source was copied directly from the selected full-model directory. `tools/eval/export_merged_model.py` was not used.
- Package size: `3432155481` bytes, below the 12GB limit.

## Gates

- `tools/eval/check_submit_package.py`: passed, reported `OK: submit package HF offline/artifact readiness (merged_model)`.
- No-rule scan: passed for `src/__init__.py` and `src/solver.py`.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward`: passed. It loaded the package-local merged model and `predict_one` returned `pass`.
- The first-forward gate was run with `CUDA_VISIBLE_DEVICES=""` because a separate GPU process was active. This avoided interfering with the parallel worker while still proving package-local offline model load and first forward.

## Code Changes Used By The Package

- `tools/eval/prepare_submit.sh`: added `--full-model` / `--merged-model` support and copies standalone full-model checkpoints to `artifacts/merged_model/`.
- `src/solver.py`: added `OPAL_MAX_LENGTH` default `8192`, raw public20 JSON string parsing, package-local full-model loading, and full-model-only TRL prompt-completion pass/fail logprob scoring.
- Focused local verification before server package build: `bash -n tools/eval/prepare_submit.sh`, `python3 -m py_compile src/solver.py tools/eval/check_submit_package.py tools/eval/runtime_smoke_submit_package.py`, and `PYTHONPATH=. uv run --with pytest pytest tests/test_prepare_submit_script.py tests/test_submit_package_readiness.py tests/test_runtime_smoke_submit_package.py tests/test_solver_merged_model_path.py` passed `24`.

## Remaining Blockers

- No blocker for this submission lane.
- DATA-CLEANUP and synthetic data eligibility remain separate: active final data path is `runs/self_instruct/targeted_schedule_20260527_192440_KST/manifest.record_count_preserved.codex_agent_fallback.jsonl`, but fallback provenance and incomplete ablations/Gate D still block synthetic sample/training eligibility.
