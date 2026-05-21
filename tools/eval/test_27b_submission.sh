#!/usr/bin/env bash
# Changed: test script for solver_27b.py submission validation.
# Why: verifies that the LLM-only solver loads, runs, and produces correct output format.
#
# Usage:
#   bash tools/eval/test_27b_submission.sh
#
# Requirements:
#   - GPU with >= 48GB VRAM (L40S or equivalent)
#   - Pre-cached Qwen/Qwen3.5-27B-FP8 model
#   - transformers, torch, accelerate packages

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== solver_27b.py Submission Test ==="
echo "Project dir: $PROJECT_DIR"
echo ""

# --- Test 1: Syntax check ---
echo "[1/4] Syntax check..."
python3 -c "import ast; ast.parse(open('$PROJECT_DIR/src/solver_27b.py').read()); print('  PASS: syntax OK')"

# --- Test 2: Import check (no GPU needed) ---
echo "[2/4] Import check..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
# Only check that the module can be parsed and non-GPU code works
from src.solver_27b import (
    extract_relevant_steps,
    format_trajectory,
    format_step,
    _compact_json,
    SYSTEM_PROMPT,
    Solver,
)
print('  PASS: all symbols importable')
"

# --- Test 3: Format pipeline test (no GPU needed) ---
echo "[3/4] Format pipeline test..."
python3 -c "
import sys, json
sys.path.insert(0, '$PROJECT_DIR')
from src.solver_27b import extract_relevant_steps, format_trajectory

# Minimal fake trajectory
steps = [
    {
        'input': {
            'method': {'name': 'StartSession', 'args': {'required': {'SPID': 'AdminSP', 'Write': True}}},
            'invoking_id': {'name': 'SessionManager'}
        },
        'output': {'status_codes': {'Name': 'SUCCESS'}}
    },
    {
        'input': {
            'method': {'name': 'Set', 'args': {'required': {}}},
            'invoking_id': {'name': 'C_PIN_SID'}
        },
        'output': {'status_codes': {'Name': 'SUCCESS'}, 'return_values': []}
    }
]

# Test extract_relevant_steps
filtered = extract_relevant_steps(steps)
assert len(filtered) == 2, f'Expected 2 steps, got {len(filtered)}'

# Test format_trajectory
text = format_trajectory(steps)
assert 'StartSession' in text, 'Missing StartSession in formatted text'
assert '[FINAL]' in text, 'Missing [FINAL] marker'
assert 'Answer:' in text, 'Missing Answer: prompt'
print('  PASS: format pipeline works correctly')
print(f'  Formatted prompt length: {len(text)} chars')
"

# --- Test 4: Full GPU test (only on server) ---
echo "[4/4] Full GPU test (requires GPU + model)..."
if python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "  GPU detected. Running full Solver test..."
    python3 -c "
import sys, json, time, logging
sys.path.insert(0, '$PROJECT_DIR')
logging.basicConfig(level=logging.INFO)

from src.solver_27b import Solver

# Minimal test dataset
dataset = [
    {
        'id': 'test_001',
        'steps': [
            {
                'input': {
                    'method': {'name': 'StartSession', 'args': {'required': {'SPID': 'AdminSP', 'Write': True, 'HostSigningAuthority': 'SID'}}},
                    'invoking_id': {'name': 'SessionManager'}
                },
                'output': {'status_codes': {'Name': 'SUCCESS'}, 'return_values': {'SPSessionID': 1}}
            },
            {
                'input': {
                    'method': {'name': 'Get', 'args': {'required': {}}},
                    'invoking_id': {'name': 'C_PIN_MSID'}
                },
                'output': {'status_codes': {'Name': 'SUCCESS'}, 'return_values': [{'UID': '0x000000000B000002', 'PIN': 'MSID_DEFAULT'}]}
            }
        ]
    },
    {
        'id': 'test_002',
        'steps': [
            {
                'input': {
                    'method': {'name': 'StartSession', 'args': {'required': {'SPID': 'LockingSP', 'Write': True}}},
                    'invoking_id': {'name': 'SessionManager'}
                },
                'output': {'status_codes': {'Name': 'NOT_AUTHORIZED'}}
            }
        ]
    }
]

t0 = time.time()
solver = Solver()
init_time = time.time() - t0
print(f'  Model loaded in {init_time:.1f}s')

t0 = time.time()
results = solver.predict(dataset)
pred_time = time.time() - t0
print(f'  Predictions: {results}')
print(f'  Prediction time: {pred_time:.1f}s for {len(dataset)} cases')
print(f'  Avg time per case: {pred_time/len(dataset):.1f}s')
print(f'  Estimated time for 200 cases: {pred_time/len(dataset)*200/60:.1f} minutes')

# Validate output format
assert isinstance(results, dict), f'Expected dict, got {type(results)}'
assert len(results) == 2, f'Expected 2 predictions, got {len(results)}'
for case_id, pred in results.items():
    assert pred in ('pass', 'fail'), f'Invalid prediction: {pred}'
    assert isinstance(case_id, str), f'Case ID should be string: {case_id}'
print('  PASS: output format correct')
"
else
    echo "  No GPU detected. Skipping full Solver test."
    echo "  Run this on the server (147.46.78.61:2227) for full validation."
fi

echo ""
echo "=== All tests passed ==="
