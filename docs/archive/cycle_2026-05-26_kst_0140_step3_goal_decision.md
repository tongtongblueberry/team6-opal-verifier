# Cycle 2 Step 3 목표 결정 기록

## 구조 Skeleton

- 문서 목적: Cycle 2의 현실적 1차 목표, 공격적 2차 목표, 궁극 목표를 확정한다.
- 입력 근거: 논문 기반 metric 목표, archive 기반 목표, Cycle 2 문제 판정, 현재 제출 상태.
- 목표 조정 원칙: leaderboard 목표와 offline/internal metric 목표를 분리하고, 서버 availability reject로 인해 job 생성 자체를 별도 목표로 둔다.
- 목표 선택 근거: 각 목표를 `[Original Text/Data] -> [Exact Interpretation] -> [Detailed Explanation/Example]` 형식으로 기록한다.
- 확정 목표: 1차, 2차, 궁극 목표를 각각 offline/internal, leaderboard, 운영 gate로 나누어 정의한다.
- 제외 사항: rule-engine architecture는 목표와 방법론에서 제외한다. 과거 rule 계열 73점은 비교 기준으로만 사용한다.

## 입력 기준

- 논문 기반 metric agent는 1차 목표로 hidden-like accuracy >= 72%, fail precision >= 90%, fail recall >= 80%, macro-F1 >= 0.72, ECE <= 0.12, package < 12GB 및 offline first-forward PASS를 제안했다.
- 논문 기반 metric agent는 2차 목표로 hidden-like accuracy >= 75%, public-hidden gap <= 8pp, ECE <= 0.08, high-rank/DoRA/partial FT가 r16 LoRA 대비 +3pp 이상을 제안했다.
- 논문 기반 metric agent는 궁극 목표로 LLM-only leaderboard >= 75, hidden-like accuracy >= 78%, fail precision >= 93%, fail recall >= 90%, ECE <= 0.05, worst source/long bucket accuracy >= 70%를 제안했다.
- archive 기반 목표 agent는 1차 목표로 유효 leaderboard job 생성, LLM-only score >= 70.00, hidden-like >= 0.9146, 20-case >= 16/20, package/runtime/data gate PASS를 제안했다.
- archive 기반 목표 agent는 2차 목표로 LLM-only leaderboard >= 73.00, hidden-like >= 0.936842, 20-case >= 17/20, ECE <= 0.12, Length Coverage >= 0.25를 제안했다.
- archive 기반 목표 agent는 궁극 목표로 LLM-only leaderboard >= 80.00, hidden-like >= 0.95, 20-case >= 18/20, server runtime failure 0건, Length Coverage >= 0.50, package < 12GB를 제안했다.
- Cycle 2 문제 판정은 최우선 병목을 length/trajectory gap, source/template 다양성 부족, label prior/calibration 불안정, FT method infra 부족으로 정했다.
- 현재 제출 상태는 merged artifact package gate PASS이나 leaderboard server availability reject로 job ID가 없는 상태다.

## 목표 선택 근거

### 1차 목표 선택 근거

[Original Text/Data] 논문 기반 1차 목표는 hidden-like accuracy >= 72%, fail precision >= 90%, fail recall >= 80%, macro-F1 >= 0.72, ECE <= 0.12, package < 12GB 및 offline first-forward PASS다. archive 기반 1차 목표는 유효 leaderboard job 생성, LLM-only score >= 70.00, hidden-like >= 0.9146, 20-case >= 16/20, package/runtime/data gate PASS다.

[Exact Interpretation] 현재 archive에는 이미 hidden-like 0.9146 수준의 LLM-only 내부 기준선이 있으므로, 72% hidden-like 목표는 현재 상태를 관리하기에는 너무 낮다. 반대로 1차 목표에서 leaderboard 73점 또는 80점을 요구하면 서버 availability reject와 현재 제출 불능 상태를 무시하는 목표가 된다.

[Detailed Explanation/Example] 따라서 1차 목표는 "현재 LLM-only 내부 기준선을 잃지 않고, 제출 가능한 package/runtime 상태를 회복하며, 서버가 받아줄 때 유효 job ID를 생성하는 것"으로 확정한다. offline/internal에서는 hidden-like >= 0.9146, 20-case >= 16/20, fail precision >= 90%, fail recall >= 80%, macro-F1 >= 0.72, ECE <= 0.12를 요구한다. leaderboard에서는 서버 availability reject가 해소된 뒤 유효 job ID 생성 자체를 먼저 목표로 두고, 생성된 job의 1차 점수 목표는 LLM-only >= 70.00으로 둔다.

