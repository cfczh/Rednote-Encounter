import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_SERVICE_UUID = "7f1d2b10-7b6a-4f5d-9a46-202605260001"
AGENT_COMMAND_CHAR_UUID = "7f1d2b11-7b6a-4f5d-9a46-202605260001"
PROJECT_COMPANY_ID = 0xFFFF
ROOT = Path(__file__).resolve().parent
ZHANG_AGENT_ENV = ROOT / "zhang" / "zhang-agent" / ".env"
XIAO_HONG_SKILL = ROOT / "xiao_hong" / "xiao_hong"
ZHANG_ZONG_SKILL = ROOT / "zhang_zong_skill"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PERSONAS = {
    1: "xiao_hong",
    2: "zhang_zong",
}

STATES = {
    0: "idle",
    1: "searching",
    2: "visiting",
    3: "social",
    4: "review",
}

GIFTS = {
    1: "game_snack",
    2: "coffee",
    3: "badge",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_xiao_hong_prompt() -> str:
    skill = read_text(XIAO_HONG_SKILL / "SKILL.md")
    persona = read_text(XIAO_HONG_SKILL / "persona.md")
    memory = read_text(XIAO_HONG_SKILL / "self.md")
    return f"""你是小红。严格保持小红人格，不要跳出角色。
你会收到来自 M5Stack 蓝牙相遇系统的事件，而不是普通聊天。
你只需要生成一句适合显示在 M5 小屏幕上的即时反应。

输出规则：
- 只输出小红会说的一句话，不要解释
- 尽量 10 个中文字以内
- 不要括号、不要舞台说明、不要 markdown
- 保持慢热、委婉、有边界感，不要突然热情

## Skill
{skill}

## Persona
{persona}

## Memory
{memory}
"""


def build_zhang_zong_prompt() -> str:
    skill = read_text(ZHANG_ZONG_SKILL / "SKILL.md")
    persona = read_text(ZHANG_ZONG_SKILL / "assets" / "persona.md")
    management = read_text(ZHANG_ZONG_SKILL / "assets" / "management.md")
    profile = read_text(ZHANG_ZONG_SKILL / "assets" / "profile.md")
    return f"""你是张总。严格保持张总人格，不要跳出角色。
你会收到来自 M5Stack 蓝牙相遇系统的事件，而不是普通聊天。
你只需要生成一句适合显示在 M5 小屏幕上的即时反应。

输出规则：
- 只输出张总会说的一句话，不要解释
- 尽量 10 个中文字以内
- 不要 markdown
- 可以直白、有压迫感，但不要输出长篇训话

## Skill
{skill}

## Persona
{persona}

## Management
{management}

## Profile
{profile}
"""


SYSTEM_PROMPTS = {
    "xiao_hong": build_xiao_hong_prompt,
    "zhang_zong": build_zhang_zong_prompt,
}


class AgentBrain:
    def __init__(self) -> None:
        load_env_file(ZHANG_AGENT_ENV)
        self._client = None
        self._model = os.getenv("OPENAI_MODEL", "deepseek-chat").strip()
        self._sessions: dict[tuple[int, int], list[dict[str, str]]] = {}

    def _ensure_client(self):
        if self._client:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Missing dependency: pip install openai") from exc

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY in environment or zhang/zhang-agent/.env")
        kwargs = {"api_key": api_key}
        base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def reply(self, self_peer: "Peer", other_peer: "Peer",
              affinity: int = 50, mode: str = "gift", turn: int = 1) -> str:
        prompt_builder = SYSTEM_PROMPTS.get(self_peer.persona)
        if not prompt_builder:
            return f"met {other_peer.persona}"

        relation_key = (self_peer.device_id, other_peer.device_id)
        messages = self._sessions.setdefault(relation_key, [])
        mood = "好感不错，可以稍微友好一点" if mode == "gift" else "不太对付，语气更冷或更冲"
        event = (
            f"蓝牙相遇事件：我是 {self_peer.persona}，对方是 {other_peer.persona}；"
            f"我的状态 {self_peer.state_name}，对方状态 {other_peer.state_name}；"
            f"对方带来的特产 {other_peer.gift}；"
            f"RSSI {self_peer.rssi}，距离感 {distance_label(self_peer.rssi)}；"
            f"好感度 {affinity}/100（{mood}）；这是第 {turn} 句。"
            "请给出此刻显示在我 M5 屏幕上的一句话。"
        )
        api_messages = [
            {"role": "system", "content": prompt_builder()},
            *messages[-6:],
            {"role": "user", "content": event},
        ]

        client = self._ensure_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=0.8,
            max_tokens=80,
        )
        text = (response.choices[0].message.content or "").strip()
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > 48:
            text = text[:48]
        messages.append({"role": "user", "content": event})
        messages.append({"role": "assistant", "content": text})
        return text

    def reset_session(self, self_id: int, other_id: int) -> None:
        self._sessions.pop((self_id, other_id), None)


