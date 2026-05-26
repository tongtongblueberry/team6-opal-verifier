# Changed: test Self-Instruct generation request dry-run artifacts.
# Why: generation wrappers must not create ad-hoc candidates or leak public20 labels.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
            self.assertEqual("opal_final_response_output_first.v1", rows[0]["prompt_contract_version"])
            self.assertEqual(["tc1"], rows[0]["source_seed_sample_ids"])
            prompt_text = rows[0]["payload"]["messages"][1]["content"]
            self.assertIn("choose target_label as pass or fail", prompt_text)
            self.assertIn("target.final_response_index", prompt_text)
            self.assertEqual(2, json.loads(prompt_text)["candidate_count"])
            self.assertNotIn("public_label", json.dumps(rows[0]["payload"]["seed_profile_context"]))

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

    def test_execute_flag_does_not_call_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")

            exit_code = generation.main(
                [
                    "--seed-jsonl",
                    str(seed_path),
                    "--requests-output",
                    str(tmp / "requests.jsonl"),
                    "--metadata-json",
                    str(tmp / "metadata.json"),
                    "--execute",
                ]
            )

            self.assertEqual(2, exit_code)


if __name__ == "__main__":
    unittest.main()
