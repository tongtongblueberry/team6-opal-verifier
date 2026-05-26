# Team 6 Opal Verifier

SNU Introduction to Deep Learning (M2177.0043) Opal command-response trajectory pass/fail classification.

## 현재 원칙

<!-- Changed: mirror the agent_handoff.md runtime architecture rule. -->
<!-- Why: active docs must state the current no-rule architecture with the same operational wording. -->
- runtime rule engine 금지, LLM-only architecture.
- rule engine, rule fallback, rule-id 기반 runtime을 사용하지 않는다.
- public20은 synthetic 데이터 검증 대상이 아니라 shape/reference 비교 기준이다.
- public20 label은 synthetic generation/judge/generated manifest target으로 쓰지 않는다.
  public20-only 모델 후보 검증에서는 별도 local artifact로 20개를 stratified `16 train` /
  `4 val`로만 나눠 labels를 train target과 val metric에 쓸 수 있고, test는 leaderboard
  hidden 평가다.
- synthetic 데이터만 생성 데이터 검증 대상. Gate A/B/C/D 통과 후 sample 공개.
- Gate A/B/C 통과 후 generated synthetic 데이터는 `train`, `val`, `test`로 분리하고,
  public20은 `public20_reference`로 따로 둔다.
- public20은 reference 및 모델 train/val 기준. public20 test split 금지. hidden leaderboard가 test.
- prompt-only/no-training baseline은 active plan에서 제거된 오해. public20 모델 검증은 실제 학습 후보만 사용.
- synthetic generation은 Self-Instruct 공식 논문과 공식 코드 기준으로만 진행한다.
  공식 출처와 차용 범위는 [third_party/self_instruct/README.md](third_party/self_instruct/README.md)에 둔다.
- 서버 작업 root는 `/workspace/sinjeongmin_opal_verifier`다. `/workspace/team6`는 현재 작업 root로 사용하지 않는다.
<!-- Changed: restore server_access as the server access authority. Why: the prior setup doc is no longer the server access source. -->
- 서버 접근 권위 문서는 [docs/archive/legacy/server_access.md](docs/archive/legacy/server_access.md); 서버 작업 agent는 먼저 읽고, 필요 시 최소 10회 재시도. 비밀번호/시크릿을 문서/로그에 복사하지 않음.
- branch/push 기준: origin `sinjeongmin`에 반영.
- 서버 비밀번호나 token은 repo, 문서, script, shell command argument에 저장하지 않는다.
- main agent는 직접 web 검색, SSH, 학습 실행, 파일 수정을 기본 작업 방식으로 삼지 않는다.
  실행/검색/수정/학습은 worker agent가 수행하고, main agent는 결과 종합과 최종 판단을 담당한다.

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
+-- dedup_self_instruct_candidates.py
+-- filter_self_instruct_judge.py
+-- audit_self_instruct_quality.py
+-- compare_public20_dimensions.py
+-- check_manifest_model_input_equivalence.py
+-- audit_public20_reference.py
+-- build_public20_train_val_split.py

tools/datagen/
+-- self_instruct_seed_schema.py
+-- self_instruct_candidate_schema.py
+-- run_self_instruct_generation.py
+-- parse_self_instruct_outputs.py

tools/training/
+-- train_manifest_lora.py
+-- train_manifest_full.py
+-- run_manifest_lora_sweep.py

tools/eval/
+-- prepare_submit.sh
+-- check_submit_package.py
+-- runtime_smoke_submit_package.py
+-- eval_manifest_adapter.py
+-- eval_manifest_full_model.py
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
- Self-Instruct 공식 구현 archive: [docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md](docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md)

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
label 파일은 synthetic generation, judge prompt, generated manifest target에는 넣지 않는다.
public20-only 모델 후보 검증에서는 별도 local artifact 안에서만 train target과 validation
metric에 사용하며 public20 `test` split은 만들지 않는다.

