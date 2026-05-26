# Changed: guard the active data audit defaults against the old shared workspace.
# Why: unattended audits must read only our workspace unless the operator passes --input.

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.analysis import data_audit


class DataAuditDefaultsTest(unittest.TestCase):
    def test_default_input_candidates_exclude_team6_workspace(self) -> None:
        candidates = [str(path) for path in data_audit.DEFAULT_INPUT_CANDIDATES]
        self.assertEqual(["/workspace/sinjeongmin_opal_verifier/training_data", "training_data"], candidates)
        self.assertFalse(any("/workspace/team6" in path for path in candidates))
        self.assertFalse(any(path.endswith("/data") or path == "data" for path in candidates))

    def test_explicit_team6_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden input root"):
            data_audit.resolve_input_roots(["/workspace/team6/training_data"])

    def test_symlink_to_team6_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            link_path = Path(tmpdir) / "training_data"
            try:
                link_path.symlink_to("/workspace/team6/training_data", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "forbidden input root"):
                data_audit.resolve_input_roots([str(link_path)])


if __name__ == "__main__":
    unittest.main()
