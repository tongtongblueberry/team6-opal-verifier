# Progress Log

- Updated: `2026-05-31 KST`.

## 2026-05-30: Cycle 10 — FSM-GFlowNet Data Generation + Training

### Val2 (public20) Results — gen_gflownet_v8_fixed

| Epoch | Checkpoint | val2 Accuracy | Pass Recall | Fail Recall | Notes |
|-------|-----------|--------------|-------------|-------------|-------|
| 2 | 464 | 65% (13/20) | 5/10 | 8/10 | |
| **4** | **928** | **70% (14/20)** | **7/10** | **7/10** | **Best** |
| 5 | 1160 | 60% (12/20) | 7/10 | 5/10 | Overfit start |
| 6 | 1392 | 60% (12/20) | 7/10 | 5/10 | |
| 7 | 1624 | 65% (13/20) | 8/10 | 5/10 | |

Best: Epoch 4, checkpoint-928 = 70% on public20
Previous best: LLM-only hidden = 70.00 (cycle 2)

### Method
- Implemented FSM-GFlowNet pipeline based on Samanta (2025, arXiv:2510.26197)
- FSM: 25 states, 89 actions, 180 transitions covering all 86 TCG/Opal spec rules
- GFlowNet: 2-layer FF policy (hidden=128), REINFORCE loss with baseline + T_MAX penalty
- Counterfactual labeling: records[0..n-2] always correct, records[n-1] output flipped 50%
- Gate A/B/C verification before training

### Data: gen_gflownet_v7
- Total: 2104 samples (Gate A/B/C PASS)
- Labels: pass 1038 / fail 1066 (50:50)
- Avg record count: 18.6 (public20: 16.4)
- Methods: 9 types including Read/Write (public20: 8)
- SPSessionIDs: 3226 unique
- Read=1772, Write=2153 commands (new vs previous gen)

### Improvements over previous data (gen_new, gen_sm)
| Issue | gen_new_4b | gen_sm | gen_gflownet_v7 |
|-------|-----------|--------|-----------------|
| Label errors | 18% | 0% | 0% |
| Sequence diversity | 22/39 | 7/340 | ~2000/2104 |
| Read/Write commands | 0 | 0 | 1772/2153 |
| SPSessionID | 1 | 460 | 3226 |
| Label balance | 28% fail | 65% fail | 50% fail |
| Gate PASS | N/A | N/A | A/B/C all PASS |

### Training
- Model: Qwen/Qwen3.5-0.8B full FT
- Train: 1693, Val: 431 (gen_gflownet_v7 80/20 + public20 10/10)
- 30 epochs, lr=5e-5, batch=1, grad_accum=8
- Status: COMPLETE — Best epoch 4, checkpoint-928 (70% val2)

### GFlowNet Training Evolution (v1→v7)
| Version | Issue | Fix | Result |
|---------|-------|-----|--------|
| v1 | 7 patterns only (gen_sm) | FSM + GFlowNet | 83 action types |
| v2 | POWER_CYCLE 30x over-represented | Restrict to recovery states | Fixed |
| v3 | Gate C: 120 label errors | Fix None record edge case | 0 errors |
| v3 | avg_len=37.2, 86% cutoff | — | — |
| v4 | Gaussian reward too narrow | — | avg=8.2 (too short) |
| v5 | Still too short | — | avg=4.1 |
| v6 | Capped log still grows via diversity | — | avg=35.7 |
| v7 | T_MAX penalty (×0.3) | Natural terminate 84% | avg=18.6 ✓ |

---

## 현재 상태

### 최신 제출
- **Job 903**: `gen-sm-e30-fullft-20260530`, Score **53.00**
- 이전 best: Job 687 `09b-e30-seed11-fix3`, Score **54.00**
- 모델: Qwen3.5-0.8B full FT, 30 epochs, gen_sm 240 train + public20 20 val

### 데이터 생성 파이프라인 이력

| 세대 | 방법 | Raw | Accepted | Exported | 핵심 문제 |
|------|------|-----|----------|----------|-----------|
| gen2 | Self-Instruct Qwen 7B | 208 | 0 | 0 | instruction_not_fixed |
| gen3 | Self-Instruct Qwen 7B | 76 | 0 | 0 | auth_session_missing |
| gen3.1 | Self-Instruct Qwen 7B | 72 | 1 | 1 | record_count_mismatch, domain_missing |
| **gen_new** | **Self-Instruct Qwen 0.8B** | **~550** | **~100** | **~43** | **mislabel 56%, state-building 3%, Get 반복** |
| **gen_new_4b** | **Self-Instruct Qwen 4B** | **~100** | **~54** | **~39** | **mislabel 18%, state-building 3%, SPID 오염** |
| **gen_sm** | **OPAL State Machine** | **300** | **300** | **300** | **label 100% 정확, state-building 76%** |

### gen_sm (State Machine Generator) — 현재 best 데이터

- 위치: `data/local/gen_sm/`
- 생성기: `runs/new_v2/opal_state_machine.py`
- 방법: Deterministic EFSM + Counterfactual Mutation
- 300건 (pass 150, fail 150), label 정확도 100%
- Phase P0-P6: Properties → MSID Read → SID Auth → Activate → Locking Read → Config → GenKey/I/O
- Mutation: Type A (status code flip), Type B (fake challenge, plaintext read), Type C (wrong UID, truncation)
- 11 unique sequence patterns, 11종 record count (1-46)

### Self-Instruct 파이프라인 (gen_new/gen_new_4b) — 폐기

Self-Instruct로 생성한 데이터는 학습에 사용하지 않는다. 이유:
1. **State tracking 부재**: 95%가 Get 반복, EndSession 0%, multi-session flow 없음
2. **Label 오류**: 0.8B에서 56% mislabel, 4B에서 18% mislabel (fail+all-SUCCESS)
3. **Rule coverage**: 86 rules 중 6-8개만 커버 (7-9%)
4. **SPID/SPSessionID 오염**: 비표준 SPID, 단일 SPSessionID 고정

근본 원인 (논문 근거):
- Sub-1B/4B 모델은 domain-specific structured data 생성 불가 (Ensemble-Instruct, 2023)
- AlpaGasus (ICLR 2024): Self-Instruct 52K 중 83%가 저품질
- 0.8B hallucination rate ~25% (arxiv 2602.14778), OPAL 도메인에서는 더 높음

### 학습 결과

| 실험 | 데이터 | Epochs | Public Score |
|------|--------|--------|-------------|
| 0.9B e30 seed11 (public20 only) | 10 train / 10 val | 30 | **54** |
| **0.9B e30 gen_sm** | **240 train / 80 val** | **30** | **53** |

gen_sm 데이터로 학습한 결과(53)가 public20-only(54)보다 1점 낮다.

가능한 원인:
1. gen_sm의 7개 sequence 패턴이 hidden test를 충분히 커버하지 못함
2. gen_sm의 trajectory 구조가 hidden test와 미묘하게 다름
3. public20 데이터가 val에만 포함되어 train에서 직접 학습하지 않음

## 다음 작업

1. **gen_sm + public20 합쳐서 train**: public20 20건을 train에도 포함
2. **gen_sm sequence diversity 확대**: 현재 7 → 20+ patterns
3. **gen_sm에 빠진 영역 추가**: Set final, GenKey final, Authority.Set final
4. **Best epoch checkpoint 선택**: epoch 12 (eval acc 94.4%)가 epoch 30보다 나을 수 있음
5. **Threshold 최적화**: p_fail threshold sweep on val
