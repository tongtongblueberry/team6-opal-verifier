# Paper Archive

All papers surveyed across research cycles (1-21). Organized by topic.

---

## A. Core Architecture: LoRA Fine-tuning

### 1. LoRA: Low-Rank Adaptation of Large Language Models
- **Authors**: Hu, E. J. et al.
- **Venue**: ICLR 2022
- **arXiv**: 2106.09685
- **Problem solved**: Fine-tune large LMs with minimal trainable parameters
- **Applied in**: `tools/training/finetune_lora_v2.py`, `src/lora_solver.py` -- LoRA adapter on Qwen3.5-4B attention layers (q/k/v/o_proj, 144 modules, ~3.1M params at r=16)
- **Status**: IMPLEMENTED (core method)

### 2. QLoRA: Efficient Finetuning of Quantized LLMs
- **Authors**: Dettmers, T. et al.
- **Venue**: NeurIPS 2023
- **arXiv**: 2305.14314
- **Problem solved**: LoRA training with 4-bit quantized base model
- **Applied in**: Evaluated during Cycle 11; not adopted because 4B model fits in FP16 on L40S
- **Status**: REJECTED (unnecessary given hardware)

### 3. TOGLL: Fine-tuned Small Models Beat Large Zero-shot 3.8x
- **Venue**: ASE 2024
- **Problem solved**: Validates that fine-tuned small models outperform large zero-shot models for domain tasks
- **Applied in**: Motivated the shift from 27B zero-shot to 4B fine-tuned LoRA
- **Status**: IMPLEMENTED (validated by our results: 4B LoRA > 27B zero-shot)

### 4. Zhang et al.: Model Scaling > Data Scaling for Fine-tuning
- **Venue**: ICLR 2024
- **Problem solved**: For fine-tuning, larger models improve more than more data
- **Applied in**: Decision to use 4B (and potentially 9B) instead of 0.8B
- **Status**: IMPLEMENTED (0.8B v1 failed, 4B v2 succeeded)

---

## B. LoRA Regularization & Overfitting

### 5. LoRA Dropout as Sparsity Regularizer
- **arXiv**: 2404.09610 (2024)
- **Problem solved**: Refined dropout on LoRA low-rank matrices reduces generalization gap
- **Applied in**: `tools/training/finetune_lora_v2.py` -- dropout parameter in sweep
- **Status**: IMPLEMENTED (swept 0.0, 0.05, 0.1, 0.2)

### 6. BiLoRA: Bi-level Optimization
- **arXiv**: 2403.13037 (2024)
- **Problem solved**: Overfitting-resilient LoRA via meta-learning (inner: task loss, outer: val loss)
- **Applied in**: Not adopted; training pipeline already uses val-based checkpoint selection
- **Status**: REJECTED (too complex for marginal gain)

### 7. ALLoRA: Adaptive Learning Rate for LoRA
- **arXiv**: 2410.09692 (2024)
- **Problem solved**: Different LRs for A and B matrices (feature extractor vs classifier roles)
- **Applied in**: Not adopted; single LR with sweep was sufficient
- **Status**: PLANNED (if further regularization needed)

### 8. NormAL LoRA: Rank-norm Regularization
- **Venue**: EMNLP Findings 2025
- **Problem solved**: L2 norm control of LoRA weights for generalization
- **Applied in**: Not adopted; weight decay serves similar purpose
- **Status**: REJECTED

### 9. LoRA vs Full Fine-tuning: Illusion of Equivalence
- **arXiv**: 2410.21228
- **Venue**: ICML 2025
- **Problem solved**: "Intruder dimensions" in LoRA hurt OOD generalization
- **Applied in**: Guided rank selection -- lower rank = fewer intruder dimensions
- **Status**: IMPLEMENTED (informed rank sweep: 4, 8, 16, 32, 64)

### 10. LoRA Learns Less and Forgets Less
- **arXiv**: 2405.09673
- **Venue**: ICML 2024
- **Problem solved**: LoRA preserves source domain knowledge better than full FT, but learns less
- **Applied in**: Justified LoRA over full fine-tuning for our small data regime
- **Status**: IMPLEMENTED (design decision)

### 11. Slow Cascaded Learning
- **arXiv**: 2407.01491 (2024)
- **Problem solved**: Gradual adaptation improves generalization over aggressive training
- **Applied in**: Informed use of cosine scheduler with warmup
- **Status**: IMPLEMENTED (cosine scheduler is standard)

