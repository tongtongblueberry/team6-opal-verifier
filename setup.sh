#!/bin/bash
# Changed: follow skeleton pattern — uv sync first, then HF env.
# Why: eval server requires uv sync to install packages into .venv.

uv sync

# HF cache/offline for evaluation phase (no network)
if [ -d /workspace/cache/hf_cache ]; then
    export HF_HOME=/workspace/cache/hf_cache
    export HF_HUB_CACHE=/workspace/cache/hf_cache
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1
elif [ -d /dl2026/skeleton/model_cache ]; then
    export HF_HOME=/dl2026/skeleton/model_cache
    export HF_HUB_CACHE=/dl2026/skeleton/model_cache
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1
fi

# Install peft if not in venv deps
pip install peft 2>/dev/null || true
