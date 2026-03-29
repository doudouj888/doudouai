#!/usr/bin/env bash
set -euo pipefail

ulimit -n 65535 || true

cd /opt/gpt_pro

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x /opt/gpt_pro/myenv/bin/python ]; then
    PYTHON_BIN="/opt/gpt_pro/myenv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    PYTHON_BIN="$(command -v python)"
  fi
fi

if [ -f /opt/gpt_pro/.worker_env ]; then
  set -a
  . /opt/gpt_pro/.worker_env
  set +a
fi

pkill -f worker.py 2>/dev/null || true
pkill -f chromedriver 2>/dev/null || true
pkill -f "google-chrome.*--no-sandbox" 2>/dev/null || true
pkill -f "chromium.*--no-sandbox" 2>/dev/null || true
pkill -f "chrome_crashpad_handler" 2>/dev/null || true
pkill -f "Xvfb" 2>/dev/null || true
sleep 2

nohup "$PYTHON_BIN" worker.py > worker_output.log 2>&1 &

echo "worker.py restarted with $PYTHON_BIN"
