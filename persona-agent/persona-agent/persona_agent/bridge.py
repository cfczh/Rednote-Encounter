"""串口 + HTTP：硬件用 PERSONA|<id> 选人设，再发起对话。"""

from __future__ import annotations

import sys
import time
from datetime import datetime

import requests
import serial

from persona_agent.config import (
    agent_api_url,
    default_persona_id,
    serial_baudrate,
    serial_port,
)
from persona_agent.hardware import (
    drain_persona_selection,
    pick_animation_state,
    send_txt,
)
from persona_agent.registry import PersonaRegistry
from persona_agent.vocalcn_stream import speak

TIMING_VERSION = "v3"
API_URL = agent_api_url()

http = requests.Session()
http.trust_env = False
registry = PersonaRegistry()


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def ts(label: str, t0: float) -> float:
    now = time.perf_counter()
    log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {label} (+{now - t0:.3f}s)")
    return now


def call_api(payload: dict) -> tuple[dict, float]:
    t0 = time.perf_counter()
    r = http.post(API_URL, json=payload, timeout=120)
    api_s = time.perf_counter() - t0
    r.raise_for_status()
    return r.json(), api_s


def open_serial() -> serial.Serial:
    port = serial_port()
    log(f"打开串口 {port} @ {serial_baudrate()}")
    return serial.Serial(port, serial_baudrate(), timeout=1)


def apply_hardware_persona(ser: serial.Serial, current: str) -> str:
    selected = drain_persona_selection(ser)
    if selected and selected != current:
        try:
            info = registry.get(selected)
            log(f"硬件切换人设 → {info.name} [{selected}]")
            return selected
        except KeyError as e:
            log(f"硬件上报未知人设 {selected!r}: {e}")
    return current


def run_bridge() -> None:
    log(f">>> bridge {TIMING_VERSION} | API={API_URL} <<<")
    log("硬件协议: PERSONA|<persona_id>  例如 PERSONA|zhang_zong")

    try:
        health = http.get(API_URL.replace("/v1/chat", "/health"), timeout=5)
        health.raise_for_status()
        log(f"Agent 服务 OK: {health.json().get('personas', [])}")
    except requests.RequestException as e:
        log(f"警告: Agent 不可用 ({e})，请先: cd persona-agent && ./serve.sh")

    for p in registry.list():
        log(f"  可用人设: {p.persona_id} ({p.name})")

    ser = open_serial()
    current_persona = default_persona_id()
    sessions: dict[str, str] = {}

    try:
        registry.get(current_persona)
    except KeyError as e:
        log(f"默认人设无效: {e}")
        sys.exit(1)

    log(f"当前人设: {registry.display_name(current_persona)} [{current_persona}]")

    while True:
        current_persona = apply_hardware_persona(ser, current_persona)
        label = registry.display_name(current_persona)

        try:
            text = input(f"你({current_persona}): ")
        except (EOFError, KeyboardInterrupt):
            log("\n退出")
            break

        if not text.strip():
            continue

        payload: dict = {
            "message": text,
            "persona_id": current_persona,
        }
        sid = sessions.get(current_persona)
        if sid:
            payload["session_id"] = sid

        try:
            data, api_s = call_api(payload)
        except requests.RequestException as e:
            log(f"API 失败: {e}")
            continue

        if "reply" not in data:
            log(f"API 响应异常: {data}")
            continue

        reply = data["reply"]
        sessions[current_persona] = data.get("session_id", sid or "")
        pid = data.get("persona_id", current_persona)
        pname = data.get("persona_name", label)

        print(data, flush=True)
        print(f"{pname}:", reply, flush=True)
        log(f"LLM 耗时 {api_s:.3f}s")

        state = pick_animation_state(reply)
        try:
            send_txt(ser, state, reply)
            speak(
                reply,
                ser,
                persona_id=pid
            )
        except serial.SerialException as e:
            log(f"串口输出失败: {e}")

        print("发送状态:", state, flush=True)

    try:
        ser.close()
    except Exception:
        pass


if __name__ == "__main__":
    run_bridge()
