<!-- Changed: add the active Self-Instruct data-generation plan and mandatory data-validation gate order. -->
<!-- Why: v4/v4.1 generators are deprecated because their labels can target an intermediate response instead of the final response, and new generated data must pass qualitative and model-path checks before submission. -->

# Current Self-Instruct Data Plan

## 목적과 비범위

<!-- Changed: define the active replacement scope before code implementation. -->
<!-- Why: the next pipeline must not reuse deprecated v4/v4.1 generation or rule-engine architecture. -->

이 문서는 `tools/datagen/generate_long_trajectories.py` 및
`tools/datagen/generate_long_shape_source.py`를 재사용하지 않는 새 데이터 생성
파이프라인의 active spec이다. 목표는 Self-Instruct 하나를 제대로 구현해
`final response` 판단용 supervised 데이터를 만들고, 학습 전 품질 gate와
평가 protocol을 고정하는 것이다.

비범위는 다음과 같다.

- v4/v4.1 deprecated generator를 학습 데이터 생성에 재사용하지 않는다.
- rule engine, rule fallback, rule-id prompt, rule-derived label을 사용하지 않는다.
- invariant checker는 데이터 품질 gate다. runtime architecture, solver fallback,
  rule engine, deterministic verifier로 사용하지 않는다.
- public 20 label은 supervised training source가 아니다. Gate B aggregate
  pass/fail distribution 비교와 fold 평가의 metric 계산에만 사용하고, 생성 prompt와
  학습 manifest에는 넣지 않는다.

## 필수 검증 gate 순서

<!-- Changed: make Gate A-D the mandatory order for generated-data validation. -->
<!-- Why: generated data must be checked qualitatively, distributionally, and through the model input path before any leaderboard submission. -->

새 generated data는 아래 순서를 건너뛰면 안 된다. 앞 gate가 fail이면 뒤 gate를 실행하지
않고 no-go archive를 작성한다.

1. Gate A: qualitative sampling state-transition audit
   - accepted pool 일부를 직접 sampling한다.
   - 검수자는 sample의 records를 처음부터 끝까지 순서대로 읽고, 필요한 session state를
     사람이 전이해 보며 final response가 generated label과 질적으로 맞는지 확인한다.
   - 이 state-transition audit는 데이터 품질 검수다. rule engine, runtime architecture,
     deterministic verifier, solver fallback이 아니며 `src/solver.py`나 package runtime에
     import하면 안 된다.

2. Gate B: public20 dimension/schema/pass-fail distribution comparison
   - Gate A를 통과한 manifest 후보와 public 20의 schema, 평균 dimension vector,
     pass/fail 분포를 비교한다.
   - dimension vector는 최소한 `record_count`, method sequence length,
     final method/status, input char/token count, return value count를 포함한다.
   - public 20 row-level label은 학습 row로 복사하지 않고, aggregate no-go 판단과
     fold metric 계산에만 사용한다.

3. Gate C: manifest/model input path equivalence check
   - manifest validation에서 통과한 동일 파일이 training loader와 실제 model first-forward
     입력에서도 같은 schema, sample id/hash, label mapping, dimension summary로 처리되는지
     확인한다.
   - loader가 row를 조용히 drop/resample/relabel하거나 deprecated source를 섞으면 fail이다.

4. Gate D: leaderboard submission only after gates pass
   - Gate A, Gate B, Gate C가 모두 pass이고 package/runtime/secret/no-rule gate도 pass일 때만
     leaderboard 제출을 go로 판단한다.
   - 제출 전에는 Korean archive record에 gate artifact path, pass/fail 근거, known risk,
     no-go 대안을 남긴다.

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

## 현재 repo 구조 감사

<!-- Changed: record the audited local structure that the plan builds on. -->
<!-- Why: implementation files must attach to active tools without reviving archived code. -->

[Original Text/Data] `tools/datagen/`에는 `generate_spec_data.py`,
`generate_gap_data.py`, `generate_long_trajectories.py`,
`generate_long_shape_source.py`가 있다. → [Exact Interpretation] active datagen은
spec/gap 계열과 deprecated long-shape 계열이 섞여 있다. → [Detailed Explanation/Example]
Self-Instruct 신규 생성기는 long trajectory 파일을 import하지 않는 독립 파일이어야 한다.

