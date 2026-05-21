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

## M. Data Generation & Distribution Matching

### 53. SynAlign: Few-shot Synthetic Data with Distribution Matching via MMD
- **Venue**: WWW 2025
- **arXiv**: 2502.08661
- **Problem solved**: Reduces synthetic-to-real distribution gap using Maximum Mean Discrepancy (MMD) alignment; directly relevant to our train/public distribution mismatch (94% short vs 80% long trajectories)
- **Applied in**: Informed public 20 upsampling strategy and distribution-aware data generation
- **Status**: TO-EVALUATE (extends Paper 24's distribution matching with explicit MMD)

### 54. Generalizing Short to Long: Context Synthesis for Length Generalization
- **arXiv**: 2502.15592
- **Problem solved**: Synthesizes long-context training examples from short ones; addresses our core distribution mismatch (short training trajectories vs long test trajectories)
- **Applied in**: Not yet adopted; candidate for generating long trajectory training data from short examples
- **Status**: TO-EVALUATE

### 55. TraceLLM: LLM as Realistic Trace Generator
- **Venue**: EMNLP 2025
- **arXiv**: 2502.17439
- **Problem solved**: Uses LLMs for recursive generation of realistic protocol traces; directly applicable to generating synthetic TCG Opal test traces
- **Applied in**: Candidate for `tools/datagen/generate_spec_data.py` improvement
- **Status**: TO-EVALUATE

### 56. Dataset Decomposition: Variable Sequence Length Curriculum
- **Venue**: NeurIPS 2024
- **arXiv**: 2405.13226
- **Problem solved**: Curriculum learning that orders training by sequence length; trains short-first then long, improving generalization on variable-length inputs
- **Applied in**: Candidate for curriculum ordering in `tools/training/finetune_lora_v2.py`
- **Status**: TO-EVALUATE

### 57. Structurally-Diverse Sampling for Subset Selection
- **Venue**: EMNLP 2021
- **Problem solved**: Diversity-focused subset selection outperforms random sampling; ensures training data covers diverse failure modes
- **Applied in**: Informed gap data diversity strategy (9 gap categories)
- **Status**: PLANNED

### 58. Model Collapse: Training on Synthetic Data Causes Distribution Collapse
- **Venue**: Nature 2024
- **Problem solved**: Warns that iterative training on model-generated data causes progressive distribution narrowing and tail loss; critical risk for our synthetic data pipeline
- **Applied in**: Motivated inclusion of real public 20 cases in training mix (never train on pure synthetic)
- **Status**: IMPLEMENTED (design constraint: always mix real + synthetic data)

---

## N. Paired/Contrastive Training

### 59. PairCFR: Pairwise Counterfactual Reasoning
- **Problem solved**: Binary CE + contrastive loss on paired counterfactual examples; trains model to distinguish pass/fail by comparing near-identical traces with different outcomes
- **Applied in**: Candidate for paired training on our pass/fail trace pairs
- **Status**: TO-EVALUATE

### 60. DISCO: Distilling Counterfactuals with Large Language Models
- **Problem solved**: Uses LLMs to generate minimal counterfactual edits; creates paired examples where a single change flips the label
- **Applied in**: Candidate for generating targeted pass/fail pairs from spec rules
- **Status**: TO-EVALUATE

### 61. Curriculum Ordering for Counterfactual Pairs
- **Venue**: NAACL 2024
- **Problem solved**: Orders contrastive pairs by difficulty during training; easy pairs first, then hard (near-boundary) pairs
- **Applied in**: Candidate for curriculum in paired training pipeline
- **Status**: TO-EVALUATE

---

## O. Self-Consistency & Voting

### 62. Self-Consistency Improves Chain of Thought Reasoning in Language Models
- **Authors**: Wang et al.
- **Venue**: ICLR 2023
- **Problem solved**: Sample multiple reasoning paths and take majority vote; +17.9% on GSM8K over single-path CoT
- **Applied in**: Candidate for multi-sample voting at inference time in `src/lora_solver.py`
- **Status**: TO-EVALUATE

### 63. Multi-Temperature Voting for LLM Classification
- **Authors**: Wu et al.
- **Venue**: NeurIPS 2025
- **arXiv**: 2510.02611
- **Problem solved**: Samples at multiple temperatures and aggregates votes; +7.3 points over single-temperature inference
- **Applied in**: Candidate for ensemble inference strategy
- **Status**: TO-EVALUATE

### 64. 3 Votes Minimum for Binary Classification
- **Authors**: Liu
- **arXiv**: 2605.03379
- **Problem solved**: Establishes theoretical and empirical minimum of 3 votes for reliable binary classification with LLMs
- **Applied in**: Candidate for minimum vote count in inference pipeline
- **Status**: TO-EVALUATE

### 65. Binary Ensemble Accuracy via LLM Voting
- **Authors**: Khorashadizadeh et al.
- **arXiv**: 2412.00166
- **Problem solved**: Binary ensemble of LLM classifiers achieves 0.975 accuracy; provides theoretical framework for voting-based binary classification
- **Applied in**: Candidate for multi-model or multi-run ensemble strategy
- **Status**: TO-EVALUATE

---

## P. Distribution Shift & Two-Stage Fine-tuning

### 66. Not All LLM-Generated Data Are Equal: Importance Weighting
- **Venue**: ICLR 2025
- **arXiv**: 2410.21526
- **Problem solved**: Assigns importance weights to synthetic training examples based on proximity to real distribution; reduces synthetic-real gap
- **Applied in**: Candidate for weighting synthetic vs real training examples in `tools/training/finetune_lora_v2.py`
- **Status**: TO-EVALUATE

### 67. Surgical Fine-Tuning: Adaptation to Distribution Shifts
- **arXiv**: 2210.11466
- **Problem solved**: Selectively fine-tunes only specific layers (early/late) depending on the type of distribution shift; more robust than full fine-tuning
- **Applied in**: Candidate for selective layer training in LoRA (e.g., only attention layers in later blocks)
- **Status**: TO-EVALUATE

### 68. Few-Shot Recalibration for Distribution Shift
- **arXiv**: 2403.18286
- **Problem solved**: Uses a few target-distribution examples to recalibrate model confidence after distribution shift
- **Applied in**: Candidate for recalibrating LoRA confidence using public 20 cases
- **Status**: TO-EVALUATE

---

## Q. Hidden State Probing

### 69. Probing Hidden States for Calibrated Predictions
- **Year**: 2025
- **Problem solved**: Extracts predictions from hidden states instead of generation tokens; hidden state probes are better calibrated than generation-mode outputs
- **Applied in**: Validates our switch from generation to logit comparison mode (commit `79a361b`); candidate for direct hidden state classifier
- **Status**: IMPLEMENTED (concept validated our logit approach)

### 70. BERTology View of LLM Orchestrations: Token/Layer Selective Probes
- **arXiv**: 2601.13288
- **Problem solved**: Identifies which tokens and layers carry the most classification-relevant information; enables targeted probing instead of using all hidden states
- **Applied in**: Candidate for selective layer probing in `src/lora_solver.py`
- **Status**: TO-EVALUATE

---

## R. TCG Opal Domain References

### 71. TCG Opal SSC Test Cases v2.01
- **Source**: Trusted Computing Group (official specification)
- **Problem solved**: Official test oracle specification defining expected behaviors for all Opal SSC operations; ground truth for rule engine
- **Applied in**: `src/solver.py` -- all 50+ rules derived from this specification
- **Status**: IMPLEMENTED (core reference)

### 72. TCG Storage Opal Family Test Cases v1.02 (Oct 2025)
- **Source**: Trusted Computing Group (official specification)
- **Problem solved**: Latest test case definitions for Opal Family; includes updated session, locking, and authority rules
- **Applied in**: `src/solver.py` -- spec mining Cycle 13 extracted 15 new rules from this document
- **Status**: IMPLEMENTED (core reference)

---

## S. Training Data Generation via Mutation / Augmentation

This section surveys papers and tools for generating training data by mutating real test cases as templates. Our situation: 20 real labeled test cases (pass/fail protocol traces, 1-39 steps, JSON format), need 500-2000 training cases matching test distribution.

### 73. Data Mutation for Structurally Complex Test Cases (Xu & Offutt)
- **Authors**: Xu, W. & Offutt, J.
- **Venue**: The Computer Journal, 2009
- **URL**: https://dl.acm.org/doi/10.1093/comjnl/bxm043
- **Problem solved**: Generating large numbers of test cases from a few seed test cases by applying mutation operators to input data (not to the program)
- **Mutations applied**:
  - Value replacement (change field values within type-valid ranges)
  - Boundary value injection (min, max, off-by-one for numeric/string fields)
  - Structure insertion/deletion (add/remove nodes in tree-structured data)
  - Type perturbation (change data types, null injection)
- **Label correctness**: Mutation operators are defined relative to the specification schema; expected outputs are derived from spec rules (spec serves as oracle)
- **Mutations per original**: Tens to hundreds per seed, depending on operator set and input complexity
- **Open source**: No public implementation; concept is straightforward to implement for JSON/XML data
- **Relevance**: DIRECTLY APPLICABLE. Our JSON protocol traces are tree-structured data. Mutation operators: change status codes, swap method names, alter UID values, insert/delete steps, modify column ranges
- **Status**: TO-IMPLEMENT (highest priority)

### 74. XML Data Perturbation for Web Services Testing (Offutt & Xu)
- **Authors**: Offutt, J. & Xu, W.
- **Venue**: TAV-WEB Workshop, 2004; extended in Info. & Soft. Tech. 2011
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0020025510004846
- **Problem solved**: Systematic perturbation of XML messages for black-box web service testing; extends data mutation with XML Schema-aware operators
- **Mutations applied**:
  - Data value perturbation (within-type random/boundary values from XML Schema facets)
  - RPC message mutation (4 new operators for RPC-style messages)
  - Interaction perturbation (modify message sequences, not just individual messages)
  - Invalid case generation (violate schema constraints to test error handling)
- **Label correctness**: Schema validation determines validity; spec defines expected error responses for invalid inputs
- **Mutations per original**: ~20-50 per message depending on schema complexity
- **Open source**: No public tool, but the operators are well-defined and implementable
- **Relevance**: HIGH. TCG Opal messages are structured similar to XML/RPC. The "interaction perturbation" (modifying message sequences) directly maps to our step insertion/deletion/reordering mutations
- **Status**: TO-IMPLEMENT

### 75. LLM2LLM: Iterative Data Enhancement (ACL 2024)
- **Authors**: Lee, N. et al. (SqueezeAILab, UC Berkeley)
- **Venue**: ACL 2024 Findings
- **arXiv**: 2403.15042
- **URL**: https://github.com/SqueezeAILab/LLM2LLM
- **Problem solved**: Targeted augmentation of training data by iteratively generating synthetic examples from misclassified cases
- **Pipeline**:
  1. Fine-tune student LLM on seed data
  2. Evaluate on training data, extract incorrect predictions
  3. Teacher LLM generates synthetic data based on incorrect data points
  4. Add synthetic data back to training set, repeat
- **Label correctness**: Teacher LLM generates labeled examples; student validates by prediction consistency
- **Results**: +24.2% GSM8K, +32.6% CaseHOLD, +39.8% SST-2 in low-data regime (LLaMA2-7B)
- **Open source**: YES -- https://github.com/SqueezeAILab/LLM2LLM (MIT license)
- **Relevance**: MEDIUM-HIGH. Can adapt pipeline: fine-tune Qwen on 20 cases, find misclassified cases, use larger Qwen (27B) as teacher to generate targeted augmentations. Requires adaptation from text generation to protocol trace mutation
- **Status**: TO-EVALUATE

### 76. Polyjuice: General-Purpose Counterfactual Generation (ACL 2021)
- **Authors**: Wu, T., Ribeiro, M.T., Heer, J., Weld, D.S.
- **Venue**: ACL 2021
- **arXiv**: 2101.00288
- **URL**: https://idl.uw.edu/papers/polyjuice
- **Problem solved**: Generates diverse counterfactual examples using control codes to guide perturbation type (negation, insertion, deletion, lexical, resemantic, quantitative, shuffle)
- **Mutations applied**:
  - Negation (add/remove negation)
  - Lexical substitution (synonym/antonym replacement)
  - Quantitative change (modify numbers/quantities)
  - Insertion/deletion of phrases
  - Shuffle (reorder components)
  - Resemantic (change meaning while preserving structure)
- **Label correctness**: Generates candidates, human labels required (~70% less effort than manual). For our case: rule engine can serve as automatic labeler
- **Mutations per original**: ~5-10 diverse counterfactuals per input
- **Open source**: YES -- GPT-2 fine-tuned model on HuggingFace
- **Relevance**: MEDIUM. Control codes concept is applicable (we can define Opal-specific control codes: status_change, step_insert, step_delete, auth_change, etc.), but the model itself is for NL text, not JSON traces. Concept transferable
- **Status**: PLANNED (concept adoption)

### 77. ICDA: Iterative Counterfactual Data Augmentation (AAAI 2025)
- **Authors**: Plyler, M. & Chi, M.
- **Venue**: AAAI 2025
- **arXiv**: 2502.18249
- **URL**: https://ojs.aaai.org/index.php/AAAI/article/view/34195
- **Problem solved**: Iterative CDA that converges to low-noise augmented datasets even with initially noisy interventions; reduces spurious correlations
- **Pipeline**:
  1. Generate counterfactual dataset via initial intervention (can be noisy)
  2. Train rationale network on augmented data
  3. Use rationale network to generate better counterfactuals
  4. Iterate until convergence (mutual information of spurious signals decreases)
- **Label correctness**: Iterative refinement; rationale network learns which features are causal vs spurious
- **Relevance**: MEDIUM. The iterative refinement concept is valuable -- even noisy initial mutations can be refined. Our rule engine provides a strong oracle, making this less necessary but useful for edge cases
- **Status**: PLANNED

### 78. FuzzAug: Coverage-Guided Fuzzing for Data Augmentation (EMNLP 2025 Findings)
- **Authors**: (Multiple)
- **Venue**: EMNLP 2025 Findings
- **arXiv**: 2406.08665
- **URL**: https://arxiv.org/abs/2406.08665
- **Problem solved**: Applies fuzzing techniques (coverage-guided input mutation) to generate diverse training data for neural test generation
- **Mutations applied**:
  - Code transformations on fuzz targets to create new test functions
  - Coverage-guided selection: keep mutations that increase coverage, discard redundant ones
- **Label correctness**: Valid program semantics preserved by construction; coverage feedback ensures diversity
- **Relevance**: HIGH. The coverage-guided selection is key: generate many mutations, keep only those that exercise new rule engine paths. Prevents generating 1000 near-identical cases
- **Open source**: Not confirmed
- **Status**: TO-EVALUATE

### 79. Perturbation-Based Synthetic Data for Hallucination Detection (ACL 2024 Findings)
- **Authors**: Zhang, D., Gangal, V., Lattimer, B., Yang, Y.
- **Venue**: ACL 2024 Findings
- **arXiv**: 2407.05474
- **URL**: https://aclanthology.org/2024.findings-acl.789/
- **Problem solved**: Generates binary-labeled training data (faithful/hallucinated) by perturbation-based rewriting of system responses; T5-base fine-tuned on generated data beats SOTA zero-shot detectors
- **Mutations applied**:
  - Faithful rewriting (paraphrase without changing facts)
  - Hallucination injection (modify facts to create incorrect statements)
  - Both perturbation types applied to the SAME source, creating natural pass/fail pairs
- **Label correctness**: Source text serves as ground truth; perturbation direction determines label (faithful=pass, hallucinated=fail)
- **Relevance**: VERY HIGH. Directly analogous to our task: they generate pass/fail pairs from the same source by applying label-preserving vs label-flipping perturbations. We can do the same: take a passing trace, inject a spec violation (hallucination = fail), or take a failing trace, fix the violation (faithful = pass)
- **Status**: TO-IMPLEMENT (high priority, conceptually closest to our needs)

### 80. Dually Self-Improved Counterfactual Data Augmentation (ACL 2025)
- **Authors**: Zhang, X. et al.
- **Venue**: ACL 2025
- **URL**: https://aclanthology.org/2025.acl-long.260/
- **Problem solved**: Self-improved counterfactual generation using attention-based causal term identification + DPO refinement of LLM generator + balanced loss to prevent over-emphasis on augmented data
- **Pipeline**:
  1. Identify task-specific causal terms via attention distribution of task model
  2. LLM generates counterfactuals by perturbing causal terms
  3. DPO refines LLM to produce higher-quality counterfactuals
  4. Balanced loss for retraining (prevents synthetic data domination)
- **Label correctness**: Causal term identification ensures perturbations target label-relevant features; DPO filters low-quality generations
- **Relevance**: MEDIUM. Balanced loss concept is directly useful (prevent synthetic data from overwhelming 20 real cases). Causal term identification maps to "which JSON fields determine pass/fail"
- **Status**: PLANNED

### 81. NeuroCounterfactuals: Beyond Minimal-Edit (EMNLP 2022 Findings)
- **Authors**: Howard, P. & Singer, G.
- **Venue**: EMNLP 2022 Findings
- **arXiv**: 2210.12365
- **URL**: https://aclanthology.org/2022.findings-emnlp.371/
- **Problem solved**: Generates "loose counterfactuals" with larger edits than minimal-edit approaches, resulting in more linguistically diverse and natural augmented data
- **Key finding**: Minimal edits often fail to change label meaningfully and reduce grammaticality. Larger edits produce better training data
- **Relevance**: MEDIUM. Validates that our multi-step mutations (changing multiple fields/steps simultaneously) may be more effective than single-field mutations
- **Status**: PLANNED (concept)

### 82. iPanda: LLM Agent for Protocol Conformance Testing (2025)
- **Authors**: (Multiple)
- **arXiv**: 2507.00378
- **URL**: https://arxiv.org/abs/2507.00378
- **Problem solved**: First LLM-based framework for automated protocol conformance testing; extracts test cases from protocol specs, generates executable tests, identifies conformance issues
- **Pipeline**:
  1. LLM extracts functional points from protocol document
  2. Generates standardized test cases automatically
  3. Optional anomaly filter removes bad cases
  4. CoT-guided executable test generation
  5. Code-oriented RAG for implementation library usage
- **Label correctness**: Protocol spec serves as oracle; conformance check determines pass/fail
- **Relevance**: HIGH. Closest existing tool to our use case (protocol conformance testing with LLM). However, designed for network protocols (CoAP, RSocket), not TCG Opal. Concept of "spec -> test case extraction -> execution -> conformance check" is exactly our pipeline
- **Status**: TO-EVALUATE (concept adoption, not direct tool reuse)

### 83. AugGPT: ChatGPT-Based Text Data Augmentation (2023)
- **Authors**: Dai, H. et al.
- **arXiv**: 2302.13007
- **URL**: https://github.com/yhydhx/AugGPT
- **Problem solved**: Uses ChatGPT to rephrase training examples into semantically similar but lexically different variants for few-shot classification
- **Pipeline**:
  1. Fine-tune BERT on base (small) dataset
  2. Prompt ChatGPT to rephrase each example
  3. Fine-tune BERT on base + augmented data
- **Label correctness**: Rephrasing preserves label (semantically equivalent)
- **Open source**: YES -- https://github.com/yhydhx/AugGPT
- **Relevance**: LOW-MEDIUM. Rephrasing preserves label but does not generate label-flipped examples. For our case: can generate "equivalent passing traces" (different valid method orders, different UIDs) but not new failing traces
- **Status**: REJECTED (too simple for our needs; need label-flipping mutations, not just paraphrases)

### 84. TCG Opal SSC: Test Cases Specification (Official Conformance Suite)
- **Source**: Trusted Computing Group
- **URL**: https://trustedcomputinggroup.org/resource/tcg-storage-opal-test-cases/
- **Latest**: TCG Storage Opal Family Test Cases v1.02 (Oct 2025)
- **What it is**: Official conformance test suite for Opal SSC 1.00/2.00/2.01; defines test procedures, expected behaviors, pass/fail criteria for all Opal operations
- **Commercial tool**: ULINK TCG Storage Certification Test Suite (proprietary, hardware-focused)
- **Relevance**: The specification itself defines mutation patterns: each test case specifies "do X, expect Y; if Z instead, fail". These test procedures are our mutation templates
- **Status**: IMPLEMENTED (already used in solver.py rules and spec mining)

### 85. Model Collapse & Synthetic Data Mixing (Nature 2024)
- **Note**: Already listed as Paper 58, cross-referenced here
- **Key constraint for this section**: Never train purely on mutated data. Always maintain real:synthetic ratio (e.g., 1:5 to 1:10). Paper 58 proves iterative synthetic-only training causes progressive distribution collapse
- **Status**: IMPLEMENTED (design constraint)

---

## S.1 Synthesis: Recommended Mutation Pipeline for TCG Opal Traces

Based on the survey above, the recommended pipeline combines ideas from Papers 73, 74, 75, 78, 79:

### Mutation Operators (from Papers 73, 74, adapted for JSON protocol traces)
1. **Status mutation**: Change status codes (SUCCESS -> NOT_AUTHORIZED, FAIL, SP_BUSY, etc.)
2. **Value mutation**: Modify UIDs, column ranges, byte values within type-valid ranges
3. **Step insertion**: Add valid/invalid method calls to trace
4. **Step deletion**: Remove steps from trace (creates incomplete sessions)
5. **Step reordering**: Swap order of operations (e.g., authenticate before StartSession)
6. **Authority mutation**: Change authority credentials (AdminSP, Locking SP, etc.)
7. **Session mutation**: Modify session handles, HSN/TSN values
8. **Method mutation**: Replace method names (Get -> Set, Authenticate -> Next)

### Label Oracle (from Papers 73, 79, 82)
- Rule engine (solver.py) serves as automatic oracle for all mutations
- Pass trace + spec-violating mutation = labeled as FAIL
- Fail trace + spec-fixing mutation = labeled as PASS
- Ambiguous cases (rule engine returns uncertain) = DISCARD

### Quality Control (from Papers 75, 78, 80, 85)
- Coverage-guided selection (Paper 78): Keep mutations that trigger different rule engine paths
- Iterative focus on errors (Paper 75): Generate more mutations for cases the model gets wrong
- Balanced mixing (Paper 80): Use balanced loss to prevent synthetic data domination
- Anti-collapse (Paper 85): Maintain minimum 15-20% real data in training mix

### Estimated Yield
- 20 seed cases x 25-50 mutations each = 500-1000 initial cases
- After coverage-guided filtering: ~500-800 diverse cases
- After iterative error-focused augmentation (2-3 rounds): 1000-2000 cases

---

## Summary Statistics

| Status | Count |
|--------|-------|
| IMPLEMENTED | 28 |
| PLANNED | 14 |
| REJECTED | 20 |
| TO-EVALUATE | 18 |
| TO-IMPLEMENT | 2 |
| **Total** | **85** |
