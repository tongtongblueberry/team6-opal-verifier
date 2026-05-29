#!/usr/bin/env bash
# Changed: adapter 또는 full-model 경로를 인자로 받아 제출 패키지를 빌드하는 스크립트.
# Why: full fine-tuning 제출은 package-local artifacts/merged_model/에 standalone model directory를 넣어야 함.
#
# 사용법:
#   bash tools/eval/prepare_submit.sh /workspace/sinjeongmin_opal_verifier/adapters/exp_a/checkpoints/checkpoint-189
#   bash tools/eval/prepare_submit.sh /workspace/sinjeongmin_opal_verifier/ops/runs/.../models/plain_seed11_e30 --full-model
#   bash tools/eval/prepare_submit.sh /workspace/sinjeongmin_opal_verifier/adapters/exp_a/checkpoints/checkpoint-189 --submit
#   bash tools/eval/prepare_submit.sh /workspace/sinjeongmin_opal_verifier/adapters/exp_a/checkpoints/checkpoint-189 --name my-run
#
# 필수 조건:
#   - 서버에서 실행 (평가 환경 아님)
#   - adapter_config.json이 있는 유효한 adapter 경로 또는 config.json+weights+tokenizer가 있는 full-model 경로
#   - git repo 안에서 실행하거나 OPAL_REPO를 지정
set -euo pipefail

# ============================================================
# 인자 파싱
# ============================================================
# Changed: keep the positional artifact generic, then infer LoRA vs merged full-model mode.
# Why: one package builder must support both legacy LoRA submissions and current full FT submissions.
ARTIFACT_PATH=""
ARTIFACT_KIND="auto"
DO_SUBMIT=false
JOB_NAME=""

for arg in "$@"; do
    case "$arg" in
        --submit) DO_SUBMIT=true ;;
        --full-model|--merged-model) ARTIFACT_KIND="full_model" ;;
        --lora|--adapter|--lora-adapter) ARTIFACT_KIND="lora_adapter" ;;
        --name)   shift_next=true ;;
        --name=*) JOB_NAME="${arg#--name=}" ;;
        *)
            if [ "${shift_next:-false}" = true ]; then
                JOB_NAME="$arg"
                shift_next=false
            elif [ -z "$ARTIFACT_PATH" ]; then
                ARTIFACT_PATH="$arg"
            fi
            ;;
    esac
done

if [ -z "$ARTIFACT_PATH" ]; then
    echo "ERROR: artifact 경로가 필요합니다."
    echo ""
    echo "사용법: $0 <artifact_path> [--full-model|--lora-adapter] [--submit] [--name <job_name>]"
    echo ""
    echo "예시:"
    echo "  $0 /workspace/sinjeongmin_opal_verifier/adapters/exp_a/checkpoints/checkpoint-189"
    echo "  $0 /workspace/sinjeongmin_opal_verifier/ops/runs/.../models/plain_seed11_e30 --full-model"
    echo "  $0 /workspace/sinjeongmin_opal_verifier/adapters/best_adapter --submit --name lora-v3-best"
    exit 1
fi

# artifact 경로 유효성 검사
if [ ! -d "$ARTIFACT_PATH" ]; then
    echo "ERROR: artifact 경로가 존재하지 않음: $ARTIFACT_PATH"
    exit 1
fi

# Changed: detect the artifact family before package layout validation.
# Why: full FT checkpoints have config.json/model weights, while LoRA adapters have adapter_config.json.
if [ "$ARTIFACT_KIND" = "auto" ]; then
    if [ -f "$ARTIFACT_PATH/adapter_config.json" ]; then
        ARTIFACT_KIND="lora_adapter"
    elif [ -f "$ARTIFACT_PATH/config.json" ]; then
        ARTIFACT_KIND="full_model"
    else
        echo "ERROR: artifact kind 자동 판별 실패: adapter_config.json 또는 config.json 없음: $ARTIFACT_PATH"
        echo "해당 디렉토리 내용:"
        ls -la "$ARTIFACT_PATH" 2>/dev/null || echo "  (디렉토리 접근 불가)"
        exit 1
    fi
fi

if [ "$ARTIFACT_KIND" = "lora_adapter" ]; then
    if [ ! -f "$ARTIFACT_PATH/adapter_config.json" ]; then
        echo "ERROR: adapter_config.json이 없음: $ARTIFACT_PATH"
        echo "해당 디렉토리 내용:"
        ls -la "$ARTIFACT_PATH" 2>/dev/null || echo "  (디렉토리 접근 불가)"
        exit 1
    fi
