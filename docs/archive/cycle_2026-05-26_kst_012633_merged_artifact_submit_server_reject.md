# 2026-05-26 KST 01:26:33 - Cycle 2 merged artifact 패키지 및 제출 시도 기록

## 요약

- 결정: LoRA adapter-only 패키지의 12GB 용량 미활용 문제를 해결하기 위해 `base + LoRA`를 `artifacts/merged_model`로 병합한 LLM-only 후보 패키지를 만들었다.
- 후보 패키지: `/workspace/team6/submit-final-merged-candidate-20260526_0115_KST`
- 로컬 브랜치: `cycle2/merged-artifact-20260526-kst`
- 커밋:
  - `9caa636 add merged artifact package path`
  - `78eacd5 harden merged package validation`
- 결론: 후보 패키지는 offline static gate와 first-forward runtime smoke를 통과했다. Leaderboard 제출은 job 생성 전 서버 issue로 reject 되었고, 제출 목록은 34개 그대로였다.

## 제출 판단

- 기존 실패와의 차이:
  - 과거 Job 401/403/481/490/493 계열은 runtime/package failure 또는 timeout으로 0점이었다.
  - 이번 후보는 `artifacts/merged_model` 직접 로드 경로를 사용하며, PEFT adapter 합성 없이 `AutoModelForCausalLM`이 병합 weight를 로드한다.
  - 서버 후보 패키지에서 `check_submit_package.py`와 `runtime_smoke_submit_package.py --offline --first-forward`가 모두 통과했다.
  - 패키지 크기는 `7.9G`, submit archive 크기는 `6378.08 MB`로 12GB 제한 안쪽이다.
- 제출 이유:
  - 사용자가 지적한 "LoRA만 3MB 사용" 문제를 직접 해소한 패키지 수용성 검증이다.
  - 현재 병합 후보는 기존 adapter-only runtime package와 물리 artifact 구성이 다르므로, 제출 서버가 정상이라면 job 생성 여부를 확인할 가치가 있다.
- 재시도 정책:
  - 결과가 모델/패키지 실패가 아니라 `Submission is not available due to server issue`이므로, 같은 패키지를 즉시 반복 제출하지 않는다.

## 구현 내용

- `src/solver.py`
  - `OPAL_MERGED_MODEL_DIR` 또는 package-local `artifacts/merged_model/config.json`이 있으면 merged model을 LoRA adapter보다 우선 로드한다.
  - env로 지정한 merged model 경로가 잘못되면 LoRA로 silently fallback하지 않고 fail-closed 한다.
  - 실제 서버 adapter 경로인 `artifacts/lora_adapter_final`을 LoRA fallback 후보에 추가했다.
- `tools/eval/export_merged_model.py`
  - `PeftModel.merge_and_unload()`로 base+LoRA를 standalone merged artifact로 저장한다.
  - `--overwrite` 시 기존 output directory를 지워 stale shard가 manifest에 섞이지 않도록 했다.
- `tools/eval/check_submit_package.py`
  - merged model 또는 LoRA adapter 중 하나를 LLM artifact로 인정한다.
  - `StatefulOpalVerifier`, `ProtocolState`, `RULE_SPEC_QUERIES`, `rule_id` 등 rule-engine marker를 실행 코드 기준으로 차단한다.
  - shard index만 있고 실제 weight shard가 없는 `artifacts/merged_model`을 실패 처리한다.
- tests
  - merged path 우선순위, invalid env fail-closed, LoRA fallback, `lora_adapter_final`, index-only artifact 실패를 추가 검증했다.

## 검증 결과

- 로컬:
  - `python3 -m py_compile ...`: 통과
  - `python3 -m unittest tests.test_submit_package_readiness tests.test_runtime_smoke_submit_package tests.test_solver_merged_model_path -v`: 17개 통과
  - `git diff --check`: 통과
  - forbidden marker scan: checker의 금지 목록 문자열만 탐지, `src/solver.py` 실행 경로에는 없음
- 서버 export:
  - base model: `Qwen/Qwen3.5-4B`
  - adapter: `/workspace/team6/submit-final/artifacts/lora_adapter_final`
  - output: `/workspace/team6/submit-final-merged-candidate-20260526_0115_KST/artifacts/merged_model`
  - merged total size: `8431600802 bytes` (`7.853 GiB`)
  - shard:
    - `model-00001-of-00003.safetensors`: `3991298872 bytes`
    - `model-00002-of-00003.safetensors`: `3979833152 bytes`
    - `model-00003-of-00003.safetensors`: `440426280 bytes`
- 서버 candidate gate:
  - `OK: submit package HF offline/artifact readiness (merged_model)`
  - `ARTIFACT_OK: merged_model at artifacts/merged_model`
  - `RUNTIME_OK: solver resolves local_files_only=True under offline env`
  - `MODEL_LOAD_OK: implied by first-forward`
  - `FIRST_FORWARD_OK: predict_one returned pass`

## 제출 결과

- run dir: `/workspace/team6/ops/runs/20260526_0120_KST_leaderboard_submit_merged_artifact`
- job name: `stratp0-llmonly-merged-artifact-20260526`
- hashes:
  - solver: `5474f418d463b38c2d898c5829dbaa6a370f44cce09024ad82093fad247dd9e0`
  - setup: `d308e64cbe7b45c105f8b2df92b5563a72699937bbd86e458a690500227d753f`
  - merged manifest: `3da8f93842f9fdba6daf5d13bacf5fa1f5ec555c49dfb6ea518a7c0f67a5067c`
- submit output:
  - `Archiving your submission... (6378.08 MB)`
  - `Checking availability...`
  - `Submission rejected.`
  - `Reason: Submission is not available due to server issue. please check TA's announcement`
- post-submit list:
  - 34 submissions 그대로
  - 새 submission ID 없음
  - 새 job ID 없음

## 다음 결정

- Leaderboard: 서버 issue가 유지되는 동안 동일 패키지 재제출은 NO-GO.
- Cycle 2 다음 단계:
  - 병합 artifact 경로는 패키징 문제를 해결했으므로, 다음 점수 개선은 새로운 학습 방법론에서 찾아야 한다.
  - 우선순위는 full fine-tuning 전면 실행보다, 48GB GPU에서 재시작 가능한 high-rank LoRA/DoRA/QLoRA 또는 partial full fine-tuning 후보를 충분히 학습하고 hidden-like metric으로 비교하는 것이다.
  - 기존 adapter와 병합 artifact는 보존한다. 실제 `/workspace/team6/submit-final`은 이번 candidate 생성 과정에서 덮지 않았다.
