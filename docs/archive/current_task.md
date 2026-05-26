# 현재 진행 상태 (세션 이어받기용)

- 최종 갱신: 2026-05-26 11:55 KST
- 원칙: 제출/학습 architecture에는 rule engine을 포함하지 않는다. 학습과 제출은 LLM 기반으로만 진행한다.
- 운영 root: `/workspace/sinjeongmin_opal_verifier`
- repo root: `/workspace/sinjeongmin_opal_verifier/repo`
- 로컬 작업 폴더: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 현재 branch: `cycle3/training-methods-20260526-kst`
- leaderboard 제출 판단: 현재 no-go. 새 artifact의 학습 완료, calibration/hidden 평가, package `<12GB`, offline first-forward smoke가 아직 없다.

## 현재 Cycle 결론

- 가장 큰 문제는 데이터 구조와 shape mismatch다.
- manifest builder가 개별 step 단위로 flatten되던 문제는 수정되어 `records` trajectory 전체가 하나의 supervised input으로 들어간다.
- `/workspace/team6`는 우리 작업 root가 아니므로 새 작업은 `/workspace/sinjeongmin_opal_verifier` 아래에서만 진행한다.
- public20은 supervised 학습 소스가 아니라 shape reference로만 쓴다.
- rulebase 73-clean verifier는 데이터 품질 감사용 weak reference일 수는 있지만, 모델 architecture나 제출 runtime에 넣지 않는다.

## 데이터 현황

- v3 manifest는 public20 shape reference 기준 기본 gate를 통과했다.
- v3 strict gate 한계:
  - char median ratio `0.631065 < 0.70`
  - manifest 최단 `record_count=2`, reference 최단 `record_count=1`
- v4는 1-record coverage와 char median을 개선했지만 `513-1024` token bin이 145개 생겨 strict `length_jsd=0.109264 > 0.08`로 실패했다.
- v4.1은 bin-aware repair로 진행 중이다.
  - token enrichment와 char enrichment를 분리한다.
  - `--max-enriched-tokens 512`로 `513-1024` overflow를 막는다.
  - dense no-whitespace payload로 char 길이를 올린다.
  - 로컬 no-reference 검증에서 builder는 통과했고, reference 필요 gate만 pending이다.

## v4.1 로컬 evidence

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

## 학습 현황

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

## 서버 상태

- SSH alias: `team6`
- 반복 재시도 명령:
  - `ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ConnectTimeout=20 -o ConnectionAttempts=1 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 team6 '...'`
- 2026-05-26 11:51 KST 기준 SSH는 `Operation timed out`.
- 연결 회복 시 즉시 확인할 것:
  1. `/workspace/sinjeongmin_opal_verifier/repo` git status/head
  2. PID `101814` 학습 생존 여부
  3. final adapter 또는 latest checkpoint
  4. GPU memory/util
  5. reference file `/workspace/sinjeongmin_opal_verifier/data/reference/shape20_input_reference.jsonl`

## 다음 실행 순서

1. v4.1 변경분을 archive와 함께 commit한다.
2. 서버 SSH를 계속 재시도한다.
3. 서버 연결이 회복되면 v4.1 strict reference validate를 실행한다.
4. LoRA baseline이 완료됐으면 calibration/hidden threshold sweep 평가를 수행한다.
5. package `<12GB`와 offline first-forward smoke가 통과할 때만 leaderboard 제출을 검토한다.
6. GPU가 비면 0.9B full fine-tuning 또는 4B selective fine-tuning short-run을 시작한다.

## 보안

- 서버 비밀번호는 저장소와 archive에 기록하지 않는다.
