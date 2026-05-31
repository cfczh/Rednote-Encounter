"""M5SerialBridge — 向板子广播 TXT / DUEL / #ACT 显示命令。

协议（cores3_encounter.ino 串口，115200 baud）：
  DUEL|<left>|<right>|<speaker>|<state>|<text>\\n  — 双人分屏
  TXT|<state>|<text>\\n                             — 单人文字
  #ACT:<action>\\n                                 — 动作指令
"""
import time
from typing import Sequence

BAUD = 115200  # cores3_encounter.ino 默认波特率


class M5SerialBridge:
    """向一台或多台 M5Stack 广播串口显示命令。"""

    def __init__(self, ports: Sequence[str], baud: int = BAUD) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("缺少 pyserial，请先运行：pip install -r requirements.txt") from exc

        self._serials = []
        for p in ports:
            if not p:
                continue
            try:
                s = serial.Serial(p, baudrate=baud, timeout=0.5)
                time.sleep(0.3)
                s.reset_input_buffer()
                self._serials.append(s)
                print(f"[Bridge] 已连接 {p}")
            except Exception as exc:
                print(f"[Bridge] 连接 {p} 失败: {exc}")

    @property
    def connected(self) -> bool:
        return len(self._serials) > 0

    def send_duel(
        self, left: str, right: str, speaker: str, state: str, text: str
    ) -> None:
        """发 DUEL 分屏命令。text 超 22 字截断（固件限制）。"""
        cmd = f"DUEL|{left}|{right}|{speaker}|{state}|{text[:22]}\n"
        self._write(cmd)

    def send_txt(self, state: str, text: str) -> None:
        """发 TXT 单人显示命令。text 超 20 字截断。"""
        cmd = f"TXT|{state}|{text[:20]}\n"
        self._write(cmd)

    def send_act(self, action: str) -> None:
        """发 #ACT: 动作命令，例如 leave。"""
        self._write(f"#ACT:{action}\n")

    def close(self) -> None:
        for s in self._serials:
            try:
                s.close()
            except Exception:
                pass

    def _write(self, cmd: str) -> None:
        data = cmd.encode("utf-8")
        for s in self._serials:
            try:
                s.write(data)
                s.flush()
            except Exception as exc:
                print(f"[Bridge] 写入失败 ({s.port}): {exc}")
