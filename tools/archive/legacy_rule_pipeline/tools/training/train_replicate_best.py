"""mutation_4b 정확 재현 스크립트.

17/20 달성한 mutation_4b 어댑터의 설정을 그대로 재현하되,
현재 format_trajectory_rich (학습/추론 포맷 일관성 보장)를 사용.

mutation_4b 원본 설정:
  - r=16, alpha=32, dropout=0.1
  - target_modules: q_proj, k_proj, v_proj, o_proj
  - lr=1e-3 (단일 LR, 표준 AdamW, LoRA+ 아님)
  - 5 epochs
  - batch_size=2, grad_accum=4 (effective=8)  →  OOM 방지를 위해 bs=1, accum=8로 조정
  - warmup=5%, cosine schedule
  - NO NEFTune, NO weight decay
  - 210 mutation cases
  - max_seq_len=2048
  - Final train loss: 0.3389

train_exp_a.py 대비 변경:
  - LoRA+ 차등 학습률 제거 → 표준 AdamW 단일 lr=1e-3
  - NEFTune 제거 (neftune_noise_alpha 미사용)
  - LoraPlusTrainer 제거 → 표준 HuggingFace Trainer
  - r=16, alpha=32 (기존 r=4, alpha=8에서 복원)
  - 5 epochs (기존 10에서 변경)
  - warmup=5% (기존 10%에서 변경)
  - save_total_limit=5 (기존 10에서 변경)
  - 출력 경로: /workspace/team6/adapters/replicate_best

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
logger = logging.getLogger("train_replicate_best")

# ============================================================
# 하이퍼파라미터 설정 — mutation_4b 정확 재현
# ============================================================
BASE_MODEL = "Qwen/Qwen3.5-4B"
MODEL_CACHE = "/workspace/cache/hf_cache/hub"

# LoRA: mutation_4b와 동일
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.1
TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj"]

# 학습률: 단일 lr=1e-3 (LoRA+ 아님, 표준 AdamW)
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 0.0

# 학습: mutation_4b와 동일
NUM_EPOCHS = 5
BATCH_SIZE = 1      # OOM 방지 (서버에서 bs=2도 OOM 가능)
GRAD_ACCUM = 8      # effective batch = 8
MAX_SEQ_LEN = 2048
WARMUP_RATIO = 0.05  # 5% (mutation_4b와 동일)
MAX_GRAD_NORM = 1.0

# NEFTune: 없음 (mutation_4b와 동일)
NEFTUNE_NOISE_ALPHA = 0.0  # 비활성화 — TrainingArguments에 전달하지 않음

LOGGING_STEPS = 10
SAVE_STRATEGY = "epoch"
SAVE_TOTAL_LIMIT = 5
MAX_CASES_DEFAULT = 210

# 경로
MUTATION_DATA = "/workspace/team6/training_data/mutation_cases.json"
ADAPTER_OUT = "/workspace/team6/adapters/replicate_best"
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
    """label masking 포함 — 프롬프트 토큰은 loss에서 제외, 답변("pass"/"fail")만 학습."""

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

            # 프롬프트 영역을 IGNORE_INDEX로 마스킹 — 답변 토큰만 학습
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
# 평가 함수 — public 20 테스트케이스에 대해 pass/fail 예측
# ============================================================
def evaluate_public20(model, tokenizer, max_seq_len):
    """학습 후 자동 평가 — logit 비교 방식 (lora_solver.py와 동일)."""
    logger.info("=== PUBLIC 20 EVALUATION ===")

    # label 로드
    if not os.path.exists(EVAL_LABELS):
        logger.warning("Label file not found: %s — skipping evaluation", EVAL_LABELS)
        return

    pub_labels = {}
    for line in open(EVAL_LABELS):
        d = json.loads(line)
        pub_labels[d["filename"]] = d["label"]

    # solver를 임포트하여 _records() 사용 — lora_solver.py와 동일한 전처리
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

        # lora_solver.py와 동일한 형식으로 프롬프트 생성
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

        # logit 비교로 예측 — generation 모드가 아닌 logit 방식
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
    parser = argparse.ArgumentParser(
        description="mutation_4b 정확 재현: r=16 LoRA, lr=1e-3, 5 epochs, 표준 Trainer"
    )
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
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("mutation_4b 재현: r=%d, alpha=%d, lr=%.0e, %d epochs",
                LORA_R, LORA_ALPHA, LEARNING_RATE, NUM_EPOCHS)
    logger.info("표준 AdamW (LoRA+ 아님), NEFTune 없음, weight_decay=%.1f",
                WEIGHT_DECAY)
    logger.info("=" * 60)
    logger.info("Config: epochs=%d, batch=%d, grad_accum=%d, eff_batch=%d",
                NUM_EPOCHS, BATCH_SIZE, GRAD_ACCUM, BATCH_SIZE * GRAD_ACCUM)
    logger.info("Config: max_seq_len=%d, dropout=%.2f, wd=%.4f",
                MAX_SEQ_LEN, LORA_DROPOUT, WEIGHT_DECAY)
    logger.info("Config: warmup_ratio=%.2f, max_grad_norm=%.1f",
                WARMUP_RATIO, MAX_GRAD_NORM)
    logger.info("Config: max_cases=%d, resume=%s", args.max_cases, args.resume)

    # ---- 데이터 로드 ----
    logger.info("Loading mutation data from %s...", MUTATION_DATA)
    data = json.load(open(MUTATION_DATA))
    logger.info("Loaded %d total cases", len(data))

    # --max-cases로 데이터 수 제한 (기본 210)
    if args.max_cases and args.max_cases < len(data):
        data = data[: args.max_cases]
        logger.info("Truncated to %d cases (--max-cases=%d)", len(data), args.max_cases)

    # 라벨 분포 확인
    n_pass = sum(1 for c in data if c.get("label") == "pass")
    n_fail = sum(1 for c in data if c.get("label") == "fail")
    logger.info("Label distribution: pass=%d, fail=%d (total=%d)", n_pass, n_fail, len(data))

    # format_for_training_v2 사용 — lora_solver.py의 format_trajectory_rich와 동일한 형식
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

    # ---- Dataset 생성 ----
    logger.info("Tokenizing %d examples (max_seq_len=%d)...", len(train_data), MAX_SEQ_LEN)
    dataset = MutationDataset(train_data, tokenizer, MAX_SEQ_LEN)

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

    # Changed: r=16, alpha=32 — mutation_4b와 동일
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
    # Changed: 표준 Trainer 사용 — NEFTune 없음, 단일 lr=1e-3
    training_args = TrainingArguments(
        output_dir=CHECKPOINT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,           # Changed: 단일 lr=1e-3 (LoRA+ 아님)
        weight_decay=WEIGHT_DECAY,             # 0.0 (mutation_4b와 동일)
        max_grad_norm=MAX_GRAD_NORM,
        warmup_ratio=WARMUP_RATIO,             # Changed: 5% warmup (mutation_4b와 동일)
        lr_scheduler_type="cosine",            # cosine schedule
        optim="adamw_torch",                   # 표준 AdamW
        # Changed: neftune_noise_alpha 전달하지 않음 — NEFTune 비활성화
        logging_steps=LOGGING_STEPS,
        save_strategy=SAVE_STRATEGY,
        save_total_limit=SAVE_TOTAL_LIMIT,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_pin_memory=True,
    )

    # Changed: 표준 HuggingFace Trainer — LoraPlusTrainer 제거
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    # ---- 체크포인트에서 재개 ----
    resume_from = None
    if args.resume:
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
    print("REPLICATE BEST (mutation_4b) TRAINING COMPLETE")
    print("=" * 60)
    print(f"Model: {BASE_MODEL}")
    print(f"LoRA: r={LORA_R}, alpha={LORA_ALPHA}, dropout={LORA_DROPOUT}")
    print(f"LR: {LEARNING_RATE} (표준 AdamW, LoRA+ 아님)")
    print(f"NEFTune: 없음 (mutation_4b와 동일)")
    print(f"Training: {len(dataset)} examples, {NUM_EPOCHS} epochs, "
          f"batch={BATCH_SIZE}*{GRAD_ACCUM}={BATCH_SIZE*GRAD_ACCUM}")
    print(f"Max seq len: {MAX_SEQ_LEN}")
    print(f"Warmup: {WARMUP_RATIO*100:.0f}%")
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
