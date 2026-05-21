#!/usr/bin/env bash
# Changed: adapter 경로를 인자로 받아 제출 패키지를 빌드하는 스크립트.
# Why: 서버에서 학습된 adapter를 즉시 제출 디렉토리로 패키징해야 함.
#
# 사용법:
#   bash tools/eval/prepare_submit.sh /workspace/team6/adapters/exp_a/checkpoints/checkpoint-189
#   bash tools/eval/prepare_submit.sh /workspace/team6/adapters/exp_a/checkpoints/checkpoint-189 --submit
#   bash tools/eval/prepare_submit.sh /workspace/team6/adapters/exp_a/checkpoints/checkpoint-189 --name my-run
#
# 필수 조건:
#   - 서버에서 실행 (평가 환경 아님)
#   - adapter_config.json이 있는 유효한 adapter 경로
#   - git repo가 /workspace/team6/team6-opal-verifier에 존재
set -euo pipefail

# ============================================================
# 인자 파싱
# ============================================================
ADAPTER_PATH=""
DO_SUBMIT=false
JOB_NAME=""

for arg in "$@"; do
    case "$arg" in
        --submit) DO_SUBMIT=true ;;
        --name)   shift_next=true ;;
        --name=*) JOB_NAME="${arg#--name=}" ;;
        *)
            if [ "${shift_next:-false}" = true ]; then
                JOB_NAME="$arg"
                shift_next=false
            elif [ -z "$ADAPTER_PATH" ]; then
                ADAPTER_PATH="$arg"
            fi
            ;;
    esac
done

if [ -z "$ADAPTER_PATH" ]; then
    echo "ERROR: adapter 경로가 필요합니다."
    echo ""
    echo "사용법: $0 <adapter_path> [--submit] [--name <job_name>]"
    echo ""
    echo "예시:"
    echo "  $0 /workspace/team6/adapters/exp_a/checkpoints/checkpoint-189"
    echo "  $0 /workspace/team6/adapters/best_adapter --submit --name lora-v3-best"
    exit 1
fi

# adapter 경로 유효성 검사
if [ ! -d "$ADAPTER_PATH" ]; then
    echo "ERROR: adapter 경로가 존재하지 않음: $ADAPTER_PATH"
    exit 1
fi

if [ ! -f "$ADAPTER_PATH/adapter_config.json" ]; then
    echo "ERROR: adapter_config.json이 없음: $ADAPTER_PATH"
    echo "해당 디렉토리 내용:"
    ls -la "$ADAPTER_PATH" 2>/dev/null || echo "  (디렉토리 접근 불가)"
    exit 1
fi

# ============================================================
# 경로 설정
# ============================================================
REPO="/workspace/team6/team6-opal-verifier"

# Changed: adapter 경로에서 실험명 추출하여 제출 디렉토리 이름 생성.
# Why: 여러 adapter를 동시에 제출 준비할 수 있도록 구분.
# 예: /workspace/team6/adapters/exp_a/checkpoints/checkpoint-189 → submit-exp-a
ADAPTER_BASENAME=$(basename "$ADAPTER_PATH")
ADAPTER_PARENT=$(basename "$(dirname "$ADAPTER_PATH")")
ADAPTER_GRANDPARENT=$(basename "$(dirname "$(dirname "$ADAPTER_PATH")")")

# checkpoint-XXX 패턴이면 상위 디렉토리명 사용
if echo "$ADAPTER_BASENAME" | grep -q "^checkpoint-"; then
    EXP_NAME="$ADAPTER_GRANDPARENT"
else
    EXP_NAME="$ADAPTER_BASENAME"
fi

# 디렉토리명에 안전하지 않은 문자 제거
EXP_NAME=$(echo "$EXP_NAME" | sed 's/[^a-zA-Z0-9_-]/-/g')
SUBMIT_DIR="/workspace/team6/submit-${EXP_NAME}"

SEP="============================================================"
echo "$SEP"
echo "제출 패키지 빌더"
echo "  Adapter:    $ADAPTER_PATH"
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
mkdir -p "$SUBMIT_DIR/artifacts/lora_adapter_v3"
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

# lora_solver.py — LoRA 추론 모듈
if [ -f "$REPO/src/lora_solver.py" ]; then
    cp "$REPO/src/lora_solver.py" "$SUBMIT_DIR/src/"
    echo "  lora_solver.py 복사 완료"
fi

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
# Step 4: adapter 파일 복사
# ============================================================
echo "[4/7] LoRA adapter 복사..."

