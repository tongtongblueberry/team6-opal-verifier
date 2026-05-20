#!/bin/bash
# Safe submission builder. NEVER touches /workspace/project/.
# Run on server: bash tools/eval/prepare_submission.sh [--with-lora] [--submit] [job-name]
#
# Examples:
#   bash tools/eval/prepare_submission.sh                    # rule engine only, test only
#   bash tools/eval/prepare_submission.sh --with-lora        # with LoRA, test only
#   bash tools/eval/prepare_submission.sh --submit my-run    # rule engine only, submit
#   bash tools/eval/prepare_submission.sh --with-lora --submit gap-retrain-v1
set -e

REPO="/workspace/team6/team6-opal-verifier"
COMMIT=$(cd $REPO && git rev-parse --short HEAD)
SUBMIT_DIR="/workspace/team6/submission-$COMMIT"
WITH_LORA=false
DO_SUBMIT=false
JOB_NAME=""

# Parse args
for arg in "$@"; do
    case $arg in
        --with-lora) WITH_LORA=true ;;
        --submit) DO_SUBMIT=true ;;
        *) JOB_NAME="$arg" ;;
    esac
done

SEP="============================================================"
echo "$SEP"
echo "SUBMISSION BUILDER (commit: $COMMIT)"
echo "  LoRA: $WITH_LORA | Submit: $DO_SUBMIT | Name: ${JOB_NAME:-auto}"
echo "$SEP"

# Step 1: Pull latest code
cd "$REPO"
git fetch origin && git checkout dev && git pull origin dev 2>/dev/null
echo "HEAD: $(git log --oneline -1)"

# Step 2: Build submission directory
rm -rf "$SUBMIT_DIR" 2>/dev/null
mkdir -p "$SUBMIT_DIR/src"

# Copy solver + lora_solver
cp "$REPO/src/solver.py" "$SUBMIT_DIR/src/"
cp "$REPO/src/lora_solver.py" "$SUBMIT_DIR/src/"

# Create __init__.py
echo "from .solver import Solver" > "$SUBMIT_DIR/src/__init__.py"

# Copy skeleton files from /workspace/project/ (but NOT solver.py!)
cp /workspace/project/setup.sh "$SUBMIT_DIR/" 2>/dev/null || true
cp /workspace/project/pyproject.toml "$SUBMIT_DIR/" 2>/dev/null || true
cp /workspace/project/uv.lock "$SUBMIT_DIR/" 2>/dev/null || true

# Step 3: LoRA adapter
if $WITH_LORA; then
    # Priority: v3 > v2
    ADAPTER=""
    for candidate in \
        "/workspace/team6/adapters/uncertainty_resolver/final" \
        "$REPO/artifacts/lora_adapter_v3" \
        "$REPO/artifacts/lora_adapter_v2"; do
        if [ -d "$candidate" ] && [ -f "$candidate/adapter_config.json" ]; then
            ADAPTER="$candidate"
            break
        fi
    done

    if [ -n "$ADAPTER" ]; then
        # Determine target name based on source
        if echo "$ADAPTER" | grep -q "v3\|uncertainty"; then
            TARGET="artifacts/lora_adapter_v3"
        else
            TARGET="artifacts/lora_adapter_v2"
        fi
        mkdir -p "$SUBMIT_DIR/$TARGET"
        cp "$ADAPTER"/* "$SUBMIT_DIR/$TARGET/"
        echo "LoRA adapter: $ADAPTER → $TARGET ($(du -sh $SUBMIT_DIR/$TARGET | awk '{print $1}'))"
    else
        echo "WARNING: --with-lora but no adapter found!"
        WITH_LORA=false
    fi
fi

if ! $WITH_LORA; then
    # Disable LoRA in solver
    python3 -c "
with open('$SUBMIT_DIR/src/solver.py') as f:
    code = f.read()
old = '''        try:
            from src.lora_solver import LoRASolver
            self.lora_solver = LoRASolver()
            if not self.lora_solver.available:
                self.lora_solver = None
        except Exception:
            self.lora_solver = None'''
code = code.replace(old, '        self.lora_solver = None  # LoRA disabled')
with open('$SUBMIT_DIR/src/solver.py', 'w') as f:
    f.write(code)
"
    echo "LoRA: DISABLED (rule engine only)"
fi

# Step 4: Local evaluation (public 20)
echo ""
echo "--- Public 20 Evaluation ---"
cd "$SUBMIT_DIR"
export PYTHONPATH="$SUBMIT_DIR"

# Use our evaluate.py
cp "$REPO/evaluate.py" "$SUBMIT_DIR/" 2>/dev/null
export DATASET_DIR="/dl2026/dataset"
export LABEL_PATH="/dl2026/dataset/label.jsonl"
python3 evaluate.py 2>&1 | tail -5
echo ""
echo "Score: $(cat scores.json 2>/dev/null)"

# Step 5: Submit if requested
if $DO_SUBMIT; then
    echo ""
    echo "$SEP"
    echo "SUBMITTING..."
    JOB_NAME=${JOB_NAME:-"$COMMIT-$([ $WITH_LORA = true ] && echo lora || echo rule)"}
    submit --dir "$SUBMIT_DIR" --job-name "$JOB_NAME" 2>&1
fi

echo ""
echo "$SEP"
echo "Submission dir: $SUBMIT_DIR ($(du -sh $SUBMIT_DIR | awk '{print $1}'))"
echo "To submit: submit --dir $SUBMIT_DIR --job-name YOUR_NAME"
echo "$SEP"
