<!-- Changed: archive SAMPLE-RESOLVE quantified remediation decision. -->
<!-- Why: future workers need a dated record that sample absence is diagnosed as a target-controlled data-generation remediation problem, not an ignored no-go. -->

# 2026-05-27 SAMPLE-RESOLVE Data Remediation

## Scope

- Updated active docs: `PROGRESS.md`, `docs/current_task.md`, `docs/current_self_instruct_data_plan.md`, `docs/agent_handoff.md`.
- This record covers the resolved sample/data analysis for the `codex_agent_fallback` pool, public20 comparison, manifest rerun, training impact, and remediation criteria.
- No code, generated manifests, server state, or `docs/samples/self_instruct_sample.md` were edited.

## Resolution

[Original Text/Data] SAMPLE is not simply closed/no-go; it is resolved as an active remediation problem: fallback pool cannot produce sample because public20 dimensional mismatch and training-input bias are quantified.
→ [Exact Interpretation] The sample remains absent, but the reason is now explicit and measurable.
→ [Detailed Explanation/Example] The next valid action is target-controlled generation aimed at the failed dimensions, not a generic retry or silent closure.

[Original Text/Data] `sample.md` remains absent until Gate A/B/C/D and ablations pass, but the issue is now explicitly diagnosed, not ignored.
→ [Exact Interpretation] `docs/samples/self_instruct_sample.md` is still no-go by policy.
→ [Detailed Explanation/Example] A sample can only be published after generated data passes state-transition audit, public20 dimension comparison, manifest/model-input equivalence, submission gate, and data-size ablations.

## Public20 Comparison

[Original Text/Data] Public20 vs fallback accepted: rows `20` vs `11`; labels `fail=10/pass=10` vs `fail=3/pass=8`; record_count min/median/mean/max `1/16/16.4/39` vs `1/2/2.090909/3`; input chars Gate B profile `429/6911.3/15256` vs `325/614.818/888`; length bins public `1-32=18` and `33-64=2` vs fallback `1-32=11` only; final method/status diversity narrower; fallback lacks fail in calibration/hidden.
→ [Exact Interpretation] The fallback pool is smaller, pass-skewed, shallower, shorter, and narrower than the public20 reference.
→ [Detailed Explanation/Example] Even an accepted fallback sample would represent short-history data, not the public20 conversation-depth profile.

[Original Text/Data] Gate B failure: `record_count_mean_difference`; conversation-depth mismatch, not just row count.
→ [Exact Interpretation] Adding more rows without deeper trajectories would not resolve Gate B.
→ [Detailed Explanation/Example] Future generation must control `target_record_count` per candidate.

## Manifest Rerun

[Original Text/Data] Manifest validation rerun with public20 reference: `overall_gate_passed=false`, length JSD `0.525597`, char mean ratio `0.073042`, split label balance failed.
→ [Exact Interpretation] The fallback manifest remains invalid against the public20 reference profile.
→ [Detailed Explanation/Example] The failure is consistent with the short input profile and missing fail labels outside train.

## Training Impact

[Original Text/Data] Public20 TRL train/val per seed is `10/10` `fail=5/pass=5`; fallback manifest train only `8` rows `fail=3/pass=5`, calibration `1 pass`, hidden `2 pass`. Adding manifest-train fallback would make train `18` rows `fail=8/pass=10`; adding all accepted fallback would make `21` rows `fail=8/pass=13`.
→ [Exact Interpretation] Fallback data would shift the train prior toward `pass` and still leave no fail validation signal.
→ [Detailed Explanation/Example] Risks are pass prior shift, short-history bias, overfitting from `8/11` rows, no usable fallback validation for fail, and spec-grounding metadata not included in model content while retrieved public20 includes spec context.

## Remediation Criteria

[Original Text/Data] Need target-controlled generation, not generic generation. Required target controls: `target_label`, `target_record_count`, optional `target_length_bin`/`final_method`/`final_status`/`allowed_source_rule_refs`.
→ [Exact Interpretation] The next generator contract must expose these controls before another SAMPLE attempt.
→ [Detailed Explanation/Example] Generation requests should explicitly ask for balanced labels, deeper record counts, optional length bins, final method/status variety, and supported rule-source boundaries.

[Original Text/Data] Minimum accepted pool for full ablation is `4000`; labels balanced at each ablation size; target public20-like record-count distribution listed in prior analysis.
→ [Exact Interpretation] Full ablation cannot start from the current `11` accepted fallback candidates.
→ [Detailed Explanation/Example] The accepted pool must support the `200/500/1000/2000/4000` ladder with balanced labels at every size and the prior public20-like record-count target.

## Decision

- Keep `docs/samples/self_instruct_sample.md` absent until Gate A/B/C/D and ablations pass.
- Keep generated synthetic data training eligibility `false`.
- Treat the current fallback artifacts as audit/no-go inventory, not provider-generated training data.
- Route the next data work to target-controlled generation using the controls above.
