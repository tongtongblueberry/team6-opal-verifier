# 2026-05-29 gen2 no-go and gen3 restart record

## Decision

gen2 is not suitable for continued accumulation or training export. Stop the active server run that produced gen2-style raw outputs, keep its artifacts as no-go evidence, and restart generation as gen3.

## Evidence

- Checked at `2026-05-29 12:09:42 KST`.
- Active server run before stop: `runs/self_instruct/qwen_local_200_auth_strict_c1_batch8_restart_20260529_095246_KST`.
- Active server processes before stop: parent bash PID `96916`, generator PID `96920`.
- Server raw count before stop decision: `208 / 1000` rows in `raw_outputs.qwen_local.jsonl`.
- The old raw rows were generated with the pre-gen3 instruction contract. After the local parser was updated to the final-pair instruction, the current gen2 pull had `accepted_count=0`, `rejected_count=200`, and `reject_reason_counts={"instruction_not_fixed": 200}`.
- The last usable pre-update incremental gen2 export report showed `41` exported rows, labels `pass=24`, `fail=17`, and auth-session row rate `0.122`, while public20 auth-session row rate is `0.8`.
- The same report warned about missing public-like record counts `1,21,26,27,39`, lower args richness, and missing `Write`. User-provided analysis also identified missing `Locking`, `MBRControl`, and `LockingInfo` domain coverage and label inconsistencies.
- `data/local/gen2` must remain no-go/quarantine output. It must not be treated as a passed generated dataset.

## Root Cause

The old generation prompt was not strict enough about the actual task: the model must read the whole trajectory but label only whether the final command-response pair `(cN, rN)` is valid. It also did not force enough rule-book-grounded Locking SP contexts, public-like session identifiers, long trajectories, or exact `docs/legacy_spec_rules.md` source text in the prompt.

## gen3 Changes

- Prompt contract moved to `opal_final_response_spec_grounded_output_first.v2`.
- Fixed instruction is now: `Given the full Opal command-response trajectory, judge only whether the final command-response pair (cN, rN) is valid under the cited rule-book.`
- Generator prompt now includes exact `source_text` lines from `docs/legacy_spec_rules.md`.
- Candidate targets can require `required_context_domains`.
- Server target schedule forces Locking, MBRControl, LockingInfo, Authority, K_AES_256, C_PIN, and SP contexts, with long public20-like trajectory lengths including `21`, `26`, `27`, and `39`.
- Prompt forbids placeholder identifiers such as `H0001`, `H-test`, `SP001`, `Session1`, and repeated unrelated `000065ab`.
- Local watcher fixed instruction is aligned with gen3 and will export to `data/local/gen3`.
- Follow-up at `2026-05-29 12:28 KST`: local watcher now runs `tools/analysis/adversarial_rulebook_quality_gate.py` before export. This gate resolves `docs/legacy_spec_rules.md` source spans, checks the final pair against the cited rule-book text and the request target schedule, rejects missing authenticated-session evidence, rejects missing required domains, and exports only accepted rows to `data/local/gen3`.
- First current gen3 accepted candidate was rejected by the rule-book gate because it had `target_final_status_mismatch:SUCCESS!=NOT_AUTHORIZED`, `target_record_count_mismatch:21!=3`, and `required_auth_session_missing_hostchallenge_or_authority`. `data/local/gen3` was reset to `0` rows after that rejection.

## Restart Plan

1. Stop gen2 server processes `96916` and `96920`.
2. Copy gen3-modified generator, schema, judge, and pipeline files to the server.
3. Start a new server run under a `gen3` run directory.
4. Start a fresh 60-second local watcher that pulls each new raw batch, performs parser/dedup/quant/instruct/adversarial qualitative checks, and exports accepted rows to `data/local/gen3`.
5. Treat `data/local/gen3` as pending until Gate A/B/C and adversarial qualitative audit pass.

## Follow-Up

<!-- Changed: link the gen3 restart record to the later gen3.1 stop. -->
<!-- Why: this file explains why gen3 began, but the current state is governed by the later gen3.1 stop record. -->

- gen3 later stopped at raw `76/1000` with local accepted `0` because authenticated-session reject patterns persisted.
- gen3.1 later stopped at raw `72/1000` with local pending accepted `1`, rejected `20`, and canonical `data/local/gen3` still `0`.
- Current authority for the stopped state is
  `docs/archive/cycles/2026-05-29_gen3_zero_accept_gen31_restart.md`.
