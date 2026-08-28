"""Локальный LLM-ассистент по технической документации.

Пакет реализует RAG-пайплайн (Retrieval-Augmented Generation — генерация
ответа с опорой на найденные фрагменты документов), который работает
полностью внутри контура предприятия: документы, индекс и языковая модель
не покидают локальную машину.

Основные точки входа:

* :class:`techdoc_assistant.rag.RagPipeline` — индексация документов и ответы
  на вопросы со ссылками на источники;
* :mod:`techdoc_assistant.evaluation` — собственная система оценки качества
  ответов (полнота поиска, точность ответа, корректность ссылок, доля
  галлюцинаций);
* :mod:`techdoc_assistant.cli` — консольная утилита ``techdoc``.
"""

from techdoc_assistant.config import Config
from techdoc_assistant.rag import Answer, RagPipeline

__all__ = ["Answer", "Config", "RagPipeline", "__version__"]

__version__ = "0.1.0"
