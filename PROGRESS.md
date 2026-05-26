# Progress Log

- 최종 갱신: 2026-05-26 16:50 KST
- 현재 원칙: 제출/학습 architecture는 LLM-only다. rule engine, rule fallback, rule-id runtime은 사용하지 않는다.
- public20은 synthetic 데이터 검증 대상이 아니다. public20 label은 synthetic generation/judge/generated manifest target으로 쓰지 않는다. public20-only 모델 후보 검증에서는 `train`/`val`만 쓰고, test는 leaderboard hidden 평가다.
- `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는 leaderboard hidden 평가다. public20 validation 결과를 test 결과로 기록하지 않는다.
- main agent는 직접 web 검색, SSH, 학습 실행, 파일 수정을 기본 작업 방식으로 삼지 않고 worker agent 결과를 종합해 최종 판단한다.
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

<!-- Changed: remove the obsolete Rule+LoRA diagram from active progress. -->
<!-- Why: active progress should not preserve a visual architecture that is explicitly forbidden for the current LLM-only submission path. -->

과거 Rule+LoRA diagram은 active progress에서 제거했다. 폐기 근거와 삭제된 legacy executable archive 목록은 [docs/archive/legacy/legacy_rule_pipeline_removed.md](docs/archive/legacy/legacy_rule_pipeline_removed.md)에 둔다.

## 현재 데이터/학습 상태

- 가장 큰 병목은 데이터 구조와 public/reference shape mismatch다.
- manifest builder의 records flatten 문제는 수정되어 전체 `records` trajectory가 하나의 supervised input으로 들어간다.
- public20 local reference를 확보했다.
  - input-only: `data/local/public20/public20_input.jsonl`
  - labels local-only: `data/local/public20/public20_labels.local.jsonl`
  - rows `20`, record_count min/mean/max `1/16.4/39`, label distribution `fail=10`, `pass=10`
  - public20은 `public20_reference`로만 두고 generated synthetic `train`, `val`, `test`와 섞지 않는다.
  - public20-only 모델 후보 검증은 20개를 `train`/`val`로만 분리한다. public20 `test` split은 만들지 않는다.
- Gate B public20/generated profile 비교 도구 `tools/analysis/compare_public20_dimensions.py`를 추가했다.
  - public20 reference와 generated profile을 비교하는 도구이며, 실제 generated 후보가 없으면 합격 데이터를 선언하지 않는다.
  - public20 label은 synthetic prompt/judge/generated manifest target에는 쓰지 않는다.
    public20-only 모델 검증 artifact에서는 train target과 `val` metric에만 쓴다.
- Gate C manifest/model input equivalence 도구 `tools/analysis/check_manifest_model_input_equivalence.py`를 추가했다.
  - normalized candidate, supervised manifest, trainer loader가 같은 전체 `records` trajectory와 label/hash를 보는지 확인한다.
  - solver/runtime, model/tokenizer, public20 label, LLM/API는 import하거나 호출하지 않는다.
- 임의 deterministic fixture/smoke synthetic data는 논문 기반 생성 데이터가 아니므로 active surface에서 제거한다.
  accepted synthetic data는 Self-Instruct output-first generation, LLM-only filtering, Gate A/B/C를 통과한 후보만 의미한다.
- Self-Instruct 공식 출처 기준을 고정했다.
  - 논문: Wang et al. 2023 ACL Self-Instruct.
  - 공식 코드: `https://github.com/yizhongw/self-instruct`.
  - License: Apache-2.0.
  - 현재는 코드를 vendor하지 않고 [third_party/self_instruct/README.md](third_party/self_instruct/README.md)에 출처와 차용 범위를 문서화한다.
  - LLM 호출 없는 `parse_self_instruct_outputs`, ROUGE-L/exact/conflict dedup/filter, Gate C manifest/model input equivalence 도구를 먼저 두고, 이후 LLM API generation wrapper와 LLM-only judge filtering을 붙인다.
- v4.1 local shape repair evidence는 폐기 후보 evidence로 전환한다.
  - raw count: `1171`
  - manifest selected records: `1170`
  - labels: `pass=625`, `fail=545`
  - token bins: `513-1024=0`
  - char median: `5472.0`
  - record_count min: `1`
