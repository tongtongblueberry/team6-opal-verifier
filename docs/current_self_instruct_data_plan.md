<!-- Changed: add the active Self-Instruct data-generation plan and mandatory data-validation gate order. -->
<!-- Why: v4/v4.1 generators are deprecated because their labels can target an intermediate response instead of the final response, and new generated data must pass qualitative and model-path checks before submission. -->

# Current Self-Instruct Data Plan

## 목적과 비범위

<!-- Changed: define the active replacement scope before code implementation. -->
<!-- Why: the next pipeline must not reuse deprecated v4/v4.1 generation or rule-engine architecture. -->

이 문서는 Self-Instruct 기반 새 데이터 생성 파이프라인의 active spec이다. 목표는
Self-Instruct 하나를 제대로 구현해 `final response` 판단용 supervised 데이터를
만들고, 학습 전 품질 gate와 평가 protocol을 고정하는 것이다.

<!-- Changed: lock the generation plan to the official Self-Instruct paper/code source. -->
<!-- Why: previous ad-hoc fixture generation drifted from the user-requested paper-backed data pipeline. -->

공식 기준은 다음이다.

- 논문: Wang et al. 2023 ACL Self-Instruct.
- 공식 코드: `https://github.com/yizhongw/self-instruct`.
- License: Apache-2.0.
- repo 내 문서 기준: `third_party/self_instruct/README.md`.
- research archive: `docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md`.

현재 단계에서는 공식 코드를 vendor하지 않는다. 코드 차용이 필요하면 commit hash, license
notice, 수정 범위, 검증 결과를 별도 기록한 뒤 진행한다. 공식 Self-Instruct 절차 없는
ad-hoc generator는 active `tools/datagen/`에 둘 수 없다.

<!-- Changed: mirror the latest active architecture and public20/model criteria. -->
<!-- Why: the Self-Instruct plan must not allow runtime rules, public20 test splits, or prompt-only/no-training baselines. -->

<!-- Changed: restore server_access as the server access authority. Why: the prior setup doc is no longer the server access source. -->
서버 접근 권위 문서는 [docs/archive/legacy/server_access.md](archive/legacy/server_access.md); 서버 작업 agent는 먼저 읽고, 필요 시 최소 10회 재시도. 비밀번호/시크릿을 문서/로그에 복사하지 않음.
branch/push 기준: origin `sinjeongmin`에 반영.

비범위는 다음과 같다.

- v4/v4.1 deprecated generator를 학습 데이터 생성에 재사용하지 않는다.
- spec/gap synthetic generator를 새 Self-Instruct 데이터 생성 경로에 재사용하지 않는다.
- runtime rule engine 금지, LLM-only architecture.
- rule engine, rule fallback, rule-id prompt, rule-derived label을 사용하지 않는다.
- invariant checker는 데이터 품질 gate다. runtime architecture, solver fallback,
  rule engine, deterministic verifier로 사용하지 않는다.
- 데이터 검증 대상은 public20이 아니라 우리가 생성한 synthetic 데이터다. public20은
  이미 주어진 기준 입력이므로 reference structure/profile 비교와 public20-only 모델
  후보 검증에만 사용한다.
- public 20 label은 synthetic generation prompt, judge prompt, generated training
  manifest target으로 쓰지 않는다. Gate B aggregate pass/fail distribution 비교와
  별도 public20-only model-validation artifact의 train target/`val` metric 계산에만 사용한다.
- synthetic 데이터 검증 절차가 끝난 뒤에는 generated dataset을 반드시 `train`, `val`,
  `test`, `public20_reference`로 분리한다. `public20_reference`는 shape/profile/reference와
  public20-only 모델 후보 검증용 local reference이며 generated supervised manifest split에
  들어가면 안 된다.
- public20-only 모델 후보 검증에서는 public20 20개를 `train`/`val`로만 나눈다.
  public20 `test` split은 만들지 않는다. test는 leaderboard hidden 평가다.
- 기본 split은 stratified `16 train / 4 val`이고, val은 `pass 2 / fail 2`를 목표로 한다.
  여러 split을 돌릴 수는 있지만 모두 validation이며 test라고 부르지 않는다.

<!-- Changed: document the prompt-grounding failure before the next generation request is used. -->
<!-- Why: prior Gemini/Codex-style text generation was not synthetic candidate evidence without spec-rule source spans. -->

[Original Text/Data] 기존 `tools/datagen/run_self_instruct_generation.py` prompt는
`seed_profile_context`와 output-first 구조 조건만 payload에 넣었고,
`docs/legacy_spec_rules.md`의 `TCG/Opal SSD Specification Rules for Training Data
Generation` rule body, source path, line source-span을 넣지 않았다. 또한
`runs/self_instruct/gemini_batch_v3/gemini_prompt_request_000.txt`는 현재 worktree에
없고 `git log --all -- runs/self_instruct/gemini_batch_v3/gemini_prompt_request_000.txt`
에서도 추적 기록을 찾지 못했다. → [Exact Interpretation] 이전 request는 final response
targeting과 shape는 요구했지만, 어떤 spec rule에서 label이 entail되는지 generator와 judge에
검증 가능한 입력으로 제공하지 못했다. `gemini_batch_v3` prompt 원문이 없으므로 복구하지
않고, "source-span이 없으면 비교 기준과 acceptance 기준을 증명할 수 없다"는 no-go 근거로만
남긴다. → [Detailed Explanation/Example] 예를 들어 final `Set INVALID_PARAMETER`가
label `pass`인지 판단하려면 `docs/legacy_spec_rules.md`의 해당 Set rule `CONDITION`,
`EXPECTED_STATUS`, `IF_VIOLATED`, line span을 후보가 인용해야 한다. 단순히 "Set failed so
fail/pass"라고 쓴 Gemini/Codex text는 synthetic 후보가 아니라 draft다. 이 비교 기준이
필요한 이유는 Gate A가 사람이 state transition과 cited span을 대조하고, Gate B/C가 그
후보를 public20 profile 및 manifest/model input path로 연결할 때 provenance 손실 여부를
확인해야 하기 때문이다.

## 필수 검증 gate 순서

<!-- Changed: make Gate A-D the mandatory order for generated-data validation. -->
<!-- Why: generated data must be checked qualitatively, distributionally, and through the model input path before any leaderboard submission. -->

새 generated data는 아래 순서를 건너뛰면 안 된다. 앞 gate가 fail이면 뒤 gate를 실행하지
않고 no-go archive를 작성한다.

1. Gate A: qualitative sampling state-transition audit
   - accepted pool 일부를 직접 sampling한다.
   - 검수자는 sample의 records를 처음부터 끝까지 순서대로 읽고, 필요한 session state를
     사람이 전이해 보며 final response가 generated label과 질적으로 맞는지 확인한다.
   - 검수자는 `spec_grounding[].source_span`이 `docs/legacy_spec_rules.md`의 실제
     rule body를 가리키는지 확인하고, cited `CONDITION`/`EXPECTED_STATUS`와 final
     response가 맞지 않으면 reject한다.
   - 이 state-transition audit는 데이터 품질 검수다. rule engine, runtime architecture,
     deterministic verifier, solver fallback이 아니며 `src/solver.py`나 package runtime에
     import하면 안 된다.

