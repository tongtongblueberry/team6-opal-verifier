# 2026-05-26 KST 08:54 - 방법론 보강 결정: full fine-tuning 및 제출 용량

## 구조 Skeleton

- cycle 위치: P1 calibration LoRA sweep 실행 중, `p1_r16_lr2e4_do20_ep5` 학습 진행 중
- branch: `cycle3/training-methods-20260526-kst`
- 목적:
  - 사용자가 지적한 "12GB 제출 제한 대비 LoRA만 쓰는 문제"를 방법론 의사결정에 반영
  - full fine-tuning, QLoRA, DoRA, AdaLoRA, target-module 확장 LoRA를 다음 cycle 후보로 정렬
  - leaderboard 제출 전 merged package 및 threshold/runtime gate 기준을 고정
- 코드 영향:
  - 코드, 데이터 흐름, 학습 실행에는 변경 없음
  - 이 문서는 결정 기록만 추가함

## 입력 자료

[Original Text/Data] -> fine-tuning 방법론 조사 agent는 LoRA, QLoRA, PEFT LoRA target-module 확장, DoRA, AdaLoRA, SFT Trainer, bitsandbytes, LOMO, LoRA vs full FT 비교, LIMA, few-sample fine-tuning 안정성, SMART, Mixout, R-Drop, calibration 논문/자료를 검토했다.

[Exact Interpretation] -> "LoRA adapter가 작다"는 현상은 LoRA의 설계상 정상이다. 그러나 제출 제한 12GB를 거의 쓰지 않는다는 사실만으로 full FT 본학습을 즉시 시작하는 것은 논리적으로 부족하다.

[Detailed Explanation/Example] -> full FT는 trainable parameter를 크게 늘려 capacity ceiling을 제거할 수 있지만, small data에서는 overfit/forgetting 위험이 크고, 48GB L40S에서 optimizer state와 activation memory가 실제 병목이 된다. 따라서 full FT는 배제하지 않되 memory dry-run, checkpoint/resume smoke, 1 epoch pilot, validation metric 개선 gate를 통과해야 한다.

[Original Text/Data] -> 제출 용량/런타임 검증 agent는 현재 실전 후보가 raw 3MB LoRA가 아니라 `32MB`급 adapter package 또는 `7.9GB`급 fp16 merged model package이며, 기존 merged 후보 archive가 약 `6.36GB`로 12GB 제한 안에 들어간다고 보고했다.

[Exact Interpretation] -> 현재 제출 구조에서 우선순위가 가장 높은 것은 최종 best adapter를 `artifacts/merged_model` 형태의 standalone fp16 merged package로 내보내는 것이다.

[Detailed Explanation/Example] -> `src/solver.py`는 `artifacts/merged_model/config.json`이 있으면 merged model을 우선 로드한다. 따라서 best 후보가 확정되면 adapter-only 제출보다 merged package + static gate + offline first-forward gate가 더 강한 제출 형태다.

## 외부 근거 요약

[EXTERNAL KNOWLEDGE] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2021). *LoRA: Low-rank adaptation of large language models*. arXiv. https://arxiv.org/abs/2106.09685

[Original Text/Data] -> LoRA는 base weight를 freeze하고 low-rank matrix만 학습한다.

[Exact Interpretation] -> 작은 adapter 크기 자체는 실패 근거가 아니다.

[Detailed Explanation/Example] -> 현재 문제는 "adapter가 작다"가 아니라 calibration precision, hidden false positive, 제출 runtime 재현성, 그리고 최종 artifact packaging gate다.

[EXTERNAL KNOWLEDGE] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). *QLoRA: Efficient finetuning of quantized LLMs*. arXiv. https://arxiv.org/abs/2305.14314

[Original Text/Data] -> QLoRA는 quantized base에 adapter gradient를 backprop하여 큰 모델을 낮은 memory로 fine-tune한다.

[Exact Interpretation] -> full FT memory gate가 실패하면 all-linear QLoRA가 가장 직접적인 대안이다.

[Detailed Explanation/Example] -> 현재 q/k/v/o LoRA만으로 capacity가 부족하다고 검증되면 `target_modules=all-linear`, rank 확대, rsLoRA/DoRA가 full FT보다 먼저 비교할 수 있는 중간 단계다.

[EXTERNAL KNOWLEDGE] Liu, S.-Y., Wang, C.-Y., Yin, H., Molchanov, P., Wang, Y.-C. F., Cheng, K.-T., & Chen, M.-H. (2024). *DoRA: Weight-decomposed low-rank adaptation*. arXiv. https://arxiv.org/abs/2402.09353

