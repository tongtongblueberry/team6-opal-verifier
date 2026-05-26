# Deprecated Sweep Plan

이 문서는 과거 sweep 계획이며 현재 cycle의 실행 지침이 아니다. 특히 `/workspace/team6`, `sshpass`, legacy sweep script 관련 명령은 사용하지 않는다.

현재 실행 기준은 [server_operations_current.md](server_operations_current.md)와 [archive/current_task.md](archive/current_task.md)를 따른다.

# LoRA Hyperparameter Sweep Plan

최종 갱신: 2026-05-19

---

## 1. Best Approach: LoRA 4B v2

유일하게 유의미한 fail 감지를 달성한 LLM 접근법.

| 접근법 | Synthetic Fail Recall | Fail Precision | Accuracy |
|--------|----------------------|----------------|----------|
| Zero-shot logit (27B) | 0% | N/A | 80.6% |
| Few-shot ICL logit (27B) | 0% | N/A | 80.6% |
| LoRA 0.8B v1 (compressed format) | 0% | N/A | 80.6% |
| **LoRA 4B v2 (rich format)** | **46.9%** | **100%** | **89.7%** |

---

## 2. 모델 아키텍처

### Base Model: Qwen3.5-4B (Decoder-only Transformer)

```
Qwen3.5-4B
├── Embedding Layer: vocab_size=151,936 → hidden_dim=3,584
├── 36 Transformer Decoder Layers (L=36)
│   ├── Multi-Head Self-Attention (H=28 heads, d_k=128)
│   │   ├── q_proj: Linear(3584 → 3584)  ← LoRA 적용
│   │   ├── k_proj: Linear(3584 → 512)   ← LoRA 적용 (GQA: 4 KV heads)
│   │   ├── v_proj: Linear(3584 → 512)   ← LoRA 적용
│   │   └── o_proj: Linear(3584 → 3584)  ← LoRA 적용
│   ├── RMSNorm
│   ├── SwiGLU FFN
│   │   ├── gate_proj: Linear(3584 → 18944)
│   │   ├── up_proj:   Linear(3584 → 18944)
│   │   └── down_proj: Linear(18944 → 3584)
│   └── RMSNorm
└── LM Head: Linear(3584 → 151,936)

Total params: 4,208,897,024 (4.2B)
```

### LoRA Adapter (Hu et al., ICLR 2022)

```
Original weight: W₀ ∈ ℝ^{d×k}
LoRA decomposition: W = W₀ + ΔW = W₀ + B·A

  A ∈ ℝ^{r×k}  (rank r, initialized Gaussian)
  B ∈ ℝ^{d×r}  (initialized zero → ΔW starts at 0)

Forward pass:
  h = W₀·x + (α/r) · B·A·x

  r = rank (sweep target)
  α = scaling factor (sweep target)
  effective scaling = α/r
```

적용 대상: 각 layer의 q_proj, k_proj, v_proj, o_proj
- 4개 modules × 36 layers = 144 LoRA modules
- r=16 기준: ~3.1M trainable params (전체의 0.075%)

---

## 3. Loss Function

### Causal LM Cross-Entropy with Label Masking

```
L = -(1/|T_answer|) * Σ_{t ∈ T_answer} log p_θ(y_t | y_{<t}, x)
```

- x = 전체 input (system + trajectory + question)
- T_answer = assistant response tokens만 ("pass" or "fail")
- Prompt tokens: label=-100 (ignored by CrossEntropyLoss)
- Padding tokens: label=-100

---

## 4. 목표 Metrics

```
Accuracy       = (TP + TN) / N
Precision_fail = TP / (TP + FP)       ← 현재 100%, 유지 목표
Recall_fail    = TP / (TP + FN)       ← 현재 46.9%, 향상 목표
F1_fail        = 2·P·R / (P + R)
```

선정 기준: **fail precision ≥ 90% 조건 하에서 fail recall 최대화**

---

## 5. Training Data

- Total: 2163 cases
  - metamorphic: 1891 (pass=650, fail=1241)
  - default_pass: 252 (pass=203, fail=49)
  - public: 20 (pass=10, fail=10)
- **Validation split**: synthetic test set 마지막 52건 (pass=3, fail=49)
- Class ratio: pass=863 (39.9%), fail=1300 (60.1%)

---

## 6. 전체 Sweep 대상 Hyperparameters

### 고정 조건 (Sweep 대상 아님)
| Parameter | 값 | 근거 |
|-----------|---|------|
| Scheduler | cosine | 장기 학습(50ep)에 smooth decay |
| Optimizer | NAdam | Adam + Nesterov momentum |
| Format | v2 (rich) | 정보 손실 방지 — trajectory에 table/column/UID/payload 포함 |
| Label masking | True | loss를 answer token에만 집중 |
| FP16 | True | Mixed precision |
| Gradient checkpointing | True | VRAM 절약 |

