"""Тонкий клиент HTTP API Ollama.

Используется голый ``requests`` вместо SDK: так в проекте нет «магии»,
каждый запрос к модели прозрачен и легко логируется/отлаживается.
"""

from __future__ import annotations

from typing import Any

import requests

from techdoc_assistant.config import OllamaConfig


class OllamaError(RuntimeError):
    """Ошибка взаимодействия с сервером Ollama."""


class OllamaClient:
    def __init__(self, cfg: OllamaConfig | None = None):
        self.cfg = cfg or OllamaConfig()
        self.base_url = self.cfg.host.rstrip("/")
        self._session = requests.Session()

    # ----------------------------------------------------------------- utils
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.post(url, json=payload, timeout=self.cfg.timeout)
        except requests.ConnectionError as exc:
            raise OllamaError(
                f"Не удалось подключиться к Ollama по адресу {self.base_url}. "
                "Убедитесь, что сервер запущен (команда `ollama serve`)."
            ) from exc
        except requests.Timeout as exc:
            raise OllamaError(f"Таймаут запроса к {url} ({self.cfg.timeout} с)") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama вернула {response.status_code}: {response.text[:500]}")
        return response.json()

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(url, timeout=self.cfg.timeout)
        except requests.ConnectionError as exc:
            raise OllamaError(f"Не удалось подключиться к Ollama по адресу {self.base_url}") from exc
        except requests.Timeout as exc:
            raise OllamaError(f"Таймаут запроса к {url} ({self.cfg.timeout} с)") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama вернула {response.status_code}: {response.text[:500]}")
        return response.json()

    # ------------------------------------------------------------------- api
    def is_available(self) -> bool:
        try:
            self._session.get(f"{self.base_url}/api/version", timeout=3)
            return True
        except requests.RequestException:
            return False

    def version(self) -> str:
        return str(self._get("/api/version").get("version", "?"))

    def list_models(self) -> list[str]:
        data = self._get("/api/tags")
        return [m.get("name", "") for m in data.get("models", [])]

    def has_model(self, name: str) -> bool:
        wanted = name if ":" in name else f"{name}:latest"
        return wanted in set(self.list_models())

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """Эмбеддинги для списка текстов (эндпоинт ``/api/embed``)."""
        if not texts:
            return []
        data = self._post("/api/embed", {"model": model, "input": texts})
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(texts):
            raise OllamaError("Ollama вернула неожиданный ответ на запрос эмбеддингов")
        return embeddings

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        num_ctx: int | None = None,
        max_tokens: int | None = None,
        think: bool | None = None,
        json_mode: bool = False,
    ) -> str:
        """Один ход диалога без стриминга; возвращает текст ответа."""
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx:
            options["num_ctx"] = num_ctx
        if max_tokens:
            options["num_predict"] = max_tokens
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        if json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload)
        message = data.get("message") or {}
        return str(message.get("content", "")).strip()
