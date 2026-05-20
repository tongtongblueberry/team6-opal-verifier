# Team 6 Opal Verifier

SSD TCG/Opal command-response trajectory pass/fail classification.
SNU Introduction to Deep Learning (M2177.0043) | Due: 2026-06-08

## Leaderboard

| Score | Method | Commit/Branch | Date |
|-------|--------|---------------|------|
| **73.00** | **Rule engine bug fixes (auth + RO write blocking)** | `solver-fix-auth-ro` / `dev` | **2026-05-20** |
| 71.50 | Rule engine (UNEXPECTED_ERROR_STATUS) | `2df1e71` / `best-71.50` | 2026-05-18 |
| 69.50 | Rule engine (field semantics) | `c613397` | 2026-05-18 |
| 68.00 | Rule engine (spec index) | `fd43bd5` | 2026-05-17 |
| 60.50 | Rule engine (initial) | `872f31d` | 2026-05-17 |

## Architecture: Rule Engine + LoRA Hybrid

```
Input trajectory (JSON command-response sequence)
       |
[1] Rule Engine (StatefulOpalVerifier)
       |  - Stateful session/auth/SP/locking tracking
       |  - 50+ spec-derived rules
       |  - UNEXPECTED_ERROR_STATUS: all unexplained errors -> fail
       |
  prediction + rule_id
       |
  Specific rule matched?
       YES --> Use rule prediction directly (high confidence)
       NO  --> rule_id == UNEXPECTED_ERROR_STATUS
              |
[2] LoRA Override (Qwen3.5-4B + LoRA adapter v2)
       |  - Rich format: method, status, payload, session state, TCG rule summary
       |  - Logit comparison: p(pass) vs p(fail)
       |
  LoRA says "pass" --> Override to pass (rescue false positive)
  LoRA says "fail" --> Keep fail (agree with rule engine)
```

**Key insight**: The aggressive approach (all unexplained errors = fail) scores higher on hidden test data than the conservative approach (unexplained errors = pass). The LoRA adapter selectively rescues false positives.

## Project Structure

```
src/                              # Submission code (deployed to evaluation server)
+-- __init__.py
+-- solver.py                     # Rule engine + Solver class (73.00 base)
+-- lora_solver.py                # LoRA adapter inference (v2 only, logit comparison)

tools/
+-- training/                     # Training pipeline
|   +-- sweep_lora.py             # HP sweep (LR -> rank -> alpha -> dropout -> len -> model)
|   +-- finetune_lora_v2.py       # Rich format training + label masking
|   +-- train_uncertainty_resolver.py  # Uncertainty resolver (tier-based LoRA + rule context)
|   +-- build_training_data.py    # Training data builder from rule engine oracle
|   +-- brier_trainer.py          # ConfTuner Brier score loss for calibration
|   +-- self_distill.py           # Self-distillation for calibration
|   +-- generate_uncertainty_data.py   # Uncertainty training data generation
|   +-- format_v4.py              # V4 format: filtered trajectory + TCG rule summary
|   +-- quick_sweep.py            # Quick HP sweep: 5 epochs x 6 configs
|   +-- deploy_and_train.sh       # Deploy code to server and start training
|   +-- run_full_pipeline.sh      # Full pipeline automation
|   +-- run_9b_pipeline.sh        # 9B model training pipeline
|   +-- cycle2_train.py           # [archive candidate] Cycle 2 training script
|   +-- cycle3_train.py           # [archive candidate] Cycle 3 training script
+-- eval/                         # Evaluation
|   +-- eval_lora.py              # LoRA model evaluation on public/synthetic data
|   +-- metamorphic_eval.py       # Metamorphic/synthetic test generation
|   +-- mutation_eval.py          # Mutation testing for rule adequacy
|   +-- conformal_calibration.py  # Conformal prediction calibration
|   +-- diagnose_public.py        # Public 20 case diagnosis
|   +-- prepare_submission.sh     # Submission preparation script
+-- datagen/                      # Data generation
|   +-- generate_spec_data.py     # Spec-based training data (1,435 cases)
|   +-- generate_gap_data.py      # Gap data for missing rule categories (209 Column ACL cases)
+-- analysis/                     # Diagnostics
    +-- cycle0_diagnose.py        # Baseline diagnostic measurements
    +-- rule_coverage.py          # Rule/spec coverage analysis
    +-- metamorphic_coverage.py   # Metamorphic coverage metrics
    +-- intermediate_eval.py      # Intermediate checkpoint evaluation
    +-- test_fail_dp_cases.py     # DEFAULT_PASS fail case analysis

configs/
+-- wandb_sweep.yaml              # W&B sweep configuration

docs/
+-- papers.md                     # Paper archive (42+ papers across all cycles)
+-- server_setup.md               # Server structure and deployment guide
+-- overfitting_analysis.md       # 12 papers + 12 improvement methods for LoRA overfitting
+-- spec_rules.md                 # Spec-derived rules documentation
+-- sweep_plan.md                 # HP sweep plan (architecture, loss, metrics)
+-- archive/                      # Historical documentation from earlier cycles

setup.sh                          # Evaluation setup script (installs peft, runs smoke test)
pyproject.toml                    # Package metadata (no runtime dependencies)
PROGRESS.md                       # Complete experiment log and timeline
```

