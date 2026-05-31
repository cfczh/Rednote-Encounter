"""人设注册表：从 skills/ 目录按 persona_id 解析路径。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from persona_agent.config import skills_dir


@dataclass(frozen=True)
class PersonaInfo:
    persona_id: str
    name: str
    path: Path


class PersonaRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or skills_dir()).resolve()
        self._index: dict[str, PersonaInfo] | None = None

    def _build_index(self) -> dict[str, PersonaInfo]:
        index: dict[str, PersonaInfo] = {}
        if not self._root.is_dir():
            return index

        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if not self._is_valid_persona_dir(entry):
                continue

            meta = self._read_meta(entry)
            persona_id = str(meta.get("slug", "")).strip() or entry.name
            name = str(meta.get("name", "")).strip() or entry.name
            index[persona_id] = PersonaInfo(
                persona_id=persona_id,
                name=name,
                path=entry,
            )
        return index

    @staticmethod
    def _read_meta(path: Path) -> dict:
        meta_file = path / "meta.json"
        if not meta_file.exists():
            return {}
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _is_valid_persona_dir(path: Path) -> bool:
        if (path / "SKILL.md").exists():
            return True
        if any(path.glob("*.md")):
            return True
        assets = path / "assets"
        return assets.is_dir() and any(assets.glob("*.md"))

    def _ensure_index(self) -> dict[str, PersonaInfo]:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def refresh(self) -> None:
        self._index = None

    def list(self) -> list[PersonaInfo]:
        return list(self._ensure_index().values())

    def list_ids(self) -> list[str]:
        return list(self._ensure_index().keys())

    def get(self, persona_id: str) -> PersonaInfo:
        info = self._ensure_index().get(persona_id)
        if info is None:
            available = ", ".join(self.list_ids()) or "(无)"
            raise KeyError(
                f"未知人设 persona_id={persona_id!r}，可用: {available}"
            )
        return info

    def resolve_path(self, persona_id: str) -> Path:
        return self.get(persona_id).path

    def display_name(self, persona_id: str) -> str:
        return self.get(persona_id).name
