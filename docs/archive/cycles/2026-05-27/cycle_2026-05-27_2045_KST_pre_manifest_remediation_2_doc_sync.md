<!-- Changed: archive final known state before manifest-remediation-2 result. -->
<!-- Why: future workers need one dated record covering 4B retrieved completion, targeted retry partial improvement, and the active DATA-REMEDIATION-2 lane. -->

# 2026-05-27 20:45 KST Pre-Manifest-Remediation-2 Doc Sync

## Scope

- Updated active docs: `PROGRESS.md`, `docs/current_task.md`, `docs/current_self_instruct_data_plan.md`, `docs/server_operations_current.md`, `docs/agent_handoff.md`.
- Read but did not modify `README.md` because the executor ownership set excluded it.
- Repo-root `AGENTS.md` was absent.
- This record captures the final known state before manifest-remediation-2 result.

## 4B Retrieved Queue

[Original Text/Data] 4B retrieval queue done at `2026-05-27 20:24:16 KST`.
→ [Exact Interpretation] The previously active 4B retrieved-context queue is no longer a polling target.
→ [Detailed Explanation/Example] Follow-up workers should not wait for `retrieved_seed47_e30`; the queue result is complete and must be treated as below-best validation evidence.

[Original Text/Data] e30 generation aggregate acc `0.6667`, macro-F1 `0.6652`; e20 generation aggregate acc `0.5667`, macro-F1 `0.5662`; e10 generation/logprob aggregate acc `0.5333`, macro-F1 `0.5313`.
→ [Exact Interpretation] 4B retrieved underperformed the current 0.9B e30 plain best across recorded aggregates.
→ [Detailed Explanation/Example] The current best remains 0.9B e30 plain acc `0.8000`, macro-F1 `0.7964`; 4B retrieved is no-go primary.

[Original Text/Data] e30/e20 logprob had OOMs.
→ [Exact Interpretation] e30/e20 retrieved logprob metrics are incomplete due memory failures.
→ [Detailed Explanation/Example] The usable final 4B retrieved evidence is generation aggregate for e30/e20 and generation/logprob aggregate for e10, with no primary-candidate promotion.

## Targeted Retry

[Original Text/Data] Targeted schedule fallback smoke: `40` targets, labels `pass=20/fail=20`, record_count mean `16.4`; generated all `40` fallback candidates.
→ [Exact Interpretation] The scheduled retry produced the full intended fallback pool with balanced labels and public20-like accepted-pool mean target.
→ [Detailed Explanation/Example] This improves over the earlier 11-row short-history fallback pool, but fallback provenance still blocks sample/training claims.

[Original Text/Data] parse `40/0`, dedup `40/0`, judge `40/0`, Gate A qualitative accepted `40/0`.
→ [Exact Interpretation] Parser, duplicate filtering, judge, and qualitative Gate A accepted the targeted fallback pool without rejects.
→ [Detailed Explanation/Example] These passes establish a larger accepted fallback pool, but downstream Gate B subset preservation, ablation count, provenance, Gate D, package, and training gates still control eligibility.

[Original Text/Data] accepted-pool Gate B passed with record_count mean delta `0.0`; Gate C passed `33/33`.
→ [Exact Interpretation] The full accepted pool fixed the prior record_count mean mismatch, and the selected candidate set passed model-input equivalence.
→ [Detailed Explanation/Example] The improvement is real at accepted-pool level, but must survive manifest selection.

[Original Text/Data] manifest selected `33/40`, label `fail=16/pass=17`, train `fail=12/pass=11`, length JSD `0.074814 <= 0.08`, validation passed.
→ [Exact Interpretation] The manifest validator accepted the selected subset and length distribution threshold.
→ [Detailed Explanation/Example] DATA-RETRY is completed with partial improvement because the retry moved past previous manifest validation blockers.

[Original Text/Data] manifest-selected subset Gate B still has `record_count_mean_difference`; subset mean/max `13.7576/28` vs accepted/public `16.4/39`.
→ [Exact Interpretation] Manifest selection did not preserve the accepted-pool/public record_count distribution.
→ [Detailed Explanation/Example] The next remediation target is not generic generation; it is manifest selection distribution preservation.

## Decision

[Original Text/Data] sample/training still false due fallback provenance, count below ablation sizes, subset Gate B mismatch, no Gate D/package/training.
→ [Exact Interpretation] No accepted sample, synthetic training eligibility, package decision, or leaderboard basis exists from this state.
→ [Detailed Explanation/Example] `docs/samples/self_instruct_sample.md` remains absent/no-go until provenance, ablation count, Gate B selected-subset distribution, Gate D, package, and training evidence are resolved.

[Original Text/Data] DATA-REMEDIATION-2 is now in progress: manifest selection distribution preservation.
→ [Exact Interpretation] The active data lane is remediation of the selected manifest subset distribution.
→ [Detailed Explanation/Example] The next archive record should report whether manifest-remediation-2 preserves record_count mean/max in the selected subset before changing sample/training/package status.

## Checklist

- GPU train/eval: completed.
- DATA-RETRY: completed with partial improvement/no sample.
- DATA-REMEDIATION-2: in progress.
- PACKAGE: pending.
- DOC-SYNC: in progress for this pre-remediation-2 state.
