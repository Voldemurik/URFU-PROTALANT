"""Лексический поиск BM25 на чистом Python.

Векторный поиск хорошо ловит смысл, но плохо — точные обозначения:
артикулы, коды ошибок («E12»), номера пунктов регламента. Для технической
документации это критично, поэтому дополнительно строится классический
индекс BM25, а результаты двух поисков объединяются (см. ``retriever.py``).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Простая токенизация: слова и числа в нижнем регистре, «ё» → «е»."""
    return [t.lower().replace("ё", "е") for t in _TOKEN_RE.findall(text)]


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: list[int] = []
        self.avg_length = 0.0
        self.term_freqs: list[Counter[str]] = []
        self.doc_freq: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------ build
    def build(self, texts: Iterable[str]) -> BM25Index:
        self.doc_lengths, self.term_freqs = [], []
        self.doc_freq = defaultdict(int)
        for text in texts:
            tokens = tokenize(text)
            counts = Counter(tokens)
            self.term_freqs.append(counts)
            self.doc_lengths.append(len(tokens))
            for term in counts:
                self.doc_freq[term] += 1
        self.avg_length = (sum(self.doc_lengths) / len(self.doc_lengths)) if self.doc_lengths else 0.0
        return self

    def __len__(self) -> int:
        return len(self.doc_lengths)

    # ----------------------------------------------------------------- search
    def idf(self, term: str) -> float:
        n = len(self.doc_lengths)
        df = self.doc_freq.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: list[str], index: int) -> float:
        counts = self.term_freqs[index]
        length = self.doc_lengths[index]
        total = 0.0
        for term in query_tokens:
            tf = counts.get(term)
            if not tf:
                continue
            norm = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / (self.avg_length or 1)))
            total += self.idf(term) * norm
        return total

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Список ``(индекс документа, скор)`` по убыванию скора; нулевые скоры отбрасываются."""
        query_tokens = tokenize(query)
        if not query_tokens or not self.doc_lengths:
            return []
        candidates: set[int] = set()
        # Кандидаты — документы, содержащие хотя бы один терм запроса.
        for i, counts in enumerate(self.term_freqs):
            if any(term in counts for term in query_tokens):
                candidates.add(i)
        scored = [(i, self.score(query_tokens, i)) for i in candidates]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]
