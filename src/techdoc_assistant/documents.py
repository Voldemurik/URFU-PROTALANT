"""Базовые структуры данных: документ и фрагмент (чанк)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Document:
    """Исходный документ целиком."""

    doc_id: str  # стабильный идентификатор: путь относительно корня индексации
    source: str  # полный путь к файлу или иной адрес источника
    text: str
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """Фрагмент документа, единица индексации и цитирования."""

    chunk_id: str  # ``<doc_id>#<порядковый номер>``
    doc_id: str
    source: str
    text: str
    position: int  # порядковый номер внутри документа
    title: str = ""
    section: str = ""  # ближайший заголовок раздела, если удалось определить
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chunk:
        return cls(**data)

    def label(self) -> str:
        """Короткая человекочитаемая подпись для ссылки на источник.

        Если чанку известны страницы PDF, добавляем «(стр. N)» или
        «(стр. N–M)» — по такой ссылке можно открыть документ сразу
        на нужной странице.
        """
        parts = [self.title or self.doc_id]
        if self.section and self.section != self.title:
            parts.append(self.section)
        label = " › ".join(parts)
        page_start = self.metadata.get("page_start")
        page_end = self.metadata.get("page_end")
        if page_start:
            if page_end and page_end != page_start:
                label += f" (стр. {page_start}–{page_end})"
            else:
                label += f" (стр. {page_start})"
        return label

    def index_text(self) -> str:
        """Текст для индексации: заголовок документа и раздела + сам фрагмент.

        Название документа («Руководство ФС-400») и раздела («Коды ошибок»)
        часто встречаются в вопросе, но не в тексте фрагмента — без них поиск
        по названию оборудования или разделу работает заметно хуже.
        """
        head = [p for p in (self.title, self.section) if p]
        if self.section == self.title:
            head = head[:1]
        return "\n".join([*head, self.text]) if head else self.text
