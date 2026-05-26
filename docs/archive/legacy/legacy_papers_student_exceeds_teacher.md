# Student가 Teacher를 초월하는 방법론 Survey

> 작성일: 2026-05-22
> 목적: Rule engine (73%) teacher의 한계를 LLM student가 넘어서기 위한 논문 조사
> 핵심 문제: Rule engine이 ~54건 (27%)에서 기본값(UNEXPECTED_ERROR_STATUS→fail, DEFAULT_PASS→pass)을 사용하며, 이 영역에서 LLM이 더 나은 판단을 해야 함

---

## 1. Weak-to-Strong Generalization (OpenAI)

**논문**: Burns, C., Izmailov, P., Kirchner, J.H., Baker, B., Gao, L., Aschenbrenner, L., Chen, Y., Ecoffet, A., Joglekar, M., Leike, J., Sutskever, I., & Wu, J. (2023). *Weak-to-Strong Generalization: Eliciting Strong Capabilities With Weak Supervision.* ICML 2024. arXiv:2312.09390.

**핵심 기법**: Weak model (GPT-2급)의 label로 strong model (GPT-4급)을 finetuning하면, strong model이 weak supervisor보다 **일관되게 더 높은 성능**을 달성. Strong model의 pretrained representation이 weak label의 noise를 자동으로 필터링.

**우리 문제에 적용**:
- Rule engine = weak supervisor (73%), 4B LLM = strong model
- Rule engine label로 finetuning하되, LLM의 pretrained 지식이 rule engine의 기본값(DEFAULT_PASS/UNEXPECTED_ERROR_STATUS) 오류를 자연스럽게 보정
- **핵심**: 단순 finetuning만으로도 teacher 초월 가능. 추가 기법 불필요할 수 있음

**기대 개선**: +3~8% (weak-to-strong gap recovery 20~60%, 논문 기준)

---

## 2. Born-Again Neural Networks (BANs)

**논문**: Furlanello, T., Lipton, Z.C., Tsworth, M., Itti, L., & Anandkumar, A. (2018). *Born Again Neural Networks.* ICML 2018. arXiv:1805.04770.

**핵심 기법**: Teacher와 **동일 아키텍처**의 student를 teacher의 soft label로 학습시키면, student가 teacher를 초월. 이를 반복하면 세대마다 성능 향상. Ensemble of born-again networks (EBAR)로 추가 개선.

**우리 문제에 적용**:
- 1세대: Rule engine label → LLM 학습
- 2세대: 1세대 LLM의 soft label → 새 LLM 학습 (반복)
- 매 세대 dark knowledge (soft label의 클래스 간 유사도 정보)가 regularization 역할

**기대 개선**: +1~3% per generation, 2~3세대로 +2~5% 가능

---

## 3. Can Students Beyond The Teacher? (Teacher Bias Rectification)

**논문**: Zhang, J., Gao, Y., Liu, R., Cheng, X., Zhang, H., & Chen, S. (2025). *Can Students Beyond The Teacher? Distilling Knowledge from Teacher's Bias.* AAAI 2025. arXiv:2412.09874.

**핵심 기법**: Teacher의 bias (잘못된 예측)를 명시적으로 분리하여 **right knowledge만 학습 + biased knowledge를 보정**하는 3단계 프레임워크. Dynamic loss weighting으로 easy task → hard task 순서 학습.

**우리 문제에 적용**:
- Rule engine의 bias가 명확히 식별 가능: UNEXPECTED_ERROR_STATUS (항상 fail), DEFAULT_PASS (항상 pass)
- 이 두 패턴에 해당하는 ~54건을 "biased knowledge"로 분류
- 나머지 ~146건을 "right knowledge"로 학습 → bias 부분은 별도 보정

**기대 개선**: +1.75% (ResNet 실험 기준), 우리 케이스에서는 bias가 명확하므로 +3~7% 가능

---

## 4. Noisy Student Self-Training

**논문**: Xie, Q., Luong, M.T., Hovy, E., & Le, Q.V. (2020). *Self-Training With Noisy Student Improves ImageNet Classification.* CVPR 2020. arXiv:1911.04252.

