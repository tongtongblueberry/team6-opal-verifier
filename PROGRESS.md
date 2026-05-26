# Progress Log

- 최종 갱신: 2026-05-26 20:39 KST
<!-- Changed: mirror the current agent_handoff.md criteria in the progress header. -->
<!-- Why: progress readers need the active architecture, data, server, and branch/push rules before following older entries. -->
- 현재 원칙: runtime rule engine 금지, LLM-only architecture. rule engine, rule fallback, rule-id runtime은 사용하지 않는다.
- synthetic 데이터만 생성 데이터 검증 대상. Gate A/B/C/D 통과 후 sample 공개.
- public20은 reference 및 모델 train/val 기준. public20 test split 금지. hidden leaderboard가 test.
- public20은 synthetic 데이터 검증 대상이 아니다. public20 label은 synthetic generation/judge/generated manifest target으로 쓰지 않는다. public20-only 모델 후보 검증에서는 `train`/`val`만 쓰고, test는 leaderboard hidden 평가다.
- prompt-only/no-training baseline은 active plan에서 제거된 오해. public20 모델 검증은 실제 학습 후보만 사용.
- `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는 leaderboard hidden 평가다. public20 validation 결과를 test 결과로 기록하지 않는다.
- main agent는 직접 web 검색, SSH, 학습 실행, 파일 수정을 기본 작업 방식으로 삼지 않고 worker agent 결과를 종합해 최종 판단한다.
- 현재 서버 root: `/workspace/sinjeongmin_opal_verifier`
- 현재 로컬 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
<!-- Changed: record the only valid local repository root for this lane. -->
<!-- Why: workers must not confuse the adjacent team folder with the active worktree. -->
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team` 폴더는 현재 작업 repo가 아니며 수정/검증/commit/push 대상이 아니다.
- 현재 GitHub branch: `origin/sinjeongmin`
<!-- Changed: restore server_access as the server access authority. Why: the prior setup doc is no longer the server access source. -->
- 서버 접근 권위 문서는 [docs/archive/legacy/server_access.md](docs/archive/legacy/server_access.md); 서버 작업 agent는 먼저 읽고, 필요 시 최소 10회 재시도. 비밀번호/시크릿을 문서/로그에 복사하지 않음.
- branch/push 기준: origin `sinjeongmin`에 반영.
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

<!-- Changed: record completed epoch5, external probe, and batch_v2 Gate v2 outcomes. -->
<!-- Why: active progress must distinguish no-go results from conditional synthetic candidates. -->
<!-- Changed: pin current official-model evidence and avoid overreading seed11. -->
<!-- Why: one full FT seed result must not replace LoRA auxiliary evidence or trigger sample/submission decisions. -->
- full FT seed11/epoch 5 서버 run은 성공했지만 validation 기준 no-go다.
  - val accuracy `0.25`, fail recall `0.0`, pass recall `0.5`, confusion `TP=0 TN=1 FP=1 FN=2`
  - OOM 1회 후 `label_smoothing=0`으로 성공했다.
  - fail recall `0.0`이므로 epoch `10/20` 확장은 no-go다.
- LoRA seed11/29/47는 보조 비교 evidence로 유지한다. full FT seed11 결과 하나가 LoRA/QLoRA/selective
  후보를 대체하지 않는다.
- 현재 accepted synthetic `sample.md` 생성과 leaderboard 제출은 모두 no-go다.
- `runs/self_instruct/external_llm_probe/`는 judge accepted `1`, Gate A `pass`, Gate B `insufficient`, Gate C `no_go`다.
  `sample.md` 생성은 no-go다.
- `runs/self_instruct/gemini_batch_v2/`는 raw `12`, parser accepted/rejected `9/3`, dedup accepted/rejected `9/0`,
  judge accepted/rejected `9/0`, label `pass=6/fail=3`, record_count min/mean/max `8/13.0/18`이다.
  Gate v2 결과는 Gate A `pass`, Gate B `conditional pass`, Gate C `pass`, final `conditional`이다.
  strict full-pass 기준에서는 `sample.md` 생성 no-go이며, larger/balanced batch v3가 필요하다.
  raw run 산출물은 원문과 큰 파일을 포함할 수 있으므로 commit하지 않고 경로와 counts만 문서에 기록한다.
- 가장 큰 병목은 데이터 구조와 public/reference shape mismatch다.
- manifest builder의 records flatten 문제는 수정되어 전체 `records` trajectory가 하나의 supervised input으로 들어간다.
- public20 local reference를 확보했다.
  - input-only: `data/local/public20/public20_input.jsonl`
  - labels local-only: `data/local/public20/public20_labels.local.jsonl`
  - rows `20`, record_count min/mean/max `1/16.4/39`, label distribution `fail=10`, `pass=10`
  - public20은 `public20_reference`로만 두고 generated synthetic `train`, `val`, `test`와 섞지 않는다.
  - public20-only 모델 후보 검증은 20개를 `train`/`val`로만 분리한다. public20 `test` split은 만들지 않는다.
