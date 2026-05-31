#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

PORT="${AGENT_PORT:-${ZHANG_AGENT_PORT:-8765}}"
if command -v lsof >/dev/null 2>&1 && lsof -ti ":${PORT}" >/dev/null 2>&1; then
  echo "端口 ${PORT} 已被占用，正在停止旧服务…"
  ./scripts/stop.sh
fi

exec .venv/bin/python -m persona_agent serve
