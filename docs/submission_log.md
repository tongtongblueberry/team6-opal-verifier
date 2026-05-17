<!-- Added: track leaderboard submissions without hidden-label inference. -->
<!-- Why: only commit-level score feedback should be retained from leaderboard. -->

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
