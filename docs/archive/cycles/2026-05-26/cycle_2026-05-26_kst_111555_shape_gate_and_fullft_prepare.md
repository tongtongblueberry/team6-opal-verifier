# Cycle 기록 - shape gate 추가 및 full/selective FT 준비

- 시각: 2026-05-26 11:15:55 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 기준 커밋: `da88fe3`
- 서버 런타임 루트: `/workspace/sinjeongmin_opal_verifier`

## 결론

- v3 manifest는 기본 shape gate를 통과하지만, 더 엄격한 public20 shape 재현 기준에서는 아직 부족하다.
- LoRA adapter-only가 12GB 제출 제한을 충분히 활용하지 못한다는 가설을 검증하기 위해 full/selective fine-tuning trainer를 추가했다.
- 현재 진행 중인 r64 all-linear LoRA 학습은 baseline으로 유지한다. 다만 `max_seq_len=2048`에서는 v3 train row 중 일부가 label truncation으로 손실될 수 있으므로, 다음 비교 학습은 `max_seq_len=4096`을 우선한다.
- leaderboard 제출은 하지 않는다. 아직 학습 완료, calibration/hidden 평가, merged 또는 standalone package `<12GB` smoke gate가 없다.

## 데이터 gate 구현

- 변경 파일:
  - `tools/analysis/validate_manifest.py`
  - `tests/test_validate_manifest_shape_gates.py`
- 새 CLI 옵션:
  - `--min-char-mean-ratio`, 기본 `0.60`
  - `--min-char-median-ratio`, 기본 `0.60`
  - `--max-min-record-count-gap`, 기본 `1`
- 새 report 항목:
  - `metrics.char_length_stats`
  - `metrics.reference_char_length_stats`
  - `metrics.record_count_stats`
  - `metrics.reference_record_count_stats`
  - `metrics.char_length_mean_ratio`
  - `metrics.char_length_median_ratio`
  - `metrics.min_record_count_gap`
  - `gate_status.char_length_mean_ratio_gte_threshold`
  - `gate_status.char_length_median_ratio_gte_threshold`
  - `gate_status.min_record_count_gap_lte_threshold`

## v3 적용 결과

- 입력:
  - manifest: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1045_KST_manifest_v3_long_shape_enriched/manifests/manifest_v3_long_shape_enriched.jsonl`
  - reference: `/workspace/sinjeongmin_opal_verifier/data/reference/shape20_input_reference.jsonl`
- 기본 gate 결과:
  - overall: 통과
  - length JSD: `0.042439`
  - char mean ratio: `0.724505`
  - char median ratio: `0.631065`
  - min record_count gap: `1`
  - manifest char mean/median: `5007.272964 / 4298.5`
  - reference char mean/median: `6911.3 / 6811.5`
  - manifest record_count min/median/mean/max: `2 / 11.0 / 16.542461 / 39`
  - reference record_count min/median/mean/max: `1 / 16.0 / 16.4 / 39`
- 엄격 gate 결과:
  - `--min-char-median-ratio 0.70 --max-min-record-count-gap 0`에서 실패
  - 실패 이유:
    - char median ratio `0.631065 < 0.70`
    - reference에는 1-record case가 있으나 manifest 최단 record_count는 `2`

## full/selective FT 준비

- 추가 커밋: `da88fe3 add manifest full finetune trainer`
- 변경 파일:
  - `tools/training/train_manifest_full.py`
  - `tests/test_train_manifest_full.py`
- 기능:
  - Data Contract v2 manifest만 읽고 train split만 사용
  - `--train-mode full|last-n-layers|lm-head-only`
  - checkpoint/resume 지원
  - `save_pretrained(..., safe_serialization=True)`로 standalone safetensors model 저장
  - `--dry-run`에서 tokenization과 freeze plan 확인
  - `--min-tokenized-ratio` gate 추가

## full/selective FT dry-run 판단

- v3 manifest 기준 dry-run 결과:
  - `max_seq_len=2048`: tokenized `470`, skipped `321`, ratio `0.594`, 실패로 보는 것이 맞다.
  - `max_seq_len=4096`: tokenized `791`, skipped `0`, ratio `1.0`, 통과.
- 결정:
  - 현재 LoRA `max_seq_len=2048` run은 baseline으로 끝까지 유지한다.
  - 다음 비교 학습은 `max_seq_len=4096`, `train-mode=last-n-layers`, `batch-size=1`부터 시작한다.
  - full FT는 48GB에서 OOM 가능성이 높으므로 selective FT dry-run/short-run 후 검증한다.

## 검증

- `python3 -m unittest discover -s tests -v`: 48 tests 통과
- `python3 -m py_compile tools/analysis/validate_manifest.py tests/test_validate_manifest_shape_gates.py`: 통과
- `python3 tools/analysis/validate_manifest.py --help`: 새 shape gate 옵션 노출 확인
- v3 기본 gate: 통과
- v3 엄격 gate: 의도한 실패

## 다음 단계

- 진행 중인 LoRA baseline 학습 완료 후 calibration/hidden 평가를 수행한다.
- baseline 평가 후 merged model package size와 offline smoke를 확인한다.
- GPU가 비면 `max_seq_len=4096` selective FT dry-run 또는 short-run을 실행한다.
- 다음 데이터 cycle에서는 char median ratio와 1-record shortest case를 개선하는 생성 데이터를 추가한다.
