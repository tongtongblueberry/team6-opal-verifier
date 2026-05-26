"""Experiment A: r=8 LoRA + NEFTune + LoRA+ 차등 학습률.

변경 사항 요약 (기존 train_wd.py 대비):
  - r=8, alpha=16 (최적 rank — 사이클 2에서 검증)
  - NEFTune noise injection (alpha=5.0) — 임베딩에 노이즈 추가로 일반화 향상
  - LoRA+ 차등 학습률: lr_A=2.5e-5, lr_B=4e-4 (16:1 비율) — B 매트릭스를 더 빠르게 학습
  - dropout=0.0 (ALLoRA 2024 — 소량 데이터에서 dropout 해로움, NEFTune이 정규화 담당)
  - label_smoothing=0.0 (3차 OOM: label_smoother의 log_softmax가 메모리 폭발 유발 → 제거)
  - batch=1, grad_accum=16 (effective batch=16, 3차 OOM 대응: batch=2→1, accum=8→16)
  - fail oversampling (class imbalance → pass:fail ≈ 50:50)
  - validation 20% + early stopping (eval_loss 기준 best model 선택)
  - --data 인자로 다양한 데이터 소스 결합 가능
  - weight_decay=0.0 (LoRA 자체가 정규화 역할)
  - cosine LR schedule + warmup 10%
  - max_seq_len=2048
  - --max-cases로 학습 데이터 수 제한 (기본 210)
  - --resume로 체크포인트에서 재개 가능
  - 학습 후 자동으로 public 20 평가

프롬프트 형식: lora_solver.py의 format_trajectory_rich + SYSTEM_PROMPT 그대로 사용.
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
import random

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
sys.path.insert(0, "/workspace/team6/team6-opal-verifier")

# Changed: format 함수를 finetune_lora_v2에서 임포트 — 학습/추론 포맷 일관성 보장
from tools.training.finetune_lora_v2 import format_for_training_v2, format_trajectory_rich

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, TaskType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("train_exp_a")

# ============================================================
# 하이퍼파라미터 설정 — 실험 A
# ============================================================
# 모델 관련
BASE_MODEL = "Qwen/Qwen3.5-4B"
# Changed: 경로 수정 — cache_dir는 models--* 폴더가 있는 hub/ 디렉토리를 가리켜야 함
MODEL_CACHE = "/workspace/cache/hf_cache/hub"

# LoRA 관련
# Changed: LORA_R 4 → 8 (최적값 반영), LORA_ALPHA 8 → 16 (alpha = 2*r).
# Why: 사이클 2에서 r=8이 최적 rank임이 검증됨. 더 이상 sed로 변경 불필요.
LORA_R = 8
LORA_ALPHA = 16
# Changed: 사이클 9 — 사이클 2 설정 복원 + 데이터만 확대 (1변수 원칙)
# dropout 0.0 → 0.1 복원 (사이클 2 검증 설정)
LORA_DROPOUT = 0.1
TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj"]

# LoRA+ 차등 학습률 — B 매트릭스를 더 빠르게 학습
# Changed: 사이클 9 — LR 사이클 2 설정 복원 (lr_A=5e-5, lr_B=8e-4)
LR_A = 5e-5
LR_B = 8e-4
WEIGHT_DECAY = 0.0        # Changed: 0 (LoRA 자체가 regularization)

# 학습 관련
NUM_EPOCHS = 5            # Changed: 사이클 9 — 5 에폭 (충분하되 과적합 전 중단)
# Changed: bs=4에서 OOM 발생 (모델 39GB + 활성화 메모리 초과) → bs=1, accum=8로 변경
BATCH_SIZE = 1            # Changed: 2→1 (3차 OOM: batch=2에서도 label_smoother OOM 재발). Why: L40S 48GB에서 4B 모델+LoRA+grad_ckpt → batch=1이 안전 상한.
# Changed: GRAD_ACCUM 8 → 16 (effective batch size 16).
# Why: 더 큰 effective batch size로 gradient 안정화. LR도 50% 감소하여 보정.
GRAD_ACCUM = 8            # Changed: 사이클 9 — 16→8 복원 (사이클 2 설정, effective batch=8)
MAX_SEQ_LEN = 2048        # 긴 trajectory도 커버
WARMUP_RATIO = 0.1        # Changed: 10% warmup (기존 5%)
MAX_GRAD_NORM = 1.0       # gradient clipping

# NEFTune 관련
NEFTUNE_NOISE_ALPHA = 5.0  # Changed: 임베딩 노이즈 강도

# 기타
LOGGING_STEPS = 10
SAVE_STRATEGY = "epoch"
SAVE_TOTAL_LIMIT = 5      # Changed: 사이클 9 — 5 에폭이므로 5개 보존
MAX_CASES_DEFAULT = 210    # 기본 학습 데이터 수

# 경로
MUTATION_DATA = "/workspace/team6/training_data/mutation_cases.json"
ADAPTER_OUT = "/workspace/team6/adapters/cycle9"  # Changed: 사이클 9 출력 경로
CHECKPOINT_DIR = f"{ADAPTER_OUT}/checkpoints"
FINAL_DIR = f"{ADAPTER_OUT}/final"

# 평가 관련
EVAL_DATASET = "/dl2026/dataset"
EVAL_LABELS = f"{EVAL_DATASET}/label.jsonl"
EVAL_TESTCASES = f"{EVAL_DATASET}/testcases"

# lora_solver.py와 동일한 시스템 프롬프트 — 반드시 일치해야 함
SYSTEM_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory with session state, "
    "determine if the final response is consistent with the specification. "
    "Answer exactly: pass or fail"
)

IGNORE_INDEX = -100


# ============================================================
# 데이터셋 클래스 — label masking으로 답변 토큰만 학습
# ============================================================
class MutationDataset(torch.utils.data.Dataset):
    """Changed: label masking 포함 — 프롬프트 토큰은 loss에서 제외, 답변("pass"/"fail")만 학습."""

    def __init__(self, train_data, tokenizer, max_seq_len):
        self.examples = []
        skipped = 0
        for item in train_data:
            try:
                # 전체 대화 (시스템+유저+어시스턴트) 인코딩
                full = tokenizer.apply_chat_template(
                    item["messages"],
                    tokenize=False,
                    add_generation_prompt=False,
                    enable_thinking=False,
                )
                # 프롬프트만 (어시스턴트 답변 제외) 인코딩 — label masking용
                prompt = tokenizer.apply_chat_template(
                    item["messages"][:-1],
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                # enable_thinking 미지원 tokenizer fallback
                full = tokenizer.apply_chat_template(
                    item["messages"],
                    tokenize=False,
                    add_generation_prompt=False,
                )
                prompt = tokenizer.apply_chat_template(
                    item["messages"][:-1],
                    tokenize=False,
                    add_generation_prompt=True,
                )

            full_enc = tokenizer(
                full,
                truncation=True,
                max_length=max_seq_len,
                padding="max_length",
                return_tensors="pt",
            )
            prompt_enc = tokenizer(
                prompt,
                truncation=True,
                max_length=max_seq_len,
                return_tensors="pt",
            )

            ids = full_enc["input_ids"].squeeze()
            mask = full_enc["attention_mask"].squeeze()
            labels = ids.clone()

            # Changed: 프롬프트 영역을 IGNORE_INDEX로 마스킹 — 답변 토큰만 학습
            plen = prompt_enc["input_ids"].shape[1]
            if plen < max_seq_len:
                labels[:plen] = IGNORE_INDEX

            # 패딩 토큰도 마스킹
            labels[mask == 0] = IGNORE_INDEX

            # 유효한 학습 토큰이 있는 경우만 포함
            if (labels != IGNORE_INDEX).sum() > 0:
                self.examples.append({
                    "input_ids": ids,
                    "attention_mask": mask,
                    "labels": labels,
                })
            else:
                skipped += 1

        logger.info(
            "Dataset: %d examples (skipped %d — no valid answer tokens)",
            len(self.examples),
            skipped,
        )

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, i):
        return self.examples[i]


# ============================================================
# LoRA+ 차등 학습률 Trainer — A/B 매트릭스에 다른 lr 적용
# ============================================================
class LoraPlusTrainer(Trainer):
    """Changed: LoRA+ 구현 — lora_A와 lora_B에 서로 다른 학습률 적용.

    이유: Hayou et al. (2024) 'LoRA+' 논문에서 B 매트릭스의 학습률을
    A보다 크게 설정하면 수렴 속도와 최종 성능이 개선됨을 보임.
    """

    def create_optimizer(self):
        """Changed: A/B 파라미터 그룹 분리하여 차등 lr 적용."""
        if self.optimizer is not None:
            return self.optimizer

        model = self.model
        decay_params = []
        no_decay_params = []

        # Changed: lora_A 파라미터 (낮은 lr)
        lora_a_params = []
        # Changed: lora_B 파라미터 (높은 lr)
        lora_b_params = []
        # 나머지 학습 가능 파라미터 (있을 경우)
        other_params = []

        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue
            if "lora_A" in name:
                lora_a_params.append(param)
            elif "lora_B" in name:
                lora_b_params.append(param)
            else:
                other_params.append(param)

        logger.info(
            "LoRA+ param groups: lora_A=%d tensors, lora_B=%d tensors, other=%d tensors",
            len(lora_a_params),
            len(lora_b_params),
            len(other_params),
        )

        # Changed: 3개 파라미터 그룹으로 optimizer 생성
        optimizer_grouped_parameters = [
            {
                "params": lora_a_params,
                "lr": LR_A,
                "weight_decay": WEIGHT_DECAY,
            },
            {
                "params": lora_b_params,
                "lr": LR_B,
                "weight_decay": WEIGHT_DECAY,
            },
        ]

        # other_params가 있으면 추가 (일반적으로 LoRA에서는 없지만 안전장치)
        if other_params:
            optimizer_grouped_parameters.append({
                "params": other_params,
                "lr": LR_A,
                "weight_decay": WEIGHT_DECAY,
            })

        from torch.optim import AdamW
        self.optimizer = AdamW(
            optimizer_grouped_parameters,
            betas=(0.9, 0.999),
            eps=1e-8,
        )

        return self.optimizer


# ============================================================
# 평가 함수 — public 20 테스트케이스에 대해 pass/fail 예측
# ============================================================
def evaluate_public20(model, tokenizer, max_seq_len):
    """Changed: 학습 후 자동 평가 — logit 비교 방식 (lora_solver.py와 동일)."""
    logger.info("=== PUBLIC 20 EVALUATION ===")

    # label 로드
    if not os.path.exists(EVAL_LABELS):
        logger.warning("Label file not found: %s — skipping evaluation", EVAL_LABELS)
        return

    pub_labels = {}
    for line in open(EVAL_LABELS):
        d = json.loads(line)
        pub_labels[d["filename"]] = d["label"]

    # Changed: solver를 임포트하여 _records() 사용 — lora_solver.py와 동일한 전처리
    from src.solver import StatefulOpalVerifier
    verifier = StatefulOpalVerifier()

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    model.eval()
    correct = 0
    total = 0
    results = []

    tc_files = sorted(glob.glob(f"{EVAL_TESTCASES}/tc*.json"))
    if not tc_files:
        logger.warning("No test cases found in %s — skipping evaluation", EVAL_TESTCASES)
        return

    for f in tc_files:
        fname = os.path.basename(f)
        gold = pub_labels.get(fname, "?")
        if gold == "?":
            continue

        steps = json.load(open(f))
        records = verifier._records(steps)
        if not records:
            continue

        total += 1

        # Changed: lora_solver.py와 동일한 형식으로 프롬프트 생성
        prompt = format_trajectory_rich(records)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_seq_len,
        )
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        # Changed: logit 비교로 예측 — generation 모드가 아닌 logit 방식
        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]

        p_l = logits[pass_id].item()
        f_l = logits[fail_id].item()

        # softmax로 P(fail) 계산 (수치 안정성을 위해 max 빼기)
        mx = max(p_l, f_l)
        p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
        pred = "fail" if p_fail > 0.5 else "pass"

        ok = pred == gold
        if ok:
            correct += 1

        mark = "OK" if ok else "XX"
        logger.info(
            "  %s: gold=%-4s pred=%-4s p_fail=%.4f %s",
            fname, gold, pred, p_fail, mark,
        )
        results.append({
            "fname": fname,
            "gold": gold,
            "pred": pred,
            "p_fail": round(p_fail, 4),
            "correct": ok,
        })

    if total > 0:
        logger.info(
            "PUBLIC 20 RESULT: %d/%d (%.1f%%)",
            correct, total, correct / total * 100,
        )
    else:
        logger.warning("No valid test cases found for evaluation")

    # 결과 저장
    result_path = f"{ADAPTER_OUT}/eval_results.json"
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    json.dump(results, open(result_path, "w"), indent=2)
    logger.info("Eval results saved to %s", result_path)

    return results


# ============================================================
# 메인 학습 함수
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Experiment A: r=8 LoRA + NEFTune + LoRA+")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=MAX_CASES_DEFAULT,
        help=f"최대 학습 데이터 수 (기본값: {MAX_CASES_DEFAULT})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="최신 체크포인트에서 학습 재개",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="학습 후 평가 건너뛰기",
    )
    # Changed: --data CLI 인자 추가.
    # Why: mutation_cases.json 외에 다른 데이터 파일도 지정 가능 (콤마 구분).
    #      supervised manifest 등 다양한 데이터 소스를 유연하게 결합.
    parser.add_argument(
        "--data",
        type=str,
        default=MUTATION_DATA,
        help="학습 데이터 경로 (콤마로 구분하여 여러 파일 지정 가능)",
    )
    # Changed: --no-split 옵션 추가.
    # Why: 사이클 2 재현 시 전체 데이터를 학습에 사용해야 함. split이 항상 실행되어 20% 데이터 손실.
    parser.add_argument(
        "--no-split",
        action="store_true",
        help="Validation split 비활성화. 전체 데이터를 학습에 사용 (사이클 2 재현용)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Experiment A: r=%d LoRA + NEFTune(%.1f) + LoRA+(A=%.0e, B=%.0e)",
                LORA_R, NEFTUNE_NOISE_ALPHA, LR_A, LR_B)
    logger.info("=" * 60)
    logger.info("Config: epochs=%d, batch=%d, grad_accum=%d, eff_batch=%d",
                NUM_EPOCHS, BATCH_SIZE, GRAD_ACCUM, BATCH_SIZE * GRAD_ACCUM)
    logger.info("Config: max_seq_len=%d, dropout=%.2f, wd=%.4f",
                MAX_SEQ_LEN, LORA_DROPOUT, WEIGHT_DECAY)
    logger.info("Config: warmup_ratio=%.2f, max_grad_norm=%.1f",
                WARMUP_RATIO, MAX_GRAD_NORM)
    logger.info("Config: max_cases=%d, resume=%s", args.max_cases, args.resume)

    # ---- 데이터 로드 ----
    # Changed: --data CLI 인자로 여러 파일 로드 가능 (콤마 구분).
    # Why: mutation_cases.json 외에 supervised manifest 등 다양한 소스를 결합.
    data = []
    for data_path in args.data.split(","):
        data_path = data_path.strip()
        if os.path.exists(data_path):
            loaded = json.load(open(data_path))
            logger.info("Loaded %d cases from %s", len(loaded), data_path)
            data.extend(loaded)
        else:
            logger.warning("Data file not found: %s", data_path)
    logger.info("Total loaded: %d cases", len(data))

    # Changed: --max-cases로 데이터 수 제한 (기본 210)
    if args.max_cases and args.max_cases < len(data):
        data = data[: args.max_cases]
        logger.info("Truncated to %d cases (--max-cases=%d)", len(data), args.max_cases)

    # 라벨 분포 확인
    n_pass = sum(1 for c in data if c.get("label") == "pass")
    n_fail = sum(1 for c in data if c.get("label") == "fail")
    logger.info("Label distribution: pass=%d, fail=%d (total=%d)", n_pass, n_fail, len(data))

    # Changed: 사이클 9 — fail oversampling 비활성화 (1변수 원칙: 데이터만 변경)
    # if n_fail > 0 and n_pass > n_fail:
    #     fail_cases = [c for c in data if c.get("label") == "fail"]
    #     oversample_factor = max(1, round(n_pass / n_fail) - 1)
    #     data.extend(fail_cases * oversample_factor)
    #     random.shuffle(data)
    #     n_pass_new = sum(1 for c in data if c.get("label") == "pass")
    #     n_fail_new = sum(1 for c in data if c.get("label") == "fail")
    #     logger.info("After oversampling: pass=%d, fail=%d (factor=%d)", n_pass_new, n_fail_new, oversample_factor)

    # Changed: format_for_training_v2 사용 — lora_solver.py의 format_trajectory_rich와 동일한 형식
    train_data = []
    for case in data:
        records = case.get("records", [])
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue
        train_data.append(format_for_training_v2(records, case["label"]))

    logger.info("Formatted: %d training examples", len(train_data))

    if not train_data:
        logger.error("No training data! Exiting.")
        return

    # 샘플 로그
    sample_prompt = train_data[0]["messages"][1]["content"]
    logger.info("Sample prompt (first 300 chars):\n%s", sample_prompt[:300])

    # ---- Tokenizer ----
    logger.info("Loading tokenizer: %s", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ---- 데이터 분할: 80% train / 20% validation (stratified) ----
    # Changed: --no-split 옵션으로 validation split 비활성화.
    # Why: 사이클 2 재현 시 전체 데이터를 학습에 사용해야 함. split이 항상 실행되어 20% 데이터 손실.
    if args.no_split:
        train_data_raw = train_data
        val_data_raw = []
        logger.info("--no-split: 전체 %d건을 학습에 사용 (validation 없음)", len(train_data_raw))
    else:
        # Changed: validation 20% + early stopping을 위한 stratified split.
        # Why: 과적합 감지 + load_best_model_at_end로 최적 체크포인트 자동 선택.
        pass_data = [d for d in train_data if d["messages"][-1]["content"].strip().lower() == "pass"]
        fail_data = [d for d in train_data if d["messages"][-1]["content"].strip().lower() == "fail"]
        random.shuffle(pass_data)
        random.shuffle(fail_data)

        val_ratio = 0.2
        n_val_pass = max(1, int(len(pass_data) * val_ratio))
        n_val_fail = max(1, int(len(fail_data) * val_ratio)) if fail_data else 0

        val_data_raw = pass_data[:n_val_pass] + fail_data[:n_val_fail]
        train_data_raw = pass_data[n_val_pass:] + fail_data[n_val_fail:]
        random.shuffle(val_data_raw)
        random.shuffle(train_data_raw)

        logger.info(
            "Split: train=%d (pass=%d, fail=%d), val=%d (pass=%d, fail=%d)",
            len(train_data_raw),
            len(pass_data) - n_val_pass,
            len(fail_data) - n_val_fail if fail_data else 0,
            len(val_data_raw),
            n_val_pass,
            n_val_fail,
        )

    # ---- Dataset 생성 ----
    logger.info("Tokenizing train set: %d examples (max_seq_len=%d)...", len(train_data_raw), MAX_SEQ_LEN)
    dataset = MutationDataset(train_data_raw, tokenizer, MAX_SEQ_LEN)

    # Changed: val_data_raw가 비어있으면 (--no-split) val_dataset 생성 생략.
    if val_data_raw:
        logger.info("Tokenizing val set: %d examples...", len(val_data_raw))
        val_dataset = MutationDataset(val_data_raw, tokenizer, MAX_SEQ_LEN)
    else:
        val_dataset = None

    if len(dataset) == 0:
        logger.error("Empty dataset after tokenization! Exiting.")
        return

    # ---- 모델 로드 ----
    logger.info("Loading model: %s", BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )

    # Changed: r=8, alpha=16 — 사이클 2에서 최적 rank로 검증됨
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
    )
    model = get_peft_model(model, lora_cfg)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(
        "Trainable: %d / %d (%.4f%%)",
        trainable, total_params, trainable / total_params * 100,
    )

    # ---- Training Arguments ----
    # Changed: lr은 LR_B로 설정 (Trainer가 사용하는 기본 lr)
    # 실제 lr은 LoraPlusTrainer의 create_optimizer에서 A/B별로 다르게 적용
    training_args = TrainingArguments(
        output_dir=CHECKPOINT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=1,          # Changed: eval batch=1 (label_smoother의 log_softmax OOM 방지)
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR_B,                    # Changed: base lr (B 매트릭스 기준)
        weight_decay=WEIGHT_DECAY,             # Changed: 0.0 (LoRA가 정규화)
        max_grad_norm=MAX_GRAD_NORM,
        warmup_ratio=WARMUP_RATIO,             # Changed: 10% warmup
        lr_scheduler_type="cosine",            # Changed: cosine schedule
        optim="adamw_torch",                   # Changed: LoraPlusTrainer가 override하므로 이 값은 무시됨
        neftune_noise_alpha=NEFTUNE_NOISE_ALPHA,  # Changed: NEFTune 임베딩 노이즈
        # Changed: label_smoothing_factor 0.1→0.0 (3차 OOM 대응).
        # Why: label_smoothing>0이면 Trainer가 label_smoother를 사용 → log_softmax(full vocab) 추가 메모리.
        #       batch=1에서도 OOM 유발 가능하므로 제거. overconfidence는 NEFTune+dropout=0으로 충분.
        label_smoothing_factor=0.0,
        logging_steps=LOGGING_STEPS,           # 10 step마다 로그
        save_strategy=SAVE_STRATEGY,           # epoch마다 체크포인트 저장
        save_total_limit=SAVE_TOTAL_LIMIT,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_pin_memory=True,
        # Changed: validation + early stopping 설정.
        # Why: 20% validation split으로 과적합 감지. eval_loss 기준 best model 선택.
        eval_strategy="no" if args.no_split else "epoch",  # Changed: --no-split이면 eval 비활성화 / Why: validation set 없으면 eval 불가
        load_best_model_at_end=False,  # Changed: 사이클 9 — eval_loss 기반 모델 선택 비활성
        metric_for_best_model="eval_loss",
    )

    # Changed: LoraPlusTrainer 사용 — A/B 매트릭스에 차등 lr 적용
    # Changed: eval_dataset 추가 — validation set으로 과적합 감지 + early stopping.
    # Why: load_best_model_at_end=True이므로 eval_loss 기준 최적 체크포인트 자동 복원.
    # Changed: eval_dataset는 val_data_raw가 있을 때만 전달.
    # Why: --no-split이면 val_dataset=None이므로 eval_dataset 생략.
    trainer = LoraPlusTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        eval_dataset=val_dataset if val_data_raw else None,
    )

    # ---- 체크포인트에서 재개 ----
    resume_from = None
    if args.resume:
        # Changed: 최신 체크포인트 자동 탐색
        checkpoints = sorted(
            glob.glob(f"{CHECKPOINT_DIR}/checkpoint-*"),
            key=lambda p: int(p.split("-")[-1]) if p.split("-")[-1].isdigit() else 0,
        )
        if checkpoints:
            resume_from = checkpoints[-1]
            logger.info("Resuming from checkpoint: %s", resume_from)
        else:
            logger.warning("No checkpoints found in %s — starting from scratch", CHECKPOINT_DIR)

    # ---- 학습 시작 ----
    logger.info("Starting training...")
    t0 = time.time()
    result = trainer.train(resume_from_checkpoint=resume_from)
    elapsed = time.time() - t0

    logger.info(
        "Training complete: %.0fs (%.1f min), final loss=%.4f",
        elapsed, elapsed / 60, result.training_loss,
    )

    # ---- 어댑터 저장 ----
    os.makedirs(FINAL_DIR, exist_ok=True)
    model.save_pretrained(FINAL_DIR)
    tokenizer.save_pretrained(FINAL_DIR)
    logger.info("Adapter saved to %s", FINAL_DIR)

    # Changed: artifacts/에도 복사 (제출용)
    import shutil
    artifacts_v3 = "/workspace/team6/team6-opal-verifier/artifacts/lora_adapter_v3"
    if os.path.exists(artifacts_v3):
        shutil.rmtree(artifacts_v3)
    shutil.copytree(FINAL_DIR, artifacts_v3)
    logger.info("Also copied to %s (for submission)", artifacts_v3)

    # ---- 학습 결과 요약 ----
    print("\n" + "=" * 60)
    print("EXPERIMENT A TRAINING COMPLETE")
    print("=" * 60)
    print(f"Model: {BASE_MODEL}")
    print(f"LoRA: r={LORA_R}, alpha={LORA_ALPHA}, dropout={LORA_DROPOUT}")
    print(f"LoRA+: lr_A={LR_A}, lr_B={LR_B} (ratio {LR_B/LR_A:.0f}:1)")
    print(f"NEFTune: alpha={NEFTUNE_NOISE_ALPHA}")
    print(f"Training: {len(dataset)} examples, {NUM_EPOCHS} epochs, "
          f"batch={BATCH_SIZE}*{GRAD_ACCUM}={BATCH_SIZE*GRAD_ACCUM}")
    print(f"Max seq len: {MAX_SEQ_LEN}")
    print(f"Final loss: {result.training_loss:.4f}")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Adapter: {FINAL_DIR}")
    print("=" * 60)

    # ---- 평가 ----
    if not args.skip_eval:
        evaluate_public20(model, tokenizer, MAX_SEQ_LEN)
    else:
        logger.info("Skipping evaluation (--skip-eval)")

    # ---- 정리 ----
    del model, trainer
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("COMPLETE")


if __name__ == "__main__":
    main()
