# Current Task

- Updated: `2026-05-31 KST`.

## 현재 상태: Training complete, epoch 4 best (70% val2)

### 학습 완료
- **Run dir**: `ops/runs/20260530_gen_gflownet_v7_08b_fullft`
- **모델**: Qwen/Qwen3.5-0.8B, full fine-tuning
- **데이터**: gen_gflownet_v8_fixed (Gate A/B/C PASS) + public20 (20)
  - Train: 1693 (pass 821 / fail 872)
  - Val: 431 (pass 227 / fail 204)
- **설정**: 30 epochs, lr=5e-5, batch=1, grad_accum=8
- **GPU**: NVIDIA L40S 48GB, ~28GB used during full FT
- **Best checkpoint**: epoch 4, checkpoint-928 = **70% (14/20)** on public20 (val2)
  - Pass Recall: 7/10, Fail Recall: 7/10
- **Overfit observed**: epoch 5+ accuracy drops to 60%

### 다음 단계
1. Best checkpoint (epoch 4, checkpoint-928)으로 leaderboard 제출
2. Threshold 최적화 sweep
3. 결과 분석 및 다음 사이클 계획

### 이전 제출 결과
- Job 903: gen_sm e30 full FT → Score **53.00** (이전 best 54.00)
- 모델: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260530_gen_sm_09b_fullft/models/gen_sm_e30`
- 패키지: `/workspace/sinjeongmin_opal_verifier/ops/submission_gen_sm_e30/submissions/submit-gen_sm_e30`
- Previous killed runs: gen_sm_09b_fullft, gen_gflownet_v3_08b_fullft

## 2026-05-30 진행 사항

### 1. Self-Instruct 파이프라인 설계 + 실행 (gen_new)

- Self-Instruct 논문 (Wang et al. 2023 ACL) 기반 output-first 생성 파이프라인 설계
- `runs/new/generate_server.py`: 서버에서 Qwen 0.8B/4B로 trajectory 생성
- `runs/new/watch.sh`: 로컬 watcher (증분 pull + 7단계 필터링)
- 7단계 필터링: parse → invariant → dedup → judge → adversarial gate → public20 비교 → audit

### 2. Self-Instruct 실패 분석

gen_new (0.8B): 550 raw → 43 exported, mislabel 56%, state-building 3%
gen_new_4b (4B): 100 raw → 39 exported, mislabel 18%, state-building 3%

근본 원인:
- LLM이 state-changing trajectory를 생성하지 못함 (Get 반복 95%)
- EndSession 0%, multi-session flow 없음
- Label을 LLM이 결정 → 56% 오류
- Spec rule coverage 7% (6/86 rules)

Agent 분석으로 확인:
- Root cause 1: Seed truncation이 EndSession 숨김
- Root cause 2: Shortest-seed 편향 → trivial trajectory만 생성
- Root cause 3: 0.8B model capacity 부족 (mode collapse)
- Root cause 4: Invariant checker의 label-status 검사 비활성화

수정 적용:
- Fix 2: Seed 선택 → multi-session 우선
- Fix 4: Deterministic label assignment (final_status vs rule expected_status)
- Fix 6: 0.8B → 4B 모델 교체
- Invariant checker: fail+all-SUCCESS hard reject 복원

### 3. OPAL State Machine Generator (gen_sm) — 새 접근법

Self-Instruct의 근본적 한계를 인식하고 완전히 다른 접근법 채택:
- Deterministic EFSM + Counterfactual Mutation
- Public20의 Phase Progression (P0-P6) 구조를 코드로 재현
- Pass trajectory를 state machine으로 생성, minimal mutation으로 fail 생성

`runs/new_v2/opal_state_machine.py` 구현:
- 300건 생성 (pass 150, fail 150)
- Label 정확도 100%, state-building 76%, 11 unique sequences
- GenKey, Authority.Set, SP_BUSY/SP_FROZEN/NO_SESSIONS_AVAILABLE 커버

### 4. FSM-GFlowNet 파이프라인 (gen_gflownet_v7) — 현재 활성

FSM-GFlowNet: GFlowNet-inspired exploration으로 OPAL state machine trajectory 생성
- gen_gflownet_v7: 2104 samples, Gate A/B/C 모두 PASS
- 이전 gen_gflownet_v3 대비 대폭 개선된 데이터 품질 및 양
- Gate A: parse + invariant validation
- Gate B: distribution analysis (record count, label balance)
- Gate C: adversarial rulebook quality gate
- Full FT 학습 중 (PID 255383)

### 5. 이전 학습 + 제출

- gen_sm 300건으로 train/val split (240/80)
- 0.9B full FT 30 epochs → eval acc 94.4% (epoch 12 peak)
- 제출: Job 903, Score 53.00

## Hard rules

- Runtime solver는 LLM-only
- Rule engine 사용 금지
- public20 labels는 train/val에만 사용, generation에 사용 안 함
