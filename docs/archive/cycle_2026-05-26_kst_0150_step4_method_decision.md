# Cycle 2 Step 4 최종 방법 결정

- 기준 시각: 2026-05-26 01:50 KST
- 역할: 최종 방법 결정 및 기록 agent
- 범위: LLM-only 학습/평가/패키징 방법 결정
- 금지: architecture에 rule engine 포함 금지, public 20 직접 최적화 금지, 민감 정보 기록 금지

## 구조 Skeleton

1. 결정 범위
   - Cycle 2 Step 3 목표를 달성하기 위한 Step 5 구현 대상을 결정한다.
   - 제출 실패와 점수 개선 문제를 분리한다.
   - LLM-only 원칙을 유지한다.
2. 입력 근거
   - 방법론 논문 agent 결론
   - 학습 원리 agent 결론
   - repo 구현 검증 agent 결론
   - 서버 기존 학습 결과
   - Step 3 목표
3. 최종 방법 우선순위
   - P0: manifest-only sweep/eval infra
   - P1: 충분 학습된 r16 LoRA baseline 재확인
   - P2: r32/r64 high-rank LoRA 비교
   - P3: calibration/threshold 및 label-prior ablation
   - P4: DoRA/partial FT pilot
   - P5: QLoRA/full FT pilot-gated 확장
4. 보류 방법 및 이유
   - full fine-tuning은 적극 고려 대상이나 즉시 본학습 대상은 아니다.
   - GPU, 재시작성, checkpoint/resume, package risk를 먼저 통과해야 한다.
5. Step 5 구현 작업 목록
   - 실제 구현 agent가 수행할 순서와 gate를 명시한다.

## 주요 근거

### 1. 현재 우선 문제는 제출 runtime/package와 점수 개선의 분리다

[Original Text/Data]
Cycle 1에서 LLM-only offline/package gate를 수정했고, 실제 `/workspace/team6/submit-final`은 offline first-forward를 통과했다. 그러나 leaderboard 제출은 job 생성 전 server issue로 reject되었다.

→ [Exact Interpretation]
현재 leaderboard 실패는 모델 점수 실패가 아니라 제출 서버 availability 문제다. 따라서 Step 5는 같은 package를 반복 제출하지 않고, 유효 job 생성 조건이 회복될 때까지 model/package 개선을 별도로 진행해야 한다.

→ [Detailed Explanation/Example]
같은 artifact를 즉시 재제출하면 하루 제출 기회를 낭비할 수 있다. 제출은 새 학습 결과, 새 artifact, 새 runtime evidence, 또는 서버 availability 회복 증거 중 하나가 있을 때만 논리적으로 정당화된다.

### 2. 기존 r16 LoRA는 충분 학습과 calibration 사이의 tradeoff가 있다

[Original Text/Data]
서버 기록상 `dcv2 r16 lr=1e-3 ep5`는 hidden-like `0.936842`, fail recall `1.0`, fail precision `0.8776`이다. `stratp0 lr=5e-5 ep3`는 hidden-like `0.9146`, fail precision `1.0`, fail recall `0.8333`이다.

→ [Exact Interpretation]
`lr=1e-3 ep5`는 충분히 학습되어 recall과 hidden-like accuracy가 높지만 precision 목표 `>=90%`에는 미달한다. 반대로 `lr=5e-5 ep3`는 precision은 좋지만 underfit 가능성이 있고 2차 hidden-like 목표에는 약하다.

→ [Detailed Explanation/Example]
Step 5에서는 r16 baseline을 다시 학습하되 `lr=1e-3/5e-4`, dropout `0.1/0.05`, `bs=2`, `ga=4`, 5 epoch 조건을 동일 manifest-only 평가로 비교해야 한다. 이 비교가 있어야 r32/r64, DoRA, partial/full FT가 실제로 r16보다 나은지 판단할 수 있다.

### 3. 기존 sweep_lora.py는 사용 금지이며 manifest-only runner가 필요하다

[Original Text/Data]
repo 구현 검증에서 `sweep_lora.py` 등 일부 스크립트는 rule dependency, public 20, 또는 legacy verifier 의존이 있어 사용 금지로 분류되었다. 안전한 주 학습 경로는 `train_manifest_lora.py`, 주 평가 경로는 `eval_manifest_adapter.py`로 판단되었다.

→ [Exact Interpretation]
Cycle 2 이후 sweep은 기존 legacy sweep 경로가 아니라 DCv2 manifest-only 학습/평가 경로로 새로 구성해야 한다.

→ [Detailed Explanation/Example]
Step 5 구현은 `train_manifest_lora.py`에 LoRA hyperparameter CLI를 추가하고, 별도 manifest-only sweep runner가 이 trainer와 evaluator만 호출하도록 해야 한다. architecture에는 rule engine을 넣지 않고, 평가도 rule fallback 없이 pass/fail token-logit 기반 metric으로 기록한다.

### 4. high-rank LoRA는 가장 빠른 capacity 확장 방법이다

