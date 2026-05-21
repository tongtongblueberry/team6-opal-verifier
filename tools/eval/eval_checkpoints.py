"""Experiment A 체크포인트 전수 평가 — 최적 에폭 선택.

각 에폭 체크포인트(checkpoint-*)와 final 어댑터를 순차적으로 로드하여
public 20 테스트케이스에 대해 logit 비교 방식으로 평가.
결과를 표로 출력하고 JSON으로 저장.

실행 방법 (서버에서):
  cd /workspace/team6/team6-opal-verifier
  python tools/eval/eval_checkpoints.py

옵션:
  --adapter-dir DIR   체크포인트 상위 디렉토리 (기본: /workspace/team6/adapters/exp_a)
  --max-length N      최대 시퀀스 길이 (기본: 2048)
  --threshold T       pass/fail 판정 임계값 (기본: 0.5)
  --output FILE       결과 JSON 저장 경로
  --sweep             threshold sweep 모드: 여러 임계값에 대해 정확도 계산 후 최적 (checkpoint, threshold) 조합 추천
"""
import os
import sys
import json
import math
import time
import gc
import glob
import logging
import argparse
from pathlib import Path

# Changed: CUDA 메모리 단편화 방지 설정 — 체크포인트 반복 로드 시 OOM 위험 감소
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
sys.path.insert(0, "/workspace/team6/team6-opal-verifier")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Changed: solver에서 _records()만 사용, format 함수는 lora_solver.py 인라인 버전 사용
# Why: 학습(train_exp_a.py)과 추론(lora_solver.py)이 동일한 format_trajectory_rich를 사용하므로
#       eval도 같은 함수를 사용해야 일관성 보장
from src.solver import StatefulOpalVerifier
from src.lora_solver import format_trajectory_rich, SYSTEM_PROMPT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("eval_checkpoints")

# ============================================================
# 기본 설정값
# ============================================================
BASE_MODEL = "Qwen/Qwen3.5-4B"
# Changed: MODEL_CACHE — train_exp_a.py와 동일한 캐시 경로 사용
MODEL_CACHE = "/workspace/cache/hf_cache/hub"
DEFAULT_ADAPTER_DIR = "/workspace/team6/adapters/exp_a"
DEFAULT_MAX_LENGTH = 2048
DEFAULT_THRESHOLD = 0.5
DEFAULT_OUTPUT = "/workspace/team6/eval_checkpoints_results.json"

# Changed: sweep 모드에서 탐색할 임계값 목록
SWEEP_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]

# 평가 데이터 경로
EVAL_LABELS = "/dl2026/dataset/label.jsonl"
EVAL_TESTCASES = "/dl2026/dataset/testcases"


# ============================================================
# 체크포인트 탐색
# ============================================================
def find_checkpoints(adapter_dir: str) -> list[dict]:
    """adapter_dir 아래의 모든 체크포인트와 final 어댑터를 찾아 정렬하여 반환.

    반환 형식: [{"name": "epoch-1", "path": "...", "epoch": 1, "step": 26}, ...]
    """
    checkpoints = []

    # Changed: checkpoint-{step} 디렉토리 탐색 — 에폭별 step 번호로 정렬
    ckpt_pattern = os.path.join(adapter_dir, "checkpoints", "checkpoint-*")
    ckpt_dirs = glob.glob(ckpt_pattern)

    for ckpt_dir in ckpt_dirs:
        # adapter_config.json이 있는지 확인 — 유효한 LoRA 체크포인트인지 검증
        if not os.path.isfile(os.path.join(ckpt_dir, "adapter_config.json")):
            logger.warning("체크포인트에 adapter_config.json 없음, 건너뜀: %s", ckpt_dir)
            continue

        # step 번호 추출
        dirname = os.path.basename(ckpt_dir)
        try:
            step_num = int(dirname.split("-")[-1])
        except ValueError:
            logger.warning("체크포인트 이름에서 step 번호 추출 실패: %s", dirname)
            continue

        checkpoints.append({
            "name": dirname,
            "path": ckpt_dir,
            "step": step_num,
        })

    # step 번호로 정렬
    checkpoints.sort(key=lambda x: x["step"])

    # Changed: 에폭 번호 할당 — step 순서대로 epoch 1, 2, 3, ...
    for i, ckpt in enumerate(checkpoints):
        ckpt["epoch"] = i + 1

    # final 어댑터 추가
    final_dir = os.path.join(adapter_dir, "final")
    if os.path.isdir(final_dir) and os.path.isfile(os.path.join(final_dir, "adapter_config.json")):
        checkpoints.append({
            "name": "final",
            "path": final_dir,
            "step": -1,  # final은 step 번호 없음
            "epoch": len(checkpoints) + 1,  # 마지막 에폭 다음
        })
    else:
        logger.warning("Final 어댑터 없음: %s", final_dir)

    return checkpoints


