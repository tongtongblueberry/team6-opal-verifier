"""Experiment C용 학습 데이터 필터링 및 IFD 스코어 산출 스크립트.

목적: 470개 mutation 학습 데이터에서 고품질 서브셋을 추출하여 fine-tuning 효율을 높인다.

필터링 파이프라인:
  1. Length analysis — record 수 기반 길이 분포 분석 및 최소 길이 필터
  2. IFD Score 산출 (Cherry LLM, NAACL 2024) — 모델이 instruction으로부터 얼마나 도움받는지 측정
  3. Label balance — pass/fail 비율 60/40 초과 시 majority class 다운샘플링
  4. Source diversity — 동일 원본 template에서 유래한 case 수 제한
  5. Output — 다양한 조건으로 필터링된 서브셋 JSON 파일 생성

참고 논문:
  [EXTERNAL KNOWLEDGE]
  - Li, M., Zhang, Y., et al. (2024). From Quantity to Quality: Boosting LLM Performance
    with Self-Guided Data Selection for Instruction Tuning. Proceedings of NAACL 2024.
    (Cherry LLM: IFD 기반 데이터 선별로 전체 데이터의 5%만으로 동등 성능 달성)

사용법:
  # GPU 없이 길이 기반 필터링만:
  python tools/datagen/filter_data.py \\
      --input /workspace/sinjeongmin_opal_verifier/training_data/mutation_cases.json \\
      --output-dir /workspace/sinjeongmin_opal_verifier/training_data/filtered/

  # IFD 포함 전체 파이프라인:
  python tools/datagen/filter_data.py \\
      --input /workspace/sinjeongmin_opal_verifier/training_data/mutation_cases.json \\
      --output-dir /workspace/sinjeongmin_opal_verifier/training_data/filtered/ \\
      --compute-ifd \\
      --top-k 150 200
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# Changed: 프로젝트 루트를 sys.path에 추가 — format 함수 임포트를 위해
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("filter_data")

Json = dict[str, Any]

# ============================================================
# 상수
# ============================================================

# Changed: 서버 환경의 모델 캐시 경로
BASE_MODEL = "Qwen/Qwen3.5-4B"
MODEL_CACHE = "/workspace/cache/hf_cache/hub"
# Changed: filter 입력/출력 기본 루트를 env로 재정의 가능하게 분리.
# Why: 기본 실행이 이전 /workspace/team6/training_data에 접근하지 않도록 함.
DEFAULT_RUNTIME_ROOT = Path(
    os.environ.get("OPAL_RUNTIME_ROOT", "/workspace/sinjeongmin_opal_verifier")
)
DEFAULT_TRAINING_DATA_DIR = DEFAULT_RUNTIME_ROOT / "training_data"

# Changed: lora_solver.py 및 train_exp_a.py와 동일한 시스템 프롬프트
SYSTEM_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory with session state, "
    "determine if the final response is consistent with the specification. "
    "Answer exactly: pass or fail"
)


# ============================================================
# format 함수 임포트 — finetune_lora_v2.py에서 가져옴
# ============================================================
try:
    from tools.training.finetune_lora_v2 import format_trajectory_rich
except ImportError:
    # Changed: 서버에서 임포트 실패 시 lora_solver.py에서 가져옴
    try:
        from src.lora_solver import format_trajectory_rich
    except ImportError:
        logger.error("format_trajectory_rich를 임포트할 수 없음. 경로를 확인하세요.")
        sys.exit(1)


# ============================================================
# Step 1: 길이 분석
# ============================================================

def analyze_lengths(cases: list[Json]) -> list[Json]:
    """각 case에 num_records 필드를 추가하고, 길이 분포 히스토그램을 출력한다.

    Changed: record 수 기준으로 trajectory 길이를 측정.
    Why: 짧은 trajectory는 정보가 부족하여 학습에 도움이 안 됨.
    """
    for case in cases:
        records = case.get("records", [])
        # Changed: 유효한 dict record만 카운트
        valid_records = [r for r in records if isinstance(r, dict)]
        case["num_records"] = len(valid_records)

    # 히스토그램 출력
    lengths = [c["num_records"] for c in cases]
    if not lengths:
        logger.warning("데이터가 비어 있음")
        return cases

    counter = Counter(lengths)
    min_len = min(lengths)
    max_len = max(lengths)
    avg_len = sum(lengths) / len(lengths)

    logger.info("=" * 60)
    logger.info("길이 분포 분석 (총 %d cases)", len(cases))
    logger.info("=" * 60)
    logger.info("  min=%d, max=%d, avg=%.1f, median=%d",
                min_len, max_len, avg_len, sorted(lengths)[len(lengths) // 2])

    # Changed: 히스토그램을 구간별로 출력 (가독성)
    # 구간: 1-3, 4-7, 8-11, 12-15, 16-19, 20+
    bins = [(1, 3), (4, 7), (8, 11), (12, 15), (16, 19), (20, 25), (26, 35), (36, 50)]
    logger.info("  Length distribution:")
    for lo, hi in bins:
        count = sum(v for k, v in counter.items() if lo <= k <= hi)
        bar = "#" * min(count, 60)
        if count > 0:
            logger.info("    [%2d-%2d]: %3d  %s", lo, hi, count, bar)

    # Changed: 개별 길이도 출력 (상세)
    logger.info("  Per-length counts:")
    for length in sorted(counter.keys()):
        logger.info("    len=%2d: %3d cases", length, counter[length])

    return cases


def filter_by_length(cases: list[Json], min_length: int) -> list[Json]:
    """최소 길이 기준으로 필터링.

    Changed: num_records >= min_length인 case만 유지.
    """
    filtered = [c for c in cases if c.get("num_records", 0) >= min_length]
    logger.info("길이 필터 (min=%d): %d -> %d cases", min_length, len(cases), len(filtered))
    return filtered


# ============================================================
# Step 2: IFD Score 산출 (Cherry LLM, NAACL 2024)
# ============================================================

def _build_prompt_text(records: list[Json]) -> str:
    """records에서 chat template 적용 전 프롬프트 텍스트를 생성한다.

    Changed: format_trajectory_rich를 사용하여 학습/추론 포맷과 일관성 유지.
    """
    valid_records = [r for r in records if isinstance(r, dict)]
    if not valid_records:
        return ""
    return format_trajectory_rich(valid_records)


def compute_ifd_scores(
    cases: list[Json],
    model,
    tokenizer,
    max_seq_len: int = 2048,
) -> list[Json]:
    """각 case에 대해 IFD score를 산출한다.

    Changed: Cherry LLM (NAACL 2024) 논문의 IFD 방식을 구현.
    IFD = log P(answer | instruction) - log P(answer)
    - Higher IFD = instruction이 도움됨 = 모델이 이미 판단할 수 있는 easy case
    - Lower IFD = instruction이 도움 안 됨 = hard case

    논문에서는 HIGH IFD case를 선별 (instruction이 도움이 되는, 즉 instruction-answer 관계가
    잘 형성된 case). 우리도 이 방식을 따름.
    """
    import torch

    model.eval()
    device = next(model.parameters()).device

    logger.info("IFD 스코어 산출 시작 (총 %d cases)...", len(cases))
    t0 = time.time()

    for idx, case in enumerate(cases):
        records = case.get("records", [])
        valid_records = [r for r in records if isinstance(r, dict)]
        label = case.get("label", "pass")
        answer_text = label  # "pass" 또는 "fail"

        if not valid_records:
            case["ifd_score"] = 0.0
            continue

        # ---- 1) instruction + answer의 전체 텍스트 구성 ----
        # Changed: chat template를 적용하여 실제 학습 포맷과 동일하게 구성
        prompt = _build_prompt_text(valid_records)
        messages_full = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer_text},
        ]
        messages_prompt_only = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            full_text = tokenizer.apply_chat_template(
                messages_full, tokenize=False,
                add_generation_prompt=False, enable_thinking=False,
            )
            prompt_text = tokenizer.apply_chat_template(
                messages_prompt_only, tokenize=False,
                add_generation_prompt=True, enable_thinking=False,
            )
        except TypeError:
            full_text = tokenizer.apply_chat_template(
                messages_full, tokenize=False,
                add_generation_prompt=False,
            )
            prompt_text = tokenizer.apply_chat_template(
                messages_prompt_only, tokenize=False,
                add_generation_prompt=True,
            )

        # ---- 2) P(answer | instruction) 산출 ----
        # Changed: 전체 텍스트를 인코딩하고, 프롬프트 부분 이후 answer 토큰의 log-prob를 구함
        full_ids = tokenizer(
            full_text, return_tensors="pt", truncation=True, max_length=max_seq_len,
        )
        prompt_ids = tokenizer(
            prompt_text, return_tensors="pt", truncation=True, max_length=max_seq_len,
        )

        full_input_ids = full_ids["input_ids"].to(device)
        prompt_len = prompt_ids["input_ids"].shape[1]
        full_len = full_input_ids.shape[1]

        # Changed: answer 토큰이 없으면 (프롬프트가 max_seq_len에 도달) 스킵
        if prompt_len >= full_len:
            case["ifd_score"] = 0.0
            if idx < 5 or idx % 50 == 0:
                logger.info("  [%d/%d] 프롬프트가 시퀀스 전체를 차지하여 IFD=0.0", idx + 1, len(cases))
            continue

        with torch.no_grad():
            outputs_full = model(full_input_ids)
            logits_full = outputs_full.logits  # (1, seq_len, vocab_size)

        # Changed: answer 토큰 범위의 log-prob 산출
        # logits[t]는 position t+1의 예측이므로, answer 시작은 prompt_len-1번째 logit부터
        answer_start = prompt_len - 1
        answer_end = full_len - 1  # 마지막 토큰의 logit은 full_len-2 위치에서 나옴
        answer_logits = logits_full[0, answer_start:answer_end, :]  # (num_answer_tokens, vocab)
        answer_target_ids = full_input_ids[0, prompt_len:full_len]  # (num_answer_tokens,)

        # Changed: log-softmax로 log-probability 계산
        log_probs_full = torch.nn.functional.log_softmax(answer_logits, dim=-1)
        # Changed: gather로 target token의 log-prob만 추출
        answer_log_probs_with_inst = log_probs_full.gather(
            1, answer_target_ids.unsqueeze(1)
        ).squeeze(1)  # (num_answer_tokens,)
        avg_log_prob_with_inst = answer_log_probs_with_inst.mean().item()

        # ---- 3) P(answer) 산출 (instruction 없이) ----
        # Changed: answer 텍스트만 단독으로 인코딩하여 base perplexity 측정
        answer_only_ids = tokenizer(
            answer_text, return_tensors="pt", add_special_tokens=True,
        )["input_ids"].to(device)

        answer_only_len = answer_only_ids.shape[1]

        if answer_only_len <= 1:
            # Changed: 토큰이 1개 이하면 다음 토큰 예측 불가 → uniform prior 가정
            avg_log_prob_without_inst = math.log(1.0 / tokenizer.vocab_size)
        else:
            with torch.no_grad():
                outputs_bare = model(answer_only_ids)
                logits_bare = outputs_bare.logits  # (1, answer_only_len, vocab)

            # Changed: 첫 토큰 이후부터의 log-prob (autoregressive)
            log_probs_bare = torch.nn.functional.log_softmax(logits_bare[0, :-1, :], dim=-1)
            bare_targets = answer_only_ids[0, 1:]
            bare_log_probs = log_probs_bare.gather(
                1, bare_targets.unsqueeze(1)
            ).squeeze(1)
            avg_log_prob_without_inst = bare_log_probs.mean().item()

        # ---- 4) IFD = log P(answer|inst) - log P(answer) ----
        # Changed: higher IFD = instruction이 더 도움됨 = Cherry LLM이 선호하는 case
        ifd = avg_log_prob_with_inst - avg_log_prob_without_inst
        case["ifd_score"] = round(ifd, 6)

        if idx < 5 or idx % 50 == 0:
            logger.info(
                "  [%d/%d] label=%s, len=%d, logP(a|i)=%.4f, logP(a)=%.4f, IFD=%.4f",
                idx + 1, len(cases), label, case.get("num_records", 0),
                avg_log_prob_with_inst, avg_log_prob_without_inst, ifd,
            )

        # Changed: GPU 메모리 관리 — 매 case마다 중간 텐서 해제
        del full_input_ids, logits_full, outputs_full
        del answer_only_ids
        if 'outputs_bare' in dir():
            del outputs_bare
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

    elapsed = time.time() - t0
    logger.info("IFD 산출 완료: %.1fs (%.2fs/case)", elapsed, elapsed / max(len(cases), 1))

    # Changed: IFD 분포 통계 출력
    ifd_scores = [c["ifd_score"] for c in cases if c.get("ifd_score") is not None]
    if ifd_scores:
        logger.info("IFD 분포: min=%.4f, max=%.4f, avg=%.4f, median=%.4f",
                     min(ifd_scores), max(ifd_scores),
                     sum(ifd_scores) / len(ifd_scores),
                     sorted(ifd_scores)[len(ifd_scores) // 2])

    return cases


def select_top_k_ifd(cases: list[Json], k: int) -> list[Json]:
    """IFD score 상위 k개를 선택한다.

    Changed: Cherry LLM 논문에 따라 IFD가 높은 case를 우선 선택.
    Why: IFD가 높은 case = instruction(trajectory)이 answer 예측에 도움이 되는,
    즉 trajectory와 label 사이의 관계가 명확한 고품질 데이터.
    """
    # Changed: IFD score 기준 내림차순 정렬 후 상위 k개 선택
    sorted_cases = sorted(cases, key=lambda c: c.get("ifd_score", 0.0), reverse=True)
    selected = sorted_cases[:k]
    logger.info("IFD top-%d 선택: 평균 IFD=%.4f (선택), %.4f (전체)",
                k,
                sum(c.get("ifd_score", 0) for c in selected) / max(len(selected), 1),
                sum(c.get("ifd_score", 0) for c in cases) / max(len(cases), 1))
    return selected


# ============================================================
# Step 3: Label balance 체크 및 조정
# ============================================================

def balance_labels(cases: list[Json], max_ratio: float = 0.6) -> list[Json]:
    """pass/fail 비율이 max_ratio를 초과하면 majority class를 다운샘플링한다.

    Changed: IFD score가 있으면 IFD 기준으로 우선 유지, 없으면 랜덤 샘플링.
    Why: 학습 데이터의 class imbalance는 majority class 편향을 유발.
    """
    import random
    random.seed(42)

    n_pass = sum(1 for c in cases if c.get("label") == "pass")
    n_fail = sum(1 for c in cases if c.get("label") == "fail")
    total = n_pass + n_fail

    if total == 0:
        return cases

    pass_ratio = n_pass / total
    fail_ratio = n_fail / total

    logger.info("Label balance: pass=%d (%.1f%%), fail=%d (%.1f%%)",
                n_pass, pass_ratio * 100, n_fail, fail_ratio * 100)

    if pass_ratio <= max_ratio and fail_ratio <= max_ratio:
        logger.info("  -> 균형 OK (%.0f/%.0f 이내)", max_ratio * 100, (1 - max_ratio) * 100)
        return cases

    # Changed: majority class 결정
    if pass_ratio > max_ratio:
        majority_label = "pass"
        minority_count = n_fail
    else:
        majority_label = "fail"
        minority_count = n_pass

    # Changed: target = minority_count / (1 - max_ratio) * max_ratio 로 계산하면
    # 최종 비율이 정확히 max_ratio가 됨. 하지만 단순히 minority / majority 비율 맞추기 위해
    # majority를 minority_count * max_ratio / (1 - max_ratio)로 제한.
    target_majority = int(minority_count * max_ratio / (1 - max_ratio))

    majority_cases = [c for c in cases if c.get("label") == majority_label]
    minority_cases = [c for c in cases if c.get("label") != majority_label]

    # Changed: IFD가 있으면 IFD 높은 순으로, 없으면 랜덤
    has_ifd = any(c.get("ifd_score") is not None for c in majority_cases)
    if has_ifd:
        majority_cases.sort(key=lambda c: c.get("ifd_score", 0.0), reverse=True)
    else:
        random.shuffle(majority_cases)

    majority_cases = majority_cases[:target_majority]

    balanced = minority_cases + majority_cases
    logger.info("  -> 다운샘플링: %s %d -> %d, 총 %d cases",
                majority_label, n_pass if majority_label == "pass" else n_fail,
                len(majority_cases), len(balanced))

    return balanced


# ============================================================
# Step 4: Source diversity — 동일 template 기반 case 수 제한
# ============================================================

def _extract_source_template(case: Json) -> str:
    """case의 source 필드에서 원본 template ID(tc번호)를 추출한다.

    Changed: source 형식 = "mutation:{filename}:{mutation_type}:..."
    예: "mutation:tc1.json:status_flip:SUCCESS->NOT_AUTHORIZED"
    """
    source = case.get("source", "")
    # Changed: "mutation:tc{N}.json:" 패턴에서 tc{N} 추출
    match = re.search(r"tc(\d+)\.json", source)
    if match:
        return f"tc{match.group(1)}"
    # Changed: source가 없는 경우 (원본 public case일 수 있음)
    filename = case.get("filename", "")
    match2 = re.search(r"tc(\d+)", filename)
    if match2:
        return f"tc{match2.group(1)}"
    return "unknown"


def limit_per_template(cases: list[Json], max_per_template: int) -> list[Json]:
    """동일 원본 template에서 유래한 case 수를 제한한다.

    Changed: IFD score가 있으면 IFD 높은 순으로 유지, 없으면 원래 순서 유지.
    Why: 동일 template에서 과도한 mutation은 다양성을 해침.
    """
    groups: dict[str, list[Json]] = defaultdict(list)
    for case in cases:
        template = _extract_source_template(case)
        case["_source_template"] = template  # Changed: 임시 필드 추가 (출력 시 제거)
        groups[template].append(case)

    logger.info("Source template 분포:")
    for template in sorted(groups.keys(), key=lambda t: int(re.search(r'\d+', t).group()) if re.search(r'\d+', t) else 0):
        logger.info("  %s: %d cases", template, len(groups[template]))

    # Changed: 각 그룹에서 max_per_template 이하로 제한
    filtered = []
    for template, group in groups.items():
        has_ifd = any(c.get("ifd_score") is not None for c in group)
        if has_ifd:
            group.sort(key=lambda c: c.get("ifd_score", 0.0), reverse=True)
        selected = group[:max_per_template]
        if len(group) > max_per_template:
            logger.info("  %s: %d -> %d (제한됨)", template, len(group), len(selected))
        filtered.extend(selected)

    logger.info("Template 제한 (max=%d): %d -> %d cases",
                max_per_template, len(cases), len(filtered))

    return filtered


# ============================================================
# Step 5: 출력 — 필터링된 서브셋 JSON 저장
# ============================================================

def _clean_case_for_output(case: Json) -> Json:
    """출력용으로 임시 필드를 제거한다.

    Changed: _source_template 같은 내부용 필드 제거, ifd_score와 num_records는 유지.
    """
    output = {}
    for key, value in case.items():
        if key.startswith("_"):
            continue
        output[key] = value
    return output


def save_subset(cases: list[Json], output_path: str, description: str) -> None:
    """필터링된 서브셋을 JSON으로 저장하고 요약 통계를 출력한다."""
    # Changed: 임시 필드 제거
    clean_cases = [_clean_case_for_output(c) for c in cases]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(clean_cases, f, indent=2, ensure_ascii=False)

    # Changed: 요약 통계 출력
    n_pass = sum(1 for c in clean_cases if c.get("label") == "pass")
    n_fail = sum(1 for c in clean_cases if c.get("label") == "fail")
    lengths = [c.get("num_records", 0) for c in clean_cases]
    ifd_scores = [c.get("ifd_score", 0) for c in clean_cases if c.get("ifd_score") is not None]

    logger.info("-" * 50)
    logger.info("저장: %s", output_path)
    logger.info("  설명: %s", description)
    logger.info("  총 %d cases (pass=%d, fail=%d)", len(clean_cases), n_pass, n_fail)
    if lengths:
        logger.info("  길이: min=%d, max=%d, avg=%.1f",
                     min(lengths), max(lengths), sum(lengths) / len(lengths))
    if ifd_scores:
        logger.info("  IFD: min=%.4f, max=%.4f, avg=%.4f",
                     min(ifd_scores), max(ifd_scores), sum(ifd_scores) / len(ifd_scores))


# ============================================================
# 메인 함수
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Experiment C: 학습 데이터 필터링 및 IFD 스코어 산출",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DEFAULT_TRAINING_DATA_DIR / "mutation_cases.json"),
        help="입력 mutation 데이터 JSON 경로",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_TRAINING_DATA_DIR / "filtered"),
        help="필터링 결과 출력 디렉토리",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=8,
        help="최소 record 수 (기본값: 8)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        nargs="+",
        default=[150, 200],
        help="IFD 상위 k개 선택 (여러 값 지정 가능, 기본값: 150 200)",
    )
    parser.add_argument(
        "--max-per-template",
        type=int,
        default=20,
        help="동일 원본 template 당 최대 case 수 (기본값: 20)",
    )
    parser.add_argument(
        "--compute-ifd",
        action="store_true",
        help="IFD 스코어 산출 (GPU 필요, 생략 시 길이 기반 필터링만 수행)",
    )
    parser.add_argument(
        "--ifd-cache",
        type=str,
        default=None,
        help="IFD 스코어 캐시 파일 경로 (재계산 방지용). 미지정 시 output-dir/ifd_scores.json",
    )
    parser.add_argument(
        "--max-seq-len",
        type=int,
        default=2048,
        help="모델 최대 시퀀스 길이 (기본값: 2048)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Experiment C: 학습 데이터 필터링")
    logger.info("=" * 60)
    logger.info("입력: %s", args.input)
    logger.info("출력: %s", args.output_dir)
    logger.info("설정: min_length=%d, top_k=%s, max_per_template=%d, compute_ifd=%s",
                args.min_length, args.top_k, args.max_per_template, args.compute_ifd)

    # ---- 데이터 로드 ----
    logger.info("데이터 로드 중: %s", args.input)
    with open(args.input) as f:
        cases = json.load(f)
    logger.info("총 %d cases 로드됨", len(cases))

    # ---- Step 1: 길이 분석 ----
    logger.info("\n=== Step 1: 길이 분석 ===")
    cases = analyze_lengths(cases)

    # ---- Step 2: IFD 산출 (선택적) ----
    ifd_cache_path = args.ifd_cache or os.path.join(args.output_dir, "ifd_scores.json")

    if args.compute_ifd:
        # Changed: 캐시가 있으면 재사용
        if os.path.exists(ifd_cache_path):
            logger.info("IFD 캐시 발견: %s — 로드 중...", ifd_cache_path)
            with open(ifd_cache_path) as f:
                cached_scores = json.load(f)

            # Changed: 캐시된 스코어를 case에 매핑 (source 필드 기준)
            score_map = {}
            for item in cached_scores:
                key = item.get("source", item.get("filename", ""))
                score_map[key] = item.get("ifd_score", 0.0)

            matched = 0
            for case in cases:
                key = case.get("source", case.get("filename", ""))
                if key in score_map:
                    case["ifd_score"] = score_map[key]
                    matched += 1

            logger.info("캐시에서 %d/%d cases의 IFD 매칭 완료", matched, len(cases))

            # Changed: 매칭 안 된 case가 있으면 모델 로드하여 나머지만 계산
            unmatched = [c for c in cases if c.get("ifd_score") is None]
            if unmatched:
                logger.info("매칭 안 된 %d cases에 대해 IFD 재산출...", len(unmatched))
                model, tokenizer = _load_model()
                unmatched = compute_ifd_scores(unmatched, model, tokenizer, args.max_seq_len)
                # Changed: 결과를 원본 cases에 반영
                unmatched_map = {}
                for c in unmatched:
                    key = c.get("source", c.get("filename", ""))
                    unmatched_map[key] = c.get("ifd_score", 0.0)
                for case in cases:
                    key = case.get("source", case.get("filename", ""))
                    if key in unmatched_map:
                        case["ifd_score"] = unmatched_map[key]
                del model, tokenizer
                _cleanup_gpu()
        else:
            logger.info("\n=== Step 2: IFD 스코어 산출 ===")
            model, tokenizer = _load_model()
            cases = compute_ifd_scores(cases, model, tokenizer, args.max_seq_len)
            del model, tokenizer
            _cleanup_gpu()

        # Changed: IFD 스코어를 별도 파일로 저장 (재계산 방지)
        _save_ifd_cache(cases, ifd_cache_path)

    # ---- 서브셋 생성 ----
    logger.info("\n=== Step 5: 서브셋 생성 ===")
    os.makedirs(args.output_dir, exist_ok=True)

    # --- 길이 필터만 적용한 서브셋 ---
    for min_len in [args.min_length, 10]:
        len_filtered = filter_by_length(cases, min_len)
        # Changed: template 제한 적용
        len_filtered = limit_per_template(len_filtered, args.max_per_template)
        # Changed: label balance 조정
        len_filtered = balance_labels(len_filtered)
        save_subset(
            len_filtered,
            os.path.join(args.output_dir, f"filtered_len{min_len}_all.json"),
            f"길이>={min_len}, template 제한={args.max_per_template}, label 균형 조정",
        )

    # --- IFD 기반 서브셋 (compute-ifd가 활성화된 경우만) ---
    if args.compute_ifd or any(c.get("ifd_score") is not None for c in cases):
        has_ifd = [c for c in cases if c.get("ifd_score") is not None]
        if has_ifd:
            for k in args.top_k:
                # Changed: IFD top-k (길이 필터 없음)
                ifd_selected = select_top_k_ifd(has_ifd, k)
                ifd_selected = limit_per_template(ifd_selected, args.max_per_template)
                ifd_selected = balance_labels(ifd_selected)
                save_subset(
                    ifd_selected,
                    os.path.join(args.output_dir, f"filtered_ifd{k}.json"),
                    f"IFD top-{k}, template 제한={args.max_per_template}, label 균형 조정",
                )

                # Changed: 길이 필터 + IFD top-k
                len_filtered_ifd = filter_by_length(has_ifd, args.min_length)
                ifd_len_selected = select_top_k_ifd(len_filtered_ifd, k)
                ifd_len_selected = limit_per_template(ifd_len_selected, args.max_per_template)
                ifd_len_selected = balance_labels(ifd_len_selected)
                save_subset(
                    ifd_len_selected,
                    os.path.join(args.output_dir, f"filtered_len{args.min_length}_ifd{k}.json"),
                    f"길이>={args.min_length} + IFD top-{k}, template 제한={args.max_per_template}, label 균형 조정",
                )

    # ---- 최종 요약 ----
    logger.info("\n" + "=" * 60)
    logger.info("필터링 완료!")
    logger.info("=" * 60)
    logger.info("출력 디렉토리: %s", args.output_dir)

    # Changed: 생성된 파일 목록 출력
    output_files = sorted(Path(args.output_dir).glob("filtered_*.json"))
    for fpath in output_files:
        with open(fpath) as f:
            subset = json.load(f)
        n_p = sum(1 for c in subset if c.get("label") == "pass")
        n_f = sum(1 for c in subset if c.get("label") == "fail")
        logger.info("  %s: %d cases (pass=%d, fail=%d)", fpath.name, len(subset), n_p, n_f)


# ============================================================
# 유틸리티 함수
# ============================================================

def _load_model():
    """Qwen3.5-4B BASE 모델을 로드한다 (LoRA adapter 없이).

    Changed: IFD 산출에는 base model을 사용해야 함.
    Why: IFD는 base model의 관점에서 instruction이 얼마나 도움되는지를 측정.
    fine-tuned model을 쓰면 이미 학습된 편향이 반영됨.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("모델 로드 중: %s (cache: %s)", BASE_MODEL, MODEL_CACHE)
    t0 = time.time()

    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )
    model.eval()

    logger.info("모델 로드 완료: %.1fs", time.time() - t0)
    return model, tokenizer


def _cleanup_gpu():
    """GPU 메모리 정리."""
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _save_ifd_cache(cases: list[Json], cache_path: str) -> None:
    """IFD 스코어를 별도 캐시 파일로 저장한다.

    Changed: source/filename + ifd_score만 저장하여 파일 크기 최소화.
    Why: IFD 재계산은 GPU 시간이 많이 들므로 캐시로 재사용.
    """
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    cache_entries = []
    for case in cases:
        if case.get("ifd_score") is None:
            continue
        entry = {
            "ifd_score": case["ifd_score"],
        }
        # Changed: 식별을 위해 source 또는 filename 포함
        if "source" in case:
            entry["source"] = case["source"]
        if "filename" in case:
            entry["filename"] = case["filename"]
        if "label" in case:
            entry["label"] = case["label"]
        if "num_records" in case:
            entry["num_records"] = case["num_records"]
        cache_entries.append(entry)

    with open(cache_path, "w") as f:
        json.dump(cache_entries, f, indent=2, ensure_ascii=False)

    logger.info("IFD 캐시 저장: %s (%d entries)", cache_path, len(cache_entries))


if __name__ == "__main__":
    main()