---

## C. LoRA Variants (Advanced)

### 12. TLoRA: Adaptive Rank Allocation
- **arXiv**: 2604.18124
- **Problem solved**: Different ranks per layer based on importance
- **Applied in**: Not adopted; uniform rank was sufficient
- **Status**: PLANNED

### 13. LoRA-DA: Fisher-gradient Optimal Initialization
- **arXiv**: 2510.24561
- **Problem solved**: Better initialization of LoRA matrices using Fisher information
- **Applied in**: Not adopted
- **Status**: PLANNED

### 14. alpha-LoRA: RMT-derived Optimal Scaling
- **arXiv**: 2510.21345
- **Problem solved**: Optimal alpha/rank ratio derived from random matrix theory
- **Applied in**: Informed alpha sweep (ratios 1.0, 2.0, 4.0, 8.0)
- **Status**: PLANNED

### 15. D2LoRA: Warm-up on General Data
- **arXiv**: 2503.18089
- **Problem solved**: Warm-up phase on general data before task-specific fine-tuning
- **Applied in**: Not adopted; no general SSD/Opal pretraining corpus available
- **Status**: REJECTED

---

## D. Calibration & Uncertainty

### 16. Conformal Prediction Deferral
- **arXiv**: 2509.12573
- **Problem solved**: Training-free routing between rule engine and LoRA
- **Applied in**: `tools/eval/conformal_calibration.py` -- calibrate confidence threshold for override decisions
- **Status**: IMPLEMENTED (Cycle 4)

### 17. Know When You're Wrong (Self-distillation)
- **arXiv**: 2603.06604
- **Problem solved**: Anchor token calibration, ECE 0.163 -> 0.034
- **Applied in**: `tools/training/self_distill.py` -- self-distillation for LoRA calibration
- **Status**: IMPLEMENTED (Cycle 5)

### 18. ConfTuner: Tokenized Brier Score Loss
- **arXiv**: 2508.18847
- **Venue**: NeurIPS 2025
- **Problem solved**: Brier score loss for LLM confidence calibration, 2000-sample convergence
- **Applied in**: `tools/training/brier_trainer.py` -- Brier loss training
- **Status**: IMPLEMENTED (Cycle 10)

### 19. HypeLoRA: Calibrated Fine-Tuning
- **arXiv**: 2603.19278 (2025)
- **Problem solved**: Hyper-network generates LoRA factors for structural coupling -> calibration
- **Applied in**: Not adopted; simpler calibration methods tried first
- **Status**: REJECTED

### 20. Bayesian LoRA (Laplace-LoRA)
- **arXiv**: 2308.13111
- **Venue**: ICLR 2024
- **Problem solved**: Posterior distribution estimation of LoRA parameters via Laplace approximation
- **Applied in**: Not adopted; too complex for production pipeline
- **Status**: REJECTED

### 21. CogCalib: Cognition-aware Calibration
- **arXiv**: 2505.20903
- **Venue**: ACL 2025
- **Problem solved**: 57% ECE reduction via cognition-aware calibration
- **Applied in**: Not adopted
- **Status**: PLANNED

### 22. ALiS: Adaptive Label Smoothing
- **Problem solved**: Per-confidence-bin label smoothing
- **Applied in**: Label smoothing 0.1 used in Cycle 3 training (commit `ff8a64e`)
- **Status**: IMPLEMENTED (simplified version: fixed 0.1 smoothing)

---

## E. Data & Distribution

### 23. Synthetic Eggs in Many Baskets
- **arXiv**: 2511.01490 (2024)
- **Problem solved**: Synthetic data diversity critical for OOD generalization
- **Applied in**: Motivated diverse data generation (9 gap categories, 209 Column ACL cases)
- **Status**: IMPLEMENTED (diverse gap data generation)

### 24. Few-shot LLM Synthetic Data with Distribution Matching
- **Venue**: ACM WWW 2025
- **Problem solved**: Synthetic-to-real distribution gap reduction
- **Applied in**: Informed public 20 upsampling and hard negative mining strategies
- **Status**: IMPLEMENTED (public case upsampling in training)

### 25. Improving OOD Performance through Strategic Data Selection
- **arXiv**: 2505.20209 (2025)
- **Problem solved**: Representative data selection beats random sampling for OOD
- **Applied in**: Prioritized Column ACL cases in gap data (73% of gap data)
- **Status**: IMPLEMENTED

