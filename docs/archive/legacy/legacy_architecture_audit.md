# 아키텍처 감사: LLM-Only 전환 계획

일자: 2026-05-22
감사자: Claude Opus 4.6 (자동화 코드 감사)

---

## 1. 현재 코드 목록

### `src/` 내 소스 파일

| 파일 | 크기 | 역할 | 상태 |
|------|------|------|--------|
| `solver.py` | ~1278줄 | 규칙 엔진 (`StatefulOpalVerifier`) + `Solver` 클래스 (제출 진입점) | 주력 — 리더보드 73.00 |
| `lora_solver.py` | 324줄 | LoRA adapter 추론 (logit 비교 방식) | 보조 — `solver.py`의 Solver에서 로드 |
| `llm_solver.py` | 197줄 | Zero-shot 9B 생성 기반 solver | 보조 — `solver.py`의 Solver에서 로드 |
| `spec_solver.py` | 679줄 | 27B-FP8 logit solver (ACE 테이블 + 프로토콜 규칙을 프롬프트에 포함) | 독립형 LLM-only 후보 |
| `solver_27b.py` | 488줄 | 깔끔한 27B-FP8 logit solver (규칙 엔진 없음) | 독립형 LLM-only 후보 |
| `probe_solver.py` | 150줄 | Hidden state 추출 + 로지스틱 회귀 probe | 실험용, 미사용 |
| `__init__.py` | 1줄 | 빈 패키지 마커 | 해당 없음 |

### `tools/training/` 내 학습 스크립트

| 파일 | 역할 |
|------|------|
| `finetune_lora_v2.py` | LoRA SFT (rich format + label masking). `format_trajectory_rich()` 및 `format_for_training_v2()` 정의. 기본 학습 스크립트. |
| `train_wd.py` | Weight decay + label smoothing 변형. `finetune_lora_v2.py`의 import를 사용. mutation 데이터(470건)로 학습. |

### `tools/datagen/` 내 데이터 생성 스크립트

| 파일 | 역할 |
|------|------|
| `generate_mutations.py` | public 20으로부터 대조 쌍(contrastive pairs) 생성: 상태 코드 뒤집기, 절단, HostChallenge 손상 (~210-400건) |
| `generate_spec_data.py` | 21개 규칙에 걸쳐 ~3000건 이상의 합성 데이터 생성 (조합적 확장) |
| `generate_gap_data.py` | 9개 누락 카테고리 보충: SP_BUSY, AUTHORITY_LOCKED_OUT, Column ACL, Revert, Disabled auth, NO_SESSIONS, SP_FROZEN, Inactive SP, Timeout |

### `tools/eval/` 내 평가 스크립트

| 파일 | 역할 |
|------|------|
| `eval_lora.py` | public 20 + 합성 데이터에서 LoRA adapter 평가 (생성 모드 또는 logit 모드) |
| `eval_3adapters.py` | 3개 mutation adapter를 public 20에서 나란히 비교 |

---

## 2. 현재 코드 흐름 (End-to-End 평가)

### 2.1 제출 진입점

평가 하니스는 `src/solver.py :: Solver.predict(dataset)`를 호출한다.

```
dataset: list[dict]  →  각 항목은 {"id": str, "steps": list[dict]}
returns: dict[str, str]  →  {case_id: "pass" | "fail"}
```

### 2.2 현재 `Solver.__init__()` (solver.py, 1183-1215줄)

```python
class Solver:
    def __init__(self):
        self.verifier = StatefulOpalVerifier()   # 규칙 엔진
        self.lora_solver = None
        self.llm_solver = None
        # USE_LLM=1이면 LLMSolver (9B 생성) 로드 (기본값=1)
        # USE_LORA=1이고 LLM이 없으면 LoRASolver (4B logit) 로드 (기본값=0)
```

### 2.3 현재 `Solver.predict()` 흐름 (1217-1263줄)

