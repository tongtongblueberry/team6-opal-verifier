# 현재 진행 상태 (세션 이어받기용)

<!-- 변경: Self-Instruct/RAG/RAFT 논리 구조 연구 기록 경로를 추가했다. 이유: 현재 작업의 산출물 위치만 최소 기록하기 위함이다. -->
- 연구 기록: docs/archive/research/paper_logic_self_instruct_rag_raft_2026-05-26_kst.md

- 최종 갱신: 2026-05-26 20:39 KST
- 원칙: 제출/학습 architecture에는 rule engine을 포함하지 않는다. 학습과 제출은 LLM 기반으로만 진행한다.
- 운영 root: `/workspace/sinjeongmin_opal_verifier`
- repo root: `/workspace/sinjeongmin_opal_verifier/repo`
- 로컬 작업 폴더: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
<!-- Changed: clarify the document/git lane local root. -->
<!-- Why: workers must not treat the adjacent team folder as the active repo. -->
- 작업 금지 폴더: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`은 현재 작업 repo가 아니므로 수정/검증/commit/push하지 않는다.
- 현재 branch: `cycle3/training-methods-20260526-kst`
- 최근 주요 commit:
  - `0f9214d refresh current operations docs`
  - `b2f6d3d make handoff sync checks authoritative`
  - `72d3e6a archive ssh retry status after resume`
  - `28bcacd refresh handoff after prepare submit test`
  - `3ba0f46 add prepare submit integration test`
  - `61d375e refresh current cycle handoff after guard cleanup`
  - `5056017 tighten submit and audit guards`
  - `98612ba archive rule prompt experiments and disable public seed`
  - `073f733 correct current handoff head`
  - `90fe432 archive second ssh retry batch`
  - `a2a24af archive legacy tool scripts`
  - `bad4fdd archive legacy source solvers`
  - `f1cb501 exclude legacy helper solvers from packages`
  - `c552158 archive legacy pipeline entrypoints`
  - `e8ba9b9 add v4.1 bin aware shape repair`
- GitHub:
  - authoritative check: `git ls-remote origin refs/heads/sinjeongmin`
  - 이 cleanup 직전 확인값: `0f9214d refresh current operations docs`
- 서버 sync용 최신 bundle:
  - authoritative 생성 명령: `git bundle create /tmp/opal_cycle3_$(git rev-parse --short HEAD)_after_fca0652.bundle fca06523f66fdd8f4950da6c51d87e4efaa74b6d..HEAD`
  - 이 cleanup 직전 확인값: `/tmp/opal_cycle3_0f9214d_after_fca0652.bundle`
  - required base: `fca06523f66fdd8f4950da6c51d87e4efaa74b6d`
- 로컬 테스트:
  - `python3 -m unittest discover -s tests -v`: 63 tests OK
- leaderboard 제출 판단: 현재 no-go. 새 artifact의 학습 완료, calibration/hidden 평가, package `<12GB`, offline first-forward smoke가 아직 없다.

## 현재 Cycle 결론

<!-- Changed: mirror the latest agent_handoff.md operating criteria. -->
<!-- Why: resumed workers must see the active architecture, data, public20, model, server, and branch/push rules in current_task.md. -->
<!-- Changed: add completed epoch5/external probe/batch_v2 Gate v2 status. -->
<!-- Why: current task state must separate completed no-go outcomes from conditional synthetic candidates. -->
- 완료 결과 archive: `docs/archive/cycles/2026-05-26/cycle_2026-05-26_kst_2035_completed_results_archive.md`
- 0.9B full FT epoch 5는 서버 run 성공 후 validation no-go다. val accuracy `0.25`, fail recall `0.0`,
  pass recall `0.5`, confusion `TP=0 TN=1 FP=1 FN=2`이며 epoch `10/20`은 no-go다.
- `external_llm_probe`는 judge accepted `1`, Gate A `pass`, Gate B `insufficient`, Gate C `no_go`다.
  `sample.md` 생성은 no-go다.
- `gemini_batch_v2`는 raw `12`, parser accepted/rejected `9/3`, dedup accepted/rejected `9/0`, judge accepted/rejected `9/0`,
  label `pass=6/fail=3`, record_count min/mean/max `8/13.0/18`이다. Gate v2 결과는 Gate A `pass`, Gate B `conditional pass`,
  Gate C `pass`, final `conditional`이다. strict full-pass 기준에서 `sample.md` 생성은 no-go이며 larger/balanced batch v3가 필요하다.
  raw run 산출물은 commit하지 않고 경로와 counts만 기록한다.
- 가장 큰 문제는 데이터 구조와 shape mismatch다.
- runtime rule engine 금지, LLM-only architecture.
<!-- Changed: restore server_access as the server access authority. Why: the prior setup doc is no longer the server access source. -->
- 서버 접근 권위 문서는 [docs/archive/legacy/server_access.md](archive/legacy/server_access.md); 서버 작업 agent는 먼저 읽고, 필요 시 최소 10회 재시도. 비밀번호/시크릿을 문서/로그에 복사하지 않음.
- synthetic 데이터만 생성 데이터 검증 대상. Gate A/B/C/D 통과 후 sample 공개.
- public20은 reference 및 모델 train/val 기준. public20 test split 금지. hidden leaderboard가 test.
- prompt-only/no-training baseline은 active plan에서 제거된 오해. public20 모델 검증은 실제 학습 후보만 사용.
- branch/push 기준: origin `sinjeongmin`에 반영.
- manifest builder가 개별 step 단위로 flatten되던 문제는 수정되어 `records` trajectory 전체가 하나의 supervised input으로 들어간다.
- `/workspace/team6`는 우리 작업 root가 아니므로 새 작업은 `/workspace/sinjeongmin_opal_verifier` 아래에서만 진행한다.
- synthetic 데이터 검증 대상은 public20이 아니라 우리가 생성한 generated data다.
- public20은 synthetic 데이터의 shape/profile/reference 비교 기준으로 쓴다.
- public20-only 모델 후보 검증에서는 public20 20개를 `train`/`val`로만 나누며 public20 `test` split은 만들지 않는다. test는 leaderboard hidden 평가다.
- `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는 leaderboard hidden 평가이므로 public20 validation 결과를 test 결과로 기록하지 않는다.
- public20-only 모델 검증 기본 split은 stratified `16 train / 4 val`이며 val은 `pass 2 / fail 2`를 목표로 한다. 여러 split을 돌려도 모두 validation이다.
- 최종 제출 후보가 정해진 뒤에만 선택 recipe로 public20 20개 전체를 학습에 쓸지 별도 판단한다.
- Gate B public20/generated profile 비교 도구는 `tools/analysis/compare_public20_dimensions.py`다.
- Gate C manifest/model input equivalence 도구는 `tools/analysis/check_manifest_model_input_equivalence.py`다.
- raw Self-Instruct output parser는 `tools/datagen/parse_self_instruct_outputs.py`다. 이 도구는 synthetic trajectory를 자체 생성하지 않는다.
- Self-Instruct dedup/filter는 `tools/analysis/dedup_self_instruct_candidates.py`다.
- Self-Instruct generation request dry-run wrapper는 `tools/datagen/run_self_instruct_generation.py`다. 이 도구는 prompt payload/metadata만 만들고 LLM/API 호출과 자체 candidate 생성을 하지 않는다.
- LLM-only judge dry-run/filter 도구는 `tools/analysis/filter_self_instruct_judge.py`다. 이 도구는 judge payload 생성과 외부 judge result parsing만 수행한다.
- ad-hoc fixture/smoke generated data는 논문 기반 synthetic data가 아니므로 active surface에서 제거한다.
  다음 synthetic generation은 Self-Instruct output-first generation과 LLM-only judge filtering을 따라야 한다.