## How to Train

### Prerequisites

- Server access: `ssh student@147.46.78.61 -p 2227`
- Pre-cached models at `/dl2026/skeleton/model_cache/`
- Training data at `/workspace/team6/training_data/`

### Deploy Code to Server

```bash
# Deploy src/ and tools/ to server
sshpass -p '$PASSWORD' scp -P 2227 -r \
  src/ tools/ setup.sh pyproject.toml \
  student@147.46.78.61:/workspace/team6/team6-opal-verifier/
```

### Run Training

```bash
# Option 1: Full pipeline (deploy + train + evaluate)
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   nohup bash tools/training/run_full_pipeline.sh > /workspace/team6/pipeline.log 2>&1 &"

# Option 2: HP sweep
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   nohup python3 tools/training/sweep_lora.py > /workspace/team6/sweep.log 2>&1 &"

# Option 3: Quick sweep (5 epochs x 6 configs)
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   nohup python3 tools/training/quick_sweep.py > /workspace/team6/quick_sweep.log 2>&1 &"

# Monitor training
ssh student@147.46.78.61 -p 2227 "tail -30 /workspace/team6/pipeline.log"
```

## How to Evaluate

```bash
# Evaluate LoRA model on public 20 cases
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   python3 tools/eval/eval_lora.py --dataset-root /dl2026/dataset"

# Diagnose public cases (rule engine only)
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   python3 tools/eval/diagnose_public.py --dataset-root /dl2026/dataset"
```

## How to Submit

```bash
# Prepare submission directory
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   bash tools/eval/prepare_submission.sh"

# Submit (submit command available on server)
ssh student@147.46.78.61 -p 2227 \
  "submit --dir /workspace/team6/submit-latest/"
```

Submission includes `src/` (solver + lora_solver) + `setup.sh` + `pyproject.toml`. Model weights (LoRA adapter) are loaded from the evaluation server's model cache; the adapter itself is small (~32MB) and can be included in the submission directory under `artifacts/`.

## Constraints (project.pdf p.10)

- **Evaluation**: NO network access, 3 hours, L40S 48GB
- **Setup**: Network available, 20 minutes
- **Models**: Pre-cached only (Qwen3.5-{0.8B,2B,4B,9B,27B-FP8}, gemma-4-*)
- **Submission size**: 12GB max
- **Daily submission quota**: Limited (often exceeded)

## References

- Hu, E. J. et al. (2022). *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR.
- Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
- TOGLL (ASE 2024): Fine-tuned small models beat large zero-shot 3.8x.
- Zhang et al. (ICLR 2024): Model scaling > data scaling for fine-tuning.
- Agrawal et al. (NeurIPS 2024): Many-Shot In-Context Learning.
- See `docs/papers.md` for the full 42+ paper archive.