2. Gate B: public20 reference dimension/schema/pass-fail distribution comparison
   - Gate A를 통과한 generated manifest 후보와 public20 reference의 schema,
     평균 dimension vector, pass/fail 분포를 비교한다.
   - public20 자체를 검증하는 단계가 아니다.
   - 현재 확보한 public20 기준 facts는 rows `20`, record_count min/mean/max
     `1/16.4/39`, label 분포 `fail=10`, `pass=10`이다.
   - dimension vector는 최소한 `record_count`, method sequence length,
     final method/status, input char/token count, return value count를 포함한다.
   - public 20 row-level label은 synthetic 학습 row로 복사하지 않고, aggregate no-go
     판단과 public20-only `val` metric 계산에만 사용한다.
   - active 도구는 `tools/analysis/compare_public20_dimensions.py`다. 이 도구는
     public20 label을 local aggregate JSON으로만 선택적으로 받아 distribution report에
     기록한다.

3. Gate C: manifest/model input path equivalence check
   - manifest validation에서 통과한 동일 파일이 training loader와 실제 model first-forward
     입력에서도 같은 schema, sample id/hash, label mapping, dimension summary로 처리되는지
     확인한다.
   - `spec_grounding`은 candidate/judge/Gate A audit metadata로 보존하되, model input은
     `{"records": records}` trajectory만 사용해야 한다.
   - loader가 row를 조용히 drop/resample/relabel하거나 deprecated source를 섞으면 fail이다.

4. Gate D: leaderboard submission only after gates pass
   - Gate A, Gate B, Gate C가 모두 pass이고 package/runtime/secret/no-rule gate도 pass일 때만
     leaderboard 제출을 go로 판단한다.
   - 제출 전에는 Korean archive record에 gate artifact path, pass/fail 근거, known risk,
     no-go 대안을 남긴다.

## raw sample 공개 정책

<!-- Changed: define when generated raw data can be shown as accepted data. -->
<!-- Why: generated data must not be presented as usable training evidence before qualitative, distributional, and model-input gates pass. -->

<!-- Changed: require Gate A/B/C/D before sample publication. -->
<!-- Why: generated raw data must not be exposed as accepted sample before the full gate sequence. -->

synthetic 데이터만 생성 데이터 검증 대상. Gate A/B/C/D 통과 후 sample 공개.
Self-Instruct synthetic data가 Gate A/B/C/D를 모두 통과하면
`docs/samples/self_instruct_sample.md`를 작성한다. 이 파일에는 다음을 모두 포함한다.

- raw trajectory 전체
- label
- target
- primary evidence
- spec grounding source span
- profile
- public20 raw sample 1개 전체
- Gate A audit summary
- Gate B comparison summary
- Gate C manifest/model-input summary
- Gate D leaderboard submission summary

Gate A/B/C/D 전에는 raw synthetic sample을 "합격 데이터"로 제시하지 않는다. 이 단계의
sample은 검수 대기 또는 reject/no-go evidence로만 기록한다.

## data partition invariant

<!-- Changed: require explicit train/val/test/public20_reference separation after validation. -->
<!-- Why: public20 must remain a reference/evaluation set, while generated data is the only supervised training source. -->

Gate A/B/C를 통과한 뒤 generated synthetic manifest를 만들 때 데이터 partition은 다음
이름으로 고정한다.

- `train`: Self-Instruct generated accepted data의 학습 split.
- `val`: threshold, calibration, early stopping, ablation 선택에 쓰는 generated validation split.
- `test`: synthetic 데이터의 최종 내부 holdout 평가에 쓰는 generated test split.
- `public20_reference`: public20 input-only shape/profile/reference 및 public20-only 모델
  `train`/`val` 후보 검증에 쓰는 별도 local reference.

별도 모델 후보 검증 protocol:

- public20-only 모델 후보 검증은 public20 20개를 `train`/`val`로만 나눠 수행한다.
- 이 검증의 `val`은 후보 선택, threshold/calibration, ablation 선택용 내부 검증이다.
- 이 검증의 `test`는 public20에서 만들지 않는다. 최종 test는 leaderboard hidden 평가다.
- public20-only train/val 결과가 좋아도 leaderboard 제출은 하루 5회 제한과 Gate D 조건을
  만족할 때만 1회 단위로 판단한다.

금지 사항:

- public20 row를 `train`, `val`, `test` supervised manifest에 복사하기.
- public20 label을 synthetic generation prompt, judge prompt, generated synthetic manifest target으로 쓰기.
- generated split과 public20 reference를 같은 path나 같은 manifest split 이름으로 섞기.
- public20을 `train`/`val`/`test`로 3분할해 public20 test를 만드는 것.
- Gate A/B/C 통과 전 generated raw data를 training-ready split으로 선언하기.

## public20 local reference facts

<!-- Changed: record the fetched public20 local reference facts used by Gate B. -->
<!-- Why: Gate B must compare generated data against the actual local public20 reference, not memory or stale archive notes. -->

현재 로컬 reference:

- input-only: `data/local/public20/public20_input.jsonl`
- labels local-only: `data/local/public20/public20_labels.local.jsonl`
- input rows: `20`
- label rows: `20`
- input 내 label/gold/answer 계열 필드: 없음
- record_count min/mean/max: `1 / 16.4 / 39`
- label distribution: `fail=10`, `pass=10`

`public20_labels.local.jsonl`은 aggregate distribution 비교와 별도 public20-only
model-validation artifact의 train target/`val` metric 계산에만 쓴다.

## 모델 후보 검증 병렬 원칙

<!-- Changed: separate model-method validation from synthetic-data validation. -->
<!-- Why: public20 can be used for small train/val model comparison, but it must not replace generated-data quality gates or create a fake test split. -->

RAG, full fine-tuning, selective fine-tuning 후보 조사는 데이터 검증 이후 또는 병렬 보조로
진행할 수 있다. 단, 모델 검증이 synthetic 데이터 검증 자원을 전부 가져가면 안 된다.

- public20-only 모델 후보 검증은 public20 20개를 `train`/`val`로만 분리한다.
- `val`은 후보 선택, threshold/calibration, ablation 선택용 내부 검증이다.
- `test`는 leaderboard hidden 평가이며 public20에서 따로 만들지 않는다.
- 기본 split은 stratified `16 train / 4 val`이고, val은 `pass 2 / fail 2`를 목표로 한다.
- 여러 split을 돌릴 수는 있지만 모두 validation이며 test라고 부르지 않는다.
- 최종 제출 후보가 정해지면 선택된 recipe로 public20 20개 전체를 학습에 쓸지 별도 결정한다.
- RAG가 맞는지, FT가 맞는지는 유사 문제 논문과 검증된 코드 기반 구현을 보고 결정한다.
- 모델 코드는 가능하면 검증된 라이브러리와 reference implementation을 사용하고, 새 trainer를
  처음부터 크게 작성하지 않는다.
