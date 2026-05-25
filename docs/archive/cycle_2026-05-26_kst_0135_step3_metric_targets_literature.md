# Cycle 2 Step 3 - 논문 기반 Metric 목표 설정

- 기준 시각: 2026-05-26 01:35 KST
- 범위: LLM-only fine-tuning, 데이터 분포, calibration, OOD/generalization, PEFT/full FT 비교 metric
- 금지: 결정론적 검증 로직을 architecture에 포함하는 제안. 본 문서는 LLM 학습 및 평가 metric만 다룬다.

## 1. 참고 문헌

1. [EXTERNAL KNOWLEDGE] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). LoRA: Low-rank adaptation of large language models. International Conference on Learning Representations. https://openreview.net/forum?id=nZeVKeeFYf9
2. [EXTERNAL KNOWLEDGE] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). QLoRA: Efficient finetuning of quantized LLMs. Advances in Neural Information Processing Systems, 36. https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract-Conference.html
3. [EXTERNAL KNOWLEDGE] Liu, S.-Y., Wang, C.-Y., Yin, H., Molchanov, P., Wang, Y.-C. F., Cheng, K.-T., & Chen, M.-H. (2024). DoRA: Weight-decomposed low-rank adaptation. arXiv. https://arxiv.org/abs/2402.09353
4. [EXTERNAL KNOWLEDGE] Zhang, Q., Chen, M., Bukharin, A., He, P., Cheng, Y., Chen, W., & Zhao, T. (2023). AdaLoRA: Adaptive budget allocation for parameter-efficient fine-tuning. International Conference on Learning Representations. https://arxiv.org/abs/2303.10512
5. [EXTERNAL KNOWLEDGE] Ben Zaken, E., Ravfogel, S., & Goldberg, Y. (2022). BitFit: Simple parameter-efficient fine-tuning for transformer-based masked language-models. Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics. https://aclanthology.org/2022.acl-short.1/
6. [EXTERNAL KNOWLEDGE] Biderman, D., Portes, J., Gonzalez Ortiz, J. J., Paul, M., Greengard, P., Jennings, C., King, D., Havens, S., Chiley, V., Frankle, J., Blakeney, C., & Cunningham, J. P. (2024). LoRA learns less and forgets less. Transactions on Machine Learning Research. https://arxiv.org/abs/2405.09673
7. [EXTERNAL KNOWLEDGE] Lv, K., Yang, Y., Liu, T., Guo, Q., & Qiu, X. (2024). Full parameter fine-tuning for large language models with limited resources. Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics, 8187-8198. https://aclanthology.org/2024.acl-long.445/
8. [EXTERNAL KNOWLEDGE] Chung, H. W., Hou, L., Longpre, S., Zoph, B., Tay, Y., Fedus, W., Li, Y., Wang, X., Dehghani, M., Brahma, S., Webson, A., Gu, S. S., Dai, Z., Suzgun, M., Chen, X., Chowdhery, A., Narang, S., Mishra, G., Yu, A., ... Wei, J. (2022). Scaling instruction-finetuned language models. arXiv. https://arxiv.org/abs/2210.11416
9. [EXTERNAL KNOWLEDGE] Zhou, C., Liu, P., Xu, P., Iyer, S., Sun, J., Mao, Y., Ma, X., Efrat, A., Yu, P., Yu, L., Zhang, S., Ghosh, G., Lewis, M., Zettlemoyer, L., & Levy, O. (2023). LIMA: Less is more for alignment. Advances in Neural Information Processing Systems, 36. https://papers.neurips.cc/paper_files/paper/2023/hash/ac662d74829e4407ce1d126477f4a03a-Abstract-Conference.html
10. [EXTERNAL KNOWLEDGE] Chen, L., Li, S., Yan, J., Wang, H., Gunaratna, K., Yadav, V., Tang, Z., Srinivasan, V., Zhou, T., Huang, H., & Jin, H. (2024). AlpaGasus: Training a better Alpaca with fewer data. International Conference on Learning Representations. https://proceedings.iclr.cc/paper_files/paper/2024/hash/9543942c237ded1b39b1fd37259ff88e-Abstract-Conference.html
11. [EXTERNAL KNOWLEDGE] Xia, M., Malladi, S., Gururangan, S., Arora, S., & Chen, D. (2024). LESS: Selecting influential data for targeted instruction tuning. Proceedings of the 41st International Conference on Machine Learning, 54104-54132. https://proceedings.mlr.press/v235/xia24c.html
12. [EXTERNAL KNOWLEDGE] Ivison, H., Wang, Y., Pyatkin, V., Lambert, N., Peters, M., Dasigi, P., Jang, J., Wadden, D., Smith, N. A., Beltagy, I., & Hajishirzi, H. (2024). Long is more for alignment: A simple but tough-to-beat baseline for instruction fine-tuning. arXiv. https://arxiv.org/abs/2402.04833
13. [EXTERNAL KNOWLEDGE] Cui, Y., Jia, M., Lin, T.-Y., Song, Y., & Belongie, S. (2019). Class-balanced loss based on effective number of samples. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. https://arxiv.org/abs/1901.05555
14. [EXTERNAL KNOWLEDGE] Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. Proceedings of the 34th International Conference on Machine Learning, 1321-1330. https://proceedings.mlr.press/v70/guo17a.html
15. [EXTERNAL KNOWLEDGE] Kadavath, S., Conerly, T., Askell, A., Henighan, T., Drain, D., Perez, E., Schiefer, N., Hatfield-Dodds, Z., DasSarma, N., Tran-Johnson, E., ... Kaplan, J. (2022). Language models (mostly) know what they know. arXiv. https://arxiv.org/abs/2207.05221
16. [EXTERNAL KNOWLEDGE] Liu, W., Wang, X., Owens, J., & Li, Y. (2020). Energy-based out-of-distribution detection. Advances in Neural Information Processing Systems, 33. https://proceedings.neurips.cc/paper/2020/hash/f5496252609c43eb8a3d147ab9b9c006-Abstract.html

