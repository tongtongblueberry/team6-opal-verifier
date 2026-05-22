"""Self-Consistency Voting + 온도 perturbation 평가 스크립트.

Changed: 단일 forward pass 대신 N회 forward pass (다른 temperature) → 투표/평균으로 최종 결정.
Why: temperature scaling은 logit을 1/T로 나눈 후 softmax — 모델 재로딩 불필요.
     여러 temperature에서의 예측을 앙상블하면 noise에 강건한 결정 가능.
     추가 학습 불필요(inference-time improvement).

사용법:
  python tools/eval/eval_consistency.py \
      --adapter-path /workspace/team6/adapters/exp_r8_diverse/checkpoints/checkpoint-588 \
      --n-samples 5 \
      --temperatures 0.5,0.7,0.9,1.1,1.3 \
      --threshold 0.70 \
      --dataset-root /dl2026/dataset \
      --strategy average
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

# Changed: 프로젝트 루트를 sys.path에 추가 — 서버에서도 import 가능하도록.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("eval_consistency")

Json = dict[str, Any]

# Changed: 시스템 프롬프트를 solver.py / lora_solver.py와 동일하게 유지.
# Why: 학습 시 사용한 프롬프트와 일치해야 모델이 올바르게 예측.
SYSTEM_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory with session state, "
    "determine if the final response is consistent with the specification. "
    "Answer exactly: pass or fail"
)


# ============================================================
# format_trajectory_rich_inline: solver.py와 동일한 포맷 함수
# Changed: 별도 파일 import 없이 인라인 — 서버 환경 독립성.
# Why: tools/ 구조가 없는 제출 환경에서도 동작해야 함.
# ============================================================
def _compact_json(obj, max_depth=2, cur_depth=0) -> str:
    """JSON 객체를 간결한 문자열로 변환."""
    if cur_depth >= max_depth:
        if isinstance(obj, dict):
            return "{...}"
        elif isinstance(obj, list):
            return "[...]"
        return str(obj)
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            parts.append(f"{k}={_compact_json(v, max_depth, cur_depth+1)}")
        return "{" + ", ".join(parts) + "}"
    elif isinstance(obj, list):
        if len(obj) == 0:
            return "[]"
        if len(obj) <= 3:
            return "[" + ", ".join(_compact_json(x, max_depth, cur_depth+1) for x in obj) + "]"
        return f"[{_compact_json(obj[0], max_depth, cur_depth+1)}, ... ({len(obj)} items)]"
    elif isinstance(obj, str) and len(obj) > 60:
        return obj[:60] + "..."
    return str(obj)


def format_trajectory_rich(records: list) -> str:
    """trajectory를 rich 포맷 문자열로 변환 (lora_solver.py와 동일)."""
    if not records:
        return ""

    lines = []
    session_active = False
    authenticated = False
    current_sp = ""

    for i, step in enumerate(records):
        if not isinstance(step, dict):
            continue
        cmd = step.get("input", {})
        out = step.get("output", {})

        # Changed: DATA_COMMAND 처리.
        data_cmd = cmd.get("command", "")
        if data_cmd and not cmd.get("method"):
            data_args = cmd.get("args", {})
            data_result = out.get("args", {}).get("result", "")
            data_out_cmd = out.get("command", data_cmd)
            is_final = (i == len(records) - 1)
            prefix = "[FINAL] " if is_final else ""
            line = f"{prefix}Step {i}: DATA_COMMAND {data_cmd}"
            if data_args:
                line += f" args={_compact_json(data_args)}"
            line += f" -> {data_out_cmd}"
            if data_result:
                line += f" result={data_result}"
            lines.append(line)
            continue

        method_obj = cmd.get("method", {})
        method_name = method_obj.get("name", "") if isinstance(method_obj, dict) else str(method_obj)
        method_args = method_obj.get("args", {}) if isinstance(method_obj, dict) else {}

        inv_obj = cmd.get("invoking_id", {})
        inv_name = inv_obj.get("name", "") if isinstance(inv_obj, dict) else str(inv_obj)
        inv_uid = inv_obj.get("uid", "") if isinstance(inv_obj, dict) else ""

        status = out.get("status_codes", out.get("status", ""))
        if isinstance(status, dict):
            status = status.get("Name", status.get("name", str(status)))
        return_values = out.get("return_values", out.get("payload", None))

        method_lower = str(method_name).lower()
        status_lower = str(status).lower()
        if method_lower == "startsession" and "success" in status_lower:
            session_active = True
            if isinstance(method_args, dict):
                req = method_args.get("required", method_args)
                if isinstance(req, dict):
                    spid = req.get("SPID", "")
                    write = req.get("Write", "")
                    if spid:
                        current_sp = f"SPID={spid}"
                    if write:
                        current_sp += f",Write={write}"
            authenticated = True
        elif method_lower == "endsession":
            session_active = False
            authenticated = False

        is_final = (i == len(records) - 1)
        prefix = "[FINAL] " if is_final else ""

        # Changed: required + optional args 포함.
        args_str = ""
        if method_args:
            if isinstance(method_args, dict):
                req = method_args.get("required", {})
                opt = method_args.get("optional", {})
                parts = []
                if isinstance(req, dict) and req:
                    parts.append(_compact_json(req))
                if isinstance(opt, dict) and opt:
                    parts.append("opt=" + _compact_json(opt))
                if parts:
                    args_str = ", ".join(parts)
                elif isinstance(method_args, dict) and not req and not opt:
                    args_str = _compact_json(method_args)
            else:
                args_str = _compact_json(method_args)
        if len(args_str) > 300:
            args_str = args_str[:300] + "..."

        rv_str = ""
        if return_values is not None:
            rv_str = _compact_json(return_values)
            if len(rv_str) > 150:
                rv_str = rv_str[:150] + "..."

        line = f"{prefix}Step {i}: {method_name}"
        if inv_name:
            line += f" target={inv_name}"
        if inv_uid:
            line += f"[{inv_uid}]"
        if args_str and args_str != "{}":
            line += f" args={args_str}"
        line += f" -> {status}"
        if rv_str and rv_str != "[]" and rv_str != "{}":
            line += f" payload={rv_str}"
        lines.append(line)

    state_line = f"SessionState: active={session_active}, auth={authenticated}"
    if current_sp:
        state_line += f", {current_sp}"

    trajectory_text = "\n".join(lines)
    prompt = (
        "TCG/Opal SSD protocol trajectory verification.\n"
        f"{state_line}\n\n"
        f"{trajectory_text}\n\n"
        "Is the final response consistent with the TCG/Opal specification? Answer: "
    )
    return prompt


# ============================================================
# 모델 로드
# ============================================================
def load_model(base_model: str, adapter_path: str):
    """base model + LoRA adapter 로드.

    Changed: eval_lora.py / eval_3adapters.py와 동일한 로드 로직.
    Why: 일관성 유지 — 같은 모델을 같은 방식으로 로드.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    logger.info("토크나이저 로드: %s", adapter_path)
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info("베이스 모델 로드: %s", base_model)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    logger.info("LoRA 어댑터 로드: %s", adapter_path)
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    logger.info("모델 로드 완료. pass_id=%d, fail_id=%d", pass_id, fail_id)
    return model, tokenizer, pass_id, fail_id


