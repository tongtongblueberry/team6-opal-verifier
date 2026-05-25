# Step 3 목표 결정 기록: p1_r4

<!-- 변경 주석: Step 3 목표 결정과 다음 조사 질문을 감사 가능한 기록으로 남기기 위해 새 archive 문서를 추가한다. -->

## 기준

- 작성 기준: 2026-05-26 08:00:00 KST (UTC+09:00)
- 시간 표기: 모든 판단과 목표는 KST 기준으로 기록한다.
- 민감정보: 기록하지 않는다.
- 코드 및 실행 영향: 문서 추가만 수행하므로 데이터 흐름, 학습 의존성, 런타임 모듈, 제출 파이프라인에는 영향이 없다.

## 입력 전제

[Original Text/Data] Step2 최종 문제는 전체 데이터 붕괴 또는 LLM 학습 실패가 아니라 calibration split에서 pass를 fail로 과잉 판단하는 제한적 calibration false-positive 문제이다.  
[Exact Interpretation] 현재 실패 원인은 전면 재학습 실패가 아니라 calibration pass 샘플에 대한 fail 예측 과다이다.  
[Detailed Explanation/Example] 따라서 1차 목표는 leaderboard 점수 직접 최적화가 아니라 calibration false positive를 줄이면서 fail recall과 hidden 성능을 유지하는 방향으로 둔다.

[Original Text/Data] p1_r4@0.50은 calibration precision 0.827586, recall 0.960000, accuracy 0.875000, ECE 0.107627; hidden accuracy 0.957895, precision 0.933333, recall 0.976744, ECE 0.038430; overall precision 0.891892, recall 0.970588, accuracy 0.930070, ECE 0.049274이다.  
[Exact Interpretation] p1_r4는 hidden 성능은 제출 후보에 가까우나 calibration precision과 ECE가 1차 hard gate에 미달한다.  
[Detailed Explanation/Example] calibration precision_fail 0.827586은 목표 0.90보다 낮고, calibration ECE 0.107627은 보조 목표 0.10보다 높다. hidden accuracy 0.957895와 hidden recall_fail 0.976744는 강하지만 calibration false positive 수리 전 제출 판단에는 충분하지 않다.

[Original Text/Data] P0 relaxed best r32@0.30은 calibration accuracy 0.895833, precision 0.833333, recall 1.0; hidden accuracy 0.936842, precision 0.877551, recall 1.0이다.  
[Exact Interpretation] 완화 기준의 P0 후보도 calibration precision과 hidden precision이 hard gate에 미달한다.  
[Detailed Explanation/Example] recall은 높지만 pass를 fail로 과잉 판단하는 문제가 남아 있으므로 precision 중심의 hard gate가 필요하다.

[Original Text/Data] 기록 기반 목표 agent는 p1_r4를 제출 후보가 아니라고 판단했고, 1차는 calibration FP 수리 게이트, 2차는 기존 LLM-only >=73.00, 궁극은 >=78.00 및 stretch >=80.00 유지를 추천했다.  
[Exact Interpretation] 제출 후보 판정은 보류하고, 단계별 목표를 calibration 수리, leaderboard 73.00 후보, leaderboard 78.00 이상 후보로 분리한다.  
[Detailed Explanation/Example] p1_r4는 첫 후보로서 진단 가치는 있으나 calibration hard gate를 통과하지 못했기 때문에 즉시 제출하지 않는다.

[Original Text/Data] 논문 기반 목표 agent는 PR-AUC/AP, ECE/Brier, FPR/FDR, risk-coverage/AURC가 calibration false positive 문제에 적합하다고 제안했다. 다만 1차 precision 0.86은 너무 완화적이므로 최종 결정에서는 hard gate 0.90을 유지한다. 보조지표는 calibration FPR <=0.174, ECE <=0.09, AURC <=0.90x p1_r4 baseline이다.  
[Exact Interpretation] 목표 평가는 precision/recall/accuracy만 보지 않고 calibration 품질과 risk-coverage 계열 지표를 함께 본다.  
[Detailed Explanation/Example] 1차 precision_fail 기준은 0.86으로 낮추지 않고 0.90으로 유지한다. 보조지표는 hard gate를 대체하지 않으며, 같은 후보 간 우선순위를 정하거나 false-positive 수리 정도를 설명하는 용도로 쓴다.

