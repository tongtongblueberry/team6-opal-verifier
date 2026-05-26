# public20 profile verification report

- 입력 행 수: 20
- label 행 수: 20
- 실제 public20 포맷: `sample_id + input(JSON string containing records) + source`
- `self_instruct_seed_schema.py` 결과: 실패 (`instruction_missing`)
- `public20.normalized.jsonl` 생성: 아니오
- `public20.profile.json` 생성: 아니오
- raw-format profile 생성: `public20_raw_format_profile.json`
- label 분포(local eval reference only): {'fail': 10, 'pass': 10}
- record_count min/mean/max: 1/16.40/39
- input_json_chars min/mean/max: 429/6911.30/15256
- final_method_counts: {'': 2, 'Activate': 1, 'Get': 6, 'Properties': 2, 'Set': 2, 'StartSession': 7}
- schema extraction warnings: 2 rows (tc10, tc20)
- final_status_counts: {'': 2, 'FAIL': 1, 'INVALID_PARAMETER': 3, 'NOT_AUTHORIZED': 3, 'SUCCESS': 11}

## sample 1 summary

- sample_id: tc1
- record_count: 1
- final_method/status: Properties/SUCCESS
- method/status sequence: [{'method': 'Properties', 'status': 'SUCCESS'}]

주의: label 파일은 generation/training prompt 또는 manifest 입력으로 사용하지 않았다.