```
각 케이스에 대해:
  1. 규칙 엔진: verifier.verify_with_trace(steps)
     → {prediction, trace} 반환
     → trace[-1]["rule_id"]로 어떤 규칙이 트리거됐는지 식별

  2. 규칙 신뢰도 분류:
     HIGH = PARSE_FINAL_COMMAND, PROPERTIES_*, STARTSESSION_FINAL,
            PRECONDITION_EXPECTED_ERROR, KNOWN_FIELD_INVALID_VALUE,
            LOCKING_DATA_ACCESS, ACTIVATE_TARGET
     LOW  = UNEXPECTED_ERROR_STATUS, DEFAULT_PASS, KNOWN_FIELD_EXPECTED_SUCCESS
     MEDIUM = 그 외 전부

  3. tier == LOW이고 LLM/LoRA 사용 가능하면:
     → LLM 생성 결과가 규칙 엔진 예측을 오버라이드
     → (LoRA: 임계값 기반 오버라이드)

  4. 그 외: 규칙 엔진 예측 유지
```

**핵심 관찰**: 규칙 엔진이 항상 먼저 실행된다. LLM은 LOW 신뢰도 케이스에만 참조된다. 이 아키텍처는 LLM의 영향력을 근본적으로 제한한다.

### 2.4 기존 LLM-Only 진입점 (이미 존재)

- **`solver_27b.py :: Solver`**: 깔끔한 LLM-only solver. 자체 `format_trajectory()`를 사용하며 Qwen3.5-27B-FP8에서 logit 비교를 수행한다. ACE 테이블 + 프로토콜 규칙이 시스템 프롬프트에 포함되어 있다. `predict(dataset) -> dict[str, str]`.

- **`spec_solver.py :: SpecSolver`**: solver_27b와 유사하나 더 풍부한 프롬프트 구조를 가진다. logit 및 생성 모드 모두 지원. `predict(dataset) -> dict[str, str]`.

두 solver 모두 올바른 제출 인터페이스 시그니처를 이미 갖추고 있다.

---

## 3. LLM-Only Solver에 필요한 것

### 3.1 입력 형식

평가 하니스가 제공하는 형식:
```python
dataset: list[dict]
# 각 항목: {"id": str, "steps": list[dict]}
# 각 step: {"input": {"method": {...}, "invoking_id": {...}, ...},
#           "output": {"status_codes": ..., "return_values": ..., ...}}
```

### 3.2 출력 형식

```python
dict[str, str]  # {case_id: "pass" | "fail"}
```

### 3.3 모델 로딩

- L40S 48GB에 사전 캐시된 모델: `Qwen/Qwen3.5-{0.8B, 2B, 4B, 9B, 27B-FP8}`
- LoRA adapter는 `artifacts/lora_adapter_v2` 또는 `artifacts/lora_adapter_v3`에서 로드
- 평가 중 네트워크 접근 불가
- 200개 케이스에 대해 3시간 시간 제한

### 3.4 시간 예산

| 접근법 | 모델 | 케이스당 시간 | 200건 | 실현 가능? |
|----------|-------|-----------|-----------|-----------|
| Logit 비교 | 4B + LoRA | ~0.5초 | ~2분 | 예 |
| Logit 비교 | 27B-FP8 | ~2.4초 | ~8분 | 예 |
| 생성 (no think) | 9B | ~7.5초 | ~25분 | 예 |
| 생성 (no think) | 27B-FP8 | ~27초 | ~90분 | 예 |
| 생성 (think) | 27B-FP8 | ~90초 | ~5시간 | 아니오 |

---

## 4. 재사용 가능한 것 vs. 재작성 필요한 것

### 4.1 그대로 재사용 가능

1. **`solver_27b.py`** — 이미 올바른 제출 인터페이스를 갖춘 완전한 LLM-only solver. 27B-FP8에서 logit 비교 사용. Zero-shot으로 public 15/20 (75%).

