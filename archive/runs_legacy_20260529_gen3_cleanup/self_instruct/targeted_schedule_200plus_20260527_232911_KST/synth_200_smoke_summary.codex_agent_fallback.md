# SYNTH-200 codex_agent_fallback Smoke Summary

- run_root: `runs/self_instruct/targeted_schedule_200plus_20260527_232911_KST`
- provider status: `skipped_missing_env`; executed `0` / requests `50`
- targets/requests/fallback raw/candidates: `200` / `50` / `50` / `200`
- parse/dedup/judge/Gate A: `200/0` -> `25/175` -> `25/0` -> `25/0`
- manifest rows/splits: `25` / `{"calibration": 2, "hidden": 5, "train": 18}`
- Gate B warnings: `[{"code": "record_count_mean_difference", "details": {"absolute_difference": 2.719999999999999, "generated_mean": 13.68, "generated_minus_public": -2.719999999999999, "public_mean": 16.4}, "message": "public20와 generated의 평균 record_count가 다르므로 Gate B에서 질적 검토가 필요하다.", "severity": "no_go_warning"}]`
- manifest validation: `False`; Gate C: `True`

## Blockers
- provider-backed generation missing env key; no provider raw output exists
- dedup collapsed 200 fallback candidates to 25 due near_duplicate_trajectory_signature
- Gate B has record_count_mean_difference after dedup: generated mean 13.68 vs public20 16.4
- manifest validation failed length_jsd 0.4356 > 0.08
- Gate D/package/training not run because upstream gates failed and provenance is fallback-only
