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
        [2] LoRA Override (Qwen3.5-4B + LoRA adapter)
            |
            +-- LoRA says "pass" --> Override to pass (rescue false positive)
            +-- LoRA says "fail" --> Keep fail
```

**Key discovery**: `UNEXPECTED_ERROR_STATUS` (모든 unexplained error = fail)이 71.50의 핵심.
이것을 `DEFAULT_PASS`(= pass)로 바꾸면 68.00으로 하락. LoRA는 이 중 false positive만 선별 rescue.

## LoRA 4B v2 Results (synthetic 252 cases)

| Metric | Value |
|--------|-------|
| Fail precision | **100%** (0 false positives) |
| Fail recall | **46.9%** (23/49) |
| Accuracy | **89.7%** (226/252) |

## Current: HP Sweep

서버에서 LoRA hyperparameter sweep 실행 중.
- LR: {5e-5, 1e-4, 2e-4, 5e-4, 1e-3}
- Rank, alpha, dropout, max_length 순차 sweep
- Scheduler: cosine, Optimizer: AdamW, Batch: 8 (VRAM 94%)
- 상세: `docs/sweep_plan.md`

## Files

| File | Role |
|------|------|
| `src/solver.py` | Rule engine (best-71.50) + LoRA override |
| `src/lora_solver.py` | LoRA adapter loading and prediction |
| `tools/sweep_lora.py` | HP sweep script |
| `tools/finetune_lora_v2.py` | LoRA training (rich format + label masking) |
| `tools/eval_lora.py` | LoRA evaluation |
| `PROGRESS.md` | Full experiment log (Cycle 1-15) |
| `docs/sweep_plan.md` | HP sweep plan (architecture, loss, metrics) |
| `docs/archive/` | Historical docs |

## References

- Hu, E. J. et al. (2022). *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR.
- Lewis, P. et al. (2020). *RAG for Knowledge-Intensive NLP Tasks*. NeurIPS.
