# Cycle 기록 - v4.1 shape repair 로컬 검증 및 reference pending

- 시각: 2026-05-26 11:55 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 로컬 작업 폴더: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 서버 런타임 루트: `/workspace/sinjeongmin_opal_verifier`

## 결론

- v4.1은 v4 실패 원인인 `513-1024` token bin overflow를 제거했다.
- 로컬 raw 생성과 manifest builder는 통과했다.
- reference가 없는 상태의 validator에서는 `length_jsd`만 계산 불가로 실패 처리되었다.
- 따라서 v4.1은 구현/test는 통과했지만, public20 shape reference strict gate 최종 통과는 아직 pending이다.
- leaderboard 제출은 하지 않는다. 학습 완료 artifact, calibration/hidden 평가, package smoke가 없다.

## 변경 내용

- `tools/datagen/generate_long_shape_source.py`
  - token enrichment와 char enrichment 후보 선별을 분리했다.
  - `--max-enriched-tokens`로 enrichment 후 token 상한을 둔다.
  - `--enrich-selection token-only`로 token-bin matching 대상만 token enrichment한다.
  - `--dense-char-fill-*` 옵션으로 whitespace token 수를 거의 늘리지 않고 char 길이를 보강한다.
- `tests/test_generate_long_shape_source.py`
  - `513-1024` overflow 방지 테스트를 추가했다.
  - `min-enriched-tokens > max-enriched-tokens` 조합 reject를 테스트한다.
  - token-only selection과 dense char fill의 token growth 방지를 테스트한다.
- `tools/training/deploy_and_train.sh`
  - 오래된 rule-id 기반 배포/학습 파이프라인을 실행 불가능한 guard로 교체했다.
  - 저장소에 서버 비밀번호가 남지 않도록 제거했다.
  - 현재 cycle의 owned root와 LLM-only 학습 도구만 안내하도록 바꿨다.

## 실행 명령

```bash
RUN=/tmp/opal_v41_shape_repair_local_1779763839
mkdir -p "$RUN/raw" "$RUN/reports" "$RUN/manifests"

python3 tools/datagen/generate_long_shape_source.py \
  --output "$RUN/raw/long_shape_v41.jsonl" \
  --summary-output "$RUN/reports/long_shape_v41_raw_summary.json" \
  --source-name long_shape_v41 \
  --single-record-per-label 8 \
  --enrich-fraction 0.65 \
  --enrich-selection token-only \
  --min-enriched-tokens 257 \
  --min-enriched-chars 0 \
  --max-enriched-tokens 512 \
  --dense-char-fill-fraction 1.0 \
  --dense-char-fill-min-chars 5200 \
  --dense-char-fill-field-cycles 10 \
  --dense-char-fill-value-repeat 2 \
  --enrichment-field-cycles 2 \
  --enrichment-value-repeat 1

python3 tools/analysis/build_supervised_manifest.py \
  --input "$RUN/raw/long_shape_v41.jsonl" \
  --output "$RUN/manifests/manifest_v41.jsonl" \
  --report-out "$RUN/reports/manifest_v41" \
  --hidden-fraction 0.2 \
  --calibration-fraction 0.1 \
  --seed 42

python3 tools/analysis/validate_manifest.py \
  --manifest "$RUN/manifests/manifest_v41.jsonl" \
  --report-out "$RUN/reports/manifest_v41_validate_no_reference" \
  --min-template-entropy 0.75 \
  --max-top-template-share 0.20 \
  --min-char-median-ratio 0.70 \
  --max-min-record-count-gap 0
```

## 로컬 결과

- raw count: `1171`
- build selected records: `1170`
- build gate: 통과
- manifest label counts:
  - `pass=625`
  - `fail=545`
- split label counts:
  - train: `pass=447`, `fail=384`
  - calibration: `pass=63`, `fail=54`
  - hidden: `pass=115`, `fail=107`

## Shape 수치

