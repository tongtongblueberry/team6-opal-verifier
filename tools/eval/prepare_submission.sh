#!/bin/bash
# Safe LLM-only submission builder. NEVER touches /workspace/project/.
# Run on server: bash tools/eval/prepare_submission.sh [--with-lora] [--submit] [job-name]
#
# Examples:
#   bash tools/eval/prepare_submission.sh --with-lora        # with LoRA, test only
#   bash tools/eval/prepare_submission.sh --with-lora --submit gap-retrain-v1
set -e

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
COMMIT=$(cd "$REPO" && git rev-parse --short HEAD)
SUBMIT_DIR="$OPAL_RUNTIME_ROOT/submissions/submission-$COMMIT"
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

# Changed: submission packaging fails closed without an LLM artifact.
# Why: this project is LLM-only, so packaging must not create a non-LLM fallback submission.
if ! $WITH_LORA; then
    echo "ERROR: --with-lora is required until merged-model packaging is implemented."
    echo "LLM-only submission packaging must include a trained LLM artifact."
    exit 1
fi

SEP="============================================================"
echo "$SEP"
echo "SUBMISSION BUILDER (commit: $COMMIT)"
echo "  LoRA: $WITH_LORA | Submit: $DO_SUBMIT | Name: ${JOB_NAME:-auto}"
echo "$SEP"

# Step 1: Record current code state
cd "$REPO"
# Changed: package the explicitly selected repo/branch without checkout or pull.
# Why: branch ownership must stay stable during long-running training cycles.
echo "HEAD: $(git log --oneline -1)"

# Step 2: Build submission directory
rm -rf "$SUBMIT_DIR" 2>/dev/null
mkdir -p "$SUBMIT_DIR/src"

# Changed: copy only the submission entrypoint solver.
# Why: solver.py has the LLM-only model path inline; legacy helper solvers can carry rule-context code.
cp "$REPO/src/solver.py" "$SUBMIT_DIR/src/"

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
    # Changed: runtime adapter candidate uses OPAL_RUNTIME_ROOT.
    # Why: LoRA packaging must not depend on the old shared workspace path.
    for candidate in \
        "$OPAL_RUNTIME_ROOT/adapters/uncertainty_resolver/final" \
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
        echo "ERROR: --with-lora was requested but no adapter was found."
        exit 1
    fi
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
    JOB_NAME=${JOB_NAME:-"$COMMIT-lora"}
    submit --dir "$SUBMIT_DIR" --job-name "$JOB_NAME" 2>&1
fi

echo ""
echo "$SEP"
echo "Submission dir: $SUBMIT_DIR ($(du -sh $SUBMIT_DIR | awk '{print $1}'))"
echo "To submit: submit --dir $SUBMIT_DIR --job-name YOUR_NAME"
echo "$SEP"
