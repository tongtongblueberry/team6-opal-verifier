<!-- Changed: add a stable handoff context that every worker agent must read or receive before doing repository work. -->
<!-- Why: agents were making isolated local progress without the project discussion context, which caused repeated drift from the LLM-only/data-first objective. -->

# Agent Handoff

- 최종 갱신: 2026-05-26 16:50 KST
- 목적: 새 agent가 단발 작업만 수행하지 않고, 현재 논의 맥락과 금지사항을 유지한 채 작업하게 한다.
- 적용 범위: repo 작업, 문서 정리, 데이터 생성/검증, 학습 실행, 서버 SSH 재시도, git push를 맡는 모든 worker agent.

## 절대 원칙

- 제출/학습 architecture에는 rule engine을 포함하지 않는다.
- runtime fallback, rule-id prompt, rule-derived label, rulebase verifier 결합은 금지한다.
- `src/solver.py`와 제출 package는 LLM-only entrypoint 기준으로 유지한다.
- 데이터 품질 gate용 invariant/state-transition audit는 runtime rule engine이 아니다. `src/solver.py`나 package inference path에서 import하면 안 된다.
- 사용자가 채팅에 남긴 서버 비밀번호, token, secret은 repo, docs, archive, log, command output에 저장하거나 출력하지 않는다.
- 기록은 한국어로 작성하고 시간은 KST를 사용한다.
- active docs update set은 `README.md`, `PROGRESS.md`, `docs/README.md`, `docs/current_task.md`, `docs/current_self_instruct_data_plan.md`, `docs/agent_handoff.md`, `docs/samples/README.md`다. 데이터/학습/제출/sample 공개/cleanup 기준을 바꾸면 이 묶음을 함께 점검한다.
- git push 대상은 `origin/sinjeongmin`이다.
- destructive git command, 다른 사람 변경 revert, `/workspace/team6` 의존 복구는 금지한다.
- main agent는 직접 web 검색, SSH, 학습 실행, 파일 수정을 기본 작업 방식으로 삼지 않는다.
  실행/검색/수정/학습은 worker agent가 맡고, main agent는 결과 종합과 최종 판단을 맡는다.

## 현재 결정사항

- 프로젝트 목표는 LLM-only Opal verifier다. Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 맞는지 `pass`/`fail`로 판정한다.
- 현재 병목은 모델보다 데이터다. 검증 대상은 우리가 새로 생성한 synthetic 데이터다.
  public20은 이미 주어진 기준 입력이므로 "public20 자체를 검증"하지 않는다.
  새 synthetic 데이터는 양적 dimension뿐 아니라 질적으로 pass/fail이 맞는지 검증해야 한다.
- v4/v4.1 생성 데이터는 학습 금지 및 폐기 상태다.
  - 재현 근거: fail sample에서 중간 `Set FAIL` 뒤 마지막 `EndSession SUCCESS`인데 label이 `fail`이었다.
  - 원천 fail 538개 중 440개가 final `EndSession SUCCESS`로 끝나는 문제가 archive에 기록되어 있다.
  - 원인은 fail case 뒤에 `_endsession()`을 붙여 final-response label target이 중간 event로 밀린 생성 패턴이다.
- active `tools/datagen/`에는 Self-Instruct seed/candidate schema만 남긴다.
  - v4/v4.1 generator와 spec/gap synthetic generator는 active datagen에서 제거했다.
  - 정리 근거는 `docs/archive/legacy_datagen/README.md`와 v4/v4.1 폐기 archive에 둔다.
- ad-hoc fixture/smoke generated data is not accepted synthetic data.
  임의 deterministic fixture/smoke 산출물은 논문 기반 생성 데이터나 검증된 코드 기반 synthetic data가 아니므로 active surface에 두지 않는다.