- Self-Instruct 공식 기준은 Wang et al. 2023 ACL 논문, `https://github.com/yizhongw/self-instruct`,
  Apache-2.0 license다. 출처와 차용 범위는 `third_party/self_instruct/README.md`와
  `docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md`에 둔다.
- 다음 구현 순서는 외부 LLM runner raw output 확보, parser/dedup/judge filter 적용, Gate A/B/C/D 실행이다.
- rulebase 73-clean verifier는 데이터 품질 감사용 weak reference일 수는 있지만, 모델 architecture나 제출 runtime에 넣지 않는다.
- 제출 package는 `src/solver.py` 단일 LLM-only entrypoint를 기준으로 한다.
- legacy helper solver와 rule-prompt/27B public-eval 실험 solver 실행 코드는 active repo에서 삭제했고, 필요한 폐기 근거만 `docs/archive/legacy/legacy_rule_pipeline_removed.md`에 남긴다.
- spec/gap synthetic generator와 v4/v4.1 generator는 active `tools/datagen/`에서 제거했다.

## 데이터 현황

- v3 manifest는 public20 shape reference 기준 기본 gate를 통과했다.
- v3 strict gate 한계:
  - char median ratio `0.631065 < 0.70`
  - manifest 최단 `record_count=2`, reference 최단 `record_count=1`
