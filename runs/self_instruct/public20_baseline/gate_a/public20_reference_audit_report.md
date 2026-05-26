# Public20 Reference Qualitative Audit Report

이 문서는 public20을 실제 입력 구조 reference로 검수하기 위한 offline 데이터 품질 산출물이다.
rule engine, runtime verifier, solver fallback이 아니며 LLM-only architecture에 포함되지 않는다.

- 생성 시각(KST): 2026-05-26T15:59:18+09:00
- normalized JSONL: `runs/self_instruct/public20_baseline/gate_b/public20.normalized.jsonl`
- profile JSON: `runs/self_instruct/public20_baseline/gate_b/public20.profile.json`
- 전체 public20 row 수: 20
- audit pack sample 수: 20

## 사용 금지 정책

- local-only label은 aggregate reference/evaluation summary에만 사용한다.
- generation prompt, judge prompt, training manifest에는 public20 row-level label을 넣지 않는다.
- audit pack에는 sample별 label을 노출하지 않는다.

## Profile Summary

- count: `20`
- final_method_counts: `{"Activate": 1, "Get": 6, "Properties": 2, "Read": 2, "Set": 2, "StartSession": 7}`
- final_status_counts: `{"8E": 1, "FAIL": 1, "INVALID_PARAMETER": 3, "NOT_AUTHORIZED": 3, "RANDOM DATA": 1, "SUCCESS": 11}`

## Local-Only Label Aggregate

`{"available": true, "extra_label_ids": [], "label_distribution": {"fail": 10, "pass": 10}, "missing_input_ids": [], "policy": "local-only aggregate for reference/evaluation only; never use row labels in generation prompts, judge prompts, or training manifests.", "row_count": 20, "sample_id_match": true}`

## Audit Targets

- sample_id `tc1`, records `1`, final `Properties/SUCCESS`
- sample_id `tc2`, records `2`, final `Get/SUCCESS`
- sample_id `tc3`, records `7`, final `StartSession/SUCCESS`
- sample_id `tc4`, records `10`, final `StartSession/SUCCESS`
- sample_id `tc5`, records `11`, final `StartSession/SUCCESS`
- sample_id `tc6`, records `21`, final `Set/SUCCESS`
- sample_id `tc7`, records `26`, final `StartSession/SUCCESS`
- sample_id `tc8`, records `21`, final `Get/SUCCESS`
- sample_id `tc9`, records `27`, final `Get/SUCCESS`
- sample_id `tc10`, records `39`, final `Read/RANDOM DATA`
- sample_id `tc11`, records `1`, final `Properties/INVALID_PARAMETER`
- sample_id `tc12`, records `2`, final `Get/NOT_AUTHORIZED`
- sample_id `tc13`, records `7`, final `StartSession/NOT_AUTHORIZED`
- sample_id `tc14`, records `10`, final `StartSession/SUCCESS`
- sample_id `tc15`, records `9`, final `Activate/SUCCESS`
- sample_id `tc16`, records `21`, final `Set/INVALID_PARAMETER`
- sample_id `tc17`, records `26`, final `StartSession/NOT_AUTHORIZED`
- sample_id `tc18`, records `21`, final `Get/INVALID_PARAMETER`
- sample_id `tc19`, records `27`, final `Get/FAIL`
- sample_id `tc20`, records `39`, final `Read/8E`
