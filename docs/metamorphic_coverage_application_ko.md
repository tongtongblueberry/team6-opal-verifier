<!-- Added: document the selected paper and how its metrics/architecture map to this project. -->
<!-- Why: the next improvement loop should follow one concrete paper instead of mixing methods loosely. -->

> **NOTE: This document reflects an earlier project phase (pre-71.50).** The metamorphic coverage
> metrics (MC, mutation score) described here were applied and contributed to reaching 71.50.
> The diagnostic tools (`tools/metamorphic_coverage.py`, `tools/mutation_eval.py`) remain in use.
> See `PROGRESS.md` for current state.

# Metamorphic Coverage 논문 적용 계획

작성일: 2026-05-18

## 선택한 논문

[EXTERNAL KNOWLEDGE] Ba, J., Jiang, Y., & Rigger, M. (2025). *Metamorphic coverage*. arXiv. https://doi.org/10.48550/arXiv.2508.16307

링크:

- arXiv: https://arxiv.org/abs/2508.16307
- PDF: https://arxiv.org/pdf/2508.16307

## 왜 이 논문인가

[Original Text/Data] → 현재 `c613397`은 public `20/20`, metamorphic `1821/1821`, rule coverage `low_confidence=0`이지만 leaderboard는 `69.50`에서 오르지 않았다.

[Exact Interpretation] → 기존 지표가 포화되어 hidden gap을 더 이상 잘 드러내지 못하고 있다. 따라서 pass rate나 coverage grid의 크기를 더 키우는 것보다, source/follow-up pair가 실제로 서로 다른 rule/state path를 검증하는지 봐야 한다.

[Detailed Explanation/Example] → 같은 final status mutation을 수백 개 늘려도 trace가 같은 `UNEXPECTED_ERROR_STATUS` 또는 같은 `KNOWN_FIELD_EXPECTED_SUCCESS`만 반복하면 새 hidden rule을 찾지 못한다. 반대로 source와 follow-up이 서로 다른 rule/state path를 타면, 그 pair가 더 많은 bug/fault boundary를 건드릴 가능성이 높다.

## 논문의 핵심 metric

### 1. Metamorphic Coverage

[Original Text/Data] → 논문은 source input `ta`와 follow-up input `tb`의 coverage를 각각 `Cov(ta)`, `Cov(tb)`라고 두고, `MC(t) = Cov(ta) △ Cov(tb)`로 정의한다. `△`는 symmetric difference다.

[Exact Interpretation] → 두 입력이 공통으로 실행한 부분은 일반 coverage에는 잡히지만, metamorphic relation이 실제로 검증한 차이점으로 보기 어렵다. 논문은 서로 다르게 실행된 coverage가 bug 발견 가능성을 더 잘 설명한다고 본다.

[Detailed Explanation/Example] → 같은 line coverage 100%인 두 metamorphic relation이라도, 한 relation은 source/follow-up이 서로 다른 branch를 타고 다른 relation은 같은 branch만 탈 수 있다. line coverage는 둘을 구분하지 못하지만 MC는 구분한다.

우리 적용:

- `Cov(trajectory)`를 code line이 아니라 solver trace feature로 정의한다.
- trace feature:
  - `rule:<rule_id>`
  - `rule_transition:<rule_a>-><rule_b>`
  - `read:<state_read>`
  - `write:<state_write>`
  - `rule_read:<rule_id>:<state_read>`
  - `rule_write:<rule_id>:<state_write>`
  - `final_method:<method>`
  - `final_object_kind:<kind>`
  - `final_status:<status>`
  - `prediction:<pass|fail>`
- `MC(pair)`는 source public prefix trace와 synthetic follow-up trace의 symmetric difference다.

### 2. Mutation Score

[Original Text/Data] → 논문은 mutation score를 `killed mutants / total mutants`로 설명하고, 좋은 test suite는 더 많은 mutant를 kill해야 한다고 본다. 다만 mutation testing은 비용이 커서 MC를 더 lightweight한 a priori metric으로 제안한다.

[Exact Interpretation] → mutation score는 여전히 강한 기준이지만, 매번 쓰기에는 비용이 크다. MC는 mutation score 전 단계에서 어떤 metamorphic pair가 더 유망한지 고르는 기준이다.

[Detailed Explanation/Example] → 우리 프로젝트에서는 solver rule을 삭제/약화한 mutant를 만들 수 있다. 예를 들어 `GET_PAYLOAD` requested-column check를 제거했을 때 synthetic suite가 실패를 유도하면 그 mutant는 killed다.

우리 적용:

- 이번 적용에서는 먼저 lightweight MC를 추가했다.
- 다음 단계에서 `tools/mutation_eval.py`로 mutation score를 추가한다.

### 3. Sensitivity

[Original Text/Data] → 논문은 metric의 민감도를 coefficient of variation, 즉 `CV = sigma / mu`로 비교한다. MC는 line coverage보다 평균적으로 더 민감했다고 보고한다.

[Exact Interpretation] → 단순히 coverage 크기가 큰 metric보다, 서로 다른 metamorphic relation의 품질 차이를 더 잘 벌려 주는 metric이 유용하다.

[Detailed Explanation/Example] → 모든 relation의 일반 coverage가 비슷하면 coverage metric은 포화된다. 하지만 relation별 MC 평균이 다르면 어떤 relation이 더 다양한 state/rule path를 검증하는지 볼 수 있다.

우리 적용:

