<!-- Changed: update handoff to reflect LoRA override architecture and current project state. -->
<!-- Why: RAG hybrid is no longer used. Architecture is rule engine (71.50 base) + LoRA override. -->

# Legacy Handoff - 현재 사용 금지

이 파일은 2026-05-19 기준 과거 handoff 기록이다. 현재 architecture, 서버 root, 제출 판단 기준으로 사용하지 않는다.

- 현재 handoff: [current_task.md](current_task.md)
- 현재 서버 운영: [../server_operations_current.md](../server_operations_current.md)
- 현재 원칙: LLM-only architecture. rule engine + LoRA override는 과거 접근이다.

# TODO / Handoff

작성일: 2026-05-19

## 프로젝트 한 줄 요약

SSD TCG/Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 부합하는지 `pass`/`fail`로 판정하는 과제다. 현재 접근은 **rule engine (71.50 base, UNEXPECTED_ERROR_STATUS) + LoRA fine-tuned override**: 규칙 엔진이 unexplained error를 aggressive하게 fail로 판정하고, LoRA adapter가 false positive를 rescue한다.

## 현재 저장소 상태

- Local path: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`
- GitHub: `https://github.com/tongtongblueberry/team6-opal-verifier`
- Main branch: `main`
- Best branch: `best-71.50` (commit `2df1e71`, 안전한 제출 코드)
- Server clone path used: `/workspace/team6/team6-opal-verifier`
- Clean submission paths used: `/workspace/team6/submission-<commit>`
- Server non-secret access memo: `server_access.md`
- 비밀번호와 token은 저장소에 저장하지 않는다.

## 현재 성능

- Best leaderboard score: **71.50** (pure rule engine, commit `2df1e71`, branch `best-71.50`)
- Latest submissions:
  - Job 185: 68.00 (post-71.50 rule engine changes caused regression)
  - Job 186: 68.00 (embedding classifier -- regression)
  - Job 187: 71.50 (revert to best-71.50 confirmed)
  - Job 188: 71.50 (auth rule addition on 71.50 base)
- LoRA 4B v2 (synthetic test set): fail precision 100%, fail recall 46.9%, accuracy 89.7%
- HP sweep: currently running on server

### CRITICAL: 71.50 base만 사용

- Post-71.50 rule engine 변경은 **3.5점 regression** 유발 (71.50 -> 68.00)
- 핵심 차이: `UNEXPECTED_ERROR_STATUS` (모든 unexplained error -> fail) vs `DEFAULT_PASS` (-> pass)
- 71.50의 aggressive 접근이 hidden test에서 더 정확
- 이후 모든 작업은 `best-71.50` branch를 base로 사용

### 아키텍처: Rule Engine + LoRA Override

```
Input trajectory
       |
[1] Rule Engine (StatefulOpalVerifier.verify_with_trace)
       |
  prediction + rule_id
       |
  rule_id == UNEXPECTED_ERROR_STATUS?
       NO  -> rule prediction 그대로 사용 (high confidence)
       YES -> LoRA 4B override 적용
              |
[2] Qwen3.5-4B + LoRA adapter (artifacts/lora_adapter_v2/)
       |
  LoRA says "pass" -> override to pass (rescue false positive)
  LoRA says "fail" -> keep fail
```

### LoRA 4B v2 결과 (synthetic test set, 252 cases)

| Metric | 값 |
|--------|---|
| Accuracy | 89.7% |
| Fail Precision | 100% |
| Fail Recall | 46.9% |
| False Positives (pass->fail) | 0 |
| False Negatives (fail->pass) | 26/49 |

### 목표

| Metric | 현재 | 목표 | 근거 |
|--------|------|------|------|
| Leaderboard Accuracy | 71.50 | >= 85.00 | LoRA가 UNEXPECTED_ERROR_STATUS FP를 ~50% 제거하면 +7~14점 |
| Fail Precision | 100% | >= 90% | FP 방지가 핵심 -- rule engine이 맞춘 것을 뒤집으면 안 됨 |
| Fail Recall | 46.9% | >= 70% | HP sweep + 50-epoch 학습으로 향상 기대 |

## 중요한 해석

- **UNEXPECTED_ERROR_STATUS가 71.50의 핵심**: 모든 unexplained error를 fail로 판정하는 aggressive 규칙이 hidden test에서 정확
- **LoRA의 역할은 false positive rescue**: rule engine이 "fail"이라고 한 것 중 실제로는 "pass"인 case를 LoRA가 교정
- **Post-71.50 regression 원인 확정**: UNEXPECTED_ERROR_STATUS를 DEFAULT_PASS로 변경한 것이 3.5점 하락의 원인
- Public 100점은 hidden 일반화를 보장하지 않는다

## 주요 파일

- `src/solver.py`: 제출 solver. Rule engine (best-71.50 base) + LoRA override
- `src/lora_solver.py`: LoRA model loading and prediction
- `src/rag.py`: BM25 retrieval + LLM judge (legacy, 제출에 미사용)
- `tools/finetune_lora_v2.py`: 4B LoRA training (rich format + label masking)
- `tools/sweep_lora.py`: HP sweep script (LR, rank, alpha, dropout, max_length, batch)
- `tools/eval_lora.py`: LoRA evaluation
- `tools/intermediate_eval.py`: public train/dev 중간평가 도구
- `tools/mutation_eval.py`: mutation testing adequacy framework
- `artifacts/lora_adapter_v2/`: 4B LoRA adapter (~32MB)
- `docs/submission_log.md`: commit-level leaderboard 기록
- `docs/sweep_plan.md`: HP sweep 계획 및 architecture 상세
- `docs/rag_cycle_log.md`: RAG 실험 Cycle 1-10 상세 기록 (legacy)
- `docs/current_task.md`: 세션 이어받기용 상태 문서

