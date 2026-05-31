"""硬件串口协议：人设切换、文字、播放完成同步。"""

from __future__ import annotations

import re
import sys
import time

import serial

PLAYBACK_DONE_MARKERS = frozenset(
    {"PCM DONE", "PCM END", "PLAY DONE", "AUDIO DONE"}
)

# 设备发送格式（任选其一）:
#   PERSONA|zhang_zong
#   SEL|xiao_hong
_PERSONA_LINE = re.compile(
    r"^(?:PERSONA|SEL)\|([A-Za-z0-9_-]+)\s*$",
    re.IGNORECASE,
)


def parse_persona_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    m = _PERSONA_LINE.match(line)
    return m.group(1) if m else None


def drain_persona_selection(ser: serial.Serial) -> str | None:
    """非阻塞读取串口缓冲区里的人设切换指令，返回最新 persona_id。"""
    selected: str | None = None
    while ser.in_waiting:
        raw = ser.readline()
        if not raw:
            break
        try:
            line = raw.decode("utf-8", errors="ignore")
        except Exception:
            continue
        pid = parse_persona_line(line)
        if pid:
            selected = pid
    return selected


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def send_persona(ser: serial.Serial, persona_id: str) -> None:
    """
    主机 → M5 下发人设（需固件支持）。
    当前 M5 只支持设备 → 主机上报 PERSONA；默认不下发，避免卡住 PCM。
    设 DUEL_HOST_PERSONA=1 可尝试开启。
    """
    import os

    if os.getenv("DUEL_HOST_PERSONA", "").lower() not in ("1", "true", "yes"):
        return
    ser.write(f"PERSONA|{persona_id}\n".encode("utf-8"))
    ser.flush()
    time.sleep(0.08)


def send_txt(ser: serial.Serial, state: str, text: str) -> None:
    safe = " ".join(text.replace("\r", "\n").splitlines()).strip()
    ser.write(f"TXT|{state}|{safe}\n".encode("utf-8"))
    ser.flush()


def send_duel_txt(
    ser: serial.Serial,
    display_name: str,
    state: str,
    text: str,
) -> None:
    """与 bridge 相同 TXT 协议；屏幕前缀说话者便于区分两人。"""
    safe = " ".join(text.replace("\r", "\n").splitlines()).strip()
    screen = f"{display_name}：{safe}"
    ser.write(f"TXT|{state}|{screen}\n".encode("utf-8"))
    ser.flush()
    _log(f"  → TXT|{state}|{screen[:40]}…")


def drain_serial(ser: serial.Serial, timeout: float = 0.15) -> list[str]:
    """读掉串口缓冲里的回显/状态行，避免干扰下一轮。"""
    lines: list[str] = []
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if ser.in_waiting:
            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    lines.append(line)
                    _log(f"  M5: {line}")
        else:
            time.sleep(0.01)
    # 超时后再清一次残留
    while ser.in_waiting:
        raw = ser.readline()
        if raw:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                lines.append(line)
                _log(f"  M5: {line}")
    return lines


def wait_after_txt(ser: serial.Serial, timeout: float = 4.0) -> None:
    """
    发完 TXT 后等 M5 处理完屏幕更新，再发 PCM。
    典型回显: State: … / Text: …
    """
    deadline = time.perf_counter() + timeout
    saw_ack = False
    while time.perf_counter() < deadline:
        if ser.in_waiting:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                _log(f"  M5: {line}")
            if line.startswith(("State:", "Text:", "TXT|")):
                saw_ack = True
        elif saw_ack:
            break
        else:
            time.sleep(0.02)
    time.sleep(0.12)


def wait_playback_done(
    ser: serial.Serial,
    pcm_bytes: int,
    sample_rate: int = 16000,
    extra_margin: float = 0.6,
    signal_timeout: float = 120.0,
) -> None:
    """
    等待 M5 播完当前 PCM。
    优先等设备上报 PCM DONE；否则按音频时长估算阻塞。
    """
    estimated = pcm_bytes / (sample_rate * 2) + extra_margin
    deadline = time.perf_counter() + max(estimated, 0.5)
    signal_deadline = time.perf_counter() + signal_timeout
    got_signal = False

    while time.perf_counter() < signal_deadline:
        if ser.in_waiting:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                _log(f"  M5: {line}")
            if line in PLAYBACK_DONE_MARKERS:
                got_signal = True
                break
        elif time.perf_counter() >= deadline:
            break
        else:
            time.sleep(0.02)

    if not got_signal:
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            _log(f"  未收到播放完成信号，按音频时长等待 {remaining:.1f}s")
            time.sleep(remaining)


def pick_animation_state(reply: str) -> str:
    angry_words = ["滚", "扣", "废物", "不准", "达标", "赶紧", "加班", "绩效"]
    for w in angry_words:
        if w in reply:
            return "idle"
    return "leave"
