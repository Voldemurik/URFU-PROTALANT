"""Модели эмбеддингов.

Интерфейс :class:`Embedder` намеренно минимален — один метод ``embed``.
Это позволяет подменять реализацию: боевая работает через Ollama,
а :class:`HashingEmbedder` — детерминированная и без сети — используется
в тестах и для быстрой проверки пайплайна на машине без GPU.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from techdoc_assistant.config import EmbeddingConfig
from techdoc_assistant.ollama_client import OllamaClient


class Embedder(Protocol):
    name: str  # подпись для проверки совместимости индекса
    dim: int | None

    def embed(self, texts: list[str]) -> np.ndarray:
        """Матрица ``(len(texts), dim)`` L2-нормированных векторов float32."""
        ...


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix[None, :]
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class OllamaEmbedder:
    """Эмбеддинги через локальный сервер Ollama."""

    def __init__(self, client: OllamaClient, cfg: EmbeddingConfig | None = None):
        self.client = client
        self.cfg = cfg or EmbeddingConfig()
        self.dim: int | None = None

    @property
    def name(self) -> str:
        return f"ollama:{self.cfg.model}"

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.cfg.batch_size):
            batch = texts[start : start + self.cfg.batch_size]
            vectors.extend(self.client.embed(self.cfg.model, batch))
        if not vectors:
            return np.zeros((0, self.dim or 0), dtype=np.float32)
        matrix = l2_normalize(np.asarray(vectors, dtype=np.float32))
        self.dim = matrix.shape[1]
        return matrix


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class HashingEmbedder:
    """Детерминированный «эмбеддер» без нейросети.

    Строит мешок слов и символьных триграмм, хэшируя признаки в вектор
    фиксированной размерности (feature hashing). Семантики не понимает,
    но для лексически близких текстов даёт высокую косинусную близость —
    этого достаточно для юнит-тестов и офлайн-демонстрации механики RAG.
    """

    def __init__(self, dim: int = 512):
        self.dim = dim

    @property
    def name(self) -> str:
        return f"hashing:{self.dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "little")
                index = value % self.dim
                sign = 1.0 if (value >> 63) & 1 else -1.0
                matrix[row, index] += sign
        return l2_normalize(matrix)

    @staticmethod
    def _features(text: str) -> list[str]:
        tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
        features = list(tokens)
        for token in tokens:
            # Символьные триграммы сглаживают морфологию русского языка.
            padded = f"_{token}_"
            features.extend(padded[i : i + 3] for i in range(len(padded) - 2))
        return features
