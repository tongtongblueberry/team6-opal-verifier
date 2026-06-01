# Team 6 Opal Verifier

SNU Introduction to Deep Learning (M2177.0043) Opal command-response trajectory
pass/fail classification project.

## Current Status (2026-05-30 KST)

- Architecture: **LLM-only** (Qwen3.5-0.8B full fine-tuning)
- **Best leaderboard**: 54.00 (Job 687, 0.9B e30 public20-only)
- **Latest submission**: 53.00 (Job 903, 0.9B e30 gen_sm state machine data)

### Training In Progress

- Server PID: 255383
- Model: Qwen/Qwen3.5-0.8B full FT
- Data: gen_gflownet_v7 (2104 samples) + public20 (20 samples)
- Train: 1693 (pass 821 / fail 872), Val: 431 (pass 227 / fail 204)
- Settings: 30 epochs, lr=5e-5, batch=1, grad_accum=8, bf16
- Run dir: `ops/runs/20260530_gen_gflownet_v7_08b_fullft`
- Estimated: ~5.3 hours

## 과제 정의

- 입력: OPAL 프로토콜 command-response trajectory (records 배열)
- 출력: 마지막 record (cN, rN)이 TCG/Opal 명세 + 이전 records로 구축된 상태에서 유효한지 pass/fail 판정
- 핵심: records[0..N-2]는 항상 참 (정상적 state 전이), records[N-1]의 output만 판정
- pass = 마지막 output이 spec상 예상되는 응답
- fail = 마지막 output이 spec상 예상되지 않는 응답

## 데이터 생성 파이프라인 이력

### 3. FSM-GFlowNet (gen_gflownet_v7) — 현재 사용

Based on the paper "Structurally Valid Log Generation using FSM-GFlowNets" (Samanta, 2025, arXiv:2510.26197).

Pipeline:
1. **FSM**: 25 states, 89 actions, 180 transitions covering 86 TCG/Opal spec rules
2. **GFlowNet**: 2-layer FF policy (hidden=128), REINFORCE loss with baseline + T_MAX penalty
3. **Counterfactual labeling**: last record output flipped 50% → pass/fail
4. **Gate A/B/C verification**: structural integrity, public20 dimension match, label quality

- 데이터: gen_gflownet_v7 (2104건, pass 1048 / fail 1056)
- Train: 1693 (pass 821 / fail 872), Val: 431 (pass 227 / fail 204)
- Label: 100% 정확 (deterministic counterfactual + gate verification)

Files:
- `tools/datagen/opal_fsm.py` — FSM definition
- `tools/datagen/opal_gflownet_env.py` — GFlowNet environment
- `tools/datagen/opal_gflownet_train.py` — Training + generation
- `tools/datagen/opal_record_builder.py` — FSM action → JSON record
- `tools/datagen/opal_export_trajectories.py` — Export with counterfactual labeling

### 2. OPAL State Machine (gen_sm) — FSM-GFlowNet으로 대체됨

Deterministic EFSM (Extended Finite State Machine) + Counterfactual Mutation.

- 생성기: `runs/new_v2/opal_state_machine.py`
- 데이터: `data/local/gen_sm/` (300건, pass 150 / fail 150)
- Label: 100% 정확 (deterministic counterfactual)
- State-building: 76% meaningful (public20과 동등)
- Phase Progression: P0(Properties) → P1(MSID Read) → P2(SID Auth) → P3(Activate) → P4(Locking Read) → P5(Config) → P6(GenKey/I/O)
- Mutation Types:
  - Type A: status code flip (SUCCESS ↔ NOT_AUTHORIZED/INVALID_PARAMETER/FAIL/SP_BUSY/SP_FROZEN)
  - Type B: value corruption (fake HostChallenge, plaintext Read)
  - Type C: structural (wrong SP UID, truncation)

논문 근거:
- [EXTERNAL KNOWLEDGE] Kalaji et al. (2021). EFSM based protocol test generation.
- [EXTERNAL KNOWLEDGE] Kulkarni et al. (2024). SynthDST: template + schema generation (EACL 2024).
- [EXTERNAL KNOWLEDGE] Kaushik et al. (2020). Counterfactual Data Augmentation (ICLR 2020).

