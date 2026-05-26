# 2026-05-26 08:36:00 KST - Step 2 P1 r8 문제 판단 기록

## 입력 검증

- 데이터 구조 기반 검증 결론: 데이터 문제 제한적.
  - r8은 calibration split 기준 recall_fail >= 0.95 조건에서 precision_fail 최대값이 0.833333이다.
  - tie threshold는 0.30, 0.35, 0.40, 0.45, 0.50이며, 가장 높은 threshold 0.50에서도 calibration precision hard gate 0.90을 통과하지 못한다.
  - r8의 hidden 악화는 FP 증가 때문이다. r4 hidden FP=3, r8 hidden FP=6이다.
  - 추가 FP 3개는 hidden split의 `remove_step` 계열이며 p_fail이 0.516~0.547로 threshold 근처다.
  - length bucket은 단일 bucket이고 source bucket은 140/143으로 희소해 source/length 일반화 결론은 약하다.
- 학습 구조 기반 검증 결론: 학습 구조 문제 제한적.
  - r8은 r4 대비 trainable parameter가 786432에서 1572864로 늘었고, lr/dropout/label smoothing/weight decay는 동일하다.
  - train loss는 r8 8.723, r4 8.918로 r8이 약간 낮고, gradient 폭주/소실 근거는 없다.
  - fixed threshold 0.50에서 r8 hidden은 r4보다 나쁘지만, r8 threshold 0.55에서는 hidden accuracy 0.9684, precision_fail 0.9348, FP=3, FN=0으로 회복된다.
  - 따라서 hidden 악화는 학습 구조 붕괴보다 r8 score 분포에 맞지 않는 fixed threshold 0.50 영향이 강하다.
- 논문 검증 결론: 정규화·threshold 우선.
  - r4가 이미 낮은 intrinsic rank에서 충분한 방향을 학습했을 수 있고, r8은 score 분포와 FP 경계를 더 공격적으로 움직였을 가능성이 있다.
  - rank 증가를 계속 밀기보다 validation 기반 threshold 재선택, PR curve, dropout/label smoothing/AdamW weight decay/lr 재튜닝을 우선해야 한다.
  - rule engine 방식은 제외한다.

## 최종 문제 판단

r8 문제는 전체 데이터 붕괴나 LLM 학습 구조 실패가 아니다. 핵심 문제는 r8이 fail recall을 높이며 score 분포를 fail 쪽으로 이동시켰지만, calibration false positive 5개를 줄이지 못했고 hidden split에서는 threshold 근처 `remove_step` pass 샘플을 fail로 더 많이 오탐한 것이다.

따라서 r8은 Step3 1차 목표 통과 후보가 아니다.

## 제출 판단

- leaderboard 제출은 하지 않는다.
- 이유:
  - calibration precision_fail 0.833333으로 hard gate 0.90 미달이다.
  - hidden precision/accuracy가 r4보다 낮다.
  - P1 sweep은 아직 진행 중이며 r16 결과가 남아 있다.
  - 서버 제출 가능 상태가 개선되었다는 근거가 없다.

## 다음 결정

- 진행 중인 `p1_r16_lr2e4_do20_ep5` 학습을 유지한다.
- r16 결과가 나오면 같은 calibration-first 기준으로 판단한다.
- P1 완료 전에는 새 학습을 시작하지 않는다.
- r4/r8 현재 결과만 보면 단순 rank 증가보다 threshold/정규화/FP 분석 우선순위가 높다.
- rule engine은 architecture에 포함하지 않는다.
