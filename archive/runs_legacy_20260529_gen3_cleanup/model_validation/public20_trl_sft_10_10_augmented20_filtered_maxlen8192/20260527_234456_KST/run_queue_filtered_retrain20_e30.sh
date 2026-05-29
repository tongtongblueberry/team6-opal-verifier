#!/usr/bin/env bash
set -uo pipefail

# Changed: run RETRAIN-20 filtered max_length-compatible augmented public20 validation comparison from an ops run-root snapshot.
# Why: generated fallback rows are experimental comparison data only; rows 00038 and 00039 are excluded for max_length=8192 compatibility, and public20 validation must stay byte-identical to the baseline validation files.
RUN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$RUN_ROOT/repo"
PY=/workspace/sinjeongmin_opal_verifier/ops/venvs/trl_sft/bin/python
MODEL=Qwen/Qwen3.5-0.8B
DATASET_BASE=runs/model_validation/public20_trl_sft_10_10_augmented20_filtered_maxlen8192/20260527_234456_KST/datasets
MAX_LENGTH=8192
LEARNING_RATE=1e-5
export CUDA_VISIBLE_DEVICES=0
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1

mkdir -p "$RUN_ROOT"/logs "$RUN_ROOT"/plans "$RUN_ROOT"/models "$RUN_ROOT"/eval "$RUN_ROOT"/status
exec >> "$RUN_ROOT/queue.log" 2>&1
echo $$ > "$RUN_ROOT/status/queue_runner.pid"
cd "$REPO_DIR" || exit 2

echo "QUEUE_START $(TZ=Asia/Seoul date "+%F %T") KST"
echo "RUN_ROOT $RUN_ROOT"
echo "MODEL $MODEL"
echo "PY $PY"
echo "MAX_LENGTH $MAX_LENGTH"
echo "LEARNING_RATE $LEARNING_RATE"
if nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | grep -q "[0-9]"; then
  echo "BLOCKED existing GPU compute process detected before queue start"
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader || true
  printf "blocked_existing_gpu_process\n" > "$RUN_ROOT/status/queue_state.txt"
  exit 10
fi
printf "running\n" > "$RUN_ROOT/status/queue_state.txt"

run_pfail_sidecar() {
  local input_json=$1
  local output_json=$2
  "$PY" - "$input_json" "$output_json" <<PY
import json, math, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src, encoding="utf-8"))
items = []
for pred in data.get("predictions", []):
    scores = pred.get("scores") or {}
    fail = (scores.get("fail") or {}).get("mean_logprob")
    pas = (scores.get("pass") or {}).get("mean_logprob")
    p_fail = None
    if fail is not None and pas is not None:
        m = max(fail, pas)
        ef = math.exp(fail - m)
        ep = math.exp(pas - m)
        p_fail = ef / (ef + ep)
    items.append({
        "sample_id": pred.get("sample_id"),
        "gold": pred.get("gold"),
        "prediction": pred.get("prediction"),
        "p_fail_from_mean_logprob_softmax": p_fail,
        "mean_logprob_margin_fail_minus_pass": pred.get("mean_logprob_margin_fail_minus_pass"),
        "raw_scores": scores,
    })
out = {
    "source_logprob_json": src,
    "calibration_threshold_supported_by_evaluator": False,
    "p_fail_derivation": "softmax over saved pass/fail candidate mean_logprob",
    "items": items,
}
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
    f.write("\n")
PY
}

