#!/bin/bash
# Prepare and test a leaderboard submission.
# Run on server: bash tools/eval/prepare_submission.sh [commit_hash]
#
# Steps:
# 1. Create submission directory from current dev code
# 2. Copy LoRA adapter (if available)
# 3. Run local evaluation on public 20
# 4. Show expected score before submission
set -e

REPO="/workspace/team6/team6-opal-verifier"
COMMIT=${1:-$(cd $REPO && git rev-parse --short HEAD)}
SUBMIT_DIR="/workspace/team6/submission-$COMMIT"
ADAPTER_V3="/workspace/team6/adapters/uncertainty_resolver/final"
ADAPTER_V2="/workspace/team6/team6-opal-verifier/artifacts/lora_adapter_v2"

echo "============================================================"
echo "SUBMISSION PREPARATION: $COMMIT"
echo "============================================================"

# Step 1: Create submission directory
if [ -d "$SUBMIT_DIR" ]; then
    echo "Submission dir already exists: $SUBMIT_DIR"
else
    echo "Creating submission from $REPO..."
    cd "$REPO"
    git checkout dev
    git pull origin dev
    mkdir -p "$SUBMIT_DIR"
    # Copy essential files
    cp -r src "$SUBMIT_DIR/"
    cp evaluate.py "$SUBMIT_DIR/"
    cp -r tools "$SUBMIT_DIR/" 2>/dev/null || true
    mkdir -p "$SUBMIT_DIR/artifacts"
fi

# Step 2: Copy LoRA adapter
if [ -d "$ADAPTER_V3" ]; then
    echo "Copying v3 adapter from $ADAPTER_V3..."
    cp -r "$ADAPTER_V3" "$SUBMIT_DIR/artifacts/lora_adapter_v3"
    echo "  v3 adapter: $(du -sh $SUBMIT_DIR/artifacts/lora_adapter_v3 | awk '{print $1}')"
elif [ -d "$ADAPTER_V2" ]; then
    echo "Copying v2 adapter from $ADAPTER_V2..."
    cp -r "$ADAPTER_V2" "$SUBMIT_DIR/artifacts/lora_adapter_v2"
    echo "  v2 adapter: $(du -sh $SUBMIT_DIR/artifacts/lora_adapter_v2 | awk '{print $1}')"
else
    echo "WARNING: No LoRA adapter found. Submission will use rule engine only."
fi

# Step 3: Run local evaluation
echo ""
echo "--- Local Evaluation (Public 20) ---"
cd "$SUBMIT_DIR"
export PYTHONPATH="$SUBMIT_DIR:$PYTHONPATH"
export DATASET_DIR="/dl2026/dataset"
export LABEL_PATH="/dl2026/dataset/label.jsonl"

python3 evaluate.py 2>&1

echo ""
echo "--- Predictions ---"
cat predictions.jsonl 2>/dev/null

echo ""
echo "--- Score ---"
cat scores.json 2>/dev/null

echo ""
echo "============================================================"
echo "Submission ready at: $SUBMIT_DIR"
echo "Size: $(du -sh $SUBMIT_DIR | awk '{print $1}')"
echo "============================================================"
