"""Векторное хранилище фрагментов.

Хранит L2-нормированные векторы и метаданные чанков; поиск — по косинусной
близости (скалярное произведение нормированных векторов). Если установлен
``faiss-cpu``, используется ``IndexFlatIP``; иначе — точный поиск через NumPy,
которого для корпуса в десятки тысяч фрагментов более чем достаточно.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from techdoc_assistant.documents import Chunk

try:  # pragma: no cover - наличие faiss зависит от окружения
    import faiss  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    faiss = None


class VectorStore:
    def __init__(self, dim: int | None = None, embedder_name: str = ""):
        self.dim = dim
        self.embedder_name = embedder_name  # каким эмбеддером построен индекс
        self.chunks: list[Chunk] = []
        self._vectors = np.zeros((0, dim or 0), dtype=np.float32)
        self._faiss_index: Any = None

    # ---------------------------------------------------------------- basics
    def __len__(self) -> int:
        return len(self.chunks)

    @property
    def vectors(self) -> np.ndarray:
        return self._vectors

    @property
    def backend(self) -> str:
        return "faiss" if self._faiss_index is not None else "numpy"

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        if len(chunks) != vectors.shape[0]:
            raise ValueError("Число чанков и векторов не совпадает")
        if self.dim is None:
            self.dim = int(vectors.shape[1]) if vectors.size else None
        if self.dim is not None and vectors.size and vectors.shape[1] != self.dim:
            raise ValueError(f"Размерность векторов {vectors.shape[1]} ≠ {self.dim}")
        self.chunks.extend(chunks)
        if self._vectors.size == 0:
            self._vectors = vectors.copy()
        else:
            self._vectors = np.vstack([self._vectors, vectors])
        self._rebuild_faiss()

    def clear(self) -> None:
        self.chunks = []
        self._vectors = np.zeros((0, self.dim or 0), dtype=np.float32)
        self._faiss_index = None

    def _rebuild_faiss(self) -> None:
        if faiss is None or self._vectors.size == 0:
            self._faiss_index = None
            return
        index = faiss.IndexFlatIP(self._vectors.shape[1])
        index.add(np.ascontiguousarray(self._vectors))
        self._faiss_index = index

    # ---------------------------------------------------------------- search
    def search(self, query: np.ndarray, top_k: int = 10) -> list[tuple[int, float]]:
        """``(индекс чанка, косинусная близость)`` по убыванию близости."""
        if not self.chunks:
            return []
        query = np.asarray(query, dtype=np.float32).reshape(1, -1)
        top_k = min(top_k, len(self.chunks))
        if self._faiss_index is not None:
            scores, ids = self._faiss_index.search(np.ascontiguousarray(query), top_k)
            return [(int(i), float(s)) for i, s in zip(ids[0], scores[0], strict=True) if i >= 0]
        scores = self._vectors @ query[0]
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [(int(i), float(scores[i])) for i in order]

    # ------------------------------------------------------------- persistence
    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "vectors.npy", self._vectors)
        with (directory / "chunks.jsonl").open("w", encoding="utf-8") as fh:
            for chunk in self.chunks:
                fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
        meta = {
            "dim": self.dim,
            "count": len(self.chunks),
            "backend": self.backend,
            "embedder": self.embedder_name,
        }
        (directory / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: str | Path) -> VectorStore:
        directory = Path(directory)
        if not (directory / "chunks.jsonl").exists():
            raise FileNotFoundError(
                f"Индекс не найден в {directory}. Сначала выполните `techdoc ingest <документы>`."
            )
        vectors = np.load(directory / "vectors.npy")
        chunks = [
            Chunk.from_dict(json.loads(line))
            for line in (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        embedder_name = ""
        meta_path = directory / "meta.json"
        if meta_path.exists():
            embedder_name = str(json.loads(meta_path.read_text(encoding="utf-8")).get("embedder", ""))
        store = cls(dim=int(vectors.shape[1]) if vectors.size else None, embedder_name=embedder_name)
        store.add(chunks, vectors)
        return store