2. **`spec_solver.py`** — 또 다른 완전한 LLM-only solver. 더 풍부한 ACE 테이블과 프로토콜 규칙 포함. logit 및 생성 모드 모두 지원.

3. **`lora_solver.py :: format_trajectory_rich()`** — LoRA 학습에 사용된 trajectory 포맷팅 함수. `finetune_lora_v2.py`에도 중복 존재. mutation_4b adapter (85%)가 학습된 형식.

4. **`lora_solver.py :: LoRASolver`** — 4B + LoRA logit 비교. 보조가 아닌 주력 solver로 직접 사용 가능.

5. **학습 파이프라인** — `finetune_lora_v2.py`와 `train_wd.py`가 완전히 작동함. `format_for_training_v2()` 함수가 올바르게 구조화된 SFT 데이터를 생성.

6. **데이터 생성** — 3개 생성기(`generate_mutations.py`, `generate_spec_data.py`, `generate_gap_data.py`) 모두 규칙 엔진 지식을 인코딩하는 학습 데이터를 생성.

### 4.2 재작성 필요

1. **`src/solver.py :: Solver`** (제출 진입점) — 현재 규칙 엔진이 주력이고 LLM이 오버라이드하는 구조. LLM이 주력이 되고 추론 시 규칙 엔진이 실행되지 않도록 재작성 필요.

2. **형식 일관성** — 4가지 서로 다른 trajectory 포맷팅 함수가 존재:
   - `lora_solver.py :: format_trajectory_rich()` — 학습에 사용 (85% adapter)
   - `spec_solver.py :: format_trajectory()` — SpecSolver에서 사용 (다른 구조: 상단에 세션 상태, ">>>", "---" 구분자)
   - `solver_27b.py :: format_trajectory()` — Solver_27b에서 사용 (더 단순)
   - `llm_solver.py :: extract_relevant_steps()` + 원시 JSON dump — LLMSolver에서 사용

   **제출 solver는 반드시 adapter가 학습된 것과 동일한 형식을 사용해야 한다.** mutation_4b adapter의 경우 `lora_solver.py`/`finetune_lora_v2.py`의 `format_trajectory_rich()`이다.

3. **시스템 프롬프트 정렬** — 학습 시 사용된 프롬프트:
   ```
   "You are a TCG/Opal SSD protocol compliance verifier. Given a command-response
   trajectory with session state, determine if the final response is consistent
   with the specification. Answer exactly: pass or fail"
   ```
   LoRA adapter를 사용하는 경우 제출 solver도 반드시 이 동일한 시스템 프롬프트를 사용해야 한다.

### 4.3 삭제해야 할 것 (Dead Code)

- `probe_solver.py` — 실험용, 성과 없음.
- `solver.py :: Solver`의 규칙-엔진-주력 흐름 — 완전히 대체됨.
- `llm_solver.py` — Zero-shot 생성 접근법. 리더보드 개선 없음 (73.00 -> 73.00).

---

## 5. 필요한 정확한 변경 사항

### 5.1 새로운 `src/solver.py :: Solver` (최소 재작성)

`Solver` 클래스를 LLM-only로 재작성해야 한다. 두 가지 실현 가능한 아키텍처:

#### 옵션 A: 4B LoRA Logit (최고 기록: public 85%)

```python
class Solver:
    def __init__(self):
        # Qwen3.5-4B + LoRA adapter 로드
        # pass/fail에 대한 logit 비교
        # format_trajectory_rich() 사용 — 학습 형식과 일치해야 함

    def predict(self, dataset) -> dict[str, str]:
        # 각 케이스에 대해:
        #   1. 레코드 파싱
        #   2. format_trajectory_rich(records)
        #   3. 채팅 템플릿 적용 (system + user)
        #   4. 단일 forward pass
        #   5. logits[pass_id] vs logits[fail_id] 비교
        #   6. p_fail > threshold이면 "fail", 아니면 "pass" 반환
```

