#!/usr/bin/env python3
"""Run manifest-only LoRA training/evaluation sweeps.

Changed: add a sweep runner that never imports solver/rule evaluation modules.
Why: Cycle 3 needs sufficient r16/r32/r64 LoRA comparisons on DCv2 manifests only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
KST = timezone(timedelta(hours=9), name="KST")
DEFAULT_THRESHOLD_SWEEP = "0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70"


# Changed: keep sweep entries explicit and serializable.
# Why: every run must be reproducible from archived sweep_results.json.
@dataclass(frozen=True)
class SweepConfig:
    name: str
    lr: float
    epochs: float
    batch_size: int
    grad_accum: int
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    weight_decay: float = 0.05
    label_smoothing: float = 0.1
    max_seq_len: int = 2048
    warmup_ratio: float = 0.05
    target_modules: str = "q_proj,k_proj,v_proj,o_proj"
    seed: int = 42

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "SweepConfig":
        allowed = set(cls.__dataclass_fields__)
        unknown = sorted(set(data) - allowed)
        if unknown:
            fail(f"Unknown sweep config fields for {data.get('name', '<unnamed>')}: {unknown}")
        return cls(**data)

    def asdict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "lr": self.lr,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "grad_accum": self.grad_accum,
            "lora_r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "weight_decay": self.weight_decay,
            "label_smoothing": self.label_smoothing,
            "max_seq_len": self.max_seq_len,
            "warmup_ratio": self.warmup_ratio,
            "target_modules": self.target_modules,
            "seed": self.seed,
        }


def fail(message: str, exit_code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def default_configs() -> list[SweepConfig]:
    # Changed: encode the Step 4 method decision as the default sweep plan.
    # Why: r16 baselines and r32/r64 high-rank LoRA must be compared after sufficient training.
    return [
        SweepConfig(
            name="r16_lr1e3_do10_ep5",
            lr=1e-3,
            epochs=5.0,
            batch_size=2,
            grad_accum=4,
            lora_r=16,
            lora_alpha=32,
            lora_dropout=0.10,
        ),
        SweepConfig(
            name="r16_lr5e4_do10_ep5",
            lr=5e-4,
            epochs=5.0,
            batch_size=2,
            grad_accum=4,
            lora_r=16,
            lora_alpha=32,
            lora_dropout=0.10,
        ),
        SweepConfig(
            name="r16_lr1e3_do05_ep5",
            lr=1e-3,
            epochs=5.0,
            batch_size=2,
            grad_accum=4,
            lora_r=16,
            lora_alpha=32,
            lora_dropout=0.05,
        ),
        SweepConfig(
            name="r32_lr1e3_do10_ep5",
            lr=1e-3,
            epochs=5.0,
            batch_size=2,
            grad_accum=4,
            lora_r=32,
            lora_alpha=64,
            lora_dropout=0.10,
        ),
        SweepConfig(
            name="r64_lr1e3_do05_ep5",
            lr=1e-3,
            epochs=5.0,
            batch_size=2,
            grad_accum=4,
            lora_r=64,
            lora_alpha=128,
            lora_dropout=0.05,
        ),
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run manifest-only LoRA sweep configs.")
    parser.add_argument("--manifest", required=True, help="Data Contract v2 manifest JSONL.")
    parser.add_argument("--run-root", required=True, help="Run root for adapters/artifacts/logs.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--config-json", default=None, help="Optional JSON list or {'configs': [...]} sweep plan.")
    parser.add_argument("--eval-splits", default="calibration,hidden")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--threshold-sweep", default=DEFAULT_THRESHOLD_SWEEP)
    parser.add_argument("--train-script", default=str(ROOT / "tools" / "training" / "train_manifest_lora.py"))
    parser.add_argument("--eval-script", default=str(ROOT / "tools" / "eval" / "eval_manifest_adapter.py"))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--limit-configs", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Pass --resume to train_manifest_lora.py.")
    parser.add_argument("--force", action="store_true", help="Rerun configs even when eval JSON already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Write the plan without launching training/eval.")
    parser.add_argument("--selection-metric", default="metrics.by_split.hidden.accuracy")
    parser.add_argument("--precision-metric", default="metrics.by_split.hidden.precision_fail")
    parser.add_argument("--recall-metric", default="metrics.by_split.hidden.recall_fail")
    parser.add_argument("--min-fail-precision", type=float, default=0.90)
    parser.add_argument("--min-fail-recall", type=float, default=0.80)
    parser.add_argument("--logging-steps", type=int, default=10)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if not 0.0 <= args.threshold <= 1.0:
        fail("--threshold must be between 0.0 and 1.0")
    if args.limit_configs is not None and args.limit_configs <= 0:
        fail("--limit-configs must be positive when provided")
    for metric_name in ("min_fail_precision", "min_fail_recall"):
        value = getattr(args, metric_name)
        if not 0.0 <= value <= 1.0:
            fail(f"--{metric_name.replace('_', '-')} must be between 0.0 and 1.0")


def load_configs(config_json: str | None, limit: int | None = None) -> list[SweepConfig]:
    if config_json is None:
        configs = default_configs()
    else:
        raw = json.loads(Path(config_json).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw_configs = raw.get("configs")
        else:
            raw_configs = raw
        if not isinstance(raw_configs, list):
            fail("--config-json must contain a list or an object with a 'configs' list")
        configs = [SweepConfig.from_mapping(item) for item in raw_configs]
    if limit is not None:
        configs = configs[:limit]
    names = [config.name for config in configs]
    if len(names) != len(set(names)):
        fail("Sweep config names must be unique")
    if not configs:
        fail("No sweep configs selected")
    return configs


def split_values(value: str) -> list[str]:
    splits = [part.strip() for part in value.split(",") if part.strip()]
    if not splits:
        fail("--eval-splits must contain at least one split")
    return splits


def config_paths(run_root: Path, config: SweepConfig) -> dict[str, Path]:
    return {
        "adapter_final": run_root / "adapters" / config.name / "final",
        "train_log": run_root / "logs" / f"{config.name}.train.log",
        "eval_log": run_root / "logs" / f"{config.name}.eval.log",
        "eval_json": run_root / "artifacts" / f"{config.name}.eval_manifest.json",
        "eval_md": run_root / "artifacts" / f"{config.name}.eval_manifest.md",
    }


def build_train_command(args: argparse.Namespace, config: SweepConfig, run_root: Path) -> list[str]:
    command = [
        args.python,
        args.train_script,
        "--manifest",
        str(Path(args.manifest).expanduser()),
        "--run-root",
        str(run_root),
        "--adapter-name",
        config.name,
        "--base-model",
        args.base_model,
        "--epochs",
        str(config.epochs),
        "--batch-size",
        str(config.batch_size),
        "--grad-accum",
        str(config.grad_accum),
        "--lr",
        str(config.lr),
        "--weight-decay",
        str(config.weight_decay),
        "--label-smoothing",
        str(config.label_smoothing),
        "--max-seq-len",
        str(config.max_seq_len),
        "--warmup-ratio",
        str(config.warmup_ratio),
        "--lora-r",
        str(config.lora_r),
        "--lora-alpha",
        str(config.lora_alpha),
        "--lora-dropout",
        str(config.lora_dropout),
        "--target-modules",
        config.target_modules,
        "--seed",
        str(config.seed),
        "--logging-steps",
        str(args.logging_steps),
    ]
    if args.resume:
        command.append("--resume")
    return command


def build_eval_command(
    args: argparse.Namespace,
    config: SweepConfig,
    paths: dict[str, Path],
) -> list[str]:
    command = [
        args.python,
        args.eval_script,
        "--manifest",
        str(Path(args.manifest).expanduser()),
        "--base-model",
        args.base_model,
        "--adapter-path",
        str(paths["adapter_final"]),
        "--threshold",
        str(args.threshold),
        "--threshold-sweep",
        args.threshold_sweep,
        "--output-json",
        str(paths["eval_json"]),
        "--output-md",
        str(paths["eval_md"]),
    ]
    for split in split_values(args.eval_splits):
        command.extend(["--split", split])
    command.extend(["--batch-size", "1"])
    return command


def run_logged(command: Sequence[str], log_path: Path) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with log_path.open("w", encoding="utf-8") as log_handle:
        log_handle.write("$ " + " ".join(command) + "\n")
        log_handle.flush()
        process = subprocess.run(
            list(command),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return {
        "returncode": process.returncode,
        "elapsed_seconds": time.time() - start,
        "log_path": str(log_path),
    }


def nested_get(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def load_eval_summary(eval_json: Path) -> dict[str, Any]:
    if not eval_json.exists():
        return {}
    data = json.loads(eval_json.read_text(encoding="utf-8"))
    return {
        "metrics": data.get("metrics"),
        "threshold_sweep": data.get("threshold_sweep"),
        "selection": data.get("selection"),
    }


def result_metric(result: dict[str, Any], dotted_path: str) -> float | None:
    value = nested_get(result.get("eval_summary", {}), dotted_path)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def choose_best(results: Sequence[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any] | None:
    completed = [item for item in results if item.get("status") in {"completed", "skipped_completed"}]
    constrained: list[dict[str, Any]] = []
    for item in completed:
        precision = result_metric(item, args.precision_metric)
        recall = result_metric(item, args.recall_metric)
        if (
            precision is not None
            and recall is not None
            and precision >= args.min_fail_precision
            and recall >= args.min_fail_recall
        ):
            constrained.append(item)
    candidates = constrained or completed
    if not candidates:
        return None
    scored = [
        (result_metric(item, args.selection_metric), item)
        for item in candidates
    ]
    scored = [(score, item) for score, item in scored if score is not None]
    if not scored:
        return None
    score, best = max(scored, key=lambda pair: pair[0])
    return {
        "name": best["config"]["name"],
        "selection_metric": args.selection_metric,
        "selection_metric_value": score,
        "constraints_applied": bool(constrained),
        "min_fail_precision": args.min_fail_precision,
        "min_fail_recall": args.min_fail_recall,
        "adapter_final": best["paths"]["adapter_final"],
        "eval_json": best["paths"]["eval_json"],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Manifest-only LoRA Sweep",
        "",
        f"- created_at_kst: `{report['created_at_kst']}`",
        f"- manifest: `{report['manifest']}`",
        f"- run_root: `{report['run_root']}`",
        f"- dry_run: `{report['dry_run']}`",
        f"- best: `{report['best']}`",
        "",
        "| Config | Status | Accuracy | Precision | Recall | Eval JSON |",
        "|---|---|---:|---:|---:|---|",
    ]
    for result in report["results"]:
        accuracy = result_metric(result, report["selection"]["selection_metric"])
        precision = result_metric(result, report["selection"]["precision_metric"])
        recall = result_metric(result, report["selection"]["recall_metric"])
        lines.append(
            f"| `{result['config']['name']}` | `{result['status']}` | "
            f"{format_optional_float(accuracy)} | {format_optional_float(precision)} | "
            f"{format_optional_float(recall)} | `{result['paths']['eval_json']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_optional_float(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.6f}"


def run_config(args: argparse.Namespace, config: SweepConfig, run_root: Path) -> dict[str, Any]:
    paths = config_paths(run_root, config)
    serial_paths = {key: str(value) for key, value in paths.items()}
    if paths["eval_json"].exists() and not args.force:
        return {
            "config": config.asdict(),
            "paths": serial_paths,
            "status": "skipped_completed",
            "train": None,
            "eval": None,
            "eval_summary": load_eval_summary(paths["eval_json"]),
        }

    train_command = build_train_command(args, config, run_root)
    eval_command = build_eval_command(args, config, paths)
    if args.dry_run:
        return {
            "config": config.asdict(),
            "paths": serial_paths,
            "status": "planned",
            "train_command": train_command,
            "eval_command": eval_command,
            "train": None,
            "eval": None,
            "eval_summary": {},
        }

    train_result = run_logged(train_command, paths["train_log"])
    if train_result["returncode"] != 0:
        return {
            "config": config.asdict(),
            "paths": serial_paths,
            "status": "train_failed",
            "train": train_result,
            "eval": None,
            "eval_summary": {},
        }
    eval_result = run_logged(eval_command, paths["eval_log"])
    status = "completed" if eval_result["returncode"] == 0 else "eval_failed"
    return {
        "config": config.asdict(),
        "paths": serial_paths,
        "status": status,
        "train": train_result,
        "eval": eval_result,
        "eval_summary": load_eval_summary(paths["eval_json"]) if status == "completed" else {},
    }


def build_report(args: argparse.Namespace, configs: Sequence[SweepConfig], results: list[dict[str, Any]]) -> dict[str, Any]:
    run_root = Path(args.run_root).expanduser().resolve()
    return {
        "created_at_kst": datetime.now(KST).isoformat(),
        "manifest": str(Path(args.manifest).expanduser()),
        "run_root": str(run_root),
        "base_model": args.base_model,
        "dry_run": args.dry_run,
        "config_count": len(configs),
        "selection": {
            "selection_metric": args.selection_metric,
            "precision_metric": args.precision_metric,
            "recall_metric": args.recall_metric,
            "min_fail_precision": args.min_fail_precision,
            "min_fail_recall": args.min_fail_recall,
        },
        "best": choose_best(results, args),
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    configs = load_configs(args.config_json, args.limit_configs)
    run_root = Path(args.run_root).expanduser().resolve()
    (run_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_root / "logs").mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    report_json = run_root / "artifacts" / "manifest_lora_sweep_results.json"
    report_md = run_root / "artifacts" / "manifest_lora_sweep_results.md"
    for config in configs:
        result = run_config(args, config, run_root)
        results.append(result)
        write_json(report_json, build_report(args, configs, results))
        write_markdown(report_md, build_report(args, configs, results))
        if result["status"] in {"train_failed", "eval_failed"}:
            return 1

    report = build_report(args, configs, results)
    write_json(report_json, report)
    write_markdown(report_md, report)
    print(f"sweep_report_json={report_json}")
    print(f"sweep_report_md={report_md}")
    print(f"best={report['best']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
