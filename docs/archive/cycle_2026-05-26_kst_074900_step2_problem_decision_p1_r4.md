# Cycle 2026-05-26 KST 07:49:00 Step 2 문제 판단 기록 - p1_r4

## 기록 기준

- 기준 시간대: KST
- 기록 대상: Step 2 문제 판단 및 기록
- 대상 후보: p1_r4
- 민감정보: 기록하지 않음

## 입력 근거

### 데이터 구조 검증 결론

- p1_r4@0.50의 전체 성능은 overall accuracy 93.01%, calibration accuracy 87.50%, hidden accuracy 95.79%이다.
- 약점은 hidden split이 아니라 calibration split에 집중되어 있다.
- calibration ECE는 0.1076이고 hidden ECE는 0.0384이다.
- pass gold mean p_fail은 calibration 0.2195, hidden 0.0939로, calibration pass가 fail로 과잉 판단되는 경향이 있다.
- bucket 근거는 length 1개, source 140개/143행이므로 source/length 일반화 근거는 약하다.
- threshold 0.30은 recall 1.0을 얻는 대신 FP=12이고, threshold 0.50은 best accuracy/fail F1 기준으로 FP=8/FN=2이다.
- P0 relaxed best r32@0.30 대비 p1_r4@0.50은 hidden은 개선되었지만 calibration은 약화되었다.

### 학습 구조 검증 결론

- 학습 구조 문제는 제한적이다.
- r=4, dropout=0.20, weight decay=0.05, label smoothing=0.1은 보수적인 설정이고 trainable ratio는 0.00018695이다.
- loss는 34.09 -> 26.48 -> 9.326 -> 7.563 이후 6.1~7.0 구간에서 plateau를 보였다.
- lr schedule은 정상이고, gradient explosion 또는 vanishing 증거는 없다.
- threshold sweep에서 best accuracy와 fail F1은 0.50이므로 현재 관측상 threshold mismatch로 보지 않는다.
- 전체 ECE 0.0493과 hidden ECE 0.0384는 양호하지만, calibration split의 ECE와 accuracy만 약하다.

### 논문 검증 결론

- 판단은 보류한다.
- LoRA/QLoRA/AdaLoRA/DoRA/Dropout/AdamW/Label Smoothing/Calibration/PR curve/Selective classification/Verifier 관련 논문 17편 근거상 r=4 자체 부족과 higher rank 필요성을 모두 뒷받침할 수 있다.
- 현재 관측만으로 rank bottleneck과 calibration/threshold/imbalance 문제를 분리할 수 없다.
- 같은 split에서 r=4/8/16, 동일 calibration, 동일 threshold rule로 PR-AUC, risk-coverage, recall@precision, precision@recall 비교가 필요하다.

## Step 2 최종 결정

현재 문제는 전체 데이터 붕괴나 LLM 학습 구조 실패가 아니다. p1_r4의 현재 문제는 calibration split에서 pass를 fail로 과잉 판단하는 제한적 calibration/false-positive 문제로 결정한다.

이 결정의 근거는 다음과 같다.

- hidden accuracy는 95.79%이고 hidden ECE는 0.0384로, hidden split 전반 붕괴 증거가 없다.
- calibration accuracy는 87.50%이고 calibration ECE는 0.1076으로, calibration split에서만 약점이 집중된다.
- calibration pass gold mean p_fail이 0.2195로 hidden 0.0939보다 높아, calibration pass 샘플을 fail로 과잉 판단하는 방향의 false positive 문제가 관측된다.
- 학습 로그와 설정상 lr schedule 이상, gradient explosion, gradient vanishing, 명확한 threshold mismatch 증거가 없다.

## 보류 결정

p1_r4 하나만 완료된 상태이므로 다음 판단은 보류한다.

- r=4 유지 또는 폐기 판단은 보류한다.
- full fine-tuning 전환 판단은 보류한다.
- leaderboard 제출 판단은 보류한다.

보류 이유는 rank bottleneck, calibration/threshold 문제, class imbalance 가능성을 현재 단일 후보 관측만으로 분리할 수 없기 때문이다. 동일 split, 동일 calibration, 동일 threshold rule 조건에서 r=4/8/16 등 P1 sweep 비교가 필요하다.

## Leaderboard 제출 제외 사유

현재 p1_r4는 leaderboard에 제출하지 않는다.

- 첫 후보 하나뿐이므로 반복 비교 근거가 없다.
- 기존 P0 relaxed best 대비 hidden은 개선되었지만 calibration은 약하다.
- calibration split에서 pass를 fail로 과잉 판단하는 false positive 문제가 남아 있다.
- 제출 가능 상태로 개선되었다는 근거가 없다.

## Rule Engine 결정

rule engine은 architecture에 추가하지 않았다. 앞으로도 architecture에 rule engine을 추가하지 않는다.

## 다음 단계 후보 방향

P1 sweep은 계속 진행한다. 다음 Step 3의 목표 후보는 calibration split 기준 fail precision 0.90 이상을 유지하면서 fail recall 0.95 이상, hidden no-peek accuracy 0.94 이상을 유지하는 방향으로 잡는다.

단, 위 항목은 Step 3 목표 후보 방향이며 최종 목표 설정은 Step 3에서 별도 기록한다.