# ============================================================
# 테스트케이스 준비 (1회만 수행)
# ============================================================
def prepare_test_cases() -> list[dict]:
    """Public 20 테스트케이스를 로드하고 포맷하여 반환.

    반환 형식: [{"fname": "tc1.json", "gold": "pass", "prompt": "..."}, ...]
    """
    # label 로드
    if not os.path.exists(EVAL_LABELS):
        logger.error("라벨 파일 없음: %s", EVAL_LABELS)
        return []

    pub_labels = {}
    with open(EVAL_LABELS) as f:
        for line in f:
            d = json.loads(line)
            pub_labels[d["filename"]] = d["label"]

    logger.info("라벨 로드: %d개", len(pub_labels))

    # Changed: StatefulOpalVerifier._records()로 trajectory를 records로 변환
    # Why: lora_solver.py와 동일한 전처리 파이프라인 사용
    verifier = StatefulOpalVerifier()
    test_cases = []

    tc_files = sorted(glob.glob(os.path.join(EVAL_TESTCASES, "tc*.json")))
    if not tc_files:
        logger.error("테스트케이스 없음: %s", EVAL_TESTCASES)
        return []

    for f in tc_files:
        fname = os.path.basename(f)
        gold = pub_labels.get(fname)
        if gold is None:
            continue

        with open(f) as handle:
            steps = json.load(handle)
        records = verifier._records(steps)
        if not records:
            logger.warning("records 비어있음, 건너뜀: %s", fname)
            continue

        # Changed: format_trajectory_rich — lora_solver.py와 동일한 포맷 함수
        prompt = format_trajectory_rich(records)
        test_cases.append({
            "fname": fname,
            "gold": gold,
            "prompt": prompt,
        })

    logger.info("테스트케이스 준비 완료: %d개", len(test_cases))
    return test_cases


