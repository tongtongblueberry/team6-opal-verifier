# 2026-05-26 KST 06:30 - Step3 목표 설정 결정

## 구조 Skeleton
- 입력 agent
- 기준선
- 1차 목표
- 2차 목표
- 궁극 목표
- Gate 및 No-Go
- 결정

## 입력 agent
- metric 논문 agent:
  - calibration metric은 ECE 하나만 보면 불안정하므로 Brier, NLL, adaptive/top-label/classwise ECE, bootstrap CI를 같이 봐야 한다고 제안했다.
  - hidden 기준 threshold 선택은 selection bias를 만들므로 selection gap과 hidden 이후 threshold 변경 횟수 `0`을 gate로 둬야 한다고 제안했다.
  - primary 후보로 `Coverage@Risk<=5%`, hard constraint로 `FPR <= baseline`, `ECE 95% upper CI <= baseline`을 제안했다.
- archive 기반 목표 agent:
  - 현재 전체 leaderboard best는 `73.00`이고, LLM-only로 실제 제출되어 점수를 받은 기준선은 `70.00`이다.
  - 20-case 기준선은 제출 이력이 있는 `16/20`, 참고 최고치는 `17/20`, no-go 하한은 `15/20`이다.
  - 최신 제출 실패는 서버 availability 외부 상태이며, package/static/runtime 문제로 판정하지 않는다.
- 목표 결정 agent:
  - 1차는 유효 제출 복구와 LLM-only no-regress.
  - 2차는 calibration-first로 `73.00` 도달.
  - 궁극은 LLM-only `78.00`, stretch `80.00`로 제안했다.

## 기준선
[Original Text/Data] 현재 전체 leaderboard best는 `73.00`이며 과거 LLM-only 제출 기준선은 `70.00`이다. 20-case 기준선은 `16/20`, 참고 최고치는 `17/20`, 최신 악화 하한은 `15/20`이다.

[Exact Interpretation] 목표는 rule-engine 기반 `73.00`을 복구하는 것이 아니라 LLM-only 제출로 `70.00`을 재현하고, 이후 calibration-first로 `73.00`을 넘는 것이다.

[Detailed Explanation/Example] 이번 Cycle 3 후보는 hidden에서 높지만 threshold가 hidden 기준으로 선택됐다. 따라서 2차 목표는 hidden score만 재현하는 것이 아니라 calibration split에서 threshold를 고른 뒤 hidden no-peek에서 성능을 유지하는 것이다.

## 1차 목표: 유효 제출 복구 + LLM-only no-regress
- leaderboard:
  - 서버 availability 회복 후 유효 submission ID 및 job ID 생성
  - score 수신
  - LLM-only leaderboard `>=70.00`
- 20-case:
  - `>=16/20`
  - `15/20` 이하는 no-go
- offline/internal:
  - hidden no-peek accuracy `>=0.95`
  - fail precision `>=0.90`
  - fail recall `>=0.80`
  - macro-F1 `>=0.72`
  - ECE `<=0.12`
  - Brier 기록 필수
- selection/calibration:
  - threshold는 calibration split에서 1회 선택
  - hidden split으로 threshold 선택 금지
  - hidden 평가 이후 threshold 변경 횟수 `0`
  - risk-coverage 또는 FP-coverage curve 기록
  - FP/FPR은 직전 채택 후보보다 악화 금지
- package/runtime:
  - package `<12GB`
  - offline first-forward PASS
  - model-load PASS
  - runtime failure `0`
  - 제출 archive 및 hash 기록

## 2차 목표: calibration-first로 LLM-only 73.00 도달
- leaderboard:
  - LLM-only leaderboard `>=73.00`
- 20-case:
  - `>=17/20`
- calibration-first:
  - calibration precision_fail `>=0.90`
  - calibration ECE `<=0.08`
  - calibration threshold 선택 후 hidden no-peek 재선택 금지
- hidden no-peek:
  - accuracy `>=0.96`
  - precision_fail `>=0.94`
  - recall_fail `>=0.95`
  - Brier `<=0.08`
  - FP `<=3`
- coverage:
  - length bucket coverage 기록
  - `step_count` 또는 long trajectory bucket metric 기록
  - Length Coverage `>=0.25`
  - worst source/template bucket 악화 금지
- method gate:
  - high-rank LoRA, DoRA, partial/full fine tuning은 r16 baseline 대비 internal score `+3pp` 또는 risk/calibration 명확 개선이 있을 때만 제출 후보로 승격한다.

## 궁극 목표: LLM-only 고득점 안정 제출
- leaderboard:
  - hard target `>=78.00`
  - stretch target `>=80.00`
- 20-case:
  - `>=18/20`
- calibration-first hidden no-peek:
  - accuracy `>=0.97`
  - precision_fail `>=0.95`
  - recall_fail `>=0.95`
  - ECE `<=0.05`
  - Brier `<=0.05`
- coverage:
  - worst long/source bucket accuracy `>=0.70`
  - Length Coverage `>=0.50`
  - trajectory cluster coverage baseline 대비 감소 없음
- 운영:
  - server-side runtime failure `0`
  - package `<12GB`
  - offline first-forward PASS
  - resume 가능
  - 제출 archive/hash 완비

## Gate 및 No-Go
- NO-GO: 서버 availability reject 상태에서 동일 package 반복 제출.
- NO-GO: hidden split으로 threshold 선택 또는 재선택.
- NO-GO: ECE 목표 초과, FP/FPR 악화, fail precision hard target 미달.
- NO-GO: selected data가 계속 `1-32` length bin에만 몰린 상태에서 long/trajectory 개선을 주장.
- NO-GO: r64 이상 rank 확대나 full fine tuning을 calibration/risk-coverage 검증 없이 주력 제출 후보로 채택.
- NO-GO: fail oversampling이나 label prior 왜곡으로 단기 hidden score만 끌어올리기.
- NO-GO: rule engine 또는 rule-context를 architecture에 포함.

## 결정
Step3 목표는 다음과 같이 확정한다.

1. 1차 목표는 유효 job ID를 받는 LLM-only 제출 복구와 `>=70.00` no-regress다.
2. 2차 목표는 calibration-first threshold로 LLM-only `>=73.00`을 달성하는 것이다.
3. 궁극 목표는 LLM-only `>=78.00`, stretch `>=80.00`이다.
4. 다음 Step4 방법 결정은 calibration-first selector, risk/coverage metric, length/trajectory bucket metric을 우선 검토한다.
