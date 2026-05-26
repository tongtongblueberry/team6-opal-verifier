<!-- Changed: add official-source documentation for the Self-Instruct pipeline without vendoring code. -->
<!-- Why: synthetic generation must follow a verified paper/code path and must not reintroduce ad-hoc generators. -->

# Self-Instruct Official Source

이 디렉터리는 Self-Instruct 공식 출처와 차용 범위를 고정하기 위한 문서 전용 위치다.
현재는 공식 코드를 vendor하지 않는다. 코드 복사가 필요해지면 별도 commit에서 출처 commit
hash, license notice, 수정 범위, 검증 결과를 함께 기록한 뒤 진행한다.

## 공식 출처

[EXTERNAL KNOWLEDGE] Wang, Y., Kordi, Y., Mishra, S., Liu, A., Smith, N. A.,
Khashabi, D., & Hajishirzi, H. (2023). *Self-Instruct: Aligning language
models with self-generated instructions*. In A. Rogers, J. Boyd-Graber, &
N. Okazaki (Eds.), *Proceedings of the 61st Annual Meeting of the Association
for Computational Linguistics (Volume 1: Long Papers)* (pp. 13484-13508).
Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.754

- 논문 페이지: https://aclanthology.org/2023.acl-long.754/
- 공식 코드: https://github.com/yizhongw/self-instruct
- License: Apache-2.0

## 공식 Pipeline

Self-Instruct 공식 pipeline은 다음 단계로 구성된다.

1. Seed task에서 새 instruction 생성.
2. Classification task 여부 판정.
3. Classification task에는 output-first instance generation 적용.
4. Invalid, duplicate, conflicting, near-duplicate sample filtering.
5. Generated data quality audit.
6. Data size 및 data quality ablation.

우리 과제는 항상 `pass`/`fail` classification이므로 classification identification은
고정 `true`로 취급한다. 구현 대상은 output-first classification candidate generation,
filtering, quality audit, ablation이다.

## 차용 범위

차용할 수 있는 것은 다음이다.

- 공식 prompt 구조와 metadata 저장 방식.
- Classification output-first generation 절차.
- ROUGE-L 기반 near-duplicate filtering 원칙.
- Duplicate/conflicting instance 제거 원칙.
- Generated sample quality audit protocol.
- Data size/data quality ablation protocol.

## 금지 사항

- 공식 Self-Instruct 절차 없이 deterministic fixture/smoke generator를 active datagen에 두지 않는다.
- v4/v4.1, spec/gap generator를 재사용하지 않는다.
- 중간 실패 뒤 마지막 `EndSession SUCCESS`를 붙이고 label을 `fail`로 두는 데이터를 만들지 않는다.
- public20 label을 generation prompt, judge prompt, generated manifest target에 넣지 않는다.
- rule engine, rule id, archived verifier output으로 synthetic label을 만들지 않는다.
- Gate A/B/C 전 raw synthetic sample을 accepted training data처럼 공개하지 않는다.

## 다음 구현 순서

LLM 호출이 필요 없는 단계부터 구현한다.

1. `tools/datagen/parse_self_instruct_outputs.py`
   - 공식 output-first response를 candidate schema로 파싱한다.
   - secret/API response 원문 중 민감 정보는 기록하지 않는다.

2. `tools/analysis/dedup_self_instruct_candidates.py`
   - ROUGE-L, exact duplicate, conflicting label/input 제거를 수행한다.
   - public20 exact/near duplicate도 reject한다.

3. `tools/analysis/check_manifest_model_input_equivalence.py`
   - raw candidate, normalized candidate, manifest, training loader, first-forward input이 같은 trajectory 단위인지 검증한다.

4. 이후 `tools/datagen/run_self_instruct_generation.py`
   - LLM API generation wrapper를 붙인다.
   - 공식 Self-Instruct prompt/metadata 계약을 보존하고, 임의 fixture mode를 넣지 않는다.
