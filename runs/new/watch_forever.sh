#!/bin/bash
# Restart watcher if it dies
while true; do
  echo "$(date '+%F %T') Starting watcher..."
  REMOTE_RUN_FILE="runs/new/latest_run.txt" \
  LOCAL_ROOT="runs/new/local_mirror" \
  CURRENT_DIR="runs/new/local_mirror/current" \
  COMBINED_DIR="runs/new/local_mirror/combined" \
  EXPORT_DIR="data/local/gen_new" \
  SLEEP_SECONDS=90 \
  SSH_ALIAS="team6" \
  REMOTE_REPO="/workspace/sinjeongmin_opal_verifier/repo" \
  bash runs/new/watch.sh 2>&1
  echo "$(date '+%F %T') Watcher died. Restarting in 10s..."
  sleep 10
done