@dataclass
class Peer:
    address: str
    name: str
    rssi: int
    device_id: int
    persona_id: int
    state: int
    gift_id: int
    flags: int
    counter: int
    seen_at: float

    @property
    def persona(self) -> str:
        return PERSONAS.get(self.persona_id, f"persona_{self.persona_id}")

    @property
    def state_name(self) -> str:
        return STATES.get(self.state, f"state_{self.state}")

    @property
    def gift(self) -> str:
        return GIFTS.get(self.gift_id, f"gift_{self.gift_id}")


def distance_label(rssi: int) -> str:
    if rssi >= -58:
        return "很近"
    if rssi >= -68:
        return "靠近"
    return "路过"


def parse_project_payload(manufacturer_data: dict[int, bytes]) -> tuple[bool, dict]:
    payload = manufacturer_data.get(PROJECT_COMPANY_ID)
    if payload and len(payload) >= 9 and payload[0:2] == b"RN":
        data = payload
    else:
        data = None
        for company_id, raw in manufacturer_data.items():
            if company_id == PROJECT_COMPANY_ID and len(raw) >= 9 and raw[0:2] == b"RN":
                data = raw
                break
            if len(raw) >= 11 and raw[0:2] == b"\xff\xff" and raw[2:4] == b"RN":
                data = raw[2:]
                break

    if not data or len(data) < 9:
        return False, {}

    version = data[2]
    if version != 1:
        return False, {}

    flags_counter = data[8]
    return True, {
        "version": version,
        "device_id": data[3] | (data[4] << 8),
        "persona_id": data[5],
        "state": data[6],
        "gift_id": data[7],
        "flags": flags_counter & 0x0F,
        "counter": flags_counter >> 4,
    }


def make_fallback_reply(self_peer: Peer, other_peer: Peer, mode: str = "gift") -> str:
    if self_peer.persona == "xiao_hong":
        if mode == "kick":
            return "你先回吧。"
        return "那好吧，待一会儿。"
    if self_peer.persona == "zhang_zong":
        if mode == "kick":
            return "没空，回去干活。"
        return "来了就别磨蹭。"
    return f"met {other_peer.persona}"


# ======================================================================
# 1. 好感度逻辑 + 相遇动画 2 选一
#    affinity 0-100。>=50 -> 亮特产(gift)，<50 -> 踢人(kick)。
# ======================================================================

AFFINITY_THRESHOLD = 50

# 两个人格之间的基础好感度（无序对）
PAIR_BASE = {
    frozenset({"xiao_hong", "zhang_zong"}): 38,   # 慢热有边界 vs 直接压迫，天然偏低
}
DEFAULT_PAIR_BASE = 50


def favorability(a: Peer, b: Peer, history_bonus: int = 0) -> int:
    """计算 a 与 b 这一对的双人好感度（对称）。"""
    score = PAIR_BASE.get(frozenset({a.persona, b.persona}), DEFAULT_PAIR_BASE)

    # 带了特产加分（双方各自带礼物都算）
    if a.gift_id:
        score += 6
    if b.gift_id:
        score += 6

    # 性格冲突/契合：flags bit0=talkative bit1=slowWarm bit2=boundary
    a_boundary, a_talk = a.flags & 0x04, a.flags & 0x01
    b_boundary, b_talk = b.flags & 0x04, b.flags & 0x01
    if (a_boundary and b_talk) or (b_boundary and a_talk):
        score -= 12      # 有边界感的人遇到话痨，减分
    if a_talk and b_talk:
        score += 6       # 两个话痨聊得来

    score += history_bonus
    return max(0, min(100, score))


