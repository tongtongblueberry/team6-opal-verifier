# Cycle 2 Step 4 목표 달성 방법론 논문 조사

## 구조 Skeleton

- 문서 목적: Cycle 2 Step 3에서 확정한 1차, 2차, 궁극 목표를 달성하기 위한 LLM-only 방법론을 논문 근거로 비교한다.
- 입력 목표: hidden-like, 20-case, leaderboard, calibration, Length Coverage, package/runtime gate.
- 조사 범위: full fine-tuning, partial fine-tuning, high-rank LoRA, QLoRA, DoRA, data selection/quality filtering, calibration/thresholding, class-balanced sampling.
- 비교 기준: 적용 난이도, 48GB GPU OOM risk, package < 12GB 가능성, 재시작성, 우선순위.
- 결정 형식: 주요 근거는 `[Original Text/Data] -> [Exact Interpretation] -> [Detailed Explanation/Example]` 형식으로 기록한다.
- 제외 사항: deterministic rule architecture, protocol rule fallback, rule-derived input feature는 방법론 후보에서 제외한다.
- 출력: Step 5 구현 후보의 우선순위와 실행 조건을 확정한다.

## 입력 목표

- 1차 목표: hidden-like >= 0.9146, 20-case >= 16/20, fail precision >= 90%, fail recall >= 80%, ECE <= 0.12, package < 12GB, offline first-forward PASS, 유효 leaderboard job 생성, LLM-only score >= 70.00.
- 2차 목표: hidden-like >= 0.936842, 20-case >= 17/20, public-hidden gap <= 8pp, ECE <= 0.08, Length Coverage >= 0.25, r16 LoRA 대비 +3pp 이상, LLM-only leaderboard >= 73.00.
- 궁극 목표: hidden-like >= 0.95, 20-case >= 18/20, fail precision >= 93%, fail recall >= 90%, ECE <= 0.05, worst source/long bucket >= 70%, Length Coverage >= 0.50, runtime failure 0건, LLM-only leaderboard >= 78.00.

## [EXTERNAL KNOWLEDGE] 근거 논문

- Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). *LoRA: Low-rank adaptation of large language models*. International Conference on Learning Representations. https://arxiv.org/abs/2106.09685
- Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). *QLoRA: Efficient finetuning of quantized LLMs*. Advances in Neural Information Processing Systems. https://arxiv.org/abs/2305.14314
- Liu, S.-Y., Wang, C.-Y., Yin, H., Molchanov, P., Wang, Y.-C. F., Cheng, K.-T., & Chen, M.-H. (2024). *DoRA: Weight-decomposed low-rank adaptation*. arXiv. https://arxiv.org/abs/2402.09353
- Zhang, Q., Chen, M., Bukharin, A., Karampatziakis, N., He, P., Cheng, Y., Chen, W., & Zhao, T. (2023). *AdaLoRA: Adaptive budget allocation for parameter-efficient fine-tuning*. International Conference on Learning Representations. https://arxiv.org/abs/2303.10512
- Biderman, D., Portes, J., Ortiz, J. J. G., Paul, M., Greengard, P., Jennings, C., King, D., Havens, S., Chiley, V., Frankle, J., Blakeney, C., & Cunningham, J. P. (2024). *LoRA learns less and forgets less*. Transactions on Machine Learning Research. https://arxiv.org/abs/2405.09673
- Lv, K., Yang, Y., Liu, T., Gao, Q., Guo, Q., & Qiu, X. (2023). *Full parameter fine-tuning for large language models with limited resources*. arXiv. https://arxiv.org/abs/2306.09782
- Malladi, S., Gao, T., Nichani, E., Damian, A., Lee, J. D., Chen, D., & Arora, S. (2023). *Fine-tuning language models with just forward passes*. Advances in Neural Information Processing Systems. https://arxiv.org/abs/2305.17333
- Ben Zaken, E., Ravfogel, S., & Goldberg, Y. (2022). *BitFit: Simple parameter-efficient fine-tuning for transformer-based masked language-models*. Association for Computational Linguistics. https://arxiv.org/abs/2106.10199
- Li, X. L., & Liang, P. (2021). *Prefix-tuning: Optimizing continuous prompts for generation*. Association for Computational Linguistics. https://arxiv.org/abs/2101.00190
- Chen, Y., Qian, S., Tang, H., Lai, X., Liu, Z., Han, S., & Jia, J. (2023). *LongLoRA: Efficient fine-tuning of long-context large language models*. arXiv. https://arxiv.org/abs/2309.12307
- Jain, N., Chiang, P.-Y., Wen, Y., Kirchenbauer, J., Chu, H.-M., Somepalli, G., Bartoldson, B. R., Kailkhura, B., Schwarzschild, A., Saha, A., Goldblum, M., Geiping, J., & Goldstein, T. (2023). *NEFTune: Noisy embeddings improve instruction finetuning*. arXiv. https://arxiv.org/abs/2310.05914
- Zhou, C., Liu, P., Xu, P., Iyer, S., Sun, J., Mao, Y., Ma, X., Efrat, A., Yu, P., Yu, L., Zhang, S., Ghosh, G., Lewis, M., Zettlemoyer, L., & Levy, O. (2023). *LIMA: Less is more for alignment*. Advances in Neural Information Processing Systems. https://arxiv.org/abs/2305.11206
- Chen, L., Li, S., Yan, J., Wang, H., Gunaratna, K., Yadav, V., Tang, Z., Srinivasan, V., Zhou, T., Huang, H., & Jin, H. (2024). *AlpaGasus: Training a better Alpaca with fewer data*. International Conference on Learning Representations. https://arxiv.org/abs/2307.08701
- Xia, M., Malladi, S., Gururangan, S., Arora, S., & Chen, D. (2024). *LESS: Selecting influential data for targeted instruction tuning*. International Conference on Machine Learning. https://arxiv.org/abs/2402.04333
- Liu, W., Zeng, W., He, K., Jiang, Y., & He, J. (2024). *What makes good data for alignment? A comprehensive study of automatic data selection in instruction tuning*. International Conference on Learning Representations. https://arxiv.org/abs/2312.15685
- Cui, Y., Jia, M., Lin, T.-Y., Song, Y., & Belongie, S. (2019). *Class-balanced loss based on effective number of samples*. IEEE/CVF Conference on Computer Vision and Pattern Recognition. https://arxiv.org/abs/1901.05555
- Lin, T.-Y., Goyal, P., Girshick, R., He, K., & Dollár, P. (2017). *Focal loss for dense object detection*. IEEE International Conference on Computer Vision. https://arxiv.org/abs/1708.02002
- Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). *On calibration of modern neural networks*. International Conference on Machine Learning. https://proceedings.mlr.press/v70/guo17a.html

## 주요 근거

### 근거 1: 현재 병목은 모델 capacity만이 아니라 data distribution과 calibration이다

[Original Text/Data] Step 3 확정 목표는 hidden-like >= 0.9146에서 시작해 0.936842, 0.95까지 올리고, ECE를 0.12, 0.08, 0.05로 낮추며, Length Coverage를 0.25, 0.50까지 올리는 것이다. Cycle 2 문제 판정은 length/trajectory gap, source/template 다양성 부족, label prior/calibration 불안정을 핵심 병목으로 기록했다. LIMA, AlpaGasus, LESS, automatic data selection 연구는 instruction tuning에서 데이터 품질과 target 영향도가 데이터 양만큼 중요하다는 근거를 제공한다.

[Exact Interpretation] full fine-tuning부터 실행하는 것은 목표와 병목의 순서가 맞지 않다. 우선 data selection, quality filtering, long trajectory coverage, pass/fail prior 보존, calibration을 고쳐야 한다.

[Detailed Explanation/Example] 현재 r16 LoRA가 hidden-like 0.9146 또는 그 이상 내부 점수를 만든 기록이 있으므로, 다음 2차 목표는 단순히 optimizer를 더 크게 쓰는 문제가 아니다. 긴 session, 다양한 source, pass/fail 균형, ambiguous/noisy sample 제거를 먼저 통제해야 20-case와 hidden-like가 동시에 오른다. 따라서 Step 5의 1순위 구현은 새로운 model class가 아니라 manifest audit, selected data build, per-bucket evaluation, threshold/calibration report다.

### 근거 2: high-rank LoRA와 DoRA는 full fine-tuning 전의 합리적 capacity 확장이다

[Original Text/Data] LoRA는 low-rank update로 효율적인 adaptation을 제공한다. AdaLoRA는 rank budget을 layer importance에 따라 조정한다. DoRA는 weight magnitude와 direction을 분해해 LoRA보다 full fine-tuning에 가까운 capacity를 목표로 한다. LoRA Learns Less and Forgets Less는 LoRA가 full fine-tuning보다 덜 배우는 경향이 있음을 분석한다.

