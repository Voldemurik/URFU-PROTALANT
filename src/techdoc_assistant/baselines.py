"""Базовые (baseline) ответчики, с которыми сравнивается LLM.

Любую метрику нужно с чем-то сравнивать. Экстрактивный бейзлайн отвечает
текстом самого релевантного фрагмента — без генерации вообще. Если LLM
не обгоняет его по метрикам, значит, генерация только вредит.
"""

from __future__ import annotations

import re

from techdoc_assistant.prompts import NO_ANSWER_MARKER

_BLOCK_RE = re.compile(r"^\[(\d+)\] Источник: .*?\n(.*?)(?=\n\n\[\d+\] Источник: |\n\nВопрос: )", re.S | re.M)


class ExtractiveLLM:
    """Возвращает текст первого фрагмента контекста со ссылкой [1]."""

    name = "extractive"

    def __init__(self, max_chars: int = 600):
        self.max_chars = max_chars

    def generate(self, system: str, user: str, *, json_mode: bool = False) -> str:
        match = _BLOCK_RE.search(user)
        if not match:
            return NO_ANSWER_MARKER
        text = match.group(2).strip()
        if len(text) > self.max_chars:
            text = text[: self.max_chars].rsplit(" ", 1)[0] + "…"
        return f"{text} [1]"