- 폐기 근거:
  <!-- Changed: summarize deprecated generator evidence through archive-only wording. -->
  <!-- Why: deleted datagen modules should not remain visible as active code targets in progress notes. -->
  - raw line 2는 `label=fail`이지만 마지막 response가 `EndSession SUCCESS`다.
  - 같은 row의 `records[25]`는 0-based 기준 `Set FAIL`이다.
  - 폐기 archive의 원천 통계상 fail 538개 중 440개가 마지막 `EndSession SUCCESS`로 끝난다.
  - 마지막 response 기준 과제라면 v4/v4.1은 학습 금지다.

## 현재 서버 상태

- 서버 repo: `/workspace/sinjeongmin_opal_verifier/repo`
- 마지막으로 알려진 baseline run:
  - `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2`
  - adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4`
  - 마지막 확인 시 epoch 1 checkpoint 존재
- 이후 public20 reference fetch 시점에는 서버 접속이 1회 성공했다.
- 기존 4B LoRA baseline 학습 완료 여부와 GPU 상태는 아직 재확인하지 않았다.
- 서버 접속 재시도나 상태 확인은 agent가 최소 10회 재시도 단위로 수행한다.

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
- active `tools/datagen/`은 Self-Instruct seed/candidate schema만 남긴다.
- `tools/eval/merge_adapters.py`는 active 호출/테스트 경로가 없는 adapter-soup 실험 도구라 제거했다.
- legacy spec/gap synthetic generator와 v4/v4.1 long trajectory generator는 active datagen에서 제거했다.
- 삭제 근거는 `docs/archive/legacy_datagen/README.md`와 v4/v4.1 폐기 archive에 남겼다.
- `tools/archive/legacy_rule_pipeline/` 실행 코드는 active repo에서 삭제하고, 필요한 근거만 `docs/archive/legacy/legacy_rule_pipeline_removed.md`에 문서형 archive로 남겼다.
- `docs/agent_handoff.md`는 README/PROGRESS/current docs와 함께 계속 갱신해야 하는 active 문서로 고정했다.
- Gate A/B/C 통과 뒤에만 `docs/samples/self_instruct_sample.md`를 만들고, generated raw trajectory 전체와 public20 raw sample 1개 전체를 생략 없이 포함한다.
- Gate B dimension comparison은 `tools/analysis/compare_public20_dimensions.py`로 수행한다.
- Gate C manifest/model input equivalence는 `tools/analysis/check_manifest_model_input_equivalence.py`로 수행한다.
- LLM output parser는 `tools/datagen/parse_self_instruct_outputs.py`로 수행한다. 이 도구는 raw LLM output을 candidate schema로 파싱/정규화하고 reject report를 만들 뿐, synthetic trajectory를 자체 생성하지 않는다.
- Self-Instruct dedup/filter는 `tools/analysis/dedup_self_instruct_candidates.py`로 수행한다. 이 도구는 ROUGE-L 0.7 near duplicate, exact duplicate, same-input conflicting label, public20 duplicate를 reject한다.
- public20 reference structure/profile audit pack을 `runs/self_instruct/public20_baseline/gate_a/`에 생성했다. 이 pack은 public20 검증 결과가 아니라 reference 구조 확인용이며, sample별 label을 노출하지 않고 state-transition/shape 메모용 빈 섹션만 제공한다.
- 모델 방법론 조사는 데이터 검증 이후 또는 병렬 보조로 진행한다. RAG/full FT/selective FT 구현은 관련 논문과 검증된 라이브러리/reference code를 따르며, synthetic 데이터의 질적/정량 검증을 중단하지 않는다.
- public20-only 모델 검증 기본 split은 stratified `16 train / 4 val`이고, val은 `pass 2 / fail 2`를 목표로 한다.
- 비교 후보는 Prompt-only/few-shot, Frozen RAG classifier, 0.9B full fine-tuning, 4B QLoRA/LoRA selective fine-tuning, RAFT-style RAG+SFT/QLoRA다.
- pure RAG 문제는 아니지만 rulebook/spec retrieval과 trajectory reasoning이 함께 필요한 문제이므로 RAFT-style retrieval-augmented classifier를 최종 유력 후보로 둔다.
- val macro-F1 상승이 멈추고 loss만 좋아지거나 fail recall이 떨어지면 no-go 또는 early stopping한다. leaderboard 제출은 내부 val 개선, qualitative error 감소, 제출물 차별점이 명확할 때만 1회 단위로 판단한다.
- Self-Instruct 공식 구현 계획은 [docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md](docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md)에 아카이빙했다.
