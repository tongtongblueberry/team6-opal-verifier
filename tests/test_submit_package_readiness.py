# Changed: cover submit-package readiness checks for HF offline/cache parity.
# Why: setup.sh and solver.py regressions should fail before evaluator submission.

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.eval.check_submit_package import check_submit_package


# Changed: build a minimal package fixture from the current worktree files.
# Why: readiness checks should run without model artifacts, datasets, or submit commands.
def _make_package(root: Path) -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory()
    package_dir = Path(temp_dir.name)
    (package_dir / "src").mkdir()
    shutil.copy2(root / "setup.sh", package_dir / "setup.sh")
    shutil.copy2(root / "src" / "solver.py", package_dir / "src" / "solver.py")
    shutil.copy2(root / "src" / "__init__.py", package_dir / "src" / "__init__.py")
    return temp_dir


# Changed: test the checker as a package-level gate.
# Why: missing HF env defaults or local_files_only propagation must block readiness.
class SubmitPackageReadinessTest(unittest.TestCase):
    def test_current_package_files_pass_hf_offline_readiness(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            errors = check_submit_package(Path(temp_name))
        self.assertEqual([], errors)

    def test_missing_offline_setup_env_fails_readiness(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with _make_package(root) as temp_name:
            setup_path = Path(temp_name) / "setup.sh"
            setup_path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
            errors = check_submit_package(Path(temp_name))
        self.assertTrue(any("HF_HOME" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