elif [ "$ARTIFACT_KIND" = "full_model" ]; then
    if [ ! -f "$ARTIFACT_PATH/config.json" ]; then
        echo "ERROR: config.json이 없음: $ARTIFACT_PATH"
        exit 1
    fi
    # Changed: validate standalone full-model weight and tokenizer markers before copying.
    # Why: artifacts/merged_model with config only would be selected by solver.py and fail at runtime.
    if ! find "$ARTIFACT_PATH" -maxdepth 1 -type f \( -name "model*.safetensors" -o -name "pytorch_model*.bin" \) | grep -q .; then
        echo "ERROR: full model weight shard가 없음: $ARTIFACT_PATH"
        exit 1
    fi
    if [ ! -f "$ARTIFACT_PATH/tokenizer.json" ] && [ ! -f "$ARTIFACT_PATH/tokenizer_config.json" ] && [ ! -f "$ARTIFACT_PATH/vocab.json" ] && [ ! -f "$ARTIFACT_PATH/sentencepiece.bpe.model" ]; then
        echo "ERROR: tokenizer marker file이 없음: $ARTIFACT_PATH"
        exit 1
    fi
else
    echo "ERROR: 알 수 없는 artifact kind: $ARTIFACT_KIND"
    exit 1
fi

# ============================================================
# 경로 설정
# ============================================================
# Changed: runtime/repo paths are environment-driven.
# Why: submission packaging must not depend on the old shared workspace path.
OPAL_RUNTIME_ROOT="${OPAL_RUNTIME_ROOT:-/workspace/sinjeongmin_opal_verifier}"
if [ -n "${OPAL_REPO:-}" ]; then
    REPO="$OPAL_REPO"
else
    REPO=$(git rev-parse --show-toplevel 2>/dev/null || true)
    if [ -z "$REPO" ]; then
        echo "ERROR: current git repo root not found. Set OPAL_REPO."
        exit 1
    fi
fi

# Changed: artifact 경로에서 실험명 추출하여 제출 디렉토리 이름 생성.
# Why: 여러 adapter/full-model artifact를 동시에 제출 준비할 수 있도록 구분.
# 예: /workspace/sinjeongmin_opal_verifier/adapters/exp_a/checkpoints/checkpoint-189 -> submit-exp-a
ARTIFACT_BASENAME=$(basename "$ARTIFACT_PATH")
ARTIFACT_PARENT=$(basename "$(dirname "$ARTIFACT_PATH")")
ARTIFACT_GRANDPARENT=$(basename "$(dirname "$(dirname "$ARTIFACT_PATH")")")

# checkpoint-XXX 패턴이면 상위 디렉토리명 사용
if echo "$ARTIFACT_BASENAME" | grep -q "^checkpoint-"; then
    EXP_NAME="$ARTIFACT_GRANDPARENT"
else
    EXP_NAME="$ARTIFACT_BASENAME"
fi

# 디렉토리명에 안전하지 않은 문자 제거
EXP_NAME=$(echo "$EXP_NAME" | sed 's/[^a-zA-Z0-9_-]/-/g')
SUBMIT_DIR="$OPAL_RUNTIME_ROOT/submissions/submit-${EXP_NAME}"

SEP="============================================================"
echo "$SEP"
echo "제출 패키지 빌더"
echo "  Artifact:   $ARTIFACT_PATH"
echo "  Kind:       $ARTIFACT_KIND"
echo "  실험명:     $EXP_NAME"
echo "  제출 디렉토리: $SUBMIT_DIR"
echo "  제출 실행:  $DO_SUBMIT"
echo "$SEP"
echo ""

# ============================================================
# Step 1: repo 상태 확인
# ============================================================
echo "[1/7] Git repo 상태 확인..."
if [ ! -d "$REPO" ]; then
    echo "ERROR: repo가 존재하지 않음: $REPO"
    exit 1
fi

cd "$REPO"
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
echo "  Branch: $BRANCH, Commit: $COMMIT"
echo ""

# ============================================================
# Step 2: 제출 디렉토리 생성
# ============================================================
echo "[2/7] 제출 디렉토리 생성..."

