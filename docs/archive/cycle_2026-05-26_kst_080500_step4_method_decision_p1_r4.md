# Cycle 2026-05-26 KST 08:05:00 Step4 방법 결정 기록 P1 R4

작성 기준: 2026-05-26 KST.

민감정보 기록 여부: 없음.

<!-- 변경 사유: Step4에서 P1 sweep 진행 중의 방법 결정과 후속 우선순위를 archive 문서로 고정한다. -->

## 1. 입력 결론

### 1.1 Calibration false positive 수리 조사 결론

- 우선순위 1은 constrained threshold selection과 PR/risk-coverage 검증이다.
- recall >= 0.95를 hard constraint로 두고, calibration precision >= 0.90을 만족하는 최소 threshold 또는 최적 operating point를 찾는다.
- 이 접근은 rule engine이 아니다.
- 우선순위 2는 binary post-hoc calibration 후 threshold 재선택이다.
- ECE 0.1076이 관측되었으므로 Platt calibration 또는 beta calibration을 우선 검토한다.
- isotonic calibration은 작은 calibration split에서는 과적합 위험이 있다.
- temperature scaling은 baseline으로는 가능하지만 ranking 변화가 작아 단독 false positive 감소 효과는 제한적이다.
- 우선순위 3은 다음 학습 라운드에서 hard negative mining과 mild reweighting/focal을 적용하는 것이다.
- calibration false positive를 hard negative pool로 구성하되 recall lower bound는 유지한다.
- rule engine, symbolic validator, deterministic post-filter는 제외한다.

### 1.2 Fine-tuning 및 학습 원리 조사 결론

- P1 완료 전에는 새 학습을 시작하지 않는다.
- r8/r16 결과를 기다리며 각 run의 calibration precision, hidden proxy, false positive 유형, saved adapter size, peak VRAM을 정리한다.
- P1 완료 직후 1순위는 hard gate에 가까운 rank 기준 target_modules 확장 sweep이다.
- target_modules 확장 순서는 q/v 유지, q/k/v/o, q/k/v/o + mlp 또는 all-linear 순서다.
- 2순위는 best LoRA 구조 주변의 learning rate, weight decay, label smoothing, lora dropout, effective batch에 대한 작은 sweep이다.
- 3순위는 rank가 도움을 주지만 불안정할 때 rsLoRA, LoRA+, LoRA-FA를 검토하는 것이다.
- 4순위는 r16/all-linear 또는 고rank가 12GB/VRAM 내에서 calibration 부족을 보이면 DoRA/AdaLoRA를 비교하는 것이다.
- 5순위는 QLoRA이며, 메모리 절감이 필요하거나 더 큰 base 또는 더 넓은 target이 필요할 때만 적용한다.
- 현재 30.4GB 사용이 관측되어 메모리 절감 자체는 1차 병목이 아니다.
- full fine-tuning은 위 단계가 실패하고, short pilot에서 hard gate와 hidden proxy가 동시에 개선되며, artifact < 12GB가 확인될 때만 후보로 둔다.
- rule engine, 후처리 규칙, 외부 classifier는 제외한다.

## 2. 최종 방법 결정

### 2.1 즉시 실행 결정

- 지금 즉시 구현 또는 새 학습을 시작하지 않는다.
- 이유는 P1 sweep이 진행 중이며 r8/r16 결과를 먼저 확인해야 하기 때문이다.
- 현재 단계에서는 P1 결과 판정에 필요한 후처리 분석 계획만 확정한다.

### 2.2 P1 결과 판정 계획

- r8/r16 완료 후 calibration-first selector를 실행한다.
- threshold sweep에서 recall >= 0.95 조건을 만족하는 threshold 후보를 찾는다.
- 해당 후보들 중 precision이 최대인 operating point를 비교한다.
- 함께 기록할 항목은 risk_coverage_summary, bucket_metrics, ECE, Brier다.
- 판정 기준은 calibration precision과 recall hard constraint를 함께 보는 것이다.

### 2.3 P1 통과 시 경로

- P1이 1차 목표를 통과하면 leaderboard 후보 패키징으로 이동한다.
- 서버 제출 가능 상태를 확인한다.
- 단, 제출 자체는 이 Step4 기록 작업 범위에 포함하지 않는다.

### 2.4 P1 미통과 시 구현 우선순위

1. threshold selector 보강 및 PR operating point report 작성
2. post-hoc binary calibration 실험 스크립트 작성
3. hard negative mining manifest 생성
4. target module 확장 LoRA sweep
5. DoRA/AdaLoRA 비교
6. full fine-tuning short pilot

### 2.5 Full fine-tuning 판단

- full fine-tuning은 적극 고려 대상이지만 즉시 주력 전환하지 않는다.
- 현재 실패 원인이 full capacity 부족으로 확정되지 않았다.
- full fine-tuning은 12GB 제출 제한, overfitting, forgetting, calibration 악화 위험이 있다.
- 따라서 short pilot에서 hard gate와 hidden proxy의 동시 개선을 먼저 확인해야 한다.
- artifact size가 12GB 미만인지도 먼저 검증해야 한다.

### 2.6 Leaderboard 미제출 이유

- 새 후보가 아직 P1 sweep 중이다.
- Step3 기준 1차 목표를 통과한 후보가 없다.
- 서버 제출 가능 상태가 개선되었다는 근거가 없다.
- 따라서 현 시점에서는 leaderboard 제출을 하지 않는다.

### 2.7 금지 사항 유지

- rule engine은 계속 금지한다.
- symbolic validator, deterministic post-filter, 후처리 규칙, 외부 classifier도 현재 결정 범위에서 제외한다.

## 3. 실행 범위

- 이 기록 작업에서는 archive 문서만 작성한다.
- 테스트, 커밋, push, 서버 제출, 새 학습 시작, 진행 중 학습 중단은 수행하지 않는다.
