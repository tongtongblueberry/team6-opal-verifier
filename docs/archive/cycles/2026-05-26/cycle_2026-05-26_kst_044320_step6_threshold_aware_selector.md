# 2026-05-26 KST 04:43 - Cycle 3 Step 6 threshold-aware selector 추가

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- code commit: `bedbac4 add threshold aware sweep selector`
- local tool: `tools/eval/select_manifest_sweep_candidate.py`
- local test: `tests/test_select_manifest_sweep_candidate.py`
- server deployed tool: `/workspace/team6/team6-opal-verifier/tools/eval/select_manifest_sweep_candidate.py`
- server report:
  - `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep/artifacts/threshold_aware_candidate.json`
  - `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep/artifacts/threshold_aware_candidate.md`

## 변경 이유

[Original Text/Data] → `run_manifest_lora_sweep.py`의 `best`는 `metrics.by_split.hidden.accuracy`를 기본 threshold `0.50`에서 고르고, fail precision/recall 제약도 기본 threshold metric으로만 적용한다.

[Exact Interpretation] → 실제 제출 solver 기본 threshold가 `0.70`이고 eval report에는 threshold sweep이 존재하므로, runner의 `best`만으로 제출 후보를 확정하면 평가 기준과 runtime threshold가 어긋날 수 있다.

[Detailed Explanation/Example] → 현재 3개 r16 완료 결과 기준 runner best는 `r16_lr1e3_do05_ep5@0.50`이지만, threshold-aware hidden accuracy 최고 후보는 `r16_lr5e4_do10_ep5@0.70`이다. 둘은 adapter와 threshold가 다르므로 최종 packaging 전에 분리 기록이 필요하다.

## 구현 내용

[Original Text/Data] → `tools/eval/select_manifest_sweep_candidate.py`는 `manifest_lora_sweep_results.json`과 각 `eval_manifest.json`의 `threshold_sweep.metrics_by_threshold`를 다시 읽는다.

[Exact Interpretation] → 이 도구는 학습이나 solver runtime을 실행하지 않는 JSON-only 후처리다.

[Detailed Explanation/Example] → `solver`, verifier, rule module, model load를 import하지 않는다. hidden split에서 `precision_fail >= 0.90`, `recall_fail >= 0.80`을 만족하는 threshold 후보만 `best`로 고르고, runner의 base-threshold best는 `base_threshold_best`로 별도 보관한다.

## 검증

[Original Text/Data] → 로컬 검증: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`.

[Exact Interpretation] → 전체 unit test 32개가 통과했다.

[Detailed Explanation/Example] → 추가 테스트는 eval summary cache가 아니라 실제 eval JSON을 다시 읽는지, 제약 불만족 시 `best=None`인지, Markdown report가 생성되는지를 확인한다.

[Original Text/Data] → 서버 검증: `python3 tools/eval/select_manifest_sweep_candidate.py --sweep-json ... --output-json ... --output-md ... --format markdown`.

[Exact Interpretation] → 3개 완료 r16 결과 기준 threshold-aware 리포트 생성이 성공했다.

[Detailed Explanation/Example] → 후보 threshold 수는 `27`, 제약 만족 threshold 수는 `12`였다. 현재 threshold-aware best는 `r16_lr5e4_do10_ep5@0.70`, hidden accuracy `0.968421`, fail precision `0.954545`, fail recall `0.976744`, Brier `0.038745`, ECE `0.045576`이다.

## 중간 결정

- r32/r64 결과가 완료되기 전까지 최종 best adapter를 확정하지 않는다.
- 전체 sweep 완료 후 이 selector를 다시 실행해 threshold-aware best를 갱신한다.
- 제출 후보 package에는 최종 threshold를 명시적으로 고정해야 한다. 현재 best가 `0.70`이면 solver 기본값과 일치하지만, 최종 best가 다른 threshold면 packaging 단계에서 threshold lock을 별도 검증한다.
- leaderboard 제출은 아직 NO-GO. sweep 완료, best merged package 생성, static/runtime gate PASS, server availability 확인이 필요하다.
