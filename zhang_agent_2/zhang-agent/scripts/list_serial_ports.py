import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from serial.tools import list_ports
except ImportError:
    raise SystemExit("缺少 pyserial，请先运行：pip install -r requirements.txt")


for port in list_ports.comports():
    print(f"{port.device}\t{port.description}\t{port.hwid}")