<!-- Changed: add the Gate B dimension comparison tool to the active surface. -->
<!-- Why: generated candidate profiles must be compared against public20 before Gate C model-input checks. -->
Gate B dimension 비교는 `tools/analysis/compare_public20_dimensions.py`가 담당한다.
이 도구는 public20 label을 row-level로 읽지 않고, local aggregate JSON만 선택적으로
받아 distribution report에 기록한다. 이것은 public20 자체 검증이 아니라 generated
synthetic 데이터가 public20 reference 구조/분포를 반영하는지 확인하는 gate다.

<!-- Changed: record the public20-only model validation rule. -->
<!-- Why: validation and test must not be conflated; leaderboard is the hidden test. -->
RAG, full fine-tuning, selective fine-tuning 후보 검증은 public20-only `train`/`val`
split으로 병렬 진행할 수 있다. 이때 `val`은 후보 선택/튜닝용 내부 검증이고, `test`는
public20에서 만들지 않는다. 하루 5회 제한이 있는 leaderboard hidden 평가가 test다.
따라서 public20-only 결과는 validation evidence이며 최종 test evidence로 쓰지 않는다.
모델 구현은 관련 논문과 검증된 라이브러리/reference code를 우선 따른다.
기본 split은 stratified `16 train / 4 val`이고, val은 `pass 2 / fail 2`를 목표로 한다.
여러 split을 돌릴 수는 있지만 모두 validation이며 test라고 부르지 않는다. 최종 제출 후보가
정해지면 선택된 recipe로 public20 20개 전체를 학습에 쓸지 별도 결정한다.

<!-- Changed: record the implemented public20 train/val split artifacts. -->
<!-- Why: public20-only model validation now has deterministic split inputs and reports, without creating a public20 test split. -->
public20-only split 생성 도구는 `tools/analysis/build_public20_train_val_split.py`다.
현재 seed `11`, `29`, `47` split을 `runs/model_validation/public20_splits/` 아래에
생성했다. 각 split은 `train.jsonl`, `val.jsonl`, `split_report.json`, `split_report.md`를
포함하며 row schema는 `sample_id`, `input`, `label`, `split`이다. 이 artifact는
public20-only model validation 전용이며 synthetic generation, synthetic judge, generated
synthetic manifest target으로 쓰지 않는다.

<!-- Changed: replace non-learning comparison notes with the five requested public20 training candidates. -->
<!-- Why: the user asked to train on public20 train/val because verified synthetic data is not ready. -->
모델 검증 축은 public20 `16 train / 4 val`로 실제 학습을 수행하는 후보 5개로 고정한다.

- 0.9B full fine-tuning: public20 train 16개만 사용하고 epoch `5/10/20`, patience `2`를 비교한다.
- 0.9B full fine-tuning + retrieved rulebook/spec context: 동일 split에서 retrieval context를 prompt에 붙이고 epoch `5/10/20`, patience `2`를 비교한다.
- 4B LoRA/QLoRA selective fine-tuning: PEFT/Transformers 검증 코드를 사용하고 epoch `3/5/10`, patience `1-2`를 비교한다.
- 4B LoRA/QLoRA + retrieved rulebook/spec context: 4B selective tuning에 retrieval context를 붙이고 epoch `3/5/10`, patience `1-2`를 비교한다.
- RAFT-style retrieval-augmented SFT/QLoRA: public20-only에서는 epoch `1/3/5`로 smoke/overfit check만 수행하고, synthetic Gate A/B/C 통과 데이터가 생기면 epoch `3/5/10`으로 확장한다.

<!-- Changed: add the full-model validation evaluator to the public20 training loop. -->
<!-- Why: 0.8B/0.9B full FT 후보는 LoRA adapter evaluator가 아니라 standalone full model path로 val metric을 봐야 한다. -->
Full/selective FT standalone model validation은 `tools/eval/eval_manifest_full_model.py`가 담당한다.
이 도구는 `train_manifest_full.build_messages` prompt contract를 사용하고, full model directory 또는
base model path를 직접 로드해 `val` rows의 next-token `pass`/`fail` logprob을 비교한다.
보고 metric은 accuracy, macro-F1, fail recall, pass recall, confusion matrix, per-sample
prediction/logprob이다. public20-only full FT early stopping은 epoch별 이 report를 비교해
val macro-F1 정체 또는 fail recall 하락 시 no-go/patience 중단으로 판단한다.

