# 2026-05-26 KST Invalid Fixture Smoke Removed

<!-- Changed: archive the removal decision for ad-hoc fixture/smoke generated data. -->
<!-- Why: synthetic data must be paper-protocol based and must not be confused with deterministic plumbing fixtures. -->

## 결정

- 2026-05-26 16:37 KST 기준, `tools/datagen/generate_self_instruct_candidates.py`,
  `tests/test_generate_self_instruct_candidates.py`, `runs/self_instruct/fixture_smoke/`
  산출물을 폐기 대상으로 확정했다.
- 이유: 해당 fixture/smoke는 논문 기반 Self-Instruct generation도 아니고, 검증된 코드 기반
  synthetic data generation도 아니다.
- 학습, 검증, leaderboard 제출 판단, `docs/samples/self_instruct_sample.md` 공개 근거로
  사용하지 않는다.

## 재발 방지 기준

- ad-hoc fixture/smoke generated data is not accepted synthetic data.
- 앞으로 synthetic generation은 선택 논문 방법론과 평가 protocol을 따르는 후보만 허용한다.
- 현재 선택 논문 기준은 Wang et al. 2023 Self-Instruct의 output-first classification
  generation, LLM-only judge filtering, quality audit/evaluation/ablation 절차다.
- `sample.md`는 Gate A qualitative state-transition audit, Gate B public20 reference
  dimension comparison, Gate C manifest/model-input equivalence를 모두 통과한 synthetic
  data에 대해서만 생성한다.

## 제거 범위

- active datagen generator: `tools/datagen/generate_self_instruct_candidates.py`
- 관련 테스트: `tests/test_generate_self_instruct_candidates.py`
- 관련 runs 산출물: `runs/self_instruct/fixture_smoke/`
- active docs의 fixture/smoke 유효 단계 표현

## 현재 상태

- active `tools/datagen/`에는 Self-Instruct seed/candidate schema만 둔다.
- 실제 candidate generation 구현은 논문 protocol과 검증된 library/reference code 기준을
  먼저 세운 뒤 별도 agent가 구현한다.