- 이 작업은 Gate A synthetic state-transition audit, Gate B public20 reference dimension
  comparison, Gate C model-input path equivalence를 대체하지 않는다.

### 모델 후보와 중단 기준

[EXTERNAL KNOWLEDGE] Zhang, T., Patil, S. G., Jain, N., Shen, S., Zaharia, M.,
Stoica, I., & Gonzalez, J. E. (2024). *RAFT: Adapting Language Model to Domain
Specific RAG*. arXiv. https://arxiv.org/abs/2403.10131

[EXTERNAL KNOWLEDGE] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin,
V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., &
Kiela, D. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP
Tasks*. In *Advances in Neural Information Processing Systems, 33*.

[EXTERNAL KNOWLEDGE] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L.
(2023). *QLoRA: Efficient Finetuning of Quantized LLMs*. In *Advances in Neural
Information Processing Systems, 36*.

<!-- Changed: replace comparison-only candidates with the active five training candidates. -->
<!-- Why: the immediate model validation request is to train on public20 train split because verified synthetic data is not available yet. -->
prompt-only/no-training baseline은 active plan에서 제거된 오해. public20 모델 검증은 실제 학습 후보만 사용.
public20은 reference 및 모델 train/val 기준. public20 test split 금지. hidden leaderboard가 test.
모델 후보는 public20 `16 train / 4 val` split에서 실제 학습을 수행하는 다음 5개로 고정한다.

1. 0.9B full fine-tuning
   - public20 train 16개만 사용한다.
   - 12GB 제출 한계를 활용하는 후보로 둔다.
   - epoch 후보는 `5`, `10`, `20`이고 patience는 `2`다.

2. 0.9B full fine-tuning + retrieved rulebook/spec context
   - 0.9B full FT 입력에 retrieved rulebook/spec context를 함께 제공한다.
   - epoch 후보는 `5`, `10`, `20`이고 patience는 `2`다.
   - retrieval이 weight-only full FT보다 도움이 되는지 비교한다.

3. 4B LoRA/QLoRA selective fine-tuning
   - PEFT/Transformers 계열 검증 코드와 reference implementation을 우선 사용한다.
   - epoch 후보는 `3`, `5`, `10`이고 patience는 `1-2`다.

4. 4B LoRA/QLoRA + retrieved rulebook/spec context
   - 4B selective tuning 입력에 retrieved rulebook/spec context를 함께 제공한다.
   - epoch 후보는 `3`, `5`, `10`이고 patience는 `1-2`다.
   - retrieval이 selective FT의 rulebook coverage를 보완하는지 본다.

5. RAFT-style retrieval-augmented SFT/QLoRA
   - trajectory와 retrieved spec chunks를 함께 넣고, retrieved evidence를 사용하는 방식으로 학습한다.
   - public20-only에서는 epoch `1`, `3`, `5`만 smoke/overfit check로 수행한다.
   - synthetic Gate A/B/C 통과 데이터가 생기면 epoch `3`, `5`, `10`으로 확장한다.

이 문제는 pure RAG 문제는 아니다. rulebook/spec이 커서 weight에 모두 암기시키기 어렵고,
trajectory state transition은 단순 검색만으로 해결되지 않는다. 따라서 retrieval된 규칙,
trajectory reasoning, final response classification을 함께 처리하는 문제로 본다.
최종 후보는 retrieval만 하는 비학습 대체물이 아니라 retrieval + fine-tuning/RAFT-style
학습 조합이 맞다.

학습 중단 기준은 다음이다.

- val macro-F1 상승이 멈추고 loss만 좋아지면 과적합으로 본다.
- fail recall이 떨어지면 no-go다.
- val 4개는 작으므로 단일 split 점수만 믿지 않고 여러 train/val split 평균과 오류 사례를 같이 본다.
- leaderboard는 내부 val 개선, qualitative error 감소, 제출물 차별점이 명확할 때만 1회 사용한다.

<!-- Changed: define the evaluator used by full/selective FT public20 validation. -->
<!-- Why: standalone full FT checkpoints must not be evaluated with the LoRA adapter-only evaluator. -->
Full/selective FT standalone checkpoint 평가는 `tools/eval/eval_manifest_full_model.py`로 수행한다.
입력은 train/val 포함 manifest 또는 val jsonl, full model directory/base model path, `--split val`이다.
이 도구는 `train_manifest_full.build_messages`와 같은 prompt contract를 사용하고,
full model을 직접 로드해 next-token `pass`/`fail` logprob을 비교한다. report는 accuracy,
macro-F1, fail recall, pass recall, confusion matrix, per-sample prediction/logprob을 포함한다.
epoch `5/10/20` 같은 후보 비교에서는 각 epoch/checkpoint별 이 report를 만들고, val macro-F1이
정체되거나 fail recall이 하락하면 patience/no-go 기준으로 중단한다.

<!-- Changed: add the implemented public20 train/val split builder and artifacts. -->
<!-- Why: public20-only model validation needs deterministic train/val inputs without inventing a public20 test split. -->
public20 train/val split 생성은 `tools/analysis/build_public20_train_val_split.py`가 담당한다.
현재 seed `11`, `29`, `47` split은 `runs/model_validation/public20_splits/` 아래에 있고,
각 split은 `train.jsonl`, `val.jsonl`, `split_report.json`, `split_report.md`를 포함한다.
row schema는 `sample_id`, `input`, `label`, `split`이며, 이 artifact는 public20-only
model validation 전용이다. synthetic generation prompt, synthetic judge prompt, generated
synthetic manifest target으로 쓰지 않는다.

## 선택 논문과 citation

<!-- Changed: select one paper as the implementation target rather than keeping a paper list. -->
<!-- Why: the user requested a concrete implementation/evaluation protocol, not a literature survey. -->

[EXTERNAL KNOWLEDGE] Wang, Y., Kordi, Y., Mishra, S., Liu, A., Smith, N. A.,
Khashabi, D., & Hajishirzi, H. (2023). *Self-Instruct: Aligning language
models with self-generated instructions*. In A. Rogers, J. Boyd-Graber, &
N. Okazaki (Eds.), *Proceedings of the 61st Annual Meeting of the Association
for Computational Linguistics (Volume 1: Long Papers)* (pp. 13484-13508).
Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.754

채택 이유는 하나다. Self-Instruct는 seed task에서 instruction, input, output을
LLM이 생성하고 invalid 또는 near-duplicate sample을 필터링한 뒤 원 모델을
finetune하는 pipeline이다. 이 repo에서는 일반 instruction tuning이 아니라
Opal trajectory의 `final response` pass/fail 판단 데이터 생성으로 좁혀 적용한다.

