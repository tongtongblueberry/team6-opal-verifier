"""Experiment B: 5개 LoRA 어댑터 앙상블 학습 및 평가.

근거: "LoRA Ensembles for Large Language Model Fine-tuning" (Wang et al., arXiv 2310.00035, Oct 2023)
  - 서로 다른 random seed로 독립적으로 학습한 여러 LoRA 어댑터
  - 추론 시 logit 평균 → 분산 감소, 과적합 방지
  - 각 어댑터 ~3-5MB → 5개 앙상블도 메모리 부담 미미

변경 사항 요약 (train_exp_a.py 대비):
  - 5개 어댑터를 순차 학습 (GPU 메모리 절약: 각 어댑터 학습 후 모델 완전 해제)
  - rank/alpha/seed 조합을 다양화 → 다양성 확보
  - 앙상블 평가: 각 어댑터의 logit을 평균내어 예측
  - --resume-from N: N번째 어댑터부터 학습 재개 (이전 것은 건너뜀)
  - --eval-only: 학습 건너뛰고 기존 어댑터로 평가만 수행
  - 앙상블 추론 함수 (EnsembleLoRASolver) 포함 — solver.py에서 사용 가능

어댑터 구성:
  | Adapter | Rank | Alpha | LR_A  | LR_B  | Seed | Epochs |
  |---------|------|-------|-------|-------|------|--------|
  | ens_1   | 2    | 4     | 5e-5  | 8e-4  | 42   | 10     |
  | ens_2   | 2    | 4     | 5e-5  | 8e-4  | 123  | 10     |
  | ens_3   | 4    | 8     | 5e-5  | 8e-4  | 42   | 10     |
  | ens_4   | 4    | 8     | 5e-5  | 8e-4  | 456  | 10     |
  | ens_5   | 8    | 16    | 5e-5  | 8e-4  | 789  | 10     |
"""
import os
import sys
import json
import math
import time
import gc
import glob as glob_mod
import logging
import argparse
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
sys.path.insert(0, "/workspace/team6/team6-opal-verifier")

# Changed: format 함수를 finetune_lora_v2에서 임포트 — 학습/추론 포맷 일관성 보장
from tools.training.finetune_lora_v2 import format_for_training_v2, format_trajectory_rich

import torch
import numpy as np
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, PeftModel, TaskType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("train_exp_b_ensemble")

# ============================================================
# 공통 하이퍼파라미터 — 모든 어댑터에 공유
# ============================================================
BASE_MODEL = "Qwen/Qwen3.5-4B"
# Changed: cache_dir는 models--* 폴더가 있는 hub/ 디렉토리를 가리켜야 함
MODEL_CACHE = "/workspace/cache/hf_cache/hub"

# 공통 학습 설정
LORA_DROPOUT = 0.1            # 모든 어댑터 동일
TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj"]
WEIGHT_DECAY = 0.0            # LoRA 자체가 regularization
NUM_EPOCHS = 10
BATCH_SIZE = 1                # Changed: OOM 방지 (모델이 ~39GB 점유)
GRAD_ACCUM = 8                # effective batch size = 1*8 = 8
MAX_SEQ_LEN = 2048
WARMUP_RATIO = 0.1
MAX_GRAD_NORM = 1.0
NEFTUNE_NOISE_ALPHA = 5.0     # NEFTune 임베딩 노이즈
LOGGING_STEPS = 10
SAVE_STRATEGY = "epoch"
SAVE_TOTAL_LIMIT = 10         # 모든 에폭 체크포인트 보존
MAX_CASES_DEFAULT = 210

# 경로
MUTATION_DATA = "/workspace/team6/training_data/mutation_cases.json"
ENSEMBLE_BASE_DIR = "/workspace/team6/adapters/ensemble"

# 평가 관련
EVAL_DATASET = "/dl2026/dataset"
EVAL_LABELS = f"{EVAL_DATASET}/label.jsonl"
EVAL_TESTCASES = f"{EVAL_DATASET}/testcases"

# lora_solver.py와 동일한 시스템 프롬프트
SYSTEM_PROMPT = (
    "You are a TCG/Opal SSD protocol compliance verifier. "
    "Given a command-response trajectory with session state, "
    "determine if the final response is consistent with the specification. "
    "Answer exactly: pass or fail"
)

IGNORE_INDEX = -100


