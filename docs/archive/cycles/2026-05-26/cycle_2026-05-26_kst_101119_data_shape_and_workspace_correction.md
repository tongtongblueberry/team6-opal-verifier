# 2026-05-26 10:11:19 KST 데이터 구조 검증 및 서버 작업 루트 정정

## 결론

[Original Text/Data] 사용자가 `/workspace/team6`는 본인 폴더가 아니라고 정정했다.
→ [Exact Interpretation] `/workspace/team6` 아래 산출물은 앞으로 우리 작업 루트나 소유 산출물로 간주하지 않는다.
→ [Detailed Explanation/Example] 새 작업 루트는 `/workspace/sinjeongmin_opal_verifier`로 분리했고, 명시적으로 우리가 만든 run-only 디렉터리만 삭제했다.

[Original Text/Data] public 20 testcases는 `/dl2026/dataset/testcases/tc1.json`부터 `tc20.json`, label은 `/dl2026/dataset/label.jsonl`이다.
→ [Exact Interpretation] 각 testcase의 top-level은 JSON list이고, 각 원소는 `index`, `input`, `output`을 가진 record이다.
→ [Detailed Explanation/Example] solver 입력 단위는 단일 record가 아니라 case 전체 record trajectory이다. manifest builder가 `records` 내부 step으로 flatten하면 학습 단위가 leaderboard 입력 단위와 달라진다.

[Original Text/Data] public 20 label count는 pass 10, fail 10이다.
→ [Exact Interpretation] public 20 기준 pass/fail prior는 50:50이다.
→ [Detailed Explanation/Example] 생성 데이터도 최소한 split별 prior drift를 별도 gate로 봐야 하며, fail oversampling만으로 점수를 올리는 방향은 보류한다.

## Public 20 차원

[Original Text/Data] public 20 record count stats: min 1, median 16.0, mean 16.4, max 39.
→ [Exact Interpretation] 평균 입력 길이는 약 16-step trajectory이다.
→ [Detailed Explanation/Example] 1-step command만 학습하는 manifest는 public 20 평균 입력 구조와 맞지 않는다.

[Original Text/Data] `{"records": records}` compact JSON 기준 char stats: min 429, median 6811.5, mean 6911.3, max 15256.
→ [Exact Interpretation] public 입력은 짧은 scalar command가 아니라 수천 character의 구조화 trajectory이다.
→ [Detailed Explanation/Example] 기존 broken manifest의 median 99 char 입력은 public 20 입력 분포와 크게 다르다.

[Original Text/Data] whitespace token stats: min 17, median 211.5, mean 211.3, max 458.
→ [Exact Interpretation] public 20은 max_seq_len 2048 안에는 여유가 있지만, 단일 step만 쓰면 sequence 분포가 collapse된다.
→ [Detailed Explanation/Example] 학습/평가 prompt는 full trajectory를 넣고, truncation audit은 계속 유지한다.

[Original Text/Data] pass subset record stats: min 1, median 16.0, mean 16.5, max 39. fail subset record stats: min 1, median 15.5, mean 16.3, max 39.
→ [Exact Interpretation] public 20에서는 pass/fail 간 record_count 분포가 거의 같다.
→ [Detailed Explanation/Example] 모델이 길이만으로 label을 맞추는 shortcut은 public 20 기준으로 기대하기 어렵다.

## Leaderboard 입력 판단

[Original Text/Data] `src/solver.py::predict`는 dict input이면 `testcases`, `cases`, `data` 중 하나를 꺼내고, list input이면 그대로 `Solver().predict()`에 전달한다. `Solver.predict()`는 각 item에서 `id`와 `steps`를 읽고, `steps`가 없으면 item 자체를 trajectory로 본다. `_parse_records()`는 dict의 `records` 또는 list를 record list로 변환한다.
→ [Exact Interpretation] leaderboard private data도 public 20과 같은 record trajectory 계열 interface로 들어온다고 보는 것이 현재 코드 기준의 합리적 판단이다.
→ [Detailed Explanation/Example] 정확한 private 차원과 pass/fail 비율은 private label/file 접근 권한이 없으므로 알 수 없다. 따라서 public 20과 local hidden-like split의 차원 일치만 검증하고, private prior를 가정하지 않는다.

## 생성 데이터 판단

[Original Text/Data] 이전 archive의 broken manifest는 480 rows 중 `records` 포함 input이 0개, command step 16개, ifd/score auxiliary 464개였다.
→ [Exact Interpretation] 그 manifest는 full trajectory 학습 데이터가 아니므로 생성 데이터 품질 평가 대상으로 부적합하다.
→ [Detailed Explanation/Example] line 1 같은 row는 어떤 case의 `records[32].input` 수준으로 flatten된 단일 command라서 이전 상태 transition과 final output/status를 잃는다.