## 2. 문제별 metric 근거

1. [Original Text/Data] 최신 기록상 LLM-only 병목은 길이/trajectory 구조 분포 불일치, source/template 다양성 부족, label prior/calibration 불안정, 그리고 LoRA r16 중심 capacity 제한으로 정리되었다.  
   -> [Exact Interpretation] 단일 public 20-case 점수나 training loss만으로 목표를 잡으면 hidden gap을 설명하지 못한다.  
   -> [Detailed Explanation/Example] metric은 전체 accuracy와 함께 길이-bin별 accuracy, source group별 worst accuracy, pass/fail precision-recall, calibration, package/runtime gate를 동시에 봐야 한다.

2. [Original Text/Data] LIMA, AlpaGasus, LESS, Long Is More는 소량 fine-tuning에서 데이터 양보다 고품질, target relevance, 길이와 정보량이 중요하다는 근거를 제공한다.  
   -> [Exact Interpretation] 현재 데이터 문제는 "더 많은 샘플"보다 hidden trajectory를 대표하는 샘플을 얼마나 균형 있게 포함하는가로 평가해야 한다.  
   -> [Detailed Explanation/Example] selected train set이 늘어도 길이-bin long 영역과 source group이 비어 있으면 hidden-like accuracy 목표를 달성했다고 보지 않는다.

3. [Original Text/Data] Class-balanced loss와 calibration 논문은 class imbalance와 confidence miscalibration이 accuracy와 별개로 실패할 수 있음을 보인다.  
   -> [Exact Interpretation] fail recall만 높거나 precision만 높은 모델은 leaderboard에서 불안정하다.  
   -> [Detailed Explanation/Example] fail precision, fail recall, macro-F1, ECE, Brier score, threshold drift를 모두 gate로 둔다.