**시간 추정**: ~0.5초/케이스 x 200 = ~2분. 3시간 제한 내에서 충분.

**이미 존재하는 것**: `lora_solver.py :: LoRASolver.predict_prob()`가 정확히 이 작업을 수행. 새 `Solver`는 올바른 `predict(dataset)` 인터페이스로 감싸기만 하면 됨.

#### 옵션 B: 27B-FP8 Zero-Shot Logit (public 75%)

`solver_27b.py :: Solver`에 이미 완전히 구현되어 있음. `src/solver.py`에 제출용 `Solver`로 복사하면 됨.

#### 옵션 C: Multi-Adapter 앙상블 (미검증)

여러 LoRA adapter(mutation_4b, mutation_15ep, mutation_470)를 로드하여 logit을 평균. 모델 로드/언로드 또는 adapter 병합이 필요. 위험도 높지만 잠재력도 높음.

**권장사항**: 옵션 A. 4B LoRA adapter (mutation_4b)가 public 85%로 최고 기록. 코드가 이미 `lora_solver.py`에 존재하며 — `Solver` 래퍼만 재작성하면 됨.

### 5.2 옵션 A의 구체적 Diff

`src/solver.py :: Solver` 클래스(1183-1278줄)를 다음을 수행하는 새 클래스로 교체:

1. `__init__`에서: `artifacts/lora_adapter_v3` (또는 설정 가능한 경로)에서 Qwen3.5-4B base + LoRA adapter 로드
2. `predict(dataset)`에서: 케이스를 순회하며 `format_trajectory_rich()` 호출 후 logit 비교 수행
3. 추론 경로 어디에도 `StatefulOpalVerifier` 없음

`solver.py`에서 보존해야 할 핵심 함수:
- `StatefulOpalVerifier._records()` (566-574줄) — 원시 trajectory JSON을 dict 리스트로 파싱. 형식 정규화이지 규칙 로직이 아님.

새 Solver에 인라인해야 할 함수 (교차 모듈 의존성 방지):
- `lora_solver.py` 59-181줄의 `format_trajectory_rich()`
- `lora_solver.py` 36-56줄의 `_compact_json()`

### 5.3 Artifacts 디렉토리

제출 패키지에 필요한 것:
```
src/solver.py          # 새로운 LLM-only Solver
artifacts/
  lora_adapter_v3/     # LoRA adapter 가중치
    adapter_config.json
    adapter_model.safetensors
    tokenizer.json
    tokenizer_config.json
    ...
```

---

## 6. 규칙 엔진의 지식을 LLM이 학습하도록 학습 데이터를 구성하는 방법

### 6.1 현재 규칙 엔진의 지식 (solver.py, 1278줄)

규칙 엔진은 25개 이상의 규칙을 인코딩한다. 카테고리별 요약:

**세션 규칙** (603-645줄):
- StartSession은 세션을 생성하고, EndSession은 세션을 제거
- HostChallenge 존재 + 정상 형식 → 인증됨
- Write 플래그 → RW 또는 RO 세션

**전제조건 에러** (942-972줄):
- 세션 없음 + 메서드 → notauthorized
- 인증 없음 + 쓰기 메서드 → notauthorized
- RO 세션 + 쓰기 메서드 → notauthorized
- 유효하지 않은 cellblock → invalidparameter
- 중복 Set 컬럼 → invalidparameter
- 유효하지 않은 boolean 값 → invalidparameter
- 유효하지 않은 Activate 대상 → invalidparameter