# 기존 디렉토리가 있으면 삭제 (깔끔한 빌드)
if [ -d "$SUBMIT_DIR" ]; then
    echo "  기존 디렉토리 삭제: $SUBMIT_DIR"
    rm -rf "$SUBMIT_DIR"
fi

mkdir -p "$SUBMIT_DIR/src"
# Changed: create only the artifact family directory selected for this package.
# Why: solver.py gives artifacts/merged_model precedence; stale empty artifact dirs should not confuse readiness checks.
if [ "$ARTIFACT_KIND" = "full_model" ]; then
    MODEL_ARTIFACT_DIR="$SUBMIT_DIR/artifacts/merged_model"
else
    MODEL_ARTIFACT_DIR="$SUBMIT_DIR/artifacts/lora_adapter_v3"
fi
mkdir -p "$MODEL_ARTIFACT_DIR"
echo "  생성 완료"
echo ""

# ============================================================
# Step 3: src/ 파일 복사
# ============================================================
echo "[3/7] src/ 파일 복사..."

# solver.py — LLM-only 모드 확인
if [ ! -f "$REPO/src/solver.py" ]; then
    echo "ERROR: solver.py가 없음: $REPO/src/solver.py"
    exit 1
fi
cp "$REPO/src/solver.py" "$SUBMIT_DIR/src/"
echo "  solver.py 복사 완료"

# Changed: legacy helper solvers are intentionally not copied.
# Why: solver.py contains the LLM-only model path inline; lora_solver.py can contain historical rule-context code.
echo "  legacy helper solvers 복사 생략 (solver.py 단일 LLM-only entrypoint)"

# __init__.py — 패키지 초기화
if [ -f "$REPO/src/__init__.py" ]; then
    cp "$REPO/src/__init__.py" "$SUBMIT_DIR/src/"
else
    # Changed: __init__.py가 없으면 최소한의 것을 생성.
    # Why: src 패키지로 인식되어야 Solver 클래스를 import할 수 있음.
    echo "# expose the submission package" > "$SUBMIT_DIR/src/__init__.py"
fi
echo "  __init__.py 복사 완료"
echo ""

# ============================================================
# Step 4: model artifact 파일 복사
# ============================================================
echo "[4/7] Model artifact 복사..."

# Changed: copy LoRA adapters to artifacts/lora_adapter_v3 and full FT checkpoints to artifacts/merged_model.
# Why: solver.py loads standalone full models from merged_model first, then legacy LoRA adapters.
cp -R "$ARTIFACT_PATH"/. "$MODEL_ARTIFACT_DIR/"

# artifact 파일 목록 출력
echo "  복사된 파일:"
ls -lh "$MODEL_ARTIFACT_DIR/" | tail -n +2 | awk '{printf "    %-40s %s\n", $NF, $5}'
echo ""

# ============================================================
# Step 5: setup.sh, pyproject.toml 복사
# ============================================================
echo "[5/7] setup.sh, pyproject.toml 복사..."

# Changed: repo-local setup/metadata만 복사하고 외부 workspace fallback을 제거.
# Why: 제출 패키지는 현재 repo에서 재현되어야 하며 다른 workspace 의존은 stale 경로다.
if [ -f "$REPO/setup.sh" ]; then
    cp "$REPO/setup.sh" "$SUBMIT_DIR/"
    echo "  setup.sh 복사 (from repo)"
else
    echo "WARNING: setup.sh를 찾을 수 없음"
fi

if [ -f "$REPO/pyproject.toml" ]; then
    cp "$REPO/pyproject.toml" "$SUBMIT_DIR/"
    echo "  pyproject.toml 복사 (from repo)"
else
    echo "WARNING: pyproject.toml을 찾을 수 없음"
fi

# Changed: uv.lock도 repo-local 파일만 선택적으로 복사.
# Why: 외부 workspace lockfile을 섞으면 제출 환경 재현성이 깨진다.
if [ -f "$REPO/uv.lock" ]; then
    cp "$REPO/uv.lock" "$SUBMIT_DIR/"
    echo "  uv.lock 복사 (from repo)"
fi
echo ""

# ============================================================
# Step 6: 검증
# ============================================================
echo "[6/7] 제출 패키지 검증..."
echo ""

ERRORS=0

# --- 6a: 필수 파일 존재 확인 ---
echo "  [6a] 필수 파일 존재 확인..."
REQUIRED_FILES=(
    "src/solver.py"
    "src/__init__.py"
    "setup.sh"
    "pyproject.toml"
    # Changed: require uv.lock in generated submit directories.
    # Why: project.pdf lists uv.lock as dependency information for the evaluation setup phase.
    "uv.lock"
)

