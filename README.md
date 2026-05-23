# Team 6 Opal Verifier: Rule Baseline 73.00

This branch is a cleaned rule-based baseline for SSD TCG/Opal trajectory pass/fail
classification. It is based on the historical 73.00 leaderboard branch:

- Source branch: `origin/rule_base`
- Source commit: `dec0840938e4fdbec72d413ccbb12c2065b45a27`
- Recorded leaderboard result: Job `300`, `solver-fix-auth-ro`, score `73.00`
- Clean-branch recheck: Job `415`, `rulebase-73-clean-20260523_051344_KST`, score `73.00`
- Key changes over the 71.50 baseline: empty `HostChallenge` is treated as unauthenticated, and Read-Only sessions reject write methods.

No LoRA, RAG, training pipeline, generated data, or model artifact is used in this
branch. The prediction path is deterministic and stdlib-only.

## Repository Layout

```text
.
├── README.md
├── pyproject.toml
├── setup.sh
├── uv.lock
└── src
    ├── __init__.py
    └── solver.py
```

## Prediction Path

```text
input trajectory
  -> src.solver.StatefulOpalVerifier
  -> protocol-state tracking and rule checks
  -> "pass" or "fail"
```

Important rule families include:

- final command/response parsing
- StartSession authentication state
- authenticated vs unauthenticated method preconditions
- Read-Only session write blocking
- known object field access checks
- locking data read/write access checks
- unexpected final error status handling

## Local Smoke Test

Run the submission setup smoke:

```bash
bash setup.sh
```

Run a direct one-case prediction:

```bash
python3 - <<'PY'
from src.solver import predict_one

case = [
    {
        "input": {"Method": {"Name": "Properties"}, "InvokingUID": {"Name": "Session Manager UID"}},
        "output": {"Status": {"Name": "SUCCESS"}, "Properties": {"MaxMethods": 1}},
    }
]

print(predict_one(case))
PY
```

Expected output:

```text
pass
```

## Using This As A Data-Generation Baseline

Use this branch as a fixed teacher only through the public solver API:

```python
from src.solver import predict_one

label = predict_one(trajectory)
```

Do not mix this branch with LoRA or generated-model artifacts when measuring whether
new synthetic data improves over the rule baseline. If a generated dataset is being
audited, compare its labels against this branch first, then test any new model or
rule change in a separate branch.

## Leaderboard Recheck

This cleaned branch was submitted again from an isolated server package and returned
`Success 73.00` on Job `415`. The submitted package contained only:

- `README.md`
- `pyproject.toml`
- `setup.sh`
- `uv.lock`
- `src/__init__.py`
- `src/solver.py`

The server package smoke passed before submission.
