#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "请先: cp .env.example .env 并填写 OPENAI_API_KEY"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "请先: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate

mkdir -p logs
nohup python -m persona_agent serve >> logs/agent.log 2>&1 &
echo $! > logs/agent.pid
echo "Persona Agent 已后台启动 PID=$(cat logs/agent.pid)"
echo "日志: $(pwd)/logs/agent.log"
echo "健康检查: curl http://127.0.0.1:${AGENT_PORT:-8765}/health"