- `mc_cv_by_relation`: relation별 평균 MC size의 CV.
- `coverage_cv_by_relation`: relation별 일반 union coverage size의 CV.
- `mc_cv_by_relation`이 더 높으면 MC가 기존 coverage보다 relation 차이를 더 잘 분리한다고 해석한다.

### 4. Time / Efficiency

[Original Text/Data] → 논문은 MC가 mutation score보다 훨씬 가볍고, line coverage와 같은 magnitude의 비용이라고 보고한다.

[Exact Interpretation] → leaderboard 제출 전 매번 실행 가능한 진단이어야 한다.

[Detailed Explanation/Example] → 우리 MC 도구는 solver trace를 기존 synthetic cases에 대해 한 번 더 실행하는 수준이다. 모델 다운로드나 재학습은 없다.

## 논문의 architecture

논문 architecture를 우리 프로젝트에 맞추면 다음과 같다.

1. Source input 수집
   - 논문: metamorphic source test input.
   - 우리: public trajectory 또는 public prefix.

2. Follow-up input 생성
   - 논문: metamorphic relation으로 변환한 input.
   - 우리: `tools/metamorphic_eval.py`가 만든 synthetic positive/negative trajectory.

3. Coverage 수집
   - 논문: line/branch/function coverage.
   - 우리: `StatefulOpalVerifier.verify_with_trace()`의 rule/state/spec trace.

4. Differential coverage 계산
   - 논문: `Cov(ta) △ Cov(tb)`.
   - 우리: `source_trace_features △ followup_trace_features`.

5. Guidance
   - 논문: MC가 증가하지 않으면 test input generation을 바꾼다.
   - 우리: MC가 낮거나 zero인 relation은 case 수를 늘리지 않고 relation 자체를 재설계한다. MC가 높은 relation은 hidden gap 탐지 후보로 우선 유지한다.

## Loss / 학습 방법

[Original Text/Data] → 이 논문은 neural model 학습 논문이 아니라 metamorphic testing metric 논문이다.

[Exact Interpretation] → loss function, optimizer, fine-tuning architecture는 없다. 여기서 "학습"에 해당하는 부분은 feedback-guided test generation이다.

[Detailed Explanation/Example] → 논문은 model parameter를 gradient로 업데이트하지 않는다. 대신 coverage/MC가 증가하는 test generation 방향을 선택한다. 우리도 Qwen fine-tuning을 하지 않고, MC feedback으로 synthetic relation과 rule extraction 우선순위를 조정한다.

## 구현 반영

추가 파일:

- `tools/metamorphic_coverage.py`

실행:

```bash
python3 tools/metamorphic_coverage.py \
  --dataset-root /dl2026/dataset \
  --out reports/metamorphic_coverage_<commit>.json \
  --jsonl-out reports/metamorphic_coverage_<commit>.jsonl
```

출력 핵심:

- `pairs`: source/follow-up pair 수.
- `correct`: 기존 metamorphic expected label과 solver prediction 일치 수.
- `identity_pairs`: source와 follow-up이 완전히 같은 회귀용 positive control 수.
- `guidance_pairs`: MC guidance에 실제로 쓰는 non-identity pair 수.
- `mean_pair_mc_size`: pair별 MC size 평균.
- `zero_mc_pairs`: non-identity pair 중 differential feature가 없는 pair 수.
- `mc_cv_by_relation`: relation별 MC 민감도.
- `coverage_cv_by_relation`: relation별 일반 coverage 민감도.
- `low_mc_relations`: relation 재설계 우선순위.
- `high_mc_relations`: hidden gap 탐지에 유망한 relation.

## 서버 적용 결과

[Original Text/Data] → 서버 `/dl2026/dataset`에서 `tools/metamorphic_coverage.py`를 실행했다. 결과는 `pairs=1821`, `correct=1821/1821`, `identity_pairs=195`, `guidance_pairs=1626`, `mean_pair_mc_size=5.67`, `zero_mc_pairs=245`, `mc_cv_by_relation=0.77`, `coverage_cv_by_relation=0.32`였다.

[Exact Interpretation] → MC가 일반 union coverage보다 relation 간 차이를 더 잘 분리한다. `mc_cv_by_relation=0.77`이 `coverage_cv_by_relation=0.32`보다 높기 때문이다. 동시에 non-identity pair 중 `245`개는 differential trace feature가 없어서, 기존 metamorphic pass rate 100%가 hidden gap 탐지력을 충분히 의미하지 않는다는 점을 보여준다.

[Detailed Explanation/Example] → low-MC relation에는 `endsession_no_session_success`, `get_no_session_success`, `known_pin_success`가 포함됐다. 이들은 regression check로는 쓸 수 있지만, source/follow-up trace가 거의 같은 rule path를 타므로 MC-guided rule discovery에는 약하다. high-MC relation은 `known_cpin_get_*`, `known_cpin_set_*`, `known_locking_get_*`, `known_mbrcontrol_get_*`였다. 즉 현재 synthetic suite는 field-status mutation 쪽 differential coverage가 크고, session/precondition 계열 일부는 relation 재설계가 필요하다.

## 다음 적용 기준

1. `identity_pairs`는 회귀용 positive control로 유지하되 MC guidance 해석에서는 제외한다.
2. `zero_mc_pairs`가 있으면 해당 relation은 제거하거나 source/follow-up 설계를 바꾼다.
3. `low_mc_relations`는 case 수를 늘리지 않는다. relation 자체가 같은 path를 반복할 가능성이 높다.
4. `high_mc_relations` 주변에서 guidebook rule extraction을 확장한다.
5. 이후 mutation score를 추가해 MC가 실제 rule mutant kill과 맞는지 확인한다.
