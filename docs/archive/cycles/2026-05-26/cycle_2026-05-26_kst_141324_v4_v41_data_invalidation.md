# Cycle 기록 - v4/v4.1 데이터 폐기 판단

- 기록 시각: 2026-05-26 14:13:24 KST
- 범위: v4/v4.1 long trajectory 및 shape-source 데이터 문제 기록
- 결론: 마지막 response 기준 과제라면 v4/v4.1은 학습 금지이며 폐기 후보로 둔다.

## 구조 골격

- 원천 생성기: `tools/datagen/generate_long_trajectories.py`
  - 함수: `gen_all()`, `add_length_padding()`, `main()`
- shape source 생성기: `tools/datagen/generate_long_shape_source.py`
  - 함수: `build_single_record_family()`, `write_jsonl()`, `main()`
- active 문서 반영 대상:
  - `docs/current_task.md`
  - `docs/server_operations_current.md`
  - `README.md`
  - `PROGRESS.md`

## 증거

[Original Text/Data] 원본 `/tmp/opal_v41_shape_repair_local_1779763839` raw 파일은 현재 로컬에 남아 있지 않았다. 동일 code path를 파일 생성 없이 재현한 결과, raw line 2에 해당하는 두 번째 row는 `label=fail`, `spec_rule=UNEXPECTED_ERROR_STATUS`, `description=SID+Set(C_PIN_MSID)->FAIL(unexpected)`, `step_count=27`이었다.
→ [Exact Interpretation] 사용자가 지적한 raw line 2 `label=fail` 현상은 현재 repo의 v4/v4.1 생성 경로에서 재현된다.
→ [Detailed Explanation/Example] 이 row의 마지막 step은 27번째 `EndSession SUCCESS`다. 같은 row에서 `records[25]`를 0-based로 읽으면 `Set FAIL`이고, 사람 기준 1-based step 번호로는 26번째 step이다. 즉 label-relevant failure가 중간에 있고 마지막 response는 정상 종료다.

[Original Text/Data] 재현 command의 aggregate 출력: `raw_cases 1155`, `labels Counter({'pass': 617, 'fail': 538})`, `fail_cases 538`, `fail_end_session_success 440`.
→ [Exact Interpretation] `tools/datagen/generate_long_trajectories.py`의 `gen_all()` 원천 fail 538개 중 440개가 마지막 `EndSession SUCCESS`로 끝난다.
→ [Detailed Explanation/Example] 마지막 response만 보고 pass/fail을 판정해야 하는 과제라면, 이 440개 fail row는 마지막 response 기준 label이 뒤집힌 학습 신호가 된다. 모델은 마지막 `EndSession SUCCESS`를 보면서 fail을 학습하게 된다.

[Original Text/Data] `tools/datagen/generate_long_trajectories.py:152`의 `gen_all()`에서 `end_steps = [_endsession()]`를 만들고, `tools/datagen/generate_long_trajectories.py:166-168`에서 `ues_ops = list(ops) + [_set_step(obj_name, obj_uid, "FAIL")]` 뒤에 `add(base_steps + ues_ops + end_steps, "fail", "UNEXPECTED_ERROR_STATUS", ...)`를 호출한다. 같은 파일의 UES boundary family도 `tools/datagen/generate_long_trajectories.py:317-320`에서 `add(base + [_set_step(..., "FAIL"), _endsession()], "fail", ...)` 패턴을 사용한다.
→ [Exact Interpretation] 코드 원인은 fail case 뒤에 `EndSession`을 append하는 생성 규칙이다.
→ [Detailed Explanation/Example] fail label은 중간 `Set FAIL` 또는 `Get FAIL`에 붙어 있는데, serialized trajectory의 마지막 response는 `EndSession SUCCESS`다. 최종 response 기준 학습에서는 label과 관측 대상이 불일치한다.

[Original Text/Data] `tools/datagen/generate_long_shape_source.py:480-502`는 `cases = add_length_padding(gen_all(), target_lengths)`로 v4/v4.1 raw source를 시작하고, 그 뒤 single-record family, enrichment, dense char fill, `write_jsonl()`까지 이어간다.
→ [Exact Interpretation] v4.1 shape repair는 token/char shape 문제를 줄였더라도 `gen_all()`의 중간 failure 뒤 `EndSession SUCCESS` 문제를 상속한다.
→ [Detailed Explanation/Example] v4.1 local evidence의 `513-1024=0`, `char median=5472.0`, `record_count min=1`은 shape gate 관점의 개선일 뿐, 마지막 response label alignment 문제를 해결하지 않는다.

## 판단

[Original Text/Data] 과제 기준이 마지막 response 판정이면 supervised input의 최종 response와 `label`이 일치해야 한다.
→ [Exact Interpretation] v4/v4.1은 이 기준을 만족하지 못하는 대량 fail sample을 포함한다.
→ [Detailed Explanation/Example] raw line 2는 `records[25] Set FAIL` 뒤 `records[26] EndSession SUCCESS`로 끝난다. 이런 row를 fail로 학습하면 모델이 마지막 response가 아닌 중간 event를 label target으로 오인할 수 있다.

[Original Text/Data] 사용자는 `제거할 것은 제거`라고 했지만 데이터 문제 원인 근거는 남겨야 한다고 지시했다.
→ [Exact Interpretation] 문제 생성기는 즉시 삭제하지 않고 근거 보존 및 감사 재현 전용으로 격리해야 한다.
→ [Detailed Explanation/Example] active CLI 기본 실행은 차단하고, 필요한 경우에만 명시적 audit reproduction flag로 재현한다. 학습 manifest 생성, 서버 strict validation, leaderboard 제출 판단에서는 v4/v4.1 산출물을 제외한다.

## 운영 결정

- v4 raw와 v4.1 raw/manifest는 학습 금지다.
- v4/v4.1은 폐기 후보이며, 새 학습 artifact의 근거로 사용하지 않는다.
- 후속 정리(2026-05-26 15:02 KST): `tools/datagen/generate_long_trajectories.py`와 `tools/datagen/generate_long_shape_source.py`는 active datagen에서 제거했다. 실패 근거는 이 archive와 `docs/archive/legacy_datagen/README.md`로 보존한다.
- active handoff와 서버 운영 절차에서는 v4.1 strict reference validation을 다음 단계에서 제거한다.