- public20 train/val split 도구 `tools/analysis/build_public20_train_val_split.py`를 추가했다.
  - seed `11`, `29`, `47` split artifact는 `runs/model_validation/public20_splits/`에 있다.
  - 각 split은 `16 train / 4 val`, val `pass=2/fail=2`, test `0`이다.
  - split rows는 `sample_id`, `input`, `label`, `split`만 포함하며 public20-only model validation 전용이다.
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
- Self-Instruct generation/judge dry-run wrapper를 추가했다.
  <!-- Changed: record spec-grounded prompt/request redesign. -->
  <!-- Why: ungrounded Gemini/Codex text is not valid synthetic candidate evidence. -->
  - `tools/datagen/run_self_instruct_generation.py`는 공식 output-first classification prompt payload와 metadata만 쓰며,
    `docs/legacy_spec_rules.md`의 rule card/source-span을 payload에 포함한다.
  - raw candidate는 `spec_grounding` source span 없이는 parser/judge 경로에서 accepted synthetic 후보가 아니다.
  - `tools/analysis/filter_self_instruct_judge.py`는 LLM-only judge prompt payload와 외부 judge result parser만 제공하고,
    required spec grounding, source-span support, state-transition consistency, manifest-loader compatibility를 judge boolean으로 요구한다.
  - 두 도구 모두 기본 실행에서 LLM/API를 호출하지 않고, synthetic trajectory를 자체 생성하지 않는다.
  <!-- Changed: record provider-gated LLM runner skip state. -->
  <!-- Why: runner implementation alone is not generated-data evidence without provider env and raw output. -->
  - `tools/datagen/self_instruct_llm_runner.py`를 추가했지만 현재 `OPENAI_API_KEY`/`GEMINI_API_KEY` env가 없어서
    실제 generation은 `skipped_missing_env`로 skip 상태다. raw output JSONL이 없으므로
    `sample.md` 생성과 Gate A/B/C pass 선언은 no-go다.
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
- active `tools/datagen/`은 Self-Instruct seed/candidate schema, dry-run generation request wrapper, raw output parser만 남긴다.
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
- Self-Instruct generation request는 `tools/datagen/run_self_instruct_generation.py`로 생성한다. 이 도구는 dry-run payload/metadata writer이며, 생성 데이터 자체나 sample.md를 만들지 않는다.
- Self-Instruct judge filter는 `tools/analysis/filter_self_instruct_judge.py`로 수행한다. 이 도구는 judge payload를 만들고 외부 judge JSON 결과를 accepted/rejected로 분리한다.
- public20 reference structure/profile audit pack을 `runs/self_instruct/public20_baseline/gate_a/`에 생성했다. 이 pack은 public20 검증 결과가 아니라 reference 구조 확인용이며, sample별 label을 노출하지 않고 state-transition/shape 메모용 빈 섹션만 제공한다.
- 모델 방법론 조사는 데이터 검증 이후 또는 병렬 보조로 진행한다. RAG/full FT/selective FT 구현은 관련 논문과 검증된 라이브러리/reference code를 따르며, synthetic 데이터의 질적/정량 검증을 중단하지 않는다.
  <!-- Changed: correct public20 model validation plan to training-based candidates only. -->
  <!-- Why: public20-only model verification must actually train on public20 train split. -->
- public20-only 모델 검증 기본 split은 stratified `16 train / 4 val`이고, val은 `pass 2 / fail 2`를 목표로 한다.
- deterministic split 산출물은 `runs/model_validation/public20_splits/split_seed_11`, `split_seed_29`, `split_seed_47`에 생성했다.
- 모델 학습 후보 5개는 다음으로 고정한다: 0.9B full FT `5/10/20` epoch patience `2`, 0.9B full FT + retrieved rulebook/spec context `5/10/20` epoch patience `2`, 4B LoRA/QLoRA selective FT `3/5/10` epoch patience `1-2`, 4B LoRA/QLoRA + retrieved context `3/5/10` epoch patience `1-2`, RAFT-style retrieval-augmented SFT/QLoRA public20-only `1/3/5` smoke/overfit check.
- RAFT-style 후보는 synthetic Gate A/B/C 통과 데이터가 생기면 epoch `3/5/10`으로 확장한다.
  <!-- Changed: record the standalone full-model evaluator for public20 val metrics. -->
  <!-- Why: full FT checkpoints cannot be evaluated with the LoRA adapter-only script. -->
- Full/selective FT standalone checkpoint 평가는 `tools/eval/eval_manifest_full_model.py`로 수행한다.
  이 도구는 `train_manifest_full.build_messages` prompt contract를 사용하고 full model path를 직접 로드해
  `val` split의 next-token `pass`/`fail` logprob을 비교한다. metric은 accuracy, macro-F1,
  fail recall, pass recall, confusion matrix, per-sample prediction/logprob이다. epoch별
  report에서 val macro-F1이 정체되고 fail recall이 떨어지면 no-go 또는 patience 중단으로 판단한다.
- pure RAG 문제는 아니지만 rulebook/spec retrieval과 trajectory reasoning이 함께 필요한 문제다. 따라서 retrieval만 하는 비학습 대체물이 아니라 retrieval + fine-tuning/RAFT-style 학습을 최종 방향으로 둔다.
- val macro-F1 상승이 멈추고 loss만 좋아지거나 fail recall이 떨어지면 no-go 또는 early stopping한다. leaderboard 제출은 내부 val 개선, qualitative error 감소, 제출물 차별점이 명확할 때만 1회 단위로 판단한다.
- Self-Instruct 공식 구현 계획은 [docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md](docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md)에 아카이빙했다.
