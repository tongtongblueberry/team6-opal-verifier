# Changed: verify gap datagen keeps owned default paths import-safe.
# Why: DEFAULT_* path definitions must not depend on sys.path branch execution.

from __future__ import annotations

import unittest

from tools.datagen import generate_gap_data


class GenerateGapDataDefaultsTest(unittest.TestCase):
    def test_default_training_data_dir_is_owned_workspace(self) -> None:
        self.assertTrue(hasattr(generate_gap_data, "DEFAULT_RUNTIME_ROOT"))
        self.assertTrue(hasattr(generate_gap_data, "DEFAULT_TRAINING_DATA_DIR"))
        self.assertEqual(
            "/workspace/sinjeongmin_opal_verifier/training_data",
            str(generate_gap_data.DEFAULT_TRAINING_DATA_DIR),
        )
        self.assertNotIn("/workspace/team6", str(generate_gap_data.DEFAULT_TRAINING_DATA_DIR))


if __name__ == "__main__":
    unittest.main()
