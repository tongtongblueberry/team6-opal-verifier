#!/bin/bash
# Changed: FSM 기반 solver로 전환 — GPU/torch/transformers 불필요.
# Why: 순수 Python FSM 검증기이므로 추가 패키지 설치 없이 동작.

uv sync

# Changed: HF 환경변수 설정 유지 (호환성).
# Why: 평가 서버가 이 변수를 기대할 수 있으므로 안전하게 설정.
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

# Changed: import smoke test.
# Why: solver가 정상 import되는지 확인.
python -c "from src.solver import Solver, predict, predict_one; print('solver import OK')"
