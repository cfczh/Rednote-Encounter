#!/usr/bin/env python3
"""
WebSocket 命令桥 —— 用 WS 替代串口给 M5 板子下发动画命令。

板子(cores3_encounter.ino，填好 WIFI_SSID/WS_HOST 后)作为 WS 客户端连到本服务器，
上线时发送  HELLO|<persona>  报告自己是谁。本服务器可向某块板或所有板广播
与串口完全相同的命令行：
  TXT|<state>|<text>
  DUEL|<left>|<right>|<speaker>|<state>|<text>
  #ACT:<state>

依赖：pip install websockets

用法：
  python tools/ws_bridge.py                # 监听 0.0.0.0:8765
  python tools/ws_bridge.py --port 8765

启动后在控制台直接输入整行命令回车即广播给所有已连板子；
用  to:<persona> <命令>  只发给某块板，例如：
  DUEL|xiao_hong|zhang_zong|zhang_zong|chat|你好呀
  to:zhang_zong TXT|leave|先走了

把本机的局域网 IP 填到固件的 WS_HOST，两端同一 WiFi 即可联通。
（后续可把这里的广播逻辑接到 zhang_agent 的对话循环，实现"靠近→对话→语音+动画"。）
"""
import argparse
import asyncio
import sys

try:
    import websockets
except ImportError:
    print("缺少依赖：请先运行  pip install websockets")
    sys.exit(1)


clients = {}  # persona -> websocket


async def handler(ws, *_):
    """每个板子一个连接；首条 HELLO|<persona> 注册身份，其余打印为板子回报。"""
    persona = None
    try:
        async for raw in ws:
            msg = raw.strip()
            if msg.startswith("HELLO|"):
                persona = msg[6:].strip() or "unknown"
                clients[persona] = ws
                print(f"[+] 板子上线: {persona}  (当前在线: {', '.join(clients)})")
            else:
                print(f"[板子 {persona}] {msg}")
    except Exception as exc:
        print(f"[!] 连接异常 {persona}: {exc}")
    finally:
        if persona and clients.get(persona) is ws:
            del clients[persona]
            print(f"[-] 板子下线: {persona}")


async def send_to(targets, cmd):
    dead = []
    for persona, ws in targets:
        try:
            await ws.send(cmd)
            print(f"  -> {persona}: {cmd}")
        except Exception as exc:
            print(f"  !! 发送失败 {persona}: {exc}")
            dead.append(persona)
    for p in dead:
        clients.pop(p, None)


async def console():
    loop = asyncio.get_event_loop()
    print("=" * 56)
    print("输入整行命令回车=广播给所有板；to:<persona> <命令>=单发；空行跳过。")
    print("例: DUEL|xiao_hong|zhang_zong|zhang_zong|chat|你好呀")
    print("=" * 56)
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.rstrip("\r\n")
        if not line:
            continue
        if not clients:
            print("  (暂无板子在线)")
            continue
        if line.startswith("to:"):
            head, _, cmd = line.partition(" ")
            persona = head[3:]
            targets = [(p, w) for p, w in clients.items() if p == persona]
            if not targets:
                print(f"  (没有在线的 {persona})")
                continue
        else:
            cmd = line
            targets = list(clients.items())
        await send_to(targets, cmd)


async def main(host, port):
    async with websockets.serve(handler, host, port):
        print(f"WS 桥已启动: ws://{host}:{port}")
        await console()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="M5 WebSocket 命令桥")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    ap.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        print("\n再见。")