4. [Original Text/Data] LoRA, QLoRA, DoRA, AdaLoRA, BitFit, LoRA Learns Less and Forgets Less, LOMO 계열 논문은 PEFT와 full/partial FT가 capacity, forgetting, memory trade-off를 가진다는 근거를 제공한다.  
   -> [Exact Interpretation] 3MB급 adapter가 나쁘다는 결론은 아직 성립하지 않지만, 12GB 제출 한도를 고려하면 merged artifact, high-rank LoRA, DoRA, partial/full FT를 같은 metric으로 비교해야 한다.  
   -> [Detailed Explanation/Example] 충분 학습 기준을 통과한 뒤 adapter-only 대비 hidden-like metric이 유의하게 개선될 때만 더 큰 artifact나 full/partial FT를 채택한다.

5. [Original Text/Data] OOD/generalization 및 LLM confidence 논문은 public-like validation과 hidden distribution 사이의 불확실성을 별도 측정해야 함을 시사한다.  
   -> [Exact Interpretation] hidden-public gap을 줄이려면 OOD flag와 confidence bucket별 정확도를 기록해야 한다.  
   -> [Detailed Explanation/Example] logit margin, energy score, length/source shift bucket에서 low-confidence 오답이 집중되는지 확인하고, gap이 줄지 않으면 데이터 selection 또는 calibration을 우선 수정한다.

## 3. 1차 목표

- hidden-like accuracy: 72% 이상.
  - 이유: 현재 LLM-only 운영 기준 70점대 초반을 안정적으로 회복하는 최소 목표다. 제출 runtime 문제가 해결된 뒤 첫 비교선으로 사용한다.
- fail precision: 90% 이상, fail recall: 80% 이상, macro-F1: 0.72 이상.
  - 이유: 기존 기록에서 precision 100%/recall 83.33% 또는 recall 100%/precision 87.76%처럼 한쪽으로 치우친 결과가 있었다. 1차 목표는 이 불균형을 동시에 줄이는 것이다.
- long trajectory bucket accuracy: 60% 이상.
  - 이유: hidden median step이 train보다 길다는 기록이 있으므로, 전체 accuracy가 높아도 long bucket이 낮으면 문제 해결로 보지 않는다.
- worst source/template group accuracy: 55% 이상, train/eval group leakage: 0건.
  - 이유: source 다양성 부족이 병목 후보이므로 평균만 보지 않고 worst group을 gate로 둔다.
- length-bin JSD: 0.08 이하, max source share: 35% 이하, duplicate/group leakage: 0건.
  - 이유: 기존 Data Contract v2의 길이 분포 gate를 유지하고, 특정 source domination을 제한한다.
- ECE: 0.12 이하, Brier score는 직전 best LLM-only 대비 개선.
  - 이유: pass/fail threshold 이동이 있었으므로 1차에서는 calibration이 악화되지 않는 것을 최소 조건으로 둔다.
- OOD/logit-margin AUROC: 0.70 이상 또는 confidence 하위 30% bucket의 error concentration이 명확히 관측될 것.
  - 이유: hidden-public gap을 설명할 수 있는 confidence/OOD 신호가 있어야 다음 데이터 selection이 가능하다.
- FT 방법 비교 gate: r16 LoRA baseline, high-rank LoRA/DoRA/partial FT 후보는 각각 최소 5 epoch 또는 동일 token budget 학습 후 비교.
  - 이유: 충분히 학습하지 않은 제출 반복을 막는다.
- package/runtime gate: offline model-load 및 first-forward PASS, package size 12GB 미만.
  - 이유: 현재 제출 문제는 점수보다 package availability/runtime 검증이 먼저다.

## 4. 2차 목표

- hidden-like accuracy: 75% 이상.
  - 이유: adapter-only 70점대 baseline을 실질적으로 넘는 LLM-only 개선 목표다.
- fail precision: 92% 이상, fail recall: 85% 이상, macro-F1: 0.75 이상.
  - 이유: class imbalance와 threshold 흔들림을 줄이고, hidden fail case를 놓치지 않으면서 false positive를 제한한다.
- public-private 또는 public-hidden-like gap: 8pp 이하.
  - 이유: public 20 case에만 맞는 개선을 배제한다.