# Changed: append required artifact files according to the selected artifact family.
# Why: full-model packages should require config/weights/tokenizer, not LoRA adapter metadata.
if [ "$ARTIFACT_KIND" = "full_model" ]; then
    REQUIRED_FILES+=(
        "artifacts/merged_model/config.json"
    )
else
    REQUIRED_FILES+=(
        "artifacts/lora_adapter_v3/adapter_config.json"
        "artifacts/lora_adapter_v3/adapter_model.safetensors"
    )
fi

for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$SUBMIT_DIR/$f" ]; then
        echo "    OK: $f"
    else
        # adapter_model.safetensors 대신 adapter_model.bin일 수도 있음
        if [ "$f" = "artifacts/lora_adapter_v3/adapter_model.safetensors" ]; then
            if [ -f "$SUBMIT_DIR/artifacts/lora_adapter_v3/adapter_model.bin" ]; then
                echo "    OK: $f (adapter_model.bin 형식으로 존재)"
            else
                echo "    FAIL: $f (safetensors/bin 모두 없음)"
                ERRORS=$((ERRORS + 1))
            fi
        else
            echo "    FAIL: $f"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done
echo ""

# --- 6b: artifact config 유효성 확인 ---
echo "  [6b] artifact config 유효성..."
if [ "$ARTIFACT_KIND" = "lora_adapter" ]; then
    ADAPTER_CONFIG="$SUBMIT_DIR/artifacts/lora_adapter_v3/adapter_config.json"
    if [ -f "$ADAPTER_CONFIG" ]; then
        # JSON 파싱 가능한지 확인
        if python3 -c "import json; json.load(open('$ADAPTER_CONFIG')); print('    OK: JSON 유효')" 2>/dev/null; then
            # base_model_name_or_path 확인
            BASE_MODEL=$(python3 -c "
import json
cfg = json.load(open('$ADAPTER_CONFIG'))
print(cfg.get('base_model_name_or_path', 'NOT_SET'))
" 2>/dev/null || echo "PARSE_ERROR")
            echo "    base_model: $BASE_MODEL"

            # lora rank/alpha 확인
            python3 -c "
import json
cfg = json.load(open('$ADAPTER_CONFIG'))
r = cfg.get('r', '?')
alpha = cfg.get('lora_alpha', '?')
modules = cfg.get('target_modules', [])
print(f'    LoRA rank={r}, alpha={alpha}')
print(f'    target_modules: {modules}')
" 2>/dev/null || true
        else
            echo "    FAIL: JSON 파싱 실패"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "    FAIL: adapter_config.json 없음"
        ERRORS=$((ERRORS + 1))
    fi
else
    MERGED_CONFIG="$SUBMIT_DIR/artifacts/merged_model/config.json"
    if [ -f "$MERGED_CONFIG" ]; then
        # Changed: parse merged model config and report only non-secret model metadata.
        # Why: full FT package readiness needs config validity without dumping model internals.
        if python3 -c "import json; json.load(open('$MERGED_CONFIG')); print('    OK: JSON 유효')" 2>/dev/null; then
            python3 -c "
import json
cfg = json.load(open('$MERGED_CONFIG'))
print('    model_type: ' + str(cfg.get('model_type', 'NOT_SET')))
print('    architectures: ' + str(cfg.get('architectures', 'NOT_SET')))
" 2>/dev/null || true
        else
            echo "    FAIL: JSON 파싱 실패"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "    FAIL: merged_model config.json 없음"
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# --- 6c: solver.py의 LLM-only 구조 확인 ---
echo "  [6c] solver.py LLM-only 구조 확인..."
# Changed: USE_RULE_ENGINE 플래그 존재 여부 검증을 LLM-only 금지 패턴/필수 API 검증으로 교체.
# Why: 현재 LLM-only solver에서는 USE_RULE_ENGINE 부재가 정상이며 rule-engine 경로가 있으면 제출 구조 오류임.
SOLVER_FILE="$SUBMIT_DIR/src/solver.py"

if grep -Fq "_init_rule_engine(" "$SOLVER_FILE"; then
    echo "    FAIL: _init_rule_engine( 호출 또는 정의 발견"
    ERRORS=$((ERRORS + 1))
else
    echo "    OK: _init_rule_engine( 없음"
fi

if grep -Fq "USE_RULE_ENGINE" "$SOLVER_FILE"; then
    echo "    FAIL: USE_RULE_ENGINE 발견 (LLM-only 구조에서는 없어야 함)"
    ERRORS=$((ERRORS + 1))
else
    echo "    OK: USE_RULE_ENGINE 없음 (LLM-only 정상)"
fi

if grep -Fq "StatefulOpalVerifier(" "$SOLVER_FILE"; then
    echo "    FAIL: StatefulOpalVerifier( 생성 호출 발견"
    ERRORS=$((ERRORS + 1))
else
    echo "    OK: StatefulOpalVerifier( 생성 호출 없음"
fi

if grep -Eq "Rule engine으로 fallback|rule engine으로 fallback" "$SOLVER_FILE"; then
    echo "    FAIL: rule engine fallback 문자열 발견"
    ERRORS=$((ERRORS + 1))
else
    echo "    OK: rule engine fallback 문자열 없음"
fi

if grep -Eq "^[[:space:]]*class[[:space:]]+Solver\b" "$SOLVER_FILE"; then
    echo "    OK: class Solver 존재"
else
    echo "    FAIL: class Solver를 찾을 수 없음"
    ERRORS=$((ERRORS + 1))
fi

if grep -Eq "^[[:space:]]*def[[:space:]]+predict[[:space:]]*\(" "$SOLVER_FILE"; then
    echo "    OK: def predict 존재"
else
    echo "    FAIL: def predict를 찾을 수 없음"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# --- 6d: setup.sh에 peft 설치 확인 ---
echo "  [6d] setup.sh peft 설치 확인..."
if grep -q "peft" "$SUBMIT_DIR/setup.sh" 2>/dev/null; then
    echo "    OK: setup.sh에 peft 설치 포함"
else
    echo "    WARNING: setup.sh에 peft 설치가 없음!"
    echo "    LoRA adapter 로드 시 peft 패키지가 필요합니다."
    echo "    setup.sh에 다음을 추가합니다:"
    echo "      pip install peft"
    # Changed: setup.sh 상단에 peft 설치 추가.
    # Why: LoRA 모델 로드 시 peft 필수. 평가 서버 setup phase에서 설치해야 함.
    sed -i '1a\# Changed: peft 설치 추가 (LoRA adapter 로드 필수)\npip install --break-system-packages peft 2>/dev/null || pip install peft 2>/dev/null || true' "$SUBMIT_DIR/setup.sh"
    echo "    추가 완료"
fi
echo ""

# --- 6e: 절대 경로 검사 (평가 환경에서 작동하지 않을 수 있는 경로) ---
echo "  [6e] 절대 경로 검사..."
# Changed: /workspace/ 문자열은 운영 후보/로그 경로일 수 있으므로 warning-only로 유지.
# Why: solver.py는 repo-local adapter를 우선 사용하며, 서버 후보 경로 문자열만으로 제출 실패 처리하면 안 됨.
ABS_PATHS=$(grep -n "/workspace/" "$SUBMIT_DIR/src/solver.py" 2>/dev/null | grep -v "^#" | grep -v "# " || true)
if [ -n "$ABS_PATHS" ]; then
    echo "    WARNING: solver.py에 /workspace/ 절대 경로 발견:"
    echo "$ABS_PATHS" | head -5 | sed 's/^/      /'
    echo "    repo-local adapter가 우선 사용되면 운영 후보/로그 문자열은 경고로만 처리합니다."
else
    echo "    OK: solver.py에 절대 경로 없음"
fi

if [ -f "$SUBMIT_DIR/src/lora_solver.py" ]; then
    echo "    FAIL: legacy lora_solver.py가 제출 패키지에 포함됨"
    ERRORS=$((ERRORS + 1))
else
    echo "    OK: legacy lora_solver.py 미포함"
fi
echo ""

# --- 6f: solver.py 문법 검사 ---
echo "  [6f] solver.py 문법 검사..."
if python3 -c "import ast; ast.parse(open('$SUBMIT_DIR/src/solver.py').read())" 2>/dev/null; then
    echo "    OK: 문법 정상"
else
    echo "    FAIL: solver.py 문법 오류!"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# --- 6g: Solver 클래스 존재 확인 ---
echo "  [6g] Solver 클래스 확인..."
if grep -q "class Solver" "$SUBMIT_DIR/src/solver.py"; then
    echo "    OK: Solver 클래스 존재"
else
    echo "    FAIL: Solver 클래스를 찾을 수 없음!"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "def predict" "$SUBMIT_DIR/src/solver.py"; then
    echo "    OK: predict 메서드 존재"
else
    echo "    FAIL: predict 메서드를 찾을 수 없음!"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# --- 6h: model artifact 파일 크기 확인 ---
echo "  [6h] model artifact 파일 크기..."
ARTIFACT_DIR_SIZE=$(du -sh "$MODEL_ARTIFACT_DIR" | awk '{print $1}')
echo "    Artifact 크기: $ARTIFACT_DIR_SIZE"

# safetensors/bin 파일 크기 (너무 작으면 이상)
SAFETENSORS=$(find "$MODEL_ARTIFACT_DIR" \( -name "*.safetensors" -o -name "*.bin" \) 2>/dev/null | head -1)
if [ -n "$SAFETENSORS" ]; then
    SAFETENSORS_SIZE=$(stat -c%s "$SAFETENSORS" 2>/dev/null || stat -f%z "$SAFETENSORS" 2>/dev/null || echo "0")
    SAFETENSORS_MB=$((SAFETENSORS_SIZE / 1024 / 1024))
    echo "    모델 파일: $(basename "$SAFETENSORS") ($SAFETENSORS_MB MB)"
    if [ "$SAFETENSORS_MB" -lt 1 ]; then
        echo "    WARNING: 모델 파일이 1MB 미만 — 비정상적으로 작음"
    fi
fi
echo ""

# --- 6i: Python package readiness gate ---
echo "  [6i] Python package readiness gate..."
# Changed: run the shared readiness checker inside packaging, not only as a manual follow-up.
# Why: packaged helper contamination, HF offline parity, and incomplete artifacts must fail before submission.
CHECKER="$REPO/tools/eval/check_submit_package.py"
if [ -f "$CHECKER" ]; then
    if python3 "$CHECKER" "$SUBMIT_DIR"; then
        echo "    OK: check_submit_package.py 통과"
    else
        echo "    FAIL: check_submit_package.py 실패"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "    FAIL: check_submit_package.py 없음: $CHECKER"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# ============================================================
# Step 7: 최종 결과
# ============================================================
echo "[7/7] 최종 결과..."
echo ""

# 전체 크기
TOTAL_SIZE=$(du -sh "$SUBMIT_DIR" | awk '{print $1}')

# 디렉토리 구조 출력
echo "  제출 디렉토리 구조:"
find "$SUBMIT_DIR" -type f | sort | while read -r f; do
    REL="${f#$SUBMIT_DIR/}"
    SIZE=$(du -h "$f" | awk '{print $1}')
    printf "    %-50s %s\n" "$REL" "$SIZE"
done
echo ""
echo "  총 크기: $TOTAL_SIZE"
echo ""

if [ "$ERRORS" -gt 0 ]; then
    echo "$SEP"
    echo "FAIL: $ERRORS개 검증 오류 발견!"
    echo "위의 오류를 수정한 후 다시 실행하세요."
    echo "$SEP"
    exit 1
fi

echo "$SEP"
echo "SUCCESS: 제출 패키지 준비 완료"
echo ""
echo "  디렉토리: $SUBMIT_DIR"
echo "  총 크기:  $TOTAL_SIZE"
echo "  Artifact: $ARTIFACT_PATH"
echo "  Kind:     $ARTIFACT_KIND"
echo "  Commit:   $COMMIT ($BRANCH)"
echo ""
echo "제출 명령어:"
if [ -n "$JOB_NAME" ]; then
    echo "  submit --dir $SUBMIT_DIR --job-name $JOB_NAME"
else
    echo "  submit --dir $SUBMIT_DIR --job-name ${EXP_NAME}-${COMMIT}"
fi
echo "$SEP"

# ============================================================
# 자동 제출 (--submit 옵션)
# ============================================================
if $DO_SUBMIT; then
    echo ""
    echo "자동 제출 실행 중..."
    FINAL_JOB_NAME="${JOB_NAME:-${EXP_NAME}-${COMMIT}}"
    echo "  submit --dir $SUBMIT_DIR --job-name $FINAL_JOB_NAME"
    submit --dir "$SUBMIT_DIR" --job-name "$FINAL_JOB_NAME" 2>&1
fi
