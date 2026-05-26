# Changed: guard the active data audit defaults against the old shared workspace.
# Why: unattended audits must read only our workspace unless the operator passes --input.

from __future__ import annotations

import unittest

from tools.analysis import data_audit


class DataAuditDefaultsTest(unittest.TestCase):
    def test_default_input_candidates_exclude_team6_workspace(self) -> None:
        candidates = [str(path) for path in data_audit.DEFAULT_INPUT_CANDIDATES]
        self.assertNotIn("/workspace/team6/training_data", candidates)
        self.assertTrue(any(path.startswith("/workspace/sinjeongmin_opal_verifier") for path in candidates))


if __name__ == "__main__":
    unittest.main()
