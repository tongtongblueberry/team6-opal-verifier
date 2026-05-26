# 2026-05-26 KST 06:20 - Step2 문제 확인 결정

## 구조 Skeleton
- 입력 agent
- 현재 leaderboard 제출 병목
- 모델 성능 병목
- Step3으로 넘길 metric 후보
- 당장 하지 말아야 할 것
- 결정

## 입력 agent
- 데이터 구조 기반 검증 agent:
  - hard gate는 통과했으나 selected manifest가 작고 calibration split이 작다.
  - selected manifest는 모두 `1-32` 길이 bin에 몰려 있으며 long trajectory coverage 근거가 약하다.
  - hidden split으로 threshold를 고른 점이 selection bias를 만든다.
- 학습 구조 기반 검증 agent:
  - 최종 개선 원인은 rank 증가가 아니라 `r16 + lr=5e-4 + dropout=0.10 + threshold=0.70` 조합이다.
  - r32/r64는 trainable params를 늘렸지만 hidden fail precision과 ECE가 악화됐다.
- 논문 검토 agent:
  - Guo et al. (2017), Kumar et al. (2019), Cawley and Talbot (2010), Ovadia et al. (2019), Desai and Durrett (2020), Hu et al. (2022), Wang et al. (2023) 등은 calibration, model selection bias, dataset shift, LoRA uncertainty 문제를 직접 지지한다.
- 결론 통합 agent:
  - 현재 성능 병목은 calibration-first threshold 부재, 작은 calibration split, 길이/trajectory coverage 부족, rank 증가에 따른 false positive/ECE 악화 순서다.

## 현재 leaderboard 제출 병목
[Original Text/Data] 최신 제출은 archive 생성 `6363.38 MB`와 availability check까지 도달했지만 아래 메시지로 거절됐다.

```text
Submission rejected.
Reason: Submission is not available due to server issue. please check TA's announcement
```

`submit --list`는 여전히 `34 submission(s) for team6`이며 새 submission ID와 job ID가 없다.

[Exact Interpretation] 현재 제출 병목은 모델 성능, `uv.lock`, `submit` CLI 사용법, package size, static gate 문제가 아니라 서버 availability 외부 상태다.

[Detailed Explanation/Example] 이번 시도는 `uv.lock`을 포함했고 `submit -d`로 실행했으며 static package gate가 PASS였다. archive 생성과 availability check까지 도달했으므로 제출 패키지 계약 문제는 해소됐다. 같은 서버 상태에서 동일 패키지를 즉시 반복 제출하는 것은 정보 이득이 작다.

## 모델 성능 병목
### 1순위: hidden split 기준 threshold 선택
[Original Text/Data] 최종 후보 `r16_lr5e4_do10_ep5@threshold=0.70`의 hidden metric은 accuracy `0.9684210526`, precision_fail `0.9545454545`, recall_fail `0.9767441860`, ECE `0.0455764314`, Brier `0.0387454765`다.

[Exact Interpretation] 수치는 현재 sweep 내 최고 성능이지만, threshold가 calibration-first가 아니라 hidden 기준으로 선택된 상태라 최종 일반화 근거가 약하다.

[Detailed Explanation/Example] Cawley and Talbot (2010)은 유한 sample에서 model-selection criterion을 최적화하면 selection bias가 생긴다고 설명한다. 따라서 hidden으로 threshold를 고르면 hidden은 더 이상 no-peek test가 아니다. 다음 cycle에서는 calibration split에서 threshold를 고르고 hidden은 검증용으로 보존한다.

### 2순위: 작은 calibration split과 불안정한 calibration
[Original Text/Data] manifest split은 train/calibration/hidden = `337/48/95`다. r16 계열 calibration precision은 `0.8275862069` 또는 `0.8333333333`, ECE는 대략 `0.1046~0.1186`이다.

[Exact Interpretation] hidden 성능이 좋은 threshold가 calibration split에서는 fail precision 목표 `0.90`을 넘지 못한다.

