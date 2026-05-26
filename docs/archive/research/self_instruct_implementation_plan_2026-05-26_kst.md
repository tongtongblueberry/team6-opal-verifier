<!-- Changed: archive the official Self-Instruct implementation decision. -->
<!-- Why: future workers need the source-backed rationale and must not recreate ad-hoc synthetic generation. -->

# Self-Instruct 공식 구현 계획

- 작성일: 2026-05-26 KST
- 목적: Opal trajectory `final response` pass/fail synthetic data를 Self-Instruct 공식 논문/공식 코드 기반으로만 생성하도록 기준을 고정한다.

## 결론

Self-Instruct를 계속 선택한다. 단, 새 데이터를 임의 template이나 fixture로 찍어내지 않는다.
공식 Self-Instruct 절차 중 우리 과제에 맞는 부분만 좁혀 사용한다.

## 공식 출처

[EXTERNAL KNOWLEDGE] Wang, Y., Kordi, Y., Mishra, S., Liu, A., Smith, N. A.,
Khashabi, D., & Hajishirzi, H. (2023). *Self-Instruct: Aligning language
models with self-generated instructions*. In A. Rogers, J. Boyd-Graber, &
N. Okazaki (Eds.), *Proceedings of the 61st Annual Meeting of the Association
for Computational Linguistics (Volume 1: Long Papers)* (pp. 13484-13508).
Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.754

- 논문: https://aclanthology.org/2023.acl-long.754/
- 공식 코드: https://github.com/yizhongw/self-instruct
- License: Apache-2.0

## 우리 과제 대응

[Original Text/Data] Self-Instruct 공식 pipeline은 instruction generation,
classification identification, instance generation, filtering, quality audit,
ablation으로 구성된다. → [Exact Interpretation] 우리 과제는 항상 `pass`/`fail`
classification이므로 classification identification은 고정 `true`로 둔다. →
[Detailed Explanation/Example] 새 candidate는 target label을 먼저 만들고, 마지막
response가 그 label을 직접 뒷받침하도록 output-first로 생성해야 한다.

[Original Text/Data] public20은 이미 주어진 기준 입력이며 label reference는 local-only다.
→ [Exact Interpretation] public20 label은 synthetic generation, judge, generated
manifest target에 쓰면 안 된다. → [Detailed Explanation/Example] public20 label은
Gate B aggregate distribution 비교와 public20-only `train`/`val` 모델 검증 artifact의
train target/val metric에만 사용한다.

[Original Text/Data] v4/v4.1은 중간 실패 뒤 마지막 `EndSession SUCCESS`인데 label이
`fail`인 sample을 만들었다. → [Exact Interpretation] label target이 final response가
아니라 중간 event로 밀린 데이터다. → [Detailed Explanation/Example] 새 pipeline은
`target.final_response_index == len(records)-1`과 `primary_evidence.record_index ==
len(records)-1`을 hard gate로 둔다.

## 구현 순서

LLM 호출 없는 검증/파싱 도구를 먼저 구현한다.

1. `parse_self_instruct_outputs`
   - 공식 output-first response를 candidate schema로 파싱한다.
   - generated label, target, primary evidence, records를 명시한다.

2. `dedup/filter candidates`
   - ROUGE-L near duplicate, exact duplicate, same input conflicting label, public20 near duplicate를 제거한다.
   - rule-engine/rule-id marker와 archived verifier output은 reject한다.

3. `Gate C manifest/model input equivalence`
   - raw candidate에서 manifest, trainer/eval/submission input까지 같은 trajectory 단위가 유지되는지 확인한다.

4. `LLM API generation wrapper`
   - 공식 Self-Instruct prompt/metadata 계약을 따른다.
   - API key나 secret은 출력/저장하지 않는다.
   - deterministic fixture/smoke mode는 금지한다.

## 검증 Gate

- Gate A: generated candidate를 label별 stratified sample로 뽑아 state-transition을 직접 검수한다.
- Gate B: public20 reference와 record count, input chars/tokens, method/status sequence, return value count, pass/fail distribution을 비교한다.
- Gate C: manifest/model input equivalence를 확인한다.
- Gate D: Gate A/B/C와 package/runtime/secret/no-rule gate가 모두 통과할 때만 leaderboard 제출을 판단한다.

## 금지 사항

- ad-hoc fixture/smoke generator.
- v4/v4.1 또는 spec/gap generator 재사용.
- public20 label을 synthetic generation/judge/generated target에 넣기.
- rule engine이나 rule id 기반 label 생성.
- Gate A/B/C 전 raw synthetic sample을 accepted data로 공개하기.
