# Deprecated Server Setup Guide

이 문서는 과거 `/workspace/team6` 및 `sshpass` 기반 운영 기록을 보존하는 legacy 문서다. 현재 cycle에서는 사용하지 않는다.

- 현재 운영 문서: [server_operations_current.md](server_operations_current.md)
- 현재 서버 root: `/workspace/sinjeongmin_opal_verifier`
- 현재 repo: `/workspace/sinjeongmin_opal_verifier/repo`
- 금지: `/workspace/team6`를 새 작업 root로 사용, `sshpass`/명령행 비밀번호/비밀번호 파일 저장, legacy `prepare_submission.sh` 실행

아래 내용은 과거 기록이며 실행 절차로 사용하면 안 된다.

# Server Setup & Operations Guide

## Server Access

- **Host**: `147.46.78.61`
- **Port**: `2227`
- **User**: `student` (shared account -- all team members use the same account)
- **Password**: Managed separately, NOT stored in repository
- **Tool**: `sshpass` (installed via Homebrew on macOS)
- **No sudo, no screen, no tmux**. Use `nohup` for background jobs.

### SSH Connection (retry required)

SSH to this server often fails on the first attempt. Always use a retry loop:

```bash
for i in 1 2 3 4; do
  sshpass -p '$PASSWORD' ssh student@147.46.78.61 -p 2227 \
    -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    "echo connected" && break
  echo "Attempt $i failed, retrying..."
  sleep 2
done
```

### SCP File Transfer

```bash
sshpass -p '$PASSWORD' scp -P 2227 -o StrictHostKeyChecking=no \
  src/solver.py src/lora_solver.py \
  student@147.46.78.61:/workspace/team6/team6-opal-verifier/src/
```

---

## Server Directory Structure

```
/workspace/
+-- project/                          # OTHER TEAM MEMBER's workspace
|   +-- solver1.py ... solver5.py     # DO NOT TOUCH. DO NOT READ. DO NOT MODIFY.
|   +-- ...                           # Completely separate codebase
|
+-- team6/                            # OUR workspace
|   +-- team6-opal-verifier/          # Git repo clone (dev branch)
|   |   +-- src/                      # Solver code (deployed from local)
|   |   +-- tools/                    # Training/eval scripts
|   |   +-- configs/
|   |   +-- docs/
|   |   +-- setup.sh
|   |   +-- pyproject.toml
|   |   +-- uv.lock
|   |
|   +-- training_data/                # Training datasets
|   |   +-- training_cases.json       # Main training data (2163 cases, 20.7MB)
|   |   +-- spec_train.json           # Spec-based train split (869 cases)
|   |   +-- spec_val.json             # Spec-based val split (283 cases)
|   |   +-- spec_test.json            # Spec-based test split (283 cases)
|   |   +-- gap_data.json             # Gap category training data (209 cases)
|   |
|   +-- adapters/                     # Trained LoRA adapters
|   |   +-- lora_4b_v2/              # Current best adapter
|   |   +-- ...                       # Various sweep results
|   |
|   +-- large_dp_test_set.json        # DEFAULT_PASS test set (252 cases)
|   +-- sweep_results.json            # HP sweep results
|   +-- sweep.log                     # Sweep training log
|   +-- pipeline.log                  # Full pipeline log
|   +-- submit-*/                     # Submission directories
|
+-- dl2026/                           # Course-provided resources (read-only)
    +-- dataset/                      # Public 20 labeled cases
    +-- skeleton/
        +-- model_cache/              # Pre-cached LLM weights
        |   +-- Qwen/Qwen3.5-0.8B/
        |   +-- Qwen/Qwen3.5-2B/
        |   +-- Qwen/Qwen3.5-4B/
        |   +-- Qwen/Qwen3.5-9B/
        |   +-- Qwen/Qwen3.5-27B-FP8/
        |   +-- google/gemma-4-*/
        +-- artifacts/
            +-- documents/            # TCG/Opal spec documents (BM25 index source)
                +-- core/             # Core spec chunks
                +-- opal/             # Opal spec chunks
```

