# Cycle 2 Step 2 문제 확인 - 최종 문제 판정

작성 시각: 2026-05-26 01:30 KST  
작성 범위: Cycle 2 문제 확인 단계의 최종 판정 기록  
원칙: architecture에는 rule engine을 포함하지 않는다. 과거 rule 기반 결과는 비교 기준으로만 언급한다.

## 구조 Skeleton

1. 문서 범위와 금지 사항
2. 입력 agent 결론 요약
3. 주요 근거
4. 최종 문제 판정 우선순위
5. 다음 검증 및 목표 설정으로 넘길 metric 후보
6. leaderboard/제출 상태 판정

## 입력 agent 결론 요약

- 데이터 구조 agent: 최신 DCv2는 leakage, 중복, 길이 JSD gate를 통과했다. 그러나 raw 381,086개 중 selected 480개만 사용되므로 데이터 양과 다양성은 제한적이다. 병목 후보는 길이/trajectory 구조 분포 불일치, source/template 다양성 부족, label prior 및 calibration 불안정 순서다.
- 학습 구조 agent: 현재 LLM-only 주 trainer는 `train_manifest_lora.py`다. 기존 충분 학습 LoRA는 recall은 좋지만 precision이 약하고, 최신 StratP0는 precision은 좋지만 lr/epoch가 보수적이라 underfit 가능성이 있다. full FT, QLoRA, DoRA, partial FT 지원은 아직 코드에 없다. `sweep_lora.py`는 rule dependency 때문에 현재 branch에서 사용 금지다.
- 논문 agent: LoRA, QLoRA, DoRA, AdaLoRA, BitFit, Prefix-Tuning, LIMA, AlpaGasus, LESS, LoRA/full FT 비교, LOMO, class-balanced loss, calibration, OOD detection 계열 근거상 small-data 문제에서는 데이터 품질, class balance, calibration, capacity 비교가 핵심이다.
- 제출 상태: merged artifact package는 static gate와 offline first-forward를 통과했다. leaderboard는 server availability reject이며 job ID가 없다.

## 주요 근거

1. [Original Text/Data] 최신 DCv2는 leakage, duplicate, length JSD gate를 통과했지만 raw 381,086개 중 selected 480개만 남았다.  
   → [Exact Interpretation] 현재 확인된 데이터 gate 기준으로는 명백한 contamination이나 중복이 1차 blocker라는 근거는 약하다. 반면 실제 학습에 쓰이는 데이터의 양과 다양성은 매우 작다.  
   → [Detailed Explanation/Example] selected 480개는 raw 후보의 극히 일부이므로, hidden set의 긴 trajectory나 새로운 source pattern을 포괄하지 못할 가능성이 크다. 따라서 다음 단계는 단순히 raw를 많이 넣는 것이 아니라 DCv2 gate를 유지한 채 long/diverse/balanced trajectory를 늘리는 방향이어야 한다.

2. [Original Text/Data] 데이터 구조 agent는 병목 1순위를 길이/trajectory 구조 분포 불일치 및 hidden-public gap으로 판정했다.  
   → [Exact Interpretation] public-like case에서는 맞지만 hidden case에서 흔들리는 주된 원인은 모델 구조보다 입력 분포의 길이와 단계 구성 차이일 가능성이 크다.  
   → [Detailed Explanation/Example] 짧은 1-2 step 학습 예시 위주로 학습하면 10 step 이상 protocol session에서 fail/pass decision boundary가 달라질 수 있다. 목표 설정 단계에서는 length bin별 accuracy, long trajectory recall, hidden-like gap을 별도 metric으로 둬야 한다.

3. [Original Text/Data] 기존 충분 학습 LoRA는 recall은 좋지만 precision이 약했고, 최신 StratP0는 precision은 좋지만 lr/epoch가 보수적이라 underfit 가능성이 있다.  
   → [Exact Interpretation] 현재 성능 문제는 단일 방향으로 단정할 수 없다. 한쪽은 fail을 과하게 잡아 precision이 낮고, 다른 쪽은 보수적으로 학습되어 recall/coverage가 부족할 수 있다.  
   → [Detailed Explanation/Example] 같은 manifest와 같은 eval split에서 epoch, lr, threshold를 통제해 비교해야 한다. fail precision, fail recall, macro-F1, calibration error를 함께 보지 않으면 단순 accuracy 상승이 실제 leaderboard 개선으로 이어지는지 판단할 수 없다.

