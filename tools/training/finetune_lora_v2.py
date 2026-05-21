# Changed: LoRA fine-tune v2 with rich trajectory format and label masking.
# Why: v1 used format_trajectory_for_embedding() which strips all payload/parameter
# information (table, column, UID, args, return values). Papers show:
# - TOGLL (ASE 2024): fine-tuned small models beat large zero-shot 3.8x with proper format
# - Zhang et al. (ICLR 2024): model scaling > data scaling for fine-tuning
# - RBCTest (ASE 2024): constraint-relevant info is key for spec compliance checking
#
# Key improvements over v1:
# 1. Rich trajectory format: includes method args, table/column, UIDs, payloads
# 2. Label masking: only compute loss on the answer token, not the entire prompt
# 3. Target 4B model (scaling law: bigger model = better for finetuning)
# 4. Longer max_length (1024) to capture more trajectory context

from __future__ import annotations
import json, sys, os, time, logging, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Changed: sentinel value for masked (ignored) labels in cross-entropy loss.
IGNORE_INDEX = -100


def _compact_json(obj, max_depth=2, cur_depth=0) -> str:
    """Compact JSON representation, truncating deep nesting."""
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
    """Format trajectory with full constraint-relevant information.

    Changed: includes method args (table, column, UID), response payloads,
    and session state tracking. This gives the model enough information to
    reason about spec compliance.
    """
    if not records:
        return ""

    lines = []
    # Changed: track session state for context
    session_active = False
    authenticated = False
    current_sp = ""

    for i, step in enumerate(records):
        if not isinstance(step, dict):
            continue
        cmd = step.get("input", {})
        out = step.get("output", {})

        # Changed: handle DATA_COMMAND Read/Write steps (no "method" key, uses "command").
        # Why: tc10/tc20 pair differs only in DATA_COMMAND Read result ("Random Data" vs "8E").
        # Old code rendered these as empty "Step N:  -> " because method_obj was {}.
        data_cmd = cmd.get("command", "")
        if data_cmd and not cmd.get("method"):
            # This is a DATA_COMMAND (Read/Write), not a TCG method call
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

        # Extract method info
        method_obj = cmd.get("method", {})
        method_name = method_obj.get("name", "") if isinstance(method_obj, dict) else str(method_obj)
        method_uid = method_obj.get("uid", "") if isinstance(method_obj, dict) else ""
        method_args = method_obj.get("args", {}) if isinstance(method_obj, dict) else {}

        # Extract invoking ID
        inv_obj = cmd.get("invoking_id", {})
        inv_name = inv_obj.get("name", "") if isinstance(inv_obj, dict) else str(inv_obj)
        inv_uid = inv_obj.get("uid", "") if isinstance(inv_obj, dict) else ""

        # Extract output
        status = out.get("status_codes", out.get("status", ""))
        if isinstance(status, dict):
            status = status.get("Name", status.get("name", str(status)))
        return_values = out.get("return_values", out.get("payload", None))

        # Track session state
        method_lower = str(method_name).lower()
        status_lower = str(status).lower()
        if method_lower == "startsession" and "success" in status_lower:
            session_active = True
            # Check if SPID indicates which SP
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

        # Build step line
        is_final = (i == len(records) - 1)
        prefix = "[FINAL] " if is_final else ""

        # Changed: include both required AND optional args (esp. HostChallenge).
        # Why: tc4/tc14 pair differs only in optional HostChallenge.
        # Old code only showed required args, making pairs indistinguishable.
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

        # Compact return values
        rv_str = ""
        if return_values is not None:
            rv_str = _compact_json(return_values)
            if len(rv_str) > 150:
                rv_str = rv_str[:150] + "..."

        # Build line
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

    # Session state summary
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


def format_for_training_v2(records: list, label: str) -> dict:
    """Format a trajectory + label into chat format for SFT with rich format."""
    prompt = format_trajectory_rich(records)

    messages = [
        {"role": "system", "content": (
            "You are a TCG/Opal SSD protocol compliance verifier. "
            "Given a command-response trajectory with session state, "
            "determine if the final response is consistent with the specification. "
            "Answer exactly: pass or fail"
        )},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": label},
    ]
    return {"messages": messages}


