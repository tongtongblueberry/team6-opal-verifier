# Progress Log

## Current Best: 73.00 (leaderboard)

| Job | Score | Method | Commit/Branch | Date |
|-----|-------|--------|---------------|------|
| 93 | 60.50 | Rule engine v1 | `872f31d` | 2026-05-17 |
| 94 | 68.00 | + spec index, Get rules | `fd43bd5` | 2026-05-17 |
| 96 | 69.00 | + C_PIN secret tracking | `bf6c40b` | 2026-05-17 |
| 100 | 69.50 | + coverage gaps | `67cd09d` | 2026-05-18 |
| **107** | **71.50** | **+ Locking access rules (UNEXPECTED_ERROR_STATUS)** | `2df1e71` / `best-71.50` | **2026-05-18** |
| 185 | 68.00 | Post-71.50 rule changes (REGRESSION) | - | 2026-05-19 |
| 186 | 68.00 | Embedding classifier (REGRESSION) | - | 2026-05-19 |
| 187 | 71.50 | Revert to best-71.50 (confirmed) | `2df1e71` | 2026-05-19 |
| 188 | 71.50 | + Authenticate rule (no change) | - | 2026-05-19 |
| - | **73.00** | **Solver bug fixes (auth detection + RO session write blocking)** | `solver-fix-auth-ro` | **2026-05-20** |
| - | 73.00 | + status code fix (SP_BUSY/FROZEN/LOCKED) | - | 2026-05-20 |

---

## Architecture

```
Input trajectory
       |
[1] Rule Engine (StatefulOpalVerifier.verify_with_trace) -- 73.00 base
       |
  prediction + rule_id
       |
  rule_id == UNEXPECTED_ERROR_STATUS?
       NO  --> rule prediction (high confidence)
       YES --> LoRA 4B override
              |
[2] Qwen3.5-4B + LoRA adapter (uncertainty resolver)
       |
  LoRA says "pass" --> override to pass (rescue false positive)
  LoRA says "fail" --> keep fail
```

**Key discovery**: `UNEXPECTED_ERROR_STATUS` (all unexplained errors = fail) is the core of the 71.50+ score. Changing this to `DEFAULT_PASS` (= pass) drops 3.5 points. The remaining ~54 hidden errors are mostly Column ACL cases that require LLM reasoning.

---

## Currently Running

**Gap retrain** on server (`/workspace/team6/`):
- Training uncertainty resolver with gap data (Column ACL focus, 209 gap cases = 73% of gap data)
- Step ~787/4660 (estimated)
- Auto-resume from checkpoint on restart (commit `914f6c1`)
- V4 format: filtered trajectory + TCG rule summary
- Quick HP sweep: 5 epochs x 6 configs

---

## Cycle Log

### Phase 1: RAG Hybrid (Cycles 1-6, abandoned)

**Cycle 1: RAG-Sequence Marginalization**
- BM25 retrieval + Qwen3.5-27B-FP8 logit scoring
- Result: fail recall 0% (severe pass-bias, p_fail max 0.35)
- 10 papers surveyed (Lewis 2020 RAG, Shi 2026 CRAG, Anthropic Contextual Retrieval, etc.)

**Cycle 2: RAG Generation Mode**
- Generation + thinking mode (8192 max tokens)
- Result: 67% accuracy on 6 DEFAULT_PASS cases, 811s/case (time exceeded)
- 10 papers (few-shot, calibration, rubric-based judging)

**Cycle 3: RAG Conclusion**
- Logit mode: 55% forced accuracy on public 20 (fail recall 10%)
- Generation mode: 407s/case average, 3-hour limit exceeded
- **Conclusion**: LLM zero-shot spec reasoning is insufficient. RAG abandoned.

### Phase 2: Test Data + Few-shot ICL (Cycles 4-6)

**Cycle 4: Large Test Set Generation**
- 206 DEFAULT_PASS synthetic cases generated (later expanded to 252)
- Generation mode: 4/6 = 67% on DEFAULT_PASS subset
- 20 papers surveyed (RAGAS, Self-Instruct, etc.)