공식 pipeline 대응은 다음처럼 고정한다.

- Instruction generation: Opal verification case family generation으로 축소한다.
- Classification identification: 우리 과제는 항상 `pass`/`fail`이므로 고정 `true`다.
- Classification instance generation: output-first로 target label과 final verdict step을 먼저 만든다.
- Filtering: ROUGE-L near duplicate, exact duplicate, conflicting label/input, invalid output을 제거한다.
- Quality audit: accepted synthetic sample을 label별로 sampling해 state-transition audit한다.
- Data size/data quality ablation: `200/500/1k/2k/4k` 후보와 stronger judge regeneration variant를 비교한다.

## 현재 repo 구조 감사

<!-- Changed: record the audited local structure that the plan builds on. -->
<!-- Why: implementation files must attach to active tools without reviving archived code. -->

[Original Text/Data] 현재 active `tools/datagen/`에는 `self_instruct_seed_schema.py`,
`self_instruct_candidate_schema.py`, `parse_self_instruct_outputs.py`, `__init__.py`만 둔다.
→ [Exact Interpretation] active datagen은 public20 input-only seed contract, generated
candidate contract, raw LLM output parser만 담당한다. → [Detailed Explanation/Example]
ad-hoc fixture/smoke generated data is not accepted synthetic data. real LLM generation을
붙일 때도 v4/v4.1, spec/gap generator, 임의 deterministic fixture generator를 import하거나
active surface에 두면 안 된다.

[Original Text/Data] v4/v4.1과 spec/gap synthetic generator 정리 근거는
`docs/archive/legacy_datagen/README.md`와 v4/v4.1 폐기 archive에 둔다. →
[Exact Interpretation] 실패 원인과 과거 판단은 archive evidence로 남기되, active
CLI/import surface에서는 제거한다. → [Detailed Explanation/Example] v4/v4.1의
`_endsession()` append 패턴처럼 intermediate failure 뒤 final `EndSession SUCCESS`를
붙이는 구조는 새 manifest에 들어오면 label target을 오염시킨다.

[Original Text/Data] `tools/analysis/`에는 manifest/audit 도구와
`self_instruct_invariants.py`, `audit_self_instruct_quality.py`,
`compare_public20_dimensions.py`, `check_manifest_model_input_equivalence.py`,
`dedup_self_instruct_candidates.py`가 있다. → [Exact Interpretation] 현재 분석 계층은
manifest construction, hard gate, Gate A/B/C, duplicate/conflict filtering을 담당한다.
→ [Detailed Explanation/Example] Self-Instruct judge filtering과 final-response invariant
검사는 `tools/analysis/`에 추가하는 것이 책임 경계에 맞다.

[Original Text/Data] `tests/`는 `unittest` 기반이고 각 파일 상단에 Changed/Why
comment를 둔다. → [Exact Interpretation] 새 scaffold도 `unittest`와 top-level
change comment를 따라야 한다. → [Detailed Explanation/Example] 구현 전 테스트는
없는 모듈을 import-time failure로 만들지 말고 conditional skip으로 둔다.

## docs/tools 정리 기준

<!-- Changed: define what remains active, what moves to archive, and what should be deleted. -->
<!-- Why: repeated use of failed generators or stale docs must be blocked while preserving audit evidence. -->

active에 남길 것은 다음 조건을 모두 만족해야 한다.

- 현재 실행 순서 또는 다음 구현 순서를 직접 결정한다.
- default CLI 또는 import path가 현재 LLM-only data/training/package pipeline에 안전하게 연결된다.
- secret, token, password, server-only path를 출력하거나 저장하지 않는다.
- deprecated v4/v4.1 또는 spec/gap source를 active datagen default execution에서 호출하지 않는다.

archive할 것은 다음이다.

- 날짜가 붙은 실행 기록, 제출 시도, no-go 판단, 실패 원인 분석.
- 재현 가치가 있는 legacy 판단 근거. legacy executable code는 active `tools/` namespace에
  남기지 않고, 필요한 삭제 범위와 폐기 사유만 `docs/archive/legacy/`에 문서로 보존한다.
- v4/v4.1 같은 실패 코드와 spec/gap synthetic generator는 archive evidence와 재현
  근거만 남긴다. active `tools/datagen/`에는 두지 않으며, 학습 manifest와 제출 판단의
  default path에서는 0개여야 한다.

삭제할 것은 다음이다.

- secret, token, password, credential이 들어간 파일 또는 로그. 이런 파일은 archive하지 않는다.
- 동일 내용을 중복한 stale docs 중 최신 active/archive 문서로 완전히 대체된 파일.
- 재현 가능한 tmp output, partial generated data, 캐시성 산출물 중 no-go 근거로 쓰이지 않는 파일.
- ad-hoc fixture/smoke generated data. 논문 기반 생성 방법이나 검증된 코드 기반이 아니므로
  학습, 검증, leaderboard 제출 근거로 쓰지 않고 active surface에서 제거한다.

정리 후에는 active doc이 archive evidence를 링크해야 한다. 실패 코드나 실패 데이터를
다시 default 실행 경로에 연결하는 변경은 Gate A 이전 단계에서 fail로 본다.

Active docs update set은 `README.md`, `PROGRESS.md`, `docs/README.md`,
`docs/current_task.md`, `docs/current_self_instruct_data_plan.md`,
`docs/agent_handoff.md`, `docs/samples/README.md`다. 데이터 생성, 검증 gate, 학습,
제출, sample 공개, cleanup 기준을 바꾸는 작업은 이 문서 묶음을 함께 점검한다.

## 필요한 파일 제안

<!-- Changed: propose the minimum file set for the new pipeline. -->
<!-- Why: implementation should be small, auditable, and separated from training/runtime code. -->

1. `tools/datagen/self_instruct_seed_schema.py`
   - seed 20 input을 canonical JSON으로 정규화한다.
   - public label을 읽거나 출력하지 않는다.
   - `label`, `gold_label`, `expected_label`, `answer` 등 label-like field는
     default에서 명시적으로 reject한다. audit-only ingest가 필요하면 별도 옵션으로
     허용하되 output에는 쓰지 않는다.
   - public20-only 모델 검증용 `val` split exclusion list를 만들 수 있어야 한다.

2. `tools/datagen/self_instruct_candidate_schema.py`
   - label-bearing generated candidate를 canonical JSON으로 정규화한다.
   - `label`, `target`, `primary_evidence`, `spec_grounding`은 candidate schema에만 존재한다.
   - `spec_grounding`은 `docs/legacy_spec_rules.md` source-span provenance이며
     manifest/model input text에 들어가지 않는다.
   - `check_final_response_label_invariant()`는 candidate schema에서만 적용한다.

