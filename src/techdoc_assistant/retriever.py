"""Гибридный поиск: векторный + BM25 с объединением по Reciprocal Rank Fusion.

RRF (Reciprocal Rank Fusion) складывает «обратные ранги» документа в
каждом из списков: ``score = Σ 1 / (k + rank)``. Метод не требует
нормировки несопоставимых скоров (косинус vs BM25) и устойчиво повышает
качество поиска на технических текстах, где важны и смысл, и точные термины.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from techdoc_assistant.config import RetrievalConfig
from techdoc_assistant.documents import Chunk
from techdoc_assistant.embeddings import Embedder
from techdoc_assistant.lexical import BM25Index
from techdoc_assistant.vector_store import VectorStore


@dataclass
class Hit:
    chunk: Chunk
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None
    details: dict[str, float] = field(default_factory=dict)


class HybridRetriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        cfg: RetrievalConfig | None = None,
    ):
        self.store = store
        self.embedder = embedder
        self.cfg = cfg or RetrievalConfig()
        self.bm25 = BM25Index().build(chunk.index_text() for chunk in store.chunks)

    def refresh(self) -> None:
        """Перестроить лексический индекс после добавления чанков в хранилище."""
        self.bm25 = BM25Index().build(chunk.index_text() for chunk in self.store.chunks)

    def retrieve(self, query: str, top_k: int | None = None) -> list[Hit]:
        top_k = top_k or self.cfg.top_k
        if not self.store.chunks:
            return []
        candidates = max(self.cfg.candidates, top_k)

        query_vec = self.embedder.embed([query])[0]
        dense = self.store.search(np.asarray(query_vec), candidates)
        lexical = self.bm25.search(query, candidates) if self.cfg.hybrid else []

        fused: dict[int, Hit] = {}
        for rank, (idx, score) in enumerate(dense, start=1):
            hit = fused.setdefault(idx, Hit(chunk=self.store.chunks[idx], score=0.0))
            hit.dense_rank = rank
            hit.details["dense"] = score
            hit.score += 1.0 / (self.cfg.rrf_k + rank)
        for rank, (idx, score) in enumerate(lexical, start=1):
            hit = fused.setdefault(idx, Hit(chunk=self.store.chunks[idx], score=0.0))
            hit.lexical_rank = rank
            hit.details["bm25"] = score
            hit.score += 1.0 / (self.cfg.rrf_k + rank)

        hits = sorted(fused.values(), key=lambda h: (-h.score, h.chunk.chunk_id))
        if self.cfg.min_score > 0:
            hits = [h for h in hits if h.score >= self.cfg.min_score]
        return hits[:top_k]