# ============================================================
# 단일 체크포인트 평가
# ============================================================
def evaluate_checkpoint(
    ckpt: dict,
    test_cases: list[dict],
    tokenizer: AutoTokenizer,
    pass_id: int,
    fail_id: int,
    max_length: int,
    threshold: float,
) -> dict:
    """단일 체크포인트를 로드하여 모든 테스트케이스를 평가하고 결과 반환.

    Changed: 모델을 매번 새로 로드하고 평가 후 완전히 해제
    Why: 메모리 누수 방지 — PeftModel은 merge/unmerge가 불완전할 수 있음
    """
    ckpt_name = ckpt["name"]
    ckpt_path = ckpt["path"]
    epoch = ckpt["epoch"]
    step = ckpt["step"]

    logger.info("=" * 60)
    logger.info("체크포인트 평가 시작: %s (epoch=%d, step=%d)", ckpt_name, epoch, step)
    logger.info("경로: %s", ckpt_path)
    t0 = time.time()

    # Changed: base model 로드 — float16 + auto device map
    try:
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
            cache_dir=MODEL_CACHE,
        )
    except Exception as e:
        logger.error("베이스 모델 로드 실패: %s", e)
        return {"checkpoint": ckpt_name, "epoch": epoch, "step": step, "error": str(e)}

    # Changed: LoRA 어댑터 로드
    try:
        model = PeftModel.from_pretrained(base_model, ckpt_path)
        model.eval()
    except Exception as e:
        logger.error("어댑터 로드 실패 (%s): %s", ckpt_path, e)
        del base_model
        gc.collect()
        torch.cuda.empty_cache()
        return {"checkpoint": ckpt_name, "epoch": epoch, "step": step, "error": str(e)}

    load_time = time.time() - t0
    logger.info("모델 로드 완료: %.1fs", load_time)

    # 테스트케이스별 평가
    results = []
    correct = 0
    total = len(test_cases)

    for tc in test_cases:
        # Changed: chat template 적용 — enable_thinking=False (Qwen3.5 thinking 모드 비활성화)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": tc["prompt"]},
        ]
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            # enable_thinking 미지원 tokenizer fallback
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        # Changed: tokenize + truncation — train_exp_a.py와 동일한 max_length 사용
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
        )
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        # Changed: logit 비교 방식 — generation이 아닌 마지막 토큰의 logit으로 판정
        # Why: lora_solver.py와 동일한 추론 방식 유지
        try:
            with torch.no_grad():
                logits = model(**inputs).logits[0, -1, :]

            p_logit = logits[pass_id].item()
            f_logit = logits[fail_id].item()

            # Changed: 수치 안정성을 위한 softmax — max 빼기 후 exp
            mx = max(p_logit, f_logit)
            p_fail = math.exp(f_logit - mx) / (math.exp(p_logit - mx) + math.exp(f_logit - mx))
            pred = "fail" if p_fail > threshold else "pass"
            error_msg = None
        except torch.cuda.OutOfMemoryError:
            # Changed: OOM 발생 시 해당 케이스만 건너뜀 — 전체 평가를 중단하지 않음
            logger.warning("OOM on %s — 이 케이스 건너뜀", tc["fname"])
            torch.cuda.empty_cache()
            p_fail = 0.5
            pred = "unknown"
            error_msg = "OOM"
        except Exception as e:
            logger.warning("추론 실패 %s: %s", tc["fname"], e)
            p_fail = 0.5
            pred = "unknown"
            error_msg = str(e)

        ok = pred == tc["gold"]
        if ok:
            correct += 1

        results.append({
            "fname": tc["fname"],
            "gold": tc["gold"],
            "pred": pred,
            "p_fail": round(p_fail, 4),
            "correct": ok,
            "error": error_msg,
        })

    eval_time = time.time() - t0
    accuracy = correct / total if total > 0 else 0.0

    logger.info(
        "결과: %s — %d/%d (%.1f%%) — 소요시간: %.1fs",
        ckpt_name, correct, total, accuracy * 100, eval_time,
    )

    # Changed: 모델 완전 해제 — 다음 체크포인트 로드를 위한 GPU 메모리 확보
    del model, base_model
    gc.collect()
    torch.cuda.empty_cache()

    return {
        "checkpoint": ckpt_name,
        "epoch": epoch,
        "step": step,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "per_case": results,
        "load_time_s": round(load_time, 1),
        "eval_time_s": round(eval_time, 1),
    }


