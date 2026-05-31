#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PID_FILE=logs/agent.pid
if [[ -f "$PID_FILE" ]]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null && echo "已停止 PID $(cat "$PID_FILE")" || echo "进程可能已退出"
  rm -f "$PID_FILE"
else
  echo "未找到 logs/agent.pid"
fi
