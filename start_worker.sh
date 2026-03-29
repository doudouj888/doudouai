#!/usr/bin/env bash
# 简易启动脚本：提高文件句柄上限 + 重启 worker.py

# 1. 提高当前进程能打开的最大文件数（防止 Too many open files）
ulimit -n 65535

# 2. 进入项目目录
cd /opt/gpt_pro

# 2.1 可选加载 worker 环境变量（例如 CHATGPT_API_PROXY）
if [ -f /opt/gpt_pro/.worker_env ]; then
  set -a
  . /opt/gpt_pro/.worker_env
  set +a
fi

# 3. 停掉旧的 worker（没有也没关系）
pkill -f worker.py 2>/dev/null || true
pkill -f chromedriver 2>/dev/null || true
pkill -f "google-chrome.*--no-sandbox" 2>/dev/null || true
pkill -f "chrome_crashpad_handler" 2>/dev/null || true
pkill -f "Xvfb" 2>/dev/null || true
sleep 2

# 4. 启动新的 worker
nohup ./myenv/bin/python worker.py > worker_output.log 2>&1 &

echo "✅ worker.py 已重新启动（open files 已提升到 65535）。"
