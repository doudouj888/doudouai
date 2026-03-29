#!/usr/bin/env bash
set -u

WORKDIR="/opt/gpt_pro"
LOG="$WORKDIR/monitor_worker.log"
FD_THRESHOLD=900          # fd 太多就重启
IDLE_SECONDS=900          # 15分钟没新日志就重启（防止一直卡盾）

ts() { date "+%F %T"; }

restart() {
  echo "$(ts) 🔁 restart worker: $1" >> "$LOG"
  cd "$WORKDIR" || exit 1
  ./start_worker.sh >> "$LOG" 2>&1
}

# 1) worker 是否存在
pid="$(pgrep -f "worker.py" | head -n 1 || true)"
if [ -z "${pid}" ]; then
  restart "worker not running"
  exit 0
fi

# 2) 最近是否出现 select fd 错误
if tail -n 400 "$WORKDIR/worker_output.log" 2>/dev/null | grep -q "filedescriptor out of range in select"; then
  restart "found select fd out of range in log"
  exit 0
fi

# 3) fd 数是否过高（防止慢性累积）
fd_count="$(ls "/proc/$pid/fd" 2>/dev/null | wc -l | tr -d ' ')"
if [ -n "$fd_count" ] && [ "$fd_count" -ge "$FD_THRESHOLD" ]; then
  restart "fd_count=${fd_count} >= ${FD_THRESHOLD}"
  exit 0
fi
# 队列为空：worker 不输出日志是正常的，不要重启
if [ ! -s "$WORKDIR/queue.txt" ]; then
  exit 0
fi

# 4) 日志太久不更新（经常是卡在盾/卡死）
if [ -f "$WORKDIR/worker_output.log" ]; then
  last_update="$(stat -c %Y "$WORKDIR/worker_output.log" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  if [ "$last_update" -gt 0 ] && [ $((now - last_update)) -ge "$IDLE_SECONDS" ]; then
    restart "log idle >= ${IDLE_SECONDS}s"
    exit 0
  fi
fi

exit 0
