# OPAL State Machine Data Generator v2

## 접근법

Self-Instruct가 실패한 근본 원인 (LLM이 state-changing trajectory를 생성 불가)을 해결하기 위해,
Deterministic EFSM (Extended Finite State Machine) + Counterfactual Mutation 방식으로 전환.

논문 근거:
- Kalaji et al. (2021): EFSM based protocol test generation
- SynthDST (EACL 2024): template + schema > LLM free generation
- Kaushik et al. (ICLR 2020): Counterfactual Data Augmentation → OOD generalization

## 핵심 설계

1. **State Machine**: OPAL protocol의 Phase Progression (P0-P6)을 Python으로 구현
2. **Pass trajectory**: State machine을 따라 valid trajectory를 deterministic 생성
3. **Fail mutation**: Pass trajectory에 minimal counterfactual edit → fail
4. **Label**: Deterministic (state machine이 oracle)

## Phase Progression (public20 분석 기반)

| Phase | 내용 | Records |
|-------|------|---------|
| P0 | Properties | 1 |
| P1 | Admin SP no-auth → Read MSID | 2 |
| P2 | SID auth → Set password → re-auth | 7 |
| P3 | SID auth → Get SP → Activate → Locking SP auth | 11 |
| P4 | Read LockingInfo, MBRControl, Locking | 18-21 |
| P4a | Authority.Set (enable User1) | 21 |
| P5 | MBR config + verify | 27 |
| P5a | User1 password set + User1 auth | 26 |
| P6 | GenKey | 33 |
| P6io | Full I/O (Write/Read/ReKey/Read) | 46 |

## Mutation Types

| Type | 비율 | 방법 |
|------|------|------|
| A: Status code flip | 70% | SUCCESS ↔ NOT_AUTHORIZED/INVALID_PARAMETER/FAIL/SP_BUSY/SP_FROZEN/NO_SESSIONS |
| B: Value corruption | 20% | Fake HostChallenge, plaintext Read |
| C: Structural | 10% | Wrong SP UID, truncation |

## 사용법

```bash
python3 runs/new_v2/opal_state_machine.py --variants 15 --output-dir data/local/gen_sm
```

## 생성 결과

- 300건 (pass 150, fail 150)
- 11 unique sequence patterns
- 11종 record count (1-46)
- Label 정확도 100%
- State-building 76%

## 제출 결과

- Job 903: Score **53.00** (이전 best 54.00 대비 -1)
