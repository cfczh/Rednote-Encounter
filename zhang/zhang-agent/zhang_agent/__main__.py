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

    args = parser.parse_args()

    if args.cmd == "serve":
        from zhang_agent.server import run_server

        run_server()
    elif args.cmd == "chat":
        from zhang_agent.cli import run_cli

        run_cli()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