- v4는 1-record coverage와 char median을 개선했지만 `513-1024` token bin이 145개 생겨 strict `length_jsd=0.109264 > 0.08`로 실패했다.
- v4/v4.1은 label alignment 문제 때문에 학습 금지 및 폐기 후보로 전환한다.
  <!-- Changed: keep active task docs from naming deleted datagen modules as active evidence paths. -->
  <!-- Why: v4/v4.1 failure details now live in archive-only evidence, while active docs should not preserve executable generator references. -->
  - raw line 2 재현: `label=fail`, 마지막 response `EndSession SUCCESS`.
  - 같은 row의 `records[25]`는 0-based 기준 `Set FAIL`이며, 1-based로는 26번째 step이다.
  - 폐기 archive의 원천 통계상 fail 538개 중 440개가 마지막 `EndSession SUCCESS`로 끝난다.
  - 코드 원인은 fail case 뒤에 `_endsession()`을 append하는 생성 패턴이다.
  - 마지막 response 기준 과제라면 v4/v4.1은 label target이 중간 event로 밀려 학습 신호가 오염된다.

## v4/v4.1 폐기 evidence

- run: `/tmp/opal_v41_shape_repair_local_1779763839`
- raw count: `1171`
- manifest selected records: `1170`
- labels: `pass=625`, `fail=545`
- split labels:
  - train: `pass=447`, `fail=384`
  - calibration: `pass=63`, `fail=54`
  - hidden: `pass=115`, `fail=107`
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
- no-reference validator:
  - reference 부재 때문에 `length_jsd`만 실패 처리됨
  - required fields, labels, duplicate, group leakage, template entropy, public holdout, rule-context gates는 통과
- 폐기 근거 archive:
  - `docs/archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md`
- active datagen 처리:
  - v4/v4.1 generator는 active `tools/datagen/`에서 제거했다.
  - spec/gap synthetic generator도 새 Self-Instruct-only 경로와 맞지 않아 active `tools/datagen/`에서 제거했다.
  - 정리 근거는 `docs/archive/legacy_datagen/README.md`에 둔다.

## 학습 현황

<!-- Changed: record current public20-only full FT stopping decision. -->
<!-- Why: next workers should not continue epoch 10/20 after fail recall collapsed at epoch 5. -->
- 0.9B full FT epoch 5:
  - 서버 run 성공
  - OOM 1회 후 `label_smoothing=0`으로 성공
  - val accuracy `0.25`
  - fail recall `0.0`
  - pass recall `0.5`
  - confusion `TP=0 TN=1 FP=1 FN=2`
  - epoch `10/20` no-go
