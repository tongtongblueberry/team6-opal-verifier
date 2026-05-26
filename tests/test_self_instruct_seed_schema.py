# Changed: cover input-only Self-Instruct seed normalization and profile metrics.
# Why: public20 seeds must not carry labels, targets, or evidence into generation/training paths.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.datagen import self_instruct_seed_schema as schema


def _record(method: str, status: str, return_values: list[object] | None = None) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": [] if return_values is None else return_values},
    }


class SelfInstructSeedSchemaTests(unittest.TestCase):
    def test_normalizes_input_only_seed_without_label_fields(self) -> None:
        seed = {
            "sample_id": "seed-pass",
            "instruction": "Use this trajectory shape as generation context.",
            "records": [
                _record("StartSession", "SUCCESS"),
                _record("Get", "SUCCESS", [{"3": "value"}]),
            ],
            "source": "public20_input_only",
        }

        normalized = schema.normalize_seed(seed)

        self.assertEqual("self_instruct.seed.v1", normalized["schema_version"])
        self.assertEqual("seed-pass", normalized["sample_id"])
        self.assertEqual("public20_input_only", normalized["source"])
        self.assertNotIn("label", normalized)
        self.assertNotIn("target", normalized)
        self.assertNotIn("primary_evidence", normalized)
        self.assertEqual(2, normalized["profile"]["record_count"])
        self.assertEqual("Get", normalized["profile"]["final_method"])
        self.assertEqual("SUCCESS", normalized["profile"]["final_status"])

    def test_normalizes_seed_from_trajectory_container(self) -> None:
        seed = {
            "seed_id": "seed-container",
            "instruction": "Use the last response shape only.",
            "trajectory": {
                "records": [
                    _record("StartSession", "SUCCESS"),
                    _record("Set", "FAIL"),
                ]
            },
        }

        normalized = schema.normalize_seed(seed)

        self.assertEqual("seed-container", normalized["sample_id"])
        self.assertEqual("public20_input_only", normalized["source"])
        self.assertEqual(["StartSession", "Set"], normalized["profile"]["method_sequence"])
        self.assertEqual(["SUCCESS", "FAIL"], normalized["profile"]["status_sequence"])

    def test_rejects_label_like_seed_fields_by_default(self) -> None:
        seed = {
            "sample_id": "seed-with-label",
            "instruction": "This must not leak labels.",
            "records": [_record("Get", "SUCCESS")],
            "label": "pass",
        }

        with self.assertRaisesRegex(schema.SeedSchemaError, "forbidden_seed_fields:label"):
            schema.normalize_seed(seed)

    def test_allows_label_fields_for_audit_but_omits_them(self) -> None:
        seed = {
            "sample_id": "seed-audit",
            "instruction": "Audit-only ingest.",
            "records": [_record("Get", "SUCCESS")],
            "expected_label": "pass",
        }

        normalized = schema.normalize_seed(seed, allow_label_fields_for_audit=True)

        self.assertNotIn("expected_label", normalized)
        self.assertNotIn("label", normalized)
        self.assertEqual("Get", normalized["profile"]["final_method"])

    def test_profile_calculates_dimension_vector(self) -> None:
        seed = schema.normalize_seed(
            {
                "sample_id": "seed-profile",
                "instruction": "Profile this input-only trajectory.",
                "records": [
                    _record("Properties", "SUCCESS"),
                    _record("EndSession", "SUCCESS", ["done"]),
                ],
            }
        )

        profile = schema.profile_seed(seed)
        expected_input_json_chars = len(
            json.dumps(
                {"instruction": seed["instruction"], "records": seed["records"]},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

        self.assertEqual(2, profile["record_count"])
        self.assertEqual(expected_input_json_chars, profile["input_json_chars"])
        self.assertEqual(["Properties", "EndSession"], profile["method_sequence"])
        self.assertEqual(["SUCCESS", "SUCCESS"], profile["status_sequence"])
        self.assertEqual("EndSession", profile["final_method"])
        self.assertEqual("SUCCESS", profile["final_status"])
        self.assertEqual([0, 1], profile["return_value_counts"])
        self.assertEqual(1, profile["total_return_value_count"])
        self.assertEqual(1, profile["final_return_value_count"])
        self.assertEqual("1-32", profile["length_bin"])
        self.assertNotIn("label", profile)

    def test_cli_writes_input_only_jsonl_and_profile_json(self) -> None:
        seed = {
            "sample_id": "seed-cli",
            "instruction": "Normalize through CLI.",
            "records": [_record("Get", "SUCCESS")],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "input.jsonl"
            output_path = tmp / "normalized.jsonl"
            profile_path = tmp / "profile.json"
            input_path.write_text(json.dumps(seed) + "\n", encoding="utf-8")

            exit_code = schema.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--profile-output",
                    str(profile_path),
                ]
            )

            self.assertEqual(0, exit_code)
            normalized_rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(normalized_rows))
            self.assertEqual("seed-cli", normalized_rows[0]["sample_id"])
            self.assertNotIn("label", normalized_rows[0])
            self.assertEqual(1, profile["count"])
            self.assertEqual({"public20_input_only": 1}, profile["source_counts"])
            self.assertNotIn("label_counts", profile)


if __name__ == "__main__":
    unittest.main()
