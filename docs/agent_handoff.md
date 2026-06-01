# Agent Handoff

<!-- Changed: handoff를 gen_gflownet_v7 0.8B full FT 학습 상태 중심으로 갱신했다. -->
<!-- Why: 다음 agent가 현재 활성 학습 PID와 데이터 파이프라인을 정확히 파악해야 한다. -->

- Updated: `2026-05-31 KST`.
- Active local root:
  `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`.
- Active server root: `/workspace/sinjeongmin_opal_verifier`.

## 먼저 읽을 것

<!-- Changed: 현재 활성 상태 기준으로 우선순위 재배열. -->

1. `docs/current_task.md`
2. `docs/server_operations_current.md`
3. `docs/agent_handoff.md`
4. `README.md`
5. `PROGRESS.md`

## 현재 상태: Training complete, epoch 4 best (70% val2)

<!-- Changed: 학습 완료, val2 결과 반영. -->
<!-- Why: 다음 agent는 best checkpoint로 submission + threshold 최적화를 수행해야 한다. -->

- **Run dir**: `ops/runs/20260530_gen_gflownet_v7_08b_fullft`
- **Model**: Qwen/Qwen3.5-0.8B, full fine-tuning, 30 epochs
- **Data**: gen_gflownet_v8_fixed (Gate A/B/C PASS) + public20 20 samples
- **Train split**: 1693 (pass 821 / fail 872)
- **Val split**: 431 (pass 227 / fail 204)
- **GPU**: NVIDIA L40S 48GB, ~28GB used

### Val2 (public20) Results

| Epoch | Checkpoint | val2 Accuracy | Pass Recall | Fail Recall | Notes |
|-------|-----------|--------------|-------------|-------------|-------|
| 2 | 464 | 65% (13/20) | 5/10 | 8/10 | |
| **4** | **928** | **70% (14/20)** | **7/10** | **7/10** | **Best** |
| 5 | 1160 | 60% (12/20) | 7/10 | 5/10 | Overfit start |
| 6 | 1392 | 60% (12/20) | 7/10 | 5/10 | |
| 7 | 1624 | 65% (13/20) | 8/10 | 5/10 | |

- **Best**: Epoch 4, checkpoint-928 = 70% on public20
- **Previous best**: LLM-only hidden = 70.00 (cycle 2)
- **Overfit**: epoch 5+ accuracy drops, fail recall degrades

### 다음 단계

1. Best checkpoint (epoch 4, checkpoint-928)으로 leaderboard 제출
2. Threshold 최적화 sweep
3. 결과 분석 및 다음 사이클 계획

## FSM-GFlowNet 파이프라인 요약

FSM-GFlowNet은 GFlowNet-inspired exploration을 OPAL deterministic finite state machine 위에서 수행하여 trajectory를 생성하는 파이프라인이다.

- OPAL spec에서 state machine을 구축하고, GFlowNet의 flow-based exploration으로 다양한 state transition path를 탐색
- Pass trajectory: 정상 state transition으로 expected final status에 도달
- Fail trajectory: counterfactual mutation 또는 invalid transition으로 fail condition 유발
- gen_gflownet_v7: 2104 samples 생성, label balance 양호 (pass/fail ~50:50)

### Gate A/B/C 프로세스

- **Gate A**: Parse validation + invariant check (구조적 정합성, label-status 일관성)
- **Gate B**: Distribution analysis (record count 분포, label balance, public20 대비 유사도)
- **Gate C**: Adversarial rulebook quality gate (spec rule coverage, domain coverage, auth-session evidence)

## 주요 파일 목록

### 서버 측 (학습 관련)
- `ops/runs/20260530_gen_gflownet_v7_08b_fullft/` — 현재 학습 run directory
- `ops/runs/20260530_gen_gflownet_v7_08b_fullft/train_pid.txt` — 학습 PID
- `ops/runs/20260530_gen_gflownet_v7_08b_fullft/train.log` — 학습 로그

### 서버 측 (데이터)
- `/workspace/sinjeongmin_opal_verifier/data/gen_gflownet_v7/` — gen_gflownet_v7 데이터
- `/workspace/sinjeongmin_opal_verifier/data/public20/` — public20 데이터

### 로컬 측 (생성 파이프라인)
- `runs/new/generate_server.py` — 서버 trajectory 생성 스크립트
- `runs/new/watch.sh` — 로컬 watcher (증분 pull + 필터링)
- `runs/new_v2/opal_state_machine.py` — OPAL state machine generator (gen_sm)
- `tools/analysis/adversarial_rulebook_quality_gate.py` — Gate C adversarial quality gate

### 이전 실행 (참고용)
- gen_sm_09b_fullft: killed, Job 903 Score 53.00
- gen_gflownet_v3_08b_fullft: killed, superseded by v7

## Data Generation History (archived)

### Self-Instruct (gen_new, gen3, gen3.1) — stopped/no-go

Self-Instruct 파이프라인은 gen2 → gen3 → gen3.1을 거치며 모두 낮은 acceptance rate로 중단됨.
- gen3.1: 72 raw → 1 accepted (stopped)
- 근본 원인: LLM이 state-changing trajectory 생성 불가, quality gate bypass 없이는 사용 불가
- 상세: `docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`, `docs/archive/cycles/2026-05-29_gen3_zero_accept_gen31_restart.md`

### OPAL State Machine (gen_sm) — 제출됨, 낮은 성능

- 300건 deterministic 생성 (pass 150, fail 150)
- 학습 후 제출: Score 53.00 (Job 903)
- 근본 원인: sequence diversity 부족 (11 unique patterns)

### FSM-GFlowNet (gen_gflownet_v8_fixed) — 학습 완료

- GFlowNet-inspired exploration으로 다양한 state transition path 탐색
- 2104 samples, Gate A/B/C 모두 PASS
- 0.8B full FT 학습 완료, best checkpoint: epoch 4 (70% val2)

## hard rules

<!-- Changed: runtime and data eligibility rules를 유지했다. -->
<!-- Why: cleanup이 solver architecture나 training eligibility를 바꾸면 안 된다. -->

- Runtime solver remains LLM-only.
- Offline rule-book gates are data validation, not runtime inference.
- Do not use public20 labels in generation, judge prompts, or generated targets.
- Do not train on `data/local/gen3_pending`.
- Do not train on `data/local/gen3` until server canonical export is synced and follow-up gates pass.
- Do not store secrets in repo files, docs, command lines, logs, or archives.
- Do not revert user changes or run destructive git commands.
