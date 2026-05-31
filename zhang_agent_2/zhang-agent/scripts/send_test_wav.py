import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zhang_agent.m5_audio import M5SerialAudioOutput
from zhang_agent.voice import VocalCNSpeaker


def main() -> None:
    parser = argparse.ArgumentParser(description="发送一段测试语音到单台 M5Stack")
    parser.add_argument("port", help="M5Stack USB 串口，例如 /dev/cu.usbmodemXXXX")
    parser.add_argument("--text", default="你好，我是测试语音。", help="测试文本")
    args = parser.parse_args()

    wav_path = VocalCNSpeaker().synthesize(args.text)
    size = Path(wav_path).stat().st_size
    print(f"WAV: {wav_path} ({size} bytes)")
    print("Sending with ZAV1 header + per-chunk ACK handshake...")

    output = M5SerialAudioOutput(args.port, label=args.port)
    try:
        output.play(wav_path)
    finally:
        output.close()
    print("DONE")


if __name__ == "__main__":
    main()