- 새 데이터 생성은 Wang et al. 2023 Self-Instruct 하나를 제대로 따른다.
  - output-first classification generation을 사용한다.
  - LLM-only judge filtering을 사용한다.
  - 논문식 quality audit, evaluation, data-size/data-quality ablation을 구현 대상으로 둔다.
  - 공식 코드 기준은 `https://github.com/yizhongw/self-instruct`이고 license는 Apache-2.0이다.
  - 공식 출처와 차용 범위는 `third_party/self_instruct/README.md`와
    `docs/archive/research/self_instruct_implementation_plan_2026-05-26_kst.md`에 둔다.
  - 공식 Self-Instruct 절차 없는 ad-hoc generator는 active tools에 추가하지 않는다.
- public20 seed schema는 input-only다. `label`, `gold_label`, `expected_label`, `answer`
  계열 필드는 default에서 reject하고 output에도 쓰지 않는다.
- public20 local reference는 확보되어 있다.
  - input-only: `data/local/public20/public20_input.jsonl`
  - label reference: `data/local/public20/public20_labels.local.jsonl`
  - rows `20`, labels `20`, record_count min/mean/max `1/16.4/39`, label 분포 `fail=10`, `pass=10`
  - label 파일은 synthetic generation prompt, judge prompt, generated synthetic manifest 입력에 넣지 않는다.
  - public20-only 모델 검증 artifact에서는 public20 label을 train target과 `val` metric으로만 쓸 수 있다.
- synthetic 데이터 검증 완료 후 저장 partition은 반드시 `train`, `val`, `test`,
  `public20_reference`로 분리한다.
  - `train`, `val`, `test`는 Gate A/B/C를 통과한 generated Self-Instruct 데이터에서만 만든다.
  - `public20_reference`는 shape/profile/reference 비교와 public20-only 모델 검증용 local reference다.
  - public20-only 모델 후보 검증을 할 때는 public20 20개를 `train`/`val`로만 나눈다.
    public20 `test` split은 만들지 않는다. test는 leaderboard hidden 평가다.
    기본 split은 stratified `16 train / 4 val`이고 val은 `pass 2 / fail 2`를 목표로 한다.
- label-bearing generated row는 `tools/datagen/self_instruct_candidate_schema.py`의
  candidate schema로만 다루며, final-response invariant는 candidate에만 적용한다.
- leaderboard 제출은 Gate A-D와 package/runtime/secret/no-rule gate가 모두 통과한 뒤에만 검토한다.
- Self-Instruct synthetic data가 Gate A/B/C를 통과한 뒤에만 `docs/samples/self_instruct_sample.md`에 raw trajectory 전체를 "합격 데이터" sample로 공개한다. 그 전에는 sample을 검수 대상 또는 실패/대기 데이터로만 표기한다.
  - sample 문서는 generated raw trajectory 전체와 public20 raw sample 1개 전체를 모두 생략 없이 포함해야 한다.
- 12GB 제출 한계를 고려해 LoRA 3MB만 고집하지 않는다.
  - 0.8B/0.9B급 full fine-tuning은 후보로 유지한다.
  - 4B는 selective fine-tuning, LoRA/DoRA/QLoRA, last-n-layers 계열을 비교한다.
  - 27B는 full fine-tuning보다 특정 layer/adapter/quantized selective 계열만 현실 후보로 본다.
- 모델 방법론 검증은 public20-only `train`/`val` split으로 병렬 진행할 수 있다.
  다만 전체 자원을 모델 검증에 몰아주지 않고, synthetic 데이터 생성의 질적/정량 검증을 계속 병렬 진행한다.
  RAG/FT 후보 구현은 관련 논문과 검증된 라이브러리/코드를 따른다.
  이때 `val`은 후보 선택/튜닝/early stopping용 내부 검증이고, `test`는 leaderboard hidden 평가다.
