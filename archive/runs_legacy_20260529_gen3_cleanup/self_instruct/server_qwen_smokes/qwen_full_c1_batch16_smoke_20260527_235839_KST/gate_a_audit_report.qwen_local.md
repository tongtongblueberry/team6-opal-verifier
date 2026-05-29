# Gate A Self-Instruct Quality Audit Report

이 문서는 offline 데이터 품질 gate 결과다. rule engine, runtime architecture, solver fallback이 아니다.
이 입력은 generated synthetic candidate pool이며 state-transition audit decision을 채워야 한다.

- 생성 시각(KST): 2026-05-28T09:11:41+09:00
- status: `pending-qualitative-state-transition-audit`
- training_use: `pending-gate-a-human-or-llm-judge-review`
- sample_md_policy: `create-only-after-gate-a-b-c-pass`
- 입력 JSONL: `runs/self_instruct/qwen_full_c1_batch16_smoke_20260527_235839_KST/judge_accepted_candidates.qwen_local.jsonl`
- 전체 candidate 수: 8
- hard invariant pass 수: 8
- hard invariant fail 수: 0
- 요청 sample 수: 5
- 실제 audit pack sample 수: 5
- seed: 20260528

## Label 분포

- Accepted pool: `{"fail": 1, "pass": 7}`
- Audit sample: `{"fail": 1, "pass": 4}`

## Hard Invariant Failures

- 없음

## Audit Pack Targets

- line 6, sample_id `self-instruct-gen-00013-cand-00`, label `fail`, final `EndSession/NOT_AUTHORIZED`
- line 5, sample_id `self-instruct-gen-00012-cand-00`, label `pass`, final `StartSession/SUCCESS`
- line 3, sample_id `self-instruct-gen-00006-cand-00`, label `pass`, final `StartSession/SUCCESS`
- line 7, sample_id `self-instruct-gen-00014-cand-00`, label `pass`, final `Activate/SUCCESS`
- line 8, sample_id `self-instruct-gen-00016-cand-00`, label `pass`, final `EndSession/SUCCESS`
