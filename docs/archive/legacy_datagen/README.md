# Legacy datagen 정리 기록

- 작성 시각: 2026-05-26 15:02 KST
- 범위: active `tools/datagen/` 표면 정리
- 결론: 현재 데이터 생성 경로는 Self-Instruct input-only seed schema와 label-bearing candidate schema만 active로 둔다.

## 삭제한 active datagen

[Original Text/Data] `tools/datagen/generate_long_trajectories.py`와 `tools/datagen/generate_long_shape_source.py`는 v4/v4.1 long trajectory 및 shape-source 생성기였다.
→ [Exact Interpretation] 이 두 파일은 final-response label alignment 문제로 학습 금지/폐기된 경로다.
→ [Detailed Explanation/Example] 실패 근거는 [v4/v4.1 데이터 폐기 판단](../cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md)에 남겼다. 원천 fail 538개 중 440개가 마지막 `EndSession SUCCESS`로 끝났고, 일부 row는 중간 `Set FAIL`을 label 근거로 삼으면서 final response는 success였다.

[Original Text/Data] `tools/datagen/generate_spec_data.py`와 `tools/datagen/generate_gap_data.py`는 spec/gap synthetic generator였다.
→ [Exact Interpretation] 새 경로가 Wang et al. 2023 Self-Instruct 하나로 고정되었으므로 active datagen에 남기지 않는다.
→ [Detailed Explanation/Example] 과거 spec/gap generator의 rule/spec 지식 인코딩 문제와 public seed hard-fail 변경 내역은 [legacy architecture audit](../legacy/legacy_architecture_audit.md) 및 [public seed cleanup cycle](../cycles/2026-05-26/cycle_2026-05-26_kst_124500_rule_prompt_public_seed_cleanup.md)에 이미 남아 있다.

## 삭제한 active 테스트

[Original Text/Data] `tests/test_generate_long_shape_source.py`, `tests/test_generate_spec_data_cli.py`, `tests/test_generate_gap_data_defaults.py`는 위 삭제 파일의 active 회귀 테스트였다.
→ [Exact Interpretation] 삭제된 generator를 active test surface에서 계속 검증하면 현재 목표와 맞지 않는 경로를 유지하게 된다.
→ [Detailed Explanation/Example] Self-Instruct 경로의 회귀는 `tests/test_self_instruct_seed_schema.py`, `tests/test_self_instruct_candidate_schema.py`, `tests/test_self_instruct_final_response_invariant.py`가 담당한다.

## 현재 active datagen

[Original Text/Data] active `tools/datagen/`에는 `self_instruct_seed_schema.py`, `self_instruct_candidate_schema.py`, `__init__.py`만 남긴다.
→ [Exact Interpretation] public20 input-only seed와 generated label-bearing candidate의 schema contract만 현재 datagen surface다.
→ [Detailed Explanation/Example] 실제 candidate generation, judge filtering, Gate A/B/C 도구는 별도 구현 대상이며, deprecated v4/v4.1 또는 spec/gap generator를 import하면 안 된다.