4. [Original Text/Data] full FT, QLoRA, DoRA, partial FT 지원은 아직 코드에 없고, 현재 LLM-only 주 trainer는 `train_manifest_lora.py`다.  
   → [Exact Interpretation] 제출 용량 12GB를 활용하는 방향은 필요하지만, 현재 즉시 신뢰 가능한 학습 경로는 manifest 기반 LoRA뿐이다. full/partial/DoRA 계열은 먼저 구현과 재시작성, OOM, package gate를 검증해야 한다.  
   → [Detailed Explanation/Example] high-rank LoRA 또는 merged artifact는 현재 infra와 가장 가깝다. DoRA/QLoRA/partial FT/full FT는 구현 후 최소 pilot, 충분 학습, 동일 metric 비교를 거쳐야 한다. 단순히 더 큰 artifact를 만든다는 이유만으로 leaderboard 제출 대상이 되지는 않는다.

5. [Original Text/Data] 논문 agent는 small-data 상황에서 데이터 품질, class balance, calibration, capacity 비교가 핵심이라고 결론냈다.  
   → [Exact Interpretation] 다음 개선은 모델 capacity 확대와 데이터/threshold/calibration 검증을 분리해서 해야 한다.  
   → [Detailed Explanation/Example] LIMA, AlpaGasus, LESS 계열 근거는 고품질/영향도 높은 데이터 선별을 지지한다. Class-balanced loss와 calibration 문헌은 pass/fail label prior가 흔들릴 때 threshold와 confidence를 별도 관리해야 함을 시사한다.

6. [Original Text/Data] merged artifact package는 static gate와 offline first-forward를 통과했지만 leaderboard는 server availability reject이며 job ID가 없다.  
   → [Exact Interpretation] 현재 제출 실패는 모델 성능 실패가 아니라 외부 leaderboard availability 문제로 분류한다.  
   → [Detailed Explanation/Example] job ID가 없으므로 leaderboard score가 생성되지 않았다. 동일 artifact를 즉시 반복 제출하면 daily chance를 낭비할 수 있으므로, server reject 해소 증거가 있을 때만 제출한다.

## 최종 문제 판정 우선순위

1. 길이/trajectory 구조 분포 불일치와 hidden-public gap  
   - 판정: 최우선 병목이다. DCv2 gate가 통과됐더라도 selected set이 hidden의 긴 session 구조를 충분히 대표한다는 증거가 없다.  
   - 다음 metric 후보: length bin별 accuracy, long trajectory fail recall, hidden-like accuracy, public-hidden gap, worst-bin accuracy.

2. source/template 다양성 부족  
   - 판정: 두 번째 병목이다. public template 기반 mutation에 의존하면 public 20개에는 맞지만 hidden source pattern으로 일반화하기 어렵다.  
   - 다음 metric 후보: source group별 accuracy, template family별 macro-F1, group leakage 0 유지, unseen template holdout accuracy.

3. label prior 및 calibration 불안정  
   - 판정: 세 번째 병목이다. fail oversampling 또는 pass/fail prior 변화가 threshold를 흔들어 precision/recall tradeoff를 악화시킨다.  
   - 다음 metric 후보: fail precision, fail recall, macro-F1, ECE, Brier score, threshold sweep 안정성, logit margin bucket별 accuracy.

4. 학습 capacity와 구현 infra 미성숙  
   - 판정: 네 번째 병목이다. LoRA r16 adapter만으로는 capacity가 부족할 수 있으나, full FT/QLoRA/DoRA/partial FT는 아직 구현과 재시작성 검증이 필요하다.  
   - 다음 metric 후보: 동일 manifest 기준 LoRA r16/r32/r64, DoRA, QLoRA, partial FT 비교 accuracy; peak VRAM; OOM 여부; checkpoint resume 성공; merged package size < 12GB; offline first-forward PASS.

## 다음 검증 및 목표 설정으로 넘길 metric 후보

- 1차 목표 후보: hidden-like accuracy >= 72%, fail precision >= 90%, fail recall >= 80%, package static gate PASS, offline first-forward PASS.
- 2차 목표 후보: hidden-like accuracy >= 75%, macro-F1 개선, public-hidden gap <= 8pp, worst length/source group accuracy >= 60%, ECE <= 0.08.
- 궁극 목표 후보: LLM-only leaderboard >= 75, adapter-only 대비 +3pp 이상, package < 12GB, server-side runtime failure 0건.

## leaderboard/제출 상태 판정

- 현재 leaderboard 제출은 NO-GO다.
- 이유: 마지막 제출 시도는 server availability reject였고 job ID가 없다.
- 다음 제출 조건: 새 artifact가 기존 제출 실패와 다른 점을 명확히 가져야 하고, static gate, offline first-forward, size gate, archive 기록이 모두 있어야 하며, server reject가 해소됐다는 증거가 있어야 한다.
