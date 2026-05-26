# Team 6 Opal Verifier

SNU Introduction to Deep Learning (M2177.0043) Opal command-response trajectory pass/fail classification.

## 현재 원칙

- 제출 및 학습 architecture는 LLM-only다.
- rule engine, rule fallback, rule-id 기반 runtime, public label supervised 학습을 사용하지 않는다.
- public 20은 supervised train source가 아니라 shape/reference 감사용으로만 사용한다.
- 서버 작업 root는 `/workspace/sinjeongmin_opal_verifier`다. `/workspace/team6`는 현재 작업 root로 사용하지 않는다.
- 서버 비밀번호나 token은 repo, 문서, script, shell command argument에 저장하지 않는다.

## 현재 제출 구조

```text
src/
+-- solver.py       # LLM artifact 기반 제출 entrypoint
+-- __init__.py

artifacts/
+-- merged_model/ 또는 lora_adapter*/
```

`src/solver.py`는 package-local merged model 또는 LoRA adapter를 로드한다. 모델 artifact가 없으면 rule fallback으로 돌아가지 않고 fail-closed 한다.

## 현재 주요 도구

```text
tools/analysis/
+-- build_supervised_manifest.py
+-- validate_manifest.py
+-- data_audit.py

tools/datagen/
+-- generate_long_shape_source.py
+-- generate_long_trajectories.py
+-- generate_spec_data.py
+-- generate_gap_data.py

tools/training/
+-- train_manifest_lora.py
+-- train_manifest_full.py
+-- run_manifest_lora_sweep.py

tools/eval/
+-- prepare_submit.sh
+-- check_submit_package.py
+-- runtime_smoke_submit_package.py
+-- eval_manifest_adapter.py
+-- select_manifest_sweep_candidate.py
```

과거 rule pipeline, rule-prompt solver, public-label eval script, `/workspace/team6` 기반 script는 `tools/archive/legacy_rule_pipeline/` 아래에만 보존한다. 현재 학습/제출 실행 경로로 사용하지 않는다.

## 현재 운영 문서

- 서버 운영: [docs/server_operations_current.md](docs/server_operations_current.md)
- 현재 handoff: [docs/archive/current_task.md](docs/archive/current_task.md)
- 최신 cycle 기록: [docs/archive/](docs/archive/)

## 로컬 검증

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile src/solver.py tools/eval/check_submit_package.py
git diff --check
```

현재 로컬 회귀 테스트는 package readiness, no-rule marker gate, manifest trajectory 구조, v4.1 shape generation, data audit root guard, full/selective fine-tuning CLI, LoRA sweep CLI, runtime smoke 계약을 포함한다.

## 서버 Sync 원칙

서버 연결은 최소 10회 재시도 단위로 점검한다. 연결이 회복되면 `/workspace/sinjeongmin_opal_verifier/repo`에서만 작업하고, `origin/sinjeongmin` 또는 검증된 bundle로 fast-forward만 수행한다.

```bash
git ls-remote origin refs/heads/sinjeongmin
git bundle verify /tmp/opal_cycle3_<short_head>_after_fca0652.bundle
```

자세한 명령은 [docs/server_operations_current.md](docs/server_operations_current.md)를 따른다.

## Leaderboard 제출 기준

현재 leaderboard 제출은 no-go 상태다. 제출하려면 다음 evidence가 필요하다.

- 새 학습 artifact 또는 평가 대상 artifact 완료.
- calibration/hidden 평가 및 threshold 결정 기록.
- package 크기 `<12GB`.
- `tools/eval/check_submit_package.py` 통과.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward` 통과.
- 기존 leaderboard 결과와 비교해 왜 지금 제출해야 하는지에 대한 Korean archive 기록.
