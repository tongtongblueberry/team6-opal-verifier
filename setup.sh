#!/usr/bin/env bash
# Changed: keep setup explicit and offline-safe.
# Why: the submission environment allows setup time, but this solver has no external dependencies.
set -euo pipefail
# Changed: use python3 explicitly for macOS and course-server compatibility.
# Why: some environments do not provide a `python` executable.
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
