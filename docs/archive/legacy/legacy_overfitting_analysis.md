# LoRA Overfitting Analysis & Improvement Plan

## Problem Statement

LoRA 4B v2 모델이 val set (spec-based 283건)에서 80%+ accuracy를 달성하지만,
public 20 cases에서 override한 10건이 **전부 오답** (0% accuracy).

**핵심 증상**: Distribution mismatch — synthetic training data ≠ real test data.

---

## 1. 논문 조사 (12편)

### A. LoRA Overfitting & Regularization

1. **LoRA Dropout as Sparsity Regularizer** (arXiv 2404.09610, 2024)
   - LoRA의 low-rank matrices에 refined dropout 적용
   - 이론: dropout이 sparse fine-tuning으로 작용, generalization error bound 축소
   - 핵심: 적절한 sparsity가 empirical risk와 generalization risk 간 gap을 줄임

2. **BiLoRA: Bi-level Optimization** (arXiv 2403.13037, 2024)
   - Bi-level optimization으로 overfitting-resilient adaptation
   - Inner loop: task loss 최소화, Outer loop: validation loss 최소화
   - 핵심: meta-learning 방식으로 generalization 직접 최적화

3. **ALLoRA: Adaptive Learning Rate** (arXiv 2410.09692, 2024)
   - LoRA의 A, B matrix에 서로 다른 learning rate 적용
   - 핵심: A matrix는 feature extractor, B matrix는 classifier 역할 → 다른 LR 필요

4. **NormAL LoRA** (EMNLP Findings 2025)
   - Rank-norm regularization으로 LoRA weight의 L2 norm 제어
   - 핵심: norm 크기가 generalization과 직결

### B. Distribution Shift & Generalization

5. **LoRA vs Full Fine-tuning: Illusion of Equivalence** (arXiv 2410.21228, ICML 2025)
   - LoRA가 "intruder dimensions" 생성 — pre-trained weights와 다른 고순위 singular vectors
   - Intruder dimensions이 적을수록 OOD generalization 향상
   - 핵심: LoRA의 spectral structure가 generalization 결정

6. **LoRA Learns Less and Forgets Less** (arXiv 2405.09673, ICML 2024)
   - LoRA는 full FT보다 target domain 성능이 낮지만, source domain 지식을 더 보존
   - Trade-off: 학습량 vs 일반화
   - 핵심: rank가 높을수록 더 많이 배우지만 더 많이 잊음 (더 overfitting)

7. **Slow Cascaded Learning** (arXiv 2407.01491, 2024)
   - LoRA의 expressiveness와 generalization을 동시에 향상
   - Cascaded low-rank adapters + slow learning
   - 핵심: 급격한 adaptation이 아니라 점진적 적응이 generalization에 유리

### C. Synthetic Data & Distribution Matching

8. **Synthetic Eggs in Many Baskets** (arXiv 2511.01490, 2024)
   - Synthetic data의 diversity가 fine-tuning 성능에 미치는 영향
   - 핵심: diversity가 높을수록 OOD generalization 향상. 동일 template 반복은 해로움

9. **Few-shot LLM Synthetic Data with Distribution Matching** (ACM WWW 2025)
   - LLM으로 생성한 synthetic data의 distribution을 real data에 매칭
   - 핵심: synthetic-to-real distribution gap을 줄이는 것이 핵심

10. **Improving OOD Performance through Strategic Data Selection** (arXiv 2505.20209, 2025)
    - Training data 선택 전략으로 OOD 성능 향상
    - 핵심: 대표적인 데이터 선별이 무작위 데이터보다 효과적

### D. Calibration & Uncertainty

11. **HypeLoRA: Calibrated Fine-Tuning** (arXiv 2603.19278, 2025)
    - Hyper-network으로 LoRA factors 생성 → structural coupling → calibration 향상
    - 핵심: 과신(overconfidence) 문제 해결

12. **Bayesian LoRA (Laplace-LoRA)** (arXiv 2308.13111, ICLR 2024)
    - LoRA parameters의 posterior distribution 추정 (Laplace approximation)
    - ECE (Expected Calibration Error) 개선
    - 핵심: 불확실성 정량화로 과신 방지

