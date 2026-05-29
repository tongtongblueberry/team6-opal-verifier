<!-- Changed: archive the active-doc synchronization for public20 10/10 and official Self-Instruct dry-run/schema mapping. -->
<!-- Why: future workers need a dated evidence record that separates implemented artifacts from remaining no-go gates. -->

# 2026-05-27 Active Docs 10/10 Self-Instruct Sync

[Original Text/Data] User-provided fact: public20 10/10 split builder is implemented at `runs/model_validation/public20_10_10_splits`; seed `11`, `29`, `47` each have `train=10`, `val=10`, train label `fail=5/pass=5`, val label `fail=5/pass=5`, and no public20 test split.
→ [Exact Interpretation] The active public20-only model-validation input is the balanced 10/10 split directory, not the old 16/4 directory.
→ [Detailed Explanation/Example] Active docs now point workers to `runs/model_validation/public20_10_10_splits` for the next TRL dataset conversion. Any local public20 `test` split remains forbidden because the hidden leaderboard is the test.

[Original Text/Data] User-provided fact: existing `runs/model_validation/public20_splits` 16/4 outputs are archive-only.
→ [Exact Interpretation] The previous 16 train / 4 val split may remain as historical evidence but must not drive active training, validation restart, or sample decisions.
→ [Detailed Explanation/Example] Active docs can mention `runs/model_validation/public20_splits` only as 16/4 archive-only evidence. The next training worker should not convert that directory into a TRL dataset.

[Original Text/Data] User-provided fact: official Self-Instruct dry-run/schema mapping is implemented, including instruction generation artifact, classification detection audited no-op artifact, output-first instance artifact, and prepare/finetuning candidate artifact reflected in code/tests.
→ [Exact Interpretation] The repository now has the official-protocol artifact contracts for local dry-run/schema wiring, but these are not accepted generated data.
→ [Detailed Explanation/Example] Active docs now distinguish implemented contracts from real data: the dry-run artifacts can prove payload/schema wiring, while accepted synthetic data still requires external LLM raw output, parsing, deduplication, judge filtering, and gates.

[Original Text/Data] User-provided fact: no real LLM raw output exists yet, Gate A/B/C/D do not exist yet, and sample publication remains no-go.
→ [Exact Interpretation] `docs/samples/self_instruct_sample.md` must not be created as an accepted sample record.
→ [Detailed Explanation/Example] Even with parser/judge/schema code and public20 10/10 split artifacts, the sample policy remains blocked until a real raw generation candidate passes parser, dedup, judge, Gate A, Gate B, Gate C, Gate D, and Self-Instruct quality verification.

[Original Text/Data] User-provided fact: split builder 6 tests OK, self_instruct 23 tests OK, and worker `git diff --check` OK.
→ [Exact Interpretation] Prior workers reported focused verification for the split builder, Self-Instruct code path, and whitespace diff checks.
→ [Detailed Explanation/Example] This archive records those reported results as handoff facts. The current docs sync still reruns stale phrase grep, key phrase grep, and `git diff --check` before final reporting.

[Original Text/Data] User-provided next step: 10/10 TRL dataset conversion and GPU training restart remain.
→ [Exact Interpretation] Split creation is no longer the next active task; dataset conversion and training restart are.
→ [Detailed Explanation/Example] Active docs now say the next worker should convert `runs/model_validation/public20_10_10_splits` to TRL datasets, sync server state as needed, and restart GPU training without using the archived 16/4 outputs.
