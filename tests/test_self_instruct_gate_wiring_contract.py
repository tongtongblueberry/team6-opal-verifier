# Changed: document Gate A/B/C command wiring in executable tests.
# Why: artifact requirements must be explicit without declaring real Gate pass from mock fixtures.

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "self_instruct_gate_wiring"


# Changed: keep the required artifact flags for Gate A/B/C in one visible test contract.
# Why: command wiring must identify inputs and outputs even when no real generated accepted data exists.
GATE_COMMAND_CONTRACTS = {
    "Gate A": {
        "script": ROOT / "tools" / "analysis" / "audit_self_instruct_quality.py",
        "artifact_flags": (
            "--accepted-jsonl",
            "--sample-size",
            "--seed",
            "--invariant-jsonl",
            "--audit-pack-md",
            "--audit-report-json",
            "--audit-report-md",
        ),
        "contract_note": "Requires post-judge accepted candidate JSONL and writes audit artifacts; mock wiring is no pass declaration.",
    },
    "Gate B": {
        "script": ROOT / "tools" / "analysis" / "compare_public20_dimensions.py",
        "artifact_flags": (
            "--public-profile",
            "--generated-profile",
            "--public-label-distribution",
            "--output-json",
            "--output-md",
        ),
        "contract_note": "Requires public20/generated profile artifacts and optional public aggregate labels; mock wiring is no pass declaration.",
    },
    "Gate C": {
        "script": ROOT / "tools" / "analysis" / "check_manifest_model_input_equivalence.py",
        "artifact_flags": (
            "--candidates-jsonl",
            "--manifest-jsonl",
            "--output-json",
            "--output-md",
        ),
        "contract_note": "Requires normalized candidates plus supervised manifest artifacts; mock wiring is no pass declaration.",
    },
}


class SelfInstructGateWiringContractTests(unittest.TestCase):
    # Changed: verify the Gate CLIs expose every artifact flag named in the contract.
    # Why: docs and tests should fail together if command wiring drifts.
    def test_cli_help_exposes_gate_artifact_flags(self) -> None:
        for gate_name, contract in GATE_COMMAND_CONTRACTS.items():
            result = subprocess.run(
                [sys.executable, str(contract["script"]), "--help"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, gate_name)
            for flag in contract["artifact_flags"]:
                self.assertIn(flag, result.stdout, gate_name)

    # Changed: assert mock fixtures stay in tests/fixtures and never imply Gate pass.
    # Why: fixture-based wiring tests must not be promoted to runs/ artifacts or sample publication.
    def test_mock_fixture_contract_is_no_pass_and_not_runs_data(self) -> None:
        self.assertTrue(FIXTURE_ROOT.is_dir())
        fixture_files = {path.name for path in FIXTURE_ROOT.iterdir() if path.is_file()}
        self.assertIn("mock_raw_outputs.jsonl", fixture_files)
        self.assertIn("mock_judge_results_required_booleans.jsonl", fixture_files)
        for path in FIXTURE_ROOT.iterdir():
            self.assertIn("/tests/fixtures/", str(path))
            self.assertNotIn("/runs/", str(path))
        for contract in GATE_COMMAND_CONTRACTS.values():
            self.assertIn("no pass declaration", contract["contract_note"])


if __name__ == "__main__":
    unittest.main()
