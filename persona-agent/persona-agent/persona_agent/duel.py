"""两个人设在两块 M5 上轮流对话，并在每块屏幕同屏显示双方。"""

from __future__ import annotations

from glob import glob
import sys
import time

import serial

from persona_agent.agents import AgentPool
from persona_agent.config import (
    duel_persona_a_id,
    duel_persona_b_id,
    serial_baudrate,
)
from persona_agent.hardware import (
    drain_serial,
    parse_persona_line,
    pick_animation_state,
)
from persona_agent.registry import PersonaRegistry
from persona_agent.sessions import Session
from persona_agent.vocalcn_stream import reset_m5, speak


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _open_serial(port: str) -> serial.Serial:
    p = port
    _log(f"打开串口 {p} @ {serial_baudrate()}")
    return serial.Serial(p, serial_baudrate(), timeout=1)


def _candidate_ports() -> list[str]:
    return sorted(
        glob("/dev/cu.usbmodem*") +
        glob("/dev/cu.wchusbserial*") +
        glob("/dev/cu.usbserial*")
    )


def _read_persona(ser: serial.Serial, timeout: float = 4.0) -> str | None:
    deadline = time.perf_counter() + timeout
    selected: str | None = None

    while time.perf_counter() < deadline:
        if not ser.in_waiting:
            time.sleep(0.05)
            continue

        raw = ser.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            _log(f"  {ser.port}: {line}")

        pid = parse_persona_line(line)
        if pid:
            selected = pid
            break

    return selected


def open_persona_serials(
    required: set[str],
) -> dict[str, serial.Serial]:
    serials: dict[str, serial.Serial] = {}
    opened: list[serial.Serial] = []

    for port in _candidate_ports():
        try:
            ser = _open_serial(port)
        except serial.SerialException as exc:
            _log(f"跳过串口 {port}: {exc}")
            continue

        opened.append(ser)
        time.sleep(1.0)
        pid = _read_persona(ser)

        if not pid:
            _log(f"{port} 未上报 PERSONA，关闭")
            continue

        _log(f"{port} 绑定为 {pid}")
        if pid in required and pid not in serials:
            serials[pid] = ser

    missing = required - set(serials)
    if missing:
        for ser in opened:
            if ser not in serials.values():
                ser.close()
        raise RuntimeError(
            "缺少 M5 身份: "
            + ", ".join(sorted(missing))
            + "。请用板子按键 A=zhang_zong、B=xiao_hong，或发送 SEL|id 后重启 duel。"
        )

    for ser in opened:
        if ser not in serials.values():
            ser.close()

    return serials


def _safe_line(text: str) -> str:
    return " ".join(text.replace("\r", "\n").splitlines()).strip()


def send_duel_scene(
    ser: serial.Serial,
    left_id: str,
    right_id: str,
    speaker_id: str,
    state: str,
    display_name: str,
    text: str,
) -> None:
    screen = f"{display_name}：{_safe_line(text)}"
    msg = f"DUEL|{left_id}|{right_id}|{speaker_id}|{state}|{screen}\n"
    ser.write(msg.encode("utf-8"))
    ser.flush()
    _log(f"  → {ser.port}: DUEL|{speaker_id}|{state}|{screen[:36]}…")


def deliver_turn(
    serials: dict[str, serial.Serial],
    left_id: str,
    right_id: str,
    persona_id: str,
    display_name: str,
    reply: str,
    *,
    use_hardware: bool,
) -> None:
    """一位 agent 完整占满单板：切换人设 → 显示 → 播完，再交给下一位。"""
    _log(f">>> 轮到 {display_name} [{persona_id}]")

    if not use_hardware:
        print(f"[{display_name}] {reply}\n", flush=True)
        return

    state = pick_animation_state(reply)

    for ser in serials.values():
        drain_serial(ser, timeout=0.05)
        send_duel_scene(
            ser,
            left_id,
            right_id,
            persona_id,
            state,
            display_name,
            reply,
        )

    time.sleep(0.05)

    speaker_ser = serials[persona_id]

    try:
        reset_m5()
        speak(
            reply,
            speaker_ser,
            persona_id=persona_id
        )
    except serial.SerialException as exc:
        _log(f"speak 失败，0.5s 后重试: {exc}")
        time.sleep(0.5)

        drain_serial(speaker_ser, timeout=0.3)
        send_duel_scene(
            speaker_ser,
            left_id,
            right_id,
            persona_id,
            state,
            display_name,
            reply,
        )
        time.sleep(0.05)
        reset_m5()
        speak(
            reply,
            speaker_ser,
            persona_id=persona_id
        )

    for ser in serials.values():
        drain_serial(ser, timeout=0.1)

    _log(f"<<< {display_name} 发言结束\n")


