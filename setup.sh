#!/bin/bash
# Changed: LLM 기반 solver로 전환 — torch/transformers/accelerate 필요.
# Why: Qwen3.5-0.8B full FT merged model을 GPU에서 로드하여 추론.

uv sync

# Changed: HF 환경변수 설정 — 평가 서버의 캐시 경로를 사용.
# Why: Evaluation phase에서 네트워크 차단되므로 사전 캐시된 모델만 사용 가능.
if [ -d /workspace/cache/hf_cache ]; then
    export HF_HOME=/workspace/cache/hf_cache
    export HF_HUB_CACHE=/workspace/cache/hf_cache
elif [ -d /dl2026/skeleton/model_cache ]; then
    export HF_HOME=/dl2026/skeleton/model_cache
    export HF_HUB_CACHE=/dl2026/skeleton/model_cache
fi
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Changed: import smoke test.
# Why: solver가 정상 import되는지 확인 (모델 로드는 하지 않음 — predict 호출 시 로드).
python -c "from src.solver import Solver, predict, predict_one; print('solver import OK')"
