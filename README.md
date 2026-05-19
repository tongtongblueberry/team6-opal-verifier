# Team 6 Opal Verifier

SSD TCG/Opal command-response trajectory pass/fail classification.
SNU Introduction to Deep Learning (M2177.0043) | Due: 2026-06-08

## Leaderboard

| Score | Method | Commit | Date |
|-------|--------|--------|------|
| **71.50** | Rule engine (UNEXPECTED_ERROR_STATUS) | `2df1e71` | 2026-05-18 |
| 69.50 | Rule engine (field semantics) | `c613397` | 2026-05-18 |
| 68.00 | Rule engine (spec index) | `fd43bd5` | 2026-05-17 |
| 60.50 | Rule engine (initial) | `872f31d` | 2026-05-17 |

Best branch: `best-71.50`

## Architecture

```
Trajectory
    |
[1] Rule Engine (StatefulOpalVerifier) -- best-71.50 base
    |
    +-- Specific rule matched --> Use rule prediction (pass or fail)
    |
    +-- UNEXPECTED_ERROR_STATUS --> "fail" (aggressive: all unexplained errors)
            |
        [2] LoRA Override (Qwen3.5-4B + LoRA adapter v2)
            |
            +-- LoRA says "pass" --> Override to pass (rescue false positive)
            +-- LoRA says "fail" --> Keep fail
```

**Key discovery**: `UNEXPECTED_ERROR_STATUS` (모든 unexplained error = fail)이 71.50의 핵심.
이것을 `DEFAULT_PASS`(= pass)로 바꾸면 68.00으로 하락. LoRA는 이 중 false positive만 선별 rescue.

## Current: HP Sweep (Cycle 15)

서버에서 LoRA hyperparameter sweep 실행 중.
- Data: spec-based 1,435건 (train 869 / val 283 / test 283)
- Sweep: LR → rank → alpha → dropout → max_length → model size → final test eval
- HP selection: val fail_recall (precision ≥ 0.9), final: test set unbiased estimate
- Fixed: cosine scheduler, AdamW, batch=8 (VRAM 94%)
- 상세: `docs/sweep_plan.md`

초기 결과 (Step 1 LR sweep):

| LR | Accuracy | Fail Precision | Fail Recall | F1 |
|----|----------|----------------|-------------|-----|
| 5e-5 | 76.3% | 0.77 | 0.74 | 0.75 |
| 1e-4 | 77.0% | 0.77 | 0.76 | 0.76 |

## Project Structure

```
src/                          # Submission code (제출용)
├── solver.py                 # Rule engine + Solver (best-71.50 base)
└── lora_solver.py            # LoRA adapter inference (v2 only)

tools/
├── training/                 # Training pipeline
│   ├── sweep_lora.py         # HP sweep (LR→rank→alpha→dropout→len→model)
│   ├── finetune_lora_v2.py   # Rich format + label masking
│   └── build_training_data.py
├── eval/                     # Evaluation
│   ├── eval_lora.py          # LoRA model evaluation
│   ├── metamorphic_eval.py   # Metamorphic/synthetic test generation
│   └── mutation_eval.py      # Mutation testing for rule adequacy
├── datagen/                  # Data generation
│   └── generate_spec_data.py # Spec-based training data (1,435 cases)
└── analysis/                 # Diagnostics
    ├── rule_coverage.py      # Rule/spec coverage analysis
    ├── metamorphic_coverage.py
    ├── intermediate_eval.py
    └── test_fail_dp_cases.py

artifacts/                    # Model artifacts (generated, not in git until trained)
└── lora_adapter_v2/          # LoRA adapter weights (~12MB)

docs/
├── sweep_plan.md             # HP sweep plan (architecture, loss, metrics)
├── spec_rules.md             # Spec-derived rules
└── archive/                  # Historical docs
```

## References

- Hu, E. J. et al. (2022). *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR.
- TOGLL (ASE 2024): Fine-tuned small models beat large zero-shot 3.8x.
- Zhang et al. (ICLR 2024): Model scaling > data scaling for fine-tuning.
