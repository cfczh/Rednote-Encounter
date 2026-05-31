import os
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SKILL = _PKG_ROOT / "skills" / "张总"
_DEFAULT_OTHER_PERSONA = _PKG_ROOT / "skills" / "xiao_hong"

load_dotenv(_PKG_ROOT / ".env")


def skill_dir() -> Path:
    raw = os.getenv("ZHANG_SKILL_DIR", str(_DEFAULT_SKILL))
    return resolve_project_path(raw)


def other_persona_path() -> Path:
    raw = os.getenv("OTHER_AGENT_PATH", str(_DEFAULT_OTHER_PERSONA))
    return resolve_project_path(raw)


def resolve_project_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (_PKG_ROOT / path).resolve()
    return path.resolve()


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


def zhang_device_port() -> str | None:
    port = os.getenv("ZHANG_DEVICE_PORT", "").strip()
    return port or None


def other_device_port() -> str | None:
    port = os.getenv("OTHER_DEVICE_PORT", "").strip()
    return port or None


def server_host() -> str:
    return os.getenv("ZHANG_AGENT_HOST", "127.0.0.1").strip()


def server_port() -> int:
    return int(os.getenv("ZHANG_AGENT_PORT", "8765"))