[Exact Interpretation] 사용자가 지적한 "LoRA만 3MB" 문제는 타당한 capacity 문제다. 하지만 48GB 단일 GPU와 12GB package limit에서는 곧바로 full fine-tuning보다 high-rank LoRA, AdaLoRA, DoRA를 충분히 학습하고 merged artifact로 패키징하는 쪽이 우선이다.

[Detailed Explanation/Example] r16 LoRA adapter만 제출하면 package 용량을 거의 쓰지 못한다. r32/r64 LoRA나 DoRA를 학습한 뒤 base+adapter를 merged FP16/BF16 artifact로 export하면 제출물은 약 8-10GB가 되어 12GB 제한을 활용한다. runtime에서는 LoRA dependency 없이 standalone causal LM으로 로드할 수 있으므로 package 안정성도 좋아진다.

### 근거 3: QLoRA는 memory 절약 수단이지 현재 4B 모델의 1순위 성능 개선책은 아니다

[Original Text/Data] QLoRA는 quantized base와 LoRA를 조합해 큰 모델을 제한된 GPU에서 fine-tune할 수 있게 한다. 현재 서버는 L40S 48GB급 GPU이고, 대상 base는 Qwen3.5-4B다.

[Exact Interpretation] QLoRA는 full/partial fine-tuning이 OOM을 일으키거나 batch/sequence length를 늘릴 때 우선 검토할 수 있다. 그러나 현재 4B + 48GB 조건에서는 quantization으로 생기는 학습/런타임 복잡도가 성능 개선의 직접 원인이라고 보기 어렵다.

[Detailed Explanation/Example] QLoRA를 쓰면 VRAM은 줄지만 bitsandbytes, quantization config, merge/export path, offline runtime gate가 추가된다. leaderboard package 안정성이 이미 주요 문제였으므로, QLoRA는 "OOM 대응 후보"로 두고 high-rank LoRA/DoRA/partial FT가 실패할 때 올린다. 선택 시에도 최종 package는 quantized runtime dependency가 아니라 검증된 merged artifact로 제출해야 한다.

### 근거 4: partial fine-tuning은 full fine-tuning의 위험을 줄이는 중간 단계다

[Original Text/Data] BitFit은 bias-only update가 작은 데이터에서 경쟁적인 PEFT baseline이 될 수 있음을 보인다. Prefix-tuning은 continuous prompt parameter만으로 task adaptation이 가능함을 보인다. full parameter limited-resource 연구는 제한된 자원에서 full update를 시도하는 방법을 다룬다.

[Exact Interpretation] partial fine-tuning은 full fine-tuning보다 OOM risk와 overfit risk가 낮고, LoRA보다 큰 capacity를 줄 수 있다. 이 프로젝트에서는 top transformer block 일부, layernorm, lm_head 또는 bias 계열을 단계적으로 unfreeze하는 방식이 현실적인 중간 후보이다.

[Detailed Explanation/Example] partial FT는 optimizer state 때문에 r16/r64 LoRA보다 메모리를 더 쓰지만, 전체 4B full Adam update보다는 통제하기 쉽다. 먼저 1-batch memory dry-run, 200-500 step pilot, epoch checkpoint resume 검증을 통과한 뒤 3-5 epoch 본학습으로 확장한다.

### 근거 5: full fine-tuning은 적극 고려하되, naive Adam full FT는 48GB에서 위험하다

[Original Text/Data] full parameter fine-tuning과 MeZO 계열 연구는 제한 자원에서도 full update를 시도하는 방법을 제안한다. 하지만 4B parameter 모델의 naive Adam full FT는 parameter, gradient, optimizer state, activation memory를 모두 요구한다.

[Exact Interpretation] full FT는 사용자가 요구한 대로 후보에 포함해야 하지만, Step 5의 즉시 1순위는 아니다. OOM, checkpoint 크기, 재시작성, 학습 안정성 risk가 높기 때문이다.

[Detailed Explanation/Example] 최종 merged model package 자체는 FP16/BF16 기준 12GB 안에 들어갈 가능성이 높다. 문제는 학습 중 memory와 optimizer state다. 따라서 full FT는 LOMO/MeZO 또는 FSDP/ZeRO가 안정적으로 구성되는 경우에만 pilot한다. 이 프로젝트의 단기 목표인 유효 leaderboard job 생성과 runtime failure 0건을 해치지 않도록 high-rank LoRA/DoRA/partial FT 이후에 배치한다.