- 사용자 요청 중심 모델 후보는 Frozen RAG classifier, 0.9B full FT, 4B QLoRA/LoRA selective FT, RAFT-style RAG+SFT/QLoRA다.
- non-training prompt/logprob baseline은 agent가 추가한 sanity baseline이며, 사용자 요청 후보가 아니라 RAG/FT 비교 결과가 의미 있는지 확인하는 최소 비학습 대조군이다.
- pure RAG 문제는 아니지만 rulebook/spec retrieval과 trajectory reasoning이 함께 필요하므로 RAFT-style retrieval-augmented classifier를 최종 유력 후보로 둔다.
- val macro-F1 상승이 멈추고 loss만 좋아지거나 fail recall이 떨어지면 no-go 또는 early stopping한다. leaderboard는 내부 val 개선, qualitative error 감소, 제출물 차별점이 명확할 때만 1회 사용한다.

## 데이터 Gate 순서

1. Gate A: qualitative sampling state-transition audit
   - generated accepted pool 일부를 사람이 sampling한다.
   - records를 처음부터 끝까지 읽고 session state를 직접 전이해 본다.
   - final response가 generated label과 질적으로 맞는지 확인한다.
   - 중간 failure 뒤 final success인데 label `fail`인 sample은 reject한다.

2. Gate B: public20 reference dimension/schema/pass-fail distribution comparison
   - Gate A를 통과한 generated synthetic data를 public20 reference와 비교한다.
   - public20 자체를 검증하는 단계가 아니다.
   - schema, 평균 dimension vector, pass/fail 분포가 기준 입력과 비슷한지 확인한다.
   - 현재 public20 기준 facts: rows `20`, record_count min/mean/max `1/16.4/39`, label 분포 `fail=10`, `pass=10`.
   - 최소 dimension vector: `record_count`, method sequence length, final method/status, input char/token count, return value count.
   - public20 label은 synthetic training row로 복사하지 않고 aggregate 비교와 public20-only `val` metric 계산에만 쓴다.
   - active 도구는 `tools/analysis/compare_public20_dimensions.py`다.
   - public20 label은 row-level 입력이 아니라 local aggregate JSON으로만 report에 넣는다.

3. Gate C: manifest/model input path equivalence check
   - manifest validation을 통과한 동일 파일이 training loader와 model first-forward에서 같은 schema, sample id/hash, label mapping, dimension summary로 처리되는지 확인한다.
   - loader가 row를 조용히 drop/resample/relabel하거나 deprecated source를 섞으면 fail이다.

4. Gate D: leaderboard submission decision
   - Gate A-C, package `<12GB`, offline first-forward smoke, no-rule/secret gate가 모두 통과해야 go다.
   - 제출 전후에는 Korean archive record를 남긴다.
   - 하루 leaderboard 기회는 기존 결과와 무엇이 달라졌는지 설명할 수 있을 때만 사용한다.

## Agent가 반드시 읽어야 할 파일