[Original Text/Data] `README.md`는 `generate_long_trajectories.py`와
`generate_long_shape_source.py`를 "deprecated/audit-only"로 명시한다. →
[Exact Interpretation] 새 pipeline은 두 파일의 case builder, label pattern, CLI를
재사용하면 안 된다. → [Detailed Explanation/Example] v4/v4.1의 `_endsession()`
append 패턴처럼 intermediate failure 뒤 final `EndSession SUCCESS`를 붙이는 구조는
새 manifest에 들어오면 label target을 오염시킨다.

[Original Text/Data] `tools/analysis/`에는 `build_supervised_manifest.py`,
`validate_manifest.py`, `data_audit.py`가 있다. → [Exact Interpretation] 현재 분석
계층은 manifest construction, manifest hard gate, dataset audit에 집중한다. →
[Detailed Explanation/Example] Self-Instruct judge filtering과 final-response invariant
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
- deprecated v4/v4.1 source를 default execution에서 호출하지 않는다.

archive할 것은 다음이다.

- 날짜가 붙은 실행 기록, 제출 시도, no-go 판단, 실패 원인 분석.
- 재현 가치가 있는 legacy code와 script. 이런 파일은 `docs/archive/` 또는
  `tools/archive/legacy_rule_pipeline/` 아래에서만 실행 근거로 보존한다.
- v4/v4.1 같은 실패 코드는 audit evidence와 재현 근거만 남긴다. active 위치에
  임시로 남아 있는 경우에도 명시적 `--allow-deprecated-v4-v41` 같은 opt-in 없이는
  실행되지 않아야 하며, 학습 manifest와 제출 판단의 default path에서는 0개여야 한다.

삭제할 것은 다음이다.

- secret, token, password, credential이 들어간 파일 또는 로그. 이런 파일은 archive하지 않는다.
- 동일 내용을 중복한 stale docs 중 최신 active/archive 문서로 완전히 대체된 파일.
- 재현 가능한 tmp output, partial generated data, 캐시성 산출물 중 no-go 근거로 쓰이지 않는 파일.

정리 후에는 active doc이 archive evidence를 링크해야 한다. 실패 코드나 실패 데이터를
다시 default 실행 경로에 연결하는 변경은 Gate A 이전 단계에서 fail로 본다.

## 필요한 파일 제안

<!-- Changed: propose the minimum file set for the new pipeline. -->
<!-- Why: implementation should be small, auditable, and separated from training/runtime code. -->

1. `tools/datagen/self_instruct_seed_schema.py`
   - seed 20 input을 canonical JSON으로 정규화한다.
   - public label을 읽거나 출력하지 않는다.
   - fold별 seed exclusion list를 만들 수 있어야 한다.

2. `tools/datagen/generate_self_instruct_candidates.py`
   - output-first Self-Instruct candidate를 JSONL로 생성한다.
   - v4/v4.1 generator를 import하지 않는다.
   - LLM API key, server token, secret 값을 log 또는 output JSON에 쓰지 않는다.

3. `tools/analysis/filter_self_instruct_judge.py`
   - LLM-only judge로 candidate를 accept/reject한다.
   - judge prompt에는 rule engine, rule id, public label, archived verifier output을 넣지 않는다.
   - output은 accepted JSONL, rejected JSONL, judge report JSON/MD다.

4. `tools/analysis/self_instruct_invariants.py`
   - final-response label invariant를 검사한다.
   - 이 모듈은 데이터 품질 gate 전용이다. `src/solver.py`, inference runtime,
     package script에서 import하면 안 된다.

5. `tools/analysis/audit_self_instruct_quality.py`
   - accepted pool에서 200-sample quality audit pack과 report를 만든다.
   - manifest validation과 중복되지 않는 Self-Instruct 전용 gate를 기록한다.

6. `tools/eval/eval_self_instruct_public_seed_folds.py`
   - 5-fold public-seed evaluation을 실행한다.
   - public labels는 fold metric 계산에만 사용한다.
   - fold-held seed input은 해당 fold의 generation seed/prompt/training data에서 제외한다.

