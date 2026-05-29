import os
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SKILL = _PKG_ROOT.parent / ".cursor" / "skills" / "张总"

load_dotenv(_PKG_ROOT / ".env")


def skill_dir() -> Path:
    raw = os.getenv("ZHANG_SKILL_DIR", str(_DEFAULT_SKILL))
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (_PKG_ROOT / path).resolve()
    return path


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
    return os.getenv("ZHANG_AGENT_HOST", "127.0.0.1").strip()


def server_port() -> int:
    return int(os.getenv("ZHANG_AGENT_PORT", "8765"))
