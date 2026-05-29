# Self-Instruct Eval Summary - Codex-Agent Fallback

- provider/model: `codex_agent_fallback` raw generation
- judge: `codex_agent_fallback_judge` / `codex_agent_fallback_judge`; not Gemini
- raw_output_rows: 4
- parsed/dedup/judge accepted/Gate A accepted: 12 / 12 / 11 / 11
- labels after Gate A: {'fail': 3, 'pass': 8}
- Gate B: no-go ['record_count_mean_difference']
- Gate C: pass
- manifest validation: fail ['length_jsd_lte_threshold', 'split_label_counts_nonzero_where_possible']
- ablations: blocked_by_count (Only 11 Gate A accepted candidates are available, below the smallest required ablation size 200.)
- sample_md_may_be_created: False
- training_eligibility: False

## Filter Rates
- parse_accept_rate: 1.000000
- dedup_accept_rate: 1.000000
- judge_accept_rate: 0.916667
- gate_a_qualitative_accept_rate: 1.000000
- raw_candidate_to_gate_a_accept_rate: 0.916667

## Diversity/ROUGE
- dedup_candidates: unique_method_sequence=7, unique_spec_rule_ref_sets=12, pairwise_rouge={'pair_count': 66, 'min': 0.324675, 'mean': 0.440282, 'median': 0.440339, 'max': 0.623377, 'pairs_at_or_above_0_7': 0, 'max_pair': {'rouge_l': 0.623377, 'sample_ids': ['codex-agent-fallback-self-instruct-gen-00000-03', 'codex-agent-fallback-self-instruct-gen-00001-02']}}
- gate_a_accepted: unique_method_sequence=7, unique_spec_rule_ref_sets=11, pairwise_rouge={'pair_count': 55, 'min': 0.324675, 'mean': 0.434269, 'median': 0.436975, 'max': 0.623377, 'pairs_at_or_above_0_7': 0, 'max_pair': {'rouge_l': 0.623377, 'sample_ids': ['codex-agent-fallback-self-instruct-gen-00000-03', 'codex-agent-fallback-self-instruct-gen-00001-02']}}

## Blockers
- Gate B no-go: generated record_count mean differs from public20 reference mean and label distribution is small/imbalanced.
- Manifest validation failed: length_jsd_lte_threshold was not computable without reference and split_label_counts_nonzero_where_possible failed for fail labels in calibration/hidden splits.
- Ablations 200/500/1000/2000/4000 are blocked by accepted count 11.
- Package/runtime/leaderboard Gate D evidence was not produced in this data-gate run.
