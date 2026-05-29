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

    def reply(self, self_peer: "Peer", other_peer: "Peer") -> str:
        prompt_builder = SYSTEM_PROMPTS.get(self_peer.persona)
        if not prompt_builder:
            return f"met {other_peer.persona}"

        relation_key = (self_peer.device_id, other_peer.device_id)
        messages = self._sessions.setdefault(relation_key, [])
        event = (
            f"蓝牙相遇事件：我是 {self_peer.persona}，对方是 {other_peer.persona}；"
            f"我的状态 {self_peer.state_name}，对方状态 {other_peer.state_name}；"
            f"对方带来的特产 {other_peer.gift}；"
            f"RSSI {self_peer.rssi}，距离感 {distance_label(self_peer.rssi)}。"
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


def make_fallback_reply(self_peer: Peer, other_peer: Peer) -> str:
    if self_peer.persona == "xiao_hong":
        if self_peer.rssi >= -58:
            return "那好吧，待一会儿。"
        return "感觉有人靠近了。"
    if self_peer.persona == "zhang_zong":
        return "来了就别磨蹭。"
    return f"met {other_peer.persona}"


async def write_agent_reply(address: str, text: str) -> None:
    from bleak import BleakClient

    async with BleakClient(address, timeout=8.0) as client:
        await client.write_gatt_char(AGENT_COMMAND_CHAR_UUID, text.encode("utf-8"), response=False)


async def main() -> None:
    try:
        from bleak import BleakScanner
    except ImportError:
        print("Missing dependency: pip install bleak")
        return

    peers: dict[int, Peer] = {}
    last_sent: dict[tuple[int, int], float] = {}
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
    print("Scanning for Rednote M5 peers. Press Ctrl+C to stop.")
    while True:
        found = await BleakScanner.discover(timeout=4.0, return_adv=True)
        now = time.time()

        for device, adv in found.values():
            ok, parsed = parse_project_payload(adv.manufacturer_data)
            service_hit = PROJECT_SERVICE_UUID.lower() in [s.lower() for s in adv.service_uuids]
            if not ok and not service_hit:
                continue
            if not ok:
                continue

            peer = Peer(
                address=device.address,
                name=device.name or adv.local_name or "REDNOTE",
                rssi=adv.rssi,
                device_id=parsed["device_id"],
                persona_id=parsed["persona_id"],
                state=parsed["state"],
                gift_id=parsed["gift_id"],
                flags=parsed["flags"],
                counter=parsed["counter"],
                seen_at=now,
            )
            peers[peer.device_id] = peer

        active = [p for p in peers.values() if now - p.seen_at < 12]
        active.sort(key=lambda p: p.rssi, reverse=True)

        print(f"\n[{time.strftime('%H:%M:%S')}] {len(active)} active peer(s):")
        for p in active:
            print(f"  {p.device_id:04X} {p.persona:<12} state={p.state_name:<8} rssi={p.rssi:4d}  {p.name}")

        if len(active) >= 2:
            a, b = active[0], active[1]
            for self_peer, other_peer in ((a, b), (b, a)):
                key = (self_peer.device_id, other_peer.device_id)
                cooldown_left = 25 - (now - last_sent.get(key, 0))
                if cooldown_left > 0:
                    print(f"  Skip {self_peer.device_id:04X}: cooldown {int(cooldown_left)}s left")
                    continue
                if self_peer.state < 3:
                    print(f"  Skip {self_peer.device_id:04X}: state={self_peer.state_name} (need social)")
                    continue
                print(f"  LLM -> {self_peer.device_id:04X}({self_peer.persona}) meets {other_peer.device_id:04X}({other_peer.persona})")
                try:
                    reply = await asyncio.to_thread(brain.reply, self_peer, other_peer)
                except Exception as exc:
                    print(f"  Agent failed, using fallback: {exc}")
                    reply = make_fallback_reply(self_peer, other_peer)
                print(f"  Writing to {self_peer.device_id:04X}: {reply!r}")
                try:
                    await write_agent_reply(self_peer.address, reply)
                    last_sent[key] = now
                except Exception as exc:
                    print(f"  Write failed for {self_peer.device_id:04X}: {exc}")

        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
