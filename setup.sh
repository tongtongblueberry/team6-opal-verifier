#!/usr/bin/env bash
# Changed: install peft for LoRA adapter loading during setup phase.
# Why: LoRA fine-tuned model (4B v2) is stored in artifacts/lora_adapter_v2/.
# peft library is needed to load the adapter. Setup phase has network access.
set -euo pipefail

# Changed: define stable Hugging Face cache/offline defaults before any solver import.
# Why: evaluator runtime must see the same HF cache path and offline flags that package checks require.
if [ -n "${OPAL_HF_CACHE:-}" ]; then
    HF_CACHE_DEFAULT="$OPAL_HF_CACHE"
elif [ -d /workspace/cache/hf_cache ] || [ -w /workspace/cache ] 2>/dev/null; then
    HF_CACHE_DEFAULT="/workspace/cache/hf_cache"
else
    HF_CACHE_DEFAULT="$PWD/.hf_cache"
fi
mkdir -p "$HF_CACHE_DEFAULT" 2>/dev/null || true
export HF_HOME="${HF_HOME:-$HF_CACHE_DEFAULT}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_CACHE_DEFAULT}"

# Changed: default HF offline mode for evaluator/package shells while keeping git worktree dev online.
# Why: submit packages normally run without network, but online development should remain possible by default.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    OPAL_PACKAGE_RUNTIME_DEFAULT=0
else
    OPAL_PACKAGE_RUNTIME_DEFAULT=1
fi
if [ -d /workspace/cache/hf_cache ]; then
    HF_OFFLINE_DEFAULT=1
else
    HF_OFFLINE_DEFAULT="$OPAL_PACKAGE_RUNTIME_DEFAULT"
fi
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-$HF_OFFLINE_DEFAULT}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-$HF_OFFLINE_DEFAULT}"

# Install peft if not already available (setup phase has network)
pip install --break-system-packages peft 2>/dev/null || pip install peft 2>/dev/null || true

python3 - <<'PY'
# Changed: smoke-test import and HF parity only, without instantiating Solver.
# Why: setup must not fail just because model artifacts are absent in local/package checks.
import os
from src import solver

required = ("HF_HOME", "HF_HUB_CACHE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
missing = [name for name in required if os.environ.get(name) is None]
assert not missing, f"missing HF env defaults: {missing}"
expected_local = (
    os.environ["HF_HUB_OFFLINE"].strip().lower() in {"1", "true", "yes", "on"}
    or os.environ["TRANSFORMERS_OFFLINE"].strip().lower() in {"1", "true", "yes", "on"}
)
assert solver._hf_local_files_only() == expected_local
PY
