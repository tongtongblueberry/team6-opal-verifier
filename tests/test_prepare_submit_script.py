# Changed: exercise prepare_submit.sh as a real packaging flow.
# Why: the Python readiness checker must be enforced inside the submit builder, not only by manual follow-up.

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class PrepareSubmitScriptTest(unittest.TestCase):
    def test_prepare_submit_runs_python_readiness_gate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as runtime_dir, tempfile.TemporaryDirectory() as adapter_dir:
            adapter_path = Path(adapter_dir) / "adapter-final"
            adapter_path.mkdir()
            (adapter_path / "adapter_config.json").write_text(
                json.dumps(
                    {
                        "base_model_name_or_path": "fake/base",
                        "r": 4,
                        "lora_alpha": 8,
                        "target_modules": ["q_proj"],
                    }
                ),
                encoding="utf-8",
            )
            (adapter_path / "adapter_model.safetensors").write_bytes(b"fake")

            env = os.environ.copy()
            env["OPAL_RUNTIME_ROOT"] = runtime_dir
            env["OPAL_REPO"] = str(root)
            result = subprocess.run(
                ["bash", str(root / "tools" / "eval" / "prepare_submit.sh"), str(adapter_path)],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            submit_dir = Path(runtime_dir) / "submissions" / "submit-adapter-final"
            self.assertEqual(0, result.returncode, result.stdout)
            self.assertIn("[6i] Python package readiness gate", result.stdout)
            self.assertIn("OK: check_submit_package.py 통과", result.stdout)
            self.assertTrue((submit_dir / "src" / "solver.py").is_file())
            self.assertFalse((submit_dir / "src" / "lora_solver.py").exists())


if __name__ == "__main__":
    unittest.main()
