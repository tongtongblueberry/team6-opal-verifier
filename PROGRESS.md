# Experiment Log

## Best Score: 71.50

| Job | Score | Method | Date |
|-----|-------|--------|------|
| 93 | 60.50 | Rule engine v1 | 2026-05-17 |
| 94 | 68.00 | + spec index, Get rules | 2026-05-17 |
| 96 | 69.00 | + C_PIN secret tracking | 2026-05-17 |
| 100 | 69.50 | + coverage gaps | 2026-05-18 |
| **107** | **71.50** | **+ Locking access rules (UNEXPECTED_ERROR_STATUS)** | **2026-05-18** |
| 185 | 68.00 | Post-71.50 rule changes (REGRESSION) | 2026-05-19 |
| 186 | 68.00 | Embedding classifier (REGRESSION) | 2026-05-19 |
| 187 | 71.50 | Revert to best-71.50 (confirmed) | 2026-05-19 |
| 188 | 71.50 | + Authenticate rule (no change) | 2026-05-19 |

---

## Key Discovery: Regression Cause

Post-71.50에서 `UNEXPECTED_ERROR_STATUS`(모든 unexplained error → fail)를
`DEFAULT_PASS`(→ pass)로 변경한 것이 71.50 → 68.00 regression의 원인.
**aggressive approach가 hidden test에서 더 정확.**

---

## LLM Approach Comparison

| Approach | Fail Recall | Fail Precision | Note |
|----------|-------------|----------------|------|
| Zero-shot logit (27B) | 0% | N/A | pass-bias |
| Few-shot ICL logit (27B) | 0% | N/A | logit mode 무력 |
| Generation+thinking (27B) | N/A | N/A | 400s/case, 시간 초과 |
| Embedding+Ridge (9B) | N/A | N/A | 68.00 regression |
| LoRA 0.8B v1 (compressed) | 0% (synthetic) | N/A | format 정보 손실 |
| **LoRA 4B v2 (rich format)** | **46.9%** | **100%** | **유일한 성공** |

---

## Cycle Log

### Cycle 1-3: RAG Hybrid (폐기)
- BM25 retrieval + Qwen3.5-27B-FP8 logit/generation scoring
- Logit mode: fail recall 0% (severe pass-bias)
- Generation mode: 811s/case (시간 초과)
- **결론: zero-shot LLM spec reasoning은 불가**

### Cycle 4-6: Test Data + Few-shot ICL
- 252건 synthetic DEFAULT_PASS test set 생성
- 20-shot ICL logit: 여전히 fail recall 0%
- **결론: logit mode에서는 few-shot도 무력**

### Cycle 7-10: Rule Engine 확장 + Embedding
- Rule engine: 60.50 → 71.50 (spec 기반 규칙 추가)
- Embedding classifier (9B + Ridge): 68.00 regression
- **결론: rule engine이 LLM보다 정확. Distribution mismatch 심각**

### Cycle 11: LoRA Fine-tuning 시작
- 논문 20편 조사 (RAGChecker, LoRA, ChunkRAG 등)
- Training data 2163건 생성 (rule engine oracle)
- 0.8B LoRA v1 시작

### Cycle 12: LoRA 평가 + 논문 42편
- 0.8B v1: public fail recall 80%, synthetic fail recall 0%
- **발견: trajectory format이 정보를 거의 다 버림** (method/status만 보존)
- Rich format v2 설계: table, column, UID, payload, session state 포함
- 4B LoRA v2 학습: **fail precision 100%, recall 46.9%**

### Cycle 13: Regression 원인 확정 + Spec Mining
- Post-71.50 변경이 68.00 regression 원인 확정
- UNEXPECTED_ERROR_STATUS → DEFAULT_PASS 변경이 핵심
- Spec mining: 15개 미구현 규칙 발견 (Set ACL, class authority, session exclusivity 등)

### Cycle 14: 71.50 Base 복원 + LoRA Integration
- best-71.50 코드 복원, Solver에 LoRA override 추가
- Public 20/20 유지 확인
- 제출 한도 초과

### Cycle 15: HP Sweep Phase 1 — LR sweep 완료
- 데이터: spec-based 1,435건 (train 869 / val 283 / test 283)
- 5 epochs, batch_size=8, cosine scheduler, AdamW

LR Sweep 결과 (5 ep, val 283건, rank=16, alpha=32):

| LR | Acc | Fail Prec | Fail Rec | F1 | TP | FP | FN | TN |
|----|-----|-----------|----------|-----|----|----|----|----|
| 5e-5 | 76.3% | 0.77 | 0.74 | 0.75 | 102 | 31 | 36 | 114 |
| 1e-4 | 77.0% | 0.77 | 0.76 | 0.76 | 105 | 32 | 33 | 113 |
| 2e-4 | 78.1% | 0.77 | 0.78 | 0.78 | 108 | 32 | 30 | 113 |
| **5e-4** | **79.5%** | **0.77** | **0.83** | **0.80** | 115 | 35 | 23 | 110 |
| 1e-3 | 78.8% | 0.74 | 0.88 | 0.80 | 121 | 43 | 17 | 102 |

분석:
- Recall 단조증가 (0.74→0.88), precision은 5e-4까지 안정 (0.77) 후 1e-3에서 하락 (0.74)
- 5e-4가 accuracy 기준 best. 1e-3은 recall↑ but FP 급증 (35→43)
- 5 epochs에서 단조증가 → 수렴 전 비교일 가능성. Phase 2 (20 ep)에서 재검증 필요

### Cycle 15b: 코드 정리
- 폐기 파일 12개 삭제 (rag.py, embedding_classifier.py, v1 scripts 등)
- tools/ 서브디렉토리 재구성: training/, eval/, datagen/, analysis/
- lora_solver.py v1 fallback 제거 (v2 전용)
- sweep_lora.py: test set 평가 + adapter 저장 + extra_eval 추가

### Cycle 15c: 2-Phase Sweep (진행 중)
- Phase 1 (5 ep): sequential — LR, rank, max_length, dropout 후보 좁히기
- Phase 2 (20 ep): grid — LR(2) × rank(2) × alpha_ratio(2) × dropout(2) = 16 runs
- Why: sequential sweep은 HP 상호작용 놓침. 20 ep은 수렴 후 비교 가능

---

## Training Data (current: spec-based)

| Set | Pass | Fail | Total | 용도 |
|-----|------|------|-------|------|
| train | 486 | 383 | 869 | 모델 학습 |
| val | 145 | 138 | 283 | HP selection (sweep) |
| test | 157 | 126 | 283 | Unbiased final estimate |
| **Total** | **788** | **647** | **1,435** | |

이전 데이터 (metamorphic 2,163건, ~29% label noise)는 폐기.

---

## Server

- Host: `147.46.78.61:2227`, User: `student`
- GPU: L40S 46GB
- Pre-cached: Qwen3.5-{0.8B, 2B, 4B, 9B, 27B-FP8}
- Installed: peft, wandb, kernels (FP8)
