# Changed: cover Gate C candidate/manifest/trainer-loader equivalence.
# Why: generated synthetic data must remain a full trajectory input before any model or leaderboard use.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import build_supervised_manifest as builder
from tools.analysis import check_manifest_model_input_equivalence as gate_c


def _record(method: str, status: str) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": []},
    }


def _spec_grounding() -> list[dict[str, object]]:
    return [
        {
            "rule_ref": "RULE 01",
            "source_path": "docs/legacy_spec_rules.md",
            "source_span": "docs/legacy_spec_rules.md:10-15",
            "condition": "A method is processed completely and without error by the TPer",
            "expected_status": "SUCCESS (0x00)",
        }
    ]


def _candidate(sample_id: str = "si-001", label: str = "pass") -> dict[str, object]:
    records = [_record("StartSession", "SUCCESS"), _record("Get", "SUCCESS")]
    final_index = len(records) - 1
    return {
        "sample_id": sample_id,
        "instruction": "Judge only the final response.",
        "records": records,
        "label": label,
        "label_target": "final_response",
        "target": {
            "final_response_index": final_index,
            "final_response": records[final_index]["output"],
        },
        "primary_evidence": {
            "record_index": final_index,
            "reason": "The final response determines the label.",
        },
        "spec_grounding": _spec_grounding(),
        "source": "self_instruct_candidate",
    }


def _manifest_row(candidate: dict[str, object], *, input_text: str | None = None, label: str | None = None) -> dict[str, object]:
    manifest_input = input_text if input_text is not None else builder.stable_json({"records": candidate["records"]})
    manifest_label = label if label is not None else str(candidate["label"])
    return {
        "sample_id": candidate["sample_id"],
        "input": manifest_input,
        "label": manifest_label,
        "source": "self_instruct_candidate",
        "label_source": "label",
        "template_id": "tmpl-test",
        "mutation_family": "base",
        "length_bin": "1-32",
        "input_token_count": builder.token_count(manifest_input),
        "format_version": builder.FORMAT_VERSION,
        "content_hash": builder.content_hash(manifest_input, manifest_label),
        "input_hash_no_label": builder.input_hash_no_label(manifest_input),
        "parse_status": "full_trajectory",
        "metadata_only": False,
        "prompt_schema_version": builder.PROMPT_SCHEMA_VERSION,
        "prompt_schema_hash": builder.prompt_schema_hash(),
        "family_component": "family-test",
        "group_id": "group-test",
        "split": "train",
        "path": "candidate.jsonl",
        "row": 1,
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class GateCManifestModelInputEquivalenceTests(unittest.TestCase):
    def _build_report(self, candidate: dict[str, object], manifest: dict[str, object]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            candidates_path = tmp / "candidates.jsonl"
            manifest_path = tmp / "manifest.jsonl"
            _write_jsonl(candidates_path, [candidate])
            _write_jsonl(manifest_path, [manifest])
            return gate_c.build_report(candidates_path, manifest_path)

    def test_passes_full_trajectory_manifest_and_trainer_loader_messages(self) -> None:
        candidate = _candidate()
        manifest = _manifest_row(candidate)

        report = self._build_report(candidate, manifest)

        self.assertTrue(report["overall_pass"], report["issues"])
        self.assertEqual(1, report["matched_count"])
        self.assertTrue(report["row_reports"][0]["checks"]["full_records_match"])
        self.assertTrue(report["row_reports"][0]["checks"]["content_hash_match"])
        self.assertTrue(report["trainer_loader"]["sample_id_set_match"])
        self.assertTrue(report["trainer_loader"]["rows"][0]["input_text_match"])
        self.assertTrue(report["trainer_loader"]["rows"][0]["label_match"])

    def test_fails_step_flattened_manifest_input(self) -> None:
        candidate = _candidate()
        flattened_input = builder.stable_json(candidate["records"][0])
        manifest = _manifest_row(candidate, input_text=flattened_input)

        report = self._build_report(candidate, manifest)

        self.assertFalse(report["overall_pass"])
        reasons = {issue["reason"] for issue in report["issues"]}
        self.assertIn("full_trajectory_input_missing", reasons)

    def test_fails_label_mismatch(self) -> None:
        candidate = _candidate(label="pass")
        manifest = _manifest_row(candidate, label="fail")

        report = self._build_report(candidate, manifest)

        self.assertFalse(report["overall_pass"])
        reasons = {issue["reason"] for issue in report["issues"]}
        self.assertIn("label_mismatch", reasons)

    def test_fails_hash_mismatch(self) -> None:
        candidate = _candidate()
        manifest = _manifest_row(candidate)
        manifest["input_hash_no_label"] = "bad-hash"

        report = self._build_report(candidate, manifest)

        self.assertFalse(report["overall_pass"])
        reasons = {issue["reason"] for issue in report["issues"]}
        self.assertIn("input_hash_no_label_mismatch", reasons)


if __name__ == "__main__":
    unittest.main()
