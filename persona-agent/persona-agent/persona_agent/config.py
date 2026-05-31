import os
from glob import glob
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(_PKG_ROOT / ".env")


def project_root() -> Path:
    return _PKG_ROOT


def resolve_project_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (_PKG_ROOT / path).resolve()
    return path.resolve()


def skills_dir() -> Path:
    raw = os.getenv(
        "PERSONA_SKILLS_DIR",
        os.getenv("ZHANG_SKILL_DIR", "skills"),  # 兼容旧变量
    )
    return resolve_project_path(raw)


def default_persona_id() -> str:
    raw = os.getenv("DEFAULT_PERSONA_ID", "").strip()
    if raw:
        return raw
    legacy = os.getenv("ZHANG_SKILL_DIR", "").strip()
    if legacy:
        return Path(legacy).name.replace("张总", "zhang_zong")
    return "zhang_zong"


def duel_persona_a_id() -> str:
    return os.getenv("DUEL_PERSONA_A", default_persona_id()).strip()


def duel_persona_b_id() -> str:
    legacy = os.getenv("OTHER_AGENT_PATH", "skills/xiao_hong")
    default_b = Path(legacy).name if legacy else "xiao_hong"
    return os.getenv("DUEL_PERSONA_B", default_b).strip()


def openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "未设置 OPENAI_API_KEY。请复制 .env.example 为 .env 并填入密钥。"
        )
    return key


def openai_base_url() -> str | None:
    url = os.getenv("OPENAI_BASE_URL", "").strip()
    return url or None


def openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def server_host() -> str:
    return os.getenv(
        "AGENT_HOST",
        os.getenv("ZHANG_AGENT_HOST", "127.0.0.1"),
    ).strip()


def server_port() -> int:
    return int(os.getenv("AGENT_PORT", os.getenv("ZHANG_AGENT_PORT", "8765")))


def serial_port() -> str:
    explicit = os.getenv("SERIAL_PORT", "").strip()
    if explicit:
        return explicit

    ports = sorted(
        glob("/dev/cu.usbmodem*") +
        glob("/dev/cu.wchusbserial*") +
        glob("/dev/cu.usbserial*")
    )
    if ports:
        return ports[0]

    return "/dev/cu.usbmodem1101"


def serial_baudrate() -> int:
    return int(os.getenv("SERIAL_BAUDRATE", "2000000"))


def agent_api_url() -> str:
    return os.getenv(
        "AGENT_API_URL",
        os.getenv("ZHANG_API_URL", f"http://{server_host()}:{server_port()}/v1/chat"),
    ).strip()
