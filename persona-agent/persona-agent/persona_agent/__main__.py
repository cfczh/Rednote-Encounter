import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="persona_agent",
        description="可切换人设的独立对话 Agent",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="启动 HTTP 后台服务")
    sub.add_parser("list", help="列出 skills/ 下可用人设")

    chat = sub.add_parser("chat", help="终端交互（可指定人设）")
    chat.add_argument(
        "--persona",
        metavar="PERSONA_ID",
        help="人设 ID，默认 DEFAULT_PERSONA_ID",
    )

    bridge = sub.add_parser(
        "bridge",
        help="串口桥接：硬件上报 PERSONA|id 后，用该人设对话",
    )

    duel = sub.add_parser("duel", help="两个人设轮流对话")
    duel.add_argument(
        "--persona-a",
        metavar="ID",
        help="人设 A，默认 DUEL_PERSONA_A / DEFAULT_PERSONA_ID",
    )
    duel.add_argument(
        "--persona-b",
        metavar="ID",
        help="人设 B，默认 DUEL_PERSONA_B",
    )
    duel.add_argument("--rounds", type=int, default=6, help="对话轮数")
    duel.add_argument("--topic", help="开场话题")
    duel.add_argument(
        "--no-hardware",
        action="store_true",
        help="不用串口，仅在终端打印两人对话（测 LLM）",
    )
    duel.add_argument(
        "--hardware-smoke",
        action="store_true",
        help="不调用模型，只验证双 M5 同屏和轮流播放",
    )

    args = parser.parse_args()

    if args.cmd == "serve":
        from persona_agent.server import run_server

        run_server()
    elif args.cmd == "list":
        from persona_agent.registry import PersonaRegistry

        reg = PersonaRegistry()
        for p in reg.list():
            print(f"{p.persona_id:16s} {p.name:8s}  {p.path}")
    elif args.cmd == "chat":
        from persona_agent.cli import run_cli

        run_cli(persona_id=args.persona)
    elif args.cmd == "bridge":
        from persona_agent.bridge import run_bridge

        run_bridge()
    elif args.cmd == "duel":
        from persona_agent.duel import run_duel, run_hardware_smoke

        if args.hardware_smoke:
            run_hardware_smoke()
            return

        run_duel(
            persona_a=args.persona_a,
            persona_b=args.persona_b,
            rounds=args.rounds,
            topic=args.topic,
            use_hardware=not args.no_hardware,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