---

## F. Contrastive & Classification Losses

### 26. SCL: Supervised Contrastive Learning
- **arXiv**: 2011.01403
- **Venue**: ICLR 2021 (Gunel et al.)
- **Problem solved**: +10.7% with 20 examples via contrastive loss
- **Applied in**: `tools/training/cycle3_train.py` -- SCL loss added (Cycle 3, commit `e9da81b`)
- **Status**: IMPLEMENTED

### 27. BCO: Binary Classifier Optimization
- **Venue**: ACL 2025
- **Problem solved**: Optimized binary classification for LLMs
- **Applied in**: Informed training objective design (binary pass/fail)
- **Status**: PLANNED

### 28. Calibration-Aware RL
- **arXiv**: (2026)
- **Problem solved**: LLM overconfidence fix via RL
- **Applied in**: Not adopted; SFT shown to be better calibrated than RL (Paper 17)
- **Status**: REJECTED (SFT preferred)

---

## G. Retrieval-Augmented Generation (abandoned approach)

### 29. RAG: Retrieval-Augmented Generation
- **Authors**: Lewis, P. et al.
- **Venue**: NeurIPS 2020
- **arXiv**: 2005.11401
- **Problem solved**: Knowledge-intensive NLP via retrieval + generation
- **Applied in**: Cycles 1-3 architecture (BM25 + Qwen3.5-27B-FP8), ABANDONED due to 0% fail recall
- **Status**: REJECTED

### 30. Self-RAG
- **Authors**: Asai et al.
- **Venue**: ICLR 2024
- **Problem solved**: Reflection tokens for retrieval relevance assessment
- **Applied in**: Evaluated in Cycle 2; retrieval-less approach was nearly as good
- **Status**: REJECTED

### 31. Contextual Retrieval
- **Source**: Anthropic (2024)
- **Problem solved**: Contextual prefix on chunks reduces retrieval failure by 49%
- **Applied in**: BM25 chunking strategy in Cycles 1-3
- **Status**: REJECTED (RAG approach abandoned)

### 32. CRAG: Corrective RAG
- **Authors**: Shi et al. (2026)
- **Problem solved**: Hybrid + Rerank R@5=0.816 vs BM25 0.644
- **Applied in**: Evaluated in Cycle 1; confirmed reranking improves retrieval
- **Status**: REJECTED (RAG approach abandoned)

---

## H. Protocol & Spec Analysis

### 33. ProtocolGuard
- **Venue**: NDSS 2026
- **Problem solved**: LLM-guided protocol rule extraction, 86.3% precision
- **Applied in**: Informed spec mining approach (Cycle 13, 15 rules found)
- **Status**: IMPLEMENTED (concept applied to manual spec mining)

### 34. RBCTest: Spec Constraint Mining
- **Venue**: ASE 2024
- **Problem solved**: Automated spec constraint mining, precision 94.3%
- **Applied in**: Informed systematic rule extraction from TCG/Opal spec
- **Status**: IMPLEMENTED (concept)

### 35. FormalJudge: Neuro-symbolic Verification
- **arXiv**: 2602.11136
- **Problem solved**: Decompose spec into atomic constraints, 7B > 72B
- **Applied in**: Informed rule decomposition in solver.py (50+ atomic rules)
- **Status**: IMPLEMENTED (concept)

### 36. NSVIF: Neuro-symbolic Verification
- **arXiv**: (2025)
- **Problem solved**: Combines neural and symbolic approaches for verification
- **Applied in**: Our hybrid architecture (rule engine + LoRA) is conceptually similar
- **Status**: IMPLEMENTED (architectural inspiration)

### 37. ARc: NL to Formal Logic
- **arXiv**: (2025)
- **Problem solved**: Natural language to formal logic conversion, 99.2% soundness
- **Applied in**: Spec text -> solver rules conversion approach
- **Status**: PLANNED

---

## I. In-Context Learning

### 38. Many-Shot In-Context Learning
- **Authors**: Agrawal, R. et al.
- **Venue**: NeurIPS 2024 (Spotlight)
- **arXiv**: 2404.11018
- **Problem solved**: Scale ICL to hundreds of examples for binary classification
- **Applied in**: 20-shot ICL experiment (Cycle 6); fail recall still 0% in logit mode
- **Status**: REJECTED (logit mode fundamentally broken for fail detection)