def main() -> None:
    model_name = os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-4B")
    training_path = Path("/workspace/team6/training_data/training_cases.json")
    output_dir = Path("/workspace/team6/lora_output_v2")
    artifacts_dir = ROOT / "artifacts"
    max_length = int(os.environ.get("MAX_LENGTH", "1024"))
    num_epochs = int(os.environ.get("NUM_EPOCHS", "3"))
    lora_rank = int(os.environ.get("LORA_RANK", "16"))
    batch_size = int(os.environ.get("BATCH_SIZE", "1"))
    grad_accum = int(os.environ.get("GRAD_ACCUM", "8"))

    logger.info("=== LoRA Fine-tuning V2 ===")
    logger.info("Model: %s, max_length: %d, epochs: %d, rank: %d",
                model_name, max_length, num_epochs, lora_rank)

    logger.info("Loading training data...")
    cases = json.loads(training_path.read_text())
    logger.info("Total: %d (pass=%d, fail=%d)",
                len(cases),
                sum(1 for c in cases if c["label"] == "pass"),
                sum(1 for c in cases if c["label"] == "fail"))

    # Prepare training data with rich format
    train_data = []
    for case in cases:
        records = case["records"]
        if isinstance(records, list):
            records = [r for r in records if isinstance(r, dict)]
        if not records:
            continue
        train_data.append(format_for_training_v2(records, case["label"]))

    logger.info("Training examples prepared: %d", len(train_data))

    # Log a sample
    if train_data:
        sample = train_data[0]
        logger.info("Sample prompt (first 500 chars):\n%s",
                     sample["messages"][1]["content"][:500])

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

    # LoRA config
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_rank,
        lora_alpha=lora_rank * 2,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Changed: custom dataset with label masking.
    # Why: only compute loss on the answer token ("pass"/"fail"), not the prompt.
    # This focuses the gradient signal on the classification decision.
    from torch.utils.data import Dataset

    class ChatDatasetV2(Dataset):
        def __init__(self, data, tokenizer, max_length):
            self.examples = []
            skipped = 0
            for item in data:
                try:
                    # Encode full conversation
                    full_text = tokenizer.apply_chat_template(
                        item["messages"], tokenize=False,
                        add_generation_prompt=False, enable_thinking=False,
                    )
                except TypeError:
                    full_text = tokenizer.apply_chat_template(
                        item["messages"], tokenize=False,
                        add_generation_prompt=False,
                    )

                # Encode prompt (without assistant answer) for label masking
                prompt_messages = item["messages"][:-1]
                try:
                    prompt_text = tokenizer.apply_chat_template(
                        prompt_messages, tokenize=False,
                        add_generation_prompt=True, enable_thinking=False,
                    )
                except TypeError:
                    prompt_text = tokenizer.apply_chat_template(
                        prompt_messages, tokenize=False,
                        add_generation_prompt=True,
                    )

                full_encoded = tokenizer(
                    full_text, truncation=True, max_length=max_length,
                    padding="max_length", return_tensors="pt"
                )
                prompt_encoded = tokenizer(
                    prompt_text, truncation=True, max_length=max_length,
                    return_tensors="pt"
                )

                input_ids = full_encoded["input_ids"].squeeze()
                attention_mask = full_encoded["attention_mask"].squeeze()

                # Changed: mask prompt tokens in labels so loss is only on answer.
                labels = input_ids.clone()
                prompt_len = prompt_encoded["input_ids"].shape[1]
                if prompt_len < max_length:
                    labels[:prompt_len] = IGNORE_INDEX
                # Also mask padding
                labels[attention_mask == 0] = IGNORE_INDEX

                self.examples.append({
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "labels": labels,
                })

            logger.info("Dataset: %d examples (skipped %d)", len(self.examples), skipped)

        def __len__(self):
            return len(self.examples)

        def __getitem__(self, idx):
            return self.examples[idx]

    logger.info("Tokenizing %d examples (max_length=%d)...", len(train_data), max_length)
    dataset = ChatDatasetV2(train_data, tokenizer, max_length)

    # Training
    from transformers import Trainer

    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
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

    logger.info("Starting LoRA fine-tuning V2...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    logger.info("Training complete: %.0fs (%.1f min)", elapsed, elapsed / 60)

    # Save LoRA adapter
    adapter_path = output_dir / "adapter"
    adapter_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))
    logger.info("LoRA adapter saved to %s", adapter_path)

    # Also copy to artifacts/ for submission
    artifacts_adapter = artifacts_dir / "lora_adapter_v2"
    artifacts_adapter.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(artifacts_adapter))
    tokenizer.save_pretrained(str(artifacts_adapter))
    logger.info("Also saved to %s", artifacts_adapter)

    print(f"\n=== LORA V2 FINE-TUNING COMPLETE ===")
    print(f"Model: {model_name}")
    print(f"Training: {len(train_data)} examples, {num_epochs} epochs")
    print(f"max_length: {max_length}, LoRA rank: {lora_rank}")
    print(f"LoRA adapter: {adapter_path}")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
