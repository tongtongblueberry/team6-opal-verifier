#!/bin/bash
# 9B model training pipeline (run after 4B baseline is established).
# Uses Qwen3.5-9B with conservative VRAM settings.
# Run on server: nohup bash tools/training/run_9b_pipeline.sh >> /workspace/team6/9b_pipeline.log 2>&1 &
set -e

cd /workspace/team6/team6-opal-verifier
export PYTHONPATH="/workspace/team6/team6-opal-verifier:$PYTHONPATH"
export RAG_MODEL="Qwen/Qwen3.5-9B"
export MAX_MEMORY_GB=44
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
# Changed: disable SCL for 9B to avoid output_hidden_states OOM.
export SCL_WEIGHT=0

SEP="============================================================"
echo "$SEP"
echo "9B PIPELINE START: $(date)"
echo "Model: $RAG_MODEL"
echo "$SEP"

# Step 1: Generate gap data (if not done)
if [ ! -f /workspace/team6/training_data/gap_cases.json ]; then
    echo "Generating gap data..."
    python3 -u tools/datagen/generate_gap_data.py
fi

# Step 2: Generate uncertainty data with gap cases included
python3 -u tools/training/generate_uncertainty_data.py

# Step 3: Train 9B LoRA (bs=1, grad_accum=8, maxlen=1024)
python3 -c "
import os, sys
os.environ['RAG_MODEL'] = 'Qwen/Qwen3.5-9B'
os.environ['MAX_MEMORY_GB'] = '44'
os.environ['SCL_WEIGHT'] = '0'
sys.path.insert(0, '/workspace/team6/team6-opal-verifier')
from tools.training.train_uncertainty_resolver import Config, train_and_evaluate
cfg = Config()
cfg.model_name = 'Qwen/Qwen3.5-9B'
cfg.max_length = 1024
cfg.batch_size = 1
cfg.grad_accum = 8
cfg.epochs = 20
cfg.lr = 5e-4       # Conservative for 9B (larger model → lower LR)
cfg.rank = 16
cfg.alpha = 32
cfg.dropout = 0.1
cfg.label_smoothing = 0.05
cfg.scl_weight = 0  # Disabled for 9B VRAM safety
train_and_evaluate(cfg)
"

# Step 4: Conformal calibration
python3 -u tools/eval/conformal_calibration.py

echo "$SEP"
echo "9B PIPELINE COMPLETE: $(date)"
echo "$SEP"