[Detailed Explanation/Example] Guo et al. (2017)은 confidence score와 accuracy가 분리될 수 있음을 보였고, Kumar et al. (2019)은 calibration 추정에 충분한 sample이 필요함을 지적한다. calibration split `48`개로 threshold 후보를 많이 비교하면 FP 추정 분산이 커진다.

### 3순위: 길이 및 trajectory coverage 부족
[Original Text/Data] selected manifest는 raw `381086`개 중 `480`개이며, selected length bin은 모두 `1-32`다. reference에는 `65-128`, `129-256`, `257-512`, `513-1024` bin도 존재한다.

[Exact Interpretation] length JSD hard gate는 통과했지만, long protocol step 또는 trajectory 구조를 대표한다는 근거가 부족하다.

[Detailed Explanation/Example] Ross et al. (2011)은 sequential prediction에서 정적 i.i.d. split이 실제 trajectory 오류를 과소평가할 수 있음을 보인다. 다음 cycle은 `step_count` 또는 long trajectory bucket별 metric을 추가해야 한다.

### 4순위: 단순 capacity 증가의 false positive 악화
[Original Text/Data] r32 hidden metric은 accuracy `0.9368421053`, precision_fail `0.8775510204`, FP `6`, ECE `0.0491373698`이다. r64 hidden metric은 accuracy `0.8421052632`, precision_fail `0.7413793103`, FP `15`, ECE `0.1400879140`이다.

[Exact Interpretation] 현재 병목은 rank 부족 단독 문제가 아니다.

[Detailed Explanation/Example] r64는 trainable params `12,582,912`로 r16의 4배지만 pass를 fail로 과예측했다. LoRA rank 증가나 full fine tuning은 data quality, calibration, risk-coverage 검증 없이 본학습으로 확대하면 안 된다.

## Step3으로 넘길 metric 후보
- leaderboard:
  - 유효 submission ID 및 job ID 생성
  - LLM-only public score `>=70.00`, 이후 `>=73.00`
- calibration-first threshold:
  - calibration에서 threshold 1회 선택
  - hidden no-peek 평가 유지
  - threshold drift 기록
- classification:
  - hidden-like accuracy
  - fail precision
  - fail recall
  - macro-F1
  - FP count
- calibration:
  - ECE
  - Brier score
  - wrong-positive confidence distribution
  - risk-coverage curve 또는 FP-coverage curve
- data coverage:
  - length bucket coverage
  - `step_count` 또는 trajectory bucket coverage
  - worst source/template accuracy
  - source effective group count
  - duplicate/group leakage/public-holdout/rule-context hit `0`
- package/runtime:
  - package `<12GB`
  - offline first-forward PASS
  - runtime failure `0`

## 당장 하지 말아야 할 것
- 서버 availability 정상화 근거 없이 동일 패키지를 즉시 반복 제출하지 않는다.
- hidden split으로 threshold를 다시 고르지 않는다.
- r64 이상 rank 확대 또는 full fine tuning 본학습을 바로 주력으로 잡지 않는다.
- fail oversampling이나 label prior 왜곡으로 단기 hidden score만 끌어올리지 않는다.
- rule engine을 architecture 대안으로 넣지 않는다.

## 결정
Step2 문제 확인의 최종 결정은 다음과 같다.

1. leaderboard 병목은 서버 availability 외부 상태다. 제출 패키지 계약 문제는 이번 시도에서 해소됐다.
2. 모델 병목 1순위는 hidden 기준 threshold 선택으로 인한 selection bias다.
3. 모델 병목 2순위는 작은 calibration split과 calibration 불안정성이다.
4. 모델 병목 3순위는 long/trajectory coverage 부족이다.
5. 모델 병목 4순위는 단순 capacity 증가가 pass false positive와 ECE를 악화한다는 점이다.

다음 Step3 목표 설정은 `calibration-first threshold`, `hidden no-peek`, `risk-coverage/FP`, `length/trajectory coverage`, `LLM-only valid submission`을 동시에 만족하는 목표로 잡는다.
