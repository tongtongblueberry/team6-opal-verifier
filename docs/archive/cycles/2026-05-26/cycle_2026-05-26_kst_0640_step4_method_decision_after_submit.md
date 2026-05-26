# 2026-05-26 KST 06:40 - Step4 달성 방법 결정

## 구조 Skeleton
- 입력 agent
- 방법론 근거
- 최종 우선순위
- 구현 범위
- No-Go
- 결정

## 입력 agent
- 방법론 논문 agent:
  - hidden no-peek 프로토콜을 고정하고, threshold와 bucket 경계는 hidden 평가 전에 freeze해야 한다고 제안했다.
  - calibration-first threshold, LTT/CRC 방식 risk 또는 FP 제약, risk/FP coverage metric을 우선 제안했다.
  - fine tuning은 바로 들어가지 말고, no-regress 실패 시 LoRA/QLoRA 재학습 후 재캘리브레이션 gate를 통과해야 한다고 제안했다.
- 학습 원리 agent:
  - 다음 sweep 1순위는 rank 확대가 아니라 분포 고정과 calibration protocol 고정이라고 제안했다.
  - calibration sample이 작으므로 isotonic/Dirichlet처럼 자유도가 큰 calibrator는 보류하고 global temperature 또는 단일 threshold를 우선 제안했다.
  - r32 이상 확대보다 `r={4,8,16}`, 현재 best LR 기준 log-scale 인근, dropout/weight decay/label smoothing을 우선 제안했다.
- 방법 결정 agent:
  - P0는 post-hoc calibration protocol 고정이다.
  - P1은 보수적 LoRA 재학습 sweep이다.
  - P2는 length/trajectory coverage 계측 강화다.

## 방법론 근거
[Original Text/Data] Step2는 hidden 기준 threshold 선택을 1순위 병목으로 판정했다. Step3은 calibration-first threshold, hidden no-peek, risk/coverage metric, length/trajectory bucket metric을 다음 방법 검토 대상으로 확정했다.

[Exact Interpretation] 다음 구현은 재학습부터 시작하지 않는다. 먼저 평가와 후보 선택 protocol을 고쳐야 한다.

[Detailed Explanation/Example] hidden에서 threshold를 고른 뒤 같은 hidden score로 후보를 결정하면 selection bias가 생긴다. 따라서 calibration split에서 threshold를 선택하고 hidden은 검증-only로 남긴다.

## 최종 우선순위
### P0: calibration-first selector 및 risk/coverage metric
- `tools/eval/eval_manifest_adapter.py`
  - threshold sweep report에 risk/coverage 및 FP/FPR coverage metric을 추가한다.
  - 가능하면 length/source bucket별 metric을 report에 포함한다.
  - 현재 p_fail score와 threshold 기반 metric을 재사용하므로 model inference data flow는 바꾸지 않는다.
- `tools/eval/select_manifest_sweep_candidate.py`
  - 기본 선택 split을 hidden에서 calibration으로 바꾼다.
  - calibration metric으로 threshold 후보를 선택하고, hidden metric은 no-peek validation block으로 보존한다.
  - JSON-only post-processor 상태를 유지하고 solver/runtime/rule 코드를 import하지 않는다.
- `tools/training/run_manifest_lora_sweep.py`
  - 기본 selection metric을 calibration split 기준으로 바꾼다.
  - 기존 hidden summary는 보고용으로만 남긴다.

### P1: 보수적 LoRA/QLoRA 재학습 sweep
- 기존 r16 best를 기준선으로 둔다.
- 다음 sweep 후보는 `r={4,8,16}`, lower LR, dropout `{0.05,0.10,0.20}`, weight decay, label smoothing 중심으로 제한한다.
- r32/r64/full FT는 calibration/risk/coverage 개선 없이 주력 후보로 승격하지 않는다.
- 48GB GPU에서는 QLoRA/LoRA가 우선이다.

### P2: data coverage 계측 강화
- manifest/eval report에 length bucket, source bucket, 가능하면 `step_count` 또는 trajectory bucket을 추가한다.
- selected data가 계속 `1-32` length bin에만 몰리면 long/trajectory 개선을 주장하지 않는다.
- long trajectory 데이터 증강은 bucket metric으로 결함이 확인된 뒤 진행한다.

## 구현 범위
- 이번 즉시 구현 범위는 P0로 제한한다.
- 수정 예상 파일:
  - `tools/eval/eval_manifest_adapter.py`
  - `tools/eval/select_manifest_sweep_candidate.py`
  - `tools/training/run_manifest_lora_sweep.py`
  - 관련 unit tests
- `src/solver.py`는 이번 즉시 구현에서는 변경하지 않는다. threshold 또는 temperature를 실제 제출 runtime에 고정하는 변경은 calibration-first 후보가 확정된 뒤 별도 package gate와 함께 진행한다.
- `tools/eval/conformal_calibration.py`는 rule-engine deferral용 성격이 있어 이번 방법에 사용하지 않는다.

## No-Go
- hidden split으로 threshold 선택 또는 재선택.
- hidden 평가 이후 threshold 변경 횟수 `>0`.
- ECE 초과, FP/FPR 악화, fail precision hard target 미달 후보를 제출 후보로 승격.
- selected data가 계속 `1-32` bin에만 몰린 상태에서 long/trajectory 개선 주장.
- r64 이상, DoRA, partial/full fine tuning을 calibration/risk-coverage 개선 없이 주력 후보로 승격.
- fail oversampling이나 label prior 왜곡으로 hidden score만 올리기.
- rule engine 또는 rule-context를 architecture에 포함.

## 결정
Step4 방법은 다음으로 확정한다.

1. 즉시 구현은 P0 `calibration-first selector + risk/coverage metric`이다.
2. 다음 학습은 P0 gate로 기존 sweep을 다시 판정한 뒤, no-regress 실패 시 P1 보수적 LoRA/QLoRA sweep으로 진행한다.
3. P2 coverage 계측은 P0 이후 바로 이어서 붙인다.
4. full fine tuning은 48GB memory dry-run, checkpoint/resume smoke, 1 epoch pilot, calibration gate를 통과하기 전까지 주력 방법으로 채택하지 않는다.
