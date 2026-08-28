"""Генеративные модели.

Как и для эмбеддингов, интерфейс сведён к одному методу, чтобы пайплайн и
система оценки не зависели от конкретного движка. Сейчас поддерживается
Ollama; добавить llama.cpp или vLLM — вопрос одного класса.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from techdoc_assistant.config import LLMConfig
from techdoc_assistant.ollama_client import OllamaClient


class LLM(Protocol):
    def generate(self, system: str, user: str, *, json_mode: bool = False) -> str: ...


class OllamaLLM:
    def __init__(self, client: OllamaClient, cfg: LLMConfig | None = None):
        self.client = client
        self.cfg = cfg or LLMConfig()

    def generate(self, system: str, user: str, *, json_mode: bool = False) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self.client.chat(
            self.cfg.model,
            messages,
            temperature=self.cfg.temperature,
            num_ctx=self.cfg.num_ctx,
            max_tokens=self.cfg.max_tokens,
            think=self.cfg.think,
            json_mode=json_mode,
        )


class FakeLLM:
    """Заглушка для тестов: отвечает по заданной функции или фиксированной строкой."""

    def __init__(self, responder: str | Callable[[str, str], str] = "ответ"):
        self.responder = responder
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, user: str, *, json_mode: bool = False) -> str:
        self.calls.append((system, user))
        if callable(self.responder):
            return self.responder(system, user)
        return self.responder
