# 张总 Agent

把项目内部的 `skills/张总` 封装成**可独立运行**的后台对话服务，不依赖 Cursor。

## 安装

```bash
cd zhang-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY（及可选 OPENAI_BASE_URL、模型名）
```

## 用法

### 1. 终端直接聊

```bash
python -m zhang_agent chat
```

### 2. HTTP 后台服务（前台）

```bash
python -m zhang_agent serve
# 默认 http://127.0.0.1:8765
```

### 3. 双 Agent 对话

默认让张总和 `skills/xiao_hong` 互相对话：

```bash
python -m zhang_agent duel --rounds 3
```

也可以指定开场话题：

```bash
python -m zhang_agent duel --rounds 3 --topic "张总，小红今天来聊聊工厂里的设计改造。"
```

加上 `--voice` 会用 `VocalCN_Python源码/resources` 里的音频资源生成每句语音，并按对话顺序播放：

```bash
python -m zhang_agent duel --rounds 3 --voice
```

如果要把张总和小红分别输出到两台 USB 连接的 M5Stack Core S3 Lite：

1. 用 Arduino IDE 打开并烧录 `firmware/m5stack_usb_wav_player/m5stack_usb_wav_player.ino`
2. 两台设备都烧录同一份程序
3. 连接两台设备后查看串口：

```bash
python scripts/list_serial_ports.py
```

4. 运行双设备语音：

```bash
python -m zhang_agent duel --rounds 3 --voice --voice-output m5 \
  --zhang-port /dev/cu.usbmodemXXXX \
  --other-port /dev/cu.usbmodemYYYY
```

也可以把端口写入 `.env`：

```env
ZHANG_DEVICE_PORT=/dev/cu.usbmodemXXXX
OTHER_DEVICE_PORT=/dev/cu.usbmodemYYYY
```

### 4. HTTP 后台服务（daemon）

```bash
chmod +x scripts/run.sh scripts/stop.sh
./scripts/run.sh    # 启动
./scripts/stop.sh   # 停止
```

### API 示例

```bash
# 健康检查
curl http://127.0.0.1:8765/health

# 单轮（自动创建 session）
curl -s http://127.0.0.1:8765/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"张总，我想请两天假"}' | jq

# 多轮（带上 session_id）
curl -s http://127.0.0.1:8765/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"上一轮返回的id","message":"产量这周没达标"}' | jq
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | 必填 |
| `OPENAI_BASE_URL` | 可选，兼容 DeepSeek / 通义 / Ollama 等 |
| `OPENAI_MODEL` | 默认 `gpt-4o-mini` |
| `ZHANG_SKILL_DIR` | 张总 Skill 路径，默认 `skills/张总` |
| `OTHER_AGENT_PATH` | 另一个 Agent 人设路径，默认 `skills/xiao_hong` |
| `ZHANG_AGENT_HOST` / `ZHANG_AGENT_PORT` | 服务监听地址 |

## 架构

```
zhang_agent/prompt.py   ← 读取 persona.md / management.md
zhang_agent/chat.py     ← OpenAI 兼容 API 对话
zhang_agent/duel.py     ← 双 Agent 轮流对话
zhang_agent/server.py   ← FastAPI + 内存 session
zhang_agent/cli.py      ← 终端 REPL
```

修改张总人设时，直接编辑 `skills/张总/assets/`，重启服务即可生效。