- 서버에서 v3 기반 Qwen3.5-4B all-linear LoRA r64 baseline 학습을 시작했다.
- 안정 run:
  - `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2`
  - adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4`
  - batch size `2`, grad accumulation `4`, max_seq_len `2048`, epochs `10`
- 마지막 확인:
  - PID `101814` alive
  - epoch `1.0` checkpoint 존재
  - 이후 서버 SSH timeout으로 현재 상태는 미확정
- 새 GPU 학습은 현재 baseline run 상태를 확인하기 전에는 시작하지 않는다.

## Full/Selective Fine-tuning 판단

- 0.9B full fine-tuning은 48GB GPU에서 검증할 후보로 유지한다.
- 4B full fine-tuning은 Adam state, gradient, activation 메모리 때문에 첫 선택이 아니다.
- 4B는 우선 `last-n-layers` selective fine-tuning 또는 LoRA/DoRA/QLoRA 계열을 비교한다.
- v3 `max_seq_len=2048` dry-run은 tokenized ratio `0.594`라 비교 학습에는 부적합하다.
- 다음 full/selective 비교는 `max_seq_len=4096`을 우선한다.
- 실행 우선순위:
  1. 기존 4B LoRA r64 baseline 상태 확인 및 평가
  2. 4B `last-n-layers=4`, `max_seq_len=4096` short-run
  3. 0.8B/0.9B급 full FT
  4. 4B LoRA 4096 재학습
  5. DoRA/QLoRA 구현 검토

## Package/Git 현황

- `prepare_submit.sh`는 더 이상 `src/lora_solver.py`를 복사하지 않으며, 패키징 중 `check_submit_package.py`를 필수 실행한다.
- `tests/test_prepare_submit_script.py`는 fake LoRA adapter로 `prepare_submit.sh` 전체 패키징 flow와 `[6i] Python package readiness gate` 실행을 검증한다.
- `README.md`는 현재 LLM-only 구조와 `/workspace/sinjeongmin_opal_verifier` 운영 기준으로 정리했다.
- `PROGRESS.md`는 현재 LLM-only 구조 기준으로 정리했고, rule engine + LoRA override 설명은 과거 접근으로 명시했다.
<!-- Changed: restore server_access as the authority and preserve secret handling. -->
<!-- Why: server work must start from the authority doc and avoid copying secrets into docs/logs. -->
- `docs/server_operations_current.md`는 현재 서버 접속, sync, 평가, 제출 판단 절차의 기준 문서다.
- 서버 접근 권위 문서는 [docs/archive/legacy/server_access.md](archive/legacy/server_access.md); 서버 작업 agent는 먼저 읽고, 필요 시 최소 10회 재시도. 비밀번호/시크릿을 문서/로그에 복사하지 않음.
- 서버 접근이 필요한 후속 작업은 먼저 [docs/archive/legacy/server_access.md](archive/legacy/server_access.md)를 찾고 읽는다. 현재 repo에서는
  `docs/sweep_plan.md` 등 legacy 문서가 `docs/archive/legacy/`로 이동했으므로,
  active 기준인 `docs/server_operations_current.md`와 legacy setup 기록을 함께 확인한다.
  서버 작업 기록에는 비밀번호/시크릿을 출력하지 않는다.
- `prepare_submission.sh`는 public label 평가가 섞인 legacy script라 archive로 이동했다.
- `check_submit_package.py`는 package 안의 모든 `src/*.py`를 no-rule marker 대상으로 검사한다.
- active `src`는 `solver.py`, `__init__.py`만 남아 있다.
- `tools/analysis/data_audit.py` 기본 입력 후보는 `/workspace/sinjeongmin_opal_verifier/training_data`, 로컬 `training_data`만 허용한다.
- `/workspace/team6` 아래로 해석되는 `data_audit.py` input/reference path는 명시 입력 또는 symlink여도 실패한다.
- legacy full pipeline shell, old cycle training scripts, old datagen/eval/training helper code는 active repo에서 제거했다.
- active manifest path는 유지하고, legacy 실행 코드는 제출/학습 실행에 사용하지 않는다.
- active `configs/`는 제거했다. `wandb_sweep.yaml`은 현재 사용하지 않고, 존재하지 않는 `tools/run_optional_sweep.py`를 가리키던 stale config라 삭제했다.
- `tools/training/deploy_and_train.sh`는 비활성 legacy stub라 제거했다.
- `tools/training/brier_trainer.py`는 active 학습 코드에서 import되지 않는 독립 실험 파일이라 제거했다.
- `tests/`는 현재 active tools와 `src/solver.py` 회귀 검증만 남긴다. `__pycache__`는 생성 산출물이므로 제거했다.
- `tools/eval/prepare_submit.sh`는 repo-local `setup.sh`, `pyproject.toml`, `uv.lock`만 복사한다. 다른 workspace fallback은 제거했다.
<!-- Changed: remove active references to deleted spec/gap generator filenames. -->
<!-- Why: current_task should describe the Self-Instruct-only active surface without keeping removed datagen filenames in active docs. -->
- legacy spec/gap synthetic generators는 Self-Instruct-only 경로와 맞지 않아 active datagen에서 제거했다.
- v4/v4.1 long trajectory datagen도 active datagen에서 제거하고 archive evidence만 남긴다.
- `tools/eval/merge_adapters.py`는 active 호출/테스트 경로가 없는 adapter-soup 실험 도구라 제거했다.
- `tools/archive/legacy_rule_pipeline/` 실행 코드는 active `tools/` namespace 혼동을 줄이기 위해 삭제했고, 삭제 범위와 폐기 사유는 `docs/archive/legacy/legacy_rule_pipeline_removed.md`에 둔다.
- raw synthetic sample은 Gate A/B/C 통과 전에는 "합격 데이터"로 제시하지 않는다. 통과 뒤에는 `docs/samples/self_instruct_sample.md`에 generated 전체 trajectory, label, profile, public20 raw sample 1개 전체, Gate A/B/C 요약을 기록한다.
- Gate B dimension comparison은 public20 label을 local aggregate distribution과 public20-only `val` metric으로만 사용하고, row-level label을 synthetic generation/judge/generated manifest 입력에 넣지 않는다.
- 임의 fixture/smoke generator와 관련 runs 산출물은 삭제 대상이다.
  학습, 검증, leaderboard 제출 근거로 사용하지 않는다.
- RAG/full fine-tuning/selective fine-tuning 후보 검증은 데이터 검증 이후 또는 병렬 보조로만 진행한다. 구현은 논문과 검증된 라이브러리/reference code를 우선 따른다.
  <!-- Changed: correct the model plan to public20 training candidates only. -->
  <!-- Why: user requested actual public20 train/val learning while verified synthetic data is not ready. -->
- 모델 학습 후보 5개는 0.9B full FT, 0.9B full FT + retrieved rulebook/spec context, 4B LoRA/QLoRA selective FT, 4B LoRA/QLoRA + retrieved context, RAFT-style retrieval-augmented SFT/QLoRA다.
- public20-only 검증은 public20 train 16개로 실제 학습을 진행하는 검증이다.
- full/selective FT standalone checkpoint의 `val` 평가는 `tools/eval/eval_manifest_full_model.py`로 수행한다.
  이 도구는 LoRA adapter 전용 evaluator가 아니며 full model path를 직접 로드하고 `train_manifest_full.build_messages` prompt contract를 사용한다.
- pure RAG 문제는 아니지만 rulebook/spec retrieval과 trajectory state reasoning이 모두 필요하므로 retrieval + fine-tuning/RAFT-style 학습을 최종 유력 방향으로 본다.

## 서버 상태

- SSH alias: `team6`
- 반복 재시도 명령:
  - `ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ConnectTimeout=15 -o ConnectionAttempts=1 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 team6 '...'`
- 2026-05-26 12:22:51~12:25:51 KST에 SSH 10회 연속 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 12:27:36~12:30:37 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 12:43:30~12:46:45 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 12:53:05~12:56:20 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 12:58:54~13:02:10 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 13:04:53~13:08:08 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 13:11:56~13:15:11 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 2026-05-26 13:20:28~13:23:43 KST에 SSH 10회 추가 재시도했으나 모두 `Operation timed out`.
- 연결 회복 시 즉시 확인할 것:
  1. `/workspace/sinjeongmin_opal_verifier/repo` git status/head
  2. PID `101814` 학습 생존 여부
  3. final adapter 또는 latest checkpoint
  4. GPU memory/util
  5. reference file `/workspace/sinjeongmin_opal_verifier/data/reference/shape20_input_reference.jsonl`

## 다음 실행 순서

<!-- Changed: update next actions for completed conditional Gate v2 and epoch5 no-go. -->
<!-- Why: immediate work should archive the conditional result, avoid raw-run commits, and avoid extending failed epoch runs. -->
1. `gemini_batch_v2` Gate v2 결과를 archive와 active docs에 반영한다: Gate A `pass`, Gate B `conditional pass`, Gate C `pass`, final `conditional`, `sample.md` no-go.
2. raw run 산출물은 commit하지 않고 `PROGRESS.md`, `docs/agent_handoff.md`, `docs/current_task.md`, archive note에 경로와 counts만 기록한다.
3. larger/balanced batch v3로 Gate B full pass를 목표로 한다.
4. 0.9B full FT epoch `10/20`은 epoch 5 fail recall `0.0` 근거로 중단 상태를 유지한다.
5. 서버 SSH가 별도 작업에 필요하면 10회 이상 단위로 재시도하고, 서버 연결이 회복되면 현재 `origin/sinjeongmin` HEAD를 서버 repo에 fast-forward 방식으로 sync한다.

## 보안

- 서버 비밀번호는 저장소와 archive에 기록하지 않는다.