## 최종 목표 결정

### 1차 목표: P1 sweep calibration false-positive 수리 게이트

P1 sweep 후보 중 calibration-first threshold에서 다음 조건을 모두 만족하는 후보를 1차 통과로 본다.

- calibration precision_fail >= 0.90
- calibration recall_fail >= 0.95
- hidden no-peek accuracy >= 0.94
- hidden precision_fail >= 0.90
- hidden recall_fail >= 0.95

보조지표는 다음을 기록하고 후보 간 비교에 사용한다.

- calibration ECE <= 0.10
- calibration FPR <= 0.174
- overall precision_fail >= 0.90
- AURC <= 0.90x p1_r4 baseline

### 2차 목표: LLM-only leaderboard >=73.00 제출 후보 조건

LLM-only leaderboard 73.00 이상을 노리는 제출 후보는 다음 조건을 만족해야 한다.

- calibration precision_fail >= 0.90
- calibration recall_fail >= 0.95
- calibration ECE <= 0.08
- hidden accuracy >= 0.96
- hidden precision_fail >= 0.94
- hidden recall_fail >= 0.95
- hidden Brier <= 0.08
- hidden FP <= 3
- package < 12GB
- runtime failure = 0

### 궁극 목표: LLM-only leaderboard >=78.00, stretch >=80.00

최종 목표는 LLM-only leaderboard 78.00 이상이며, stretch 목표는 80.00 이상이다. 후보 조건은 다음과 같다.

- 20-case >= 18/20
- calibration precision_fail >= 0.95
- calibration recall_fail >= 0.95
- hidden accuracy >= 0.97
- hidden precision_fail >= 0.95
- hidden recall_fail >= 0.95
- hidden ECE <= 0.05
- hidden Brier <= 0.05
- AURC <= 0.65x p1_r4 baseline
- package < 12GB
- runtime failure = 0

## 제출 결정

[Original Text/Data] 첫 후보만 완료되었고 p1_r4는 calibration hard gate에 미달하며, 서버 제출 가능 상태가 개선되었다는 근거가 없다.  
[Exact Interpretation] 현재 시점에서는 leaderboard 제출을 하지 않는다.  
[Detailed Explanation/Example] p1_r4는 hidden 지표가 강해도 calibration precision_fail 0.90 hard gate를 통과하지 못했다. 제출은 최소한 1차 목표 통과 후보가 확인된 뒤 다시 판단한다.

## 방법 제한 및 Step4 후보

[Original Text/Data] Rule engine 금지는 유지한다. Full fine-tuning, DoRA, high-rank LoRA는 다음 Step4 방법 후보로 고려할 수 있지만, P1 sweep이 끝나기 전 주력 전환은 보류한다.  
[Exact Interpretation] 현재 라운드의 주력은 P1 sweep 검증이며, 규칙 기반 엔진으로 우회하지 않는다.  
[Detailed Explanation/Example] r8/r16 등 P1 sweep 후보가 calibration precision hard gate를 통과하는지 먼저 확인한다. 통과하지 못하면 후처리 thresholding, calibration 개선, DoRA, full fine-tuning, partial fine-tuning을 Step4에서 비교 조사한다.

## Step4로 넘길 질문

1. r8/r16이 calibration precision_fail >= 0.90 hard gate를 통과하는가?
2. 통과하지 못한다면 calibration/post-hoc thresholding/DoRA/full fine-tuning/partial fine-tuning 중 어떤 방법을 우선 조사할 것인가?

