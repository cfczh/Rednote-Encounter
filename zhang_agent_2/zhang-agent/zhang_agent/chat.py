from openai import OpenAI

from zhang_agent.config import (
    openai_api_key,
    openai_base_url,
    openai_model,
    skill_dir,
)
from zhang_agent.prompt import build_system_prompt
from zhang_agent.sessions import Session


class PersonaAgent:
    def __init__(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt
        kwargs: dict = {"api_key": openai_api_key()}
        base = openai_base_url()
        if base:
            kwargs["base_url"] = base
        self._client = OpenAI(**kwargs)
        self._model = openai_model()

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def reply(self, session: Session, user_message: str) -> str:
        session.messages.append({"role": "user", "content": user_message})

        api_messages = [
            {"role": "system", "content": self._system_prompt},
            *session.messages,
        ]

        response = self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=0.85,
            max_tokens=1024,
        )

        assistant = (response.choices[0].message.content or "").strip()
        session.messages.append({"role": "assistant", "content": assistant})
        return assistant


class ZhangBossAgent(PersonaAgent):
    def __init__(self) -> None:
        super().__init__(build_system_prompt(skill_dir()))
