# Leaderboard 제출 가이드 (project.pdf 기준)

- 작성일: 2026-05-28 KST
- 출처: `project.pdf.pdf` (Section 5, 6)

---

## 1. 제출 명령어 (서버에서 실행)

```bash
# 기본: 현재 디렉토리 제출
submit

# 특정 디렉토리 제출
submit --dir <제출_디렉토리>

# 이름 붙여서 제출
submit --job-name <이름>

# 디렉토리 + 이름
submit --dir <제출_디렉토리> --job-name <이름>

# 제출 이력 확인
submit --list
```

---

## 2. 필수 제출 파일

```
제출_디렉토리/
├── src/                    # [필수] solver 코드
│   ├── __init__.py         # [필수] Solver 클래스 export
│   └── solver.py           # [필수] class Solver + def predict()
├── setup.sh                # [필수] 환경 준비 스크립트
├── pyproject.toml          # [필수] Python 의존성 정의
├── uv.lock                 # [필수] 의존성 lock 파일
└── artifacts/              # [선택이지만 모델 쓰면 사실상 필수]
    └── merged_model/       #   full FT 모델 가중치
        ├── config.json
        ├── model*.safetensors
        ├── tokenizer.json
        └── tokenizer_config.json
    (또는)
    └── lora_adapter*/      #   LoRA adapter 가중치
        ├── adapter_config.json
        └── adapter_model.safetensors
```

**하나라도 빠지면 reject되거나 평가 실패한다.**

---

## 3. 각 파일에 들어가야 하는 내용

### 3-1. `src/solver.py`

평가 서버의 evaluator가 호출하는 핵심 파일.

**반드시 있어야 하는 것:**
- `class Solver` — 클래스 정의
- `def predict(dataset) -> list[str]` — 모듈 레벨 함수
  - input: trajectory dataset (dict 또는 list)
  - output: `["pass", "fail", "pass", ...]` 형태의 문자열 리스트
- 모델 로드 코드 — `artifacts/merged_model/` 또는 `artifacts/lora_adapter*/`에서 로드
- HF offline 대응 — `local_files_only=True` 처리 (평가 시 네트워크 차단됨)

**절대 넣으면 안 되는 것:**
- rule engine 코드 (`StatefulOpalVerifier`, `_init_rule_engine`, `rule_id` 등)
- 평가 서버에 없는 외부 파일 의존 (네트워크 차단 상태에서 다운로드 불가)

### 3-2. `src/__init__.py`

```python
from .solver import Solver, predict, predict_one
__all__ = ["Solver", "predict", "predict_one"]
```

evaluator가 `from src import Solver` 또는 `from src.solver import predict`로 접근한다.

### 3-3. `setup.sh`

평가의 **Setup phase**에서 실행. 이때만 네트워크 접근 가능.

**반드시 넣어야 하는 것:**
- HuggingFace 환경변수 export 4개:
  ```bash
  export HF_HOME=...
  export HF_HUB_CACHE=...
  export HF_HUB_OFFLINE=...
  export TRANSFORMERS_OFFLINE=...
  ```
- 추가 패키지 설치 (예: `pip install peft`)
- import smoke test (`from src import solver`가 되는지 확인)

**주의:**
- 시간 제한 **20분**. 대형 모델 다운로드 시 시간 초과 주의.
- `setup.sh`에서 설정한 환경변수가 evaluation phase까지 유지되는지 확인.

### 3-4. `pyproject.toml`

```toml
[project]
name = "team6-opal-verifier"
version = "0.1.0"
requires-python = "==3.12.3"
dependencies = [
    "accelerate>=1.13.0",
    "torch>=2.11.0",
    "transformers>=5.7.0",
    "peft>=0.15.0",
]
```

평가 서버가 `uv sync`로 `.venv/`를 만들 때 사용한다.

### 3-5. `uv.lock`

`pyproject.toml`과 쌍. 없으면 의존성 재현 실패할 수 있다.
로컬에서 `uv lock`으로 생성.

### 3-6. `artifacts/` (모델 가중치)

- **Full FT 모델**: `artifacts/merged_model/` 아래에 `config.json`, `model*.safetensors`, tokenizer 파일
- **LoRA adapter**: `artifacts/lora_adapter*/` 아래에 `adapter_config.json`, `adapter_model.safetensors`
- solver.py가 `artifacts/merged_model/config.json` 존재 여부로 full model vs LoRA를 자동 판별

---

## 4. 평가 프로세스

| 단계 | 내용 | 네트워크 | 시간 제한 |
|---|---|---|---|
| **Setup phase** | `setup.sh` 실행 | **가능** | **20분** |
| **Evaluation phase** | evaluator가 predict() 호출 | **불가** | **3시간** |

