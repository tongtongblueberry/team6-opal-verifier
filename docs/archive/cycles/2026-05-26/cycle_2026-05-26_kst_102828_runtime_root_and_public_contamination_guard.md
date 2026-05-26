# 2026-05-26 10:28:28 KST Runtime Root 정정 및 Public Contamination Guard

## 결론

[Original Text/Data] 사용자가 `/workspace/team6`가 본인 폴더가 아니라고 정정했다.
→ [Exact Interpretation] 실행 코드가 기본값으로 `/workspace/team6`를 읽거나 쓰면 안 된다.
→ [Detailed Explanation/Example] datagen/filter/diagnosis 기본 output root를 `OPAL_RUNTIME_ROOT` 또는 `/workspace/sinjeongmin_opal_verifier`로 변경했다.

[Original Text/Data] `src/solver.py`에 `/workspace/team6/ops/runs/.../adapters/.../final` absolute fallback이 남아 있었다.
→ [Exact Interpretation] 제출/운영 solver가 타인/공용 경로의 adapter를 읽을 수 있는 위험이다.
→ [Detailed Explanation/Example] solver adapter 탐색은 repo-local artifacts 또는 명시적 `OPAL_LORA_ADAPTER`만 허용하도록 수정했다. adapter가 없으면 기존처럼 fail-closed 한다.

[Original Text/Data] `generate_spec_data.py`는 `training_cases.json`의 `source=public:*` row를 train에 자동 추가했다.
→ [Exact Interpretation] 새 root에 과거 public-labelled seed 파일이 들어오면 public 20 label contamination이 자동 발생한다.
→ [Detailed Explanation/Example] public seed 추가는 `--include-public-seed` 명시 옵션이 있을 때만 수행하도록 바꿨다.

[Original Text/Data] `generate_mutations.py`는 public 20 testcase에서 mutation과 original anchor를 만든다.
→ [Exact Interpretation] 이 스크립트의 출력은 supervised training source로 쓰면 안 된다.
→ [Detailed Explanation/Example] 기본 실행은 거부하고, audit/quarantine 목적일 때만 `--allow-public-derived-output`을 요구한다.

## 변경 파일

[Original Text/Data] 수정 파일: `src/solver.py`, `tools/datagen/filter_data.py`, `tools/datagen/generate_distillation.py`, `tools/datagen/generate_gap_data.py`, `tools/datagen/generate_long_trajectories.py`, `tools/datagen/generate_mutations.py`, `tools/datagen/generate_spec_data.py`, `tools/eval/diagnose_public.py`.
→ [Exact Interpretation] 실행 기본 경로와 public-derived source guard만 바꿨다.
→ [Detailed Explanation/Example] `docs/archive` 과거 기록과 `rulebase-73-clean` worktree는 수정하지 않았다.

## 검증

[Original Text/Data] `python3 -m py_compile src/solver.py tools/datagen/generate_distillation.py tools/datagen/generate_gap_data.py tools/datagen/generate_long_trajectories.py tools/datagen/generate_mutations.py tools/datagen/generate_spec_data.py tools/datagen/filter_data.py tools/eval/diagnose_public.py`.
→ [Exact Interpretation] 수정 파일 Python syntax/import compile은 통과했다.
→ [Detailed Explanation/Example] 경로 기본값 변경으로 syntax regression은 없다.

[Original Text/Data] `python3 -m unittest discover -s tests -v`: 43 tests OK.
→ [Exact Interpretation] 기존 test suite 기준 regression은 없다.
→ [Detailed Explanation/Example] solver adapter fallback 제거 후에도 merged/LoRA path tests가 통과했다.

[Original Text/Data] `python3 tools/datagen/generate_mutations.py`는 `Refusing to generate public-derived training rows by default...`로 종료했다.
→ [Exact Interpretation] public-derived mutation data가 실수로 생성되지 않는다.
→ [Detailed Explanation/Example] audit 목적이면 명시적으로 `--allow-public-derived-output`을 붙여야 한다.

## Leaderboard 판단

[Original Text/Data] 새 manifest, 새 학습, 새 package gate가 아직 없다.
→ [Exact Interpretation] leaderboard 제출은 no-go이다.
→ [Detailed Explanation/Example] 이번 변경은 제출 후보 성능 개선이 아니라 workspace/data contamination guard이므로 제출 기회를 사용할 근거가 아니다.

## 다음 단계

1. 변경 commit을 새 서버 repo `/workspace/sinjeongmin_opal_verifier/repo`에 배포한다.
2. `spec`, `gap`, `long` 함수 import 방식으로 public-free raw trajectory를 생성한다.
3. manifest v2를 만들고 trajectory ratio, label conflict, pass/fail prior, public/rule-context marker, public20 shape gap을 검증한다.
4. manifest dry-run gate 통과 후에만 학습을 재개한다.
