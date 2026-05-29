# Changed: add a cached-model executor for Self-Instruct judge requests.
# Why: instruct/judge filtering must run on server Qwen weights when external API keys are unavailable.
"""Execute Self-Instruct judge request JSONL with a cached Hugging Face model."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.datagen.self_instruct_llm_runner import (  # noqa: E402
    SelfInstructLLMRunnerError,
    build_hf_local_batch_text_generator,
    redact_text,
)


Json = Dict[str, Any]
JUDGE_REQUEST_SCHEMA_VERSION = "self_instruct.judge_request.v1"
JUDGE_RAW_OUTPUT_SCHEMA_VERSION = "self_instruct.judge_raw_output.v1"
JUDGE_LOCAL_RUNNER_REPORT_SCHEMA_VERSION = "self_instruct.judge_local_runner_report.v1"


class SelfInstructJudgeLocalRunnerError(ValueError):
    """Raised when local judge request execution cannot continue."""


def _now_kst() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).replace(microsecond=0).isoformat()


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise SelfInstructJudgeLocalRunnerError(f"line_{line_number}_not_object")
            yield line_number, payload


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_judge_request(row: Mapping[str, Any]) -> Json:
    # Changed: validate the judge request envelope before local model execution.
    # Why: cached Qwen should only consume requests produced by filter_self_instruct_judge.py.
    if row.get("schema_version") != JUDGE_REQUEST_SCHEMA_VERSION:
        raise SelfInstructJudgeLocalRunnerError("judge_request_schema_version_mismatch")
    request_id = row.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise SelfInstructJudgeLocalRunnerError("judge_request_id_missing")
    sample_id = row.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id:
        raise SelfInstructJudgeLocalRunnerError(f"{request_id}:sample_id_missing")
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise SelfInstructJudgeLocalRunnerError(f"{request_id}:payload_missing")
    messages = payload.get("messages")
    if not isinstance(messages, Sequence) or isinstance(messages, (bytes, bytearray, str)) or len(messages) == 0:
        raise SelfInstructJudgeLocalRunnerError(f"{request_id}:messages_missing")
    normalized = dict(row)
    normalized["payload"] = dict(payload)
    return normalized


def build_raw_judge_output_row(
    *,
    request: Mapping[str, Any],
    raw_output: str,
    provider_summary: Mapping[str, Any],
    created_at_kst: str,
) -> Json:
    return {
        "schema_version": JUDGE_RAW_OUTPUT_SCHEMA_VERSION,
        "request_id": request.get("request_id"),
        "request_schema_version": request.get("schema_version"),
        "sample_id": request.get("sample_id"),
        "source_instruction_id": request.get("source_instruction_id"),
        "classification_detection_id": request.get("classification_detection_id"),
        "created_at_kst": created_at_kst,
        "provider": "hf_local",
        "model": provider_summary.get("model") or request.get("payload", {}).get("model"),
        "payload_sha256": request.get("payload_sha256"),
        "judge_contract_version": request.get("judge_contract_version"),
        "raw_output": raw_output,
        "provider_response": {
            "finish_reason": provider_summary.get("finish_reason"),
            "usage": provider_summary.get("usage"),
        },
    }


def run_judge_requests_with_hf_model(
    requests: Sequence[Mapping[str, Any]],
    *,
    model_path: Path,
    output_path: Path,
    report_path: Path,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    device_map: str,
    torch_dtype: str,
    local_files_only: bool,
    batch_size: int,
    created_at_kst: Optional[str] = None,
) -> Json:
    # Changed: execute judge prompts through the same cached-model backend as generation.
    # Why: instruct filtering must not depend on QWEN_API_KEY or a vLLM API server.
    if max_new_tokens <= 0:
        raise SelfInstructJudgeLocalRunnerError("max_new_tokens_must_be_positive")
    if not 0.0 <= temperature <= 2.0:
        raise SelfInstructJudgeLocalRunnerError("temperature_out_of_range")
    if not 0.0 < top_p <= 1.0:
        raise SelfInstructJudgeLocalRunnerError("top_p_out_of_range")
    if batch_size <= 0:
        raise SelfInstructJudgeLocalRunnerError("batch_size_must_be_positive")

    timestamp = created_at_kst or _now_kst()
    validated_requests = [validate_judge_request(request) for request in requests]
    generator = build_hf_local_batch_text_generator(
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        device_map=device_map,
        torch_dtype=torch_dtype,
        local_files_only=local_files_only,
    )

    output_rows: List[Json] = []
    errors: List[Json] = []
    # Changed: stream judge raw outputs per batch.
    # Why: Qwen judge filtering for hundreds of candidates should leave partial inspectable artifacts.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_handle:
        for offset in range(0, len(validated_requests), batch_size):
            request_batch = validated_requests[offset : offset + batch_size]
            payloads = [request["payload"] for request in request_batch]
            try:
                generated_rows = generator(payloads)
            except (SelfInstructLLMRunnerError, RuntimeError, json.JSONDecodeError) as exc:
                reason = redact_text(str(exc))
                for request in request_batch:
                    errors.append({"request_id": request.get("request_id"), "sample_id": request.get("sample_id"), "reason": reason})
                continue
            if len(generated_rows) != len(request_batch):
                reason = f"batch_result_count_mismatch:{len(generated_rows)}!={len(request_batch)}"
                for request in request_batch:
                    errors.append({"request_id": request.get("request_id"), "sample_id": request.get("sample_id"), "reason": reason})
                continue
            for request, (raw_output, provider_summary) in zip(request_batch, generated_rows):
                output_row = build_raw_judge_output_row(
                    request=request,
                    raw_output=raw_output,
                    provider_summary=provider_summary,
                    created_at_kst=timestamp,
                )
                output_rows.append(output_row)
                output_handle.write(json.dumps(output_row, ensure_ascii=False, sort_keys=True) + "\n")
                output_handle.flush()

    report = {
        "schema_version": JUDGE_LOCAL_RUNNER_REPORT_SCHEMA_VERSION,
        "created_at_kst": timestamp,
        "provider": "hf_local",
        "model_path": str(model_path),
        "output_path": str(output_path),
        "request_count": len(validated_requests),
        "executed_count": len(output_rows),
        "failed_count": len(errors),
        "batch_size": batch_size,
        "status": "completed" if not errors else "completed_with_errors",
        "errors": errors,
    }
    _write_json(report, report_path)
    return report


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute Self-Instruct judge requests with a cached Hugging Face model.")
    parser.add_argument("--requests-jsonl", required=True, type=Path, help="Judge request JSONL from filter_self_instruct_judge.py.")
    parser.add_argument("--raw-output-jsonl", required=True, type=Path, help="Raw judge output JSONL for filter_self_instruct_judge.py.")
    parser.add_argument("--runner-report-json", required=True, type=Path, help="Local judge runner report JSON.")
    parser.add_argument("--local-model-path", required=True, type=Path, help="Cached Hugging Face CausalLM path.")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Max new tokens per judge request.")
    parser.add_argument("--temperature", type=float, default=0.0, help="Judge sampling temperature.")
    parser.add_argument("--top-p", type=float, default=1.0, help="Judge top-p.")
    parser.add_argument("--device-map", default="auto", help="Transformers device_map; use 'none' to omit.")
    parser.add_argument("--torch-dtype", default="auto", help="Torch dtype: auto, bfloat16, float16, or float32.")
    parser.add_argument("--batch-size", type=int, default=1, help="Number of judge prompts to decode in one batch.")
    parser.add_argument("--allow-download", action="store_true", help="Allow Hugging Face download if local files are incomplete.")
    parser.add_argument("--created-at-kst", default=None, help="Optional fixed KST timestamp.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        requests = [row for _line_number, row in _iter_jsonl(args.requests_jsonl)]
        run_judge_requests_with_hf_model(
            requests,
            model_path=args.local_model_path,
            output_path=args.raw_output_jsonl,
            report_path=args.runner_report_json,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            device_map=args.device_map,
            torch_dtype=args.torch_dtype,
            local_files_only=not args.allow_download,
            batch_size=args.batch_size,
            created_at_kst=args.created_at_kst,
        )
    except (OSError, json.JSONDecodeError, SelfInstructLLMRunnerError, SelfInstructJudgeLocalRunnerError) as exc:
        print(f"run_self_instruct_judge_local: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
