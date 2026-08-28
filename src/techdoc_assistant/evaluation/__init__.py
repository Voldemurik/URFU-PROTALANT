"""Собственная система оценки качества ответов.

Оценивается не только «похож ли ответ на эталон», а весь пайплайн по слоям:

* **поиск** — нашлись ли нужные документы (recall@k, hit rate, MRR);
* **ответ** — точность и полнота (token-F1, покрытие обязательных фактов);
* **ссылки** — цитирует ли модель именно те источники (precision/recall);
* **галлюцинации** — отказ отвечать на вопросы вне документации, доля
  утверждений без опоры на контекст (LLM-судья).

Подробнее — в ``docs/evaluation.md``.
"""

from techdoc_assistant.evaluation.dataset import EvalSample, load_dataset, save_dataset
from techdoc_assistant.evaluation.judge import JudgeVerdict, LLMJudge
from techdoc_assistant.evaluation.runner import EvalReport, SampleResult, evaluate

__all__ = [
    "EvalReport",
    "EvalSample",
    "JudgeVerdict",
    "LLMJudge",
    "SampleResult",
    "evaluate",
    "load_dataset",
    "save_dataset",
]
