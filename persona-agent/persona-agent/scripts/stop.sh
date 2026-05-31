#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${AGENT_PORT:-${ZHANG_AGENT_PORT:-8765}}"
PID_FILE=logs/agent.pid
stopped=0

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill "$pid" 2>/dev/null; then
    echo "已停止 PID $pid（来自 logs/agent.pid）"
    stopped=1
  fi
  rm -f "$PID_FILE"
fi

if command -v lsof >/dev/null 2>&1; then
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    kill "$pid" 2>/dev/null && echo "已停止占用 :${PORT} 的进程 PID $pid" && stopped=1
  done < <(lsof -ti ":${PORT}" 2>/dev/null || true)
fi

if [[ "$stopped" -eq 0 ]]; then
  echo "端口 ${PORT} 上无运行中的服务"
else
  sleep 0.3
  lsof -ti ":${PORT}" >/dev/null 2>&1 && echo "警告: 端口仍被占用" && exit 1
  echo "端口 ${PORT} 已释放"
fi
