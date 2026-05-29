# 2026-05-29 gen3 zero-accept and gen3.1 restart record

<!-- Changed: record the gen3.1 restart decision before stopping the current gen3 run. -->
<!-- Why: the current run is alive but repeatedly produces raw rows that fail the same parser/rule-book conditions. -->

## Decision

Stop accumulating the current gen3 run as the active lane and restart as gen3.1.
Do not weaken parser, invariant, dedup, or adversarial rule-book gates. Move the
quality fix upstream into generation: public20-derived delexicalized auth skeletons,
an easier authenticated curriculum, and an explicit rule-book/state-transition
self-check inside the generation prompt.

## Evidence

<!-- Changed: preserve the exact pre-restart snapshot. -->
<!-- Why: the restart must be traceable to measured quality failures, not preference. -->

- Checked at `2026-05-29 13:21:11 KST`.
- Active server run before restart:
  `runs/self_instruct/qwen_local_200_auth_strict_gen3_batch4_20260529_121315_KST`.
- Active server processes before stop: parent bash PID `115447`, generator PID `115451`.
- Server raw count before restart decision: `64 / 1000`.
- Local watcher: screen `qwen_incremental_watch_gen3`.
- Local mirror before restart: `runs/self_instruct/server_qwen_prod_gen3`.
- Local counts: raw `64`, parse rejects `56`, parsed candidates `8`,
  rule-book accepted `0`, rule-book rejected `8`, exported rows `0`.
- Rule-book reject count had `required_auth_session_missing_hostchallenge_or_authority=8`.
- Other repeated rejects included target final method/status/count mismatch and missing
  `Authority`/`SP` required domains.

## Root Cause

<!-- Changed: connect the reject reasons to the generation prompt, not the gate. -->
<!-- Why: the gate is correctly rejecting rows that do not provide auditable authenticated state. -->

The gen3 prompt asks for authenticated sessions but mostly passes public20 seed
information as profile features such as record count, method sequence, status sequence,
and final method/status. It does not consistently provide the actual public20
`StartSession.method.args.required/optional` field skeleton. Qwen therefore creates
records that sometimes look like sessions but omit `optional.HostChallenge` and
`optional.HostSigningAuthority`, or it fails to align the final pair with the target
schedule.

Asking the generator to check the rule-book/state transition is acceptable if it is
done inside the same generation call and written into `spec_grounding.state_transition_notes`
and `primary_evidence.reason`. A separate LLM judge call for every raw candidate would
be a throughput bottleneck; an in-prompt self-check mainly costs tokens and is cheaper
than producing hundreds of invalid raw rows.

## gen3.1 Changes

<!-- Changed: describe the code-level changes being sent to the server. -->
<!-- Why: future workers must know what distinguishes gen3.1 from gen3. -->

- Prompt contract moved to `opal_final_response_spec_grounded_output_first.v3`.
- `tools/datagen/run_self_instruct_generation.py` now derives input-only, delexicalized
  public20 auth skeletons from seed records.
- The auth skeleton keeps method/field shape but mutates concrete UID, SPID,
  `SPSessionID`, `HostChallenge`, `HostSigningAuthority`, and table values.
- If the selected seed lacks an authenticated StartSession skeleton, request construction
  supplies a fallback skeleton from another public20 input-only seed.
- The generation prompt now requires a state table/self-check over session id,
  authenticated authority, relevant domain/object, cited rule, expected final status,
  and actual final status.
- The prompt explicitly tells the model to use `output.status_codes=["SUCCESS"]` for
  successful `StartSession` and `output.method.name="SyncSession"`, not
  `status_codes=["SUCCESS (SYNCSESSION)"]`.
- `tools/datagen/run_qwen_local_200_pipeline.sh` now has a gen3.1 warm-up curriculum
  for the first `CURRICULUM_WARMUP_REQUESTS` targets, default `160`, focused on
  authenticated `Get`, `Set`, and `Activate` cases before harder `GenKey`,
  `MBRControl`, `INVALID_PARAMETER`, and very long trajectories.

## Restart Plan

<!-- Changed: record the exact restart sequence. -->
<!-- Why: the server and local watcher must not mix gen3 and gen3.1 artifacts. -->

1. Run local syntax and request-shape checks.
2. Copy changed generation/pipeline/watcher/gate/export files to the server repo.
3. Stop server PIDs `115447` and `115451`.
4. Stop local watcher `qwen_incremental_watch_gen3`.
5. Archive local `runs/self_instruct/server_qwen_prod_gen3`.
6. Start server run:
   `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_<timestamp>`.
7. Start local watcher `qwen_incremental_watch_gen31` with local root
   `runs/self_instruct/server_qwen_prod_gen31` and pending export path `data/local/gen3_pending`.
8. Watch the first raw increments; success criterion is nonzero parser pass and
   removal of the repeated authenticated StartSession reject pattern.

## Restart Result

<!-- Changed: record the first gen3.1 run and initial watcher result. -->
<!-- Why: the restart should be auditable without reading terminal history. -->

- Started server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`.
- Server parent PID: `120144`; generator PID: `120148`.
- Local watcher: screen `qwen_incremental_watch_gen31`.
- Local mirror: `runs/self_instruct/server_qwen_prod_gen31`.
- First checked raw with nonzero export: `8 / 1000`.
- First local validation with nonzero pending export: raw `8`, parse rejects `5`, parsed candidates `3`,
  rule-book accepted `1`, rejected `2`, pending exported rows `1`.
- First gen3.1 reject reasons:
  `target_record_count_mismatch:21!=4`,
  `target_record_count_mismatch:10!=6`,
  `target_label_mismatch:fail!=pass`,
  `required_context_domains_missing:Locking`.
- The previous repeated gen3 reject
  `required_auth_session_missing_hostchallenge_or_authority` did not appear in the first
  gen3.1 batches.

## Canonical Data Rule

<!-- Changed: separate local monitoring output from final training data. -->
<!-- Why: the local incremental watcher does not run the full server-side judge stage, so it must not define the final training dataset. -->

- Local watcher output is `data/local/gen3_pending`.
- `data/local/gen3_pending` is for monitoring and early quality diagnosis only.
- Canonical final generated data is server `$RUN/gen_export` after the full server pipeline
  completes `parse -> invariant -> dedup -> judge -> rule-book -> audit -> export`.
- `data/local/gen3` stays empty until the server canonical export is explicitly synced back.

## Stop Result

<!-- Changed: record the final stopped state after the user stopped gen3.1. -->
<!-- Why: this archive entry is the authority for why the run should not be resumed unchanged. -->

- Stop time recorded in local docs: `2026-05-29 14:13:39 KST`.
- User decision: stop the gen3.1 pipeline because the yield was not good enough.
- Server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`.
- Former server PIDs `120144` and `120148` were killed.
- Server raw count at stop: `72 / 1000`.
- Server GPU after stop: `0 %, 0 MiB / 46068 MiB`.
- Local watcher `qwen_incremental_watch_gen31` and orphan watcher children were stopped.
- Local mirror final counts: raw `72`, parse rejects `51`, parsed candidates `21`,
  rule-book accepted `1`, rule-book rejected `20`.
- `data/local/gen3_pending`: `1` input row and `1` label row, monitoring only.
- `data/local/gen3`: `0` input rows and `0` label rows.
- Final interpretation: gen3.1 improved over gen3 by producing one rule-book accepted pending row, but accepted yield stayed too low and rejects remained structural. Do not resume this run unchanged; future work should start with reject taxonomy/gate audit or deterministic OPAL skeleton/value generation.
