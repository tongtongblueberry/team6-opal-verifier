<!-- Changed: archive the public20 split builder reset to 10 train / 10 val. -->
<!-- Why: active docs are not edited by this worker, so the completed code/artifact change needs a dated cycle record. -->

# 2026-05-27 public20 10/10 split builder 기록

## 변경 요약

<!-- Changed: record the exact artifact path and split contract. -->
<!-- Why: downstream training workers must distinguish active 10/10 artifacts from archive-only 16/4 artifacts. -->

- `tools/analysis/build_public20_train_val_split.py` 기본값을 `DEFAULT_VAL_PER_LABEL=5`로 변경했다.
- CLI `--val-per-label` 인자는 유지하되 public20 20-row 기준에서는 `5`만 허용한다.
- 기본 output root는 `runs/model_validation/public20_10_10_splits`다.
- 기존 `runs/model_validation/public20_splits`는 삭제하거나 이동하지 않았고, archive-only 16/4 evidence로 남긴다.
- seed `11`, `29`, `47` split artifact를 새 active path에 생성했다.

## 검증

<!-- Changed: record the local verification commands for this worker's scope. -->
<!-- Why: retraining should only start from a reproducible 10/10 split artifact. -->

- `python3 -m unittest tests.test_build_public20_train_val_split -v`: OK.
- `python3 tools/analysis/build_public20_train_val_split.py --input-jsonl data/local/public20/public20_input.jsonl --labels-jsonl data/local/public20/public20_labels.local.jsonl --output-root runs/model_validation/public20_10_10_splits --seeds 11 29 47`: OK.
- `jq`/`grep` count 검증: 각 seed `train=10`, `val=10`, `test=0`, train label `fail=5/pass=5`, val label `fail=5/pass=5`, `public20_test_split_created=false`.
- `git diff --check`: OK.

## 남은 blocker

<!-- Changed: list retraining blockers after split artifact creation. -->
<!-- Why: the split reset alone is not enough to restart model training or leaderboard submission. -->

- no-trust generated synthetic data 격리/감사 상태는 아직 완료되지 않았다.
- 새 synthetic 데이터는 Gate A/B/C/D와 Self-Instruct quality 검증 전까지 학습/accepted sample로 사용할 수 없다.
- 서버 상태와 package/submission required files는 재학습 전 재검증이 필요하다.
- 중단된 4B QLoRA queue 결과는 후보로 쓰지 않는다.
