#!/bin/bash
# 10-hour monitor: check server + local every 60s
END=$(($(date +%s) + 36000))
LOG="runs/new/monitor.log"

while [ $(date +%s) -lt $END ]; do
  TS="$(TZ=Asia/Seoul date '+%F %T KST')"
  
  # Server check
  SRV=$(ssh -o BatchMode=yes -o ConnectTimeout=10 -o ControlMaster=no -o ControlPath=none team6 '
cd /workspace/sinjeongmin_opal_verifier/repo 2>/dev/null || exit 1
PID=$(cat runs/new/gen_pid.txt 2>/dev/null)
ALIVE=$(ps -p $PID --no-headers 2>/dev/null | wc -l)
RAW=$(wc -l < runs/new/run_*/raw_outputs.jsonl 2>/dev/null | tail -1)
GPU=$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>/dev/null)
echo "alive=$ALIVE raw=$RAW gpu=$GPU"
' 2>/dev/null || echo "ssh_fail")

  # Watcher check
  WPID=$(cat runs/new/watcher_pid.txt 2>/dev/null)
  WALIVE=$(ps -p $WPID --no-headers 2>/dev/null | wc -l)
  
  # Exported count
  EXP=0
  [ -f data/local/gen_new/gen_input.jsonl ] && EXP=$(wc -l < data/local/gen_new/gen_input.jsonl)

  LINE="$TS | srv: $SRV | watcher=$WALIVE exp=$EXP"
  echo "$LINE" | tee -a "$LOG"

  # Auto-restart watcher if dead
  if [ "$WALIVE" -eq 0 ]; then
    echo "$TS | RESTARTING WATCHER" | tee -a "$LOG"
    REMOTE_RUN_FILE="runs/new/latest_run.txt" \
    LOCAL_ROOT="runs/new/local_mirror" \
    CURRENT_DIR="runs/new/local_mirror/current" \
    COMBINED_DIR="runs/new/local_mirror/combined" \
    EXPORT_DIR="data/local/gen_new" \
    SLEEP_SECONDS=90 \
    SSH_ALIAS="team6" \
    REMOTE_REPO="/workspace/sinjeongmin_opal_verifier/repo" \
    nohup bash runs/new/watch.sh >> runs/new/watch.log 2>&1 &
    echo "$!" > runs/new/watcher_pid.txt
    echo "$TS | WATCHER RESTARTED PID=$!" | tee -a "$LOG"
  fi

  # Auto-restart server gen if dead and not finished
  if echo "$SRV" | grep -q "alive=0"; then
    RAWCOUNT=$(echo "$SRV" | grep -oP 'raw=\K[0-9]+')
    if [ "${RAWCOUNT:-0}" -lt 500 ]; then
      echo "$TS | SERVER GEN DEAD (raw=$RAWCOUNT<500). RESTARTING..." | tee -a "$LOG"
      ssh -o BatchMode=yes -o ConnectTimeout=10 -o ControlMaster=no -o ControlPath=none team6 'bash -s' << 'RSRV' 2>/dev/null
cd /workspace/sinjeongmin_opal_verifier/repo
setsid bash -c '
cd /workspace/sinjeongmin_opal_verifier/repo
python3 runs/new/generate_server.py \
  --model Qwen/Qwen3.5-0.8B \
  --num-per-rule 3 \
  --max-new-tokens 4096 \
  --temperature 0.7 \
  --top-p 0.9 \
  >> runs/new/generation_v3.log 2>&1 &
echo $! > runs/new/gen_pid.txt
' &
RSRV
      echo "$TS | SERVER GEN RESTART SENT" | tee -a "$LOG"
    fi
  fi

  sleep 60
done
echo "$(TZ=Asia/Seoul date '+%F %T KST') | MONITOR COMPLETE (10h)" | tee -a "$LOG"
