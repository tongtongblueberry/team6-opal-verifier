<!-- Changed: archive the DATA-REMEDIATION-2 manifest selection distribution preservation result. -->
<!-- Why: the active docs need a dated evidence record for the resolved dimensional/manifest blocker and the remaining no-go gates. -->

# 2026-05-27 21:31 KST DATA-REMEDIATION-2 Manifest Distribution Preservation

## 결론

DATA-REMEDIATION-2 is completed. The dimensional/manifest blocker is resolved for the
20-row targeted fallback smoke, but sample/training eligibility remains `false`.
PACKAGE remains pending, and DOC-SYNC remains in progress until this edit completes.

## Evidence

- Root cause: `build_supervised_manifest.py` length-bin-only JSD selector dropped
  high-depth rows `22,24,25,25,28,39,39`, making selected subset mean `13.7576`
  despite accepted pool mean `16.4`.
- Existing options:
  - all `40` rows preserved mean `16.4` but failed length JSD `0.132488 > 0.08`;
  - old length balance selected `33` and validation passed, but Gate B
    `record_count_mean_difference` remained.
- Fix: optional `--preserve-record-count-distribution` in
  `tools/analysis/build_supervised_manifest.py`; default behavior unchanged;
  tests added in `tests/test_build_supervised_manifest.py`.
- Tests: full suite `160 OK`, `git diff --check OK`.
- New artifact:
  `runs/self_instruct/targeted_schedule_20260527_192440_KST/manifest.record_count_preserved.codex_agent_fallback.jsonl`
  and associated reports.
- New selected result:
  - rows `20`
  - labels `fail=10/pass=10`
  - train `14`, `fail=7/pass=7`
  - hidden `4`, `fail=2/pass=2`
  - calibration `2`, `fail=1/pass=1`
  - record_count min/median/mean/max `1/17.5/16.4/39`
  - length JSD `0.078355`
  - manifest validation passed
  - Gate B passed with `no_go_warnings=[]`
  - Gate C `20/20` passed

## Remaining No-Go Boundary

Sample/training eligibility remains `false` because fallback provenance is not
provider/Gemini, ablations `200/500/1000/2000/4000` are still incomplete, and
Gate D/package/training were not run.

Checklist: DATA-REMEDIATION-2 completed; PACKAGE pending; DOC-SYNC in progress
until this edit completes.