**핵심 기법**: Teacher가 unlabeled data에 pseudo-label 부여 → **student에 noise 주입** (dropout, stochastic depth, data augmentation) → student가 teacher 초월. Student가 teacher보다 크거나 같아야 함.

**우리 문제에 적용**:
- Rule engine으로 대량 trajectory에 label 부여
- LLM student 학습 시 dropout 강화, data augmentation (trajectory 변형)
- Noise가 regularization 역할 → teacher의 overfit (기본값 rule)을 피함
- 4B model이 rule engine보다 "큰" 모델이므로 조건 충족

**기대 개선**: +2~4% (ImageNet에서 +2.0% SOTA 개선, 88.4% 달성)

---

## 5. STaR: Self-Taught Reasoner

**논문**: Zelikman, E., Wu, Y., Mu, J., & Goodman, N.D. (2022). *STaR: Bootstrapping Reasoning With Reasoning.* NeurIPS 2022. arXiv:2203.14465.

**핵심 기법**: 모델이 스스로 rationale 생성 → 정답 맞추면 keep → 틀리면 정답 힌트 주고 재시도 → 성공한 rationale로 finetuning → 반복. 30배 큰 모델과 비슷한 성능.

**우리 문제에 적용**:
- LLM이 trajectory 분석 시 reasoning을 생성하게 함
- Rule engine이 확실히 맞는 case에서 rationale 수집
- 불확실한 54건에서 LLM이 자체 reasoning으로 판단 후, 정답 확인 가능한 20건(public)에서 검증
- Iterative bootstrapping으로 reasoning 능력 점진 향상

**기대 개선**: +5~10% on uncertain cases (전체 +1.5~3%)

---

## 6. Student as an Inherent Denoiser of Noisy Teacher (Peer-Advised KD)

**논문**: Zhao, J. (2023). *Student as an Inherent Denoiser of Noisy Teacher.* NeurIPS 2023 Workshop (ENLSP). arXiv:2312.10185.

**핵심 기법**: Student 모델이 학습 중 teacher의 noisy label을 **자연스럽게 denoise**하는 능력이 있음을 발견. Peer-Advised KD: 여러 student의 예측을 peer review처럼 활용하여 noisy label 보정. LLM teacher보다 ~5% 높은 성능.

**우리 문제에 적용**:
- Rule engine의 label 중 ~27%가 기본값 (noisy label에 해당)
- LLM student의 inherent denoising capacity가 이 noise를 자동 필터링
- 여러 checkpoint 또는 다른 seed의 student를 peer로 활용하면 추가 보정

**기대 개선**: +3~5% (논문에서 LLM 대비 ~5% 개선)

---

## 7. Quiet-STaR: Language Models Can Teach Themselves to Think

**논문**: Zelikman, E., Harik, G., Shao, Y., Jayasiri, V., Haber, N., & Goodman, N.D. (2024). *Quiet-STaR: Language Models Can Teach Themselves to Think Before Speaking.* arXiv:2403.09629.

**핵심 기법**: 모든 token 위치에서 내부 "thinking" rationale 생성 → future token prediction 향상. REINFORCE로 유용한 rationale 학습. STaR의 일반화 버전.

**우리 문제에 적용**:
- Trajectory 분석 시 각 APDU 명령어마다 implicit reasoning
- "이 명령이 왜 실패했는가" / "이 응답이 spec에 맞는가" 내부 추론
- Zero-shot reasoning 능력 향상: CommonsenseQA +10.9%, GSM8K +5.0%

**기대 개선**: Reasoning 기반 task에서 +5~10% (불확실한 케이스 한정)

---

## 8. SLaM: Student-Label Mixing for Distillation

**논문**: Kontonis, V., Iliopoulos, F., Trinh, K.B., Vempala, S., & Xu, C. (2023). *SLaM: Student-Label Mixing for Distillation with Unlabeled Examples.* NeurIPS 2023. arXiv:2302.03806.