def favorability_mode(score: int) -> str:
    return "gift" if score >= AFFINITY_THRESHOLD else "kick"


# ======================================================================
# 2. 设备指令下发（BLE GATT）
#    回复文字 = 纯 UTF-8；动画指令 = "#ACT:<name>"（见 PROTOCOL.md §6）
# ======================================================================

CMD_THINKING = "#ACT:thinking"
CMD_LEAVE = "#ACT:leave"


def cmd_encounter(mode: str) -> str:
    return f"#ACT:encounter_{mode}"      # encounter_gift / encounter_kick


async def send_to_device(address: str, payload: str) -> bool:
    from bleak import BleakClient
    try:
        async with BleakClient(address, timeout=8.0) as client:
            await client.write_gatt_char(
                AGENT_COMMAND_CHAR_UUID, payload.encode("utf-8"), response=False
            )
        return True
    except Exception as exc:
        print(f"  Send failed -> {address}: {exc}")
        return False


# ======================================================================
# 4. WebSocket 服务器（可选，调试 / 未来板子 WiFi 通道）
#    没装 websockets 库时自动跳过，不影响 BLE 主链路。
# ======================================================================

WS_PORT = 8765
WS_CLIENTS: set = set()


async def start_ws_server() -> object:
    try:
        import websockets
    except ImportError:
        print("WebSocket disabled (pip install websockets to enable).")
        return None

    async def handler(ws):
        WS_CLIENTS.add(ws)
        try:
            async for _ in ws:
                pass
        finally:
            WS_CLIENTS.discard(ws)

    server = await websockets.serve(handler, "0.0.0.0", WS_PORT)
    print(f"WebSocket server on ws://0.0.0.0:{WS_PORT}")
    return server


