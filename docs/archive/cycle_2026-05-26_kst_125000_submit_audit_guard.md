# Cycle 기록 - submit/audit guard 정리

- 시각: 2026-05-26 12:50 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: `/workspace/team6` 기본 의존과 제출 전 수동 checker 누락 가능성을 줄인다.

## 결론

- `tools/analysis/data_audit.py`의 기본 입력 후보에서 `/workspace/team6/training_data`를 제거했다.
- 기본 데이터 감사 후보는 `/workspace/sinjeongmin_opal_verifier/training_data`, `/workspace/sinjeongmin_opal_verifier/data`, 로컬 `training_data`, 로컬 `data` 순서다.
- `tools/eval/prepare_submit.sh`는 패키징 중 `tools/eval/check_submit_package.py`를 필수 실행한다.
- leaderboard 제출 사유는 아직 없다. 새 package artifact, offline first-forward smoke, calibration/hidden 평가가 필요하다.

## 근거

[Original Text/Data] `tools/analysis/data_audit.py`의 `DEFAULT_INPUT_CANDIDATES`에 과거 `/workspace/team6/training_data`가 남아 있었다.
→ [Exact Interpretation] 운영자가 `--input` 없이 audit를 실행하면 우리 root가 아닌 공유/legacy workspace를 읽을 수 있었다.
→ [Detailed Explanation/Example] 기본 후보를 우리 root와 repo-local 후보로 바꿔 unattended audit의 입력 소스를 제한했다.

[Original Text/Data] `tools/eval/prepare_submit.sh`는 shell 내부 LLM-only 검사만 수행하고, 더 강한 `check_submit_package.py`는 수동 후속 절차였다.
→ [Exact Interpretation] helper contamination, HF offline parity, incomplete artifact gate가 누락된 상태로 제출 명령까지 갈 수 있었다.
→ [Detailed Explanation/Example] Step 6i에서 Python package readiness gate를 실행하고 실패 시 `ERRORS`를 증가시켜 제출 준비가 실패하도록 했다.

## 검증

- `python3 -m unittest discover -s tests -v`: 58 tests OK
- `python3 -m py_compile tools/analysis/data_audit.py tools/eval/check_submit_package.py tests/test_data_audit_defaults.py`: OK
- `bash -n tools/eval/prepare_submit.sh`: OK
- `git diff --check`: OK
- 비밀값 prefix scan: absent
