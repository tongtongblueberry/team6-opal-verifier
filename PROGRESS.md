# Progress Log

- 최종 갱신: 2026-05-26 14:13 KST
- 현재 원칙: 제출/학습 architecture는 LLM-only다. rule engine, rule fallback, rule-id runtime, public label supervised 학습은 사용하지 않는다.
- 현재 서버 root: `/workspace/sinjeongmin_opal_verifier`
- 현재 GitHub branch: `origin/sinjeongmin`
- 현재 운영 문서: [docs/server_operations_current.md](docs/server_operations_current.md)
- 현재 handoff: [docs/current_task.md](docs/current_task.md)

## 현재 Architecture

```text
Input trajectory
       |
src/solver.py
       |
package-local LLM artifact
  - artifacts/merged_model/ 또는 artifacts/lora_adapter*/
       |
LLM next-token/logit decision
       |
"pass" 또는 "fail"
```

현재 제출 경로에는 `StatefulOpalVerifier.verify_with_trace`, rule prediction, `rule_id`, `UNEXPECTED_ERROR_STATUS` 분기, rule-engine fallback이 들어가면 안 된다. 모델 artifact가 없거나 로드에 실패하면 rule engine으로 대체하지 않고 fail-closed해야 한다.

## 과거 Rule + LoRA 설명의 상태

아래 구조는 과거 접근이고 현재 기준으로는 틀리다.

```text
Input trajectory
       |
[1] Rule Engine (StatefulOpalVerifier.verify_with_trace) -- 73.00 base
       |
  prediction + rule_id
       |
  rule_id == UNEXPECTED_ERROR_STATUS?
       NO  --> rule prediction
       YES --> LoRA 4B override
```

[Original Text/Data] 과거 문서에는 rule engine 73점 base가 먼저 판정하고 LoRA가 `UNEXPECTED_ERROR_STATUS` false positive를 rescue한다고 기록되어 있었다.
→ [Exact Interpretation] 이것은 이전 실험/leaderboard 기록 설명으로는 남길 수 있지만 현재 제출 architecture 설명으로 사용하면 안 된다.
→ [Detailed Explanation/Example] 현재 branch는 active `src`를 `solver.py`, `__init__.py`로 제한하고, legacy rule-prompt/solver 파일은 `tools/archive/legacy_rule_pipeline/` 아래로 이동했다.

## 현재 데이터/학습 상태

- 가장 큰 병목은 데이터 구조와 public/reference shape mismatch다.
- manifest builder의 records flatten 문제는 수정되어 전체 `records` trajectory가 하나의 supervised input으로 들어간다.
- v4.1 local shape repair evidence는 폐기 후보 evidence로 전환한다.
  - raw count: `1171`
  - manifest selected records: `1170`
  - labels: `pass=625`, `fail=545`
  - token bins: `513-1024=0`
  - char median: `5472.0`
  - record_count min: `1`
- 폐기 근거:
  - raw line 2는 `label=fail`이지만 마지막 response가 `EndSession SUCCESS`다.
  - 같은 row의 `records[25]`는 0-based 기준 `Set FAIL`이다.
  - `generate_long_trajectories.py` 원천 fail 538개 중 440개가 마지막 `EndSession SUCCESS`로 끝난다.
  - 마지막 response 기준 과제라면 v4/v4.1은 학습 금지다.

## 현재 서버 상태

- 서버 repo: `/workspace/sinjeongmin_opal_verifier/repo`
- 마지막으로 알려진 baseline run:
  - `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2`
  - adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4`
  - 마지막 확인 시 epoch 1 checkpoint 존재
- 이후 SSH timeout이 반복되어 현재 학습 완료 여부는 미확정이다.
- 서버 접속은 최소 10회 재시도 단위로 수행한다.

## Leaderboard 제출 판단

현재 leaderboard 제출은 no-go다.

제출 가능 조건:

- 서버 repo가 현재 `origin/sinjeongmin` HEAD로 fast-forward sync됨.
- v4/v4.1 raw/manifest가 평가 대상 학습 입력에 포함되지 않음.
- 평가 대상 artifact의 학습 완료 확인.
- calibration/hidden 평가 및 threshold 결정 기록.
- package 크기 `<12GB`.
- `tools/eval/check_submit_package.py` 통과.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward` 통과.
- 기존 leaderboard 결과와 비교해 왜 지금 제출해야 하는지 한국어 archive 기록 작성.

## 최근 정리

- `README.md`를 LLM-only 현재 구조 기준으로 교체했다.
- `docs/server_operations_current.md`를 현재 서버 운영 기준 문서로 추가했다.
- legacy `/workspace/team6`, `sshpass`, rule-engine/hybrid 문서는 archive 세부 폴더로 격리했다.
- `docs/current_task.md`가 다음 실행 순서의 기준이다.
- active `configs/`는 제거했다. 현재 `wandb`는 사용하지 않는다.
- `tools/training/deploy_and_train.sh`, `tools/training/brier_trainer.py`는 active 경로에서 제거했다.
- `src`, `tools`, `tests`의 `__pycache__` 생성 산출물은 제거했다.
- `tools/eval/prepare_submit.sh`의 외부 workspace fallback을 제거했다.
- `tools/datagen/generate_gap_data.py`의 missing `generate_uncertainty_data.py` 안내를 현재 manifest builder 경로로 고쳤다.
- `tools/eval/merge_adapters.py`는 active 호출/테스트 경로가 없는 adapter-soup 실험 도구라 제거했다.
- `tests/test_generate_gap_data_defaults.py`를 추가해 gap datagen 기본 경로가 항상 우리 workspace로 잡히는지 검증한다.
- v4/v4.1 long trajectory datagen은 deprecated/audit-only로 두고 기본 CLI 실행을 차단했다.