**메서드별 검증** (712-940줄):
- Properties: Session Manager를 대상으로 해야 하며, payload 필요
- StartSession: SyncSession 응답 검증, HostSessionID 에코, 비밀번호 일치, SP_BUSY/FROZEN/NOSESSIONS 수용
- Set/GenKey/Activate/EndSession: SUCCESS 시 return_values가 비어있어야 함
- Read: 데이터 payload 검증, GenKey 효과 (이전 데이터 파괴)
- Write: DATA_COMMAND 구조 검증
- Get: 알려진 상태에 대한 컬럼 반환값 검증
- Authenticate: SUCCESS는 활성 세션 필요, result 필드
- Locking: 데이터 명령에 대한 ReadLocked/WriteLocked 적용

**포괄 규칙** (815-823줄, 939줄):
- UNEXPECTED_ERROR_STATUS: 설명되지 않는 비성공 응답 → fail (71.50의 핵심)
- DEFAULT_PASS: 그 외 → pass

### 6.2 지식 증류(Knowledge Distillation) 전략

규칙 엔진의 지식은 추론 코드가 아닌 학습 데이터로 증류되어야 한다. 3가지 데이터 소스가 이미 존재:

**소스 1: Mutation 데이터** (generate_mutations.py, ~210-470건)
- public 20 테스트 케이스에서 생성
- 실제 테스트 데이터와 길이 분포가 일치 (중앙값 10.5 step)
- 대조 쌍 (상태 코드 뒤집기, 절단, HostChallenge 손상)
- **85% adapter가 학습한 데이터가 바로 이것**

**소스 2: Spec 기반 합성 데이터** (generate_spec_data.py, ~3000건 이상)
- 21개 규칙 카테고리 커버
- 조합적 확장 (모든 객체 x 모든 에러 x 모든 컬럼 조합)
- 짧은 trajectory (1-2 step)
- **문제: 테스트 데이터와 길이 불일치 (94% 짧음, 테스트 60% 김)**

**소스 3: Gap 데이터** (generate_gap_data.py, ~300건)
- spec 데이터에서 누락된 9개 카테고리 커버
- SP_BUSY, AUTHORITY_LOCKED_OUT, Column ACL, Revert 등
- 짧은 trajectory

### 6.3 누락된 것: UNEXPECTED_ERROR_STATUS 규칙을 위한 데이터

가장 중요한 단일 규칙 엔진 동작은 UNEXPECTED_ERROR_STATUS: "응답이 비성공 상태인데 어떤 특정 규칙도 이를 설명하지 못하면, fail이다."

현재 학습 데이터는 이것을 명시적으로 가르치지 않는다. 85% adapter는 mutation 데이터의 대조 쌍에서 이를 암묵적으로 학습했지만, 불완전하게 학습했다 (public 20에서 3건 오류).

**필요한 것**: 다음과 같은 추가 학습 케이스:
- 인증된 세션 + 쓰기 가능한 것으로 알려진 컬럼 + Set → SUCCESS (pass)
- 동일 설정인데 ACL 제한이 없는 상황에서 → NOT_AUTHORIZED (fail)
- 동일 설정인데 성공이 예상되는 상황에서 → FAIL (fail)

이 케이스들은 LLM에게 "프로토콜상 성공해야 하는데 성공하지 않으면, 그것은 fail"이라는 것을 가르친다.

### 6.4 권장 데이터 파이프라인

```
단계 1: 기존 데이터 결합
  mutation_cases.json (~210-470)     # 실제 분포
  + gap_cases.json (~300)            # 누락 카테고리
  + spec_train.json (~1800 of 3000)  # 조합적 커버리지

단계 2: UNEXPECTED_ERROR_STATUS 케이스 추가
  각 규칙 엔진 HIGH 신뢰도 규칙에 대해:
    정답이 fail인 N개 케이스 생성
    (응답이 규칙이 예상하는 것을 위반하기 때문)

단계 3: Type B 탐지 케이스 추가 (public 3건 오류)
  tc14: HostChallenge 존재 vs 부재 → 다른 예상 상태
  tc15: 잘못된 UID 대상 → INVALID_PARAMETER
  tc20: Read 데이터가 기록된 패턴과 일치 → pass; 다른 데이터 → fail

단계 4: 학습
  모델: Qwen3.5-4B
  형식: format_for_training_v2() (chat template + label masking)
  하이퍼파라미터: lr=1e-3, rank=16, 5 epochs, bs=2, grad_accum=4
  최대 시퀀스 길이: 2048 (전체 trajectory 포착)
```

