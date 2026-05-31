import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="zhang_agent",
        description="张总 — 独立后台对话 Agent",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="启动 HTTP 后台服务")
    sub.add_parser("chat", help="终端交互对话")
    duel = sub.add_parser("duel", help="让张总和另一个 AI 人设相互对话")
    duel.add_argument(
        "--other",
        help="另一个人设 .md 文件或 Skill 目录，默认读取 OTHER_AGENT_PATH",
    )
    duel.add_argument("--name", help="另一个人设的显示名称")
    duel.add_argument("--rounds", type=int, default=6, help="对话轮数，默认 6")
    duel.add_argument(
        "--topic",
        help="开场话题，默认从工厂管理开始",
    )
    duel.add_argument(
        "--voice",
        action="store_true",
        help="用 VocalCN 生成语音并按对话顺序播放",
    )
    duel.add_argument(
        "--voice-output",
        choices=("local", "m5"),
        default="local",
        help="语音输出目标：local 为电脑播放，m5 为两台 USB M5Stack 播放",
    )
    duel.add_argument("--zhang-port", help="张总 M5Stack 的 USB 串口")
    duel.add_argument("--other-port", help="另一个人设 M5Stack 的 USB 串口")
    duel.add_argument(
        "--voice-max-chars",
        type=int,
        help="M5Stack 语音最多播报的字符数，默认 10；不影响文本输出",
    )
    duel.add_argument(
        "--display",
        action="store_true",
        help="同步发送 DUEL 分屏命令到两台 M5Stack（需配合 --zhang-port / --other-port）",
    )

    args = parser.parse_args()

    if args.cmd == "serve":
        from zhang_agent.server import run_server

        run_server()
    elif args.cmd == "chat":
        from zhang_agent.cli import run_cli

        run_cli()
    elif args.cmd == "duel":
        from zhang_agent.duel import run_duel

        run_duel(
            other_path=args.other,
            rounds=args.rounds,
            topic=args.topic,
            other_name=args.name,
            voice=args.voice,
            voice_output=args.voice_output,
            zhang_port=args.zhang_port,
            other_port=args.other_port,
            voice_max_chars=args.voice_max_chars,
            display=args.display,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