[Original Text/Data]
repo 검증 결과 `train_manifest_lora.py`는 현재 LoRA `r=16`, `alpha=32`, `dropout=0.1`로 고정되어 있다. high-rank LoRA는 `--lora-r`, `--lora-alpha`, `--lora-dropout`, `--target-modules` CLI 확장으로 빠르게 구현 가능하다.

→ [Exact Interpretation]
Step 5의 첫 모델 capacity 확장 대상은 r32/r64 high-rank LoRA다. 구현 비용이 낮고, 기존 checkpoint/resume/package 흐름을 유지할 수 있다.

→ [Detailed Explanation/Example]
먼저 r16 baseline을 동일 조건으로 재확인한 뒤 r32를 5 epoch 학습한다. r32가 precision/recall/ECE 중 하나라도 명확히 개선하면 r64를 같은 protocol로 실행한다. 모든 run은 loss, grad_norm, epoch별 hidden-like metric, GPU peak, checkpoint resume 가능 여부, merged package smoke를 기록해야 한다.

### 5. calibration/threshold가 precision 목표의 직접 병목이다

[Original Text/Data]
dcv2 r16은 hidden-like `0.936842`와 recall `1.0`을 달성했지만 precision `0.8776`으로 1차 precision 목표 `>=90%`에 미달했다. Step 3 목표에는 ECE `<=0.12`가 포함되어 있다.

→ [Exact Interpretation]
단순히 더 강한 모델을 학습하는 것만으로는 목표 달성이 보장되지 않는다. precision 목표를 달성하려면 threshold sweep, ECE, Brier score, macro-F1, balanced accuracy를 평가 pipeline에 추가해야 한다.

→ [Detailed Explanation/Example]
동일 adapter라도 threshold가 바뀌면 false positive와 false negative tradeoff가 바뀐다. 따라서 Step 5는 `eval_manifest_adapter.py`에 calibration metric과 threshold sweep을 추가하고, leaderboard 제출 후보는 default threshold가 아니라 validation에서 결정한 threshold와 package runtime을 함께 기록해야 한다.

### 6. 데이터 쪽 P0는 long trajectory와 source 다양성이다

[Original Text/Data]
방법론 논문 agent와 데이터 구조 agent는 P0를 data quality, long trajectory coverage, source/template 다양성, calibration으로 제안했다. 기존 archive에는 길이/trajectory 구조 분포 불일치와 public-template 의존성이 병목 후보로 남아 있다.

→ [Exact Interpretation]
학습 방법만 키우는 것은 불충분하다. Step 5에서 모델 sweep infra를 만들면서 length/source/label bucket별 metric을 같이 기록해야 한다.

→ [Detailed Explanation/Example]
Length Coverage `>=0.25`가 2차 목표이므로, 평가 결과는 전체 accuracy 하나가 아니라 long bucket accuracy, worst source bucket, label별 precision/recall까지 포함해야 한다. 다만 Step 5의 첫 구현은 새 데이터 생성보다 manifest-only 평가/학습 infra를 먼저 안정화한다. 그래야 이후 long trajectory data를 추가했을 때 효과를 분리해 판단할 수 있다.

### 7. DoRA와 partial FT는 pilot 대상이다

[Original Text/Data]
방법론 agent는 DoRA + class-balanced ablation을 P2, partial FT를 P3로 제안했다. repo 검증에서는 DoRA와 partial FT가 현재 미구현이며, LoRA CLI 확장보다 변경 범위가 크다고 판단했다.

→ [Exact Interpretation]
DoRA와 partial FT는 무시하지 않되, r16/r32/r64 LoRA와 calibration metric이 준비된 뒤 pilot로 들어가야 한다.

→ [Detailed Explanation/Example]
DoRA는 LoRA config에 옵션을 추가하는 수준으로 시작할 수 있지만 dependency/version compatibility를 확인해야 한다. partial FT는 selective unfreeze, optimizer group, checkpoint 저장 형식, package export 방식을 바꾸므로 dry-run과 resume 검증 없이는 본학습으로 바로 가면 위험하다.

### 8. full fine-tuning은 적극 고려하되 pilot-gated로 둔다

[Original Text/Data]
사용자는 제출 용량이 12GB인데 LoRA만 사용해 3MB 수준인 것은 문제가 있을 수 있으므로 full fine-tuning 또는 다른 fine-tuning 방법을 적극 고려하라고 지시했다. 서버 검증상 GPU는 L40S 약 48GB급이고, merged candidate는 약 `7.9G`로 12GB 제한 안에 들어간다.

→ [Exact Interpretation]
full FT는 capacity 측면에서 반드시 후보에 포함해야 한다. 그러나 즉시 full FT 본학습을 시작하기보다는 GPU memory, checkpoint/resume, package size, offline first-forward를 통과하는 pilot gate 이후 확장해야 한다.

