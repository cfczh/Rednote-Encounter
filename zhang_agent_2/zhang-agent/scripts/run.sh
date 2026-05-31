#!/usr/bin/env bash
# 后台启动张总 Agent HTTP 服务
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "请先: cp .env.example .env 并填写 OPENAI_API_KEY"
  exit 1
fi

mkdir -p logs
source .venv/bin/activate 2>/dev/null || true

nohup python -m zhang_agent serve >> logs/agent.log 2>&1 &
echo $! > logs/agent.pid
echo "张总 Agent 已后台启动 PID=$(cat logs/agent.pid)"
echo "日志: $(pwd)/logs/agent.log"
echo "健康检查: curl http://127.0.0.1:8765/health"