- [docs/current_task.md](current_task.md): 현재 cycle 상태, 서버 상태, 다음 실행 순서.
- [docs/current_self_instruct_data_plan.md](current_self_instruct_data_plan.md): Self-Instruct 데이터 생성/검증 active spec.
- [docs/server_operations_current.md](server_operations_current.md): 서버 접속, sync, 제출 판단 절차.
- [docs/README.md](README.md): active/archive/delete 문서 정리 기준.
- [docs/samples/README.md](samples/README.md): raw sample 공개 정책.
- [../third_party/self_instruct/README.md](../third_party/self_instruct/README.md): Self-Instruct 공식 출처, license, 차용 범위, 금지사항.
- [archive/research/self_instruct_implementation_plan_2026-05-26_kst.md](archive/research/self_instruct_implementation_plan_2026-05-26_kst.md): 공식 Self-Instruct 구현 계획 archive.
- [../README.md](../README.md): 현재 repo 운영 원칙과 도구 목록.
- [../PROGRESS.md](../PROGRESS.md): 현재 진행 상황 요약.
- [archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md](archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md): v4/v4.1 폐기 근거.
- [../tools/analysis/self_instruct_invariants.py](../tools/analysis/self_instruct_invariants.py): final-response invariant checker. 데이터 품질 gate 전용이다.
- [../tools/analysis/compare_public20_dimensions.py](../tools/analysis/compare_public20_dimensions.py): Gate B public20/generated profile 비교 도구.
- [../tools/analysis/check_manifest_model_input_equivalence.py](../tools/analysis/check_manifest_model_input_equivalence.py): Gate C candidate/manifest/trainer-loader 입력 동등성 검증 도구.
- [../tools/datagen/parse_self_instruct_outputs.py](../tools/datagen/parse_self_instruct_outputs.py): raw LLM output을 candidate schema로 파싱/정규화하는 도구. 자체 synthetic 생성은 금지다.
- [../tools/analysis/dedup_self_instruct_candidates.py](../tools/analysis/dedup_self_instruct_candidates.py): Self-Instruct ROUGE-L/exact/conflict/public20 duplicate filter.
- [../tests/test_self_instruct_final_response_invariant.py](../tests/test_self_instruct_final_response_invariant.py): v4/v4.1 실패 모드 회귀 테스트.

## Agent 생성 시 붙일 짧은 Context Block

```text
공통 맥락:
- 목표는 LLM-only Opal verifier이며 architecture에 rule engine은 절대 넣지 않는다.
- 현재 병목은 데이터다. 검증 대상은 우리가 생성한 synthetic 데이터이며, 평균 dimension뿐 아니라 pass/fail이 final response 기준으로 질적으로 맞는지 sampling state-transition audit로 확인해야 한다.
- public20은 이미 주어진 기준 입력이다. public20 자체를 검증하지 말고, synthetic 데이터와 비교할 reference structure/profile 및 public20-only 모델 `train`/`val` 검증 소스로만 사용한다.
- public20-only 모델 검증 기본 split은 stratified 16 train / 4 val이며, val은 후보 선택/튜닝/early stopping용 내부 검증이다. test는 public20에서 만들지 않고 leaderboard hidden 평가로만 둔다.
- v4/v4.1 생성 데이터는 폐기/학습 금지다. 중간 Set FAIL 뒤 final EndSession SUCCESS인데 label fail인 문제가 archive되어 있다.
- active datagen은 Self-Instruct seed/candidate schema만 남긴다. v4/v4.1, spec/gap synthetic generator, ad-hoc fixture/smoke generator는 active tools에서 제거됐다.
- 새 데이터는 Wang et al. 2023 Self-Instruct 하나를 제대로 따른다: output-first classification generation, LLM-only judge filtering, quality audit/eval/ablation.
- Self-Instruct 공식 code source는 yizhongw/self-instruct이고 Apache-2.0이다. 현재는 vendor code 없이 문서 기준만 둔다.
- LLM 호출 없는 parse_self_instruct_outputs, ROUGE-L/exact/conflict dedup/filter, Gate C manifest/model input equivalence 도구를 먼저 둔다. 이후 LLM API generation wrapper와 LLM-only judge filtering을 붙인다.
- Gate A/B/C가 모두 통과하기 전에는 raw synthetic sample을 합격 데이터로 제시하지 않는다. 통과 후 `docs/samples/self_instruct_sample.md`에 trajectory 전체와 Gate A/B/C 요약을 기록한다.
- ad-hoc fixture/smoke generated data is not accepted synthetic data. sample.md는 Gate A/B/C를 통과한 Self-Instruct synthetic data에만 생성한다.
- synthetic 데이터 검증 완료 뒤 dataset은 train/val/test/public20_reference로 분리한다. public20-only 모델 후보 검증은 train/val만 쓰고, test는 leaderboard hidden 평가다.
- active docs update set은 README.md, PROGRESS.md, docs/README.md, docs/current_task.md, docs/current_self_instruct_data_plan.md, docs/agent_handoff.md, docs/samples/README.md 이다.
- Gate 순서: A synthetic 질적 state-transition audit, B public20 reference dimension/schema/pass-fail 분포 비교, C manifest/model input path equivalence, D leaderboard 제출 판단.
- 모델 후보 조사는 데이터 검증 이후 또는 병렬 보조로만 진행한다. RAG/FT 구현은 관련 논문과 검증된 라이브러리/코드를 따른다.
- 사용자 요청 중심 모델 후보는 Frozen RAG, 0.9B full FT, 4B QLoRA/LoRA selective FT, RAFT-style RAG+SFT/QLoRA다.
- agent가 추가한 sanity baseline은 non-training prompt/logprob baseline 하나뿐이며, 사용자 지시 후보처럼 취급하지 않는다.
- invariant checker/state-transition audit는 데이터 품질 gate이지 runtime rule engine이 아니다.
- 작업 root는 /Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst 이고 서버 기준 root는 /workspace/sinjeongmin_opal_verifier 이다.
- push 대상은 origin/sinjeongmin 이다.
- 기록은 한국어, 시간은 KST, secret/password 출력/저장 금지.
- 다른 사람 변경을 되돌리지 말고 destructive git command를 쓰지 않는다.
```