### Sweep 대상 (중요도 순)

#### A. LoRA Rank (r) — capacity 결정
| r | α (=2r) | Trainable (4B) | 특성 |
|---|---------|---------------|------|
| 4 | 8 | ~0.8M | Minimal |
| 8 | 16 | ~1.6M | Light |
| **16** | **32** | **~3.1M** | **Baseline** |
| 32 | 64 | ~6.3M | Heavy |
| 64 | 128 | ~12.6M | Max capacity |

#### B. LoRA Alpha (α) — scaling factor, rank와 독립 sweep
| α/r ratio | 의미 |
|-----------|------|
| 1.0 | Conservative scaling |
| **2.0** | **Standard (현재)** |
| 4.0 | Aggressive scaling |
| 8.0 | Very aggressive |

→ rank=16 고정 시 α ∈ {16, 32, 64, 128} sweep

#### C. Learning Rate — 수렴 속도/안정성
| LR | 특성 |
|-----|------|
| 5e-6 | Very conservative |
| 1e-5 | Conservative |
| **2e-5** | **Standard** |
| 5e-5 | Aggressive |
| 1e-4 | Very aggressive |

#### D. LoRA Dropout — regularization
| Dropout | 특성 |
|---------|------|
| 0.0 | No regularization |
| **0.05** | **Light (현재)** |
| 0.1 | Medium |
| 0.2 | Heavy |

#### E. max_length — input coverage vs memory
| Length | Tokens | VRAM impact |
|--------|--------|-------------|
| 512 | Short | Low |
| **1024** | **Medium (현재)** | Medium |
| 2048 | Long | High |

#### F. Batch Size × Grad Accumulation — effective batch
45GB VRAM 최대 활용. 4B + LoRA + max_length=1024 ≈ 14GB → batch 증가 가능.

| Batch | Grad Accum | Effective | VRAM (est.) |
|-------|------------|-----------|-------------|
| **1** | **8** | **8 (현재)** | ~14GB |
| 2 | 4 | 8 | ~20GB |
| 4 | 2 | 8 | ~32GB |
| 2 | 8 | 16 | ~20GB |
| 4 | 4 | 16 | ~32GB |

#### G. Model Size — 최종 확인
| Model | VRAM | Speed |
|-------|------|-------|
| Qwen3.5-4B | ~14GB | ~8.2s/step |
| Qwen3.5-9B | ~24GB | ~8.3s/step |

---

## 7. Sweep 실행 순서

### Phase 1: Core sweep (5 epochs each, 4B model)

Step별로 순차 진행. 각 step에서 best를 다음 step에 carry forward.

```
Step 1: LR sweep        → {5e-6, 1e-5, 2e-5, 5e-5, 1e-4}  (5 runs)
Step 2: Rank sweep       → {4, 8, 16, 32, 64}                (5 runs)
Step 3: Alpha/r ratio    → {1, 2, 4, 8}                      (4 runs)
Step 4: Dropout sweep    → {0.0, 0.05, 0.1, 0.2}             (4 runs)
Step 5: max_length sweep → {512, 1024, 2048}                  (3 runs)
Step 6: Batch size sweep → {1×8, 2×4, 4×2, 2×8, 4×4}         (5 runs)
                                                        Total: 26 runs
```

각 run ≈ 56분 (4B, 5 epochs). 총 ≈ 24시간.
→ GPU 하나로 순차 실행.

### Phase 2: Model size check (best config)
- 4B vs 9B, 5 epochs
- 2 runs ≈ 2시간

### Phase 3: 본 학습 (50 epochs, best config)
- Best (model + LR + rank + alpha + dropout + max_length + batch) 조합
- 50 epochs
- 매 5 epoch마다 validation eval → best checkpoint 저장
- 예상 시간: ~9시간 (4B) 또는 ~9.5시간 (9B)

---

## 8. 평가 기준

각 sweep run은 validation set (52 cases)에서:
1. **Primary**: fail recall (precision ≥ 0.9 조건)
2. **Secondary**: F1 (fail class)
3. **Constraint**: fail precision ≥ 0.9 (FP 방지)

Best config = max fail recall with precision ≥ 0.9

---

## 9. 서버 실행 명령

```bash
# Sweep 시작
sshpass -p '...' ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   nohup python3 tools/sweep_lora.py > /workspace/team6/sweep.log 2>&1 &"

# 진행 확인
sshpass -p '...' ssh student@147.46.78.61 -p 2227 \
  "tail -30 /workspace/team6/sweep.log"

# 결과 확인
sshpass -p '...' ssh student@147.46.78.61 -p 2227 \
  "cat /workspace/team6/sweep_results.json"

# 본 학습 시작 (sweep 완료 후)
sshpass -p '...' ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   nohup python3 tools/sweep_lora.py --main > /workspace/team6/main_train.log 2>&1 &"
```