---

## 7. 위험 평가

### 7.1 규칙 엔진이 잡아내는데 LLM이 놓칠 수 있는 것

| 규칙 | 규칙 엔진 동작 | LLM 위험 | 완화 방안 |
|------|---------------------|----------|------------|
| PARSE_FINAL_COMMAND | 메서드/상태 없음 → fail | 낮음 — 명확한 패턴 | 학습 데이터에 빈/비정상 케이스 포함 |
| PROPERTIES_TARGET | 잘못된 invoking → fail | 중간 — 미묘한 UID 검사 | 잘못된 UID가 포함된 명시적 학습 케이스 필요 |
| STARTSESSION_FINAL | SyncSession 검증, 세션 ID 에코 | **높음** — 다중 필드 구조 검사 | 불일치하는 세션 ID를 가진 학습 케이스 필요 |
| PRECONDITION_EXPECTED_ERROR | 세션/인증/RO 없음 → 에러 예상 | 낮음 — 학습 데이터에서 잘 커버됨 | Spec 데이터 + gap 데이터로 커버 |
| UNEXPECTED_ERROR_STATUS | 설명되지 않는 에러 → fail | **치명적** — hidden 57건 중 25-35건에 해당 | 명시적 학습 데이터 필수 |
| LOCKING_DATA_ACCESS | ReadLocked/WriteLocked 적용 | 중간 — 다중 step 상태 추적 필요 | 잠금 상태 변경이 포함된 학습 케이스 필요 |
| READ_PAYLOAD | GenKey가 이전 데이터 파괴 | 중간 — 인과 관계 이해 필요 | Mutation 데이터가 Write→GenKey→Read 패턴 커버 |
| KNOWN_FIELD_INVALID_VALUE | 유효하지 않은 boolean → INVALID_PARAMETER | 낮음 — 잘 정의된 패턴 | Spec 데이터로 커버 |
| Column ACL (현재 규칙 엔진에 없음) | 해당 없음 | LLM이 여기서 유리 — 학습 데이터가 규칙 엔진이 처리할 수 없는 ACL 패턴을 가르침 | Gap 데이터 + spec 데이터 |

### 7.2 회귀 위험

**시나리오**: 최고 규칙 엔진(73.00)은 ~146/200건을 정확히 분류한다. 최고 LLM(public 85%, hidden 미지)은 public 결과가 일반화되면 170/200을 맞힐 수 있지만, public에 과적합되었다면 130/200으로 회귀할 수 있다.

**완화 방안**:
- 85% 결과는 public 케이스에서 파생된 mutation 데이터를 사용했다. Hidden 케이스도 유사한 패턴을 따른다.
- mutation + spec + gap 결합 데이터로 학습하면 더 넓은 커버리지 제공.
- Logit 비교는 충분히 빨라서 필요 시 여러 adapter를 시도할 수 있다.

### 7.3 알려진 실패 모드

1. **Type B 에러** (데이터 수준 차이): public 3건 오류(tc14, tc15, tc20)는 상태 코드 패턴이 아닌 미묘한 값 차이(HostChallenge, UID, Read 데이터)와 관련된다. Logit 비교는 이를 구별하는 데 제한이 있다:
   - trajectory 텍스트가 길다 (800-2000 토큰)
   - 구별 정보가 작은 부분 문자열이다
   - 마지막 위치의 logit이 전체 컨텍스트에 걸쳐 집계된다

2. **긴 trajectory 절단**: max_length=2048에서 일부 케이스가 절단될 수 있다. `extract_relevant_steps()` 필터가 이를 완화하지만 관련 컨텍스트를 누락시킬 수 있다.