## Git/검증 기준

- 작업 전 `git status --short --branch`로 현재 변경을 확인한다.
- 관련 파일을 읽고 active/archive/delete 기준에 맞는지 먼저 판단한다.
- 코드나 문서를 수정하면 이유가 드러나도록 Changed/Why comment 또는 archive record를 남긴다.
- 최소 검증:
  - secret scan은 원문 출력 없이 수행한다.
  - `git diff --check`
  - 변경 관련 단위 테스트
  - `python3 -m unittest discover -s tests -v`
- push 전 `origin/sinjeongmin`에 올릴 commit 범위를 확인한다.
- push 후 local HEAD와 `origin/sinjeongmin`의 commit hash 일치를 확인한다.

## 이번 cycle의 다음 우선순위

- 새 Self-Instruct pipeline 구현 전에 Gate A-D를 실행 가능한 도구와 문서로 고정한다.
- public20 input-only와 local label reference는 확보됐다. 다음 agent는 public20을 synthetic 데이터 검증의 대상처럼 다루지 말고 dimension/schema/distribution reference로만 써야 한다. public20-only 모델 후보 검증에서는 `train`/`val`만 사용한다.
- public20 reference structure/profile audit pack은 `runs/self_instruct/public20_baseline/gate_a/public20_reference_audit_pack.md`에 있다. 이것은 public20 검증 결과가 아니라 reference 구조 확인용 pack이다. sample별 label은 노출하지 않았고 local label은 aggregate report에만 있다.
- 생성 candidate가 만들어지면 일부 sample을 직접 state-transition audit한 뒤에 `compare_public20_dimensions.py`로 public20 dimension 비교 report를 만든다.
- generated manifest 후보가 만들어지면 `check_manifest_model_input_equivalence.py`로 raw/normalized candidate, manifest, trainer loader가 같은 전체 trajectory 단위를 보는지 확인한다.
- 현재 Gate A/B/C를 통과한 generated candidate는 없다. 다음 단계는 real LLM output-first generation과 judge filtering을 논문 protocol에 맞게 구현하는 것이다.
- 단, LLM 호출 없는 공식-output parser, ROUGE-L/exact/conflict dedup/filter,
  Gate C manifest/model input equivalence를 먼저 둔 뒤 real LLM generation wrapper로 넘어간다.
- 서버 SSH는 main이 직접 치지 말고 agent가 10회 이상 재시도 단위로 수행한다.
- 서버가 회복되면 `/workspace/sinjeongmin_opal_verifier/repo`를 `origin/sinjeongmin` HEAD로 sync하고 기존 4B LoRA baseline 상태를 확인한다.