### 근거 6: class-balanced sampling과 calibration은 fail precision/recall 목표에 직접 대응한다

[Original Text/Data] class-balanced loss는 class imbalance에서 effective number 기반 가중치를 제안한다. Focal loss는 hard example에 더 큰 loss를 부여한다. modern neural network calibration 연구는 temperature scaling과 ECE 평가의 필요성을 보인다.

[Exact Interpretation] fail precision >= 90%, fail recall >= 80/90%, ECE <= 0.12/0.08/0.05 목표를 동시에 만족하려면 class prior와 threshold를 모델 학습/eval protocol에 포함해야 한다.

[Detailed Explanation/Example] 과거 기록에는 fail oversampling이 threshold와 precision을 흔든 사례가 있다. 따라서 class-balanced sampling은 무조건 fail을 늘리는 방식이 아니라 effective-number 또는 capped sampling으로 적용한다. calibration은 deterministic protocol rule이 아니라 LLM pass/fail token logit의 temperature/threshold를 validation split에서 정하는 절차로 제한한다.

## 방법론 비교

| 방법 | 목표 직접성 | 적용 난이도 | 48GB GPU OOM risk | package < 12GB 가능성 | 재시작성 | 우선순위 | 판단 |
|---|---:|---:|---:|---:|---:|---:|---|
| Data selection/quality filtering + long trajectory manifest | 매우 높음 | 중간 | 낮음 | 매우 높음 | 높음 | P0 | Length Coverage, hidden-public gap, source 다양성 병목에 직접 대응한다. Step 5에서 가장 먼저 구현/재실행한다. |
| Calibration/thresholding on LLM logits | 매우 높음 | 낮음 | 없음 | 매우 높음 | 높음 | P0 | fail precision/recall, ECE 목표에 직접 대응한다. validation-only로 결정하고 test/public leakage를 금지한다. |
| Class-balanced sampling/loss | 높음 | 중간 | 낮음 | 매우 높음 | 높음 | P1 | fail prior 왜곡을 줄이되 과도한 fail oversampling은 금지한다. effective-number 또는 capped sampler로 구현한다. |
| High-rank LoRA r32/r64 | 높음 | 낮음-중간 | 낮음-중간 | 높음 | 높음 | P1 | 기존 LoRA infra를 가장 적게 바꾸면서 capacity를 늘린다. merged artifact로 12GB 제한을 활용한다. |
| AdaLoRA | 중간-높음 | 중간 | 낮음-중간 | 높음 | 중간 | P1.5 | layer별 rank budget이 유리할 수 있으나 구현 복잡도는 high-rank LoRA보다 높다. |
| DoRA | 높음 | 중간 | 중간 | 높음 | 중간 | P2 | LoRA보다 full FT에 가까운 capacity 후보다. PEFT/runtime/export 호환성 검증 후 실행한다. |
| NEFTune regularization | 중간 | 낮음 | 낮음 | 매우 높음 | 높음 | P2 | small data overfit 완화용 ablation으로 적합하다. 단독 주력 방법은 아니다. |
| Partial fine-tuning | 높음 | 높음 | 중간-높음 | 높음 | 중간 | P3 | top layers/layernorm/lm_head를 단계적으로 unfreeze한다. memory dry-run과 resume gate가 필수다. |
| QLoRA | 중간 | 중간 | 낮음 | 중간-높음 | 중간 | P3 | memory 절약 후보로 유지한다. 현재 4B/48GB 조건에서는 high-rank LoRA/DoRA 이후에 실행한다. |
| Full fine-tuning | 높음 | 매우 높음 | 높음 | 높음 | 낮음-중간 | P4 | 최종 package는 12GB 안에 가능하지만 학습 OOM과 checkpoint/restart risk가 크다. pilot gate 통과 시에만 확장한다. |
| Prefix/soft prompt tuning | 낮음-중간 | 중간 | 낮음 | 매우 높음 | 중간 | P5 | 현재 binary pass/fail hidden-like 목표에서는 LoRA/DoRA보다 우선순위가 낮다. 필요 시 baseline으로만 둔다. |

## 추천 실행 순서

### P0: 데이터와 calibration gate를 먼저 고정한다

