# Changed: add a provider-gated external LLM runner for Self-Instruct generation requests.
# Why: spec-grounded generation needs an optional execution lane without storing API secrets or bypassing raw-output parsing gates.
"""Execute Self-Instruct generation request payloads with external LLM providers.

The runner is intentionally stdlib-only. It reads secrets only from environment
variables, never writes them to artifacts, and writes successful provider text
into a raw JSONL schema accepted by ``tools/datagen/parse_self_instruct_outputs.py``.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


Json = Dict[str, Any]
GENERATION_REQUEST_SCHEMA_VERSION = "self_instruct.generation_request.v1"
RAW_OUTPUT_SCHEMA_VERSION = "self_instruct.llm_raw_output.v1"
RUNNER_REPORT_SCHEMA_VERSION = "self_instruct.llm_runner_report.v1"
SUPPORTED_PROVIDERS = ("openai", "gemini")
PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"
HTTP_TRANSPORT = Callable[[str, Mapping[str, str], Mapping[str, Any], int], Mapping[str, Any]]


class SelfInstructLLMRunnerError(ValueError):
    """Raised when request loading or provider execution cannot continue safely."""


def _now_kst() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).replace(microsecond=0).isoformat()


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise SelfInstructLLMRunnerError(f"unsupported_provider:{provider}")
    return normalized


def provider_env_var(provider: str) -> str:
    return PROVIDER_ENV_VARS[normalize_provider(provider)]


# Changed: centralize provider-secret redaction for errors and diagnostic strings.
# Why: API keys must remain environment-only and must not leak through stderr, reports, or test failures.
def redact_text(text: str, env: Optional[Mapping[str, str]] = None) -> str:
    redacted = str(text)
    source_env = os.environ if env is None else env
    for env_name in PROVIDER_ENV_VARS.values():
        value = source_env.get(env_name)
        if value:
            redacted = redacted.replace(value, f"[REDACTED:{env_name}]")

    substitutions: Sequence[Tuple[str, str]] = (
        (r"(Authorization:\s*Bearer\s+)[^\s\"',}]+", r"\1[REDACTED]"),
        (r'("Authorization"\s*:\s*"Bearer\s+)[^"]+(")', r"\1[REDACTED]\2"),
        (r"(x-goog-api-key:\s*)[^\s\"',}]+", r"\1[REDACTED]"),
        (r'("x-goog-api-key"\s*:\s*")[^"]+(")', r"\1[REDACTED]\2"),
        (r"([?&]key=)[^&\s\"']+", r"\1[REDACTED]"),
    )
    for pattern, replacement in substitutions:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    return redacted


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


# Changed: validate external-runner input as generation requests, not arbitrary JSON.
# Why: a paid API call must only consume request artifacts produced by the spec-grounded request builder.
def validate_generation_request(row: Mapping[str, Any]) -> Json:
    if row.get("schema_version") != GENERATION_REQUEST_SCHEMA_VERSION:
        raise SelfInstructLLMRunnerError("request_schema_version_mismatch")
    request_id = row.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise SelfInstructLLMRunnerError("request_id_missing")
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise SelfInstructLLMRunnerError(f"{request_id}:payload_missing")
    messages = payload.get("messages")
    if not isinstance(messages, Sequence) or isinstance(messages, (bytes, bytearray, str)) or len(messages) == 0:
        raise SelfInstructLLMRunnerError(f"{request_id}:messages_missing")
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise SelfInstructLLMRunnerError(f"{request_id}:model_missing")
    return dict(row)


def load_generation_requests(path: Path) -> List[Json]:
    rows: List[Json] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, Mapping):
                raise SelfInstructLLMRunnerError(f"line_{line_number}_not_object")
            try:
                rows.append(validate_generation_request(payload))
            except SelfInstructLLMRunnerError as exc:
                raise SelfInstructLLMRunnerError(f"line_{line_number}:{exc}") from exc
    return rows


def _post_json(
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    timeout_seconds: int,
) -> Mapping[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise SelfInstructLLMRunnerError(f"http_error:{exc.code}:{error_body}") from exc
    except urllib.error.URLError as exc:
        raise SelfInstructLLMRunnerError(f"url_error:{exc.reason}") from exc
    payload = json.loads(response_body)
    if not isinstance(payload, Mapping):
        raise SelfInstructLLMRunnerError("provider_response_not_object")
    return payload


def _openai_body(payload: Mapping[str, Any]) -> Json:
    allowed_keys = (
        "model",
        "messages",
        "temperature",
        "response_format",
        "max_tokens",
        "max_completion_tokens",
        "top_p",
        "seed",
    )
    return {key: payload[key] for key in allowed_keys if key in payload}


def _content_part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, Mapping):
        value = part.get("text")
        if isinstance(value, str):
            return value
    return ""


def _extract_openai_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (bytes, bytearray, str)) or not choices:
        raise SelfInstructLLMRunnerError("openai_choices_missing")
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise SelfInstructLLMRunnerError("openai_choice_not_object")
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise SelfInstructLLMRunnerError("openai_message_missing")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(content, (bytes, bytearray, str)):
        text = "".join(_content_part_text(part) for part in content)
        if text:
            return text
    raise SelfInstructLLMRunnerError("openai_content_missing")


def _openai_finish_reason(response: Mapping[str, Any]) -> Optional[str]:
    choices = response.get("choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (bytes, bytearray, str)) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        return None
    finish_reason = first_choice.get("finish_reason")
    return finish_reason if isinstance(finish_reason, str) else None


def _gemini_model_path(model: str) -> str:
    stripped = model.strip()
    return stripped if stripped.startswith("models/") else f"models/{stripped}"


def _gemini_contents(messages: Sequence[Any]) -> Tuple[Optional[Json], List[Json]]:
    system_parts: List[Json] = []
    contents: List[Json] = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise SelfInstructLLMRunnerError("gemini_message_not_object")
        role = str(message.get("role", "user")).strip().lower()
        content = message.get("content")
        if not isinstance(content, str):
            raise SelfInstructLLMRunnerError("gemini_message_content_not_string")
        if role == "system":
            system_parts.append({"text": content})
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})
    system_instruction = {"parts": system_parts} if system_parts else None
    if not contents:
        raise SelfInstructLLMRunnerError("gemini_user_content_missing")
    return system_instruction, contents


def _gemini_body(payload: Mapping[str, Any]) -> Json:
    messages = payload.get("messages")
    if not isinstance(messages, Sequence) or isinstance(messages, (bytes, bytearray, str)):
        raise SelfInstructLLMRunnerError("gemini_messages_missing")
    system_instruction, contents = _gemini_contents(messages)
    body: Json = {
        "contents": contents,
        "generationConfig": {
            "temperature": payload.get("temperature", 0.7),
        },
    }
    response_format = payload.get("response_format")
    if isinstance(response_format, Mapping) and response_format.get("type") == "json_object":
        body["generationConfig"]["responseMimeType"] = "application/json"
    if system_instruction is not None:
        body["systemInstruction"] = system_instruction
    return body


def _extract_gemini_text(response: Mapping[str, Any]) -> str:
    candidates = response.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (bytes, bytearray, str)) or not candidates:
        raise SelfInstructLLMRunnerError("gemini_candidates_missing")
    first_candidate = candidates[0]
    if not isinstance(first_candidate, Mapping):
        raise SelfInstructLLMRunnerError("gemini_candidate_not_object")
    content = first_candidate.get("content")
    if not isinstance(content, Mapping):
        raise SelfInstructLLMRunnerError("gemini_content_missing")
    parts = content.get("parts")
    if not isinstance(parts, Sequence) or isinstance(parts, (bytes, bytearray, str)):
        raise SelfInstructLLMRunnerError("gemini_parts_missing")
    text = "".join(_content_part_text(part) for part in parts)
    if not text:
        raise SelfInstructLLMRunnerError("gemini_text_missing")
    return text


def _gemini_finish_reason(response: Mapping[str, Any]) -> Optional[str]:
    candidates = response.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (bytes, bytearray, str)) or not candidates:
        return None
    first_candidate = candidates[0]
    if not isinstance(first_candidate, Mapping):
        return None
    finish_reason = first_candidate.get("finishReason")
    return finish_reason if isinstance(finish_reason, str) else None


# Changed: keep provider-specific HTTP mechanics behind a single call surface.
# Why: generation CLI should remain provider-agnostic and avoid scattering secret/header handling.
def call_provider(
    *,
    provider: str,
    payload: Mapping[str, Any],
    api_key: str,
    timeout_seconds: int,
    transport: Optional[HTTP_TRANSPORT] = None,
) -> Tuple[str, Mapping[str, Any], Json]:
    normalized_provider = normalize_provider(provider)
    post = _post_json if transport is None else transport
    if normalized_provider == "openai":
        response = post(
            OPENAI_CHAT_COMPLETIONS_URL,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            _openai_body(payload),
            timeout_seconds,
        )
        text = _extract_openai_text(response)
        summary = {
            "id": response.get("id") if isinstance(response.get("id"), str) else None,
            "model": response.get("model") if isinstance(response.get("model"), str) else payload.get("model"),
            "finish_reason": _openai_finish_reason(response),
            "usage": response.get("usage") if isinstance(response.get("usage"), Mapping) else None,
        }
        return text, response, summary

    model = str(payload.get("model", "")).strip()
    model_path = _gemini_model_path(model)
    response = post(
        GEMINI_GENERATE_CONTENT_URL.format(model=urllib.parse.quote(model_path, safe="/")),
        {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        _gemini_body(payload),
        timeout_seconds,
    )
    text = _extract_gemini_text(response)
    summary = {
        "id": None,
        "model": model_path,
        "finish_reason": _gemini_finish_reason(response),
        "usage": response.get("usageMetadata") if isinstance(response.get("usageMetadata"), Mapping) else None,
    }
    return text, response, summary


# Changed: write successful provider text in the parser-compatible raw_output wrapper schema.
# Why: raw LLM output must pass through parse_self_instruct_outputs and candidate_schema before judge/Gate A/B/C.
def build_raw_output_row(
    *,
    request: Mapping[str, Any],
    provider: str,
    raw_output: str,
    provider_summary: Mapping[str, Any],
    created_at_kst: str,
) -> Json:
    return {
        "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
        "request_id": request.get("request_id"),
        "request_schema_version": request.get("schema_version"),
        "created_at_kst": created_at_kst,
        "provider": normalize_provider(provider),
        "model": provider_summary.get("model") or request.get("payload", {}).get("model"),
        "payload_sha256": request.get("payload_sha256"),
        "prompt_contract_version": request.get("prompt_contract_version"),
        "source_seed_sample_ids": request.get("source_seed_sample_ids"),
        "source_spec_rule_refs": request.get("source_spec_rule_refs"),
        "raw_output": raw_output,
        "provider_response": {
            "id": provider_summary.get("id"),
            "finish_reason": provider_summary.get("finish_reason"),
            "usage": provider_summary.get("usage"),
        },
    }


def _empty_report(
    *,
    provider: str,
    env_var: str,
    output_path: Path,
    created_at_kst: str,
    status: str,
    request_count: int,
) -> Json:
    return {
        "schema_version": RUNNER_REPORT_SCHEMA_VERSION,
        "created_at_kst": created_at_kst,
        "provider": provider,
        "provider_env_var": env_var,
        "output_path": str(output_path),
        "status": status,
        "request_count": request_count,
        "executed_count": 0,
        "skipped_count": request_count,
        "failed_count": 0,
        "errors": [],
    }


# Changed: require both explicit execution and provider env before any network call.
# Why: paid external generation must not happen accidentally during no-network dry-run workflows.
def run_generation_requests(
    requests: Sequence[Mapping[str, Any]],
    *,
    provider: str,
    output_path: Path,
    env: Optional[Mapping[str, str]] = None,
    timeout_seconds: int = 120,
    created_at_kst: Optional[str] = None,
    transport: Optional[HTTP_TRANSPORT] = None,
) -> Json:
    normalized_provider = normalize_provider(provider)
    env_var = provider_env_var(normalized_provider)
    source_env = os.environ if env is None else env
    timestamp = created_at_kst or _now_kst()
    validated_requests = [validate_generation_request(request) for request in requests]
    api_key = source_env.get(env_var, "")
    if not api_key:
        return _empty_report(
            provider=normalized_provider,
            env_var=env_var,
            output_path=output_path,
            created_at_kst=timestamp,
            status="skipped_missing_env",
            request_count=len(validated_requests),
        )

    output_rows: List[Json] = []
    errors: List[Json] = []
    for request in validated_requests:
        request_id = str(request.get("request_id"))
        payload = request.get("payload")
        if not isinstance(payload, Mapping):
            errors.append({"request_id": request_id, "reason": "payload_missing"})
            continue
        try:
            raw_output, _provider_response, provider_summary = call_provider(
                provider=normalized_provider,
                payload=payload,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                transport=transport,
            )
        except (SelfInstructLLMRunnerError, json.JSONDecodeError) as exc:
            errors.append({"request_id": request_id, "reason": redact_text(str(exc), source_env)})
            continue
        output_rows.append(
            build_raw_output_row(
                request=request,
                provider=normalized_provider,
                raw_output=raw_output,
                provider_summary=provider_summary,
                created_at_kst=timestamp,
            )
        )

    if output_rows:
        _write_jsonl(output_rows, output_path)

    return {
        "schema_version": RUNNER_REPORT_SCHEMA_VERSION,
        "created_at_kst": timestamp,
        "provider": normalized_provider,
        "provider_env_var": env_var,
        "output_path": str(output_path),
        "status": "completed" if not errors else "completed_with_errors",
        "request_count": len(validated_requests),
        "executed_count": len(output_rows),
        "skipped_count": 0,
        "failed_count": len(errors),
        "errors": errors,
    }
