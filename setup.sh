#!/usr/bin/env bash
# Changed: keep setup dependency-free for the rule-only baseline.
# Why: the 73.00 branch uses only stdlib code in src/solver.py, so setup should only smoke-test imports.
set -euo pipefail

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