# ============================================================
# 결과 출력 (테이블 형식)
# ============================================================
def print_summary_table(all_results: list[dict], test_cases: list[dict]):
    """모든 체크포인트의 평가 결과를 비교 테이블로 출력."""
    print()
    print("=" * 100)
    print("CHECKPOINT EVALUATION SUMMARY")
    print("=" * 100)

    # 상단: 체크포인트별 정확도 요약
    print()
    print(f"{'Checkpoint':<20} {'Epoch':<7} {'Step':<8} {'Accuracy':<12} {'Time(s)':<10}")
    print("-" * 60)
    for res in all_results:
        if "error" in res and "accuracy" not in res:
            print(f"{res['checkpoint']:<20} {res['epoch']:<7} {res['step']:<8} ERROR: {res['error']}")
            continue
        acc_str = f"{res['correct']}/{res['total']} ({res['accuracy']*100:.1f}%)"
        print(f"{res['checkpoint']:<20} {res['epoch']:<7} {res['step']:<8} {acc_str:<12} {res['eval_time_s']:<10}")
    print("-" * 60)

    # Changed: 에러가 없는 결과만 필터링하여 비교 테이블 생성
    valid_results = [r for r in all_results if "per_case" in r]
    if not valid_results:
        print("유효한 결과 없음.")
        return

    # 케이스별 비교 테이블
    print()
    print("PER-CASE COMPARISON (p_fail values)")
    print("=" * 100)

    # 헤더 구성
    header = f"{'TC':<12} {'Gold':<6}"
    for res in valid_results:
        header += f" | {res['checkpoint']:<18}"
    print(header)
    print("-" * len(header))

    # 각 테스트케이스
    for i, tc in enumerate(test_cases):
        row = f"{tc['fname']:<12} {tc['gold']:<6}"
        for res in valid_results:
            if i < len(res["per_case"]):
                r = res["per_case"][i]
                mark = "OK" if r["correct"] else "XX"
                if r.get("error"):
                    row += f" | {'ERR':<18}"
                else:
                    row += f" | {r['pred']:<5} {r['p_fail']:.3f} {mark:<3}"
            else:
                row += f" | {'N/A':<18}"
        print(row)

    print("-" * len(header))

    # 합계 행
    total_row = f"{'TOTAL':<12} {'':6}"
    for res in valid_results:
        total_row += f" | {res['correct']}/{res['total']} ({res['accuracy']*100:.0f}%)       "
    print(total_row)
    print()

    # Changed: 최적 체크포인트 추천 — 정확도 기준, 동점이면 낮은 에폭(과적합 방지) 선택
    best = max(valid_results, key=lambda r: (r["accuracy"], -r["epoch"]))
    print("=" * 100)
    print(f"RECOMMENDATION: {best['checkpoint']} (epoch {best['epoch']}, step {best['step']})")
    print(f"  Accuracy: {best['correct']}/{best['total']} ({best['accuracy']*100:.1f}%)")
    print(f"  Path: {best.get('checkpoint', '')}")

    # 같은 정확도를 가진 체크포인트가 여러 개인 경우 모두 나열
    ties = [r for r in valid_results if r["accuracy"] == best["accuracy"]]
    if len(ties) > 1:
        print(f"  (동점 체크포인트 {len(ties)}개: {', '.join(r['checkpoint'] for r in ties)})")
        print(f"  -> 과적합 방지를 위해 가장 낮은 에폭 선택: epoch {best['epoch']}")

    print("=" * 100)


# ============================================================
# Threshold Sweep 관련 함수
# ============================================================
def recompute_accuracy_at_threshold(result: dict, test_cases: list[dict], threshold: float) -> dict:
    """기존 평가 결과(p_fail 값)를 재사용하여 다른 threshold에서의 정확도를 재계산.

    Changed: 모델 재로드 없이 p_fail 값만으로 threshold sweep 가능
    Why: 각 threshold마다 모델을 다시 돌리면 시간 낭비 — p_fail은 threshold 무관
    """
    if "per_case" not in result:
        return {"checkpoint": result.get("checkpoint"), "threshold": threshold, "error": "no per_case data"}

    correct = 0
    total = len(result["per_case"])
    per_case = []

    for i, r in enumerate(result["per_case"]):
        if r.get("error"):
            pred = "unknown"
        else:
            pred = "fail" if r["p_fail"] > threshold else "pass"

        gold = test_cases[i]["gold"] if i < len(test_cases) else r["gold"]
        ok = pred == gold
        if ok:
            correct += 1
        per_case.append({
            "fname": r["fname"],
            "gold": gold,
            "pred": pred,
            "p_fail": r["p_fail"],
            "correct": ok,
        })

    accuracy = correct / total if total > 0 else 0.0
    return {
        "checkpoint": result["checkpoint"],
        "epoch": result.get("epoch"),
        "step": result.get("step"),
        "threshold": threshold,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "per_case": per_case,
    }


