# 2026-05-27 KST No-Trust Data and Server Stop Archive

<!-- Changed: create an immutable archive note for the no-trust reset and stopped server queue. -->
<!-- Why: active docs need a citable record that separates confirmed facts from candidate evidence. -->

## Scope

[Original Text/Data] → 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`; prohibited root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`; allowed edits: `docs/current_task.md`, `docs/server_operations_current.md`, `PROGRESS.md`, `README.md`, and one new file under `docs/archive/cycles/2026-05-27/`. → [Exact Interpretation] → This archive records only the current no-trust data and server-stop state for the active repo. It does not authorize editing the adjacent team folder or any other file. → [Detailed Explanation/Example] → A worker may update active handoff docs and this archive note, but must not modify source code, tests, server access documents, generated data, or existing archive files.

## No-Trust Generated Data

[Original Text/Data] → "사용자가 기존 생성 데이터 전부를 신뢰하지 않겠다고 선언함. 기존 generated synthetic data는 학습/accepted sample로 사용 금지, 감사/격리 대상으로만 취급." → [Exact Interpretation] → All pre-existing generated synthetic data is untrusted. It cannot be used as training data, an accepted sample, or accepted generated evidence. → [Detailed Explanation/Example] → Existing generated artifacts may be referenced only for audit/quarantine bookkeeping. A training manifest, accepted sample document, or candidate model recipe must not consume those rows as accepted data.

[Original Text/Data] → "sample 1개는 모든 검증 통과 뒤에만 공개." → [Exact Interpretation] → Even a single public sample remains no-go until it has passed all required validation gates. → [Detailed Explanation/Example] → A generated trajectory cannot be shown as an accepted sample after only partial parser, dedup, judge, or shape checks; every required gate must be complete first.

## Server Stop State

[Original Text/Data] → "서버 4B QLoRA queue는 중단됨. GPU 0 MiB/0%." → [Exact Interpretation] → The latest known server training queue state is stopped, and the GPU is idle. → [Detailed Explanation/Example] → A resumed worker should not assume an active 4B QLoRA process is still running; it should treat the queue as interrupted and verify state before any new server action.

[Original Text/Data] → "이전 queue run root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0434_KST_public20_candidate_training`; seed11 train ok but logprob fail, seed29 train ok but logprob eval 중 중단. 결과 후보로 쓰지 말 것." → [Exact Interpretation] → The queue outputs under that run root are not valid model candidates. seed11 lacks a passing logprob evaluation, and seed29 was interrupted during logprob evaluation. → [Detailed Explanation/Example] → These outputs must not be promoted to leaderboard, package, calibration, or model-selection evidence. They may be mentioned only as interrupted-run evidence.

## Public20 Split Reset

[Original Text/Data] → "public20 model validation split 기준은 10 train / 10 val로 재설정됨. 기존 16/4 결과는 archive evidence only." → [Exact Interpretation] → Current public20-only model validation must use a 10 train / 10 val criterion. Prior 16 train / 4 val results are historical evidence only. → [Detailed Explanation/Example] → A new validation report should not describe 16/4 results as the active criterion. If old seed11/29/47 16/4 metrics are cited, they must be labeled archive-only and not used as the current selection basis.

## Submission Revalidation

[Original Text/Data] → "required submission files는 project.pdf 기준으로 추후 재검증: setup.sh, pyproject.toml, uv.lock, src/solver.py, src/__init__.py 등." → [Exact Interpretation] → Submission package readiness is not final until required files are checked against project.pdf. → [Detailed Explanation/Example] → Before submission, at minimum `setup.sh`, `pyproject.toml`, `uv.lock`, `src/solver.py`, and `src/__init__.py` need a project.pdf-based revalidation pass; current documentation does not claim that pass is complete.

## Security

[Original Text/Data] → "비밀/접속 정보는 쓰지 마세요." → [Exact Interpretation] → This archive must not contain passwords, tokens, private connection payloads, or server access secrets. → [Detailed Explanation/Example] → Server root paths and run roots are recorded because they are operational evidence; credentials and the body of server access documents are not copied here.
