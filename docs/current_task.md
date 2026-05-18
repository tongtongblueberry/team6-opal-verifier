# 현재 진행 상태 (세션 이어받기용)

최종 갱신: 2026-05-19 02:40 UTC

---

## 최상위 목표
leaderboard accuracy 71.50 → ≥ 85.00 (LLM 필수, 딥러닝 수업 과제)

## 현재 Best
- **71.50** (rule engine only, commit `2df1e71`, branch `best-71.50`)
- 최근 제출: 71.50 (revert 확인), 68.00 (post-71.50 변경으로 인한 regression)

## CRITICAL: 71.50 코드가 유일한 안전한 base!
- **best-71.50 branch만 사용** — post-71.50 변경은 3.5점 regression 유발
- 핵심 차이: `UNEXPECTED_ERROR_STATUS` (모든 unexplained error → fail) vs `DEFAULT_PASS` (→ pass)
- 71.50의 aggressive 접근이 hidden test에서 더 정확

## 서버 정보
- Host: `147.46.78.61:2227`, User: `student`, Password: `bg@3*a&5r+uoN2FRoAU^`
- Tool: `sshpass` (Homebrew 설치됨)
- Code: `/workspace/team6/team6-opal-verifier/`
- 설치됨: wandb, kernels(FP8), scikit-learn, peft
- GPU: L40S 48GB
- 사전 캐시 모델: Qwen3.5-{0.8B,2B,4B,9B}, Qwen3.5-27B-FP8

---

## 서버에서 실행 중인 작업
- **4B LoRA v2 fine-tuning**: `nohup python3 tools/finetune_lora_v2.py`
  - Log: `/workspace/team6/lora_4b_v2.log`
  - Model: Qwen/Qwen3.5-4B, max_length=1024, label masking, rich format
  - 진행: ~207/813 (25%), 약 83분 남음
  - GPU: 13.9GB / 46GB (30%)
- **0.8B LoRA v1**: 완료, adapter at `artifacts/lora_adapter/`

---

## Cycle 12 결과 (완료)

### 논문 42편 조사
- LLM fine-tuning, calibration, rule extraction, neuro-symbolic 등
- 핵심: BCO (ACL25), Calibration-Aware RL (2026), RBCTest (ASE24), TOGLL (ASE24)

### LoRA 0.8B v1 평가
| Dataset | Fail Recall | Pass Precision | Accuracy |
|---------|-------------|----------------|----------|
| Public 20 | **80%** | 20% | 50% |
| Synthetic 252 | **0%** | 100% | 80.6% |

- Public에서 fail 감지 가능 (80%!) but pass→fail 오판 과다
- Synthetic DEFAULT_PASS에서 여전히 무력 (distribution mismatch)
- Format 정보 손실 심각 (method/status만 보존, payload 미포함)

## Cycle 13 결과 (완료)

### Spec Mining — 15개 미구현 규칙 발견
1. Set NOT_AUTHORIZED (column-level ACL) — 10-20 cases
2. Class authority INVALID_PARAMETER — 5-15 cases
3. Get silent column omit — 5-15 cases
4. Authenticate rules — 5-10 cases
5. SP_BUSY session exclusivity — 5-10 cases
... (총 15개)

### Regression 원인 확정
- Post-71.50 rule engine 변경이 68.00 regression의 원인
- UNEXPECTED_ERROR_STATUS → DEFAULT_PASS 변경이 핵심
- 새 규칙 (class authority, read-only) 자체는 무관

### 71.50 base 재확인
- team6-revert-71 제출 → 71.50 재확인 ✓
- 이후 모든 작업은 71.50 base에서 시작

---

## Cycle 14 (진행 중)

### 목표
71.50 base에 안전한 규칙 추가하여 점수 향상

### 진행
- 71.50 코드 복원 완료
- Authenticate method 추가 검토 → UNEXPECTED_ERROR_STATUS가 valid error를 잡아서 위험
- **LoRA 4B v2 학습 중** (server, ~83분 남음)

### 다음
1. 4B v2 학습 완료 → 평가
2. 71.50 DEFAULT_PASS method (authenticate, random 등)에 LoRA 적용
3. 정밀한 rule 추가 (UNEXPECTED_ERROR_STATUS 활용)

---

## 핵심 교훈 (Cycle 1-14)

| Approach | Result | 교훈 |
|----------|--------|------|
| Zero-shot logit | fail recall=0% | pass-bias |
| Few-shot ICL logit | fail recall=0% | logit mode 무력 |
| Generation+thinking | 67%, 너무 느림 | 3시간 초과 |
| Embedding+Ridge | 68.00 regression | distribution mismatch |
| LoRA 0.8B v1 | public 80%/synthetic 0% | format 문제 + distribution |
| Post-71.50 rule changes | 68.00 regression | UNEXPECTED_ERROR_STATUS 제거 → 3.5점 하락 |
| **71.50 aggressive approach** | **71.50 best** | **unexplained error = fail이 정답** |

## 절대 규칙
1. **LLM은 필수** (딥러닝 수업 과제)
2. **71.50 base만 사용** (post-71.50 변경 금지)
3. **Leaderboard는 확실할 때만 제출**
4. **Best score branch 관리** (`best-71.50`)
5. **로컬에는 GitHub 코드만** (모델/데이터는 서버)

## 주요 파일
- `src/solver.py`: Rule engine (best-71.50 base)
- `src/lora_solver.py`: LoRA model integration
- `tools/finetune_lora_v2.py`: 4B LoRA training (rich format)
- `tools/eval_lora.py`: LoRA evaluation
- `docs/rag_cycle_log.md`: Cycle 1-10 전체 기록
- `docs/current_task.md`: 이 파일

## 서버 Training Data 위치
- `/workspace/team6/training_data/training_cases.json` (2163건, 20.7MB)
- `/workspace/team6/large_dp_test_set.json` (252건 test set)
- `/workspace/team6/lora_output/` (0.8B v1 checkpoint)
- `/workspace/team6/lora_output_v2/` (4B v2 checkpoint, 학습 중)
- `artifacts/lora_adapter/` (0.8B v1 adapter)

## Git 상태
- Main branch: solver.py는 best-71.50으로 복원
- `best-71.50` branch: 안전한 제출 코드 (commit 2df1e71)
