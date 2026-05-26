# Changed: test Self-Instruct generation request dry-run artifacts.
# Why: generation wrappers must not create ad-hoc candidates or leak public20 labels.

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.datagen import run_self_instruct_generation as generation


def _seed_row(sample_id: str = "tc1") -> dict[str, object]:
    records = [
        {
            "input": {"method": {"name": "Properties"}},
            "output": {"status_codes": "SUCCESS", "return_values": []},
        }
    ]
    return {
        "sample_id": sample_id,
        "input": json.dumps({"records": records}),
        "source": "public20_input_only",
    }


class RunSelfInstructGenerationTests(unittest.TestCase):
    def test_cli_writes_dry_run_request_payload_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            request_path = tmp / "requests.jsonl"
            metadata_path = tmp / "metadata.json"
            seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")

            exit_code = generation.main(
                [
                    "--seed-jsonl",
                    str(seed_path),
                    "--requests-output",
                    str(request_path),
                    "--metadata-json",
                    str(metadata_path),
                    "--request-count",
                    "1",
                    "--seeds-per-request",
                    "1",
                    "--candidates-per-request",
                    "2",
                    "--created-at-kst",
                    "2026-05-26T18:00:00+09:00",
                ]
            )

            self.assertEqual(0, exit_code)
            rows = [json.loads(line) for line in request_path.read_text(encoding="utf-8").splitlines()]
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(rows))
            self.assertFalse(rows[0]["execute"])
            self.assertFalse(metadata["execute"])
            self.assertEqual("opal_final_response_spec_grounded_output_first.v1", rows[0]["prompt_contract_version"])
            self.assertEqual(["tc1"], rows[0]["source_seed_sample_ids"])
            self.assertIn("RULE 01", rows[0]["source_spec_rule_refs"])
            self.assertEqual("docs/legacy_spec_rules.md", rows[0]["payload"]["spec_rule_context"][0]["source_path"])
            prompt_text = rows[0]["payload"]["messages"][1]["content"]
            self.assertIn("choose target_label as pass or fail", prompt_text)
            self.assertIn("target.final_response_index", prompt_text)
            self.assertIn("spec_grounding", prompt_text)
            self.assertIn("source_span", prompt_text)
            self.assertEqual(2, json.loads(prompt_text)["candidate_count"])
            self.assertNotIn("public_label", json.dumps(rows[0]["payload"]["seed_profile_context"]))
            self.assertTrue(metadata["spec_rules_input"].endswith("docs/legacy_spec_rules.md"))

    def test_rejects_seed_rows_with_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            request_path = tmp / "requests.jsonl"
            metadata_path = tmp / "metadata.json"
            row = _seed_row()
            row["label"] = "pass"
            seed_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

            exit_code = generation.main(
                [
                    "--seed-jsonl",
                    str(seed_path),
                    "--requests-output",
                    str(request_path),
                    "--metadata-json",
                    str(metadata_path),
                ]
            )

            self.assertEqual(2, exit_code)
            self.assertFalse(request_path.exists())

    # Changed: --execute now skips safely when the provider env var is absent.
    # Why: tests and dry-run workflows must not make paid API calls without explicit env configuration.
    def test_execute_flag_skips_without_provider_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                exit_code = generation.main(
                    [
                        "--seed-jsonl",
                        str(seed_path),
                        "--requests-output",
                        str(tmp / "requests.jsonl"),
                        "--metadata-json",
                        str(tmp / "metadata.json"),
                        "--raw-output-jsonl",
                        str(tmp / "raw_outputs.jsonl"),
                        "--runner-report-json",
                        str(tmp / "runner_report.json"),
                        "--execute",
                    ]
                )

            self.assertEqual(0, exit_code)
            metadata = json.loads((tmp / "metadata.json").read_text(encoding="utf-8"))
            runner_report = json.loads((tmp / "runner_report.json").read_text(encoding="utf-8"))
            self.assertFalse(metadata["execute"])
            self.assertTrue(metadata["execute_requested"])
            self.assertEqual("skipped_missing_env", metadata["runner"]["status"])
            self.assertEqual("skipped_missing_env", runner_report["status"])
            self.assertEqual("OPENAI_API_KEY", runner_report["provider_env_var"])
            self.assertFalse((tmp / "raw_outputs.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
