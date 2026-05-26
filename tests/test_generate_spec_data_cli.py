# Changed: cover public seed ingestion as a hard-fail CLI path.
# Why: public/eval labels must not become supervised training rows by operator mistake.

from __future__ import annotations

import sys
import unittest
from unittest import mock

from tools.datagen import generate_spec_data


class GenerateSpecDataCliTest(unittest.TestCase):
    def test_include_public_seed_is_disabled(self) -> None:
        with mock.patch.object(sys, "argv", ["generate_spec_data.py", "--include-public-seed"]):
            with self.assertRaises(SystemExit) as raised:
                generate_spec_data.main()
        self.assertNotEqual(0, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