- token bins:
  - `1-32=16`
  - `33-64=131`
  - `65-128=130`
  - `129-256=285`
  - `257-512=608`
  - `513-1024=0`
- char stats:
  - min `286`
  - median `5472.0`
  - mean `5766.111111`
  - max `10581`
- record_count stats:
  - min `1`
  - median `11.0`
  - mean `16.329915`
  - max `39`

## Validator 판정

- no-reference validator overall: 실패
- 실패 이유:
  - `length_jsd_lte_threshold`는 reference가 없어서 `None`이며 fail-closed로 실패 처리됨.
- reference 불필요 hard gates:
  - JSONL parse: 통과
  - required fields: 통과
  - labeled coverage: 통과
  - unknown/invalid label: 통과
  - exact duplicate: 통과
  - group leakage: 통과
  - template entropy: `0.982376`, 통과
  - top template share: `0.004274`, 통과
  - public holdout metadata absent: 통과
  - rule-context absent: 통과

## 검증

- `python3 -m py_compile tools/datagen/generate_long_shape_source.py tests/test_generate_long_shape_source.py`: 통과
- `python3 -m unittest tests.test_generate_long_shape_source -v`: 7 tests 통과
- `python3 -m unittest discover -s tests -v`: 55 tests 통과
- `git diff --check`: 통과

## 서버 pending

- SSH 상태: 2026-05-26 11:51 KST 기준 `Operation timed out`
- 서버 연결 회복 후 먼저 local commit을 서버 repo에 sync하거나 동일 명령으로 v4.1 raw/manifest를 서버 owned root 아래에서 재생성해야 한다.
- 서버 strict gate 재생성 명령:

```bash
ROOT=/workspace/sinjeongmin_opal_verifier
REPO=$ROOT/repo
RUN=$ROOT/ops/runs/20260526_KST_manifest_v41_shape_repair
mkdir -p "$RUN/raw" "$RUN/reports" "$RUN/manifests"
cd "$REPO"

python3 tools/datagen/generate_long_shape_source.py \
  --output "$RUN/raw/long_shape_v41.jsonl" \
  --summary-output "$RUN/reports/long_shape_v41_raw_summary.json" \
  --source-name long_shape_v41 \
  --single-record-per-label 8 \
  --enrich-fraction 0.65 \
  --enrich-selection token-only \
  --min-enriched-tokens 257 \
  --min-enriched-chars 0 \
  --max-enriched-tokens 512 \
  --dense-char-fill-fraction 1.0 \
  --dense-char-fill-min-chars 5200 \
  --dense-char-fill-field-cycles 10 \
  --dense-char-fill-value-repeat 2 \
  --enrichment-field-cycles 2 \
  --enrichment-value-repeat 1

python3 tools/analysis/build_supervised_manifest.py \
  --input "$RUN/raw/long_shape_v41.jsonl" \
  --output "$RUN/manifests/manifest_v41.jsonl" \
  --report-out "$RUN/reports/manifest_v41" \
  --hidden-fraction 0.2 \
  --calibration-fraction 0.1 \
  --seed 42

python3 tools/analysis/validate_manifest.py \
  --manifest "$RUN/manifests/manifest_v41.jsonl" \
  --reference /workspace/sinjeongmin_opal_verifier/data/reference/shape20_input_reference.jsonl \
  --report-out "$RUN/reports/manifest_v41_validate_strict" \
  --min-template-entropy 0.75 \
  --max-top-template-share 0.20 \
  --min-char-median-ratio 0.70 \
  --max-min-record-count-gap 0
```

## 결정

- v4.1 구현은 commit한다.
- v4.1 데이터는 strict reference gate가 통과하기 전까지 학습에 투입하지 않는다.
- 현재 LoRA baseline 학습 상태를 서버에서 먼저 확인한다.
- 서버가 회복되면 v4.1 strict gate와 baseline evaluation을 우선 실행한다.