### 2차 목표 선택 근거

[Original Text/Data] 논문 기반 2차 목표는 hidden-like accuracy >= 75%, public-hidden gap <= 8pp, ECE <= 0.08, high-rank/DoRA/partial FT가 r16 LoRA 대비 +3pp 이상이다. archive 기반 2차 목표는 LLM-only leaderboard >= 73.00, hidden-like >= 0.936842, 20-case >= 17/20, ECE <= 0.12, Length Coverage >= 0.25다.

[Exact Interpretation] hidden-like 75%는 현재 archive 기준보다 낮아 2차 목표로 부적절하다. archive의 hidden-like >= 0.936842와 20-case >= 17/20은 기존 실험 기록과 연결되어 있어 공격적이지만 검증 가능한 목표다. ECE는 archive의 <= 0.12보다 논문 기반 <= 0.08이 calibration 문제를 더 직접적으로 압박한다.

[Detailed Explanation/Example] 따라서 2차 목표는 "데이터 분포 병목과 calibration 병목을 실제로 줄인 개선안만 다음 단계 후보로 인정하는 것"으로 확정한다. offline/internal에서는 hidden-like >= 0.936842, 20-case >= 17/20, public-hidden gap <= 8pp, ECE <= 0.08, Length Coverage >= 0.25를 요구한다. 방법론 비교에서는 high-rank LoRA, DoRA, partial FT, full FT 후보가 r16 LoRA baseline 대비 hidden-like 또는 동등 internal score에서 +3pp 이상 개선되어야 한다. leaderboard에서는 LLM-only >= 73.00을 2차 목표로 둔다. 단, 과거 73점 rule 계열은 architecture 후보가 아니라 비교 기준일 뿐이다.

### 궁극 목표 선택 근거

[Original Text/Data] 논문 기반 궁극 목표는 LLM-only leaderboard >= 75, hidden-like accuracy >= 78%, fail precision >= 93%, fail recall >= 90%, ECE <= 0.05, worst source/long bucket accuracy >= 70%다. archive 기반 궁극 목표는 LLM-only leaderboard >= 80.00, hidden-like >= 0.95, 20-case >= 18/20, server runtime failure 0건, Length Coverage >= 0.50, package < 12GB다.

[Exact Interpretation] LLM-only leaderboard >= 75는 17일 반복 사이클의 궁극 목표로는 낮고, 즉시 LLM-only >= 80.00을 확정 gate로 두는 것은 현재 hidden-public gap과 서버 제출 불능 상태를 감안하면 과도하다. 내부 목표는 archive 기반 hidden-like >= 0.95와 20-case >= 18/20까지 올려야 충분히 공격적이다. leaderboard 궁극 목표는 75와 80 사이에서, 데이터 분포 개선 및 FT method 비교가 성공했을 때 도달 가능한 중간값으로 조정해야 한다.

[Detailed Explanation/Example] 따라서 궁극 leaderboard 목표는 LLM-only >= 78.00으로 확정한다. 80.00은 장기 stretch reference로 유지하되, Cycle 2 이후 즉시 판단 gate로 사용하지 않는다. offline/internal 궁극 목표는 hidden-like >= 0.95, 20-case >= 18/20, fail precision >= 93%, fail recall >= 90%, ECE <= 0.05, worst source/long bucket accuracy >= 70%, Length Coverage >= 0.50으로 확정한다. 운영적으로는 server runtime failure 0건, package < 12GB, offline first-forward PASS, 중단 후 재시작 가능성을 필수 gate로 둔다.

### Leaderboard와 offline/internal 분리 근거

[Original Text/Data] 현재 merged artifact package는 gate PASS지만 leaderboard server availability reject로 job ID가 없다.

[Exact Interpretation] 이 상태에서는 leaderboard 점수 부재를 모델 성능 실패로 해석하면 안 된다. 현재 실패는 scoring 결과가 아니라 submit server availability 문제다.

