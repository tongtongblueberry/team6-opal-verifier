# Changed: test Self-Instruct candidate dedup/filter gates.
# Why: duplicate, conflicting, and public20-overlapping rows must be removed before quality audit and training.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.analysis import dedup_self_instruct_candidates as dedup


def _record(method: str, status: str) -> dict[str, object]:
    return {
        "input": {"method": {"name": method}},
        "output": {"status_codes": status, "return_values": []},
    }


def _candidate(
    sample_id: str,
    label: str,
    records: list[dict[str, object]],
    instruction: str = "Judge only the final response.",
) -> dict[str, object]:
    final_index = len(records) - 1
    return {
        "sample_id": sample_id,
        "instruction": instruction,
        "records": records,
        "label": label,
        "label_target": "final_response",
        "target": {
            "final_response_index": final_index,
            "final_response": records[-1]["output"],
        },
        "primary_evidence": {
            "record_index": final_index,
            "reason": "The final response determines the label.",
        },
    }


class DedupSelfInstructCandidatesTests(unittest.TestCase):
    def test_rejects_same_input_conflicting_label(self) -> None:
        records = [_record("Set", "INVALID_PARAMETER")]
        candidates = [
            _candidate("si-conflict-pass", "pass", records, "Check final Opal response A."),
            _candidate("si-conflict-fail", "fail", records, "Check final Opal response B."),
        ]

        accepted, rejected = dedup.dedup_candidates(candidates)

        self.assertEqual(["si-conflict-pass"], [row["sample_id"] for row in accepted])
        self.assertEqual(1, len(rejected))
        self.assertEqual("same_input_conflicting_label", rejected[0]["reason"])
        self.assertEqual("fail", rejected[0]["details"]["current_label"])

    def test_rejects_near_duplicate_instruction_at_threshold(self) -> None:
        candidates = [
            _candidate(
                "si-near-1",
                "pass",
                [_record("Get", "SUCCESS")],
                "Judge the final response for this Opal session.",
            ),
            _candidate(
                "si-near-2",
                "pass",
                [_record("Properties", "SUCCESS")],
                "Judge final response for this Opal session.",
            ),
        ]

        accepted, rejected = dedup.dedup_candidates(candidates, rouge_l_threshold=0.7)

        self.assertEqual(["si-near-1"], [row["sample_id"] for row in accepted])
        self.assertEqual("near_duplicate_instruction", rejected[0]["reason"])
        self.assertGreaterEqual(rejected[0]["details"]["rouge_l"], 0.7)

    def test_rejects_exact_duplicate(self) -> None:
        candidate = _candidate("si-dup-1", "pass", [_record("Get", "SUCCESS")])
        duplicate = dict(candidate)
        duplicate["sample_id"] = "si-dup-2"

        accepted, rejected = dedup.dedup_candidates([candidate, duplicate])

        self.assertEqual(["si-dup-1"], [row["sample_id"] for row in accepted])
        self.assertEqual("exact_duplicate", rejected[0]["reason"])
        self.assertEqual("si-dup-1", rejected[0]["details"]["previous_sample_id"])

    def test_public20_duplicate_check_rejects_exact_reference_match(self) -> None:
        records = [_record("Properties", "SUCCESS")]
        candidate = _candidate("si-public-dup", "pass", records)
        public20 = [
            {
                "sample_id": "tc1",
                "input": json.dumps({"records": records}),
                "source": "public20_input_only",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            public_path = Path(tmpdir) / "public20.jsonl"
            public_path.write_text("\n".join(json.dumps(row) for row in public20) + "\n", encoding="utf-8")
            references = dedup.load_public20_reference(public_path)

            accepted, rejected = dedup.dedup_candidates([candidate], public20_references=references)

        self.assertEqual([], accepted)
        self.assertEqual("public20_exact_duplicate", rejected[0]["reason"])
        self.assertEqual("tc1", rejected[0]["details"]["public20_sample_id"])

    def test_cli_writes_outputs_and_report(self) -> None:
        first = _candidate("si-cli-1", "pass", [_record("Get", "SUCCESS")], "Unique instruction one.")
        duplicate = dict(first)
        duplicate["sample_id"] = "si-cli-2"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "candidates.jsonl"
            output_path = tmp / "accepted.jsonl"
            reject_path = tmp / "rejects.jsonl"
            report_path = tmp / "report.json"
            input_path.write_text(
                "\n".join(json.dumps(row) for row in [first, duplicate]) + "\n",
                encoding="utf-8",
            )

            exit_code = dedup.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--reject-output",
                    str(reject_path),
                    "--report-json",
                    str(report_path),
                ]
            )

            self.assertEqual(0, exit_code)
            accepted = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            rejected = [json.loads(line) for line in reject_path.read_text(encoding="utf-8").splitlines()]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(accepted))
            self.assertEqual("exact_duplicate", rejected[0]["reason"])
            self.assertEqual(1, report["accepted_count"])
            self.assertEqual(1, report["rejected_count"])


if __name__ == "__main__":
    unittest.main()
