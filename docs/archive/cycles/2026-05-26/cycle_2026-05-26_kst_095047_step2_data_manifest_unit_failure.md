# 2026-05-26 KST 09:50 - Step 2 문제 확인: manifest 단위 붕괴

## 구조 Skeleton

- cycle 단계: P1 sweep 중 r16 평가 완료 후 문제 확인
- 대상 manifest: `/workspace/team6/ops/runs/20260522_164328_KST/manifests/canonical_supervised_manifest.jsonl`
- 관련 코드:
  - `tools/analysis/build_supervised_manifest.py`
  - `tools/training/train_manifest_lora.py`
  - `tools/eval/eval_manifest_adapter.py`
- 검증 agent:
  - 데이터 구조 기반 검증 agent
  - rulebase-73-clean verifier 기반 데이터 감사 agent
  - manifest builder 구조 검증 agent
  - 서버 manifest/raw 매칭 검증 agent
- 원칙:
  - rulebase verifier는 제출 architecture에 포함하지 않는다.
  - rulebase verifier는 데이터 품질 감사용 weak reference로만 사용한다.
  - 목표를 73점 재현으로 두지 않는다.

## r16 중간 평가

[Original Text/Data] -> `p1_r16_lr2e4_do20_ep5.eval_manifest.json` base threshold 0.50: overall `accuracy=0.916084`, `precision_fail=0.850000`, `recall_fail=1.000000`, `ECE=0.062724`, confusion `TP=68/TN=63/FP=12/FN=0`.

[Exact Interpretation] -> r16은 recall은 높지만 fail precision이 낮고 false positive가 많다.

[Detailed Explanation/Example] -> r4 overall precision `0.891892`, r8 overall precision `0.860759`보다 r16 precision이 더 낮다. 따라서 r16은 제출 후보가 아니다.

[Original Text/Data] -> calibration: `n=48`, `accuracy=0.895833`, `precision_fail=0.833333`, `recall_fail=1.000000`, `ECE=0.098220`, confusion `TP=25/TN=18/FP=5/FN=0`.

[Exact Interpretation] -> Step 3의 1차 목표 `calibration precision_fail >= 0.90`, `recall_fail >= 0.95` 중 precision gate를 통과하지 못한다.

[Detailed Explanation/Example] -> threshold sweep에서 calibration recall `>=0.95`를 만족하는 지점의 precision 최대도 `0.833333`이다. threshold만으로 1차 목표를 통과할 수 없다.

[Original Text/Data] -> hidden: `n=95`, `accuracy=0.926316`, `precision_fail=0.860000`, `recall_fail=1.000000`, confusion `TP=43/TN=45/FP=7/FN=0`; threshold 0.70 hidden precision은 `0.913043`, recall은 `0.976744`, FP는 `4`.

[Exact Interpretation] -> hidden에서는 threshold를 올리면 precision이 좋아지지만 calibration precision 병목은 그대로다.

[Detailed Explanation/Example] -> leaderboard 제출 기준은 calibration-first gate를 통과해야 하므로 현재 r16은 NO-GO다.

## 데이터 구조 검증 결론

[Original Text/Data] -> manifest 480행 중 `input`에 `records`가 포함된 행은 `0/480`이다.

[Exact Interpretation] -> 현재 manifest는 전체 command-response trajectory를 학습 input으로 제공하지 않는다.

[Detailed Explanation/Example] -> rulebase-73-clean verifier가 요구하는 입력 단위는 `records` list 또는 trajectory list인데, 현재 manifest는 verifier-compatible row가 `0`이다. 따라서 rulebase agreement를 의미 있게 계산할 수 없다.

[Original Text/Data] -> `input` keyset 분포: `('ifd_score','num_records','source') = 464`, `('args','command') = 16`.

[Exact Interpretation] -> 480행 중 464행은 trajectory도 command step도 아닌 보조 점수 메타데이터가 학습 input으로 들어갔다.

[Detailed Explanation/Example] -> line 15는 raw `filtered/ifd_scores.json[0]`의 `ifd_score`, `num_records`, `source`만 input으로 들어가며, 실제 Opal trajectory가 없다. 모델은 프로토콜을 학습하지 못하고 source 문자열/점수 shortcut을 학습하게 된다.

[Original Text/Data] -> command 계열 16행은 `augmented_train.json` 또는 `training_cases.json`의 flattened `records[row].input`과 대응한다.

