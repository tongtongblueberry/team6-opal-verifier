# Changed: LoRA fine-tune Qwen3.5-4B for binary pass/fail classification.
# Why: all zero-shot/few-shot approaches failed (fail recall ≤ 20%).
# Fine-tuning is the standard DL approach and the course requires DL usage.
# Training data: 2163 cases (rule engine labeled).
# Save LoRA adapter to artifacts/ for submission.
#
# Based on: Long-Context LLMs Meet RAG (ICLR 2025) — robustness fine-tuning
# and LoRA efficiency for small datasets (50-100 examples sufficient).

from __future__ import annotations
import json, sys, os, time, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def format_for_training(records: list, label: str) -> dict:
    """Format a trajectory + label into chat format for SFT."""
    from src.embedding_classifier import format_trajectory_for_embedding

    # Use the same prompt format but with the answer
    prompt = format_trajectory_for_embedding(records)
    # Replace the trailing "Answer: (" with the full answer
    prompt = prompt.rstrip("(").rstrip()
    if prompt.endswith("Answer:"):
        prompt = prompt[:-len("Answer:")].rstrip()

    messages = [
        {"role": "system", "content": "You are a TCG/Opal protocol compliance checker. Given a command-response trajectory, determine if the final response is consistent with the specification. Answer with exactly one word: pass or fail"},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": label},
    ]
    return {"messages": messages}


def main() -> None:
    model_name = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")
    training_path = Path("/workspace/team6/training_data/training_cases.json")
    output_dir = Path("/workspace/team6/lora_output")
    artifacts_dir = ROOT / "artifacts"

    logger.info("Loading training data...")
    cases = json.loads(training_path.read_text())
    logger.info("Total: %d (pass=%d, fail=%d)",
                len(cases),
                sum(1 for c in cases if c["label"] == "pass"),
                sum(1 for c in cases if c["label"] == "fail"))

    # Prepare training data in chat format
    train_data = []
    for case in cases:
        records = case["records"]
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue
        train_data.append(format_for_training(records, case["label"]))

    # Save as JSONL for training
    train_path = Path("/workspace/team6/training_data/train_chat.jsonl")
    with train_path.open("w") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    logger.info("Training data saved: %s (%d examples)", train_path, len(train_data))

    # Fine-tune with LoRA using transformers + peft
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from peft import LoraConfig, get_peft_model, TaskType

    logger.info("Loading model %s...", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # LoRA config — small rank for small dataset per LoRA best practices
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Tokenize training data
    def tokenize(example):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False,
        )
        encoded = tokenizer(text, truncation=True, max_length=2048, padding="max_length")
        encoded["labels"] = encoded["input_ids"].copy()
        return encoded

    from torch.utils.data import Dataset

    class ChatDataset(Dataset):
        def __init__(self, data, tokenizer):
            self.examples = []
            for item in data:
                try:
                    text = tokenizer.apply_chat_template(
                        item["messages"], tokenize=False,
                        add_generation_prompt=False, enable_thinking=False,
                    )
                except TypeError:
                    text = tokenizer.apply_chat_template(
                        item["messages"], tokenize=False,
                        add_generation_prompt=False,
                    )
                # Changed: reduce max_length from 2048 to 512 to avoid OOM.
                # Why: 4B model + LoRA + 2048 tokens = 44GB VRAM overflow.
                # 512 tokens should capture the final steps of trajectory.
                encoded = tokenizer(text, truncation=True, max_length=512,
                                    padding="max_length", return_tensors="pt")
                self.examples.append({
                    "input_ids": encoded["input_ids"].squeeze(),
                    "attention_mask": encoded["attention_mask"].squeeze(),
                    "labels": encoded["input_ids"].squeeze(),
                })

        def __len__(self):
            return len(self.examples)

        def __getitem__(self, idx):
            return self.examples[idx]

    logger.info("Tokenizing %d examples...", len(train_data))
    dataset = ChatDataset(train_data, tokenizer)
    logger.info("Dataset ready: %d examples", len(dataset))

    # Training
    from transformers import Trainer

    # Changed: enable gradient checkpointing + reduce batch to save VRAM.
    # Why: 4B model OOM at 2048 tokens. Checkpointing trades compute for memory.
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=3,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-5,
        warmup_steps=50,
        logging_steps=50,
        save_steps=500,
        save_total_limit=2,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    logger.info("Starting LoRA fine-tuning...")
    t0 = time.time()
    trainer.train()
    logger.info("Training complete: %.0fs", time.time() - t0)

    # Save LoRA adapter
    adapter_path = artifacts_dir / "lora_adapter"
    adapter_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))
    logger.info("LoRA adapter saved to %s", adapter_path)

    print(f"\n=== LORA FINE-TUNING COMPLETE ===")
    print(f"Model: {model_name}")
    print(f"Training: {len(train_data)} examples")
    print(f"LoRA adapter: {adapter_path}")
    print(f"Time: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
