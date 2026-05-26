# Cycle 기록 - packaging root 수정 및 v3 학습 재시작

- 시각: 2026-05-26 10:57:11 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 기준 커밋: `5fa8cb8`
- 서버 런타임 루트: `/workspace/sinjeongmin_opal_verifier`

## 결론

- `v3` manifest는 전체 `records` trajectory 단위로 구성되어 있어, 이전 manifest의 step/metadata 단위 학습 병목은 해결된 것으로 판정했다.
- 현재 architecture와 학습 실행 경로에는 rule engine을 넣지 않았다. rulebase는 audit-only 기준으로만 남긴다.
- `/workspace/team6`는 우리 작업 폴더가 아니므로, 제출 packaging 스크립트의 실행 경로 의존을 제거했다.
- leaderboard 제출은 하지 않는다. 이유는 아직 실제 학습 완료, calibration/hidden 평가, merged/package `<12GB` smoke gate를 통과하지 않았기 때문이다.

## 데이터 구조 검증

- 공개 20개 testcase는 top-level `list`이고 각 record는 `index`, `input`, `output`을 가진다.
- 공개 label prior는 `pass=10`, `fail=10`이다.
- private leaderboard의 실제 길이 분포와 label prior는 접근할 수 없으므로 알 수 없다. 다만 solver interface와 public 20을 근거로 trajectory 계열 입력이라고만 추론한다.
- `v3` manifest는 `1154/1154` row가 full trajectory JSON이며, `metadata_only=0`, input-label conflict group `0`이다.
- 남은 데이터 리스크:
  - public20 char 평균 `6911.3`, v3 char 평균 `5007.27`로 v3가 짧다.
  - public20에는 1-record case가 있으나 v3 min record count는 `2`다.

## 학습 실행 판단

- 첫 r64 all-linear LoRA run:
  - run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1120_KST_train_v3_alllinear_lora_r64`
  - adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs4ga2`
  - 결과: OOM으로 종료
  - 원인: batch-size `4`에서 label smoothing log-softmax가 추가 `7.58GiB`를 요구했지만 free VRAM이 `6.38GiB`였다.
- 재시작 run:
  - run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2`
  - adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4`
  - 변경: batch-size `2`, grad-accum `4`, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
  - 관찰: 2026-05-26 10:56:36 KST 기준 11/590 step 진행, GPU util `100%`, VRAM `33186/46068MiB` 사용, OOM 없음

## fine-tuning 대안 결정

- LoRA adapter-only가 12GB 제출 제한 중 극히 일부만 쓰는 문제는 타당한 가설이다.
- 현재 r64 all-linear LoRA는 baseline으로 끝까지 학습하고 평가한다.
- 다음 검증 순서는 다음과 같이 결정했다.
  1. 현재 r64 all-linear LoRA 학습 완료
  2. calibration/hidden manifest 평가
  3. `merge_and_unload()` 기반 standalone merged model 생성, 크기 `<12GB` 및 offline smoke 확인
  4. full fine-tuning 또는 selective/partial fine-tuning dry-run으로 VRAM peak와 checkpoint/resume 가능성 확인
  5. 충분 학습 후 LoRA baseline과 비교

## packaging root 수정

- 변경 파일:
  - `tools/eval/prepare_submit.sh`
  - `tools/eval/prepare_submission.sh`
- 변경 내용:
  - 실행 경로의 `/workspace/team6` 의존 제거
  - 기본 runtime root를 `OPAL_RUNTIME_ROOT` 또는 `/workspace/sinjeongmin_opal_verifier`로 설정
  - repo 경로를 `OPAL_REPO` 또는 현재 git root로 설정
  - 제출 디렉터리를 `$OPAL_RUNTIME_ROOT/submissions/...` 아래로 이동
  - old adapter 후보를 `$OPAL_RUNTIME_ROOT/adapters/uncertainty_resolver/final`로 변경
  - legacy `prepare_submission.sh`는 `--with-lora` 없이 실행될 경우 fail-closed하며, 자동 `git checkout dev && git pull`을 수행하지 않는다.

## 검증

- `bash -n tools/eval/prepare_submit.sh`: 통과
- `bash -n tools/eval/prepare_submission.sh`: 통과
- `rg "/workspace/team6" tools/eval/prepare_submit.sh tools/eval/prepare_submission.sh`: 매치 없음
- `OPAL_RUNTIME_ROOT=/tmp/opal_packaging_probe OPAL_REPO=$PWD bash tools/eval/prepare_submission.sh`: `--with-lora` 없음으로 exit `1`, LLM artifact 필수 fail-closed 확인
- `OPAL_RUNTIME_ROOT=/tmp/opal_packaging_probe OPAL_REPO=$PWD bash tools/eval/prepare_submit.sh /tmp/nonexistent_adapter`: adapter 없음으로 exit `1`, 잘못된 adapter path fail-closed 확인
- `git diff --check`: 통과

## 다음 단계

- 현재 학습 run을 계속 모니터링한다.
- 첫 epoch checkpoint가 생성되면 checkpoint/resume 가능성을 기록한다.
- 학습 완료 후 manifest 평가와 threshold sweep을 실행한다.
- 제출 전에는 package size `<12GB`, offline load, first-forward smoke, `/workspace/team6` 경로 오염 없음 gate를 통과해야 한다.