3. `tools/datagen/parse_self_instruct_outputs.py`
   - 공식 output-first response를 candidate schema로 파싱한다.
   - 아직 LLM API를 호출하지 않는다.
   - label, target, primary evidence, records, spec grounding을 명시하고 candidate invariant로 검증한다.
   - malformed output, missing final target, missing `spec_grounding.source_span`, label-like leakage는 reject한다.

4. `tools/analysis/dedup_self_instruct_candidates.py`
   - 공식 filtering 원칙을 반영해 ROUGE-L near duplicate, exact duplicate, same input conflicting label을 제거한다.
   - public20 exact/near duplicate와 archived verifier/rule marker도 reject한다.
   - LLM 호출 없이 local JSONL filtering과 report만 수행한다.

5. `tools/analysis/check_manifest_model_input_equivalence.py`
   - raw candidate, normalized candidate, manifest, training loader, first-forward input이 같은 trajectory 단위인지 검증한다.
   - Gate C 전용이며 trainer/eval/submission prompt mismatch를 no-go로 기록한다.

6. `tools/analysis/filter_self_instruct_judge.py`
   - generated candidate에 대한 LLM-only judge prompt payload를 만든다.
   - 외부 judge result JSONL을 accept/reject로 파싱한다.
   - judge prompt에는 candidate trajectory, final response, generated label, `spec_grounding`
     source-span metadata만 넣는다.
   - judge는 `has_required_spec_grounding`, `is_source_span_supported`,
     `is_state_transition_consistent`, `is_manifest_loader_compatible`를 JSON boolean으로
     답해야 한다.
   - judge prompt에는 runtime rule engine, rule-derived label, public label,
     archived verifier output을 넣지 않는다.
   - judge는 offline data filter이며 runtime solver나 package inference path가 아니다.

7. `tools/datagen/run_self_instruct_generation.py`
   - Self-Instruct output-first classification prompt payload와 request metadata를 생성하는 dry-run wrapper다.
   - `docs/legacy_spec_rules.md`를 읽어 `rule_ref`, `source_path`, `source_span`,
     `condition`, `expected_status`를 가진 source-span rule card를 payload에 넣는다.
   - 기본 실행은 LLM/API를 호출하지 않고 synthetic trajectory도 자체 생성하지 않는다.
   - `--execute`는 현재 API 호출 없이 실패한다.
   - LLM API key, server token, secret 값을 log 또는 output JSON에 쓰지 않는다.
   - 임의 deterministic fixture/smoke mode는 허용하지 않는다.
   - 공식 Self-Instruct prompt/metadata 계약, LLM-only judge filtering, Gate A/B/C 산출물을 함께 남기는
     후보만 active implementation으로 둘 수 있다.

8. `tools/analysis/self_instruct_invariants.py`
   - final-response label invariant를 검사한다.
   - 이 모듈은 데이터 품질 gate 전용이다. `src/solver.py`, inference runtime,
     package script에서 import하면 안 된다.

9. `tools/analysis/audit_self_instruct_quality.py`
   - accepted pool에서 200-sample quality audit pack과 report를 만든다.
   - manifest validation과 중복되지 않는 Self-Instruct 전용 gate를 기록한다.

10. `tools/analysis/compare_public20_dimensions.py`
   - Gate B에서 public20 reference profile과 generated candidate profile을 비교한다.
   - 평균 record_count 차이, final_status blank, unknown method/status, schema warning을
     no-go warning으로 보고하되, public20 label은 local aggregate distribution으로만 쓴다.

11. `tools/analysis/build_public20_train_val_split.py`
   - public20-only 모델 후보 검증용 deterministic `train`/`val` split을 만든다.
   - 기본 seed는 `11`, `29`, `47`이며 각 split은 `16 train / 4 val`, val `pass=2/fail=2`다.
   - public20 `test` split은 만들지 않는다. 최종 test는 leaderboard hidden 평가다.
   - 출력 row는 `sample_id`, `input`, `label`, `split`만 포함한다.
   - public20 label은 이 artifact 안에서만 train target과 val metric으로 사용한다.

12. `tools/eval/eval_self_instruct_public20_train_val.py`
   - public20-only train/val model validation을 실행한다.
   - public labels는 validation metric 계산에만 사용한다.
   - public20 train labels는 이 별도 public20-only validation artifact 안에서만 train target으로 쓴다.
   - public20 `test` split은 만들지 않는다. 최종 test는 leaderboard hidden 평가다.
   - fold-held `val` seed input은 해당 fold의 public20-only training input과
     generation seed/prompt/training data에서 제외한다.

13. `tools/eval/eval_manifest_full_model.py`
   - full/selective FT standalone model path를 직접 로드해 manifest `val` split을 평가한다.
   - LoRA adapter 전용 evaluator가 아니며 `adapter_path`를 받지 않는다.
   - `train_manifest_full.build_messages` prompt contract를 기준으로 next-token `pass`/`fail` logprob을 비교한다.
   - public20-only 모델 검증에서는 train target과 val metric artifact 안에서만 public20 label을 사용한다.

14. `tests/test_self_instruct_final_response_invariant.py`
   - invariant checker 구현 전 API와 실패 사례를 고정한다.
   - v4/v4.1의 핵심 실패 모드인 "중간 실패 뒤 성공 final response"를 회귀 테스트로 둔다.

## seed 20 정규화 스키마

<!-- Changed: define the seed schema used by generation and public20 train/val validation splits. -->
<!-- Why: seed normalization must prevent label leakage and preserve final-response targeting. -->

정규화된 seed record는 다음 필드만 허용한다.

```json
{
  "schema_version": "self_instruct.seed.v1",
  "seed_id": "seed-000",
  "source": "public20_input_only",
  "fold_id": 0,
  "trajectory": {
    "records": [
      {
        "index": 0,
        "input": {
          "method": {"name": "Properties"},
          "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager UID"},
          "args": {"required": {}, "optional": {}}
        },
        "output": {
          "status_codes": "SUCCESS",
          "return_values": []
        }
      }
    ],
    "final_response_index": 0,
    "final_response": {
      "status_codes": "SUCCESS",
      "return_values": []
    }
  },
  "shape": {
    "record_count": 1,
    "method_sequence": ["Properties"],
    "final_method": "Properties",
    "final_status": "SUCCESS",
    "input_char_count": 0,
    "input_token_count": 0,
    "length_bin": "1-32"
  },
  "usage": {
    "may_use_as_generation_seed": true,
    "may_use_label_for_training": false,
    "may_use_label_for_val_metric": true
  }
}
```

이 schema는 generation seed용 input-only schema다. public20-only 모델 후보 검증에서
label을 이용해 supervised `train`/`val`을 만들 때는 별도 local validation artifact를
사용하고, 그 artifact를 synthetic generation seed, judge prompt, generated manifest에
섞지 않는다.

