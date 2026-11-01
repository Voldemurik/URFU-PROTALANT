"""Повторные попытки эмбеддингов при временных сбоях runner'а Ollama.

EOF на /tokenize означает падение внутреннего процесса Ollama; следующий
запрос поднимает его заново. Проверяем, что часовая индексация не обрывается
из-за одного такого сбоя.
"""

from __future__ import annotations

import numpy as np
import pytest

from techdoc_assistant.config import EmbeddingConfig
from techdoc_assistant.embeddings import OllamaEmbedder
from techdoc_assistant.ollama_client import OllamaError


class FlakyClient:
    """Клиент-заглушка: первые `failures` вызовов падают, дальше работают."""

    def __init__(self, failures: int = 0, fail_always: bool = False):
        self.failures = failures
        self.fail_always = fail_always
        self.calls: list[list[str]] = []

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail_always or self.failures > 0:
            self.failures -= 1
            raise OllamaError('Ollama вернула 400: {"error":"tokenize: EOF"}')
        return [[1.0, 0.0] for _ in texts]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Паузы backoff в тестах не нужны."""
    monkeypatch.setattr("techdoc_assistant.embeddings.time.sleep", lambda _: None)


def make_embedder(client, batch_size: int = 4) -> OllamaEmbedder:
    return OllamaEmbedder(client, EmbeddingConfig(model="test", batch_size=batch_size))


def test_temporary_failure_is_retried():
    client = FlakyClient(failures=1)

    matrix = make_embedder(client).embed(["раз", "два"])

    assert matrix.shape == (2, 2)
    assert len(client.calls) == 2  # первая попытка упала, вторая успешна


def test_failed_batch_is_split_into_single_texts():
    # Пакет из двух текстов падает всегда, одиночные тексты проходят.
    class BatchHatingClient(FlakyClient):
        def embed(self, model, texts):
            if len(texts) > 1:
                raise OllamaError("EOF")
            return super().embed(model, texts)

    client = BatchHatingClient()

    matrix = make_embedder(client, batch_size=2).embed(["раз", "два"])

    assert matrix.shape == (2, 2)
    assert [len(call) for call in client.calls][-2:] == [1, 1]


def test_persistent_failure_reports_text_preview():
    client = FlakyClient(fail_always=True)

    with pytest.raises(OllamaError, match="ядовитый фрагмент") as excinfo:
        make_embedder(client).embed(["ядовитый фрагмент"])

    assert "3 попыток" in str(excinfo.value)
    # Три попытки на пакет из одного текста, без дробления.
    assert len(client.calls) == 3


def test_successful_run_sets_dim_and_normalizes():
    client = FlakyClient()
    embedder = make_embedder(client)

    matrix = embedder.embed(["раз", "два"])

    assert embedder.dim == 2
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1.0)