- long trajectory bucket accuracy: 65% 이상, worst length bucket accuracy: 60% 이상.
  - 이유: trajectory 구조 분포 불일치를 실제로 줄였는지 확인한다.
- worst source/template group accuracy: 60% 이상, source effective group count: 8 이상.
  - 이유: source 다양성이 낮은 corpus는 hidden template 일반화가 약하다.
- ECE: 0.08 이하, Brier score: 1차 채택 모델 대비 개선, threshold drift: validation split 간 +/-0.10 이하.
  - 이유: calibration 논문 근거상 confidence 품질을 별도 목표로 둬야 한다.
- OOD/logit-margin AUROC: 0.75 이상, high-risk bucket에서 fail recall 90% 이상.
  - 이유: OOD 또는 low-confidence 구간을 찾은 뒤 해당 구간의 fail 놓침을 줄인다.
- FT 방법 비교 gate: high-rank LoRA/DoRA/partial FT 중 하나가 r16 LoRA 대비 hidden-like accuracy +3pp 이상 또는 macro-F1 +0.03 이상.
  - 이유: 더 큰 artifact 또는 더 비싼 학습을 채택하려면 capacity 증가의 실익이 있어야 한다.
- package/runtime gate: merged artifact 또는 full/partial FT artifact가 12GB 미만, offline first-forward PASS, 중단 후 resume 가능.
  - 이유: 제출 가능한 학습 산출물만 후보로 유지한다.

## 5. 궁극 목표

- LLM-only leaderboard: 75점 이상.
  - 이유: rule-free LLM-only 경로에서 기존 70점대 초반을 명확히 넘어서는 최종 운영 목표다.
- hidden-like accuracy: 78% 이상, macro-F1: 0.78 이상.
  - 이유: public/hidden gap을 고려해 leaderboard 75점 이상을 기대하려면 local hidden-like metric에서 더 높은 여유가 필요하다.
- fail precision: 93% 이상, fail recall: 90% 이상.
  - 이유: pass/fail 결정 문제에서 한쪽 오류를 희생하는 모델은 안정적인 최종 후보가 아니다.
- long trajectory bucket accuracy: 70% 이상, worst source/template group accuracy: 70% 이상.
  - 이유: 핵심 병목으로 판정한 trajectory gap과 source 다양성 부족을 실제로 해소한 기준이다.
- public-hidden-like gap: 5pp 이하.
  - 이유: public overfit 가능성을 낮추기 위한 최종 일반화 목표다.
- ECE: 0.05 이하, threshold drift: split 간 +/-0.05 이하.
  - 이유: calibration이 안정되어야 leaderboard 1일 기회를 논리적으로 사용할 수 있다.
- OOD/logit-margin AUROC: 0.80 이상 또는 OOD bucket별 remediation 후 worst bucket accuracy 65% 이상.
  - 이유: hidden 분포 차이를 감지하고 보정할 수 있어야 한다.
- FT 방법 채택 기준: 충분 학습된 r16 LoRA 대비 hidden-like accuracy +5pp 이상, 또는 leaderboard +3점 이상, package/runtime gate 전부 PASS.
  - 이유: full/partial/high-rank/DoRA는 비용과 실패 위험이 있으므로 명확한 metric 이득이 있을 때만 최종 채택한다.

## 6. 결정

Cycle 2의 metric 목표는 다음 순서로 사용한다.

1. 제출 가능성 gate: offline first-forward, package size < 12GB, resume 가능성.
2. 점수 gate: hidden-like accuracy, macro-F1, fail precision/recall.
3. 병목 gate: long trajectory bucket, worst source group, source effective group count.
4. 안정성 gate: ECE, Brier score, threshold drift, OOD/logit-margin AUROC.
5. 방법론 gate: adapter-only 대비 high-rank LoRA/DoRA/partial/full FT의 충분 학습 후 개선폭.

현재 결론은 leaderboard 즉시 제출이 아니라, 위 1차 목표를 통과하는 merged/expanded capacity LLM-only 후보를 만든 뒤 제출 여부를 판단하는 것이다.
