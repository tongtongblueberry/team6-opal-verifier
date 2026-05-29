# Changed: cover the env-gated Self-Instruct external LLM runner.
# Why: API execution must remain opt-in, redact secrets, and produce parser-compatible raw output.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from tools.datagen import parse_self_instruct_outputs as parser
from tools.datagen.self_instruct_candidate_schema import FIXED_OPAL_VERIFIER_INSTRUCTION
from tools.datagen import self_instruct_llm_runner as runner


def _request_row() -> dict[str, object]:
    return {
        "schema_version": "self_instruct.generation_request.v1",
        "request_id": "self-instruct-gen-test",
        "created_at_kst": "2026-05-26T18:00:00+09:00",
        "execute": False,
        "prompt_contract_version": "opal_final_response_spec_grounded_output_first.v2",
        "source_seed_sample_ids": ["seed-1"],
        "source_spec_rule_refs": ["RULE 01"],
        "candidates_per_request": 1,
        "payload_sha256": "payload-hash",
        "payload": {
            "model": "gpt-test",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "prompt_contract_version": "opal_final_response_spec_grounded_output_first.v2",
        },
    }


def _record(method: str, status: str) -> dict[str, object]:
    return {
        # Changed: fake LLM output now satisfies the strict raw-input parser gate.
        # Why: null input values and bare method args are rejected before normalization.
        "input": {
            "method": {"name": method, "args": {"required": {"HostSessionID": "00000001"}, "optional": {}}},
            "invoking_id": {"uid": "00 00 00 06 00 00 00 01"},
            "status_codes": ["SUCCESS"],
        },
        "output": {"status_codes": status, "return_values": []},
    }


def _candidate() -> dict[str, object]:
    records = [_record("Get", "SUCCESS")]
    return {
        "sample_id": "si-runner-ok",
        "instruction": FIXED_OPAL_VERIFIER_INSTRUCTION,
        "records": records,
        "label": "pass",
        "label_target": "final_response",
        "target": {
            "final_response_index": 0,
            "final_response": records[0]["output"],
        },
        "primary_evidence": {
            "record_index": 0,
            "reason": "The final response determines the label.",
        },
        "spec_grounding": [
            {
                "rule_ref": "RULE 01",
                "source_path": "docs/legacy_spec_rules.md",
                "source_span": "docs/legacy_spec_rules.md:10-15",
                "condition": "A method is processed completely and without error by the TPer",
                "expected_status": "SUCCESS (0x00)",
            }
        ],
    }


