# 현재 진행 상태 (세션 이어받기용)

최종 갱신: 2026-05-19 01:30 UTC

---

## 최상위 목표
leaderboard accuracy 71.50 → ≥ 85.00 (LLM 필수, 딥러닝 수업 과제)

## 현재 Best
- **71.50** (rule engine only, commit `2df1e71`, branch `best-71.50`)
- 최근 제출 68.00 (embedding classifier, regression → reverted)

## 서버 정보
- Host: `147.46.78.61:2227`, User: `student`, Password: `bg@3*a&5r+uoN2FRoAU^`
- Tool: `sshpass` (Homebrew 설치됨)
- Code: `/workspace/team6/team6-opal-verifier/`
- 설치됨: wandb, kernels(FP8), scikit-learn, peft
- GPU: L40S 48GB
- 사전 캐시 모델: Qwen3.5-{0.8B,2B,4B,9B}, Qwen3.5-27B-FP8

---

## 서버에서 실행 중인 작업
- **0.8B LoRA fine-tuning**: `nohup python3 tools/finetune_lora.py` (RAG_MODEL=Qwen/Qwen3.5-0.8B)
  - Log: `/workspace/team6/lora_08b.log`
  - Training data: 2163 cases, max_length=512, gradient checkpointing
  - 상태: 시작됨 (SSH rate limit으로 확인 불가)

## 확인 방법
```bash
sshpass -p 'bg@3*a&5r+uoN2FRoAU^' ssh student@147.46.78.61 -p 2227 \
  -o StrictHostKeyChecking=no "tail -20 /workspace/team6/lora_08b.log"
```

---

## Cycle 11 상태 (진행 중)

### 완료
1. [x] 논문 20편 조사 (RAGChecker, Learning to Defer, LoRA, ChunkRAG, RankRAG 등)
2. [x] RAGChecker (NeurIPS 2024) 완전 분석 → Context Utilization이 병목
3. [x] 해결책 선정: LoRA fine-tuning
4. [x] Training data 2163건 생성 (rule engine oracle)
5. [x] Embedding classifier 시도 → leaderboard 68.00 (regression)
6. [x] Solver reverted to RAG mode

### 진행 중
7. [ ] 0.8B LoRA fine-tuning (서버 실행 중)

### 다음
8. [ ] Training 결과 확인
9. [ ] Fine-tuned model로 public 20/20 regression test
10. [ ] 252건 synthetic test set에서 검증
11. [ ] 확실히 개선 시에만 leaderboard 제출

---

## 핵심 교훈 (Cycle 1-11)

| Approach | Result | 교훈 |
|----------|--------|------|
| Zero-shot logit scoring | fail recall=0% | Logit의 pass-bias 극복 불가 |
| Few-shot ICL logit | fail recall=0% | Few-shot도 logit에 안 먹힘 |
| Generation+thinking | 67%, 너무 느림 | 400s/case, 3시간 한도 초과 |
| Status prediction | fail recall=20% (최초!) | Task reframing이 유일한 개선 |
| Embedding+Ridge | leaderboard 68.00 regression | Synthetic ≠ hidden distribution |
| **LoRA fine-tuning** | **진행 중** | **표준 DL approach** |

## 절대 규칙
1. **LLM은 필수** (딥러닝 수업 과제)
2. **유저 지시는 항상 검증** (논문으로)
3. **Leaderboard는 확실할 때만 제출**
4. **Best score branch 관리** (`best-71.50`)
5. **매 cycle마다 논문 10-20편 조사**
6. **모든 agent는 opus 사용**

## 주요 파일
- `src/solver.py`: Rule engine + hybrid solver (현재 RAG mode)
- `src/rag.py`: BM25 + LLM judge (status prediction, generation, logit)
- `src/embedding_classifier.py`: Embedding + Ridge (artifacts/ 로드)
- `tools/finetune_lora.py`: LoRA fine-tuning script
- `tools/build_training_data.py`: 2163건 training data 생성
- `tools/generate_large_test_set.py`: 252건 DEFAULT_PASS test set
- `docs/rag_cycle_log.md`: Cycle 1-10 전체 기록
- `docs/current_task.md`: 이 파일
- `PROGRESS.md`: 통합 아카이브

## Training Data 위치 (서버)
- `/workspace/team6/training_data/training_cases.json` (2163건, 20.7MB)
- `/workspace/team6/training_data/embeddings.npz` (4B embeddings)
- `/workspace/team6/large_dp_test_set.json` (252건 test set)

## Git 상태
- Main branch: 실험 진행
- `best-71.50` branch: 안전한 제출 코드 (commit 2df1e71)
- 최신 commit: `3f3bb4d` (Cycle 11 LoRA fine-tuning)