### 39. Chain-of-Thought Prompting
- **Authors**: Wei et al.
- **Venue**: NeurIPS 2022
- **Problem solved**: Step-by-step reasoning improves complex tasks
- **Applied in**: Thinking mode in generation experiments (Cycles 2-3)
- **Status**: REJECTED (too slow for production: 407s/case)

---

## J. Log Anomaly Detection (background research)

### 40. DeepLog
- **Authors**: Du, M. et al.
- **Venue**: ACM CCS 2017
- **Problem solved**: LSTM-based log anomaly detection
- **Applied in**: Background research only; requires thousands of normal sequences
- **Status**: REJECTED (insufficient data)

### 41. LogBERT
- **Authors**: Guo, H. et al.
- **arXiv**: 2103.04475 (2021)
- **Problem solved**: BERT-based masked log key prediction for anomaly detection
- **Applied in**: Background research only
- **Status**: REJECTED (insufficient data)

### 42. LogGPT
- **Authors**: Han, X. et al.
- **arXiv**: 2309.14482 (2023)
- **Problem solved**: GPT-2 + PPO for log anomaly detection
- **Applied in**: Background research only
- **Status**: REJECTED (insufficient data, PPO overfitting risk)

### 43. LogAnomaly
- **Authors**: Meng, W. et al.
- **Venue**: IJCAI 2019
- **Problem solved**: Semantic-aware log anomaly detection with template2Vec
- **Applied in**: Background research only
- **Status**: REJECTED (insufficient data)

---

## K. Protocol Fuzzing (background research)

### 44. RESTler: Stateful REST API Fuzzing
- **Authors**: Atlidakis, V. et al.
- **Venue**: ICSE 2019
- **Problem solved**: Spec-driven stateful API fuzzing
- **Applied in**: Inspired stateful session tracking in solver.py
- **Status**: IMPLEMENTED (concept: producer-consumer dependency tracking)

### 45. AFLNet: Greybox Fuzzing for Network Protocols
- **Authors**: Pham, V.-T. et al.
- **Venue**: ICST 2020
- **Problem solved**: Message-level mutation with state feedback
- **Applied in**: Background research; informed metamorphic test generation approach
- **Status**: IMPLEMENTED (concept)

### 46. StateAFL: Greybox Fuzzing for Stateful Servers
- **Authors**: Natella, R.
- **Venue**: Empirical Software Engineering 2022
- **Problem solved**: State variable tracking beyond response codes
- **Applied in**: Informed explicit state variable tracking in solver (session, auth, SP, locking)
- **Status**: IMPLEMENTED (concept)

### 47. ChatAFL: LLM-guided Protocol Fuzzing
- **Authors**: Meng, R. et al.
- **Venue**: NDSS 2024
- **Problem solved**: LLM guidance for protocol state exploration
- **Applied in**: LLM as rule discovery tool (not runtime classifier)
- **Status**: IMPLEMENTED (concept)

### 48. StatePre: LLM-based State Handling for Protocol Fuzzing
- **Authors**: Zhang, Y. et al.
- **Venue**: Electronics 2025
- **Problem solved**: LLM extracts state knowledge from RFC/spec
- **Applied in**: Spec-to-rule extraction approach
- **Status**: IMPLEMENTED (concept)

---

## L. Miscellaneous

### 49. RulePilot (2025)
- **Problem solved**: LLM generates executable security rules
- **Applied in**: Informed rule discovery workflow
- **Status**: PLANNED

### 50. Executable Governance (2025)
- **Problem solved**: Policy clause mining + SMT validation
- **Applied in**: Informed automated rule extraction pipeline design
- **Status**: PLANNED

### 51. Self-Refine
- **Authors**: Madaan et al.
- **Venue**: NeurIPS 2023
- **Problem solved**: Iterative self-feedback for +20% improvement
- **Applied in**: Not adopted for production
- **Status**: REJECTED

### 52. Rubric Is All You Need
- **Venue**: ACM 2025
- **Problem solved**: Structured rubric for LLM judging
- **Applied in**: System prompt design in RAG phase (Cycles 1-3)
- **Status**: REJECTED (RAG abandoned)

---

## Summary Statistics

| Status | Count |
|--------|-------|
| IMPLEMENTED | 25 |
| PLANNED | 7 |
| REJECTED | 20 |
| **Total** | **52** |