**핵심 기법**: Teacher의 noisy pseudo-label과 student 자신의 prediction을 **혼합** (mixing ratio는 이론적으로 도출). Noisy teacher label의 부정적 영향을 수학적으로 최소화. "Forward loss-adjustment" 이론적 보장.

**우리 문제에 적용**:
- Rule engine label (특히 기본값 54건)과 LLM 자체 prediction을 가중 평균
- Rule engine이 확신 높은 ~146건: rule label 비중 높게
- Rule engine이 기본값 사용한 ~54건: LLM 자체 prediction 비중 높게
- **Confidence-gated mixing** 전략과 자연스럽게 결합

**기대 개선**: +2~4% (noisy label 환경에서 일관된 개선)

---

## 9. LLKD: Learning with Less

**논문**: Dai, H., Li, S., Pan, L., Lyu, L., & Li, B. (2024). *Learning with Less: Knowledge Distillation from Large Language Models via Unlabeled Data.* NAACL 2025 Findings. arXiv:2411.08028.

**핵심 기법**: Teacher 신뢰도 높고 + Student 정보 필요도 높은 sample 우선 선택 (adaptive sample selection). Teacher/student 양쪽 signal 결합.

**우리 문제에 적용**:
- Rule engine 확신 높은 sample (명확한 rule 매칭) = high teacher confidence → 우선 학습
- Rule engine 기본값 sample (UNEXPECTED_ERROR_STATUS) = low teacher confidence → student 자체 학습에 맡김
- 데이터 효율 극대화: 200건 중 ~146건만 teacher label 사용, 나머지는 student 판단

**기대 개선**: +2~3% with better data efficiency

---

## 10. Confident Learning (Cleanlab)

**논문**: Northcutt, C.G., Jiang, L., & Chuang, I.L. (2021). *Confident Learning: Estimating Uncertainty in Dataset Labels.* JAIR, Vol. 70, pp. 1373-1411. arXiv:1911.00068.

**핵심 기법**: Label noise를 체계적으로 식별하고 수정하는 프레임워크. Model의 per-class confidence threshold를 이용하여 noisy label 탐지 → 제거 또는 교정 후 재학습하면 성능 향상.

**우리 문제에 적용**:
- 1차: Rule engine label로 LLM 학습
- 2차: 학습된 LLM의 prediction과 rule engine label 비교
- 불일치 sample (특히 rule engine 기본값 54건) 식별
- 3차: 식별된 noisy label을 LLM prediction으로 교체 → 재학습
- **우리 문제는 noisy label의 패턴이 알려져 있어 매우 효과적**

**기대 개선**: +2~5% (label 교정 후 재학습)

---

## 11. SELC: Self-Ensemble Label Correction

**논문**: Lu, Y., & He, W. (2022). *SELC: Self-Ensemble Label Correction Improves Learning with Noisy Labels.* IJCAI 2022. arXiv:2205.01156.

**핵심 기법**: Exponential moving average (EMA) of network outputs로 ensemble prediction 생성 → noisy label을 점진적으로 교정. 학습 초기에는 noisy label 사용, 후기에는 ensemble prediction으로 전환.

**우리 문제에 적용**:
- 학습 초기: Rule engine label 그대로 사용 (대부분 정확)
- 학습 후기: LLM의 EMA prediction이 rule engine 기본값을 덮어씀
- Rule engine 확신 높은 case는 label 유지, 기본값 case는 자동 교정
- 추가 hyper-parameter나 clean validation set 불필요

**기대 개선**: +2~4% (noisy label 환경에서 안정적 개선)

---

## 12. Revisiting KD via Label Smoothing (Teacher-Free KD)

**논문**: Yuan, L., Tay, F.E., Li, G., Wang, T., & Feng, J. (2020). *Revisiting Knowledge Distillation via Label Smoothing Regularization.* CVPR 2020 (Oral). arXiv:1909.11723.

