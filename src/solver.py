# Changed: solver를 LLM 기반 (Qwen3.5-0.8B full FT checkpoint)으로 교체.
# Why: DL 과제 요구사항 — LLM-only architecture. artifacts/checkpoint/에서 merged model 로드.
"""TCG/Opal SSD 프로토콜 준수 검증 Solver — LLM (Qwen3.5-0.8B full FT) 기반.

평가 서버 인터페이스:
    from src.solver import Solver, predict, predict_one
    predictions = predict(dataset)  # list[str]

내부 구조:
    artifacts/checkpoint/에 있는 Qwen3.5-0.8B full fine-tuned model을 로드하여
    trajectory JSON을 chat template으로 포맷하고 pass/fail logit 비교로 판정.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

# Changed: threshold를 환경변수로 파라미터화.
# Why: 최적 threshold는 데이터에 따라 다름. 기본 0.70은 sweep 검증 결과.
THRESHOLD = float(os.environ.get("OPAL_THRESHOLD", "0.70"))

# Changed: max_length를 환경변수로 파라미터화.
# Why: full FT 학습 시 max_length=8192 사용. 추론에서도 동일해야 truncation 없음.
MAX_LENGTH = int(os.environ.get("OPAL_MAX_LENGTH", "8192"))

Json = dict[str, Any]


# ---------------------------------------------------------------------------
# HF cache/offline 정책 — 평가 서버에서 네트워크 없이 동작하기 위한 설정
# ---------------------------------------------------------------------------

_EVALUATOR_CACHE_CANDIDATES = (
    "/workspace/cache/hf_cache",
    "/dl2026/skeleton/model_cache",
)


def _hf_local_files_only() -> bool:
    """평가 서버 offline 환경 감지."""
    for env_name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        val = os.environ.get(env_name, "").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
    # Changed: evaluator 캐시 디렉토리가 존재하면 offline으로 간주.
    # Why: 평가 서버에서는 네트워크 차단되지만 env var가 없을 수 있음.
    if any(Path(c).exists() for c in _EVALUATOR_CACHE_CANDIDATES):
        return True
    return False


def _hf_cache_dir() -> str | None:
    """HF cache 디렉토리 탐색."""
    for env_name in ("HF_HUB_CACHE", "TRANSFORMERS_CACHE", "HF_HOME"):
        raw = os.environ.get(env_name)
        if raw:
            return os.path.expanduser(os.path.expandvars(raw))
    for candidate in _EVALUATOR_CACHE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def _hf_load_kwargs() -> dict[str, Any]:
    """from_pretrained에 전달할 공통 kwargs."""
    kwargs: dict[str, Any] = {"local_files_only": _hf_local_files_only()}
    cache_dir = _hf_cache_dir()
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    return kwargs


# ---------------------------------------------------------------------------
# Record 파싱 — 다양한 입력 형태를 records list로 정규화
# ---------------------------------------------------------------------------

def _parse_records(trajectory: Any) -> list[Json]:
    """trajectory 입력에서 records 리스트를 추출.

    # Changed: 기존 solver의 _parse_records를 그대로 유지.
    # Why: 평가 서버가 다양한 형태로 입력을 줄 수 있으므로 호환성 유지.
    """
    if isinstance(trajectory, Path):
        with trajectory.open("r", encoding="utf-8") as handle:
            trajectory = json.load(handle)
    elif isinstance(trajectory, str):
        stripped = trajectory.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            trajectory = json.loads(stripped)
        else:
            with Path(trajectory).open("r", encoding="utf-8") as handle:
                trajectory = json.load(handle)
    if isinstance(trajectory, dict) and "records" in trajectory:
        trajectory = trajectory["records"]
    elif isinstance(trajectory, dict) and isinstance(trajectory.get("input"), str):
        # Changed: {"input": "{\"records\":...}"} 형태 지원.
        # Why: public20 rows가 이 schema를 사용.
        return _parse_records(trajectory["input"])
    if not isinstance(trajectory, list):
        return []
    return [item for item in trajectory if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# Solver 클래스: LLM-only 제출 진입점
# ---------------------------------------------------------------------------

class Solver:
    """평가 서버가 호출하는 메인 Solver 클래스.

    # Changed: FSM 대신 Qwen3.5-0.8B full FT merged model 사용.
    # Why: DL 과제 — LLM-only architecture 필수. artifacts/checkpoint/에서 로드.
    """

    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        t0 = time.time()
        root = Path(__file__).resolve().parents[1]

        # Changed: checkpoint 경로 탐색 — artifacts/checkpoint/ 우선.
        # Why: 제출 패키지에서 merged model은 이 경로에 배치.
        checkpoint_path = root / "artifacts" / "checkpoint"
        if not (checkpoint_path / "config.json").exists():
            # Changed: fallback으로 artifacts/merged_model/ 도 탐색.
            # Why: 기존 제출과의 호환성 유지.
            checkpoint_path = root / "artifacts" / "merged_model"
        if not (checkpoint_path / "config.json").exists():
            raise RuntimeError(
                "LLM-only architecture gate: merged model not found at "
                "artifacts/checkpoint/ or artifacts/merged_model/"
            )

        hf_kwargs = _hf_load_kwargs()
        _logger.info(
            "Loading merged model from %s (local_files_only=%s, cache_dir=%s)",
            checkpoint_path,
            hf_kwargs.get("local_files_only"),
            hf_kwargs.get("cache_dir", "<default>"),
        )

        # Changed: tokenizer를 checkpoint에서 로드, 없으면 base model fallback.
        # Why: SFTTrainer checkpoint에 tokenizer 파일이 없을 수 있음.
        #      이 경우 pre-cached Qwen/Qwen3.5-0.8B에서 tokenizer를 가져옴.
        tokenizer_path = checkpoint_path
        if not (checkpoint_path / "tokenizer_config.json").exists():
            tokenizer_path = "Qwen/Qwen3.5-0.8B"
            _logger.info("Tokenizer not in checkpoint, falling back to %s", tokenizer_path)
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_path),
            trust_remote_code=True,
            **hf_kwargs,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Changed: bfloat16 + device_map="auto"로 GPU에 자동 배치.
        # Why: 0.8B 모델은 ~1.6GB만 사용 — L40S 48GB에서 충분.
        self.model = AutoModelForCausalLM.from_pretrained(
            str(checkpoint_path),
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
            **hf_kwargs,
        )
        self.model.eval()

        # Changed: pass/fail 토큰 ID 캐시.
        # Why: 매 추론마다 encode하지 않고 미리 캐시해서 속도 향상.
        self._pass_id = self.tokenizer.encode("pass", add_special_tokens=False)[0]
        self._fail_id = self.tokenizer.encode("fail", add_special_tokens=False)[0]

        _logger.info(
            "Model loaded in %.1fs. pass_id=%d, fail_id=%d",
            time.time() - t0, self._pass_id, self._fail_id,
        )

    def predict(self, dataset: list) -> dict[str, str]:
        """dataset의 각 testcase에 대해 pass/fail 판정.

        Args:
            dataset: list of testcase dicts, each with trajectory data

        Returns:
            dict mapping case_id -> "pass" or "fail"
        """
        results: dict[str, str] = {}
        for index, case in enumerate(dataset):
            case_id = str(case.get("id", f"case_{index}")) if isinstance(case, dict) else f"case_{index}"
            try:
                records = _parse_records(case)
                if not records:
                    _logger.warning("case %s: records parse failed, defaulting to pass", case_id)
                    results[case_id] = "pass"
                    continue

                verdict = self._predict_one_trajectory(records)
                results[case_id] = verdict

            except Exception as e:
                _logger.error("case %s: exception %s, defaulting to pass", case_id, e)
                results[case_id] = "pass"

        return results

    def _predict_one_trajectory(self, records: list[Json]) -> str:
        """단일 trajectory의 records로 pass/fail logit 비교.

        # Changed: chat template 포맷 사용 (학습 시와 동일).
        # Why: train_manifest_full.py가 apply_chat_template으로 학습했으므로
        #      추론에서도 동일한 포맷을 사용해야 성능 보장.
        """
        import torch

        # Changed: 학습 시 input_text는 raw JSON 문자열.
        # Why: manifest의 input 필드가 {"records": [...]} JSON 그대로.
        input_text = json.dumps({"records": records}, ensure_ascii=False)

        # Changed: 학습 시 build_messages에서 system prompt 없이 user/assistant만 사용.
        # Why: train_manifest_full.py와 train_manifest_lora.py 모두
        #      [{"role":"user","content":input}, {"role":"assistant","content":label}] 형태.
        messages = [
            {"role": "user", "content": input_text},
        ]

        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            # Changed: enable_thinking 미지원 tokenizer 대응.
            # Why: 일부 버전의 tokenizer가 이 kwarg를 지원하지 않음.
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )

        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=MAX_LENGTH
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = self.model(**inputs).logits[0, -1, :]

        p_logit = logits[self._pass_id].item()
        f_logit = logits[self._fail_id].item()

        # Changed: softmax로 p_fail 계산 후 threshold 비교.
        # Why: 단순 logit 비교보다 확률 기반 threshold가 조정 가능.
        mx = max(p_logit, f_logit)
        p_fail = math.exp(f_logit - mx) / (
            math.exp(p_logit - mx) + math.exp(f_logit - mx)
        )

        # Changed: lowercase pass/fail 출력.
        # Why: evaluate.py가 answer.strip().lower()로 비교.
        prediction = "fail" if p_fail > THRESHOLD else "pass"
        _logger.info(
            "pass_logit=%.4f fail_logit=%.4f p_fail=%.4f threshold=%.2f -> %s",
            p_logit, f_logit, p_fail, THRESHOLD, prediction,
        )
        return prediction


# ---------------------------------------------------------------------------
# 모듈 레벨 함수: 평가 서버 호환
# ---------------------------------------------------------------------------

def predict(dataset: Any) -> list[str]:
    """평가 서버가 호출하는 메인 predict 함수.

    # Changed: LLM 기반 판정.
    # Why: dataset의 각 testcase를 Qwen3.5-0.8B full FT로 검증.

    Returns:
        list[str]: ["pass", "fail", ...] 형태의 판정 결과 리스트.
    """
    if isinstance(dataset, dict):
        cases = dataset.get("testcases") or dataset.get("cases") or dataset.get("data") or []
    else:
        cases = dataset
    if isinstance(cases, dict):
        iterable = [cases[key] for key in sorted(cases)]
    elif isinstance(cases, list):
        iterable = cases
    else:
        iterable = []
    if not iterable:
        return []

    solver = Solver()
    predictions = solver.predict(iterable)
    ordered: list[str] = []
    for index, case in enumerate(iterable):
        case_id = str(case.get("id", f"case_{index}")) if isinstance(case, dict) else f"case_{index}"
        ordered.append(predictions.get(case_id, "pass"))
    return ordered


def predict_one(testcase: Any) -> str:
    """단일 testcase 판정.

    # Changed: LLM 기반 판정.
    """
    solver = Solver()
    records = _parse_records(testcase)
    if not records:
        return "pass"
    return solver._predict_one_trajectory(records)