금지 필드는 다음과 같다.

- `label`
- `gold_label`
- `expected_label`
- `rule_id`
- `rule_engine`
- `rule_pred`
- `verifier_output`
- `public_answer`

## output-first generation 단계

<!-- Changed: specify the generation order and artifact contract. -->
<!-- Why: final-response labels must be created around the last response, not around any intermediate event. -->
<!-- Changed: ground every generation request in docs/legacy_spec_rules.md source spans. -->
<!-- Why: ungrounded Gemini/Codex text cannot be promoted from draft to synthetic candidate. -->

1. Seed sampler
   - generation seed로 허용된 input-only row만 읽는다.
   - label은 읽지 않는다.
   - method sequence, record_count, final_method, final_status distribution만 prompt context로 쓴다.

2. Spec-rule card sampler
   - `docs/legacy_spec_rules.md`를 markdown parser로 읽고 RULE 01-86 card를 만든다.
   - 각 card는 최소 `rule_ref`, `title`, `category`, `source_path`,
     `source_span`, `spec_section`, `condition`, `expected_status`, `if_violated`,
     `example_trajectory`를 포함한다.
   - `source_span`은 예: `docs/legacy_spec_rules.md:162-167`처럼 line range를 포함한다.
   - generation request는 supplied card 밖의 spec claim을 만들 수 없다.

3. Output-first target sampling
   - 먼저 target label `pass` 또는 `fail`을 고른다.
   - 그 다음 target final response의 method, status, return value shape를 만든다.
   - target은 항상 `records[-1].output`이어야 한다.
   - candidate count가 2개 이상이면 request 단위에서 최소 `pass` 1개와 `fail` 1개를 요구한다.

4. Backward trajectory synthesis
   - LLM에 final response를 먼저 고정한 뒤 preceding records를 생성하게 한다.
   - preceding records는 final response 판단에 필요한 session context만 제공한다.
   - LLM은 intermediate error를 primary label evidence로 쓰면 안 된다.
   - session open/closed, RO/RW, authenticated authority, lifecycle, TryLimit/Tries,
     object/table 상태가 cited `condition`과 충돌하면 안 된다.

5. Candidate normalization
   - output JSONL schema는 `self_instruct.candidate.v1`이다.
   - `target.final_response_index == len(records) - 1`을 기록한다.
   - `label_source`는 `self_instruct_generator`로 기록하되, judge 통과 전 manifest에는 넣지 않는다.
   - `spec_grounding`은 non-empty list여야 하며 각 item은 cited rule card의
     `rule_ref`, `source_path`, `source_span`, `condition`, `expected_status`를 포함한다.
   - raw→manifest loader compatibility: `records`는 full trajectory list로 남고,
     spec text/source span은 `records`나 `instruction` 안에 넣지 않는다. 이후 manifest/model
     input은 `{"records": records}` stable JSON만 사용한다.

6. Near-duplicate and leakage prefilter
   - exact input hash duplicate를 제거한다.
   - seed input exact/near duplicate를 제거한다.
   - public/eval/holdout metadata marker와 rule-context marker를 제거한다.
   - `spec_grounding`은 offline provenance metadata이므로 runtime rule engine output이나
     rule-derived label과 구분한다. source span이 없는 rule-like text는 leakage로 reject한다.

## LLM-only judge filtering

<!-- Changed: define the judge as an offline data filter. -->
<!-- Why: filtering must improve label quality without becoming a rule engine or runtime dependency. -->
<!-- Changed: require spec-grounding and loader-compatibility checks in judge payloads. -->
<!-- Why: judge accept must not allow unsupported text or metadata that cannot survive Gate A/B/C. -->

judge input은 candidate trajectory, target final response, generated label, generated rationale,
`spec_grounding` source-span metadata만 포함한다. judge prompt는 다음 질문에 JSON으로 답해야 한다.

- `is_final_response_targeted`: label 근거가 마지막 response에만 묶이는가.
- `has_required_spec_grounding`: `docs/legacy_spec_rules.md` source span, rule ref,
  condition, expected status가 있는가.
- `is_source_span_supported`: cited source span이 final-response pass/fail rationale을
  직접 지지하는가.
- `is_state_transition_consistent`: records의 session/auth/lifecycle/object state transition이
  cited condition과 final response에 대해 일관적인가.
- `is_manifest_loader_compatible`: manifest/model input이 `{"records": records}`만 사용해도
  label target과 full trajectory가 보존되는가.
- `is_label_plausible`: generated label이 final response 판단으로 타당한가.
- `has_intermediate_label_leak`: 중간 response 실패/성공을 label의 주근거로 삼는가.
- `has_public_or_rule_leakage`: public label, runtime rule engine text, rule-derived label,
  archived verifier output이 섞였는가.
- `decision`: `accept` 또는 `reject`.

gate 조건은 다음과 같다.

- `decision == "accept"`
- `is_final_response_targeted == true`
- `has_required_spec_grounding == true`
- `is_source_span_supported == true`
- `is_state_transition_consistent == true`
- `is_manifest_loader_compatible == true`
- `is_label_plausible == true`
- `has_intermediate_label_leak == false`
- `has_public_or_rule_leakage == false`
- judge raw response와 normalized decision을 모두 report에 남긴다.

judge는 데이터 필터다. `src/solver.py` inference, package runtime, leaderboard submission
path에서 judge를 호출하지 않는다.

## final-response label invariant

<!-- Changed: make the invariant explicit as a data-quality gate. -->
<!-- Why: this directly blocks the v4/v4.1 label-alignment failure mode. -->

hard invariant는 다음과 같다.

- `records`는 비어 있으면 안 된다.
- `target.final_response_index == len(records) - 1`
- `target.final_response`가 `records[-1].output`과 동일해야 한다.
- `label`은 `pass` 또는 `fail`이어야 한다.
- `label_target == "final_response"`이어야 한다.
- `primary_evidence.record_index == len(records) - 1`이어야 한다.
- `primary_evidence`가 없으면 judge accepted sample이라도 reject한다.
- `spec_grounding`이 없거나 empty list이면 reject한다.
- 각 `spec_grounding` item은 `docs/legacy_spec_rules.md` line range `source_span`을 포함해야 한다.
- 중간 record를 primary evidence로 삼고 final response 뒤에 정상 종료 response를 붙인 sample은 reject한다.

이 invariant checker는 pass/fail 정답을 결정하지 않는다. 구조적으로 label target이 마지막
response를 가리키는지만 확인한다. 그러므로 이 checker는 rule engine이 아니며 runtime
architecture로 사용할 수 없다.

## Gate A - qualitative sampling state-transition audit

<!-- Changed: require direct qualitative state-transition sampling before large training runs. -->
<!-- Why: generated labels need a visible human-quality gate before distribution checks, finetuning, or submission. -->

accepted pool에서 stratified 200개를 뽑는다.

