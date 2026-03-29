#!/usr/bin/env bash
set -u

WORKDIR="/opt/gpt_pro"
LOG="$WORKDIR/monitor_worker.log"
FD_THRESHOLD=900
IDLE_SECONDS=900

ts() { date "+%F %T"; }

restart() {
  echo "$(ts) restart worker: $1" >> "$LOG"
  cd "$WORKDIR" || exit 1
  ./start_worker.sh >> "$LOG" 2>&1
}

pid="$(pgrep -f "worker.py" | head -n 1 || true)"
if [ -z "${pid}" ]; then
  restart "worker not running"
  exit 0
fi

if tail -n 400 "$WORKDIR/worker_output.log" 2>/dev/null | grep -q "filedescriptor out of range in select"; then
  restart "found select fd out of range in log"
  exit 0
fi

fd_count="$(ls "/proc/$pid/fd" 2>/dev/null | wc -l | tr -d ' ')"
if [ -n "$fd_count" ] && [ "$fd_count" -ge "$FD_THRESHOLD" ]; then
  restart "fd_count=${fd_count} >= ${FD_THRESHOLD}"
  exit 0
fi

if [ ! -s "$WORKDIR/queue.txt" ]; then
  exit 0
fi

if [ -f "$WORKDIR/worker_output.log" ]; then
  last_update="$(stat -c %Y "$WORKDIR/worker_output.log" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  if [ "$last_update" -gt 0 ] && [ $((now - last_update)) -ge "$IDLE_SECONDS" ]; then
    restart "log idle >= ${IDLE_SECONDS}s"
    exit 0
  fi
fi

exit 0
