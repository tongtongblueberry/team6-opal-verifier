#!/usr/bin/env python3
"""Thin TRL SFTTrainer launcher for converted public20 prompt-completion JSONL."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Changed: keep this launcher as a thin adapter around official TRL APIs.
# Why: public20 SFT results must be separated from custom Trainer wrappers.
VALID_LABELS = {"pass", "fail"}
DEFAULT_TRAIN_FILE = "train.jsonl"
DEFAULT_VALIDATION_FILE = "validation.jsonl"
KST = timezone(timedelta(hours=9), name="KST")
PINNED_TRL_REFERENCE = "third_party/hf_trl_sft pinned HEAD a9993736c2250da0b3d2f206ec217f144b891e5a"


@dataclass(frozen=True)
class DatasetSummary:
    dataset_dir: str
    train_path: str
    validation_path: str
    train_rows: int
    validation_rows: int
    train_label_counts: dict[str, int]
    validation_label_counts: dict[str, int]


def fail(message: str, exit_code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run official TRL SFTTrainer on converted public20 prompt-completion JSONL."
    )
    parser.add_argument("--dataset-dir", required=True, help="Directory from prepare_public20_sft_dataset.py.")
    parser.add_argument("--model-name-or-path", required=True, help="HF model name/path for SFTTrainer.")
    parser.add_argument("--output-dir", required=True, help="Output directory for adapter/model artifacts.")
    parser.add_argument("--train-file", default=DEFAULT_TRAIN_FILE)
    parser.add_argument("--validation-file", default=DEFAULT_VALIDATION_FILE)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--num-train-epochs", type=float, default=5.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--per-device-eval-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--logging-steps", type=int, default=1)
    parser.add_argument("--eval-strategy", default="epoch", choices=("no", "steps", "epoch"))
    parser.add_argument("--eval-steps", type=int, default=10)
    parser.add_argument("--save-strategy", default="epoch", choices=("no", "steps", "epoch"))
    parser.add_argument("--save-steps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report-to", default="none")
    parser.add_argument("--packing", action="store_true", help="Pass packing=True to SFTConfig.")
    parser.add_argument(
        "--no-gradient-checkpointing",
        dest="gradient_checkpointing",
        action="store_false",
    )
    parser.set_defaults(gradient_checkpointing=True)

    precision = parser.add_mutually_exclusive_group()
    precision.add_argument("--bf16", action="store_true", help="Pass bf16=True to SFTConfig.")
    precision.add_argument("--fp16", action="store_true", help="Pass fp16=True to SFTConfig.")

    parser.add_argument("--use-peft", action="store_true", help="Train a PEFT LoRA adapter via SFTTrainer.")
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--lora-target-modules", default="all-linear")

    parser.add_argument("--dry-run", action="store_true", help="Validate dataset and plan only; no model load.")
    parser.add_argument(
        "--check-dependencies",
        action="store_true",
        help="Import trl/datasets/transformers and verify SFTConfig completion_only_loss support.",
    )
    parser.add_argument("--plan-json", default=None, help="Optional path for dry-run/dependency plan JSON.")
    parser.add_argument("--plan-md", default=None, help="Optional path for dry-run/dependency plan Markdown.")
    return parser.parse_args(argv)


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        fail(f"Missing converted dataset file: {path}")
    if not path.is_file():
        fail(f"Converted dataset path is not a file: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                fail(f"Invalid JSONL at {path}:{line_number}: {exc}")
            if not isinstance(value, dict):
                fail(f"Dataset row {path}:{line_number} is not an object")
            prompt = value.get("prompt")
            completion = value.get("completion")
            if not isinstance(prompt, str) or not prompt:
                fail(f"Dataset row {path}:{line_number} has missing prompt")
            if not isinstance(completion, str) or completion.strip().lower() not in VALID_LABELS:
                fail(f"Dataset row {path}:{line_number} has invalid completion {completion!r}")
            if completion != completion.strip().lower():
                fail(f"Dataset row {path}:{line_number} completion must be canonical pass/fail")
            rows.append(value)
    if not rows:
        fail(f"No rows found in converted dataset file: {path}")
    return rows


def validate_converted_dataset(dataset_dir: Path, train_file: str, validation_file: str) -> DatasetSummary:
    train_path = dataset_dir / train_file
    validation_path = dataset_dir / validation_file
    train_rows = read_jsonl_rows(train_path)
    validation_rows = read_jsonl_rows(validation_path)

    def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        result = {"fail": 0, "pass": 0}
        for row in rows:
            result[row["completion"]] += 1
        return {key: value for key, value in sorted(result.items()) if value}

    return DatasetSummary(
        dataset_dir=str(dataset_dir),
        train_path=str(train_path),
        validation_path=str(validation_path),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        train_label_counts=counts(train_rows),
        validation_label_counts=counts(validation_rows),
    )


def sft_config_supported_names(sft_config_cls: Any) -> set[str]:
    try:
        signature = inspect.signature(sft_config_cls.__init__)
    except (TypeError, ValueError) as exc:
        fail(f"Cannot inspect TRL SFTConfig signature: {exc}")
    names = {
        name
        for name, parameter in signature.parameters.items()
        if name != "self" and parameter.kind is not inspect.Parameter.VAR_KEYWORD
    }
    return names


def require_completion_only_support(supported_names: set[str]) -> None:
    if "completion_only_loss" not in supported_names:
        fail(
            "Installed TRL SFTConfig does not expose completion_only_loss. "
            "Use a TRL version matching the pinned official docs, or switch to a separately reviewed "
            "official DataCollatorForCompletionOnlyLM path."
        )


def choose_supported_name(
    supported_names: set[str],
    preferred: str,
    fallback: str | None,
    description: str,
) -> str:
    if preferred in supported_names:
        return preferred
    if fallback and fallback in supported_names:
        return fallback
    fail(f"Installed TRL SFTConfig does not expose a supported {description} field")


def build_sft_config_kwargs(args: argparse.Namespace, supported_names: set[str]) -> dict[str, Any]:
    # Changed: make completion-only loss an explicit SFTConfig argument.
    # Why: prompt tokens must be ignored by TRL, not by a custom local collator.
    require_completion_only_support(supported_names)
    kwargs: dict[str, Any] = {
        "output_dir": args.output_dir,
        "completion_only_loss": True,
        "packing": bool(args.packing),
        "learning_rate": args.learning_rate,
        "num_train_epochs": args.num_train_epochs,
        "per_device_train_batch_size": args.per_device_train_batch_size,
        "per_device_eval_batch_size": args.per_device_eval_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "logging_steps": args.logging_steps,
        "save_strategy": args.save_strategy,
        "save_steps": args.save_steps,
        "eval_steps": args.eval_steps,
        "seed": args.seed,
        "report_to": args.report_to,
        "gradient_checkpointing": bool(args.gradient_checkpointing),
    }
    eval_strategy_name = choose_supported_name(
        supported_names,
        "eval_strategy",
        "evaluation_strategy",
        "evaluation strategy",
    )
    kwargs[eval_strategy_name] = args.eval_strategy

    max_length_name = choose_supported_name(supported_names, "max_length", "max_seq_length", "max length")
    kwargs[max_length_name] = args.max_length

    if args.bf16:
        kwargs["bf16"] = True
    if args.fp16:
        kwargs["fp16"] = True

    unsupported = sorted(key for key in kwargs if key not in supported_names)
    if unsupported:
        fail(f"Installed TRL SFTConfig lacks required field(s): {', '.join(unsupported)}")
    return kwargs


def parse_target_modules(value: str) -> str | list[str]:
    text = value.strip()
    if not text:
        fail("--lora-target-modules must not be empty when --use-peft is set")
    if text == "all-linear":
        return text
    modules = [part.strip() for part in text.split(",")]
    if not modules or any(not module for module in modules):
        fail("--lora-target-modules must be 'all-linear' or a comma-separated module list")
    return modules


def check_dependencies() -> dict[str, Any]:
    modules: dict[str, Any] = {}
    versions: dict[str, str | None] = {}
    for module_name in ("trl", "datasets", "transformers"):
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            fail(f"Missing dependency {module_name!r}: {exc}", exit_code=3)
        modules[module_name] = module
        versions[module_name] = getattr(module, "__version__", None)

    try:
        from trl import SFTConfig, SFTTrainer  # type: ignore
    except ImportError as exc:
        fail(f"Installed trl does not expose SFTConfig/SFTTrainer: {exc}", exit_code=3)

    supported_names = sft_config_supported_names(SFTConfig)
    require_completion_only_support(supported_names)
    return {
        "ok": True,
        "versions": versions,
        "sft_trainer": str(SFTTrainer),
        "sft_config_supported_fields": sorted(supported_names),
    }


def dry_run_supported_fields() -> set[str]:
    return {
        "bf16",
        "completion_only_loss",
        "eval_strategy",
        "eval_steps",
        "fp16",
        "gradient_accumulation_steps",
        "gradient_checkpointing",
        "learning_rate",
        "logging_steps",
        "max_length",
        "num_train_epochs",
        "output_dir",
        "packing",
        "per_device_eval_batch_size",
        "per_device_train_batch_size",
        "report_to",
        "save_steps",
        "save_strategy",
        "seed",
    }


def build_plan_report(
    args: argparse.Namespace,
    dataset_summary: DatasetSummary,
    config_kwargs: dict[str, Any],
    dependency_report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(KST).isoformat(),
        "training_core": "trl.SFTTrainer",
        "official_reference": PINNED_TRL_REFERENCE,
        "custom_training_loop": False,
        "custom_data_collator": False,
        "formatting_func": None,
        "dataset_format": "standard_prompt_completion",
        "dataset": dataset_summary.__dict__,
        "model_name_or_path": args.model_name_or_path,
        "output_dir": args.output_dir,
        "sft_config_kwargs": config_kwargs,
        "completion_only_loss_basis": {
            "dataset_columns": ["prompt", "completion"],
            "sft_config": {"completion_only_loss": True},
            "trainer_owns_loss_masking": True,
        },
        "peft": {
            "enabled": bool(args.use_peft),
            "lora_r": args.lora_r if args.use_peft else None,
            "lora_alpha": args.lora_alpha if args.use_peft else None,
            "lora_dropout": args.lora_dropout if args.use_peft else None,
            "lora_target_modules": args.lora_target_modules if args.use_peft else None,
        },
        "dependency_report": dependency_report,
    }


# Changed: record and validate trainable parameter coverage after TRL constructs the model.
# Why: full fine-tuning must prove that no PEFT/freezing path left base parameters frozen.
def parameter_training_summary(model: Any) -> dict[str, Any]:
    total_parameters = 0
    trainable_parameters = 0
    parameter_tensors = 0
    trainable_tensors = 0
    for parameter in model.parameters():
        parameter_tensors += 1
        count = int(parameter.numel())
        total_parameters += count
        if bool(getattr(parameter, "requires_grad", False)):
            trainable_tensors += 1
            trainable_parameters += count
    trainable_ratio = trainable_parameters / total_parameters if total_parameters else None
    return {
        "total_parameters": total_parameters,
        "trainable_parameters": trainable_parameters,
        "frozen_parameters": total_parameters - trainable_parameters,
        "parameter_tensors": parameter_tensors,
        "trainable_tensors": trainable_tensors,
        "fully_trainable": total_parameters > 0 and trainable_parameters == total_parameters,
        "trainable_ratio": trainable_ratio,
    }


# Changed: fail fast when the full-FT lane is not actually training every parameter.
# Why: omitting --use-peft must mean full-parameter fine-tuning, not a silently frozen model.
def verify_training_mode(model: Any, use_peft: bool) -> dict[str, Any]:
    summary = parameter_training_summary(model)
    if summary["total_parameters"] <= 0:
        fail("Model exposes no parameters; cannot verify trainable parameter coverage")
    if not use_peft and not summary["fully_trainable"]:
        fail(
            "Full fine-tuning requires every model parameter to be trainable; "
            f"trainable={summary['trainable_parameters']} total={summary['total_parameters']} "
            f"frozen={summary['frozen_parameters']}"
        )
    return summary


def write_plan_reports(report: dict[str, Any], json_path: str | None, md_path: str | None) -> None:
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if md_path:
        lines = [
            "# public20 TRL SFT 실행 계획",
            "",
            "- 학습 core: `trl.SFTTrainer`",
            "- custom training loop: `false`",
            "- custom data collator: `false`",
            "- 데이터 형식: standard prompt-completion",
            "- completion-only loss: `SFTConfig(completion_only_loss=True)`",
            "",
            "## Dataset",
            "",
            f"- train rows: `{report['dataset']['train_rows']}`",
            f"- validation rows: `{report['dataset']['validation_rows']}`",
            "",
        ]
        Path(md_path).parent.mkdir(parents=True, exist_ok=True)
        Path(md_path).write_text("\n".join(lines), encoding="utf-8")


def build_peft_config(args: argparse.Namespace) -> Any:
    if not args.use_peft:
        return None
    if args.lora_r <= 0 or args.lora_alpha <= 0:
        fail("--lora-r and --lora-alpha must be positive")
    if not 0.0 <= args.lora_dropout < 1.0:
        fail("--lora-dropout must be in [0.0, 1.0)")
    try:
        from peft import LoraConfig  # type: ignore
    except ImportError as exc:
        fail(f"--use-peft requires peft: {exc}", exit_code=3)
    return LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=parse_target_modules(args.lora_target_modules),
        bias="none",
        task_type="CAUSAL_LM",
    )


def load_prompt_completion_dataset(dataset_summary: DatasetSummary) -> Any:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as exc:
        fail(f"Missing dependency 'datasets': {exc}", exit_code=3)
    return load_dataset(
        "json",
        data_files={
            "train": dataset_summary.train_path,
            "validation": dataset_summary.validation_path,
        },
    )


def run_training(args: argparse.Namespace, dataset_summary: DatasetSummary, config_kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        from trl import SFTConfig, SFTTrainer  # type: ignore
    except ImportError as exc:
        fail(f"Missing dependency 'trl': {exc}", exit_code=3)

    dataset = load_prompt_completion_dataset(dataset_summary)
    peft_config = build_peft_config(args)
    training_args = SFTConfig(**config_kwargs)
    trainer = SFTTrainer(
        model=args.model_name_or_path,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"] if args.eval_strategy != "no" else None,
        peft_config=peft_config,
    )
    # Changed: verify parameter mode after SFTTrainer model construction and before training.
    # Why: the official trainer owns model setup, so this is the point where full FT can be proven.
    parameter_check = verify_training_mode(trainer.model, use_peft=bool(args.use_peft))
    train_result = trainer.train()
    eval_metrics = trainer.evaluate() if args.eval_strategy != "no" else None
    trainer.save_model(args.output_dir)
    return {
        "parameter_check": parameter_check,
        "train_metrics": getattr(train_result, "metrics", None),
        "eval_metrics": eval_metrics,
        "saved_model_dir": args.output_dir,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_summary = validate_converted_dataset(
        Path(args.dataset_dir),
        args.train_file,
        args.validation_file,
    )
    dependency_report = check_dependencies() if args.check_dependencies else None
    supported_names = (
        set(dependency_report["sft_config_supported_fields"])
        if dependency_report is not None
        else dry_run_supported_fields()
    )
    config_kwargs = build_sft_config_kwargs(args, supported_names)
    report = build_plan_report(args, dataset_summary, config_kwargs, dependency_report)
    write_plan_reports(report, args.plan_json, args.plan_md)

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if dependency_report is None:
        dependency_report = check_dependencies()
        supported_names = set(dependency_report["sft_config_supported_fields"])
        config_kwargs = build_sft_config_kwargs(args, supported_names)
    train_report = run_training(args, dataset_summary, config_kwargs)
    report["train_result"] = train_report
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