[Exact Interpretation] -> 이 16행도 전체 trajectory가 아니라 개별 step input이다.

[Detailed Explanation/Example] -> line 1은 `augmented_train.json`의 flattened record `87`, 즉 어떤 case의 `records[32].input`에 대응한다. final output/status와 이전 상태 transition이 사라진 단일 command만 남는다.

[Original Text/Data] -> exact input duplicate conflict: line 2와 line 479가 동일 input인데 각각 `pass`와 `fail` label을 가진다.

[Exact Interpretation] -> 단일 command만 떼어내면 context가 사라져 같은 command가 서로 다른 label을 갖게 된다.

[Detailed Explanation/Example] -> 같은 `Write` command라도 앞선 locking/session state에 따라 pass/fail이 갈릴 수 있다. 전체 trajectory를 버리면 label이 모순처럼 보이고, 이는 학습 precision 병목으로 이어진다.

## 코드 원인

[Original Text/Data] -> `tools/analysis/build_supervised_manifest.py`의 `iter_json_records`는 `CONTAINER_KEYS`에 `records`를 포함하고, dict에 container key가 있으면 `yield from iter_json_records(payload[original_key])` 후 `return`한다.

[Exact Interpretation] -> `{"records": [...], "label": ...}` parent case가 record-like 객체여도 parent를 yield하지 않고 내부 step으로 분해한다.

[Detailed Explanation/Example] -> top-level case의 sibling `label`은 내부 step으로 전달되지 않는다. 내부 step에 `output.result` 또는 step-level `label`이 있으면 그 값이 label로 추출되고, trajectory-level label은 손실된다.

[Original Text/Data] -> `extract_input_text`는 현재 record에서 `INPUT_KEYS`를 재귀 검색하며, `records`는 input key가 아니다.

[Exact Interpretation] -> parent case가 보존되지 않는 한 `records` 전체가 input text가 되는 경로가 없다.

[Detailed Explanation/Example] -> builder가 parent case를 먼저 yield해야만 `records` 전체를 stable JSON으로 담거나 별도 trajectory formatter로 담을 수 있다.

## 결정

[Original Text/Data] -> r4/r8/r16 모두 calibration precision 목표를 통과하지 못했고, r16은 데이터 단위 붕괴가 확인된 manifest로 학습됐다.

[Exact Interpretation] -> 현재 P1 LoRA sweep의 낮은 precision 문제는 hyperparameter보다 데이터 생성/manifest 구축 오류가 1차 원인이다.

[Detailed Explanation/Example] -> rank, lr, dropout을 계속 바꾸면 보조 메타데이터/단일 step shortcut에 더 잘 맞는 모델만 만들 수 있다. 이는 leaderboard 일반화와 LLM-only 과제 목표에 부합하지 않는다.

## 다음 실행

1. 진행 중인 sweep은 중단하지 않는다. 이미 GPU가 정상 실행 중이며, 완료 결과는 참고 기록으로만 사용한다.
2. `build_supervised_manifest.py`를 수정해 trajectory case를 원자 단위로 보존한다.
3. `ifd_score`, metrics, score summary, report 계열 보조 row는 학습 후보에서 제외한다.
4. 새 manifest는 다음 hard gate를 통과해야 한다:
   - verifier-compatible trajectory row 비율 `> 0`, 목표 `>= 95%`
   - `input`에 `records` 또는 equivalent trajectory JSON 존재
   - exact input conflicting label `0`
   - public/leaderboard/rule-context leakage `0`
   - train/calibration/hidden cross-split duplicate `0`
5. 새 manifest에 대해서만 LoRA/QLoRA/DoRA/full FT 비교를 다시 시작한다.
6. full FT는 12GB 저장 가능성, 48GB memory dry-run, checkpoint/resume, 1 epoch pilot을 통과한 뒤 본학습으로 승격한다.

## Leaderboard 판단

[Original Text/Data] -> 현재 `submit --list`는 응답했지만, r16은 calibration precision gate를 통과하지 못했고 데이터 단위 오류가 확인됐다.

[Exact Interpretation] -> 현재 leaderboard 제출은 NO-GO다.

[Detailed Explanation/Example] -> 오늘 제출 기회를 쓰려면 기존과 다른 근거가 있어야 한다. 현재 새 근거는 제출 근거가 아니라 데이터 재구축 근거다.
