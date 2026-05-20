#!/bin/bash
# Full training pipeline: data gen → train → distill → calibrate → evaluate
# Run on server with: nohup bash tools/training/run_full_pipeline.sh >> /workspace/team6/pipeline.log 2>&1 &
set -e

cd /workspace/team6/team6-opal-verifier
export PYTHONPATH="/workspace/team6/team6-opal-verifier:$PYTHONPATH"

LOG_DIR="/workspace/team6"
SEP="============================================================"

echo "$SEP"
echo "FULL PIPELINE START: $(date)"
echo "$SEP"

# Step 0: Check GPU
echo ""
echo "--- GPU Status ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv
echo ""

# Step 1: Pull latest code
echo "$SEP"
echo "Step 1: Pull latest code"
echo "$SEP"
git fetch origin && git checkout dev && git pull origin dev
echo "HEAD: $(git log --oneline -1)"

# Step 2: Diagnose public 20
echo ""
echo "$SEP"
echo "Step 2: Public 20 Rule Engine Diagnosis"
echo "$SEP"
python3 -u tools/eval/diagnose_public.py 2>&1 | tee "$LOG_DIR/diagnose.log"

# Step 3: Generate uncertainty training data
echo ""
echo "$SEP"
echo "Step 3: Generate Uncertainty Training Data"
echo "$SEP"
python3 -u tools/training/generate_uncertainty_data.py 2>&1 | tee "$LOG_DIR/gen_data.log"

# Step 4: Train uncertainty resolver (20 epochs, ~4 hours)
echo ""
echo "$SEP"
echo "Step 4: Train Uncertainty Resolver (20 epochs)"
echo "$SEP"
python3 -u tools/training/train_uncertainty_resolver.py 2>&1 | tee "$LOG_DIR/uncertainty_train.log"

# Step 5: Self-distillation (10 epochs, ~2 hours)
echo ""
echo "$SEP"
echo "Step 5: Self-Distillation for Calibration"
echo "$SEP"
TEACHER_PATH="/workspace/team6/adapters/uncertainty_resolver/final"
if [ -d "$TEACHER_PATH" ]; then
    python3 -u tools/training/self_distill.py --teacher "$TEACHER_PATH" 2>&1 | tee "$LOG_DIR/self_distill.log"
else
    echo "SKIP: Teacher adapter not found at $TEACHER_PATH"
fi

# Step 6: Conformal calibration
echo ""
echo "$SEP"
echo "Step 6: Conformal Prediction Calibration"
echo "$SEP"
python3 -u tools/eval/conformal_calibration.py 2>&1 | tee "$LOG_DIR/conformal.log"

# Summary
echo ""
echo "$SEP"
echo "PIPELINE COMPLETE: $(date)"
echo "$SEP"
echo "Logs:"
echo "  Diagnosis:    $LOG_DIR/diagnose.log"
echo "  Data gen:     $LOG_DIR/gen_data.log"
echo "  Training:     $LOG_DIR/uncertainty_train.log"
echo "  Distillation: $LOG_DIR/self_distill.log"
echo "  Conformal:    $LOG_DIR/conformal.log"
echo ""
echo "Adapters:"
echo "  Stage 1: /workspace/team6/adapters/uncertainty_resolver/final"
echo "  Stage 2: /workspace/team6/adapters/distilled/final"
echo "  Submit:  artifacts/lora_adapter_v3/"
