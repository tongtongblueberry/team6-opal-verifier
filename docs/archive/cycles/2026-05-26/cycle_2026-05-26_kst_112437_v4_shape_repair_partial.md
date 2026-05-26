# Cycle 기록 - v4 shape repair 데이터 구현 및 부분 실패

- 시각: 2026-05-26 11:24:37 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 기준 커밋: `fca0652`
- 서버 런타임 루트: `/workspace/sinjeongmin_opal_verifier`

## 결론

- v4 데이터 생성 옵션은 public20 content를 복사하지 않고 `1-record` synthetic family와 char enrichment를 추가한다.
- 로컬 raw/build 검증에서는 생성과 manifest build가 성공했다.
- strict shape gate에서는 실패했다. 이유는 char median과 1-record coverage는 개선됐지만 token-bin length JSD가 기준을 초과했기 때문이다.
- 따라서 v4는 최종 학습 데이터가 아니라 v4.1 조정 대상이다.
- leaderboard 제출은 하지 않는다.

## 변경 파일

- `tools/datagen/generate_long_shape_source.py`
- `tests/test_generate_long_shape_source.py`

## v4 생성 옵션

- `--single-record-per-label`
  - pass/fail 각각 지정 개수만큼 synthetic 1-record trajectory를 추가한다.
  - public20 content/label은 사용하지 않는다.
- `--min-enriched-chars`
  - token뿐 아니라 compact input char 길이도 enrichment 목표로 사용한다.
- `--enrichment-field-cycles`
  - filler payload field 추가 반복 횟수를 조절한다.
- `--enrichment-value-repeat`
  - filler payload value 반복 강도를 조절한다.
- `--source-name`
  - v4 source family를 명시한다.

## 로컬 v4 생성/검증 결과

- run: `/tmp/opal_v4_shape_repair_local_1779762429`
- raw count: `1171`
- raw label counts: `pass=625`, `fail=546`
- raw record_count:
  - min `1`
  - median `11`
  - mean `16.318531`
  - max `39`
- raw char_count:
  - min `286`
  - median `5251`
  - mean `5629.465414`
  - max `10581`
- build selected records: `1170`
- build gate: 통과

## strict shape validator 결과

- strict validator overall: 실패
- 통과한 개선:
  - char mean ratio: `0.815103`
  - char median ratio: `0.770902`
  - min record_count gap: `0`
- 실패한 gate:
  - length JSD: `0.109264 > 0.08`
- 원인:
  - enrichment가 과해져 `513-1024` token bin이 `145`개 생겼다.
  - reference length bins에는 `513-1024`가 없다.
  - 따라서 char 길이는 개선됐지만 token-bin 분포는 public20 shape reference에서 멀어졌다.

## 결정

- v4 옵션 구현은 유지한다.
- v4 raw를 그대로 학습에 쓰지 않는다.
- 다음 데이터 cycle은 v4.1로 진행한다.
- v4.1 목표:
  - `record_count min=1` 유지
  - `char median ratio >= 0.70` 유지
  - `length JSD <= 0.08` 회복
  - `513-1024` token bin을 reference에 맞게 줄이거나 제거
  - low/mid token bin 비율을 reference에 맞추는 bin-aware enrichment 적용

## 검증

- `python3 -m py_compile tools/datagen/generate_long_shape_source.py tests/test_generate_long_shape_source.py`: 통과
- `python3 -m unittest tests.test_generate_long_shape_source -v`: 3 tests 통과
- `python3 -m unittest discover -s tests -v`: 51 tests 통과
- `git diff --check`: 통과
