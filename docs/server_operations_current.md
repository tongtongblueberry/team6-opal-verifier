# 현재 서버 운영 절차

- 최종 갱신: 2026-05-26 13:15 KST
- 원칙: 제출/학습 architecture는 LLM-only다. rule engine, public label supervised 학습, legacy `/workspace/team6` 작업 root를 사용하지 않는다.
- SSH alias: `team6`
- 운영 root: `/workspace/sinjeongmin_opal_verifier`
- repo root: `/workspace/sinjeongmin_opal_verifier/repo`
- GitHub branch: `origin/sinjeongmin`

## 접속

서버 접속은 한 번의 점검 단위에서 최소 10회 재시도한다. 비밀번호를 repo, 문서, shell script, command-line argument에 저장하지 않는다.

```bash
for i in $(seq 1 10); do
  printf 'SSH_RETRY_%02d_START %s KST\n' "$i" "$(TZ=Asia/Seoul date '+%F %T')"
  ssh -o BatchMode=yes \
      -o ControlMaster=no \
      -o ControlPath=none \
      -o ConnectTimeout=15 \
      -o ConnectionAttempts=1 \
      -o ServerAliveInterval=5 \
      -o ServerAliveCountMax=2 \
      team6 'echo connected'
  rc=$?
  printf 'SSH_RETRY_%02d_RC %s %s KST\n' "$i" "$rc" "$(TZ=Asia/Seoul date '+%F %T')"
  [ "$rc" -eq 0 ] && break
  sleep 5
done
```

## 서버 Repo 동기화

먼저 서버 repo가 우리 root인지 확인한다. `/workspace/team6`는 사용하지 않는다.

```bash
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
set -euo pipefail
cd /workspace/sinjeongmin_opal_verifier/repo
test "$PWD" = /workspace/sinjeongmin_opal_verifier/repo
git status --short --branch
git rev-parse HEAD
'
```

GitHub 접근이 가능하면 fast-forward만 허용한다.

```bash
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
set -euo pipefail
cd /workspace/sinjeongmin_opal_verifier/repo
test -z "$(git status --porcelain)"
git fetch origin sinjeongmin
git merge --ff-only FETCH_HEAD
git rev-parse HEAD
'
```

GitHub 접근이 안 되면 로컬 bundle을 scp한 뒤 서버에서 fast-forward만 수행한다. bundle 파일명은 로컬에서 `git rev-parse --short HEAD`와 `git bundle verify`로 확인한 최신 파일을 사용한다.

```bash
scp /tmp/opal_cycle3_<short_head>_after_fca0652.bundle team6:/tmp/
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
set -euo pipefail
cd /workspace/sinjeongmin_opal_verifier/repo
test -z "$(git status --porcelain)"
git fetch /tmp/opal_cycle3_<short_head>_after_fca0652.bundle HEAD
git merge --ff-only FETCH_HEAD
git rev-parse HEAD
'
```

## 연결 회복 직후 확인 순서

1. `/workspace/sinjeongmin_opal_verifier/repo`의 `git status --short --branch`, `git rev-parse HEAD`.
2. 기존 LoRA baseline run 상태:
   - run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2`
   - adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4`
3. GPU 상태: `nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader`.
4. v4.1 strict reference validation:
   - manifest/reference는 `docs/archive/current_task.md`의 최신 경로를 따른다.
5. LoRA baseline이 완료되어 있으면 calibration/hidden threshold sweep 평가.
6. package `<12GB`, `check_submit_package.py`, offline first-forward smoke가 모두 통과할 때만 leaderboard 제출을 검토한다.

## 제출 판단

현재 leaderboard 제출은 no-go다. 제출하려면 다음 evidence가 필요하다.

- 새 학습 artifact 또는 평가 대상 artifact의 완료 상태.
- calibration/hidden 평가 결과와 threshold 결정 근거.
- package 크기 `<12GB`.
- `tools/eval/check_submit_package.py` 통과.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward` 통과.
- 기존 leaderboard 결과 대비 왜 지금 제출해야 하는지에 대한 기록.