**핵심 기법**: KD의 성능 향상이 teacher의 지식 전달보다 **soft label의 regularization 효과**에 더 기인한다는 발견. Teacher 없이도 self-training + label smoothing으로 비슷한 효과 달성 (Teacher-free KD). 심지어 **약한 student가 강한 teacher를 역으로 가르칠 수 있음** (reversed KD).

**우리 문제에 적용**:
- Rule engine의 hard label (pass/fail)을 soft label로 변환 (확신도 기반)
- Rule engine 확실한 case: [0.05, 0.95] 또는 [0.95, 0.05]
- Rule engine 기본값 case: [0.4, 0.6] 또는 [0.6, 0.4] (불확실성 반영)
- Label smoothing이 LLM의 overconfidence 방지 + teacher bias 완화

**기대 개선**: +1~3% (regularization 효과)

---

## 13. RLAIF: Reinforcement Learning from AI Feedback

**논문**: Lee, H., Phatale, S., Mansoor, H., Mesnard, T., Ferret, J., Lu, K., Bishop, C., Hall, E., Carbune, V., Rastogi, A., & Prakash, S. (2023). *RLAIF: Scaling Reinforcement Learning from Human Feedback with AI Feedback.* ICML 2024. arXiv:2309.00267.

**핵심 기법**: Human label 대신 LLM이 생성한 AI feedback으로 reward model 학습 → RLHF와 동등한 성능. Weak supervisor (AI)의 label이 strong model의 alignment에 충분.

**우리 문제에 적용**:
- Rule engine = weak verifier (73% 정확), LLM의 reasoning을 rule engine이 judge
- 하지만 LLM 자체도 27% 영역에서는 rule engine보다 나은 판단 가능
- **Hybrid reward**: rule engine 확신 높은 영역은 rule reward, 낮은 영역은 LLM self-evaluation reward
- RL로 policy 개선 (PPO 또는 DPO 활용)

**기대 개선**: +3~6% (RLHF 수준 alignment을 AI feedback으로 달성)

---

## 14. On-Policy Self-Distillation for LLM Reasoning

**논문**: Huang, H., Lin, H., Ye, J., & Zheng, Z. (2025). *Self-Distilled Reasoner: On-Policy Self-Distillation for Large Language Models.* arXiv:2601.18734.

**핵심 기법**: 같은 모델이 teacher/student 역할 동시 수행. Teacher는 정답(privileged information)을 참조하여 dense token-level supervision 제공. Student는 on-policy rollout으로 자기 distribution에서 학습. External reward model 불필요.

**우리 문제에 적용**:
- Public 20건의 정답을 privileged information으로 활용
- LLM이 정답을 보고 "왜 이 결과가 나왔는지" reasoning 생성 (teacher 역할)
- 동일 LLM이 정답 없이 trajectory만 보고 판단 (student 역할)
- Teacher의 reasoning이 student에게 dense supervision 제공

**기대 개선**: +3~5% (Qwen3 모델에서 일관된 개선 보고)

---

## 15. Can Large Reasoning Models Self-Train?

**논문**: Shafayat, S., et al. (2025). *Can Large Reasoning Models Self-Train?* arXiv:2505.21444.

**핵심 기법**: Majority voting을 self-feedback으로 사용하여 RL 반복 학습. 모델의 reasoning 성능과 feedback 품질이 동시에 향상. 단, 장기간 학습 시 reward hacking 위험 → regularization 필요.

**우리 문제에 적용**:
- LLM이 여러 번 inference → majority voting으로 pass/fail 결정
- Majority voting confidence가 높은 예측을 pseudo-label로 사용
- 다음 iteration에서 이 label로 재학습 → 점진적 개선
- **주의**: 3~4 iteration 이상에서 reward hacking 발생 가능 → early stopping 필요

**기대 개선**: +2~4% (초기 2~3 iteration, 이후 수확체감)

---

## 16. Curriculum Temperature for Knowledge Distillation

**논문**: Li, Z., Li, Z., Xu, C., Leng, Y., Wu, R., Yuan, M., & Xiang, J. (2023). *Curriculum Temperature for Knowledge Distillation.* AAAI 2023. arXiv:2211.16231.

