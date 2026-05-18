#!/usr/bin/env bash
# Changed: install peft for LoRA adapter loading during setup phase.
# Why: LoRA fine-tuned model (4B v2) is stored in artifacts/lora_adapter_v2/.
# peft library is needed to load the adapter. Setup phase has network access.
set -euo pipefail

# Install peft if not already available (setup phase has network)
pip install --break-system-packages peft 2>/dev/null || pip install peft 2>/dev/null || true

python3 - <<'PY'
from src.solver import predict_one

case = [
    {
        "input": {"Method": {"Name": "Properties"}, "InvokingUID": {"Name": "Session Manager UID"}},
        "output": {"Status": {"Name": "SUCCESS"}, "Properties": {"MaxMethods": 1}},
    }
]
assert predict_one(case) == "pass"
PY
