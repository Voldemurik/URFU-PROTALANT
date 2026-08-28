"""Формат оценочного набора (JSONL — по одному JSON-объекту на строку).

Пример записи::

    {"id": "q01",
     "question": "Какой код ошибки означает перегрев шпинделя?",
     "reference_answer": "Перегреву шпинделя соответствует код E12.",
     "relevant_docs": ["fs400_manual.md"],
     "must_include": ["E12"],
     "answerable": true,
     "tags": ["коды ошибок"]}

Поле ``answerable: false`` помечает вопросы-ловушки, ответа на которые в
документации нет: правильное поведение — отказ, а не выдумка.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class EvalSample:
    id: str
    question: str
    reference_answer: str = ""
    relevant_docs: list[str] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    answerable: bool = True
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalSample:
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            log.warning("Запись %s: неизвестные поля %s игнорируются", data.get("id", "?"), sorted(unknown))
        payload = {k: v for k, v in data.items() if k in known}
        if "question" not in payload:
            raise ValueError(f"В записи нет поля question: {data}")
        payload.setdefault("id", payload["question"][:40])
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_dataset(path: str | Path) -> list[EvalSample]:
    samples: list[EvalSample] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            samples.append(EvalSample.from_dict(json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: некорректный JSON — {exc}") from exc
    return samples


def save_dataset(samples: list[EvalSample], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as fh:
        for sample in samples:
            fh.write(json.dumps(sample.to_dict(), ensure_ascii=False) + "\n")
