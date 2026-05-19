# 현재 진행 상태 (세션 이어받기용)

최종 갱신: 2026-05-19

---

## 최상위 목표
leaderboard accuracy 71.50 -> >= 85.00 (LLM 필수, 딥러닝 수업 과제)

## 현재 Best
- **71.50** (rule engine only, commit `2df1e71`, branch `best-71.50`)
- 최근 제출: 71.50 (revert 확인), 68.00 (post-71.50 변경으로 인한 regression)
- 오늘 제출 한도 초과 -- 다음 제출은 내일 이후

## CRITICAL: 71.50 코드가 유일한 안전한 base
- **best-71.50 branch만 사용** -- post-71.50 변경은 3.5점 regression 유발
- 핵심 차이: `UNEXPECTED_ERROR_STATUS` (모든 unexplained error -> fail) vs `DEFAULT_PASS` (-> pass)
- 71.50의 aggressive 접근이 hidden test에서 더 정확

## 서버 정보
- Host: `147.46.78.61:2227`, User: `student`
- Password: **저장소에 기록하지 않음. 별도 관리.**
- Tool: `sshpass` (Homebrew 설치됨)
- Code: `/workspace/team6/team6-opal-verifier/`
- 설치됨: wandb, kernels(FP8), scikit-learn, peft
- GPU: L40S 48GB
- 사전 캐시 모델: Qwen3.5-{0.8B,2B,4B,9B}, Qwen3.5-27B-FP8

---

## 현재 아키텍처

```
Input trajectory
       |
[1] Rule Engine (StatefulOpalVerifier.verify_with_trace) -- 71.50 base
       |
  prediction + rule_id
       |
  rule_id == UNEXPECTED_ERROR_STATUS?
       NO  -> rule prediction 그대로 사용 (high confidence)
       YES -> LoRA 4B override
              |
[2] Qwen3.5-4B + LoRA adapter
       |
  LoRA prediction
       |
  LoRA says "pass" -> override to pass (rescue false positive)
  LoRA says "fail" -> keep fail (agree with rule engine)
```

---

## LoRA 4B v2 현황

### 학습 완료
- Model: Qwen/Qwen3.5-4B, max_length=1024, label masking, rich format
- Adapter: `artifacts/lora_adapter_v2/` (~32MB)
- Training data: 2163건 (rule engine 생성)

### 평가 결과
| Dataset | Fail Recall | Fail Precision | Accuracy |
|---------|-------------|----------------|----------|
| Synthetic 252 | **46.9%** (23/49) | **100%** (23/23) | **89.7%** (226/252) |
| Public 20 | 80% (8/10) | 44.4% (8/18) | 50% (10/20) |

- Synthetic에서 false positive 0건 -- override mode에 안전
- Public에서 distribution mismatch로 false positive 과다 (reference only)

### Integration 준비 완료
- `src/lora_solver.py`: LoRA adapter loading + prediction
- Override mode: UNEXPECTED_ERROR_STATUS fail -> LoRA pass일 때만 override

---

## HP Sweep (진행 중)

### 목적
LoRA 4B v2의 hyperparameter 최적화로 fail recall 향상 (46.9% -> 60%+ 목표)

### Sweep 설정
- **고정**: Scheduler=cosine, Optimizer=NAdam
- **탐색 변수**: LR, rank, alpha, dropout, max_length, batch_size
- Script: `tools/sweep_lora.py`
- 서버: `/workspace/team6/team6-opal-verifier/`
- 26 runs, 각 ~56분

### 진행 상태
- Sweep script 준비 완료
- SSH rate limiting으로 서버 접속 제한됨
- 실행 대기 중

---

## Cycle 요약 (12-15)

| Cycle | 핵심 작업 | 결과 |
|-------|----------|------|
| 12 | 논문 42편 조사 + LoRA 4B v2 학습 | fail precision=100%, fail recall=46.9% |
| 13 | Regression 원인 확정 + spec mining (15 rules) | UNEXPECTED_ERROR_STATUS가 71.50 핵심 |
| 14 | 71.50 base 복원 + LoRA override 설계 | best-71.50 branch만 사용 |
| 15 | HP sweep 계획 + sweep script 구현 | 26 runs, cosine+NAdam 고정 |

---

## 다음 TODO (우선순위 순)

1. **HP sweep 실행 및 완료** -- 서버 접속 안정화 후
2. **Best config로 50-epoch 본 학습** -- 매 5 epoch validation, best checkpoint 저장
3. **Leaderboard 제출** -- fail precision >= 90% 확인 후 (내일 이후)
4. **9B model 비교** -- 4B vs 9B (같은 config)
5. **Rule engine 확장** (71.50 base에서 안전한 규칙만)

## 핵심 교훈 (Cycle 1-15)

| Approach | Result | 교훈 |
|----------|--------|------|
| Zero-shot logit | fail recall=0% | pass-bias |
| Few-shot ICL logit | fail recall=0% | logit mode 무력 |
| Generation+thinking | 67%, 너무 느림 | 3시간 초과 |
| Embedding+Ridge | 68.00 regression | distribution mismatch |
| LoRA 0.8B v1 | public 80%/synthetic 0% | format 문제 + distribution |
| Post-71.50 rule changes | 68.00 regression | UNEXPECTED_ERROR_STATUS 제거 -> 3.5점 하락 |
| **71.50 aggressive approach** | **71.50 best** | **unexplained error = fail이 정답** |
| **LoRA 4B v2 override** | **fail prec=100%, recall=46.9%** | **유일한 성공적 LLM 접근** |

## 절대 규칙
1. **LLM은 필수** (딥러닝 수업 과제)
2. **71.50 base만 사용** (post-71.50 변경 금지)
3. **Leaderboard는 확실할 때만 제출** (오늘 한도 초과)
4. **Best score branch 관리** (`best-71.50`)
5. **로컬에는 GitHub 코드만** (모델/데이터는 서버)
6. **서버 비밀번호 저장소 기록 금지**

## 주요 파일
- `src/solver.py`: Rule engine (best-71.50 base) + LoRA override
- `src/lora_solver.py`: LoRA adapter loading and prediction
- `tools/finetune_lora_v2.py`: 4B LoRA training (rich format)
- `tools/sweep_lora.py`: HP sweep script
- `tools/eval_lora.py`: LoRA evaluation
- `docs/sweep_plan.md`: HP sweep 계획 및 architecture 상세
- `docs/rag_cycle_log.md`: Cycle 1-15 전체 기록

## 서버 Training Data 위치
- `/workspace/team6/training_data/training_cases.json` (2163건, 20.7MB)
- `/workspace/team6/large_dp_test_set.json` (252건 test set)
- `/workspace/team6/lora_output/` (0.8B v1 checkpoint)
- `/workspace/team6/lora_output_v2/` (4B v2 checkpoint)
- `artifacts/lora_adapter/` (0.8B v1 adapter)
- `artifacts/lora_adapter_v2/` (4B v2 adapter, ~32MB)

## Git 상태
- Main branch: solver.py는 best-71.50으로 복원
- `best-71.50` branch: 안전한 제출 코드 (commit 2df1e71)