- DCv2 manifest 계열만 사용한다.
- public/eval holdout, duplicate, rule-context, ambiguous label, unknown label gate를 유지한다.
- long trajectory bucket을 명시하고 Length Coverage를 산출한다.
- pass/fail prior를 train, validation, hidden-like eval에서 분리 기록한다.
- validation split에서 temperature, threshold, ECE, Brier score, fail precision/recall을 산출한다.
- 이 단계는 model architecture가 아니라 LLM 학습 데이터와 LLM logit decision calibration이다.

### P1: 충분 학습된 r16 baseline과 high-rank LoRA를 같은 조건으로 비교한다

- r16 baseline은 최소 5 epoch, 동일 split, 동일 eval cadence로 재확인한다.
- r32/r64 LoRA는 alpha=2r, dropout 0.05-0.10 범위에서 시작한다.
- 각 후보는 epoch별 checkpoint, resume test, hidden-like eval, 20-case eval, calibration report를 남긴다.
- "충분한 학습" 기준은 5 epoch 완료, loss NaN 없음, checkpoint resume PASS, validation metric plateau 또는 best checkpoint 확인이다.
- 선택 후보는 merged artifact로 export하고 package < 12GB, offline model-load, offline first-forward를 통과해야 한다.

### P2: DoRA와 class-balanced sampling을 결합 후보로 검증한다

- DoRA는 high-rank LoRA 대비 +1-3pp 이상의 internal gain이 있거나 fail precision/recall 균형이 좋아질 때만 유지한다.
- class-balanced sampling은 effective-number 또는 capped ratio로 적용하고, fail oversampling으로 ECE가 악화되면 폐기한다.
- data quality filtering과 class balancing을 동시에 바꾼 실험은 원인 분리가 어렵기 때문에 한 번에 하나씩 ablation한다.

### P3: partial fine-tuning을 memory dry-run 후 실행한다

- unfreeze 범위는 top 2 block -> top 4 block -> layernorm/lm_head 추가 순서로 확장한다.
- 첫 실행은 1-batch forward/backward memory dry-run, 그다음 200-500 step pilot, 그다음 3-5 epoch 본학습이다.
- optimizer state와 checkpoint 크기를 기록하고, 중단 후 재시작을 실제로 검증한다.
- package는 최종 merged model만 포함해 < 12GB를 맞춘다.

### P4: full fine-tuning은 마지막 capacity 확장 후보로 둔다

- naive Adam full FT는 48GB OOM risk가 높으므로 즉시 본학습하지 않는다.
- LOMO/MeZO 또는 다른 memory-efficient full update가 repo와 서버 환경에서 재시작 가능하게 구현될 때 pilot한다.
- pilot gate는 OOM 없음, 500 step 이상 안정 실행, checkpoint resume PASS, hidden-like baseline 비열화, package smoke PASS다.
- full FT가 r16/high-rank/DoRA 대비 +3pp 이상을 못 만들면 유지하지 않는다.

## 최종 우선순위 결정

1. P0: data selection/quality filtering + long trajectory coverage + calibration/thresholding.
2. P1: sufficient r16 LoRA baseline 재확인 후 r32/r64 high-rank LoRA 비교.
3. P2: DoRA와 class-balanced sampling/loss ablation.
4. P3: partial fine-tuning pilot.
5. P4: QLoRA는 OOM 대응 후보로 유지하고, full fine-tuning은 memory-efficient pilot gate 통과 후 확장.
6. P5: prefix/soft prompt tuning은 낮은 우선순위 baseline으로만 유지.

## Step 5 구현 조건

- 모든 구현은 LLM-only fine-tuning 또는 LLM logit calibration 범위에 있어야 한다.
- deterministic protocol rule fallback, rule-derived feature, public 20 template memorization 경로는 금지한다.
- 모든 학습 run은 KST 기준 run directory, config, seed, git commit, data manifest hash, checkpoint resume 여부를 기록한다.
- Cycle 6에서 epoch, lr, batch size, grad accumulation, peak VRAM, loss, grad norm, fail precision/recall, ECE를 모니터링한다.
- leaderboard 제출은 server availability reject가 해소되고, 이전 제출 대비 model/data/package/runtime 조건이 명확히 달라진 경우에만 수행한다.

## 민감 정보 처리

- 이 문서에는 민감 정보를 기록하지 않았다.
- 서버 인증 정보, 개인 비밀번호, 접속 자격 증명은 조회하거나 출력하지 않았다.