while read -r variant seed epochs; do
  if [ "$variant" = "variant" ]; then
    continue
  fi
  job="${variant}_seed${seed}_e${epochs}"
  dataset_dir="$DATASET_BASE/${variant}_seed_${seed}"
  model_dir="$RUN_ROOT/models/$job"
  plan_json="$RUN_ROOT/plans/$job.plan.json"
  plan_md="$RUN_ROOT/plans/$job.plan.md"
  train_stdout="$RUN_ROOT/logs/$job.train.stdout.log"
  train_stderr="$RUN_ROOT/logs/$job.train.stderr.log"
  gen_stdout="$RUN_ROOT/logs/$job.generation.stdout.log"
  gen_stderr="$RUN_ROOT/logs/$job.generation.stderr.log"
  logprob_stdout="$RUN_ROOT/logs/$job.logprob.stdout.log"
  logprob_stderr="$RUN_ROOT/logs/$job.logprob.stderr.log"
  status_file="$RUN_ROOT/status/$job.status"
  gen_json="$RUN_ROOT/eval/$job.generation.json"
  gen_md="$RUN_ROOT/eval/$job.generation.md"
  logprob_json="$RUN_ROOT/eval/$job.logprob.json"
  logprob_md="$RUN_ROOT/eval/$job.logprob.md"
  pfail_json="$RUN_ROOT/eval/$job.logprob_pfail.json"

  echo "$job" > "$RUN_ROOT/status/current_job.txt"
  echo "JOB_START $job $(TZ=Asia/Seoul date "+%F %T") KST"
  printf "running\n" > "$status_file"
  "$PY" tools/training/run_trl_sft_public20.py \
    --dataset-dir "$dataset_dir" \
    --model-name-or-path "$MODEL" \
    --output-dir "$model_dir" \
    --max-length "$MAX_LENGTH" \
    --num-train-epochs "$epochs" \
    --learning-rate "$LEARNING_RATE" \
    --per-device-train-batch-size 1 \
    --per-device-eval-batch-size 1 \
    --gradient-accumulation-steps 8 \
    --logging-steps 1 \
    --eval-strategy epoch \
    --save-strategy no \
    --seed "$seed" \
    --report-to none \
    --bf16 \
    --check-dependencies \
    --plan-json "$plan_json" \
    --plan-md "$plan_md" \
    > "$train_stdout" 2> "$train_stderr"
  train_rc=$?
  if [ "$train_rc" -ne 0 ]; then
    echo "JOB_TRAIN_FAIL $job rc=$train_rc $(TZ=Asia/Seoul date "+%F %T") KST"
    printf "train_failed rc=%s\n" "$train_rc" > "$status_file"
    continue
  fi

  "$PY" tools/eval/eval_trl_sft_public20_generation.py \
    --dataset-jsonl "$dataset_dir/validation.jsonl" \
    --model-name-or-path "$model_dir" \
    --output-json "$gen_json" \
    --output-md "$gen_md" \
    --batch-size 1 \
    --max-new-tokens 3 \
    --max-length "$MAX_LENGTH" \
    > "$gen_stdout" 2> "$gen_stderr"
  gen_rc=$?
  if [ "$gen_rc" -ne 0 ]; then
    echo "JOB_GENERATION_FAIL $job rc=$gen_rc $(TZ=Asia/Seoul date "+%F %T") KST"
    printf "generation_failed rc=%s\n" "$gen_rc" > "$status_file"
    continue
  fi

  "$PY" tools/eval/eval_trl_sft_public20_logprob.py \
    --dataset-jsonl "$dataset_dir/validation.jsonl" \
    --model-name-or-path "$model_dir" \
    --output-json "$logprob_json" \
    --output-md "$logprob_md" \
    --batch-size 1 \
    --max-length "$MAX_LENGTH" \
    --progress-every 1 \
    > "$logprob_stdout" 2> "$logprob_stderr"
  logprob_rc=$?
  if [ "$logprob_rc" -ne 0 ]; then
    echo "JOB_LOGPROB_FAIL $job rc=$logprob_rc $(TZ=Asia/Seoul date "+%F %T") KST"
    printf "logprob_failed rc=%s\n" "$logprob_rc" > "$status_file"
    continue
  fi

  run_pfail_sidecar "$logprob_json" "$pfail_json"
  printf "done\n" > "$status_file"
  echo "JOB_DONE $job $(TZ=Asia/Seoul date "+%F %T") KST"
done < "$RUN_ROOT/job_manifest.tsv"

printf "done\n" > "$RUN_ROOT/status/queue_state.txt"
echo "QUEUE_DONE $(TZ=Asia/Seoul date "+%F %T") KST"
