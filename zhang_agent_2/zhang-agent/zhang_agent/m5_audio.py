import struct
import sys
import time
from pathlib import Path


MAGIC = b"ZAV1"


class M5SerialAudioOutput:
    def __init__(
        self,
        port: str,
        baudrate: int = 921600,
        timeout: float = 90.0,
        label: str = "M5Stack",
        chunk_size: int = 64,
        chunk_delay: float = 0.01,
    ) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("缺少 pyserial，请先运行：pip install -r requirements.txt") from exc

        self.label = label
        self._serial = serial.Serial(port, baudrate=baudrate, timeout=0.2, write_timeout=timeout)
        self._timeout = timeout
        self._chunk_size = chunk_size
        self._chunk_delay = chunk_delay
        time.sleep(1.5)
        self._serial.reset_input_buffer()

    def close(self) -> None:
        self._serial.close()

    def play(self, wav_path: Path) -> None:
        data = wav_path.read_bytes()
        header = MAGIC + struct.pack("<I", len(data))
        self._serial.write(header)
        self._serial.flush()

        status = self._read_status({"SEND"}, allow_error=True)
        if status != "SEND":
            raise RuntimeError(f"{self.label} 未准备接收音频：{status}")

        for index in range(0, len(data), self._chunk_size):
            self._serial.write(data[index : index + self._chunk_size])
            self._serial.flush()
            status = self._read_status({"ACK"}, allow_error=True)
            if status != "ACK":
                raise RuntimeError(f"{self.label} 第 {index // self._chunk_size + 1} 块发送失败：{status}")
            if index == 0 or (index // self._chunk_size + 1) % 100 == 0:
                print(f"[{self.label}] sent {min(index + self._chunk_size, len(data))}/{len(data)} bytes")
            if self._chunk_delay:
                time.sleep(self._chunk_delay)

        status = self._read_status({"DONE"}, allow_error=True)
        if status != "DONE":
            raise RuntimeError(f"{self.label} 播放失败：{status}")

    def _read_status(self, expected: set[str], allow_error: bool = False) -> str:
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            line = self._serial.readline().decode("utf-8", errors="ignore").strip()
            if line in expected:
                return line
            if allow_error and line.startswith("ERR"):
                return line
        return "TIMEOUT"


def play_on_m5_safely(output: M5SerialAudioOutput, wav_path: Path) -> None:
    try:
        output.play(wav_path)
    except Exception as exc:
        print(f"[M5Stack语音跳过] {exc}", file=sys.stderr)
