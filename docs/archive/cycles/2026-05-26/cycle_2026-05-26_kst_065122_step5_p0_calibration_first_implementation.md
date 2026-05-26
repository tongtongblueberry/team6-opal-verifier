# 2026-05-26 KST 06:51:22 - Step5 P0 calibration-first 구현 결과

## 구조 Skeleton
- 목적
- 변경 파일
- 구현 내용
- 검증 agent 결론
- 테스트
- 영향
- 다음 결정

## 목적
- Step4에서 확정한 P0 방법을 코드로 구현했다.
- 목표는 hidden split으로 threshold를 고르는 selection bias를 줄이고, calibration-first 후보 선택과 risk/coverage report를 가능하게 하는 것이다.
- architecture는 LLM-only이며 rule engine을 포함하지 않는다.

## 변경 파일
- `tools/eval/eval_manifest_adapter.py`
- `tools/eval/select_manifest_sweep_candidate.py`
- `tools/training/run_manifest_lora_sweep.py`
- `tests/test_eval_manifest_adapter_metrics.py`
- `tests/test_select_manifest_sweep_candidate.py`
- `tests/test_run_manifest_lora_sweep.py`

## 구현 내용
### eval metric
- `compute_selective_risk_metrics()`를 추가했다.
- threshold sweep entry에 다음 값을 추가했다.
  - `coverage`
  - `risk_error_rate`
  - `false_positive_rate`
  - `false_positives_per_100`
  - `fail_coverage`
- `compute_risk_coverage_summary()`를 추가했다.
  - `aurc`
  - `full_coverage_risk_error_rate`
  - `max_coverage_at_zero_error`
- Markdown threshold sweep table에도 risk/coverage 값을 노출한다.
- 기존 p_fail prediction을 재사용하므로 model inference data flow는 바뀌지 않는다.

### calibration-first selector
- `tools/eval/select_manifest_sweep_candidate.py`의 default split을 `hidden`에서 `calibration`으로 변경했다.
- hidden metric은 `no_peek_validation` block으로 별도 보존한다.
- selection metric, precision constraint, recall constraint 기본 경로가 calibration split을 본다.
- JSON-only post-processor 상태를 유지한다.

### sweep runner
- `tools/training/run_manifest_lora_sweep.py`의 기본 selection metric을 다음처럼 변경했다.
  - `metrics.by_split.calibration.accuracy`
  - `metrics.by_split.calibration.precision_fail`
  - `metrics.by_split.calibration.recall_fail`
- `--resume` 전달과 train/eval 재시작 흐름은 변경하지 않았다.

## 검증 agent 결론
- 변경 위치는 `tools/eval`, `tools/training`, `tests`로 적절하다.
- 새 solver/rule/runtime import는 없다.
- calibration-first와 hidden no-peek 요구는 테스트로 확인된다.
- tracked 변경은 요청된 6개 파일뿐이다.
- `src/`, server 문서, 제출 패키지 파일은 변경하지 않았다.
- 중간 학습 재시작 가능성은 직접 악화되지 않았다.

## 테스트
```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
Ran 35 tests in 0.071s
OK
```

추가 dry-run:
```text
python3 tools/training/run_manifest_lora_sweep.py --manifest manifest.jsonl --run-root <tmpdir> --dry-run --limit-configs 1
```

dry-run report의 selection block:
```json
{
  "min_fail_precision": 0.9,
  "min_fail_recall": 0.8,
  "precision_metric": "metrics.by_split.calibration.precision_fail",
  "recall_metric": "metrics.by_split.calibration.recall_fail",
  "selection_metric": "metrics.by_split.calibration.accuracy"
}
```

주의:
- `python3 -B -m unittest discover -v`처럼 repo root에서 discovery하면 기존 `tools/analysis/test_fail_dp_cases.py`가 테스트로 잡히며 `StatefulOpalVerifier` import 실패가 날 수 있다.
- 이번 검증 기준은 기존 프로젝트 표준인 `tests/` suite다.

## 영향
- 기존 inference와 manifest loading은 바뀌지 않는다.
- 기존 학습 checkpoint/resume 흐름은 바뀌지 않는다.
- 기존 hidden threshold 선택은 default에서 제거됐다.
- 향후 sweep 결과는 calibration-first selection이 기본이 되며, hidden은 no-peek 검증 지표로만 archive된다.

## 다음 결정
- 이 변경을 서버 repo에 배포한다.
- 기존 sweep JSON에 대해 calibration-first selector를 재실행해 현재 후보가 calibration gate를 통과하는지 확인한다.
- calibration gate 결과가 좋지 않으면 P1 보수적 LoRA/QLoRA sweep으로 이동한다.