이 문제는 pure RAG는 아니지만 RAG 성격이 강하다. rulebook/spec은 weight에 모두 암기시키기
어렵고, trajectory state transition은 검색만으로 해결되지 않는다. 따라서 retrieval만 하는
비학습 대체물이 아니라, retrieval context와 fine-tuning/RAFT-style 학습을 결합하는 후보를
최종 유력 후보로 둔다.

<!-- Changed: remove ad-hoc fixture/smoke generation from the active surface. -->
<!-- Why: synthetic data must come from the selected paper protocol and pass Gate A/B/C before it can be treated as candidate training data. -->
임의 deterministic fixture/smoke generated data는 accepted synthetic data가 아니다.
active datagen에는 public20 input-only seed schema, label-bearing candidate schema,
dry-run generation request wrapper, raw output parser만 둔다. 새 synthetic generation
구현은 Self-Instruct output-first generation, LLM-only filtering, 논문식 quality audit
protocol을 따르는 후보만 허용한다.

<!-- Changed: lock synthetic generation to the official Self-Instruct source and no-LLM-first implementation order. -->
<!-- Why: the next implementation must follow verified paper/code structure and avoid another ad-hoc generator. -->
Self-Instruct 공식 출처는 Wang et al. 2023 ACL 논문과 `yizhongw/self-instruct`
공식 repository, Apache-2.0 license다. 현재는 코드를 vendor하지 않고
[third_party/self_instruct/README.md](third_party/self_instruct/README.md)에 출처와
차용 범위만 문서화한다. LLM 호출 없는 `parse_self_instruct_outputs`,
ROUGE-L/exact/conflict dedup/filter, Gate C manifest/model input equivalence
도구를 먼저 두고, 그 다음에만 LLM API generation wrapper와 LLM-only judge
filtering을 붙인다.

<!-- Changed: add dry-run Self-Instruct generation and judge wrappers. -->
<!-- Why: the next synthetic-data step needs official-protocol prompt payloads and judge result parsing without API calls or ad-hoc candidates. -->
`tools/datagen/run_self_instruct_generation.py`는 Self-Instruct output-first
classification prompt payload와 request metadata만 생성한다. 기본 모드는 dry-run이고
synthetic trajectory를 자체 생성하지 않으며 `--execute`는 현재 API 호출 없이 실패한다.
`tools/analysis/filter_self_instruct_judge.py`는 generated candidate용 LLM-only judge
payload를 만들고 외부 judge result JSONL을 accepted/rejected candidate로 파싱한다.
public20 label, rule id, rule engine output은 두 도구의 prompt 입력에 넣지 않는다.

## 서버 Sync 원칙

<!-- Changed: restore server_access and origin sinjeongmin as active server/git authority. -->
<!-- Why: server workers need the same authority source, retry rule, secret rule, and branch/push target across operating docs. -->
서버 접근 권위 문서는 [docs/archive/legacy/server_access.md](docs/archive/legacy/server_access.md); 서버 작업 agent는 먼저 읽고, 필요 시 최소 10회 재시도. 비밀번호/시크릿을 문서/로그에 복사하지 않음.
서버 연결은 최소 10회 재시도 단위로 점검한다. 연결이 회복되면 `/workspace/sinjeongmin_opal_verifier/repo`에서만 작업하고, `origin/sinjeongmin` 또는 검증된 bundle로 fast-forward만 수행한다.
branch/push 기준: origin `sinjeongmin`에 반영.

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
<!-- Changed: require Gate A/B/C/D before sample publication. -->
<!-- Why: samples must not be presented as accepted generated data before the full gate sequence. -->
- synthetic 데이터만 생성 데이터 검증 대상. Gate A/B/C/D 통과 후 sample 공개.
- Gate A/B/C/D 통과 후 `docs/samples/self_instruct_sample.md`에 generated raw trajectory 전체와 public20 raw sample 1개 전체를 기록.