## 이미 해결한 문제

- 공식 evaluator가 `Solver` class를 요구한다는 점 반영.
- `HostSessionID`, `SPSessionID` session id parser 보강.
- `HostChallenge`를 PIN 원문과 비교하던 잘못된 rule 제거.
- DATA_COMMAND `Read/Write`와 TCG method precondition 분리.
- `Write`의 `pattern` payload parser 추가.
- `Activate` 대상 SP UID 검증 추가.
- `Set`이 쓴 object column 값을 `object_fields`로 추적하고, `Get` payload를 requested column/known field와 비교.
- DATA_COMMAND `Read` 결과에서 old pattern visibility를 정규화해 검사.
- invalid `Get` Cellblock range에 대해 expected `INVALID_PARAMETER` rule 추가.
- Locking ReadLocked/WriteLocked DATA_COMMAND 접근 제어 추가 (71.50의 핵심 규칙).
- C_PIN secret tracking -> StartSession authentication 연결.
- Mutation testing framework (MS=1.0, 11/11 killed).
- RAG hybrid solver 구현 (legacy, 현재 LoRA override로 전환).
- LoRA 4B v2 fine-tuning (fail precision 100%, fail recall 46.9%).
- Regression 원인 확정: UNEXPECTED_ERROR_STATUS -> DEFAULT_PASS 변경이 원인.

## 제출 이력 요약

| Commit | Key change | Leaderboard |
|---|---|---|
| `872f31d` | initial state verifier | 60.50 |
| `fd43bd5` | spec index, coverage, Get field/data rules | 68.00 |
| `0c5e6d8` | metamorphic/property diagnostics, GenKey empty result | 68.00 |
| `bf6c40b` | C_PIN secret tracking for StartSession | 69.00 |
| `bcfdc94` | Set duplicate column and empty result | 69.00 |
| `fc0289e` | latest submitted docs/code after daily limit | 69.00 |
| `67cd09d` | method-specific coverage gaps closed | 69.50 |
| `c613397` | known field semantics and low-confidence removal | 69.50 |
| `41b4df6` | Ba et al. 2025 MC metric/architecture applied | 69.50 |
| `2df1e71` | Locking ReadLocked/WriteLocked rules | **71.50** (best) |
| Job 185 | post-71.50 rule changes (regression) | 68.00 |
| Job 186 | embedding classifier (regression) | 68.00 |
| Job 187 | revert to best-71.50 | 71.50 |
| Job 188 | auth rule on 71.50 base | 71.50 |

## 빠른 검증 명령

로컬:

```bash
bash setup.sh
python3 -m compileall src tools
```

서버 public 중간평가:

```bash
python3 tools/intermediate_eval.py --dataset-root /dl2026/dataset
```

LoRA HP sweep:

```bash
nohup python3 tools/sweep_lora.py > /workspace/team6/sweep.log 2>&1 &
tail -30 /workspace/team6/sweep.log  # 진행 확인
```

LoRA 본 학습 (50 epochs, sweep 완료 후):

```bash
nohup python3 tools/sweep_lora.py --main > /workspace/team6/main_train.log 2>&1 &
```

제출:

```bash
mkdir -p /workspace/team6/submission-<commit>
git archive -o /workspace/team6/submission-<commit>.tar HEAD
tar -xf /workspace/team6/submission-<commit>.tar -C /workspace/team6/submission-<commit>
submit -d /workspace/team6/submission-<commit> -n team6-lora-<commit>
submit --list
```

## 다음 TODO

### 즉시 (우선순위 순)

1. **HP sweep 완료 대기** -- 서버에서 `tools/sweep_lora.py` 실행 중 (26 runs, 각 ~56분)
2. **Sweep best config로 50-epoch 본 학습** -- best (LR + rank + alpha + dropout + max_length + batch) 조합
3. **Synthetic test set에서 검증** -- fail precision >= 90%, fail recall 최대화
4. **Leaderboard 제출** -- 확실히 개선될 때만 (일일 한도 제한)

### 중기

5. **9B model로 확인** -- 4B vs 9B 비교 (같은 best config)
6. **Rule engine 자체 확장** (71.50 base에서 안전한 규칙만)
   - Set NOT_AUTHORIZED (column-level ACL) -- 10-20 hidden cases 추정
   - Class authority INVALID_PARAMETER -- 5-15 cases
   - Get silent column omit -- 5-15 cases
   - Authenticate rules -- 5-10 cases
   - SP_BUSY session exclusivity -- 5-10 cases
7. **LoRA training data 개선** -- hidden distribution에 더 가까운 synthetic data 생성

### 장기

8. **Spec mining으로 새 rule 발견** -- LLM이 spec을 읽고 미구현 규칙 제안
9. **Multi-LoRA ensemble** -- 여러 adapter의 판정을 결합
10. **제출 로그 원칙 유지** -- leaderboard 결과는 commit-level score만 기록