async def ws_broadcast(obj: dict) -> None:
    if not WS_CLIENTS:
        return
    import json
    msg = json.dumps(obj, ensure_ascii=False)
    dead = []
    for ws in list(WS_CLIENTS):
        try:
            await ws.send(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        WS_CLIENTS.discard(ws)


# ======================================================================
# 3. 相遇会话状态机 + 谈话结束判定
# ======================================================================

MAX_TURNS = 4              # 对话句数上限（到达即结束）
PAIR_LOST_AFTER = 12.0     # 对方多久没出现算"离开"（秒）
PAIR_COOLDOWN = 25.0       # 一段相遇结束后，这对设备多久内不再触发


class EncounterSession:
    """一对设备(无序)的一次相遇：encounter -> chatting -> ended。"""

    def __init__(self, a: Peer, b: Peer):
        self.affinity = favorability(a, b)
        self.mode = favorability_mode(self.affinity)
        self.state = "encounter"   # encounter -> chatting -> ended
        self.turns = 0
        self.started = time.time()
        self.ended_at = 0.0


def pair_key(id_a: int, id_b: int) -> tuple[int, int]:
    return (id_a, id_b) if id_a <= id_b else (id_b, id_a)


async def main() -> None:
    try:
        from bleak import BleakScanner
    except ImportError:
        print("Missing dependency: pip install bleak")
        return

    peers: dict[int, Peer] = {}
    sessions: dict[tuple[int, int], EncounterSession] = {}
    brain = AgentBrain()

    persona_files = {
        "xiao_hong": [XIAO_HONG_SKILL / "SKILL.md", XIAO_HONG_SKILL / "persona.md", XIAO_HONG_SKILL / "self.md"],
        "zhang_zong": [ZHANG_ZONG_SKILL / "SKILL.md", ZHANG_ZONG_SKILL / "assets" / "persona.md",
                       ZHANG_ZONG_SKILL / "assets" / "management.md", ZHANG_ZONG_SKILL / "assets" / "profile.md"],
    }
    print("Persona file check:")
    for persona, files in persona_files.items():
        for f in files:
            status = "OK" if f.exists() else "MISSING"
            print(f"  [{status}] {f.relative_to(ROOT)}")

    await start_ws_server()

    # ---- 持续扫描：回调实时更新 peers，去掉每轮 discover 的 4 秒等待 ----
    def detection_callback(device, adv):
        ok, parsed = parse_project_payload(adv.manufacturer_data)
        if not ok:
            return
        peers[parsed["device_id"]] = Peer(
            address=device.address,
            name=device.name or adv.local_name or "REDNOTE",
            rssi=adv.rssi,
            device_id=parsed["device_id"],
            persona_id=parsed["persona_id"],
            state=parsed["state"],
            gift_id=parsed["gift_id"],
            flags=parsed["flags"],
            counter=parsed["counter"],
            seen_at=time.time(),
        )

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    print(f"Continuous scan started. WS on :{WS_PORT}. Ctrl+C to stop.")

    try:
        while True:
            now = time.time()
            active = [p for p in peers.values() if now - p.seen_at < PAIR_LOST_AFTER]
            active.sort(key=lambda p: p.rssi, reverse=True)

            print(f"\n[{time.strftime('%H:%M:%S')}] {len(active)} active peer(s):")
            for p in active:
                print(f"  {p.device_id:04X} {p.persona:<12} state={p.state_name:<8} rssi={p.rssi:4d}  {p.name}")

            if len(active) >= 2:
                a, b = active[0], active[1]
                key = pair_key(a.device_id, b.device_id)
                session = sessions.get(key)
                both_social = a.state >= 3 and b.state >= 3

                # ---------- 新相遇：算好感度 -> 2 选一 ----------
                if session is None or session.state == "ended":
                    cooled = session is None or (now - session.ended_at) > PAIR_COOLDOWN
                    if both_social and cooled:
                        session = EncounterSession(a, b)
                        sessions[key] = session
                        print(f"  ENCOUNTER {a.device_id:04X}<->{b.device_id:04X}  "
                              f"affinity={session.affinity} -> {session.mode.upper()}")
                        await ws_broadcast({"type": "encounter", "a": f"{a.device_id:04X}",
                                            "b": f"{b.device_id:04X}", "affinity": session.affinity,
                                            "mode": session.mode})
                        # 通知两台板子播对应相遇动画
                        await send_to_device(a.address, cmd_encounter(session.mode))
                        await send_to_device(b.address, cmd_encounter(session.mode))
                    elif both_social and not cooled:
                        print(f"  Skip pair: cooldown {int(PAIR_COOLDOWN-(now-session.ended_at))}s")

                # ---------- 相遇动画播完 -> 进入聊天 ----------
                elif session.state == "encounter":
                    session.state = "chatting"

                # ---------- 聊天中：生成对话，或判定结束 ----------
                elif session.state == "chatting":
                    if not both_social or session.turns >= MAX_TURNS:
                        reason = "turns" if session.turns >= MAX_TURNS else "left"
                        print(f"  LEAVE {a.device_id:04X}<->{b.device_id:04X} (reason={reason})")
                        await ws_broadcast({"type": "leave", "a": f"{a.device_id:04X}",
                                            "b": f"{b.device_id:04X}", "reason": reason})
                        await send_to_device(a.address, CMD_LEAVE)
                        await send_to_device(b.address, CMD_LEAVE)
                        brain.reset_session(a.device_id, b.device_id)
                        brain.reset_session(b.device_id, a.device_id)
                        session.state = "ended"
                        session.ended_at = now
                    else:
                        session.turns += 1
                        for self_peer, other_peer in ((a, b), (b, a)):
                            try:
                                reply = await asyncio.to_thread(
                                    brain.reply, self_peer, other_peer,
                                    session.affinity, session.mode, session.turns)
                            except Exception as exc:
                                print(f"  Agent failed, fallback: {exc}")
                                reply = make_fallback_reply(self_peer, other_peer, session.mode)
                            print(f"  [{session.turns}/{MAX_TURNS}] {self_peer.device_id:04X}: {reply!r}")
                            await ws_broadcast({"type": "reply", "device": f"{self_peer.device_id:04X}",
                                                "turn": session.turns, "text": reply})
                            await send_to_device(self_peer.address, reply)

            await asyncio.sleep(0.6)
    finally:
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())
