"""Модели эмбеддингов.

Интерфейс :class:`Embedder` намеренно минимален — один метод ``embed``.
Это позволяет подменять реализацию: боевая работает через Ollama,
а :class:`HashingEmbedder` — детерминированная и без сети — используется
в тестах и для быстрой проверки пайплайна на машине без GPU.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Protocol

import numpy as np

from techdoc_assistant.config import EmbeddingConfig
from techdoc_assistant.ollama_client import OllamaClient, OllamaError

log = logging.getLogger(__name__)


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

    # Повторные попытки: EOF на /tokenize означает падение внутреннего
    # runner'а Ollama, и следующий запрос обычно поднимает его заново.
    _MAX_ATTEMPTS = 3
    _BACKOFF_S = (2.0, 5.0, 10.0)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        total = len(texts)
        for start in range(0, total, self.cfg.batch_size):
            batch = texts[start : start + self.cfg.batch_size]
            vectors.extend(self._embed_batch(batch))
            done = start + len(batch)
            # Часовой прогон без вывода выглядит как зависание — логируем прогресс.
            if total > 100 and (done % 200 < self.cfg.batch_size or done == total):
                log.info("Эмбеддинги: %d/%d фрагментов", done, total)
        if not vectors:
            return np.zeros((0, self.dim or 0), dtype=np.float32)
        matrix = l2_normalize(np.asarray(vectors, dtype=np.float32))
        self.dim = matrix.shape[1]
        return matrix

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """Эмбеддинги пакета с повторными попытками и дроблением пакета.

        Сбойный пакет из нескольких текстов повторяем по одному тексту: так
        временный сбой runner'а не обрывает часовую индексацию, а «ядовитый»
        текст виден в сообщении об ошибке.
        """
        last_error: OllamaError | None = None
        for attempt in range(self._MAX_ATTEMPTS):
            try:
                return self.client.embed(self.cfg.model, batch)
            except OllamaError as exc:
                last_error = exc
                if attempt < self._MAX_ATTEMPTS - 1:
                    pause = self._BACKOFF_S[attempt]
                    log.warning(
                        "Ollama не ответила на пакет из %d текстов "
                        "(попытка %d/%d): %s. Повтор через %.0f с",
                        len(batch),
                        attempt + 1,
                        self._MAX_ATTEMPTS,
                        exc,
                        pause,
                    )
                    time.sleep(pause)

        if len(batch) > 1:
            log.warning(
                "Пакет из %d текстов не удался после %d попыток — "
                "пробуем по одному тексту",
                len(batch),
                self._MAX_ATTEMPTS,
            )
            vectors: list[list[float]] = []
            for text in batch:
                vectors.extend(self._embed_batch([text]))
            return vectors

        preview = batch[0][:120].replace("\n", " ")
        raise OllamaError(
            "Не удалось получить эмбеддинг после "
            f"{self._MAX_ATTEMPTS} попыток: {last_error}. "
            f"Фрагмент ({len(batch[0])} символов): «{preview}…»"
        ) from last_error


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