**Cycle 5: Logit 252-case Evaluation**
- Logit mode on 252 balanced test set: fail recall = 0% (all 49 fails predicted as pass)
- **Confirmed**: logit scoring fundamentally cannot detect fail cases

**Cycle 6: Few-Shot ICL**
- 20-shot ICL logit mode on 252 cases: fail recall = 0% (identical to zero-shot)
- Based on Agrawal et al. (NeurIPS 2024) Many-Shot ICL
- **Conclusion**: Few-shot does not fix logit mode pass-bias

### Phase 3: Rule Engine Expansion (Cycles 7-10)

**Cycle 7: Coverage Gaps**
- Rule engine: 60.50 -> 69.50 via spec-based rules
- Metamorphic test generation: 1453 -> 1821 coverage pairs

**Cycle 8: Status Prediction Mode**
- Task reframing: predict expected status code instead of pass/fail
- 9B model feasibility check (28-30GB train, 0.5s/case inference)

**Cycle 9: Improved Status Parsing**
- 9B model test on server

**Cycle 10: Embedding Classifier -- REGRESSION**
- 9B embedding + Ridge regression for DEFAULT_PASS cases
- Leaderboard: **68.00** (regression from 71.50)
- Cause: synthetic training data distribution != hidden test distribution
- Reverted to rule engine only

**71.50 Achievement (Job 107)**
- Locking access rules + UNEXPECTED_ERROR_STATUS
- Branch `best-71.50` created (commit `2df1e71`)
- All unexplained errors aggressively marked as fail

### Phase 4: LoRA Fine-tuning (Cycles 11-15)

**Cycle 11: LoRA Research + 0.8B v1**
- 20 papers surveyed (LoRA, QLoRA, AdaLoRA, BCO, etc.)
- 0.8B v1 training: compressed format, 2163 cases
- Result: public fail recall 80%, synthetic fail recall 0%
- **Problem**: format information loss (method/status only)

**Cycle 12: LoRA 4B v2 (Rich Format) -- Breakthrough**
- 42 papers surveyed total
- Rich format v2: table, column, UID, payload, session state
- Result: **fail precision 100%, fail recall 46.9%** (synthetic 252 cases)
- First successful LLM approach

**Cycle 13: Regression Root Cause + Spec Mining**
- Confirmed: UNEXPECTED_ERROR_STATUS -> DEFAULT_PASS change caused 71.50 -> 68.00
- Spec mining: 15 unimplemented rules found (Column ACL, session exclusivity, etc.)

**Cycle 14: 71.50 Base Restoration + LoRA Integration**
- Restored best-71.50 code on main
- LoRA override architecture designed (UNEXPECTED_ERROR_STATUS cases only)
- Leaderboard 71.50 confirmed

**Cycle 15: HP Sweep Infrastructure**
- Sweep script (`tools/training/sweep_lora.py`): LR -> rank -> alpha -> dropout -> max_length -> model size
- Data: spec-based 1,435 cases (train 869 / val 283 / test 283)
- Phase 1 LR sweep results (5 epochs each):

| LR | Accuracy | Fail Prec | Fail Rec | F1 |
|----|----------|-----------|----------|-----|
| 5e-5 | 76.3% | 0.77 | 0.74 | 0.75 |
| 1e-4 | 77.0% | 0.77 | 0.76 | 0.76 |
| 2e-4 | 78.1% | 0.77 | 0.78 | 0.78 |
| **5e-4** | **79.5%** | **0.77** | **0.83** | **0.80** |
| 1e-3 | 78.8% | 0.74 | 0.88 | 0.80 |

**Cycle 15b: Code Restructure**
- 12 obsolete files deleted (rag.py, embedding_classifier.py, v1 scripts, etc.)
- tools/ reorganized into training/, eval/, datagen/, analysis/

### Phase 5: Autonomous Training Cycles (Cycles 16-21, dev branch)

**Cycle 16: Format Mismatch Fix**
- Critical bug: training used `->` but inference used unicode arrow `->` (different chars)
- All previous training invalidated, retrain required
- Commit `9194f59`

**Cycle 17 (implied): Gap Data Generation**
- 9 missing rule categories identified
- Gap data generation for Column ACL, session exclusivity, etc.
- Commit `f0082f2`

