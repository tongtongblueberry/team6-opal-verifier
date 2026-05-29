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


# Changed: build compact request-only target schedule rows for generation CLI tests.
# Why: schedule tests should exercise request metadata without creating raw candidates or using public labels.
def _schedule_target(
    label: str,
    record_count: int,
    *,
    rule_ref: str = "RULE 01",
    final_method: str = "Get",
    final_status: str = "SUCCESS",
    required_context_domains: list[str] | None = None,
) -> dict[str, object]:
    length_bin = "33-64" if record_count > 32 else "1-32"
    row: dict[str, object] = {
        "target_label": label,
        "target_record_count": record_count,
        "target_length_bin": length_bin,
        "target_final_method": final_method,
        "target_final_status": final_status,
        "allowed_source_rule_refs": [rule_ref],
    }
    if required_context_domains is not None:
        row["required_context_domains"] = required_context_domains
    return row


class RunSelfInstructGenerationTests(unittest.TestCase):
    def test_cli_writes_dry_run_request_payload_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            request_path = tmp / "requests.jsonl"
            metadata_path = tmp / "metadata.json"
            instruction_artifact_path = tmp / "instructions.jsonl"
            classification_artifact_path = tmp / "classification.jsonl"
            seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")

            exit_code = generation.main(
                [
                    "--seed-jsonl",
                    str(seed_path),
                    "--requests-output",
                    str(request_path),
                    "--metadata-json",
                    str(metadata_path),
                    "--instruction-artifact-output",
                    str(instruction_artifact_path),
                    "--classification-artifact-output",
                    str(classification_artifact_path),
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
            instruction_rows = [json.loads(line) for line in instruction_artifact_path.read_text(encoding="utf-8").splitlines()]
            classification_rows = [json.loads(line) for line in classification_artifact_path.read_text(encoding="utf-8").splitlines()]
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(rows))
            self.assertEqual(1, len(instruction_rows))
            self.assertEqual(1, len(classification_rows))
            self.assertFalse(rows[0]["execute"])
            self.assertFalse(metadata["execute"])
            self.assertEqual("instance_generation", rows[0]["official_stage"])
            self.assertEqual("self-instruct-instruction-00000", rows[0]["source_instruction_id"])
            self.assertEqual("self-instruct-clf-00000", rows[0]["classification_detection_id"])
            self.assertEqual("instruction_generation", instruction_rows[0]["official_stage"])
            self.assertFalse(instruction_rows[0]["machine_generated_by_llm"])
            self.assertTrue(classification_rows[0]["is_classification"])
            self.assertTrue(classification_rows[0]["audited_noop"])
            self.assertEqual("opal_final_response_spec_grounded_output_first.v2", rows[0]["prompt_contract_version"])
            self.assertNotIn("candidate_targets", rows[0])
            self.assertNotIn("candidate_targets", rows[0]["payload"])
            self.assertEqual(["tc1"], rows[0]["source_seed_sample_ids"])
            self.assertIn("RULE 01", rows[0]["source_spec_rule_refs"])
            self.assertEqual("docs/legacy_spec_rules.md", rows[0]["payload"]["spec_rule_context"][0]["source_path"])
            prompt_text = rows[0]["payload"]["messages"][1]["content"]
            self.assertIn("choose target_label as pass or fail", prompt_text)
            self.assertIn("final pair (cN, rN)", prompt_text)
            self.assertIn("target.final_response_index", prompt_text)
            self.assertIn("spec_grounding", prompt_text)
            self.assertIn("source_span", prompt_text)
            self.assertIn("source_text", prompt_text)
            self.assertIn("source_instruction_id", prompt_text)
            self.assertIn("classification_detection_artifact", prompt_text)
            self.assertEqual(2, json.loads(prompt_text)["candidate_count"])
            self.assertNotIn("public_label", json.dumps(rows[0]["payload"]["seed_profile_context"]))
            self.assertTrue(metadata["spec_rules_input"].endswith("docs/legacy_spec_rules.md"))
            self.assertEqual(
                "machine_generated_instructions.jsonl",
                metadata["artifacts"]["instruction_generation"]["official_counterpart"],
            )

    # Changed: verify target schedules are request-order payload guidance, not downstream generated data.
    # Why: external generation needs deterministic quotas while parser/dedup/judge/Gate A/B/C stay unchanged.
    def test_cli_writes_target_schedule_into_payload_prompt_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            request_path = tmp / "requests.jsonl"
            second_request_path = tmp / "requests.second.jsonl"
            metadata_path = tmp / "metadata.json"
            second_metadata_path = tmp / "metadata.second.json"
            schedule_path = tmp / "target_schedule.json"
            seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")
            schedule = {
                "targets": [
                    _schedule_target("pass", 1, rule_ref="RULE 01", final_method="Properties"),
                    _schedule_target(
                        "fail",
                        39,
                        rule_ref="RULE 21",
                        final_method="Set",
                        final_status="NOT_AUTHORIZED",
                        required_context_domains=["Locking"],
                    ),
                    _schedule_target("fail", 20, rule_ref="RULE 22", final_method="Set", final_status="INVALID_PARAMETER"),
                    _schedule_target("pass", 33, rule_ref="RULE 86", final_method="Next"),
                ]
            }
            schedule_path.write_text(json.dumps(schedule), encoding="utf-8")

            args = [
                "--seed-jsonl",
                str(seed_path),
                "--target-schedule-json",
                str(schedule_path),
                "--request-count",
                "2",
                "--seeds-per-request",
                "1",
                "--spec-rules-per-request",
                "1",
                "--candidates-per-request",
                "2",
                "--created-at-kst",
                "2026-05-26T18:00:00+09:00",
            ]

            exit_code = generation.main(
                args
                + [
                    "--requests-output",
                    str(request_path),
                    "--metadata-json",
                    str(metadata_path),
                ]
            )
            second_exit_code = generation.main(
                args
                + [
                    "--requests-output",
                    str(second_request_path),
                    "--metadata-json",
                    str(second_metadata_path),
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertEqual(0, second_exit_code)
            rows = [json.loads(line) for line in request_path.read_text(encoding="utf-8").splitlines()]
            second_rows = [json.loads(line) for line in second_request_path.read_text(encoding="utf-8").splitlines()]
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(2, len(rows))
            self.assertEqual([0, 1], [target["target_index"] for target in rows[0]["payload"]["candidate_targets"]])
            self.assertEqual([2, 3], [target["target_index"] for target in rows[1]["payload"]["candidate_targets"]])
            self.assertEqual(["pass", "fail"], [target["target_label"] for target in rows[0]["payload"]["candidate_targets"]])
            self.assertEqual([20, 33], [target["target_record_count"] for target in rows[1]["payload"]["candidate_targets"]])
            self.assertEqual(rows[0]["payload"]["candidate_targets"], rows[0]["candidate_targets"])
            self.assertEqual(
                rows[0]["payload"]["candidate_targets"],
                second_rows[0]["payload"]["candidate_targets"],
            )
            self.assertEqual(rows[0]["payload_sha256"], second_rows[0]["payload_sha256"])
            self.assertIn("RULE 21", rows[0]["source_spec_rule_refs"])
            self.assertIn("RULE 86", rows[1]["source_spec_rule_refs"])
            prompt = json.loads(rows[0]["payload"]["messages"][1]["content"])
            self.assertEqual(
                rows[0]["payload"]["candidate_targets"],
                [
                    {
                        key: value
                        for key, value in target.items()
                        if key not in {"candidate_index", "required_record_count", "required_sample_id"}
                    }
                    for target in prompt["candidate_target_schedule"]["candidate_targets"]
                ],
            )
            self.assertIn("records[-1].output", json.dumps(prompt["candidate_target_schedule"]))
            self.assertIn("required_context_domains", json.dumps(prompt["candidate_target_schedule"]))
            self.assertNotIn("public_label", json.dumps(rows))
            self.assertNotIn("gold_label", json.dumps(rows))
            self.assertEqual({"fail": 2, "pass": 2}, metadata["target_schedule"]["summary"]["label_counts"])

    # Changed: reject malformed target schedules before any request artifact is written.
    # Why: schedule inputs must not smuggle unknown labels, public labels, gold outputs, or invalid rule refs into prompts.
    def test_rejects_invalid_target_schedule(self) -> None:
        bad_schedules = [
            {"targets": [_schedule_target("maybe", 1)]},
            {"targets": [_schedule_target("pass", 0)]},
            {"targets": [_schedule_target("pass", 1, rule_ref="RULE 1")]},
            {"targets": [{**_schedule_target("pass", 1), "public_label": "pass"}]},
            {"targets": [_schedule_target("pass", 1), _schedule_target("fail", 3)]},
        ]
        for index, schedule in enumerate(bad_schedules):
            with self.subTest(index=index):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp = Path(tmpdir)
                    seed_path = tmp / "seeds.jsonl"
                    request_path = tmp / "requests.jsonl"
                    metadata_path = tmp / "metadata.json"
                    schedule_path = tmp / "target_schedule.json"
                    seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")
                    schedule_path.write_text(json.dumps(schedule), encoding="utf-8")

                    exit_code = generation.main(
                        [
                            "--seed-jsonl",
                            str(seed_path),
                            "--requests-output",
                            str(request_path),
                            "--metadata-json",
                            str(metadata_path),
                            "--target-schedule-json",
                            str(schedule_path),
                            "--request-count",
                            "1",
                            "--candidates-per-request",
                            "1",
                        ]
                    )

                    self.assertEqual(2, exit_code)
                    self.assertFalse(request_path.exists())

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

    def test_execute_local_model_path_does_not_require_provider_env(self) -> None:
        # Changed: local cached-model execution is independent from provider API keys.
        # Why: server Qwen weights must be usable when QWEN/DashScope env vars are absent.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            seed_path = tmp / "seeds.jsonl"
            seed_path.write_text(json.dumps(_seed_row()) + "\n", encoding="utf-8")

            def fake_local_runner(requests, **kwargs):
                self.assertEqual(Path("/cached/qwen"), kwargs["model_path"])
                self.assertEqual(123, kwargs["max_new_tokens"])
                return {
                    "schema_version": "self_instruct.llm_runner_report.v1",
                    "status": "completed",
                    "provider": "hf_local",
                    "executed_count": len(requests),
                    "skipped_count": 0,
                    "failed_count": 0,
                    "errors": [],
                }

            with patch.dict(os.environ, {}, clear=True), patch.object(
                generation,
                "run_generation_requests_with_hf_model",
                side_effect=fake_local_runner,
            ):
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
                        "--local-model-path",
                        "/cached/qwen",
                        "--local-model-max-new-tokens",
                        "123",
                    ]
                )

            self.assertEqual(0, exit_code)
            runner_report = json.loads((tmp / "runner_report.json").read_text(encoding="utf-8"))
            self.assertEqual("hf_local", runner_report["provider"])
            self.assertEqual("completed", runner_report["status"])


if __name__ == "__main__":
    unittest.main()
