<!-- Changed: add Job 185-188 submissions and update architecture note. -->
<!-- Why: reflect post-71.50 regression, revert, and current LoRA override approach. -->

# Submission Log

| Date | Commit | Job ID | Submission ID | Job Name | Public Score | Leaderboard Score | Notes |
|---|---|---:|---|---|---:|---:|---|
| 2026-05-17 | `872f31d` | 93 | `6629d72c38474f839b3723e553b557f6` | `team6-state-verifier-872f31d` | 100.00 | 60.50 | Public rule coverage only; hidden gap large. |
| 2026-05-17 | `fd43bd5` | 94 | `d59207632cad4289b347a2bb84fd71f8` | `team6-rule-coverage-fd43bd5` | 100.00 | 68.00 | Added spec index, coverage tool, Get field checks, DATA_COMMAND normalization, invalid Cellblock rule. |
| 2026-05-17 | `0c5e6d8` | 95 | `134f35f7e0dc4a0a89666a7590d8cb53` | `team6-metamorphic-0c5e6d8` | 100.00 | 68.00 | Added metamorphic/property diagnostics and GenKey empty-result check. |
| 2026-05-17 | `bf6c40b` | 96 | `f6e155417ebc4d3f8cf5b2af035363e5` | `team6-cpin-auth-bf6c40b` | 100.00 | 69.00 | Added C_PIN column-3 secret tracking for StartSession. |
| 2026-05-17 | `bcfdc94` | 97 | `a366f0990fc14ab2a5a9f44e82805a4f` | `team6-set-schema-bcfdc94` | 100.00 | 69.00 | Added Set duplicate-column INVALID_PARAMETER and empty-result payload checks. |
| 2026-05-17 | `fc6b8df` | - | - | `team6-endsession-fc6b8df` | 100.00 | - | Submission rejected: daily submission limit exceeded. Server diagnostics passed: metamorphic 948/948. |
| 2026-05-17 | `a814a87` | - | - | not submitted | 100.00 | - | Daily submission limit still blocked. Server diagnostics passed: metamorphic 970/970. |
| 2026-05-18 | `fc0289e` | 99 | `1dd86a84d1d34235acd8438bcf4967d5` | `team6-latest-fc0289e` | 100.00 | 69.00 | Latest HEAD submitted. Solver code matches `a814a87`; docs updated in `fc0289e`. Server diagnostics passed: metamorphic 970/970. |
| 2026-05-18 | `67cd09d` | 100 | `dcd43eb449a242e6a0cca623faae021f` | `team6-coverage-67cd09d` | 100.00 | 69.50 | Closed method-specific coverage gaps with synthetic-inclusive coverage, StartSession response validation, Properties/Get target/precondition tests, and DATA_COMMAND response invariants. Server diagnostics passed: metamorphic 1453/1453. |
| 2026-05-18 | `c613397` | 102 | `3440cbdce03e48529eacb057a3c84b77` | `team6-field-semantics-c613397` | 100.00 | 69.50 | Added known field semantics for C_PIN, Authority, Locking, and MBRControl; server diagnostics passed: metamorphic 1821/1821, synthetic-inclusive low_confidence 0. Score plateau suggests diagnostics are saturated rather than solved hidden coverage. |
| 2026-05-18 | `41b4df6` | 106 | `fcc52d52b98a437ca1afd7f3a9171f25` | `team6-mc-41b4df6` | 100.00 | 69.50 | Applied Ba et al. 2025 Metamorphic Coverage diagnostics to solver trace features. Server MC: pairs 1821, guidance pairs 1626, mean MC 5.67, zero-MC guidance pairs 245, MC CV 0.77 vs coverage CV 0.32. Solver behavior unchanged. |
| 2026-05-18 | `2df1e71` | 107 | `1871750633c343ccb8f2bc7af1fd0665` | `team6-locking-2df1e71` | 100.00 | **71.50** | Redesigned MC source/follow-up pairing and added guidebook-backed Locking ReadLocked/WriteLocked DATA_COMMAND access rules. Server diagnostics passed: metamorphic 1839/1839, low_confidence 0, MC guidance pairs 1648, mean MC 14.81, zero-MC guidance pairs 86. **BEST SCORE.** Branch `best-71.50` created. |
| 2026-05-19 | post-71.50 | 185 | - | - | 100.00 | 68.00 | Post-71.50 rule engine changes (UNEXPECTED_ERROR_STATUS removed, new rules added). **REGRESSION: -3.50 from best.** Root cause: changing UNEXPECTED_ERROR_STATUS to DEFAULT_PASS. |
| 2026-05-19 | embedding | 186 | - | - | 100.00 | 68.00 | 9B embedding + ridge classifier for DEFAULT_PASS cases. **REGRESSION: -3.50 from best.** Synthetic training data distribution mismatch with hidden test. |
| 2026-05-19 | revert | 187 | - | - | 100.00 | 71.50 | Reverted to `best-71.50` branch (commit `2df1e71`). **Score confirmed: 71.50.** |
| 2026-05-19 | auth rule | 188 | - | - | 100.00 | 71.50 | Added authentication rule on 71.50 base. No improvement but no regression. |

## Architecture Note (2026-05-19 update)

The architecture has evolved through three phases:

### Phase 1: Pure Rule Engine (up to 71.50)
- Deterministic `StatefulOpalVerifier` with `UNEXPECTED_ERROR_STATUS`
- All unexplained errors flagged as "fail" (aggressive approach)
- This remains the best leaderboard score: **71.50**

### Phase 2: RAG Hybrid (Cycle 1-6, abandoned)
- Confidence-gated: rule engine high confidence cases + RAG (BM25 + Qwen3.5-27B-FP8) for DEFAULT_PASS
- **Abandoned**: LLM zero-shot spec reasoning fail recall = 0% (logit mode), time exceeded (generation mode)

### Phase 3: Rule Engine + LoRA Override (current)
- Base: 71.50 rule engine with `UNEXPECTED_ERROR_STATUS`
- Override: Qwen3.5-4B + LoRA adapter reviews UNEXPECTED_ERROR_STATUS cases
- LoRA says "pass" -> override to pass (rescue false positive)
- LoRA says "fail" -> keep fail
- Best LoRA result: fail precision 100%, fail recall 46.9% on synthetic test set
- **HP sweep in progress** (LR, rank, alpha, dropout, max_length, batch size)

### Key Discovery: Regression Cause
- Post-71.50 changes that replaced `UNEXPECTED_ERROR_STATUS` with `DEFAULT_PASS` caused 71.50 -> 68.00
- The aggressive "unexplained error = fail" approach is correct for hidden test distribution
- All future work must start from `best-71.50` branch (commit `2df1e71`)