3. **과신(Overconfidence)**: LoRA 모델은 극단적인 logit을 생성하는 경향이 있다 (p_fail이 0 또는 1에 매우 가까움). `train_wd.py`의 label smoothing (0.1)과 weight decay (0.05)가 이를 부분적으로 해결한다.

### 7.4 점수 예측

| 시나리오 | Public 20 | Hidden 200 (추정) | 비고 |
|----------|-----------|----------------------|-------|
| 규칙 엔진 단독 | 20/20 (100%) | 146/200 (73.0%) | 현재 기준선 |
| 4B LoRA mutation_4b | 17/20 (85%) | ??? | 최고 LLM, hidden 미검증 |
| 4B LoRA + 강화된 데이터 | 18-19/20 | 150-160/200 (75-80%) | 더 나은 학습 데이터 시 낙관적 |
| 27B-FP8 zero-shot | 15/20 (75%) | 140-150/200 (70-75%) | 학습 데이터 불필요 |

---

## 8. 구현 계획 (우선순위 순)

### 단계 1: 최소 실행 가능 LLM-Only Solver (30분)

`src/solver.py :: Solver`를 4B LoRA를 직접 사용하도록 재작성. `format_trajectory_rich()`와 trajectory 파싱을 인라인. 추론 시 규칙 엔진 없음. 기존 `lora_adapter_v3` (mutation_4b) 사용.

### 단계 2: 제출 및 측정 (5분)

LLM-only solver를 제출하여 hidden 세트 점수 확인. 이것이 핵심 데이터 포인트.

### 단계 3: 강화된 학습 데이터 (2-4시간)

단계 2 점수 < 73.00인 경우:
- UNEXPECTED_ERROR_STATUS 학습 케이스 추가
- Type B 탐지 학습 케이스 추가 (HostChallenge, UID, 데이터 값 비교)
- 결합 데이터로 재학습
- 재제출

단계 2 점수 >= 73.00인 경우:
- 학습 데이터를 반복 개선하여 점수 상승 추구
- 어려운 케이스에 생성 모드 시도 (느리지만 더 많은 추론)
- 9B base 모델 시도 (더 큰 용량, 48GB에서 LoRA와 함께 적재 가능)

### 단계 4: Zero-Shot Fallback을 위한 프롬프트 엔지니어링 (1-2시간)

`solver_27b.py` / `spec_solver.py`의 시스템 프롬프트 개선:
- UNEXPECTED_ERROR_STATUS 휴리스틱을 명시적 규칙으로 프롬프트에 추가
- Type B 탐지 규칙 추가
- public 20에서 테스트

---

## 9. 파일 경로 요약

### 수정해야 할 핵심 파일:
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/src/solver.py` — `Solver` 클래스 재작성

### 참조해야 할 파일 (포맷팅이 학습과 일치해야 함):
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/src/lora_solver.py` — `format_trajectory_rich()`, `LoRASolver`
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/training/finetune_lora_v2.py` — `format_for_training_v2()`

### 기존 LLM-only solver (바로 사용 가능):
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/src/solver_27b.py` — 27B zero-shot (public 75%)
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/src/spec_solver.py` — 27B + 풍부한 spec 프롬프트

### 학습 스크립트:
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/training/train_wd.py` — 최신 학습 설정
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/training/finetune_lora_v2.py` — 기본 학습 스크립트

### 데이터 생성 스크립트:
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/datagen/generate_mutations.py` — Mutation 데이터 (최고 결과)
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/datagen/generate_spec_data.py` — Spec 기반 합성
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/datagen/generate_gap_data.py` — Gap 카테고리

### 평가 스크립트:
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/eval/eval_lora.py` — LoRA 평가
- `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team/tools/eval/eval_3adapters.py` — 다중 adapter 비교
