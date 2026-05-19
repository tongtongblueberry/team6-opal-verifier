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

### Cycle 15: HP Sweep (진행 중)
- 수정: LR 범위 5e-5~1e-3 (이전 5e-6~1e-4는 너무 낮았음)
- 수정: batch_size=8 (VRAM 94% 활용, 이전 bs=1은 30%만 사용)
- Scheduler: cosine, Optimizer: AdamW 고정
- 서버에서 실행 중

---

## Training Data

| Source | Pass | Fail | Total |
|--------|------|------|-------|
| metamorphic | 650 | 1241 | 1891 |
| default_pass (synthetic) | 203 | 49 | 252 |
| public | 10 | 10 | 20 |
| **Total** | **863** | **1300** | **2163** |

---

## Server

- Host: `147.46.78.61:2227`, User: `student`
- GPU: L40S 46GB
- Pre-cached: Qwen3.5-{0.8B, 2B, 4B, 9B, 27B-FP8}
- Installed: peft, wandb, kernels (FP8)
