"""LLM-судья: оценка обоснованности и полноты ответа второй моделью.

Подход «LLM-as-a-judge»: модель-эксперт получает вопрос, контекст, эталон
и ответ ассистента и возвращает структурированную оценку. Судья может быть
той же локальной моделью, что и ассистент, но лучше — более крупной.
Результат парсится устойчиво к «шуму» вокруг JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from techdoc_assistant.documents import Chunk
from techdoc_assistant.llm import LLM
from techdoc_assistant.prompts import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE, format_context

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class JudgeVerdict:
    faithfulness: float  # 0..1 — доля подтверждённых контекстом утверждений
    completeness: float  # 0..1 — покрытие эталонного ответа
    unsupported_claims: list[str] = field(default_factory=list)
    raw: str = ""
    parsed: bool = True

    @property
    def hallucination(self) -> float:
        return max(0.0, 1.0 - self.faithfulness)


class LLMJudge:
    def __init__(self, llm: LLM):
        self.llm = llm

    def judge(self, question: str, chunks: list[Chunk], reference: str, answer: str) -> JudgeVerdict:
        prompt = JUDGE_USER_TEMPLATE.format(
            question=question,
            context=format_context(chunks) or "(пусто)",
            reference=reference or "(не задан)",
            answer=answer,
        )
        raw = self.llm.generate(JUDGE_SYSTEM_PROMPT, prompt, json_mode=True)
        return parse_verdict(raw)


def parse_verdict(raw: str) -> JudgeVerdict:
    match = _JSON_RE.search(raw or "")
    if not match:
        return JudgeVerdict(faithfulness=0.0, completeness=0.0, raw=raw, parsed=False)
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return JudgeVerdict(faithfulness=0.0, completeness=0.0, raw=raw, parsed=False)
    claims = data.get("unsupported_claims") or []
    if not isinstance(claims, list):
        claims = [str(claims)]
    return JudgeVerdict(
        faithfulness=_clamp(data.get("faithfulness", 0.0)),
        completeness=_clamp(data.get("completeness", 0.0)),
        unsupported_claims=[str(c) for c in claims],
        raw=raw,
        parsed=True,
    )


def _clamp(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, number))
