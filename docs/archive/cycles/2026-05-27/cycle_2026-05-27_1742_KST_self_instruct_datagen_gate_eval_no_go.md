<!-- Changed: archive the 2026-05-27 17:42 KST DATA-GEN, DATA-GATE, and SELF-INSTRUCT-EVAL attempt results. -->
<!-- Why: future workers need one dated no-go record separating dry-run artifacts and fixture checks from real training-eligible synthetic data. -->

# 2026-05-27 17:42 KST Self-Instruct DATA-GEN/DATA-GATE/SELF-INSTRUCT-EVAL

## Summary

- DATA-GEN was attempted via `tools/datagen/run_self_instruct_generation.py --execute --provider openai` using the verified Wang et al. / `yizhongw/self-instruct` mapped pipeline.
- Provider credentials: `OPENAI_API_KEY=False`, `GEMINI_API_KEY=False`, `GOOGLE_API_KEY=False`, `ANTHROPIC_API_KEY=False`. Runner supports OpenAI/Gemini via `OPENAI_API_KEY`/`GEMINI_API_KEY`. No secrets were printed.
- Generated synthetic data training eligibility remains `false`.

## DATA-GEN Result

[Original Text/Data] Run directory `runs/self_instruct/datagen_try_20260527_174226_KST/` contains generation requests, metadata, dry-run instruction artifact, noop classification artifact, and `runner_report`. `raw_outputs.jsonl` is absent.
→ [Exact Interpretation] The run produced dry-run/request artifacts only, not provider-executed raw LLM output.
→ [Detailed Explanation/Example] Runner status was `skipped_missing_env`, request_count `2`, executed_count `0`, skipped_count `2`, failed_count `0`; DATA-GATE eligibility is `false`.

[Original Text/Data] Existing `official_restart_20260527_v1` remains dry-run only: request_count `4`, executed_count `0`, skipped_count `4`, status `skipped_missing_env`, no raw outputs.
→ [Exact Interpretation] The official restart did not produce eligible raw LLM output.
→ [Detailed Explanation/Example] It remains request/metadata evidence only and cannot feed parser/dedup/judge as real generated data.

## DATA-GATE Result

[Original Text/Data] DATA-GATE inventory: `datagen_try_20260527_174226_KST` dry-run only; `official_restart_20260527_v1` dry-run only; `public20_baseline` reference-only not synthetic; prior external_llm_probe/gemini_batch_v2/v3/v3/v4/v4.1 quarantine/no-trust; eligible real raw missing.
→ [Exact Interpretation] No current inventory item is eligible real generated synthetic data.
→ [Detailed Explanation/Example] `public20_baseline` can support reference comparison only, and quarantined prior lanes remain no-trust.

[Original Text/Data] DATA-GATE focused unit/fixture checks passed: `37 tests OK`. Fixture chain: parse accepted=1 rejected=0; dedup accepted=1 rejected=0; judge request_count=1 decision_count=9 accepted=1 rejected=8 with reject reasons `not_final_response_targeted`, `missing_spec_grounding`, `source_span_not_supportive`, `state_transition_inconsistent`, `manifest_loader_incompatible`, `label_not_plausible`, `intermediate_label_leak`, `public_or_rule_leakage`; Gate A fixture total=1 hard_invariant_pass=1 hard_invariant_fail=0 status `pending-qualitative-state-transition-audit`; Gate B fixture no-go `record_count_mean_difference`; Gate C fixture overall_pass=true.
→ [Exact Interpretation] Fixture/unit wiring is clean, but fixture checks do not create real Gate A/B/C/D pass artifacts.
→ [Detailed Explanation/Example] Gate A still needs qualitative state-transition audit samples from a real accepted pool; Gate B fixture is no-go due to `record_count_mean_difference`.

## SELF-INSTRUCT-EVAL Result

[Original Text/Data] SELF-INSTRUCT-EVAL focused tests passed: `68 OK`. Real eval is blocked because no provider-executed raw LLM output JSONL, no parser/dedup/judge accepted real candidates, no qualitative Gate A audit samples, no Gate B/C pass artifacts, and no 200/500/1K/2K/4K ablation reports exist.
→ [Exact Interpretation] The eval harness is fixture-clean but cannot run a real Self-Instruct evaluation.
→ [Detailed Explanation/Example] Real evaluation requires provider raw output, accepted real candidates, Gate A/B/C pass artifacts, and ablation reports.

## Sample And Training Gate

- `docs/samples/self_instruct_sample.md` remains absent/no-go.
- No sample may be created until real Gate A/B/C/D pass.
- Generated synthetic data training eligibility remains `false`.
