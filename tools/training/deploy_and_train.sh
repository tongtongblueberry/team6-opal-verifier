#!/bin/bash
# Changed: disable the deprecated rule-id deployment pipeline.
# Why: current work must use the owned runtime root and LLM-only training/submission artifacts.

set -euo pipefail

cat >&2 <<'MSG'
This script is deprecated and intentionally disabled.

Use the current cycle tools under /workspace/sinjeongmin_opal_verifier:
- tools/datagen/generate_long_shape_source.py
- tools/analysis/build_supervised_manifest.py
- tools/analysis/validate_manifest.py
- tools/training/train_manifest_lora.py
- tools/training/train_manifest_full.py

No password, /workspace/team6 dependency, or rule-id training pipeline may be stored or launched here.
MSG

exit 2
