# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-30T07:50:53+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/new/local_mirror/combined/accepted.jsonl`
- 전체 candidate 수: 213
- hard invariant pass 수: 213
- hard invariant fail 수: 0
- 요청 sample 수: 40
- 실제 audit pack sample 수: 40
- seed: 20260529

## Label 분포

- Accepted pool: `{"fail": 70, "pass": 143}`
- Audit sample: `{"fail": 1, "pass": 39}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- line 52, sample_id `req_RULE_03_fail_003_c0`, label `fail`, final `StartSession/SUCCESS`
- line 178, sample_id `req_RULE_22_pass_002_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 19, sample_id `req_RULE_01_pass_002_c0`, label `pass`, final `Get/SUCCESS`
- line 137, sample_id `req_RULE_15_pass_001_c0`, label `pass`, final `Get/INVALID_PARAMETER`
- line 95, sample_id `req_RULE_05_pass_001_c0`, label `pass`, final `StartSession/SP_FROZEN`
- line 104, sample_id `req_RULE_06_pass_000_c0`, label `pass`, final `StartSession/NO_SESSIONS_AVAILABLE`
- line 148, sample_id `req_RULE_17_pass_002_c0`, label `pass`, final `Get/FAIL`
- line 195, sample_id `req_RULE_26_pass_002_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 172, sample_id `req_RULE_20_pass_001_c0`, label `pass`, final `EndSession/SUCCESS`
- line 121, sample_id `req_RULE_09_pass_001_c0`, label `pass`, final `Properties/SUCCESS`
- line 37, sample_id `req_RULE_02_pass_003_c0`, label `pass`, final `Set/NOT_AUTHORIZED`
- line 81, sample_id `req_RULE_04_pass_000_c0`, label `pass`, final `StartSession/SP_BUSY`
- line 62, sample_id `req_RULE_03_pass_001_c0`, label `pass`, final `StartSession/NOT_AUTHORIZED`
- line 177, sample_id `req_RULE_22_pass_001_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 30, sample_id `req_RULE_02_pass_000_c0`, label `pass`, final `Set/NOT_AUTHORIZED`
- line 16, sample_id `req_RULE_01_pass_000_c0`, label `pass`, final `Get/SUCCESS`
- line 83, sample_id `req_RULE_04_pass_001_c0`, label `pass`, final `StartSession/SP_BUSY`
- line 116, sample_id `req_RULE_08_pass_001_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 200, sample_id `req_RULE_30_pass_000_c0`, label `pass`, final `Properties/INVALID_PARAMETER`
- line 110, sample_id `req_RULE_07_pass_002_c0`, label `pass`, final `StartSession/INVALID_PARAMETER`
- line 120, sample_id `req_RULE_08_pass_006_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 192, sample_id `req_RULE_25_pass_003_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 191, sample_id `req_RULE_25_pass_002_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 135, sample_id `req_RULE_13_pass_000_c0`, label `pass`, final `StartSession/SUCCESS`
- line 70, sample_id `req_RULE_03_pass_003_c0`, label `pass`, final `StartSession/NOT_AUTHORIZED`
- line 71, sample_id `req_RULE_03_pass_003_c0`, label `pass`, final `StartSession/NOT_AUTHORIZED`
- line 179, sample_id `req_RULE_22_pass_003_c0`, label `pass`, final `Set/INVALID_PARAMETER`
- line 20, sample_id `req_RULE_01_pass_002_c0`, label `pass`, final `Get/SUCCESS`
- line 138, sample_id `req_RULE_15_pass_002_c0`, label `pass`, final `Get/FAIL`
- line 169, sample_id `req_RULE_19_pass_004_c0`, label `pass`, final `Get/SUCCESS`
- line 159, sample_id `req_RULE_18_pass_002_c0`, label `pass`, final `Get/SUCCESS`
- line 124, sample_id `req_RULE_11_pass_001_c0`, label `pass`, final `Set/SUCCESS`
- line 100, sample_id `req_RULE_05_pass_004_c0`, label `pass`, final `StartSession/SP_FROZEN`
- line 84, sample_id `req_RULE_04_pass_002_c0`, label `pass`, final `StartSession/SP_BUSY`
- line 207, sample_id `req_RULE_38_pass_001_c0`, label `pass`, final `Get/SUCCESS`
- line 141, sample_id `req_RULE_16_pass_001_c0`, label `pass`, final `Get/FAIL`
- line 86, sample_id `req_RULE_04_pass_003_c0`, label `pass`, final `StartSession/SP_BUSY`
- line 174, sample_id `req_RULE_20_pass_003_c0`, label `pass`, final `EndSession/SUCCESS`
- line 139, sample_id `req_RULE_15_pass_004_c0`, label `pass`, final `Get/INVALID_PARAMETER`
- line 22, sample_id `req_RULE_01_pass_003_c0`, label `pass`, final `Set/SUCCESS`