### CRITICAL: `/workspace/project/` belongs to another team member. NEVER touch it.

All users share the `student` account. File access is not isolated. Be careful not to modify or delete files outside `/workspace/team6/`.

---

## GPU

- **Model**: NVIDIA L40S
- **VRAM**: 48GB (reported as 46068 MiB)
- **Shared**: Other users may be training simultaneously. Check with `nvidia-smi` before starting.

```bash
# Check GPU usage
nvidia-smi

# Kill orphan processes if needed (only YOUR processes)
# Do NOT kill other users' processes
```

---

## Software Environment

| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.14+ | System Python |
| PyTorch | 2.11.0+cu130 | Pre-installed |
| transformers | 5.8.1 | Pre-installed |
| peft | latest | `pip install --break-system-packages peft` |
| wandb | 0.27.0 | `pip install --break-system-packages wandb` |
| kernels | 0.14.1 | FP8 support for 27B model |
| scikit-learn | latest | For evaluation metrics |

### Installing Packages (no sudo)

```bash
pip install --break-system-packages <package>
```

The `--break-system-packages` flag is required because there is no virtual environment and pip refuses to install into the system Python without it.

---

## Deployment Workflow

### 1. Local Development -> Server Deploy

```bash
# Deploy source code
sshpass -p '$PASSWORD' scp -P 2227 -o StrictHostKeyChecking=no -r \
  src/ tools/ setup.sh pyproject.toml \
  student@147.46.78.61:/workspace/team6/team6-opal-verifier/

# Or use git pull on server (if dev branch is pushed)
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && git pull origin dev"
```

### 2. Training on Server

```bash
# Start training (background, survives disconnect)
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && \
   nohup python3 tools/training/train_uncertainty_resolver.py \
     > /workspace/team6/training.log 2>&1 &"

# Monitor
ssh student@147.46.78.61 -p 2227 "tail -50 /workspace/team6/training.log"
```

### 3. Submission

```bash
# Option A: Use prepare_submission.sh
ssh student@147.46.78.61 -p 2227 \
  "cd /workspace/team6/team6-opal-verifier && bash tools/eval/prepare_submission.sh"

# Option B: Manual
ssh student@147.46.78.61 -p 2227 \
  "mkdir -p /workspace/team6/submit-latest && \
   cp -r /workspace/team6/team6-opal-verifier/src \
         /workspace/team6/team6-opal-verifier/setup.sh \
         /workspace/team6/team6-opal-verifier/pyproject.toml \
         /workspace/team6/team6-opal-verifier/uv.lock \
         /workspace/team6/submit-latest/ && \
   submit --dir /workspace/team6/submit-latest/ --name team6-latest"
```

### 4. Evaluation Server Behavior

During evaluation, the server runs:
1. **Setup phase** (20 min, network ON): `setup.sh` executes (installs peft)
2. **Evaluation phase** (3 hours, network OFF): `evaluate.py` calls `src.solver.predict_one()` for each test case

The `predict_one()` function in `src/solver.py` is the sole entry point. It must:
- Accept a list of dicts (trajectory)
- Return "pass" or "fail"
- Complete all ~200 cases within 3 hours on L40S 48GB
- Work without network access

---

## Watchdog Setup

For long-running training jobs, a simple watchdog checks status every 5 minutes:

```bash
# Run on server (nohup)
while true; do
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
  tail -1 /workspace/team6/training.log
  sleep 300
done
```

This is not a formal monitoring system -- just a quick check to verify training is progressing.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| SSH fails on first attempt | Use retry loop (3-4 attempts) |
| GPU OOM | Reduce batch size, enable gradient checkpointing, use `MAX_MEMORY_GB` env var |
| `pip install` fails | Add `--break-system-packages` flag |
| Training crashes silently | Check `nohup.out` or the specified log file |
| Other user's process using GPU | Wait or coordinate; never kill their processes |
| Submission rejected | Daily quota exceeded; try again tomorrow |
| Model loading slow (~80s) | Normal for first load; subsequent loads use HF cache |