- label별 최소 80개를 포함한다.
- final method별 상위 method가 한쪽 label에만 몰리면 fail한다.
- length bin `1-32`, `33-64`, `65-128`, `129-256`, `257-512`를 가능한 범위에서 포함한다.
- final-response invariant pass rate는 100%여야 한다.
- exact duplicate count는 0이어야 한다.
- seed exact/near duplicate count는 0이어야 한다.
- rule/public marker count는 0이어야 한다.
- LLM judge accept rationale 중 final response mention rate는 95% 이상이어야 한다.
- `spec_grounding.source_span` present rate는 100%여야 한다.
- sampled row마다 cited source span을 열어 `CONDITION`, `EXPECTED_STATUS`,
  final response, generated label, observed state summary를 대조한다.

audit report는 JSON과 Korean MD를 모두 쓴다. 200개 sample의 `sample_id`, label,
final method/status, length bin, judge decision, invariant result를 table로 남긴다.
또한 stratified subset에 대해 검수자가 records를 순서대로 따라가며 session state를
직접 전이한 qualitative audit 결과를 남긴다. 이때 기록해야 할 최소 항목은
`sample_id`, cited source span, observed state summary, final response, generated label,
audit decision, audit rationale이다.

이 state-transition audit는 rule engine/runtime architecture가 아니라 데이터 품질
검수다. 검수자는 사람이 읽을 수 있는 trajectory 문맥으로 label 타당성을 확인하며,
이 결과를 solver fallback, deterministic verifier, runtime dependency로 사용하지 않는다.
따라서 LLM-only architecture 원칙과 충돌하지 않는다.

## Gate B - public20 reference dimension/schema/pass-fail distribution comparison

<!-- Changed: require public20 distribution comparison before fold evaluation and model-path checks. -->
<!-- Why: generated data must match public20 shape/schema/pass-fail distribution without copying public labels into training rows. -->

Gate A를 통과한 generated manifest 후보는 public20 reference와 다음 비교를 통과해야 한다.
이 단계는 public20 자체를 검증하는 단계가 아니라, synthetic 데이터가 실제 제공 입력의
구조와 분포를 충분히 반영했는지 확인하는 단계다.

- schema key set과 required/optional field presence가 public 20에서 허용되는 범위를 벗어나지 않는다.
- 평균 dimension vector가 public 20과 같은 기준으로 산출된다.
- 평균 dimension comparison에는 최소한 `record_count`, method sequence length,
  final method/status count, input char/token count, return value count를 포함한다.
- pass/fail distribution은 public20 aggregate label distribution과 비교한다.
- 현재 public20 기준 facts는 rows `20`, record_count min/mean/max `1/16.4/39`,
  label distribution `fail=10`, `pass=10`이다.
- 비교 report에는 generated manifest count, public20 count, per-dimension mean,
  absolute/relative delta, pass/fail count, fail reason을 남긴다.
- generated profile에는 `spec_rule_refs` coverage와 source-span present rate를 summary로
  남긴다. 이것은 public20 row와 rule을 matching하는 단계가 아니라 generated pool이
  spec-grounded 후보인지 확인하는 보조 지표다.
- public20 label은 aggregate audit와 public20-only `val` metric 계산에만 사용한다. generated row의
  label, judge prompt, training manifest source로 복사하면 fail이다.
- 현재 Gate B report 도구는 `tools/analysis/compare_public20_dimensions.py`다.
  이 도구는 public20 profile JSON과 generated candidate profile JSON을 비교하고,
  public20 label은 local aggregate JSON으로만 선택적으로 받는다.

Gate B report가 pass한 뒤에만 public20-only 모델 후보 검증을 병렬 보조 작업으로 실행한다.
이 검증은 public20 20개를 `train`/`val`로만 나누며 public20 `test` split을 만들지 않는다.
최종 test는 leaderboard hidden 평가다.

public20 20개를 반복 split으로 나눌 수는 있지만, 각 split의 held-out은 `val`이다.
`test`라고 부르지 않는다.

각 split에서 허용되는 것은 다음뿐이다.

- public20-only model training: held-out `val`을 제외한 public20 train rows와 train labels.
- generated synthetic data validation과의 병렬 비교: 해당 fold의 accepted Self-Instruct data는
  synthetic pipeline 검증 대상이며, public20 row를 synthetic row로 복사하지 않는다.
- metric scoring: held-out public20 `val` labels.

각 split에서 금지되는 것은 다음이다.

- public20 `val` input을 해당 fold의 public20-only training input에 넣기.
- public label을 generated synthetic training row의 label로 복사하기.
- public label을 judge prompt에 넣기.
- public case text를 exact duplicate로 training manifest에 넣기.
- public20 `test` split을 만들기.

보고 지표는 split별 accuracy, false negative count, false positive count, calibration
threshold, accepted synthetic data count, invariant pass rate, judge accept rate다. split 평균과
worst-validation-split 값을 모두 기록하되 이 값은 validation 결과이며 leaderboard test 결과가 아니다.

## Gate C - manifest/model input path equivalence check

<!-- Changed: require model-input equivalence after manifest validation and before leaderboard submission. -->
<!-- Why: data that passes manifest checks must be proven to enter the actual model through the same schema and label path. -->

Gate C는 manifest 파일이 실제 model input path에서도 같은 방법으로 처리되는지 확인한다.
이 검증은 학습/추론 architecture 변경이 아니라 data path equivalence 감사다.

현재 Gate C report 도구는 `tools/analysis/check_manifest_model_input_equivalence.py`다. 이 도구는 normalized
candidate와 supervised manifest를 비교하고, lightweight trainer loader의 `load_manifest`와 `build_messages`
계약까지만 확인한다. solver/runtime, model/tokenizer, public20 label, LLM/API는 import하거나 호출하지 않는다.

필수 확인 항목은 다음이다.

- `validate_manifest.py`에 입력한 manifest path와 training loader가 읽는 manifest path가 같다.
- loader가 읽은 `sample_id` set, row count, input hash가 manifest validation report와 같다.
- `label`의 pass/fail mapping이 manifest와 model target tensor 사이에서 뒤집히거나 재정의되지 않는다.
- Gate B의 dimension summary가 loader 후처리 결과에서도 보존된다.
- final response를 가리키는 path가 `records[-1].output`으로 유지된다.
- candidate의 `spec_grounding` metadata는 audit/report에는 남고, trainer
  `build_messages` user content에는 들어가지 않는다.
- v4/v4.1 raw/manifest, rule id, rule engine marker, public label source가 model batch에 0개다.
- first-forward smoke 또는 동등한 dry-run에서 batch schema와 label tensor shape가 report로 남는다.

loader가 silent filtering, order-dependent relabeling, default deprecated source fallback,
rule-context enrichment를 수행하면 fail이다.

## data size ablation

<!-- Changed: fix ablation sizes and selection criterion. -->
<!-- Why: dataset size should be justified by measured generalization, not by generator volume alone. -->

