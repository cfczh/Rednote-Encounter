import sys

from persona_agent.agents import AgentPool
from persona_agent.config import default_persona_id
from persona_agent.registry import PersonaRegistry
from persona_agent.sessions import Session


def run_cli(persona_id: str | None = None) -> None:
    registry = PersonaRegistry()
    pid = persona_id or default_persona_id()

    try:
        info = registry.get(pid)
    except KeyError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    pool = AgentPool(registry)
    agent = pool.get(pid)
    label = info.name

    print(f"Persona Agent（终端模式）— {label} [{pid}]")
    print(f"Skill: {info.path}")
    print("输入内容对话，/quit 退出，/reset 清空本轮记忆")
    print("/personas 列出可用人设，/persona <id> 切换人设\n")

    session = Session(id="cli", persona_id=pid)

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
        if user == "/personas":
            for p in registry.list():
                mark = " ← 当前" if p.persona_id == pid else ""
                print(f"  {p.persona_id:16s} {p.name}{mark}")
            print()
            continue
        if user.startswith("/persona "):
            new_pid = user.split(maxsplit=1)[1].strip()
            try:
                info = registry.get(new_pid)
            except KeyError as e:
                print(f"错误：{e}\n")
                continue
            pid = new_pid
            label = info.name
            agent = pool.get(pid)
            session = Session(id="cli", persona_id=pid)
            print(f"已切换为 {label} [{pid}]\n")
            continue

        try:
            reply = agent.reply(session, user)
        except Exception as e:
            print(f"\n[错误] {e}\n", file=sys.stderr)
            if session.messages and session.messages[-1]["role"] == "user":
                session.messages.pop()
            continue

        print(f"\n{label} ❯ {reply}\n")
