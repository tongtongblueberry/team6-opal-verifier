# 2026-05-26 KST 06:19:06 - Cycle 3 leaderboard 제출 재시도 결과

## 구조 Skeleton
- 목적
- 제출 판단
- 제출 후보
- 사전 검증
- 실행 결과
- 해석
- 다음 결정

## 목적
- 이전 제출 병목이었던 제출 패키지 계약 문제를 해결한 뒤, Cycle 3 최종 후보를 leaderboard에 제출 가능한지 확인했다.
- architecture는 LLM-only이며 rule engine을 포함하지 않는다.

## 제출 판단
- 제출은 논리적으로 필요했다.
- 기존 실패와의 차이:
  - 이전 시도는 `uv.lock` 누락으로 제출 패키지 계약을 만족하지 못했다.
  - 그 다음 시도는 `submit` CLI가 positional path를 받지 않는데 경로를 positional로 넘겨 실패했다.
  - 이번 시도는 `uv.lock`을 제출 디렉터리에 복사했고, `submit -d <SUBMIT_DIR> -n cycle3_r16lr5e4_merged_th0p70` 형식으로 실행했다.
  - 제출 전 static package gate가 PASS였다.
  - runtime smoke는 이전 검증에서 offline first-forward PASS였다.
- 후보 자체도 이전 public 73.00 rule-base 계열과 다르다. 이번 후보는 rule engine 없이 `r16_lr5e4_do10_ep5@threshold=0.70` adapter를 merged model로 패키징한 LLM-only 제출물이다.

## 제출 후보
- 후보: `r16_lr5e4_do10_ep5@threshold=0.70`
- hidden metric:
  - accuracy: `0.9684210526`
  - precision_fail: `0.9545454545`
  - recall_fail: `0.9767441860`
  - ECE: `0.0455764314`
  - Brier: `0.0387454765`
- 제출 디렉터리: `/workspace/team6/submit-cycle3-r16_lr5e4_do10_ep5-merged-th0p7-20260526_KST`
- submit run dir: `/workspace/team6/ops/runs/20260526_0618_KST_leaderboard_submit_cycle3_r16lr5e4_merged_uvlock_submitd`
- 패키지 크기:
  - directory: `7.9G`
  - submit archive: `6363.38 MB`
  - leaderboard limit `12GB` 미만

## 사전 검증
- static package gate:
  - `OK: submit package HF offline/artifact readiness (merged_model)`
- 핵심 hash:
  - stdout.log: `e53dbdca135a0a8f653ffc1d9f3eb5cd412efa31027174b19df39b913adc1004`
  - `src/solver.py`: `5474f418d463b38c2d898c5829dbaa6a370f44cce09024ad82093fad247dd9e0`
  - `setup.sh`: `d308e64cbe7b45c105f8b2df92b5563a72699937bbd86e458a690500227d753f`
  - `uv.lock`: `e147436cf69969f14a4f6edcbfcba5c38c010659c67bebf3c3952f31ff916015`
  - `artifacts/merged_model/manifest.json`: `988a1e6001cde0da26e4edd8ad81d72b4ce33e87c66ed0ac05a5bbe97e1f778a`
- merged model shard sizes:
  - `model-00001-of-00003.safetensors`: `3991298872 bytes`
  - `model-00002-of-00003.safetensors`: `3979833152 bytes`
  - `model-00003-of-00003.safetensors`: `440426280 bytes`
  - `tokenizer.json`: `19989424 bytes`

## 실행 결과
```text
Archiving your submission... (6363.38 MB)
Checking availability...

Submission rejected.
Reason: Submission is not available due to server issue. please check TA's announcement
```

- `submit --list` 결과는 여전히 `34 submission(s) for team6`이다.
- 새 submission ID와 job ID가 생성되지 않았다.
- leaderboard score는 없다.

## 해석
- 이번 실패는 `uv.lock`, `submit` CLI, package size, static package readiness 문제가 아니다.
- archive 생성과 availability check까지 도달했으므로 제출 패키지 계약 문제는 이전보다 진전됐다.
- 최종 실패 원인은 서버 availability 단계의 외부 상태다.
- 새 job ID가 생성되지 않았기 때문에 현재 근거상 leaderboard 평가 기회가 실제 채점으로 소모되었다고 볼 수 없다.
- 같은 서버 상태에서 동일 패키지를 즉시 반복 제출하는 것은 정보 이득이 작다.

## 다음 결정
- 동일 패키지는 server availability가 회복됐다는 새 근거가 생길 때 재제출한다.
- 그 전까지는 Cycle 2 문제 확인으로 이동한다.
- 현재 데이터/학습 검증 agent 결론에 따르면 다음 병목은 다음 순서로 다룬다.
  - hidden split으로 threshold를 고른 점
  - 작은 calibration split
  - 모든 selected manifest가 `1-32` 길이 bin에 몰린 점
  - r32/r64 rank 증가가 pass false positive와 ECE를 악화한 점
- 다음 구현 후보는 calibration-first selector와 `step_count` 또는 long trajectory bucket 기반 manifest/eval 지표 추가다.