def print_sweep_summary_table(all_results: list[dict], test_cases: list[dict], thresholds: list[float]):
    """Threshold sweep 결과를 checkpoint x threshold 매트릭스로 출력.

    Changed: 각 checkpoint별 최적 threshold와 전체 최적 조합을 표시
    """
    # all_results에서 per_case가 있는 것만 사용
    valid_results = [r for r in all_results if "per_case" in r]
    if not valid_results:
        print("유효한 결과 없음.")
        return

    print()
    print("=" * 120)
    print("THRESHOLD SWEEP RESULTS")
    print("=" * 120)

    # Changed: checkpoint x threshold accuracy 매트릭스 구성
    # matrix[ckpt_name] = {threshold: {"correct": ..., "total": ..., "accuracy": ...}}
    matrix = {}
    for res in valid_results:
        ckpt_name = res["checkpoint"]
        if ckpt_name not in matrix:
            matrix[ckpt_name] = {}
        for thr in thresholds:
            sweep_res = recompute_accuracy_at_threshold(res, test_cases, thr)
            matrix[ckpt_name][thr] = sweep_res

    # Changed: 테이블 헤더 — checkpoint x threshold 매트릭스 + best 컬럼
    thr_strs = [f"{t:.2f}" for t in thresholds]
    header = f"{'Checkpoint':<20}"
    for ts in thr_strs:
        header += f" | {ts:>7}"
    header += f" | {'BestThr':>7} {'BestAcc':>9}"
    print(header)
    print("-" * len(header))

    # Changed: 전체 최적 조합 추적
    global_best_acc = -1.0
    global_best_ckpt = None
    global_best_thr = None

    for res in valid_results:
        ckpt_name = res["checkpoint"]
        row = f"{ckpt_name:<20}"

        best_thr_for_ckpt = None
        best_acc_for_ckpt = -1.0

        for thr in thresholds:
            sweep_res = matrix[ckpt_name][thr]
            acc = sweep_res["accuracy"]
            correct = sweep_res["correct"]
            total = sweep_res["total"]
            row += f" | {correct:>2}/{total:<2} "

            # 동점이면 0.5에 가까운 threshold 선호 (안정적)
            if acc > best_acc_for_ckpt or (acc == best_acc_for_ckpt and abs(thr - 0.5) < abs(best_thr_for_ckpt - 0.5)):
                best_acc_for_ckpt = acc
                best_thr_for_ckpt = thr

        row += f" |  {best_thr_for_ckpt:.2f}  {best_acc_for_ckpt*100:>5.1f}%"
        print(row)

        # 전체 최적 갱신
        if best_acc_for_ckpt > global_best_acc or (
            best_acc_for_ckpt == global_best_acc and (
                global_best_ckpt is None or res.get("epoch", 999) < global_best_epoch
            )
        ):
            global_best_acc = best_acc_for_ckpt
            global_best_ckpt = ckpt_name
            global_best_thr = best_thr_for_ckpt
            global_best_epoch = res.get("epoch", 999)

    print("-" * len(header))
    print()

    # Changed: 최적 (checkpoint, threshold) 조합 추천
    print("=" * 80)
    print(f"BEST COMBINATION: {global_best_ckpt} @ threshold={global_best_thr:.2f}")
    best_detail = matrix.get(global_best_ckpt, {}).get(global_best_thr)
    if best_detail:
        print(f"  Accuracy: {best_detail['correct']}/{best_detail['total']} ({global_best_acc*100:.1f}%)")
    print("=" * 80)

    # Changed: 최적 threshold에서의 per-case 결과도 출력
    if best_detail and "per_case" in best_detail:
        print()
        print(f"PER-CASE DETAIL for {global_best_ckpt} @ threshold={global_best_thr:.2f}")
        print("-" * 60)
        for r in best_detail["per_case"]:
            mark = "OK" if r["correct"] else "XX"
            print(f"  {r['fname']:<12} gold={r['gold']:<5} pred={r['pred']:<5} p_fail={r['p_fail']:.4f} {mark}")
        print()

    return {
        "best_checkpoint": global_best_ckpt,
        "best_threshold": global_best_thr,
        "best_accuracy": global_best_acc,
        "matrix": {
            ckpt_name: {
                str(thr): {
                    "correct": matrix[ckpt_name][thr]["correct"],
                    "total": matrix[ckpt_name][thr]["total"],
                    "accuracy": matrix[ckpt_name][thr]["accuracy"],
                }
                for thr in thresholds
            }
            for ckpt_name in matrix
        },
    }