동일한 generation pool에서 seed와 filter를 고정한 뒤 다음 크기로 manifest를 만든다.

- 200
- 500
- 1000
- 2000
- 4000

각 크기는 label, final method, length bin을 stratified sampling한다. 같은 candidate가
여러 size에 들어갈 수 있지만, 큰 size는 작은 size의 superset이어야 한다. 평가 protocol은
동일한 public20-only train/val validation과 동일한 calibration 절차를 사용한다.

선택 기준은 다음 순서다.

1. invariant/audit hard gate 통과.
2. worst-validation-split metric 개선.
3. validation split 평균 metric 개선.
4. calibration stability.
5. training cost.

## Gate D - leaderboard submission only after gates pass

<!-- Changed: connect Gate A-C to the existing no-go submission policy. -->
<!-- Why: leaderboard submission must require qualitative data audit, public20 comparison, model-input equivalence, evaluation, and package evidence together. -->

leaderboard 제출은 다음이 모두 참일 때만 go다.

- v4/v4.1 raw/manifest가 학습 입력과 제출 판단에서 0개다.
- Self-Instruct accepted manifest가 `validate_manifest.py` hard gate를 통과한다.
- final-response invariant pass rate가 100%다.
- Gate A qualitative sampling state-transition audit와 200-sample quality audit가 통과한다.
- Gate B public20 reference dimension/schema/pass-fail distribution comparison이 통과한다.
- Gate C manifest/model input path equivalence check가 통과한다.
- public20-only train/val validation report가 존재한다.
- data size ablation 200/500/1K/2K/4K report가 존재한다.
- 선택 size가 baseline보다 validation split 평균 또는 worst-validation-split에서 명확히 낫다.
- package size가 `<12GB`다.
- `tools/eval/check_submit_package.py`가 통과한다.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward`가 통과한다.
- secret, token, password가 dataset/report/script에 기록되지 않았다.
- Korean archive record에 제출 근거, no-go 대안, known risk가 남아 있다.

## 구현 상태와 다음 순서

<!-- Changed: list implementation steps without modifying training code. -->
<!-- Why: core training code should remain untouched until the data contract is tested. -->

완료된 구현:

1. `tests/test_self_instruct_final_response_invariant.py` scaffold를 추가했다.
2. `tools/analysis/self_instruct_invariants.py`를 stdlib-only로 구현했다.
3. `tools/datagen/self_instruct_seed_schema.py`로 seed 20 input-only normalizer를 작성했다.
4. `tools/datagen/self_instruct_candidate_schema.py`로 label-bearing candidate schema를 작성했다.
5. active `tools/datagen/`에서 v4/v4.1 및 spec/gap synthetic generator를 제거했다.
6. 서버에서 public20 input-only reference와 local-only label reference를 확보했다.
7. `tools/analysis/audit_public20_reference.py`로 public20 reference structure/profile audit pack을 생성했다. 이 pack은 public20 검증 결과가 아니라 비교 기준 구조 확인용이다.
8. `tools/analysis/compare_public20_dimensions.py`로 Gate B public20/generated profile 비교 report를 구현했다.
9. `tools/analysis/check_manifest_model_input_equivalence.py`로 Gate C candidate/manifest/trainer-loader 입력 동등성 report를 구현했다.
10. `tools/datagen/parse_self_instruct_outputs.py`로 raw LLM output parser를 구현했다. 이 도구는 parsing/normalization/reject report만 수행하고 synthetic trajectory를 자체 생성하지 않는다.
11. `tools/analysis/dedup_self_instruct_candidates.py`로 ROUGE-L 0.7 near duplicate, exact duplicate, same-input conflicting label, public20 duplicate filter를 구현했다.
12. `tools/analysis/build_public20_train_val_split.py`로 public20-only 모델 검증용 deterministic `train`/`val` split을 구현했고 seed `11`, `29`, `47` artifact를 `runs/model_validation/public20_splits/`에 생성했다.
13. `tools/datagen/run_self_instruct_generation.py`로 Self-Instruct output-first
    spec-grounded generation dry-run request payload/metadata writer를 구현했다. 이 도구는
    `docs/legacy_spec_rules.md` rule card/source-span을 prompt payload에 넣으며 LLM/API 호출과
    자체 candidate 생성을 하지 않는다.
    <!-- Changed: document the provider-gated LLM runner and current skip outcome. -->
    <!-- Why: runner availability must not be confused with generated synthetic evidence. -->
    `tools/datagen/self_instruct_llm_runner.py` 실행 lane은 추가됐지만 현재 `OPENAI_API_KEY`/`GEMINI_API_KEY`
    env가 없어 실제 generation은 `skipped_missing_env`로 skip 상태다. raw output JSONL이 없으므로
    `sample.md` 생성과 Gate A/B/C pass 선언은 no-go다.
14. `tools/analysis/filter_self_instruct_judge.py`로 LLM-only judge dry-run request payload writer와 외부 judge result parser를 구현했다. judge payload는 final-response targeting,
    required spec grounding, source-span support, state-transition consistency,
    manifest-loader compatibility를 JSON boolean으로 요구한다.
15. `tools/eval/eval_manifest_full_model.py`로 full/selective FT standalone checkpoint를 `val` manifest에서 평가하는 도구를 구현했다. LoRA adapter evaluator를 사용하지 않고 full model path를 직접 로드한다.

다음 구현 순서:

1. 외부 LLM runner가 `run_self_instruct_generation.py` request payload를 실행해 raw output JSONL을 만든다. API key/secret은 repo에 저장하지 않는다.
   source-span 없는 raw output은 synthetic 후보가 아니라 reject 대상이다.
2. `parse_self_instruct_outputs.py`, `dedup_self_instruct_candidates.py`, `filter_self_instruct_judge.py`를 순서대로 적용해 accepted candidate 후보를 만든다.
3. Gate A qualitative sampling state-transition audit와 200-sample audit tool을 generated accepted data에 적용한다.
4. Gate B comparison report를 generated candidate profile에 적용한다.
5. generated manifest 후보가 생기면 Gate C 도구를 적용하고 report를 archive한다.
6. Gate A/B/C 통과 뒤 synthetic `train`, `val`, `test`와 `public20_reference`를 물리적으로 분리한다.
7. `docs/samples/self_instruct_sample.md`에 generated raw trajectory 전체와 public20 raw sample 1개 전체를 생략 없이 기록한다.
8. public20-only train/val validation runner를 작성한다.
9. 모델 후보는 0.9B full FT, 0.9B full FT + retrieved rulebook/spec context, 4B LoRA/QLoRA selective FT, 4B LoRA/QLoRA + retrieved context, RAFT-style retrieval-augmented SFT/QLoRA를 public20 train/val로 비교한다.
10. training code는 Gate A-C가 통과한 manifest가 생긴 뒤에만 연결한다.
