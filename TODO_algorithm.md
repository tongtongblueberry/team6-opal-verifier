<!-- Changed: add an algorithm-track checklist for the FSM-shadow verifier package. -->
<!-- Why: the algorithm submission work must be tracked separately from LogLLM package recovery. -->

# Algorithm Verifier TODO

Updated: `2026-06-06 KST`

## Objective

[Original Text/Data] The existing rulebase branch `team-rulebase-73-clean` is a deterministic rule-only verifier that matches public20 locally.
-> [Exact Interpretation] The algorithm package should preserve the current rulebase behavior first, then add OPAL FSM cross-checking conservatively.
-> [Detailed Explanation/Example] The intended data flow is:

```text
trajectory
  -> existing record parser
  -> existing ProtocolState prefix update
  -> existing final rule check
  -> FSM shadow expected-status/payload cross-check
  -> conservative rescue or veto
  -> pass/fail
```

## Checklist

- [x] Create `runs/algorithm/submit` as an independent stdlib-only submit package.
- [x] Copy the 73.00 rulebase solver API shape: `Solver`, `predict`, `predict_one`, and `StatefulOpalVerifier`.
- [x] Add `src/fsm_shadow.py` with a compact vendored OPAL FSM transition table derived from `tools/datagen/opal_fsm.py`.
- [x] Integrate FSM shadow into the solver without replacing the existing parser, `ProtocolState`, or final rule order.
- [x] Keep ensemble behavior conservative:
  - rescue only selected status-level false failures;
  - veto only high-confidence status or payload contradictions;
  - default to the original rulebase decision when FSM confidence is low.
- [x] Verify public20 remains `20/20`.
- [x] Verify `gen_gflownet_v10_1` remains `2320/2320` if feasible.
- [x] Run package import smoke and `setup.sh`.
- [x] Keep `setup.sh` minimal and dependency-free.
- [x] Prepare leaderboard submission command only after local checks pass.

## Verification Results

[Original Text/Data] Local algorithm package verification on 2026-06-06 KST:

```text
public20:
  20 / 20
  gt_pass pred_pass = 10
  gt_pass pred_fail = 0
  gt_fail pred_pass = 0
  gt_fail pred_fail = 10

gen_gflownet_v10_1:
  2320 / 2320
  gt_pass pred_pass = 1160
  gt_pass pred_fail = 0
  gt_fail pred_pass = 0
  gt_fail pred_fail = 1160

gen_gflownet_v10 diagnostic:
  1207 / 2292
  unchanged from the baseline rulebase diagnostic
```

-> [Exact Interpretation] The FSM-shadow ensemble preserves known-good public20 and v10.1 behavior. It does not use the noisy v10 labels as an override target.
-> [Detailed Explanation/Example] The ensemble is conservative: low-confidence FSM state drift falls back to the original rulebase decision.

## Submission Command

[Original Text/Data] `submit` is not installed in the local machine environment.
-> [Exact Interpretation] leaderboard submission must be run on the course server where the submit CLI exists.
-> [Detailed Explanation/Example]

```bash
cd /workspace/sinjeongmin_opal_verifier/repo/runs/algorithm/submit
submit -n algorithm-fsm-shadow-20260606
```

## Submission Attempt: 2026-06-08 KST

[Original Text/Data] The user explicitly asked to submit the rulebase-style algorithm package.
-> [Exact Interpretation] Submission was authorized for `runs/algorithm/submit`.
-> [Detailed Explanation/Example] Local pre-submit gates passed:

```text
public20:
  20 / 20
  gt_pass pred_pass = 10
  gt_pass pred_fail = 0
  gt_fail pred_pass = 0
  gt_fail pred_fail = 10

package size:
  100K

package surface:
  README.md
  pyproject.toml
  setup.sh
  uv.lock
  src/__init__.py
  src/solver.py
  src/fsm_shadow.py

forbidden files:
  none found after cleanup
```

[Original Text/Data] Local `submit` was unavailable and server SSH timed out.
-> [Exact Interpretation] The actual leaderboard submission could not be executed from the current local environment.
-> [Detailed Explanation/Example]

```text
which submit
  submit not found

ssh team6 'submit --list'
  ssh: connect to host 147.46.78.61 port 2227: Operation timed out

ssh -p 2227 student@147.46.78.61 'submit --list'
  ssh: connect to host 147.46.78.61 port 2227: Operation timed out

nc -vz -w 10 147.46.78.61 2227
  nc: connectx to 147.46.78.61 port 2227 (tcp) failed: Operation timed out
```

## Submission Result: 2026-06-08 KST

[Original Text/Data] The server accepted the uploaded rulebase-style algorithm package:

```text
Archiving your submission... (0.02 MB)
Checking availability...
Uploading your submission...

Your job is queued.
Job ID:           2055
Submission ID:    9bbfa183343940848c8433a99dddc1a9
Job Name:         algorithm-fsm-shadow-rulebase-style-20260608
```

-> [Exact Interpretation] The leaderboard submission was created successfully as Job `2055`.
-> [Detailed Explanation/Example] The submission was no longer blocked by local `submit` absence or SSH timeout once the course server became reachable.

[Original Text/Data] `submit --list` on the course server later reported:

```text
Submission ID                     Name                            Created               Status    Score   Job ID
------------------------------------------------------------------------------------------------------------------
9bbfa183343940848c8433a99dddc1a9  algorithm-fsm-shadow-rulebas... 2026-06-08 11:24:51   Success   73.00   2055
```

-> [Exact Interpretation] Job `2055` completed successfully with leaderboard score `73.00`.
-> [Detailed Explanation/Example] This matches the historical score of the referenced deterministic rulebase package while preserving the local `public20` result.

## Do Not Do

- Do not edit `submissions/logllm_final_epoch10_bertlarge`.
- Do not import from `tools/datagen` inside the submit package.
- Do not submit before local public20 verification is recorded here.
- Do not use public20 labels as runtime inputs.
