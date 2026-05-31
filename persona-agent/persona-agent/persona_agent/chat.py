from openai import OpenAI

from persona_agent.config import openai_api_key, openai_base_url, openai_model
from persona_agent.sessions import Session


class PersonaAgent:
    def __init__(self, system_prompt: str, persona_id: str = "") -> None:
        self._system_prompt = system_prompt
        self.persona_id = persona_id
        kwargs: dict = {"api_key": openai_api_key()}
        base = openai_base_url()
        if base:
            kwargs["base_url"] = base
        self._client = OpenAI(**kwargs)
        self._model = openai_model()

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def model(self) -> str:
        return self._model

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