**Cycle 18: Uncertainty Resolver + Calibration Stack**
- Conformal Prediction calibration (Cycle 4 impl, commit `4cce5e3`)
- Self-distillation for calibration (commit `99bc0a6`)
- ConfTuner Brier score loss (commit `3808dff`)

**Cycle 19: Solver Bug Fixes -> 73.00**
- Auth detection fix + Read-Only session write blocking (commit `dec0840`)
- Revert/RevertSP no-session check + DEFAULT_PASS hardening (commit `057a88b`)
- Recognized 4 missing status codes + valid StartSession errors (commit `95333fa`)
- **Leaderboard: 73.00** (new best)
- Status code fix (SP_BUSY/FROZEN/LOCKED): no additional improvement -> hidden cases don't have these patterns

**Cycle 20: Submission Infrastructure**
- Safe submission builder (commit `a07554f`)
- Never touches `/workspace/project/` (other team member's workspace)

**Cycle 21: Training Data + Format Improvements**
- Column ACL gap data expanded: 70 -> 209 cases (73% of gap data, commit `765c439`)
- V4 format: filtered trajectory + TCG rule summary (commit `e37392d`)
- Auto-resume from checkpoint on restart (commit `914f6c1`)
- Quick HP sweep: 5 epochs x 6 configs (commit `884c3ef`)

---

## What Worked

| Approach | Impact | Notes |
|----------|--------|-------|
| UNEXPECTED_ERROR_STATUS | +2.00 (69.50 -> 71.50) | Aggressive: all unexplained errors = fail |
| Auth detection + RO write blocking | +1.50 (71.50 -> 73.00) | Solver bug fixes |
| LoRA 4B v2 rich format | fail prec 100%, rec 46.9% | Only successful LLM approach |
| Spec-based training data | val 79.5% accuracy | Replaced noisy metamorphic data |
| Label masking (answer tokens only) | Stable training | Loss focused on "pass"/"fail" tokens |

## What Did Not Work

| Approach | Result | Lesson |
|----------|--------|--------|
| Zero-shot logit (27B) | fail recall 0% | LLM has severe pass-bias |
| Few-shot ICL logit (27B) | fail recall 0% | Logit mode ignores examples |
| Generation + thinking (27B) | 67%, 811s/case | Time exceeded (3h limit) |
| Embedding + Ridge (9B) | 68.00 regression | Distribution mismatch |
| LoRA 0.8B v1 (compressed) | synthetic fail recall 0% | Format information loss |
| Post-71.50 rule additions | 68.00 regression | Removing UNEXPECTED_ERROR_STATUS = -3.5 pts |
| Status code additions (SP_BUSY etc.) | No change (73.00) | Hidden cases lack these patterns |

---

## Next Steps

1. **Complete gap retrain** -- uncertainty resolver with Column ACL focus (currently running)
2. **Evaluate gap-trained model on public** -- target: override false positives among UNEXPECTED_ERROR_STATUS
3. **Leaderboard submission** -- rule engine (73.00 base) + LoRA override
4. **9B model comparison** -- if 4B is insufficient
5. **Additional solver rules** -- only safe additions on 73.00 base (Column ACL rules are highest priority)

---

## Training Data

| Set | Pass | Fail | Total | Source |
|-----|------|------|-------|--------|
| train | 486 | 383 | 869 | Spec-based generation |
| val | 145 | 138 | 283 | Spec-based generation |
| test | 157 | 126 | 283 | Spec-based generation |
| gap (Column ACL) | - | - | 209 | Gap data generation |
| **Total** | - | - | **1,644+** | |

Previous data (metamorphic 2,163 cases, ~29% label noise) deprecated.

---

## Server

- Host: `147.46.78.61:2227`, User: `student`
- GPU: L40S 48GB
- Pre-cached models: Qwen3.5-{0.8B, 2B, 4B, 9B, 27B-FP8}, gemma-4-*
- Installed: peft, wandb, kernels (FP8), scikit-learn
- Code: `/workspace/team6/team6-opal-verifier/` (dev branch)
- Training data: `/workspace/team6/training_data/`
- Adapters: `/workspace/team6/adapters/`