# ============================================================
# 5개 어댑터 구성 — rank/alpha/seed 조합 다양화
# ============================================================
@dataclass
class AdapterConfig:
    """각 어댑터의 개별 하이퍼파라미터."""
    name: str
    rank: int
    alpha: int
    lr_a: float
    lr_b: float
    seed: int
    epochs: int


# Changed: 5개 어댑터 구성 — rank와 seed를 다양화하여 앙상블 다양성 확보
# rank 2: 파라미터 최소 → 강한 정규화, rank 8: 파라미터 최대 → 표현력 우선
ADAPTER_CONFIGS = [
    AdapterConfig(name="ens_1", rank=2, alpha=4,  lr_a=5e-5, lr_b=8e-4, seed=42,  epochs=10),
    AdapterConfig(name="ens_2", rank=2, alpha=4,  lr_a=5e-5, lr_b=8e-4, seed=123, epochs=10),
    AdapterConfig(name="ens_3", rank=4, alpha=8,  lr_a=5e-5, lr_b=8e-4, seed=42,  epochs=10),
    AdapterConfig(name="ens_4", rank=4, alpha=8,  lr_a=5e-5, lr_b=8e-4, seed=456, epochs=10),
    AdapterConfig(name="ens_5", rank=8, alpha=16, lr_a=5e-5, lr_b=8e-4, seed=789, epochs=10),
]