[Original Text/Data] -> DoRA는 magnitude와 direction을 분리해 LoRA와 full FT의 격차를 줄이는 방향을 제안한다.

[Exact Interpretation] -> low-rank underfit이 확인될 경우 DoRA는 full FT 전의 강한 후보이다.

[Detailed Explanation/Example] -> DoRA도 LLM 기반 fine-tuning 방법이며 rule engine을 architecture에 포함하지 않는다.

[EXTERNAL KNOWLEDGE] Zhang, Q., Chen, M., Bukharin, A., Karampatziakis, N., He, P., Cheng, Y., Chen, W., & Zhao, T. (2023). *AdaLoRA: Adaptive budget allocation for parameter-efficient fine-tuning*. arXiv. https://arxiv.org/abs/2303.10512

[Original Text/Data] -> AdaLoRA는 layer별 중요도에 따라 rank budget을 재배분한다.

[Exact Interpretation] -> 단순히 rank를 키우는 것보다 같은 adapter budget에서 더 나은 성능을 낼 수 있다.

[Detailed Explanation/Example] -> P1 sweep 이후 rank 증가가 diminishing return을 보이면 adaptive rank가 다음 후보가 된다.

[EXTERNAL KNOWLEDGE] Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). *On calibration of modern neural networks*. arXiv. https://arxiv.org/abs/1706.04599

[Original Text/Data] -> modern neural network는 accuracy가 높아도 calibration이 나쁠 수 있다.

[Exact Interpretation] -> 현재 calibration false positive 문제는 단순 accuracy만으로 판단하면 안 된다.

[Detailed Explanation/Example] -> 계속 ECE, Brier, calibration precision/recall, risk coverage를 같이 기록한다. 단, rule-based rejector나 rule engine은 architecture에 넣지 않는다.

## 결정

[Original Text/Data] -> `p1_r16_lr2e4_do20_ep5`는 2026-05-26 08:53 KST 기준 `122/215` step, GPU 약 `30.4GB`, util `100%`, OOM 징후 없이 실행 중이다.

[Exact Interpretation] -> 진행 중인 충분 학습 비교를 중단하지 않는다.

[Detailed Explanation/Example] -> 새 full FT 본학습을 지금 시작하면 P1 sweep 비교가 깨지고 GPU 자원을 충돌시킨다. 따라서 r16 및 남은 P1 설정 평가를 먼저 완료한다.

[Original Text/Data] -> 기존 r4/r8 결과는 calibration precision 목표를 통과하지 못했고, r8은 hidden false positive가 증가했다.

[Exact Interpretation] -> 아직 leaderboard 제출 GO가 아니다.

[Detailed Explanation/Example] -> 제출은 best 후보가 새 metric gate를 통과하고, 기존 제출 대비 무엇이 다른지 설명 가능하며, package gate와 서버 availability 근거가 있을 때만 수행한다.

## 다음 실행 우선순위

1. P1 sweep을 계속 진행한다. r16 평가가 생성되면 Step 1 중간평가 archive를 남긴다.
2. r16이 1차 목표를 통과하면 threshold, package threshold lock, merged export, static gate, offline first-forward를 검증한다.
3. r16이 실패하면 데이터 구조 agent, 학습 구조 agent, 문헌 agent, 종합 결정 agent로 Step 2 문제 확인을 수행한다.
4. P1 sweep 전체 완료 후 best selector를 다시 실행한다.
5. P1 전체가 목표를 만족하지 못하면 다음 방법론은 `all-linear LoRA/QLoRA`, `DoRA`, `AdaLoRA`, `full FT memory dry-run` 순서로 진행한다.
6. full FT는 다음 gate를 모두 통과해야 본학습으로 승격한다:
   - 12GB 이하 저장 가능성 실측
   - 48GB L40S에서 OOM 없는 memory dry-run
   - checkpoint/resume smoke 통과
   - 1 epoch pilot에서 validation metric 비열화 없음
   - LoRA/QLoRA/DoRA baseline 대비 충분한 metric 개선

## Leaderboard 판단

[Original Text/Data] -> 최근 제출 실패 사유는 package 오류가 아니라 `Submission is not available due to server issue`였다.

[Exact Interpretation] -> 같은 package를 같은 서버 상태에서 반복 제출하지 않는다.

[Detailed Explanation/Example] -> 새 제출은 다음 차이가 있어야 한다: P1 또는 이후 방법론에서 더 나은 후보, merged package 검증 완료, threshold 재현성 보장, 서버 availability 개선 근거.
