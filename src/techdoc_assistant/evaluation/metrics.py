"""Метрики качества. Все функции чистые и не зависят от моделей."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Минимальный список стоп-слов: убираем служебные слова, чтобы token-F1
# измерял совпадение по содержательным терминам, а не по предлогам.
STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все", "она",
    "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только", "ее",
    "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда",
    "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до",
    "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя", "их", "чем",
    "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже", "себе", "под", "будет",
    "тогда", "кто", "этот", "того", "потому", "этого", "какой", "совсем", "ним", "здесь",
    "этом", "один", "почти", "мой", "тем", "чтобы", "нее", "были", "куда", "зачем", "всех",
    "можно", "при", "об", "это", "также", "the", "a", "an", "of", "to", "is", "are", "in",
}


def normalize_tokens(text: str, *, drop_stopwords: bool = True) -> list[str]:
    tokens = [t.lower().replace("ё", "е") for t in _TOKEN_RE.findall(text)]
    if drop_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


# ------------------------------------------------------------------ retrieval
def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """Доля релевантных документов, попавших в выдачу."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0
    return len(relevant_set & set(retrieved)) / len(relevant_set)


def hit_rate(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0
    return 1.0 if relevant_set & set(retrieved) else 0.0


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """Обратный ранг первого релевантного документа (Mean Reciprocal Rank для одного запроса)."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant_set:
            return 1.0 / rank
    return 0.0


# --------------------------------------------------------------------- answer
def token_f1(prediction: str, reference: str) -> float:
    """F1 по мультимножествам содержательных токенов (как в SQuAD, но с русскими стоп-словами)."""
    pred = Counter(normalize_tokens(prediction))
    ref = Counter(normalize_tokens(reference))
    if not pred and not ref:
        return 1.0
    if not pred or not ref:
        return 0.0
    common = sum((pred & ref).values())
    if common == 0:
        return 0.0
    precision = common / sum(pred.values())
    recall = common / sum(ref.values())
    return 2 * precision * recall / (precision + recall)


def must_include_coverage(prediction: str, required: Sequence[str]) -> float:
    """Доля обязательных фактов (кодов, чисел, терминов), присутствующих в ответе."""
    if not required:
        return 1.0
    text = _loose(prediction)
    found = sum(1 for item in required if _loose(item) in text)
    return found / len(required)


def _loose(text: str) -> str:
    """Нормализация для нестрогого сравнения: регистр, ё/е, пробелы, запятая/точка в числах."""
    text = text.lower().replace("ё", "е")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ------------------------------------------------------------------ citations
def citation_precision(cited: Sequence[str], relevant: Iterable[str]) -> float:
    """Доля процитированных документов, которые действительно релевантны."""
    if not cited:
        return 0.0
    relevant_set = set(relevant)
    return len([c for c in cited if c in relevant_set]) / len(cited)


def citation_recall(cited: Sequence[str], relevant: Iterable[str]) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0
    return len(relevant_set & set(cited)) / len(relevant_set)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