**핵심 기법**: Distillation temperature를 고정하지 않고, easy sample → low temperature, hard sample → high temperature로 **점진적 증가**. Curriculum learning + temperature scheduling 결합.

**우리 문제에 적용**:
- Rule engine 확신 높은 146건: 낮은 temperature (sharp label, teacher 따르기)
- Rule engine 기본값 54건: 높은 temperature (soft label, student 자유도 높이기)
- 학습 초기에 easy case 먼저, 후기에 hard case (기본값 영역) 도입
- Student가 hard case에서 teacher를 넘어설 수 있는 공간 확보

**기대 개선**: +1~3% (curriculum + temperature 결합 효과)

---

## 종합 전략 제안

### 우리 상황 분석
| 영역 | 건수 | Rule Engine | LLM 목표 |
|------|------|-------------|-----------|
| 확실한 rule 매칭 | ~146건 | 정확 (100%) | 동일하게 따름 |
| UNEXPECTED_ERROR_STATUS (기본 fail) | ~27건 | 기본값 | 더 나은 판단 |
| DEFAULT_PASS (기본 pass) | ~27건 | 기본값 | 더 나은 판단 |

### 추천 조합 (실현 가능한 순서)

**Phase 1: Confidence-Gated Distillation** (논문 3, 8, 9, 12)
1. Rule engine label을 confidence로 분류:
   - High confidence (명확한 rule 매칭): hard label [0, 1] or [1, 0]
   - Low confidence (기본값): soft label [0.45, 0.55] or [0.55, 0.45]
2. SLaM-style mixing: high confidence → teacher label 위주, low confidence → student prediction 위주

**Phase 2: Iterative Self-Training** (논문 2, 4, 5, 15)
1. Phase 1 모델을 teacher로 사용
2. Noisy Student: dropout + data augmentation 추가
3. Born-Again: 2~3 세대 반복
4. 매 세대 public 20건으로 성능 체크

**Phase 3: Self-Correction** (논문 6, 10, 11)
1. 학습된 모델과 rule engine label 비교
2. Confident Learning으로 의심 label 식별
3. SELC-style EMA correction 적용
4. 재학습

### 기대 최종 성능
- 현재: 73% (rule engine) / 70% (LLM)
- Phase 1 후: 76~80% (confidence-gated distillation)
- Phase 2 후: 78~83% (iterative self-training)
- Phase 3 후: 80~85% (self-correction + label cleaning)

---

## 참고 문헌 요약

| # | 논문 | 학회/년도 | 핵심 아이디어 |
|---|------|-----------|---------------|
| 1 | Weak-to-Strong Generalization | ICML 2024 | Strong model이 weak label 넘어섬 |
| 2 | Born-Again Neural Networks | ICML 2018 | 동일 아키텍처 반복 distillation |
| 3 | Can Students Beyond Teacher | AAAI 2025 | Teacher bias 분리 및 보정 |
| 4 | Noisy Student | CVPR 2020 | Noise 주입 self-training |
| 5 | STaR | NeurIPS 2022 | Reasoning bootstrapping |
| 6 | Student as Denoiser | NeurIPS WS 2023 | Student의 내재적 denoising |
| 7 | Quiet-STaR | arXiv 2024 | 매 token 내부 reasoning |
| 8 | SLaM | NeurIPS 2023 | Student-label mixing |
| 9 | LLKD | NAACL 2025 | Adaptive sample selection |
| 10 | Confident Learning | JAIR 2021 | Label noise 탐지/교정 |
| 11 | SELC | IJCAI 2022 | EMA ensemble label correction |
| 12 | Teacher-Free KD | CVPR 2020 | Label smoothing ≈ KD |
| 13 | RLAIF | ICML 2024 | AI feedback으로 RL |
| 14 | Self-Distilled Reasoner | arXiv 2025 | On-policy self-distillation |
| 15 | Self-Train Reasoning | arXiv 2025 | Majority voting self-feedback |
| 16 | Curriculum Temperature KD | AAAI 2023 | Temperature scheduling |