→ [Detailed Explanation/Example]
full FT는 LoRA보다 trainable parameter가 훨씬 많아 optimizer state와 gradient memory가 커진다. 48GB GPU에서 OOM이 발생할 수 있고, 중간 중단 후 재시작 가능한 checkpoint 구조도 LoRA와 다르다. 또한 full model 저장은 12GB package 제한에 직접 닿기 때문에 shard size, dtype, tokenizer 포함 여부, stale shard 제거, offline loader 검증이 필요하다. 따라서 Step 5에서는 full FT를 보류가 아니라 `pilot-gated active candidate`로 지정한다. 먼저 partial FT 또는 memory-efficient full FT dry-run을 수행하고, 성공 시 1 epoch pilot, 이후 metric이 r16/r32 대비 의미 있게 개선될 때만 3-5 epoch 본학습으로 확장한다.

## 최종 방법 결정

### 채택

1. Step 5의 첫 구현 대상은 manifest-only sweep/eval infra다.
2. `train_manifest_lora.py`를 LoRA hyperparameter가 CLI로 조절되도록 확장한다.
3. `eval_manifest_adapter.py`에 ECE, Brier, macro-F1, balanced accuracy, threshold sweep, bucket별 metric을 추가한다.
4. r16 baseline을 충분 학습 조건으로 재확인한다.
5. r32 → r64 순서로 high-rank LoRA를 충분 학습 비교한다.
6. 모든 run은 checkpoint/resume, GPU peak, loss/grad_norm, package size, offline first-forward를 기록한다.
7. leaderboard는 server availability reject가 해소되고, 이전 제출과 다른 학습 결과 또는 artifact 근거가 있을 때만 시도한다.

### 보류하되 active candidate로 유지

1. DoRA
   - 이유: 구현 변경은 중간 규모이나 dependency/version 확인이 필요하다.
   - gate: r32/r64 LoRA baseline과 동일 metric으로 5 epoch pilot 비교.
2. partial FT
   - 이유: selective unfreeze, optimizer group, checkpoint/save 경로가 필요하다.
   - gate: memory dry-run, resume 검증, 1 epoch pilot metric.
3. QLoRA
   - 이유: 48GB GPU에서는 high-rank LoRA가 먼저 가능하고, QLoRA는 quantization dependency와 merge/export 검증이 추가된다.
   - gate: OOM이 발생하거나 r64 이상이 memory-bound일 때 우선순위 상승.
4. full FT
   - 이유: 사용자 지시상 적극 고려 대상이지만, GPU memory와 optimizer state, 재시작성, 12GB package 제한, offline first-forward risk가 크다.
   - gate: memory dry-run PASS, checkpoint/resume PASS, package `<12GB` 예상 PASS, 1 epoch pilot에서 r16 또는 r32 대비 개선 신호 확인.

## Step 5 구현 작업 목록

1. `train_manifest_lora.py`에 LoRA CLI 확장 구현
   - `--lora-r`
   - `--lora-alpha`
   - `--lora-dropout`
   - `--target-modules`
   - run config JSON에 실제 적용 hyperparameter 기록

2. manifest-only sweep runner 신규 구현
   - 기존 `sweep_lora.py` 사용 금지
   - `train_manifest_lora.py`와 `eval_manifest_adapter.py`만 호출
   - 실험 단위별 run directory, config, stdout/stderr, checkpoint, eval result 저장
   - 중단 후 재시작 가능해야 함

3. `eval_manifest_adapter.py` metric 확장
   - accuracy
   - macro-F1
   - balanced accuracy
   - fail precision/recall/F1
   - ECE
   - Brier score
   - threshold sweep
   - length/source/label bucket metric

4. r16 baseline 재학습 실행
   - 후보 A: `lr=1e-3`, dropout `0.1`, `bs=2`, `ga=4`, 5 epoch
   - 후보 B: `lr=1e-3`, dropout `0.05`, `bs=2`, `ga=4`, 5 epoch
   - 후보 C: `lr=5e-4`, dropout `0.1`, `bs=2`, `ga=4`, 5 epoch
   - 후보 D: `lr=5e-4`, dropout `0.05`, `bs=2`, `ga=4`, 5 epoch

5. high-rank LoRA 실행
   - r32, alpha 64, dropout `0.05/0.1`, 5 epoch
   - r32가 r16 대비 metric 또는 calibration 개선 시 r64, alpha 128 실행
   - 각 run은 동일 manifest, 동일 split, 동일 평가 protocol 사용

6. package/export 검증 연결
   - best adapter를 merged artifact로 export
   - package size `<12GB` 확인
   - offline model-load 및 first-forward PASS 확인
   - no-rule architecture scan PASS 확인

7. full FT pilot 준비
   - 즉시 본학습이 아니라 dry-run 구현부터 수행
   - GPU peak memory 측정
   - checkpoint/resume 검증
   - 1 epoch pilot 저장/로드/package 예상 크기 검증
   - r16/r32 대비 개선 신호가 있을 때만 3-5 epoch full FT로 확장

8. archive 및 git 관리
   - 각 run의 시작/종료/metric/package 결과를 KST 기준 한글 md로 기록
   - 코드 변경은 기능 단위로 commit
   - leaderboard 제출 시도는 job 생성 여부와 reject 사유까지 별도 archive로 기록
