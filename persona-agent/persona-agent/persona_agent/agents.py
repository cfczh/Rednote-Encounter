from __future__ import annotations

from persona_agent.chat import PersonaAgent
from persona_agent.prompt import build_persona_prompt
from persona_agent.registry import PersonaRegistry


class AgentPool:
    def __init__(self, registry: PersonaRegistry | None = None) -> None:
        self._registry = registry or PersonaRegistry()
        self._agents: dict[str, PersonaAgent] = {}

    @property
    def registry(self) -> PersonaRegistry:
        return self._registry

    def get(self, persona_id: str) -> PersonaAgent:
        if persona_id not in self._agents:
            path = self._registry.resolve_path(persona_id)
            self._agents[persona_id] = PersonaAgent(
                build_persona_prompt(path),
                persona_id=persona_id,
            )
        return self._agents[persona_id]

    def invalidate(self, persona_id: str | None = None) -> None:
        if persona_id is None:
            self._agents.clear()
            self._registry.refresh()
        else:
            self._agents.pop(persona_id, None)