# ============================================================
# 데이터셋 클래스 — label masking으로 답변 토큰만 학습
# (train_exp_a.py의 MutationDataset와 동일)
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
# (train_exp_a.py의 LoraPlusTrainer와 동일, 단 lr을 인스턴스 변수로 받음)
# ============================================================
class LoraPlusTrainer(Trainer):
    """Changed: LoRA+ 구현 — lora_A와 lora_B에 서로 다른 학습률 적용.

    Hayou et al. (2024) 'LoRA+' 논문:
    B 매트릭스의 학습률을 A보다 크게 설정하면 수렴 속도/최종 성능 개선.
    """

    def __init__(self, lr_a: float, lr_b: float, **kwargs):
        """Changed: lr_a, lr_b를 인스턴스 변수로 받아 어댑터별 차등 lr 적용."""
        super().__init__(**kwargs)
        self._lr_a = lr_a
        self._lr_b = lr_b

    def create_optimizer(self):
        """Changed: A/B 파라미터 그룹 분리하여 차등 lr 적용."""
        if self.optimizer is not None:
            return self.optimizer

        model = self.model

        # Changed: lora_A 파라미터 (낮은 lr) / lora_B 파라미터 (높은 lr) 분리
        lora_a_params = []
        lora_b_params = []
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
                "lr": self._lr_a,
                "weight_decay": WEIGHT_DECAY,
            },
            {
                "params": lora_b_params,
                "lr": self._lr_b,
                "weight_decay": WEIGHT_DECAY,
            },
        ]

        # other_params가 있으면 추가 (일반적으로 LoRA에서는 없지만 안전장치)
        if other_params:
            optimizer_grouped_parameters.append({
                "params": other_params,
                "lr": self._lr_a,
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
# seed 고정 함수 — 어댑터별 재현성 보장
# ============================================================
def set_seed(seed: int):
    """Changed: 모든 RNG seed 고정 — 어댑터별 다른 초기화 보장."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    logger.info("Random seed set to %d", seed)


# ============================================================
# 단일 어댑터 학습 함수
# ============================================================
def train_single_adapter(
    cfg: AdapterConfig,
    train_data: List[Dict],
    tokenizer: AutoTokenizer,
) -> str:
    """하나의 LoRA 어댑터를 학습하고 저장 경로를 반환.

    Changed: 각 어댑터마다 모델을 새로 로드/해제하여 GPU 메모리 누수 방지.
    """
    adapter_dir = os.path.join(ENSEMBLE_BASE_DIR, cfg.name)
    checkpoint_dir = os.path.join(adapter_dir, "checkpoints")
    final_dir = os.path.join(adapter_dir, "final")

    logger.info("=" * 60)
    logger.info("TRAINING ADAPTER: %s (rank=%d, alpha=%d, seed=%d)",
                cfg.name, cfg.rank, cfg.alpha, cfg.seed)
    logger.info("=" * 60)

    # Changed: 어댑터별 seed 고정 — 다른 초기화로 다양성 확보
    set_seed(cfg.seed)

    # ---- Dataset 생성 (seed에 따라 셔플 순서가 달라짐) ----
    logger.info("Tokenizing %d examples (max_seq_len=%d)...", len(train_data), MAX_SEQ_LEN)
    dataset = MutationDataset(train_data, tokenizer, MAX_SEQ_LEN)

    if len(dataset) == 0:
        logger.error("Empty dataset after tokenization! Skipping %s.", cfg.name)
        return ""

    # ---- 모델 로드 ----
    logger.info("Loading model: %s", BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )

    # Changed: 어댑터별 rank/alpha 설정 — 다양한 capacity로 앙상블 다양성 확보
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg.rank,
        lora_alpha=cfg.alpha,
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
    # Changed: seed를 TrainingArguments에도 전달 → DataLoader 셔플 등에 반영
    training_args = TrainingArguments(
        output_dir=checkpoint_dir,
        num_train_epochs=cfg.epochs,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=cfg.lr_b,                     # base lr (B 매트릭스 기준)
        weight_decay=WEIGHT_DECAY,
        max_grad_norm=MAX_GRAD_NORM,
        warmup_ratio=WARMUP_RATIO,
        lr_scheduler_type="cosine",
        optim="adamw_torch",                        # LoraPlusTrainer가 override
        neftune_noise_alpha=NEFTUNE_NOISE_ALPHA,    # NEFTune 임베딩 노이즈
        logging_steps=LOGGING_STEPS,
        save_strategy=SAVE_STRATEGY,
        save_total_limit=SAVE_TOTAL_LIMIT,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_pin_memory=True,
        seed=cfg.seed,                              # Changed: 어댑터별 seed
        data_seed=cfg.seed,                         # Changed: 데이터 셔플 seed
    )

    # Changed: LoraPlusTrainer에 어댑터별 lr_a/lr_b 전달
    trainer = LoraPlusTrainer(
        lr_a=cfg.lr_a,
        lr_b=cfg.lr_b,
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    # ---- 학습 시작 ----
    logger.info("Starting training for %s...", cfg.name)
    t0 = time.time()
    result = trainer.train()
    elapsed = time.time() - t0

    logger.info(
        "[%s] Training complete: %.0fs (%.1f min), final loss=%.4f",
        cfg.name, elapsed, elapsed / 60, result.training_loss,
    )

    # ---- 어댑터 저장 ----
    os.makedirs(final_dir, exist_ok=True)
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    logger.info("[%s] Adapter saved to %s", cfg.name, final_dir)

    # ---- GPU 메모리 완전 해제 ----
    # Changed: 다음 어댑터를 위해 모델/trainer/dataset 완전 삭제
    del trainer, model, dataset
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    logger.info("[%s] GPU memory released", cfg.name)

    return final_dir


# ============================================================
# 단일 어댑터 평가 함수 — logit과 p_fail 반환
# ============================================================
def get_logits_single_adapter(
    adapter_path: str,
    tokenizer: AutoTokenizer,
    tc_inputs: List[Dict],
    pass_id: int,
    fail_id: int,
) -> List[Dict]:
    """하나의 어댑터로 모든 테스트케이스의 logit을 계산.

    Changed: logit을 반환하여 앙상블 평균에 사용.

    Returns:
        List of {"fname": str, "pass_logit": float, "fail_logit": float, "p_fail": float}
    """
    logger.info("Loading adapter from %s for evaluation...", adapter_path)

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()

    results = []
    for tc in tc_inputs:
        fname = tc["fname"]
        inputs = tc["inputs"]
        inputs_gpu = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = model(**inputs_gpu).logits[0, -1, :]

        p_l = logits[pass_id].item()
        f_l = logits[fail_id].item()

        # softmax로 P(fail) 계산 (수치 안정성)
        mx = max(p_l, f_l)
        p_fail = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))

        results.append({
            "fname": fname,
            "pass_logit": p_l,
            "fail_logit": f_l,
            "p_fail": p_fail,
        })

    # Changed: 평가 후 모델 해제 — 다음 어댑터를 위해
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    return results


# ============================================================
# 앙상블 평가 함수 — 5개 어댑터의 logit 평균
# ============================================================
def evaluate_ensemble(
    adapter_paths: List[str],
    adapter_names: List[str],
    threshold: float = 0.5,
):
    """모든 어댑터를 순차 로드하여 logit 수집 후, 앙상블 평균으로 평가.

    Changed: 메모리 절약을 위해 한 번에 하나의 어댑터만 로드.
    각 어댑터의 raw logit을 수집한 뒤, softmax 전에 평균하여 최종 예측.
    """
    logger.info("=== ENSEMBLE EVALUATION (threshold=%.2f) ===", threshold)

    # label 로드
    if not os.path.exists(EVAL_LABELS):
        logger.warning("Label file not found: %s — skipping evaluation", EVAL_LABELS)
        return None

    pub_labels = {}
    for line in open(EVAL_LABELS):
        d = json.loads(line)
        pub_labels[d["filename"]] = d["label"]

    # Changed: solver를 임포트하여 _records() 사용 — lora_solver.py와 동일한 전처리
    from src.solver import StatefulOpalVerifier
    verifier = StatefulOpalVerifier()

    # tokenizer 로드 (아무 어댑터에서나 — 동일한 base model이므로)
    tokenizer = AutoTokenizer.from_pretrained(
        adapter_paths[0] if adapter_paths else BASE_MODEL,
        trust_remote_code=True,
        cache_dir=MODEL_CACHE,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    # ---- 테스트케이스 전처리 (한 번만) ----
    tc_files = sorted(glob_mod.glob(f"{EVAL_TESTCASES}/tc*.json"))
    if not tc_files:
        logger.warning("No test cases found in %s — skipping evaluation", EVAL_TESTCASES)
        return None

    tc_inputs = []
    tc_golds = {}
    for f in tc_files:
        fname = os.path.basename(f)
        gold = pub_labels.get(fname, "?")
        if gold == "?":
            continue

        steps = json.load(open(f))
        records = verifier._records(steps)
        if not records:
            continue

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
            max_length=MAX_SEQ_LEN,
        )

        tc_inputs.append({
            "fname": fname,
            "inputs": inputs,
        })
        tc_golds[fname] = gold

    logger.info("Prepared %d test cases for evaluation", len(tc_inputs))

    if not tc_inputs:
        logger.warning("No valid test cases found for evaluation")
        return None

    # ---- 각 어댑터별 logit 수집 ----
    # all_results[adapter_idx] = [{"fname", "pass_logit", "fail_logit", "p_fail"}, ...]
    all_results = []
    for idx, (apath, aname) in enumerate(zip(adapter_paths, adapter_names)):
        logger.info("--- Evaluating adapter %d/%d: %s ---", idx + 1, len(adapter_paths), aname)
        results = get_logits_single_adapter(apath, tokenizer, tc_inputs, pass_id, fail_id)
        all_results.append(results)

    # ---- 개별 어댑터 결과 출력 ----
    print("\n" + "=" * 70)
    print("PER-ADAPTER RESULTS")
    print("=" * 70)

    per_adapter_scores = []
    for idx, (aname, results) in enumerate(zip(adapter_names, all_results)):
        correct = 0
        total = len(results)
        for r in results:
            gold = tc_golds[r["fname"]]
            pred = "fail" if r["p_fail"] > threshold else "pass"
            if pred == gold:
                correct += 1
        acc = correct / total * 100 if total > 0 else 0
        per_adapter_scores.append(correct)
        print(f"  {aname}: {correct}/{total} ({acc:.1f}%)")

    # ---- 앙상블 결과 계산 ----
    # Changed: 각 테스트케이스에 대해 raw logit을 평균한 뒤 softmax
    print("\n" + "=" * 70)
    print("ENSEMBLE RESULT (logit averaging)")
    print("=" * 70)

    ensemble_correct = 0
    ensemble_total = len(tc_inputs)
    ensemble_details = []

    for tc_idx in range(len(tc_inputs)):
        fname = tc_inputs[tc_idx]["fname"]
        gold = tc_golds[fname]

        # Changed: 모든 어댑터의 pass/fail logit을 수집하여 평균
        pass_logits = []
        fail_logits = []
        p_fails_individual = []
        for adapter_results in all_results:
            r = adapter_results[tc_idx]
            pass_logits.append(r["pass_logit"])
            fail_logits.append(r["fail_logit"])
            p_fails_individual.append(r["p_fail"])

        # 방법 1: logit 평균 후 softmax (논문 권장)
        avg_pass_logit = sum(pass_logits) / len(pass_logits)
        avg_fail_logit = sum(fail_logits) / len(fail_logits)
        mx = max(avg_pass_logit, avg_fail_logit)
        p_fail_logit_avg = math.exp(avg_fail_logit - mx) / (
            math.exp(avg_pass_logit - mx) + math.exp(avg_fail_logit - mx)
        )

        # 방법 2: probability 평균 (참고용)
        p_fail_prob_avg = sum(p_fails_individual) / len(p_fails_individual)

        # 최종 예측: logit 평균 방식 사용
        pred = "fail" if p_fail_logit_avg > threshold else "pass"
        ok = pred == gold
        if ok:
            ensemble_correct += 1

        mark = "OK" if ok else "XX"
        logger.info(
            "  %s: gold=%-4s pred=%-4s p_fail_logit=%.4f p_fail_prob=%.4f %s  [%s]",
            fname, gold, pred, p_fail_logit_avg, p_fail_prob_avg, mark,
            " ".join(f"{p:.3f}" for p in p_fails_individual),
        )

        ensemble_details.append({
            "fname": fname,
            "gold": gold,
            "pred": pred,
            "p_fail_logit_avg": round(p_fail_logit_avg, 4),
            "p_fail_prob_avg": round(p_fail_prob_avg, 4),
            "p_fails_individual": [round(p, 4) for p in p_fails_individual],
            "correct": ok,
        })

    if ensemble_total > 0:
        ens_acc = ensemble_correct / ensemble_total * 100
        print(f"\n  ENSEMBLE: {ensemble_correct}/{ensemble_total} ({ens_acc:.1f}%)")
        print(f"  Best single adapter: {max(per_adapter_scores)}/{ensemble_total}")
        print(f"  Worst single adapter: {min(per_adapter_scores)}/{ensemble_total}")
    else:
        logger.warning("No valid test cases found for evaluation")

    # ---- 결과 저장 ----
    result_path = os.path.join(ENSEMBLE_BASE_DIR, "ensemble_eval_results.json")
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    json.dump({
        "threshold": threshold,
        "n_adapters": len(adapter_paths),
        "adapter_names": adapter_names,
        "per_adapter_accuracy": [
            s / ensemble_total * 100 if ensemble_total > 0 else 0
            for s in per_adapter_scores
        ],
        "ensemble_accuracy": ens_acc if ensemble_total > 0 else 0,
        "details": ensemble_details,
    }, open(result_path, "w"), indent=2)
    logger.info("Ensemble eval results saved to %s", result_path)

    return ensemble_details


# ============================================================
# EnsembleLoRASolver — solver.py에서 사용할 수 있는 앙상블 추론 클래스
# ============================================================
class EnsembleLoRASolver:
    """5개 LoRA 어댑터의 logit 평균으로 예측하는 앙상블 solver.

    Changed: solver.py에서 LoRASolver 대신 사용 가능.
    사용법:
        from tools.training.train_exp_b_ensemble import EnsembleLoRASolver
        solver = EnsembleLoRASolver()  # 기본 경로에서 어댑터 로드
        p_fail = solver.predict_prob(records)
    """

    def __init__(
        self,
        adapter_dir: Optional[str] = None,
        base_model: Optional[str] = None,
        adapter_names: Optional[List[str]] = None,
    ):
        """Changed: 앙상블 어댑터 순차 로드.

        Args:
            adapter_dir: 어댑터 루트 디렉토리 (기본: /workspace/team6/adapters/ensemble)
            base_model: base 모델 경로 (기본: Qwen/Qwen3.5-4B)
            adapter_names: 로드할 어댑터 이름 리스트 (기본: ens_1~ens_5)
        """
        self.models = []
        self.tokenizer = None
        self.available = False
        self._pass_id = None
        self._fail_id = None

        if adapter_dir is None:
            adapter_dir = ENSEMBLE_BASE_DIR
        if base_model is None:
            base_model = os.environ.get("RAG_MODEL", BASE_MODEL)
        if adapter_names is None:
            adapter_names = [cfg.name for cfg in ADAPTER_CONFIGS]

        self.adapter_names = adapter_names

        try:
            self._load_all(adapter_dir, base_model, adapter_names)
        except Exception as e:
            logger.warning("Failed to load ensemble models: %s", e)

    def _load_all(self, adapter_dir: str, base_model: str, adapter_names: List[str]) -> None:
        """Changed: 모든 어댑터를 각각 별도의 PeftModel로 로드.

        주의: 5개 모델을 동시에 메모리에 올림 → GPU 메모리 ~10GB (어댑터만 다름, base 공유 불가).
        메모리 부족 시 predict_prob_sequential() 사용 (순차 로드/해제).
        """
        import torch as _torch
        from transformers import AutoModelForCausalLM as _AutoModel, AutoTokenizer as _AutoTok
        from peft import PeftModel as _PeftModel

        t0 = time.time()

        # Changed: 먼저 유효한 어댑터만 필터링
        valid_paths = []
        valid_names = []
        for name in adapter_names:
            path = os.path.join(adapter_dir, name, "final")
            config_path = os.path.join(path, "adapter_config.json")
            if os.path.exists(config_path):
                valid_paths.append(path)
                valid_names.append(name)
            else:
                logger.warning("Adapter not found: %s — skipping", path)

        if not valid_paths:
            logger.error("No valid adapters found in %s", adapter_dir)
            return

        # tokenizer 로드 (첫 번째 어댑터에서)
        self.tokenizer = _AutoTok.from_pretrained(
            valid_paths[0], trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self._pass_id = self.tokenizer.encode("pass", add_special_tokens=False)[0]
        self._fail_id = self.tokenizer.encode("fail", add_special_tokens=False)[0]

        # Changed: 각 어댑터를 별도 모델로 로드
        for name, path in zip(valid_names, valid_paths):
            logger.info("Loading ensemble member: %s from %s", name, path)
            base = _AutoModel.from_pretrained(
                base_model,
                torch_dtype=_torch.float16,
                device_map="auto",
                trust_remote_code=True,
            )
            model = _PeftModel.from_pretrained(base, path)
            model.eval()
            self.models.append(model)

        self.adapter_names = valid_names
        self.available = len(self.models) > 0

        logger.info(
            "Ensemble loaded: %d adapters in %.1fs",
            len(self.models), time.time() - t0,
        )

    def predict_prob(self, records: list, threshold: float = 0.5) -> float:
        """Changed: 앙상블 logit 평균으로 P(fail) 반환.

        모든 어댑터의 pass/fail logit을 수집하여 평균 후 softmax.
        """
        if not self.available or not records:
            return 0.5

        import torch as _torch

        # Changed: lora_solver.py와 동일한 형식으로 프롬프트 생성
        prompt = format_trajectory_rich(records)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )

        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=MAX_SEQ_LEN,
        )

        pass_logits = []
        fail_logits = []

        for model in self.models:
            inputs_gpu = {k: v.to(model.device) for k, v in inputs.items()}
            with _torch.no_grad():
                logits = model(**inputs_gpu).logits[0, -1, :]
            pass_logits.append(logits[self._pass_id].item())
            fail_logits.append(logits[self._fail_id].item())

        # Changed: logit 평균 후 softmax (Wang et al., 2023 권장)
        avg_pass = sum(pass_logits) / len(pass_logits)
        avg_fail = sum(fail_logits) / len(fail_logits)
        mx = max(avg_pass, avg_fail)
        p_fail = math.exp(avg_fail - mx) / (math.exp(avg_pass - mx) + math.exp(avg_fail - mx))
        return p_fail

    def predict(self, records: list, threshold: float = 0.5) -> str:
        """Changed: 앙상블 예측 — pass/fail 이진 분류."""
        p_fail = self.predict_prob(records, threshold)
        return "fail" if p_fail > threshold else "pass"


# ============================================================
# 순차 로드 방식 앙상블 추론 (메모리 절약용)
# ============================================================
def ensemble_predict_sequential(
    records: list,
    adapter_dir: Optional[str] = None,
    adapter_names: Optional[List[str]] = None,
    base_model: Optional[str] = None,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Changed: 메모리 절약 버전 — 어댑터를 하나씩 로드/해제하며 logit 수집.

    5개 모델을 동시에 올릴 수 없는 환경 (GPU < 48GB)에서 사용.
    속도는 느리지만 메모리 사용량은 단일 모델과 동일.

    Returns:
        {"p_fail": float, "prediction": str, "individual_p_fails": List[float]}
    """
    if adapter_dir is None:
        adapter_dir = ENSEMBLE_BASE_DIR
    if base_model is None:
        base_model = os.environ.get("RAG_MODEL", BASE_MODEL)
    if adapter_names is None:
        adapter_names = [cfg.name for cfg in ADAPTER_CONFIGS]

    if not records:
        return {"p_fail": 0.5, "prediction": "pass", "individual_p_fails": []}

    # tokenizer 로드
    first_adapter = os.path.join(adapter_dir, adapter_names[0], "final")
    tokenizer = AutoTokenizer.from_pretrained(first_adapter, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    pass_id = tokenizer.encode("pass", add_special_tokens=False)[0]
    fail_id = tokenizer.encode("fail", add_special_tokens=False)[0]

    # 프롬프트 준비
    prompt = format_trajectory_rich(records)
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

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_SEQ_LEN)

    pass_logits = []
    fail_logits = []
    p_fails = []

    # Changed: 어댑터를 하나씩 로드/해제
    for name in adapter_names:
        adapter_path = os.path.join(adapter_dir, name, "final")
        if not os.path.exists(os.path.join(adapter_path, "adapter_config.json")):
            logger.warning("Adapter not found: %s — skipping", adapter_path)
            continue

        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
            cache_dir=MODEL_CACHE,
        )
        model = PeftModel.from_pretrained(model, adapter_path)
        model.eval()

        inputs_gpu = {k: v.to(model.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs_gpu).logits[0, -1, :]

        p_l = logits[pass_id].item()
        f_l = logits[fail_id].item()
        pass_logits.append(p_l)
        fail_logits.append(f_l)

        mx = max(p_l, f_l)
        p_fail_i = math.exp(f_l - mx) / (math.exp(p_l - mx) + math.exp(f_l - mx))
        p_fails.append(p_fail_i)

        # 해제
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if not pass_logits:
        return {"p_fail": 0.5, "prediction": "pass", "individual_p_fails": []}

    # Changed: logit 평균 후 softmax
    avg_pass = sum(pass_logits) / len(pass_logits)
    avg_fail = sum(fail_logits) / len(fail_logits)
    mx = max(avg_pass, avg_fail)
    p_fail_ensemble = math.exp(avg_fail - mx) / (math.exp(avg_pass - mx) + math.exp(avg_fail - mx))

    pred = "fail" if p_fail_ensemble > threshold else "pass"

    return {
        "p_fail": p_fail_ensemble,
        "prediction": pred,
        "individual_p_fails": p_fails,
    }


# ============================================================
# 메인 함수 — 5개 어댑터 순차 학습 + 앙상블 평가
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Experiment B: 5개 LoRA 어댑터 앙상블 학습 및 평가"
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=MAX_CASES_DEFAULT,
        help=f"최대 학습 데이터 수 (기본값: {MAX_CASES_DEFAULT})",
    )
    parser.add_argument(
        "--resume-from",
        type=int,
        default=1,
        help="N번째 어댑터부터 학습 시작 (1-5). 이전 어댑터는 건너뜀 (기본값: 1)",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="학습 건너뛰고 기존 어댑터로 평가만 수행",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="학습 후 평가 건너뛰기",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="fail 판정 임계값 (기본값: 0.5)",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Experiment B: 5-Adapter LoRA Ensemble")
    logger.info("=" * 70)
    logger.info("Adapter configs:")
    for cfg in ADAPTER_CONFIGS:
        logger.info(
            "  %s: rank=%d, alpha=%d, lr_A=%.0e, lr_B=%.0e, seed=%d, epochs=%d",
            cfg.name, cfg.rank, cfg.alpha, cfg.lr_a, cfg.lr_b, cfg.seed, cfg.epochs,
        )
    logger.info("Common: dropout=%.2f, neftune=%.1f, bs=%d*%d=%d, max_seq=%d",
                LORA_DROPOUT, NEFTUNE_NOISE_ALPHA, BATCH_SIZE, GRAD_ACCUM,
                BATCH_SIZE * GRAD_ACCUM, MAX_SEQ_LEN)
    logger.info("resume_from=%d, eval_only=%s, threshold=%.2f",
                args.resume_from, args.eval_only, args.threshold)

    # ---- 학습 단계 ----
    if not args.eval_only:
        # ---- 데이터 로드 ----
        logger.info("Loading mutation data from %s...", MUTATION_DATA)
        data = json.load(open(MUTATION_DATA))
        logger.info("Loaded %d total cases", len(data))

        # Changed: --max-cases로 데이터 수 제한
        if args.max_cases and args.max_cases < len(data):
            data = data[: args.max_cases]
            logger.info("Truncated to %d cases (--max-cases=%d)", len(data), args.max_cases)

        # 라벨 분포 확인
        n_pass = sum(1 for c in data if c.get("label") == "pass")
        n_fail = sum(1 for c in data if c.get("label") == "fail")
        logger.info("Label distribution: pass=%d, fail=%d (total=%d)", n_pass, n_fail, len(data))

        # Changed: format_for_training_v2 사용 — lora_solver.py와 동일한 형식
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

        # ---- Tokenizer 로드 (데이터셋 생성용) ----
        logger.info("Loading tokenizer: %s", BASE_MODEL)
        tokenizer = AutoTokenizer.from_pretrained(
            BASE_MODEL,
            trust_remote_code=True,
            cache_dir=MODEL_CACHE,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # ---- 5개 어댑터 순차 학습 ----
        trained_adapters = []
        total_t0 = time.time()

        for idx, cfg in enumerate(ADAPTER_CONFIGS):
            adapter_num = idx + 1  # 1-based

            # Changed: --resume-from N으로 이전 어댑터 건너뛰기
            if adapter_num < args.resume_from:
                final_dir = os.path.join(ENSEMBLE_BASE_DIR, cfg.name, "final")
                if os.path.exists(os.path.join(final_dir, "adapter_config.json")):
                    logger.info(
                        "Skipping adapter %d/%d (%s) — already trained (--resume-from=%d)",
                        adapter_num, len(ADAPTER_CONFIGS), cfg.name, args.resume_from,
                    )
                    trained_adapters.append(final_dir)
                else:
                    logger.warning(
                        "Adapter %d (%s) not found at %s but --resume-from=%d — skipping anyway",
                        adapter_num, cfg.name, final_dir, args.resume_from,
                    )
                continue

            logger.info(
                "\n>>> ADAPTER %d/%d: %s <<<",
                adapter_num, len(ADAPTER_CONFIGS), cfg.name,
            )

            final_dir = train_single_adapter(cfg, train_data, tokenizer)
            if final_dir:
                trained_adapters.append(final_dir)
            else:
                logger.error("Failed to train adapter %s!", cfg.name)

        total_elapsed = time.time() - total_t0
        logger.info(
            "ALL TRAINING COMPLETE: %d adapters in %.0fs (%.1f min)",
            len(trained_adapters), total_elapsed, total_elapsed / 60,
        )
    else:
        logger.info("--eval-only: skipping training")

    # ---- 평가 단계 ----
    if not args.skip_eval:
        # Changed: 기존에 저장된 어댑터 경로 수집
        adapter_paths = []
        adapter_names = []
        for cfg in ADAPTER_CONFIGS:
            final_dir = os.path.join(ENSEMBLE_BASE_DIR, cfg.name, "final")
            if os.path.exists(os.path.join(final_dir, "adapter_config.json")):
                adapter_paths.append(final_dir)
                adapter_names.append(cfg.name)
            else:
                logger.warning("Adapter %s not found at %s — excluding from evaluation", cfg.name, final_dir)

        if not adapter_paths:
            logger.error("No trained adapters found for evaluation!")
            return

        logger.info("Found %d adapters for evaluation: %s", len(adapter_paths), adapter_names)

        evaluate_ensemble(adapter_paths, adapter_names, threshold=args.threshold)
    else:
        logger.info("Skipping evaluation (--skip-eval)")

    # ---- 최종 요약 ----
    print("\n" + "=" * 70)
    print("EXPERIMENT B COMPLETE")
    print("=" * 70)
    print(f"Model: {BASE_MODEL}")
    print(f"Adapters: {len(ADAPTER_CONFIGS)}")
    for cfg in ADAPTER_CONFIGS:
        final_dir = os.path.join(ENSEMBLE_BASE_DIR, cfg.name, "final")
        exists = os.path.exists(os.path.join(final_dir, "adapter_config.json"))
        status = "TRAINED" if exists else "MISSING"
        print(f"  {cfg.name}: rank={cfg.rank}, alpha={cfg.alpha}, seed={cfg.seed} [{status}]")
    print(f"Base dir: {ENSEMBLE_BASE_DIR}")
    print("=" * 70)

    # 정리
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("COMPLETE")


if __name__ == "__main__":
    main()