# ============================================================
# 메인 실행
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Experiment A 체크포인트 전수 평가 — 최적 에폭 선택",
    )
    parser.add_argument(
        "--adapter-dir",
        type=str,
        default=DEFAULT_ADAPTER_DIR,
        help=f"체크포인트 상위 디렉토리 (기본: {DEFAULT_ADAPTER_DIR})",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_MAX_LENGTH,
        help=f"최대 시퀀스 길이 (기본: {DEFAULT_MAX_LENGTH})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"pass/fail 판정 임계값 (기본: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT,
        help=f"결과 JSON 저장 경로 (기본: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="특정 체크포인트만 평가 (쉼표 구분, 예: checkpoint-26,checkpoint-52,final)",
    )
    # Changed: --sweep 플래그 추가 — threshold sweep 모드 활성화
    # Why: 최적 threshold를 자동으로 탐색하여 정확도 최대화
    parser.add_argument(
        "--sweep",
        action="store_true",
        default=False,
        help="threshold sweep 모드: 여러 임계값(0.30~0.70)에 대해 정확도 비교 후 최적 조합 추천",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Checkpoint Evaluation — 최적 에폭 탐색")
    logger.info("=" * 60)
    logger.info("Adapter dir: %s", args.adapter_dir)
    logger.info("Max length: %d", args.max_length)
    logger.info("Threshold: %.2f", args.threshold)
    logger.info("Sweep mode: %s", "ON" if args.sweep else "OFF")
    logger.info("Output: %s", args.output)

    # ---- 1. 체크포인트 탐색 ----
    checkpoints = find_checkpoints(args.adapter_dir)
    if not checkpoints:
        logger.error("체크포인트를 찾을 수 없음: %s", args.adapter_dir)
        logger.error("확인 사항:")
        logger.error("  - %s/checkpoints/checkpoint-* 디렉토리 존재 여부", args.adapter_dir)
        logger.error("  - 각 체크포인트에 adapter_config.json 파일 존재 여부")
        sys.exit(1)

    # Changed: --only 옵션으로 특정 체크포인트만 필터링
    if args.only:
        only_names = set(args.only.split(","))
        checkpoints = [c for c in checkpoints if c["name"] in only_names]
        if not checkpoints:
            logger.error("--only로 지정한 체크포인트를 찾을 수 없음: %s", args.only)
            sys.exit(1)

    logger.info("발견된 체크포인트: %d개", len(checkpoints))
    for ckpt in checkpoints:
        logger.info("  - %s (epoch=%d, step=%d, path=%s)",
                     ckpt["name"], ckpt["epoch"], ckpt["step"], ckpt["path"])

    # ---- 2. 테스트케이스 준비 ----
    test_cases = prepare_test_cases()
    if not test_cases:
        logger.error("테스트케이스가 없음. 종료.")
        sys.exit(1)

    # ---- 3. Tokenizer 로드 (1회만) ----
    logger.info("Tokenizer 로드: %s", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Changed: pass/fail 토큰 ID — 모든 체크포인트에서 공유 (동일 tokenizer)
    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]
    logger.info("Token IDs: pass=%d, fail=%d", pass_id, fail_id)

    # ---- 4. 각 체크포인트 순차 평가 ----
    all_results = []
    total_t0 = time.time()

    for i, ckpt in enumerate(checkpoints):
        logger.info("[%d/%d] 평가 중: %s", i + 1, len(checkpoints), ckpt["name"])

        result = evaluate_checkpoint(
            ckpt=ckpt,
            test_cases=test_cases,
            tokenizer=tokenizer,
            pass_id=pass_id,
            fail_id=fail_id,
            max_length=args.max_length,
            threshold=args.threshold,
        )
        all_results.append(result)

        # Changed: 중간 결과 출력 — 진행 상황 확인용
        if "accuracy" in result:
            logger.info(
                "[진행] %s: %d/%d (%.1f%%) -- 누적 시간: %.0fs",
                result["checkpoint"],
                result["correct"],
                result["total"],
                result["accuracy"] * 100,
                time.time() - total_t0,
            )

    total_elapsed = time.time() - total_t0
    logger.info("전체 평가 완료: %.0fs (%.1f분)", total_elapsed, total_elapsed / 60)

    # ---- 5. 결과 테이블 출력 ----
    print_summary_table(all_results, test_cases)

    # ---- 5b. Sweep 모드: threshold sweep 수행 ----
    # Changed: --sweep 플래그가 있으면 여러 threshold에 대해 정확도를 재계산
    # Why: p_fail 값은 threshold와 무관하므로 모델 재로드 없이 sweep 가능
    sweep_data = None
    if args.sweep:
        logger.info("Threshold sweep 시작: %s", SWEEP_THRESHOLDS)
        sweep_data = print_sweep_summary_table(all_results, test_cases, SWEEP_THRESHOLDS)

    # ---- 6. 결과 JSON 저장 ----
    # Changed: per_case의 p_fail 값을 소수점 4자리로 반올림하여 저장 크기 절약
    output_data = {
        "metadata": {
            "base_model": BASE_MODEL,
            "adapter_dir": args.adapter_dir,
            "max_length": args.max_length,
            "threshold": args.threshold,
            "sweep_mode": args.sweep,
            "sweep_thresholds": SWEEP_THRESHOLDS if args.sweep else None,
            "num_checkpoints": len(checkpoints),
            "num_test_cases": len(test_cases),
            "total_time_s": round(total_elapsed, 1),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "results": all_results,
    }
    # Changed: sweep 결과가 있으면 JSON에 추가
    if sweep_data:
        output_data["sweep"] = sweep_data

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    logger.info("결과 저장: %s", args.output)

    # ---- 7. 최적 체크포인트 추천 (최종 출력) ----
    valid = [r for r in all_results if "accuracy" in r]
    if valid:
        # Changed: sweep 모드에서는 sweep 결과의 best 조합을, 아닐 때는 기존 방식 사용
        if args.sweep and sweep_data:
            best_ckpt_name = sweep_data["best_checkpoint"]
            best_thr = sweep_data["best_threshold"]
            best_acc = sweep_data["best_accuracy"]
            best = next(r for r in valid if r["checkpoint"] == best_ckpt_name)
            print()
            print(f"BEST COMBINATION: {best_ckpt_name} @ threshold={best_thr:.2f}")
            ckpt_path_str = os.path.join(
                args.adapter_dir,
                "checkpoints" if best_ckpt_name != "final" else "",
                best_ckpt_name,
            )
            print(f"  Path: {ckpt_path_str}")
            sweep_detail = sweep_data["matrix"][best_ckpt_name][str(best_thr)]
            print(f"  Accuracy: {sweep_detail['correct']}/{sweep_detail['total']} ({best_acc*100:.1f}%)")
            print(f"  Threshold: {best_thr:.2f}")
        else:
            best = max(valid, key=lambda r: (r["accuracy"], -r["epoch"]))
            print()
            print(f"BEST CHECKPOINT: {best['checkpoint']}")
            print(f"  Path: {os.path.join(args.adapter_dir, 'checkpoints' if best['checkpoint'] != 'final' else '', best['checkpoint'])}")
            print(f"  Accuracy: {best['correct']}/{best['total']} ({best['accuracy']*100:.1f}%)")

        # Changed: 최적 체크포인트를 artifacts/로 복사하는 명령어 제안
        if best["checkpoint"] != "final":
            ckpt_path = os.path.join(args.adapter_dir, "checkpoints", best["checkpoint"])
        else:
            ckpt_path = os.path.join(args.adapter_dir, "final")
        print()
        print("이 체크포인트를 제출용으로 사용하려면:")
        print(f"  cp -r {ckpt_path}/* /workspace/team6/team6-opal-verifier/artifacts/lora_adapter_v3/")
        if args.sweep and sweep_data:
            print(f"  그리고 lora_solver.py의 threshold를 {sweep_data['best_threshold']:.2f}로 설정")


if __name__ == "__main__":
    main()