---

## 2. 진단 Metrics

| # | Metric | 측정 대상 | 구현 방법 |
|---|--------|----------|----------|
| M1 | **Val-Public Gap** | Distribution shift 크기 | val acc - public acc |
| M2 | **ECE (Expected Calibration Error)** | 확률 보정 | predicted prob vs actual accuracy |
| M3 | **Prediction Entropy** | 과신 정도 | -Σ p·log(p) for pass/fail logits |
| M4 | **Override Accuracy** | LoRA 실용성 | rule≠lora인 case 중 lora가 맞는 비율 |
| M5 | **Confidence Distribution** | 확신도 분포 | p_fail histogram on val vs public |
| M6 | **Intruder Dimension Count** | Spectral 건강도 | SVD of LoRA weight changes |
| M7 | **Per-rule Accuracy** | Rule별 취약점 | rule_id별 정확도 |

---

## 3. 개선 방법 (12가지)

### A. Regularization (모델 측)
1. **LoRA Dropout 증가** (0.05 → 0.1, 0.2, 0.3)
2. **Weight Decay 추가** (0.01 → 0.1)
3. **Rank 축소** (16 → 8, 4) — capacity 제한으로 overfitting 방지
4. **Early Stopping** — public 20 case 기준 조기 종료

### B. Data (데이터 측)
5. **Public cases upsampling** — public 20을 train에 10배 복제
6. **Data augmentation** — trajectory 순서 섞기, 일부 step 제거
7. **Hard negative mining** — rule engine이 틀리는 패턴 중심으로 데이터 구성
8. **Label smoothing** (0.1) — 과신 방지

### C. Inference (추론 측)
9. **Confidence threshold** — p_fail > 0.7/0.8일 때만 override
10. **Temperature scaling** — logit을 T로 나눠 calibration
11. **LoRA ensemble** — 여러 seed로 학습한 adapter 다수결

### D. Architecture (구조 측)
12. **Freeze A matrix** — B만 학습 (regularization 효과, HypeLoRA 참조)

---

## 4. 실행 계획 (10 Cycles)

### Cycle 0: Baseline 측정
- 현재 모델로 M1-M7 모든 metric 측정
- Public 20에서 logit 분포 분석

### Cycle 1-3: Post-hoc (GPU 불필요)
- C1: Temperature scaling (T=2, 3, 5)
- C2: Confidence threshold (0.6, 0.7, 0.8, 0.9)
- C3: Rule-engine-only fallback (LoRA 비활성) + public 진단

### Cycle 4-6: Regularization (재학습 필요)
- C4: LoRA Dropout 0.2
- C5: Weight Decay 0.1
- C6: Rank 축소 (r=8)

### Cycle 7-9: Data (재학습 필요)
- C7: Public 20 × 10배 upsampling
- C8: Label smoothing 0.1
- C9: Hard negative mining

### Cycle 10: Best combination
- 위 결과에서 효과 있는 방법들 조합

---

## Sources

- [LoRA Dropout](https://arxiv.org/pdf/2404.09610)
- [LoRA vs Full Fine-tuning](https://arxiv.org/html/2410.21228v2)
- [BiLoRA](https://arxiv.org/pdf/2403.13037)
- [Slow Cascaded Learning](https://arxiv.org/pdf/2407.01491)
- [Synthetic Eggs](https://arxiv.org/pdf/2511.01490)
- [Few-shot Distribution Matching](https://dl.acm.org/doi/10.1145/3701716.3715245)
- [HypeLoRA](https://arxiv.org/pdf/2603.19278)
- [Bayesian LoRA](https://arxiv.org/pdf/2308.13111)
- [Preserving Pre-trained Features](https://arxiv.org/pdf/2305.19249)
- [NormAL LoRA](https://aclanthology.org/2025.findings-emnlp.1074.pdf)
- [ALLoRA](https://arxiv.org/pdf/2410.09692)
- [LoRA Learns Less and Forgets Less](https://arxiv.org/pdf/2405.09673)