### 1. Self-Instruct (gen2/gen3/gen3.1/gen_new/gen_new_4b) — 폐기

LLM(Qwen 0.8B/4B/7B)으로 trajectory를 직접 생성하는 방식.

실패 원인:
- LLM이 구조적으로 유효한 OPAL trajectory를 생성하지 못함 (parse 37-43%)
- State tracking 부재: EndSession 0%, multi-session flow 없음, Get 반복 95%
- Label 오류: 18-56% mislabel (fail+all-SUCCESS, pass+error-status)
- Spec rule coverage: 86 rules 중 6-8개만 (7-9%)

논문 근거:
- [EXTERNAL KNOWLEDGE] Wang et al. (2023). Self-Instruct. ACL 2023.
- [EXTERNAL KNOWLEDGE] Kim et al. (2023). Ensemble-Instruct: sub-40B 모델은 adequate quality 불가.
- [EXTERNAL KNOWLEDGE] Chen et al. (2024). AlpaGasus (ICLR 2024): Self-Instruct 83% 저품질.

### Public20 구조 분석

Public20의 20건은 10개 pass/fail **paired counterfactual data**:
- 8/10 쌍에서 method sequence 동일, 마지막 record만 다름
- Fail type: 70% status code flip, 20% value corruption, 10% structural

| Phase | Session | 내용 | tc범위 |
|-------|---------|------|--------|
| P0 | 없음 | Properties | tc1/tc11 |
| P1 | Admin SP, no auth | Read MSID | tc2/tc12 |
| P2 | Admin SP, SID auth | Change SID password | tc3-4/tc13-14 |
| P3 | Admin SP, SID auth | Activate Locking SP | tc5/tc15 |
| P4 | Locking SP | Read initial state | tc6-8/tc16-18 |
| P5 | Locking SP, Admin1 auth | Configure | tc9/tc19 |
| P6 | I/O | Encryption verification | tc10/tc20 |

## 학습

- 모델: Qwen3.5-0.8B (0.9B params), full fine-tuning
- Framework: TRL SFTTrainer, completion_only_loss=True
- 서버: 147.46.78.61:2227, NVIDIA L40S 46GB

### 제출 이력

| Job | 데이터 | Score | 날짜 |
|-----|--------|-------|------|
| 687 | public20 10 train / 10 val, e30 | **54** | 2026-05-28 |
| 903 | gen_sm 240 train / 80 val, e30 | 53 | 2026-05-30 |

## 파일 구조

### 활성 도구

#### 데이터 생성 (FSM-GFlowNet)
- `tools/datagen/opal_fsm.py`: FSM definition (25 states, 89 actions, 180 transitions)
- `tools/datagen/opal_gflownet_env.py`: GFlowNet environment
- `tools/datagen/opal_gflownet_train.py`: GFlowNet training + generation
- `tools/datagen/opal_record_builder.py`: FSM action → JSON record converter
- `tools/datagen/opal_export_trajectories.py`: Export with counterfactual labeling

#### 학습 / 평가
- `tools/training/run_trl_sft_public20.py`: TRL SFTTrainer launcher
- `tools/training/prepare_public20_sft_dataset.py`: SFT dataset converter
- `tools/eval/check_submit_package.py`: 제출 패키지 검증
- `tools/eval/prepare_submit.sh`: 제출 패키지 빌드

### 데이터
- `data/local/public20/`: 공개 20건 (reference)
- `data/local/gen_gflownet_v7/`: FSM-GFlowNet 생성 2104건 (현재 사용)
- `data/local/gen_sm/`: State Machine 생성 300건 (FSM-GFlowNet으로 대체)
- `data/local/gen_new/`: Self-Instruct 생성 (폐기, 참고용)

### 아카이브
- `runs/new_v2/opal_state_machine.py`: State Machine generator (FSM-GFlowNet으로 대체)
- `runs/new/`: Self-Instruct output-first pipeline (폐기)
- `runs/self_instruct/`: gen2/gen3/gen3.1 artifacts (폐기)
- `docs/archive/`: 과거 cycle 기록

## Spec Rules

`docs/legacy_spec_rules.md`에 86개 TCG/Opal spec rule 정의.
18개 카테고리: status codes, session, Get, Set, Authenticate, C_PIN, authority, lifecycle, locking, access control 등.