**어느 단계든 시간 초과 시 0점.**

---

## 5. 핵심 제약 — 실수하면 0점

### 5-1. 파일 크기 12GB 초과 → reject
- 제출 archive 전체가 12GB를 넘으면 서버가 거부한다.
- 현재 우리 0.9B full FT 패키지는 ~3.4GB로 OK.
- 4B 이상 모델은 크기 주의.

### 5-2. Evaluation phase에서 네트워크 차단
- 모델 다운로드 불가. `artifacts/`에 포함하거나 `setup.sh`에서 미리 받아야 한다.
- `from_pretrained("Qwen/Qwen3.5-0.8B")` 같은 호출은 캐시에 있어야만 동작.

### 5-3. 평가 서버에 사전 캐시된 모델 (이것만 네트워크 없이 사용 가능)
```
Qwen/Qwen3.5-0.8B
Qwen/Qwen3.5-2B
Qwen/Qwen3.5-4B
Qwen/Qwen3.5-9B
Qwen/Qwen3.5-27B-FP8
Qwen/Qwen3.5-35B-A3B-FP8
google/gemma-4-E2B-it
google/gemma-4-E4B-it
google/gemma-4-31B-it
google/gemma-4-26B-A4B-it
openai/gpt-oss-20b
```
이 목록에 없는 모델은 `artifacts/`에 직접 넣거나 `setup.sh`에서 다운로드해야 한다.

### 5-4. 1팀 동시 1job
- 이전 제출이 queue/running이면 새 제출 reject.
- `submit --list`로 이전 job 상태 확인 후 제출.

### 5-5. 최종 평가는 private dataset
- leaderboard에 없는 시나리오 포함.
- public score에 과적합하면 private에서 떨어진다.
- black-box optimization 금지 (명시적으로 경고됨).

---

## 6. 제출 전 로컬 검증 체크리스트

서버에서 제출하기 전에 반드시 확인:

```bash
# 1. 패키지 빌드 (서버에서)
bash tools/eval/prepare_submit.sh <모델_경로> --full-model

# 2. 정적 검증
python3 tools/eval/check_submit_package.py <패키지_디렉토리>

# 3. 오프라인 런타임 검증
python3 tools/eval/runtime_smoke_submit_package.py --offline --first-forward <패키지_디렉토리>

# 4. 로컬 평가 (서버 /workspace/project에서)
cd /workspace/project
bash setup.sh
python evaluate.py
```

**모든 검증 통과 후에만 submit.**

---

## 7. 흔한 실수 목록

| 실수 | 결과 |
|---|---|
| `setup.sh`에서 HF 환경변수 export 빠짐 | 모델 로드 실패, 0점 |
| `uv.lock` 안 넣음 | 의존성 설치 실패 |
| `src/__init__.py` 안 넣음 | `from src import Solver` 실패 |
| `artifacts/` 안에 모델 안 넣음 | inference 불가, 0점 |
| 12GB 초과 | 제출 자체가 reject |
| `setup.sh`에서 20분 초과하는 작업 | 0점 |
| Evaluation phase에서 네트워크 호출 | timeout/실패, 0점 |
| solver.py에 rule engine 코드 남김 | 우리 내부 정책 위반 (no-rule gate fail) |
| 이전 job running 상태에서 재제출 | reject |
| predict()가 list[str] 아닌 것 반환 | 평가 실패 |

---

## 8. 우리 현재 제출 현황

<!-- Changed: add latest generated-data status to the submission guide. -->
<!-- Why: the stopped gen3.1 pending row must not be mistaken for a new submission/training candidate. -->

Current generated-data status as of `2026-05-29 14:13:39 KST`: gen3.1 Qwen Self-Instruct generation was stopped at server raw `72/1000`. Local validation has pending accepted `1` row in `data/local/gen3_pending`, but canonical `data/local/gen3` has `0` rows. This does not change the current submitted model and is not a submission candidate.

| 항목 | 상태 |
|---|---|
| 제출 모델 | 0.9B Qwen3.5-0.8B full FT e30 seed11 |
| 패키지 크기 | 3.43 GB |
| Job ID | 668 |
| Submission ID | 5bcc1bdda5e347d499aa99adbb2ba2ee |
| 제출 시각 | 2026-05-27 23:41 KST |
| 서버 checkpoint | `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0716_KST_public20_trl_10_10_09b_fullft_maxlen8192/models/plain_seed11_e30` |
| 패키지 경로 | `/workspace/sinjeongmin_opal_verifier/ops/submission_worker_20260527_2317_KST_leaderboard_seed11_e30/submissions/submit-plain_seed11_e30` |