[Detailed Explanation/Example] 따라서 "유효 leaderboard job 생성"은 별도 운영 목표다. 같은 package를 서버 availability reject 상태에서 반복 제출하지 않는다. 다음 제출은 server reject가 해소되었거나 package/model/data가 이전 제출 시도와 논리적으로 달라졌다는 근거가 있을 때만 수행한다. 제출 후에는 job ID, score 또는 reject 사유, package hash, 제출 근거를 별도 archive 문서로 기록한다.

### Rule-engine 제외 근거

[Original Text/Data] 사용자 지시는 architecture에 rule engine을 포함하지 말고 LLM 기반으로만 바꾸라는 것이다. 과거 73점 rule 계열은 존재하지만 현재 방향은 LLM-only다.

[Exact Interpretation] rule 계열 점수는 목표 설정의 비교 기준으로만 사용할 수 있고, 구현 후보나 architecture 후보로 사용할 수 없다.

[Detailed Explanation/Example] 2차 leaderboard 목표 LLM-only >= 73.00은 "rule 계열 73점에 LLM-only로 도달하거나 초과한다"는 비교 목표다. 이를 위해 deterministic rule fallback, rule_id 기반 입력, rule engine architecture를 재도입하지 않는다.

## 확정 목표

### 1차 목표: 제출 가능 상태 회복과 현재 LLM-only 기준선 유지

- offline/internal: hidden-like >= 0.9146, 20-case >= 16/20, fail precision >= 90%, fail recall >= 80%, macro-F1 >= 0.72, ECE <= 0.12.
- package/runtime: package < 12GB, offline first-forward PASS, model-load PASS, data gate PASS, runtime failure 0건.
- leaderboard 운영: server availability reject가 해소된 뒤 유효 job ID 생성.
- leaderboard 점수: 유효 job 기준 LLM-only >= 70.00.

### 2차 목표: 데이터 분포와 calibration 개선이 확인된 공격적 성능 향상

- offline/internal: hidden-like >= 0.936842, 20-case >= 17/20, public-hidden gap <= 8pp, ECE <= 0.08, Length Coverage >= 0.25.
- method 비교: high-rank LoRA, DoRA, partial FT, full FT 후보 중 적어도 하나가 r16 LoRA baseline 대비 hidden-like 또는 동등 internal score에서 +3pp 이상 개선.
- package/runtime: 선택된 방법은 package < 12GB, offline first-forward PASS, 중단 후 재시작 가능, 서버 내 타인 파일 비접촉을 모두 만족.
- leaderboard 점수: LLM-only >= 73.00. 과거 rule 계열 73점은 비교 기준일 뿐 architecture 후보가 아니다.

### 궁극 목표: LLM-only 고득점과 장기 안정성

- offline/internal: hidden-like >= 0.95, 20-case >= 18/20, fail precision >= 93%, fail recall >= 90%, ECE <= 0.05, worst source/long bucket accuracy >= 70%, Length Coverage >= 0.50.
- package/runtime: server runtime failure 0건, package < 12GB, offline first-forward PASS, model-load PASS, 중단 후 재시작 가능, 제출 archive 완비.
- leaderboard 점수: LLM-only >= 78.00.
- stretch reference: LLM-only >= 80.00은 장기 상한 목표로 추적하되, 현재 Cycle 2의 필수 gate로 삼지 않는다.

## 다음 단계 적용 기준

- Cycle 4 방법 결정에서는 length/trajectory gap, source/template 다양성, label prior/calibration, FT method infra를 직접 개선하는 방법만 우선 후보로 둔다.
- Cycle 5 구현에서는 full FT, partial FT, high-rank LoRA, DoRA, QLoRA 중 package < 12GB와 offline runtime gate를 만족할 수 있는 경로를 우선한다.
- Cycle 6 실행에서는 GPU OOM 여부, 48GB 활용률, batch size, epoch, lr, loss, calibration metric, checkpoint resume 가능성을 함께 모니터링한다.
- leaderboard 제출은 하루 기회를 낭비하지 않도록, 이전 제출 시도 대비 package/model/data/runtime 조건이 무엇이 달라졌는지 명시한 뒤 수행한다.

## 민감 정보 처리

- 이 문서에는 민감 정보를 기록하지 않았다.
- 서버 접속 및 개인 인증 관련 값은 archive 목표 문서에 포함하지 않는다.