class SelfInstructLLMRunnerTests(unittest.TestCase):
    def test_missing_env_skips_without_writing_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "raw_outputs.jsonl"
            report = runner.run_generation_requests(
                [_request_row()],
                provider="openai",
                output_path=output_path,
                env={},
                created_at_kst="2026-05-26T18:00:00+09:00",
            )

            self.assertEqual("skipped_missing_env", report["status"])
            self.assertEqual(0, report["executed_count"])
            self.assertEqual(1, report["skipped_count"])
            self.assertEqual("OPENAI_API_KEY", report["provider_env_var"])
            self.assertFalse(output_path.exists())

    def test_load_generation_requests_validates_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request_path = Path(tmpdir) / "requests.jsonl"
            request_path.write_text(json.dumps(_request_row()) + "\n", encoding="utf-8")

            rows = runner.load_generation_requests(request_path)

            self.assertEqual(1, len(rows))
            self.assertEqual("self-instruct-gen-test", rows[0]["request_id"])
            self.assertEqual("gpt-test", rows[0]["payload"]["model"])

    def test_redacts_provider_secrets_and_header_values(self) -> None:
        redacted = runner.redact_text(
            'plain=sk-live gem=gm-live qwen=qw-live dash=ds-live Authorization: Bearer sk-live "x-goog-api-key": "gm-live" https://x.test?key=query-secret',
            env={
                "OPENAI_API_KEY": "sk-live",
                "GEMINI_API_KEY": "gm-live",
                "QWEN_API_KEY": "qw-live",
                "DASHSCOPE_API_KEY": "ds-live",
            },
        )

        self.assertNotIn("sk-live", redacted)
        self.assertNotIn("gm-live", redacted)
        self.assertNotIn("qw-live", redacted)
        self.assertNotIn("ds-live", redacted)
        self.assertNotIn("query-secret", redacted)
        self.assertIn("[REDACTED:OPENAI_API_KEY]", redacted)
        self.assertIn("[REDACTED:GEMINI_API_KEY]", redacted)
        self.assertIn("[REDACTED:QWEN_API_KEY]", redacted)
        self.assertIn("[REDACTED:DASHSCOPE_API_KEY]", redacted)

    # Changed: use a fake transport to validate success output without making a network call.
    # Why: unit tests must prove parser compatibility while keeping paid API execution disabled.
    def test_success_output_schema_feeds_raw_parser(self) -> None:
        def fake_transport(
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: int,
        ) -> Mapping[str, Any]:
            self.assertEqual("https://api.openai.com/v1/chat/completions", url)
            self.assertEqual("Bearer sk-test", headers["Authorization"])
            self.assertNotIn("prompt_contract_version", body)
            self.assertEqual(30, timeout_seconds)
            return {
                "id": "chatcmpl-test",
                "model": body["model"],
                "choices": [
                    {
                        "message": {"content": json.dumps({"candidates": [_candidate()]})},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 11},
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "raw_outputs.jsonl"
            report = runner.run_generation_requests(
                [_request_row()],
                provider="openai",
                output_path=output_path,
                env={"OPENAI_API_KEY": "sk-test"},
                timeout_seconds=30,
                created_at_kst="2026-05-26T18:00:00+09:00",
                transport=fake_transport,
            )

            self.assertEqual("completed", report["status"])
            self.assertEqual(1, report["executed_count"])
            row = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual("self_instruct.llm_raw_output.v1", row["schema_version"])
            self.assertEqual("self-instruct-gen-test", row["request_id"])
            self.assertEqual("openai", row["provider"])
            self.assertEqual("payload-hash", row["payload_sha256"])
            self.assertIn("raw_output", row)

            accepted, rejected = parser.parse_raw_output_rows([(1, row)])
            self.assertEqual([], rejected)
            self.assertEqual(["si-runner-ok"], [candidate["sample_id"] for candidate in accepted])

    def test_qwen_uses_openai_compatible_base_url(self) -> None:
        # Changed: prove Qwen execution can target a server-side OpenAI-compatible API.
        # Why: Qwen may be served by DashScope or by a private vLLM endpoint.
        def fake_transport(
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: int,
        ) -> Mapping[str, Any]:
            self.assertEqual("http://qwen-server.example:8000/v1/chat/completions", url)
            self.assertEqual("Bearer qw-test", headers["Authorization"])
            self.assertEqual("qwen-plus", body["model"])
            return {
                "id": "qwen-test",
                "model": body["model"],
                "choices": [
                    {
                        "message": {"content": json.dumps({"candidates": [_candidate()]})},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 13},
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "raw_outputs.jsonl"
            request = _request_row()
            request["payload"]["model"] = "qwen-plus"
            report = runner.run_generation_requests(
                [request],
                provider="qwen",
                output_path=output_path,
                env={"QWEN_API_KEY": "qw-test", "QWEN_BASE_URL": "http://qwen-server.example:8000/v1"},
                timeout_seconds=30,
                created_at_kst="2026-05-26T18:00:00+09:00",
                transport=fake_transport,
            )

            self.assertEqual("completed", report["status"])
            self.assertEqual("QWEN_API_KEY", report["provider_env_var"])
            self.assertEqual("QWEN_BASE_URL", report["provider_base_url_env_var"])
            row = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual("qwen", row["provider"])
            self.assertEqual("qwen-plus", row["model"])

    def test_qwen_accepts_dashscope_api_key_fallback(self) -> None:
        # Changed: accept DashScope's native API key env var for Qwen.
        # Why: Qwen-compatible API keys are commonly provided as DASHSCOPE_API_KEY.
        def fake_transport(
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: int,
        ) -> Mapping[str, Any]:
            self.assertEqual("Bearer ds-test", headers["Authorization"])
            return {
                "id": "dashscope-test",
                "model": body["model"],
                "choices": [
                    {
                        "message": {"content": json.dumps({"candidates": [_candidate()]})},
                        "finish_reason": "stop",
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "raw_outputs.jsonl"
            request = _request_row()
            request["payload"]["model"] = "qwen-plus"
            report = runner.run_generation_requests(
                [request],
                provider="qwen",
                output_path=output_path,
                env={"DASHSCOPE_API_KEY": "ds-test"},
                created_at_kst="2026-05-26T18:00:00+09:00",
                transport=fake_transport,
            )

            self.assertEqual("completed", report["status"])
            self.assertEqual("DASHSCOPE_API_KEY", report["provider_env_var"])
            self.assertEqual(["QWEN_API_KEY", "DASHSCOPE_API_KEY"], report["provider_env_var_candidates"])

    def test_hf_local_runner_writes_parser_compatible_raw_output(self) -> None:
        # Changed: cover cached-model execution without loading a real model in tests.
        # Why: server Qwen weights should use the same raw-output parser path as API generation.
        def fake_generator(payload: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
            self.assertEqual("gpt-test", payload["model"])
            return json.dumps({"candidates": [_candidate()]}), {
                "model": "/cached/qwen",
                "finish_reason": "stop",
                "usage": {"total_tokens": 17},
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "raw_outputs.jsonl"
            report = runner.run_generation_requests_with_hf_model(
                [_request_row()],
                model_path=Path("/cached/qwen"),
                output_path=output_path,
                created_at_kst="2026-05-26T18:00:00+09:00",
                text_generator=fake_generator,
            )

            self.assertEqual("completed", report["status"])
            self.assertEqual("hf_local", report["provider"])
            self.assertEqual("/cached/qwen", report["model_path"])
            row = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual("qwen", row["provider"])
            self.assertEqual("/cached/qwen", row["model"])
            accepted, rejected = parser.parse_raw_output_rows([(1, row)])
            self.assertEqual([], rejected)
            self.assertEqual(["si-runner-ok"], [candidate["sample_id"] for candidate in accepted])


if __name__ == "__main__":
    unittest.main()