# Changed: adapter 파일을 artifacts/lora_adapter_v3/에 복사.
# Why: solver.py가 v3 > v2 > 기본 순서로 adapter를 탐색.
#      v3에 넣으면 최우선으로 로드됨.
cp "$ADAPTER_PATH"/* "$SUBMIT_DIR/artifacts/lora_adapter_v3/"

# adapter 파일 목록 출력
echo "  복사된 파일:"
ls -lh "$SUBMIT_DIR/artifacts/lora_adapter_v3/" | tail -n +2 | awk '{printf "    %-40s %s\n", $NF, $5}'
echo ""

# ============================================================
# Step 5: setup.sh, pyproject.toml 복사
# ============================================================
echo "[5/7] setup.sh, pyproject.toml 복사..."

# Changed: 우리 repo의 setup.sh 우선, 없으면 /workspace/project/ fallback.
# Why: 우리 setup.sh에 peft 설치가 포함되어 있음.
if [ -f "$REPO/setup.sh" ]; then
    cp "$REPO/setup.sh" "$SUBMIT_DIR/"
    echo "  setup.sh 복사 (from repo)"
elif [ -f "/workspace/project/setup.sh" ]; then
    cp "/workspace/project/setup.sh" "$SUBMIT_DIR/"
    echo "  setup.sh 복사 (from /workspace/project/)"
else
    echo "WARNING: setup.sh를 찾을 수 없음"
fi

if [ -f "$REPO/pyproject.toml" ]; then
    cp "$REPO/pyproject.toml" "$SUBMIT_DIR/"
    echo "  pyproject.toml 복사 (from repo)"
elif [ -f "/workspace/project/pyproject.toml" ]; then
    cp "/workspace/project/pyproject.toml" "$SUBMIT_DIR/"
    echo "  pyproject.toml 복사 (from /workspace/project/)"
else
    echo "WARNING: pyproject.toml을 찾을 수 없음"
fi

# uv.lock이 있으면 복사
if [ -f "/workspace/project/uv.lock" ]; then
    cp "/workspace/project/uv.lock" "$SUBMIT_DIR/"
    echo "  uv.lock 복사"
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
    "artifacts/lora_adapter_v3/adapter_config.json"
    "artifacts/lora_adapter_v3/adapter_model.safetensors"
    "setup.sh"
    "pyproject.toml"
)

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

# --- 6b: adapter_config.json 유효성 확인 ---
echo "  [6b] adapter_config.json 유효성..."
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
echo ""

# --- 6c: solver.py의 USE_RULE_ENGINE 플래그 확인 ---
echo "  [6c] solver.py USE_RULE_ENGINE 확인..."
USE_RULE_FLAG=$(grep -n "^USE_RULE_ENGINE" "$SUBMIT_DIR/src/solver.py" 2>/dev/null || echo "NOT_FOUND")

if echo "$USE_RULE_FLAG" | grep -q "False"; then
    echo "    OK: USE_RULE_ENGINE = False (LLM-only 모드)"
elif echo "$USE_RULE_FLAG" | grep -q "True"; then
    echo "    WARNING: USE_RULE_ENGINE = True (rule engine 모드)"
    echo "    LLM-only 제출이라면 False로 변경 필요!"
    echo ""
    read -r -p "    USE_RULE_ENGINE을 False로 변경하시겠습니까? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        # Changed: sed로 USE_RULE_ENGINE 플래그를 False로 변경.
        # Why: LLM-only 제출에서는 반드시 False여야 함.
        sed -i 's/^USE_RULE_ENGINE = True/USE_RULE_ENGINE = False/' "$SUBMIT_DIR/src/solver.py"
        echo "    변경 완료: USE_RULE_ENGINE = False"
    else
        echo "    유지: USE_RULE_ENGINE = True"
    fi
else
    echo "    WARNING: USE_RULE_ENGINE 플래그를 찾을 수 없음"
    echo "    $USE_RULE_FLAG"
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
# Changed: /workspace/ 경로가 solver.py에 하드코딩되어 있으면 경고.
# Why: 평가 서버의 작업 디렉토리는 /workspace/가 아닐 수 있음.
#      solver.py는 상대 경로 (Path(__file__).parents[1]) 사용해야 함.
ABS_PATHS=$(grep -n "/workspace/" "$SUBMIT_DIR/src/solver.py" 2>/dev/null | grep -v "^#" | grep -v "# " || true)
if [ -n "$ABS_PATHS" ]; then
    echo "    WARNING: solver.py에 /workspace/ 절대 경로 발견:"
    echo "$ABS_PATHS" | head -5 | sed 's/^/      /'
    echo "    평가 환경에서 작동하지 않을 수 있습니다."
else
    echo "    OK: solver.py에 절대 경로 없음"
fi

ABS_PATHS_LORA=$(grep -n "/workspace/" "$SUBMIT_DIR/src/lora_solver.py" 2>/dev/null | grep -v "^#" | grep -v "# " || true)
if [ -n "$ABS_PATHS_LORA" ]; then
    echo "    WARNING: lora_solver.py에 /workspace/ 절대 경로 발견:"
    echo "$ABS_PATHS_LORA" | head -5 | sed 's/^/      /'
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

# --- 6h: adapter 파일 크기 확인 ---
echo "  [6h] adapter 파일 크기..."
ADAPTER_DIR_SIZE=$(du -sh "$SUBMIT_DIR/artifacts/lora_adapter_v3" | awk '{print $1}')
echo "    Adapter 크기: $ADAPTER_DIR_SIZE"

# safetensors 파일 크기 (너무 작으면 이상)
SAFETENSORS=$(find "$SUBMIT_DIR/artifacts/lora_adapter_v3" -name "*.safetensors" -o -name "*.bin" 2>/dev/null | head -1)
if [ -n "$SAFETENSORS" ]; then
    SAFETENSORS_SIZE=$(stat -c%s "$SAFETENSORS" 2>/dev/null || stat -f%z "$SAFETENSORS" 2>/dev/null || echo "0")
    SAFETENSORS_MB=$((SAFETENSORS_SIZE / 1024 / 1024))
    echo "    모델 파일: $(basename "$SAFETENSORS") ($SAFETENSORS_MB MB)"
    if [ "$SAFETENSORS_MB" -lt 1 ]; then
        echo "    WARNING: 모델 파일이 1MB 미만 — 비정상적으로 작음"
    fi
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
echo "  Adapter:  $ADAPTER_PATH"
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
