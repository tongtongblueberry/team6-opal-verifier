# Team 6 Opal Verifier

SNU Introduction to Deep Learning (M2177.0043) Opal command-response trajectory pass/fail classification.

## 현재 원칙

- 제출 및 학습 architecture는 LLM-only다.
- rule engine, rule fallback, rule-id 기반 runtime, public label supervised 학습을 사용하지 않는다.
- public 20은 supervised train source가 아니라 shape/reference 감사용으로만 사용한다.
- Gate A/B/C 통과 후 데이터는 `train`, `val`, `test`, `public20_reference`로 분리한다.
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
+-- self_instruct_invariants.py
+-- audit_self_instruct_quality.py
+-- compare_public20_dimensions.py
+-- audit_public20_reference.py

tools/datagen/
+-- self_instruct_seed_schema.py
+-- self_instruct_candidate_schema.py

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
+-- export_merged_model.py
```

<!-- Changed: remove the legacy executable archive from the active tools namespace. -->
<!-- Why: stale executable code under tools/ kept reappearing in searches even though the current architecture is LLM-only. -->
과거 rule pipeline, rule-prompt solver, public-label eval script, `/workspace/team6` 기반 script의 실행 코드는 active repo에서 제거했다. 필요한 폐기 근거와 삭제 범위는 [docs/archive/legacy/legacy_rule_pipeline_removed.md](docs/archive/legacy/legacy_rule_pipeline_removed.md)에만 둔다.

<!-- Changed: remove legacy synthetic generators from the active datagen surface. -->
<!-- Why: the current data path is Self-Instruct only, while v4/v4.1 and spec/gap generators are archived failure or legacy evidence. -->
v4/v4.1 long trajectory datagen과 spec/gap synthetic datagen은 active `tools/datagen/`에서 제거했다. 근거는 `docs/archive/legacy_datagen/`와 `docs/archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md`에 둔다.

현재 active `configs/` 폴더는 없다. `wandb` sweep은 사용하지 않는다.

## 현재 운영 문서

- 서버 운영: [docs/server_operations_current.md](docs/server_operations_current.md)
- 현재 handoff: [docs/current_task.md](docs/current_task.md)
- agent 공통 맥락: [docs/agent_handoff.md](docs/agent_handoff.md)
- Self-Instruct data plan: [docs/current_self_instruct_data_plan.md](docs/current_self_instruct_data_plan.md)
- archive index: [docs/README.md](docs/README.md)
- sample 공개 정책: [docs/samples/README.md](docs/samples/README.md)
- 최신 cycle 기록: [docs/archive/cycles/2026-05-26/](docs/archive/cycles/2026-05-26/)

## 로컬 검증

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile src/solver.py tools/eval/check_submit_package.py
git diff --check
```

현재 로컬 회귀 테스트는 package readiness, no-rule marker gate, manifest trajectory 구조, data audit root guard, Self-Instruct seed/candidate schema, final-response invariant, full/selective fine-tuning CLI, LoRA sweep CLI, runtime smoke 계약을 포함한다.

<!-- Changed: record public20 local reference facts and split policy in the root README. -->
<!-- Why: data workers must not confuse public20 reference data with supervised training data. -->
현재 public20 local reference는 `data/local/public20/public20_input.jsonl`과
`data/local/public20/public20_labels.local.jsonl`이다. rows `20`, record_count
min/mean/max `1/16.4/39`, label distribution `fail=10`, `pass=10`이다.
label 파일은 aggregate 비교와 held-out metric에만 쓰고 generation/training prompt나
manifest target에는 넣지 않는다.

<!-- Changed: add the Gate B dimension comparison tool to the active surface. -->
<!-- Why: generated candidate profiles must be compared against public20 before Gate C model-input checks. -->
Gate B dimension 비교는 `tools/analysis/compare_public20_dimensions.py`가 담당한다.
이 도구는 public20 label을 row-level로 읽지 않고, local aggregate JSON만 선택적으로
받아 distribution report에 기록한다.

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
- Gate A/B/C 통과 후 `docs/samples/self_instruct_sample.md`에 generated raw trajectory 전체와 public20 raw sample 1개 전체를 기록.