# ============================================================
# 핵심: temperature-scaled logit → p_fail 계산
# ============================================================
def get_p_fail_with_temperature(
    model,
    tokenizer,
    prompt: str,
    pass_id: int,
    fail_id: int,
    temperature: float = 1.0,
    max_length: int = 2048,
) -> float:
    """단일 forward pass에서 temperature-scaled p_fail 반환.

    Changed: logit을 1/T로 나눈 후 softmax 적용.
    Why: temperature > 1이면 확률 분포가 평탄(불확실 → 0.5에 가까움),
         temperature < 1이면 확률 분포가 뾰족(확신 → 0 또는 1에 가까움).
         모델 재로딩 불필요 — logit 후처리만으로 구현.
    """
    import torch

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits[0, -1, :]

    # Changed: temperature scaling 적용.
    # Why: logit / T → softmax. T=1이면 원래 확률, T<1이면 뾰족, T>1이면 평탄.
    p_logit = logits[pass_id].item() / temperature
    f_logit = logits[fail_id].item() / temperature

    mx = max(p_logit, f_logit)
    p_fail = math.exp(f_logit - mx) / (math.exp(p_logit - mx) + math.exp(f_logit - mx))
    return p_fail


def predict_consistency(
    model,
    tokenizer,
    prompt: str,
    pass_id: int,
    fail_id: int,
    temperatures: list[float],
    threshold: float = 0.5,
    strategy: str = "average",
    max_length: int = 2048,
) -> dict:
    """Self-consistency voting: 여러 temperature에서 N회 forward pass → 최종 결정.

    Changed: strategy에 따라 다른 앙상블 방법 사용.
    Why:
      - "average": p_fail 평균 → threshold 비교 (부드러운 결정)
      - "majority": 개별 예측 투표 → 과반 기준 (이진 결정)
      - "median": p_fail 중앙값 → threshold 비교 (outlier 내성)

    Args:
        temperatures: forward pass별 temperature 리스트
        threshold: p_fail이 이 값을 초과하면 fail (average/median 전략)
        strategy: "average", "majority", "median"

    Returns:
        {
            "prediction": "pass" or "fail",
            "p_fail_avg": float,
            "p_fail_median": float,
            "p_fails": list[float],
            "individual_preds": list[str],
            "vote_pass": int,
            "vote_fail": int,
        }
    """
    p_fails = []
    for temp in temperatures:
        p_fail = get_p_fail_with_temperature(
            model, tokenizer, prompt, pass_id, fail_id,
            temperature=temp, max_length=max_length,
        )
        p_fails.append(p_fail)

    # Changed: 개별 예측 (threshold 기준).
    individual_preds = ["fail" if pf > threshold else "pass" for pf in p_fails]
    vote_fail = sum(1 for p in individual_preds if p == "fail")
    vote_pass = len(individual_preds) - vote_fail

    # Changed: 다양한 앙상블 전략.
    avg_p_fail = sum(p_fails) / len(p_fails)
    sorted_pf = sorted(p_fails)
    median_p_fail = sorted_pf[len(sorted_pf) // 2]

    if strategy == "majority":
        prediction = "fail" if vote_fail > vote_pass else "pass"
    elif strategy == "median":
        prediction = "fail" if median_p_fail > threshold else "pass"
    else:  # average (기본값)
        prediction = "fail" if avg_p_fail > threshold else "pass"

    return {
        "prediction": prediction,
        "p_fail_avg": avg_p_fail,
        "p_fail_median": median_p_fail,
        "p_fails": p_fails,
        "individual_preds": individual_preds,
        "vote_pass": vote_pass,
        "vote_fail": vote_fail,
    }


# ============================================================
# 단일 pass 예측 (비교용 baseline)
# ============================================================
def predict_single(
    model,
    tokenizer,
    prompt: str,
    pass_id: int,
    fail_id: int,
    threshold: float = 0.5,
    max_length: int = 2048,
) -> dict:
    """단일 forward pass (T=1.0) — baseline 비교용.

    Changed: consistency 결과와 동일한 형식으로 반환.
    Why: 단일 pass와 consistency 결과를 직접 비교하기 위함.
    """
    p_fail = get_p_fail_with_temperature(
        model, tokenizer, prompt, pass_id, fail_id,
        temperature=1.0, max_length=max_length,
    )
    prediction = "fail" if p_fail > threshold else "pass"
    return {
        "prediction": prediction,
        "p_fail": p_fail,
    }


# ============================================================
# Public 20 평가
# ============================================================
def eval_public_consistency(
    model,
    tokenizer,
    pass_id: int,
    fail_id: int,
    dataset_root: Path,
    temperatures: list[float],
    threshold: float = 0.5,
    strategy: str = "average",
    max_length: int = 2048,
) -> list[dict]:
    """Public 20 케이스를 self-consistency로 평가.

    Changed: 단일 pass와 consistency 결과를 동시에 기록.
    Why: 개선 효과를 직접 비교.
    """
    # Changed: label.jsonl 로드.
    labels = {}
    label_path = dataset_root / "label.jsonl"
    with label_path.open() as f:
        for line in f:
            rec = json.loads(line.strip())
            labels[rec["filename"]] = str(rec["label"]).strip().lower()

    testcase_dir = dataset_root / "testcases"
    results = []

    for path in sorted(testcase_dir.glob("tc*.json")):
        if path.name not in labels:
            continue

        with path.open() as f:
            steps = json.load(f)

        # Changed: records 파싱 — dict이면 "records" 키 확인.
        if isinstance(steps, dict) and "records" in steps:
            steps = steps["records"]
        records = [item for item in steps if isinstance(item, dict)]
        if not records:
            continue

        gold = labels[path.name]
        prompt = format_trajectory_rich(records)

        # Changed: 단일 pass baseline.
        t0 = time.time()
        single_result = predict_single(
            model, tokenizer, prompt, pass_id, fail_id,
            threshold=threshold, max_length=max_length,
        )
        single_time = time.time() - t0

        # Changed: self-consistency (N회 forward pass).
        t0 = time.time()
        consistency_result = predict_consistency(
            model, tokenizer, prompt, pass_id, fail_id,
            temperatures=temperatures,
            threshold=threshold,
            strategy=strategy,
            max_length=max_length,
        )
        consistency_time = time.time() - t0

        result = {
            "file": path.name,
            "gold": gold,
            # 단일 pass 결과
            "single_pred": single_result["prediction"],
            "single_p_fail": single_result["p_fail"],
            "single_time": single_time,
            # Consistency 결과
            "consistency_pred": consistency_result["prediction"],
            "consistency_p_fail_avg": consistency_result["p_fail_avg"],
            "consistency_p_fail_median": consistency_result["p_fail_median"],
            "consistency_p_fails": consistency_result["p_fails"],
            "consistency_individual": consistency_result["individual_preds"],
            "consistency_vote_pass": consistency_result["vote_pass"],
            "consistency_vote_fail": consistency_result["vote_fail"],
            "consistency_time": consistency_time,
        }
        results.append(result)

        # Changed: 케이스별 실시간 로그.
        s_ok = "OK" if single_result["prediction"] == gold else "XX"
        c_ok = "OK" if consistency_result["prediction"] == gold else "XX"
        logger.info(
            "%s gold=%s | single=%s(%.3f) %s | consistency=%s(avg=%.3f) %s | "
            "votes: %d/%d | p_fails=%s",
            path.name, gold,
            single_result["prediction"], single_result["p_fail"], s_ok,
            consistency_result["prediction"], consistency_result["p_fail_avg"], c_ok,
            consistency_result["vote_fail"], len(temperatures),
            [f"{pf:.3f}" for pf in consistency_result["p_fails"]],
        )

    return results


# ============================================================
# 결과 리포트
# ============================================================
def print_report(results: list[dict], temperatures: list[float], strategy: str, threshold: float):
    """단일 pass vs self-consistency 비교 리포트 출력.

    Changed: 정확도, 변화된 케이스, 전략별 결과를 상세히 출력.
    Why: 개선 효과를 정량적으로 확인.
    """
    n = len(results)
    if n == 0:
        print("결과 없음.")
        return

    # 단일 pass 메트릭
    s_correct = sum(1 for r in results if r["single_pred"] == r["gold"])
    s_tp = sum(1 for r in results if r["gold"] == "fail" and r["single_pred"] == "fail")
    s_fp = sum(1 for r in results if r["gold"] == "pass" and r["single_pred"] == "fail")
    s_fn = sum(1 for r in results if r["gold"] == "fail" and r["single_pred"] == "pass")
    s_tn = sum(1 for r in results if r["gold"] == "pass" and r["single_pred"] == "pass")
    s_prec = s_tp / (s_tp + s_fp) if (s_tp + s_fp) > 0 else 0
    s_rec = s_tp / (s_tp + s_fn) if (s_tp + s_fn) > 0 else 0
    s_f1 = 2 * s_prec * s_rec / (s_prec + s_rec) if (s_prec + s_rec) > 0 else 0
    s_total_time = sum(r["single_time"] for r in results)

    # Consistency 메트릭
    c_correct = sum(1 for r in results if r["consistency_pred"] == r["gold"])
    c_tp = sum(1 for r in results if r["gold"] == "fail" and r["consistency_pred"] == "fail")
    c_fp = sum(1 for r in results if r["gold"] == "pass" and r["consistency_pred"] == "fail")
    c_fn = sum(1 for r in results if r["gold"] == "fail" and r["consistency_pred"] == "pass")
    c_tn = sum(1 for r in results if r["gold"] == "pass" and r["consistency_pred"] == "pass")
    c_prec = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0
    c_rec = c_tp / (c_tp + c_fn) if (c_tp + c_fn) > 0 else 0
    c_f1 = 2 * c_prec * c_rec / (c_prec + c_rec) if (c_prec + c_rec) > 0 else 0
    c_total_time = sum(r["consistency_time"] for r in results)

    print("\n" + "=" * 80)
    print(f"Self-Consistency 평가 결과 (strategy={strategy}, threshold={threshold})")
    print(f"Temperatures: {temperatures}")
    print("=" * 80)

    print(f"\n{'메트릭':<25} {'단일 Pass':>15} {'Consistency':>15} {'변화':>10}")
    print("-" * 65)
    print(f"{'정확도':<25} {s_correct}/{n} ({s_correct/n*100:.1f}%){'':<4} "
          f"{c_correct}/{n} ({c_correct/n*100:.1f}%){'':<4} "
          f"{c_correct - s_correct:+d}")
    print(f"{'Precision(fail)':<25} {s_prec:>15.4f} {c_prec:>15.4f} {c_prec - s_prec:>+10.4f}")
    print(f"{'Recall(fail)':<25} {s_rec:>15.4f} {c_rec:>15.4f} {c_rec - s_rec:>+10.4f}")
    print(f"{'F1(fail)':<25} {s_f1:>15.4f} {c_f1:>15.4f} {c_f1 - s_f1:>+10.4f}")
    print(f"{'TP/FP/FN/TN':<25} {s_tp}/{s_fp}/{s_fn}/{s_tn}{'':<8} "
          f"{c_tp}/{c_fp}/{c_fn}/{c_tn}")
    print(f"{'총 시간 (초)':<25} {s_total_time:>15.1f} {c_total_time:>15.1f}")
    print(f"{'케이스당 시간 (초)':<25} {s_total_time/n:>15.2f} {c_total_time/n:>15.2f}")

    # Changed: 예측이 변한 케이스 강조.
    # Why: consistency가 기존 단일 pass와 다른 결정을 내린 케이스를 확인.
    changed = [r for r in results if r["single_pred"] != r["consistency_pred"]]
    if changed:
        print(f"\n예측 변경된 케이스 ({len(changed)}건):")
        print(f"  {'파일':<15} {'Gold':>5} {'단일':>6} {'Consist':>8} "
              f"{'단일 p_f':>10} {'avg p_f':>10} {'결과':>6}")
        print("  " + "-" * 60)
        for r in changed:
            s_ok = "OK" if r["single_pred"] == r["gold"] else "XX"
            c_ok = "OK" if r["consistency_pred"] == r["gold"] else "XX"
            effect = ""
            if s_ok == "XX" and c_ok == "OK":
                effect = "개선"
            elif s_ok == "OK" and c_ok == "XX":
                effect = "악화"
            print(f"  {r['file']:<15} {r['gold']:>5} {r['single_pred']:>6} "
                  f"{r['consistency_pred']:>8} {r['single_p_fail']:>10.4f} "
                  f"{r['consistency_p_fail_avg']:>10.4f} {effect:>6}")
    else:
        print("\n예측 변경 없음 — 단일 pass와 consistency 결과 동일.")

    # Changed: 경계 케이스 (p_fail이 threshold 근처) 분석.
    # Why: consistency가 가장 효과적인 영역 = 불확실한 케이스.
    print(f"\n경계 케이스 (|p_fail - {threshold}| < 0.15):")
    borderline = [r for r in results
                  if abs(r["single_p_fail"] - threshold) < 0.15]
    if borderline:
        for r in borderline:
            s_ok = "OK" if r["single_pred"] == r["gold"] else "XX"
            c_ok = "OK" if r["consistency_pred"] == r["gold"] else "XX"
            print(f"  {r['file']}: gold={r['gold']}, "
                  f"single={r['single_pred']}({r['single_p_fail']:.4f}) {s_ok}, "
                  f"consist={r['consistency_pred']}(avg={r['consistency_p_fail_avg']:.4f}) {c_ok}, "
                  f"votes={r['consistency_vote_fail']}/{len(temperatures)}")
    else:
        print("  없음.")

    # Changed: temperature별 개별 정확도.
    # Why: 어떤 temperature가 가장 좋은지 파악.
    print(f"\nTemperature별 개별 정확도:")
    for t_idx, temp in enumerate(temperatures):
        t_correct = 0
        for r in results:
            if t_idx < len(r["consistency_individual"]):
                if r["consistency_individual"][t_idx] == r["gold"]:
                    t_correct += 1
        print(f"  T={temp:.1f}: {t_correct}/{n} ({t_correct/n*100:.1f}%)")


# ============================================================
# Threshold sweep (최적 threshold 탐색)
# ============================================================
def sweep_thresholds(results: list[dict], temperatures: list[float]):
    """다양한 threshold에서 consistency 정확도를 탐색.

    Changed: 0.3~0.9 범위에서 0.05 간격으로 sweep.
    Why: 최적 threshold는 데이터에 따라 다름 — 실험적으로 탐색.
    """
    print(f"\nThreshold Sweep (average p_fail 기준):")
    print(f"  {'Threshold':>10} {'정확도':>10} {'Correct':>10} {'TP':>5} {'FP':>5} {'FN':>5} {'TN':>5}")
    print("  " + "-" * 55)

    best_acc = 0
    best_th = 0.5
    n = len(results)

    for th_int in range(30, 91, 5):
        th = th_int / 100.0
        correct = 0
        tp = fp = fn = tn = 0
        for r in results:
            pred = "fail" if r["consistency_p_fail_avg"] > th else "pass"
            gold = r["gold"]
            if pred == gold:
                correct += 1
            if gold == "fail" and pred == "fail":
                tp += 1
            elif gold == "pass" and pred == "fail":
                fp += 1
            elif gold == "fail" and pred == "pass":
                fn += 1
            else:
                tn += 1

        acc = correct / n if n > 0 else 0
        marker = " <-- best" if acc > best_acc else ""
        if acc > best_acc:
            best_acc = acc
            best_th = th
        print(f"  {th:>10.2f} {acc*100:>9.1f}% {correct:>10} {tp:>5} {fp:>5} {fn:>5} {tn:>5}{marker}")

    print(f"\n  최적 threshold: {best_th:.2f} (정확도: {best_acc*100:.1f}%)")
    return best_th


def main():
    parser = argparse.ArgumentParser(
        description="Self-Consistency Voting 평가 (다중 temperature forward pass)"
    )
    parser.add_argument(
        "--adapter-path",
        required=True,
        help="LoRA 어댑터 경로",
    )
    parser.add_argument(
        "--base-model",
        default="Qwen/Qwen3.5-4B",
        help="베이스 모델 (기본값: Qwen/Qwen3.5-4B)",
    )
    parser.add_argument(
        "--dataset-root",
        default="/dl2026/dataset",
        help="공개 데이터셋 루트 (label.jsonl + testcases/)",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=5,
        help="Forward pass 횟수 (temperatures 미지정 시 자동 생성)",
    )
    parser.add_argument(
        "--temperatures",
        type=str,
        default="0.5,0.7,0.9,1.1,1.3",
        help="Temperature 리스트 (쉼표 구분). 지정 시 --n-samples 무시.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="p_fail > threshold → fail (기본값: 0.5)",
    )
    parser.add_argument(
        "--strategy",
        choices=["average", "majority", "median"],
        default="average",
        help="앙상블 전략: average(기본), majority, median",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=2048,
        help="토큰 최대 길이 (기본값: 2048)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Threshold sweep 수행 (최적 threshold 탐색)",
    )
    parser.add_argument(
        "--save-results",
        type=str,
        default=None,
        help="결과를 JSON 파일로 저장 (경로 지정)",
    )
    args = parser.parse_args()

    # Changed: temperature 리스트 파싱.
    if args.temperatures:
        temperatures = [float(t) for t in args.temperatures.split(",")]
    else:
        # Changed: n-samples 기반 자동 생성 (0.5 ~ 1.5 범위 균등 분배).
        step = 1.0 / (args.n_samples - 1) if args.n_samples > 1 else 0
        temperatures = [0.5 + step * i for i in range(args.n_samples)]

    logger.info("설정: adapter=%s, base=%s, temperatures=%s, threshold=%.2f, strategy=%s",
                args.adapter_path, args.base_model, temperatures, args.threshold, args.strategy)

    # Changed: 어댑터 경로 검증.
    if not os.path.exists(args.adapter_path):
        logger.error("어댑터 경로 없음: %s", args.adapter_path)
        sys.exit(1)

    dataset_root = Path(args.dataset_root)
    if not dataset_root.exists():
        logger.error("데이터셋 경로 없음: %s", args.dataset_root)
        sys.exit(1)

    # 1. 모델 로드
    model, tokenizer, pass_id, fail_id = load_model(args.base_model, args.adapter_path)

    # 2. 평가 수행
    logger.info("Public 20 self-consistency 평가 시작...")
    t0 = time.time()
    results = eval_public_consistency(
        model, tokenizer, pass_id, fail_id,
        dataset_root, temperatures,
        threshold=args.threshold,
        strategy=args.strategy,
        max_length=args.max_length,
    )
    elapsed = time.time() - t0
    logger.info("평가 완료: %.1f초 (%.1f초/케이스)", elapsed, elapsed / max(len(results), 1))

    # 3. 결과 리포트
    print_report(results, temperatures, args.strategy, args.threshold)

    # 4. Threshold sweep (선택)
    if args.sweep:
        sweep_thresholds(results, temperatures)

    # 5. 결과 저장 (선택)
    if args.save_results:
        with open(args.save_results, "w") as f:
            json.dump({
                "config": {
                    "adapter_path": args.adapter_path,
                    "base_model": args.base_model,
                    "temperatures": temperatures,
                    "threshold": args.threshold,
                    "strategy": args.strategy,
                },
                "results": results,
            }, f, indent=2, default=str)
        logger.info("결과 저장: %s", args.save_results)

    # 6. 메모리 해제
    del model
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    logger.info("완료.")


if __name__ == "__main__":
    main()