7. `tests/test_self_instruct_final_response_invariant.py`
   - invariant checker 구현 전 API와 실패 사례를 고정한다.
   - v4/v4.1의 핵심 실패 모드인 "중간 실패 뒤 성공 final response"를 회귀 테스트로 둔다.

## seed 20 정규화 스키마

<!-- Changed: define the seed schema used by generation and public-seed folds. -->
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
    "may_use_label_for_fold_metric": true
  }
}
```

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

1. Seed sampler
   - fold에서 허용된 seed input만 읽는다.
   - label은 읽지 않는다.
   - method sequence, record_count, final_method, final_status distribution만 prompt context로 쓴다.

2. Output-first target sampling
   - 먼저 target label `pass` 또는 `fail`을 고른다.
   - 그 다음 target final response의 method, status, return value shape를 만든다.
   - target은 항상 `records[-1].output`이어야 한다.

3. Backward trajectory synthesis
   - LLM에 final response를 먼저 고정한 뒤 preceding records를 생성하게 한다.
   - preceding records는 final response 판단에 필요한 session context만 제공한다.
   - LLM은 intermediate error를 primary label evidence로 쓰면 안 된다.

4. Candidate normalization
   - output JSONL schema는 `self_instruct.candidate.v1`이다.
   - `target.final_response_index == len(records) - 1`을 기록한다.
   - `label_source`는 `self_instruct_generator`로 기록하되, judge 통과 전 manifest에는 넣지 않는다.

5. Near-duplicate and leakage prefilter
   - exact input hash duplicate를 제거한다.
   - seed input exact/near duplicate를 제거한다.
   - public/eval/holdout metadata marker와 rule-context marker를 제거한다.

## LLM-only judge filtering

<!-- Changed: define the judge as an offline data filter. -->
<!-- Why: filtering must improve label quality without becoming a rule engine or runtime dependency. -->

judge input은 candidate trajectory, target final response, generated label, generated rationale만
포함한다. judge prompt는 다음 질문에 JSON으로 답해야 한다.

- `is_final_response_targeted`: label 근거가 마지막 response에만 묶이는가.
- `is_label_plausible`: generated label이 final response 판단으로 타당한가.
- `has_intermediate_label_leak`: 중간 response 실패/성공을 label의 주근거로 삼는가.
- `has_public_or_rule_leakage`: public label, rule id, rule engine text가 섞였는가.
- `decision`: `accept` 또는 `reject`.

gate 조건은 다음과 같다.

- `decision == "accept"`
- `is_final_response_targeted == true`
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

audit report는 JSON과 Korean MD를 모두 쓴다. 200개 sample의 `sample_id`, label,
final method/status, length bin, judge decision, invariant result를 table로 남긴다.
또한 stratified subset에 대해 검수자가 records를 순서대로 따라가며 session state를
직접 전이한 qualitative audit 결과를 남긴다. 이때 기록해야 할 최소 항목은
`sample_id`, observed state summary, final response, generated label, audit decision,
audit rationale이다.

이 state-transition audit는 rule engine/runtime architecture가 아니라 데이터 품질
검수다. 검수자는 사람이 읽을 수 있는 trajectory 문맥으로 label 타당성을 확인하며,
이 결과를 solver fallback, deterministic verifier, runtime dependency로 사용하지 않는다.
따라서 LLM-only architecture 원칙과 충돌하지 않는다.

## Gate B - public20 dimension/schema/pass-fail distribution comparison

<!-- Changed: require public20 distribution comparison before fold evaluation and model-path checks. -->
<!-- Why: generated data must match public20 shape/schema/pass-fail distribution without copying public labels into training rows. -->

Gate A를 통과한 manifest 후보는 public 20과 다음 비교를 통과해야 한다.

- schema key set과 required/optional field presence가 public 20에서 허용되는 범위를 벗어나지 않는다.
- 평균 dimension vector가 public 20과 같은 기준으로 산출된다.
- 평균 dimension comparison에는 최소한 `record_count`, method sequence length,
  final method/status count, input char/token count, return value count를 포함한다.
- pass/fail distribution은 public 20 aggregate label distribution과 비교한다.
- 비교 report에는 generated manifest count, public20 count, per-dimension mean,
  absolute/relative delta, pass/fail count, fail reason을 남긴다.
- public 20 label은 aggregate audit와 fold metric 계산에만 사용한다. generated row의
  label, judge prompt, training manifest source로 복사하면 fail이다.

Gate B report가 pass한 뒤에만 5-fold public-seed evaluation을 실행한다.

public seed 20개를 5개 fold로 나누고 fold마다 4개를 held-out으로 둔다.

각 fold에서 허용되는 것은 다음뿐이다.

- training seed context: held-out 4개를 제외한 input-only seed shape.
- generated synthetic training data: 해당 fold의 accepted Self-Instruct data.
- metric scoring: held-out 4개 public labels.

각 fold에서 금지되는 것은 다음이다.

- held-out seed input을 generation prompt에 넣기.
- public label을 generated training row의 label로 복사하기.
- public label을 judge prompt에 넣기.
- public case text를 exact duplicate로 training manifest에 넣기.

보고 지표는 fold별 accuracy, false negative count, false positive count, calibration
threshold, accepted data count, invariant pass rate, judge accept rate다. fold 평균과
worst-fold 값을 모두 기록한다.

## Gate C - manifest/model input path equivalence check

<!-- Changed: require model-input equivalence after manifest validation and before leaderboard submission. -->
<!-- Why: data that passes manifest checks must be proven to enter the actual model through the same schema and label path. -->

Gate C는 manifest 파일이 실제 model input path에서도 같은 방법으로 처리되는지 확인한다.
이 검증은 학습/추론 architecture 변경이 아니라 data path equivalence 감사다.

필수 확인 항목은 다음이다.

- `validate_manifest.py`에 입력한 manifest path와 training loader가 읽는 manifest path가 같다.
- loader가 읽은 `sample_id` set, row count, input hash가 manifest validation report와 같다.
- `label`의 pass/fail mapping이 manifest와 model target tensor 사이에서 뒤집히거나 재정의되지 않는다.
- Gate B의 dimension summary가 loader 후처리 결과에서도 보존된다.
- final response를 가리키는 path가 `records[-1].output`으로 유지된다.
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
동일한 5-fold public-seed evaluation과 동일한 calibration 절차를 사용한다.

선택 기준은 다음 순서다.

1. invariant/audit hard gate 통과.
2. worst-fold metric 개선.
3. fold 평균 metric 개선.
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
- Gate B public20 dimension/schema/pass-fail distribution comparison이 통과한다.
- Gate C manifest/model input path equivalence check가 통과한다.
- 5-fold public-seed evaluation report가 존재한다.
- data size ablation 200/500/1K/2K/4K report가 존재한다.
- 선택 size가 baseline보다 fold 평균 또는 worst-fold에서 명확히 낫다.
- package size가 `<12GB`다.
- `tools/eval/check_submit_package.py`가 통과한다.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward`가 통과한다.
- secret, token, password가 dataset/report/script에 기록되지 않았다.
- Korean archive record에 제출 근거, no-go 대안, known risk가 남아 있다.

## 다음 구현 순서

<!-- Changed: list implementation steps without modifying training code. -->
<!-- Why: core training code should remain untouched until the data contract is tested. -->

1. `tests/test_self_instruct_final_response_invariant.py` scaffold를 추가한다.
2. `tools/analysis/self_instruct_invariants.py`를 stdlib-only로 구현한다.
3. seed 20 input-only normalizer를 작성한다.
4. generator candidate schema와 dry-run fixture를 작성한다.
5. LLM-only judge filter를 JSON contract first로 작성한다.
6. Gate A qualitative sampling state-transition audit와 200-sample audit tool을 작성한다.
7. Gate B public20 dimension/schema/pass-fail distribution comparison report를 작성한다.
8. 5-fold evaluation runner를 작성한다.
9. ablation manifest builder를 작성한다.
10. Gate C manifest/model input path equivalence check를 training loader/first-forward smoke로 작성한다.
11. training code는 Gate A-C가 통과한 manifest가 생긴 뒤에만 연결한다.