[Original Text/Data] 이전 archive 기준 raw `augmented_train.json`은 300 trajectory, pass 150/fail 150, record mean 16.853이었다.
→ [Exact Interpretation] raw augmented source 자체는 public 20의 평균 record_count 16.4와 매우 가깝다.
→ [Detailed Explanation/Example] 문제는 raw 생성 데이터 전체가 아니라 manifest builder가 이를 step 또는 auxiliary row로 잘못 변환한 경로다.

[Original Text/Data] 이전 archive 기준 raw `training_cases.json`은 2163 trajectory, pass 863/fail 1300, record mean 10.75였다.
→ [Exact Interpretation] 이 source는 public 20보다 짧고 fail-heavy이다.
→ [Detailed Explanation/Example] 그대로 섞으면 fail prior와 length distribution이 public 20에서 멀어질 수 있으므로 selector나 split gate가 필요하다.

[Original Text/Data] 새 작업 루트 `/workspace/sinjeongmin_opal_verifier`에는 아직 재생성된 training manifest가 없다.
→ [Exact Interpretation] `/workspace/team6`의 이전 training data는 우리 소유 루트 산출물로 더 이상 취급하지 않는다.
→ [Detailed Explanation/Example] 다음 실행은 새 루트에 repo와 data를 재구성한 뒤 같은 dimension audit을 다시 수행해야 한다.

## 구현 검증

[Original Text/Data] `tools/analysis/build_supervised_manifest.py`는 `{"records": [...], "label": ...}` parent trajectory를 하나의 raw record로 보존하도록 수정했다.
→ [Exact Interpretation] 생성 데이터가 full trajectory 입력으로 manifest에 들어간다.
→ [Detailed Explanation/Example] `extract_input_text()`는 labeled trajectory에 대해 `{"records": ...}` JSON만 사용하고 `ifd_score`, `metrics`를 input에 넣지 않는다.

[Original Text/Data] 같은 `input_hash_no_label`에서 pass/fail label이 섞이면 해당 group 전체를 `label_conflict`로 제외하도록 수정했다.
→ [Exact Interpretation] 동일 trajectory에 상반 label이 걸린 샘플은 학습 후보에서 빠진다.
→ [Detailed Explanation/Example] content_hash는 label을 포함하므로 동일 input의 pass/fail 충돌을 잡지 못한다. 별도 input-only hash가 필요하다.

[Original Text/Data] manifest row에 `parse_status`, `metadata_only`, `prompt_schema_hash`, `input_hash_no_label`, `input_token_count`, `family_component`를 추가했다.
→ [Exact Interpretation] downstream validator/training/eval이 P0 semantic field를 다시 검증할 수 있다.
→ [Detailed Explanation/Example] prompt_schema_hash는 row content가 아니라 renderer contract hash라 split마다 하나로 유지된다.

[Original Text/Data] `python3 -m py_compile tools/analysis/build_supervised_manifest.py tests/test_build_supervised_manifest.py`, `python3 -m unittest discover -s tests -v`, `git diff --check`가 모두 통과했다.
→ [Exact Interpretation] 현재 로컬 코드 변경은 최소 regression test를 통과했다.
→ [Detailed Explanation/Example] unittest는 43개 통과했고, trajectory 보존, auxiliary 제외, label conflict 제외, P0 semantic field 존재를 포함한다.

## 제출 판단

[Original Text/Data] 새 루트에서 재생성된 manifest와 학습 결과가 아직 없다.
→ [Exact Interpretation] leaderboard 제출은 no-go이다.
→ [Detailed Explanation/Example] 제출하려면 기존 결과와 다른 점이 새 full-trajectory manifest, label-conflict 제거, P0 semantic gate 통과, 새 root에서 재현된 학습/eval metric으로 입증되어야 한다.

## 다음 단계

1. `/workspace/sinjeongmin_opal_verifier/repo`에 현재 branch 작업물을 배치한다.
2. public 20 reference를 새 root의 `data/reference/public20_shape.json` 형태로 저장한다.
3. 새 root에서 생성 데이터 또는 migration candidate를 재구성한다.
4. fixed builder로 manifest v2를 만들고 label_conflict, trajectory_ratio, pass/fail prior, record_count/length distribution을 검증한다.
5. gate 통과 전에는 학습과 leaderboard 제출을 재개하지 않는다.
