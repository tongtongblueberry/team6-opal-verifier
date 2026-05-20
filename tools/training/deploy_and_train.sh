#!/bin/bash
# Deploy code to server and start uncertainty resolver training pipeline.
# Usage: bash tools/training/deploy_and_train.sh
#
# Pipeline:
# 1. Push dev branch to origin
# 2. Pull on server
# 3. Generate uncertainty training data (tags each case with rule_id)
# 4. Train uncertainty resolver LoRA (20 epochs, lr=1e-3, rank=16)
# 5. Evaluate on public 20

set -e

SSH_CMD="sshpass -p 'bg@3*a&5r+uoN2FRoAU^' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 student@147.46.78.61 -p 2227"
REMOTE_DIR="/workspace/team6/team6-opal-verifier"

ssh_retry() {
    for i in 1 2 3 4 5 6; do
        eval "$SSH_CMD \"$1\"" 2>&1 && return 0
        echo "SSH attempt $i failed, retrying..."
        sleep 2
    done
    echo "SSH FAILED after 6 attempts"
    return 1
}

echo "=== Step 1: Check GPU availability ==="
ssh_retry "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv && ps aux | grep python | grep -v grep || echo 'No python processes'"

echo ""
echo "=== Step 2: Pull latest code on server ==="
ssh_retry "cd $REMOTE_DIR && git fetch origin && git checkout dev && git pull origin dev"

echo ""
echo "=== Step 3: Generate uncertainty training data ==="
ssh_retry "cd $REMOTE_DIR && python3 -u tools/training/generate_uncertainty_data.py"

echo ""
echo "=== Step 4: Start training (nohup) ==="
ssh_retry "cd $REMOTE_DIR && nohup python3 -u tools/training/train_uncertainty_resolver.py >> /workspace/team6/uncertainty_train.log 2>&1 & echo \$! > /workspace/team6/uncertainty_train.pid && echo 'Training started, PID:' && cat /workspace/team6/uncertainty_train.pid"

echo ""
echo "=== Monitoring ==="
echo "Check progress: ssh_retry 'tail -20 /workspace/team6/uncertainty_train.log'"
echo "Check GPU: ssh_retry 'nvidia-smi'"
echo "Check process: ssh_retry 'ps aux | grep train_uncertainty'"
