import sys

from zhang_agent.chat import ZhangBossAgent
from zhang_agent.config import skill_dir
from zhang_agent.sessions import Session


def run_cli() -> None:
    root = skill_dir()
    if not (root / "assets" / "persona.md").exists():
        print(f"错误：找不到张总 Skill：{root}", file=sys.stderr)
        sys.exit(1)

    print("张总 Agent（终端模式）")
    print(f"Skill: {root}")
    print("输入内容对话，/quit 退出，/reset 清空本轮记忆\n")

    agent = ZhangBossAgent()
    session = Session(id="cli")

    while True:
        try:
            user = input("你 ❯ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        if not user:
            continue
        if user in ("/quit", "/exit", "quit", "exit"):
            print("再见。")
            break
        if user == "/reset":
            session.messages.clear()
            print("（对话已清空）\n")
            continue

        try:
            reply = agent.reply(session, user)
        except Exception as e:
            print(f"\n[错误] {e}\n", file=sys.stderr)
            session.messages.pop()  # 去掉失败的 user 消息
            continue

        print(f"\n张总 ❯ {reply}\n")
