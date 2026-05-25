# 2026-05-26 07:19:52 KST - Step 6 P2 bucket metrics 배포 기록

## 결정

- P2 평가 코드 변경을 로컬 전체 테스트 통과 후 서버에 배포했다.
- 이번 변경은 데이터 문제를 더 잘 보기 위한 평가 리포트 확장이다. architecture에 rule engine을 추가하지 않았고, solver 추론 경로도 건드리지 않았다.
- leaderboard 제출은 하지 않았다. 이유는 현재 변경이 제출 산출물의 새 성능 근거가 아니라 평가/분석 계측 개선이며, 직전 제출은 서버 이슈로 reject 되었고 같은 패키지 재제출 근거가 아직 없다.

## 구현 내용

- `tools/eval/eval_manifest_adapter.py`
  - prediction row에 `source`, `input_length_chars`, `length_bucket`을 보존한다.
  - base threshold 기준 `split`, `source`, `length_bucket` bucket metric을 계산한다.
  - Markdown bucket summary를 추가한다.
  - manifest에서 온 `source` 값이 `|` 또는 newline을 포함해도 Markdown table이 깨지지 않도록 escape한다.
- `tests/test_eval_manifest_adapter_metrics.py`
  - source/length bucket metric 산출 테스트를 추가했다.
  - Markdown escape 테스트를 추가했다.
  - `evaluate_rows()`가 metadata를 prediction row에 싣는 경로를 직접 테스트했다.

## 검증

- 로컬 시각: 2026-05-26 07:19:21 KST
- 로컬 전체 테스트:
  - 명령: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
  - 결과: 38 tests, OK
- diff whitespace:
  - 명령: `git diff --check`
  - 결과: OK

## 서버 배포

- 대상 파일: `/workspace/team6/team6-opal-verifier/tools/eval/eval_manifest_adapter.py`
- 배포 시각: 2026-05-26 07:19:36 KST
- 배포 후 서버 sha256:
  - `b3a134ee6300bd1235c4ff08c70a03651c9a5c72f421abc51f5084940fdb4a06`
- 로컬 sha256:
  - `b3a134ee6300bd1235c4ff08c70a03651c9a5c72f421abc51f5084940fdb4a06`

## 다음 기준

- P1 sweep의 첫 config 평가가 끝나면 `bucket_metrics`와 `risk_coverage_summary`가 report에 포함되는지 확인한다.
- 특정 source 또는 length bucket에서 성능 하락이 확인되면 다음 cycle의 Step 2 문제 판단 근거로 기록한다.
- 동일 패키지 leaderboard 재제출은 서버 제출 가능 상태가 바뀌었다는 근거가 생긴 뒤에만 고려한다.