def run_duel(
    persona_a: str | None = None,
    persona_b: str | None = None,
    rounds: int = 6,
    topic: str | None = None,
    *,
    use_hardware: bool = True,
) -> None:
    registry = PersonaRegistry()
    pool = AgentPool(registry)

    pid_a = persona_a or duel_persona_a_id()
    pid_b = persona_b or duel_persona_b_id()

    try:
        info_a = registry.get(pid_a)
        info_b = registry.get(pid_b)
    except KeyError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    agent_a = pool.get(pid_a)
    agent_b = pool.get(pid_b)
    session_a = Session(id=f"duel-{pid_a}", persona_id=pid_a)
    session_b = Session(id=f"duel-{pid_b}", persona_id=pid_b)

    label_a = info_a.name
    label_b = info_b.name

    message = topic or f"{label_b}，我想跟你聊聊。"

    print("双 Persona 对话（双板轮流）")
    print(f"  A: {label_a} [{pid_a}]")
    print(f"  B: {label_b} [{pid_b}]")
    print(f"  轮数: {rounds}")
    print(f"  硬件: {'开' if use_hardware else '关（仅终端）'}\n")

    serials: dict[str, serial.Serial] = {}
    if use_hardware:
        reset_m5()
        serials = open_persona_serials(
            {pid_a, pid_b}
        )
        _log("双串口就绪，每轮：DUEL 场景广播 → 当前说话者音频(播完) → 下一位\n")

    try:
        for index in range(1, rounds + 1):
            print(f"—— 第 {index}/{rounds} 轮 ——", flush=True)

            _log(f"[LLM] 生成 {label_a} 回复…")
            reply_a = agent_a.reply(session_a, f"{label_b}：{message}")
            print(f"[{index}. {label_a}]\n{reply_a}\n", flush=True)
            deliver_turn(
                serials,
                pid_a,
                pid_b,
                pid_a,
                label_a,
                reply_a,
                use_hardware=use_hardware,
            )

            _log(f"[LLM] 生成 {label_b} 回复…")
            reply_b = agent_b.reply(session_b, f"{label_a}：{reply_a}")
            print(f"[{index}. {label_b}]\n{reply_b}\n", flush=True)
            deliver_turn(
                serials,
                pid_a,
                pid_b,
                pid_b,
                label_b,
                reply_b,
                use_hardware=use_hardware,
            )

            message = reply_b
    finally:
        for ser in serials.values():
            ser.close()
        reset_m5()

    print("对话结束。")


def run_hardware_smoke() -> None:
    """不调用模型，只验证双板身份绑定、同屏显示和轮流音频。"""
    registry = PersonaRegistry()
    pid_a = duel_persona_a_id()
    pid_b = duel_persona_b_id()
    label_a = registry.get(pid_a).name
    label_b = registry.get(pid_b).name

    reset_m5()
    serials = open_persona_serials(
        {pid_a, pid_b}
    )

    try:
        deliver_turn(
            serials,
            pid_a,
            pid_b,
            pid_a,
            label_a,
            "你好小红，我是张总，双板测试开始。",
            use_hardware=True,
        )
        deliver_turn(
            serials,
            pid_a,
            pid_b,
            pid_b,
            label_b,
            "你好张总，我是小红，双板切换正常。",
            use_hardware=True,
        )
    finally:
        for ser in serials.values():
            ser.close()
        reset_m5()

    print("双板硬件 smoke test 结束。")


if __name__ == "__main__":
    run_duel()
