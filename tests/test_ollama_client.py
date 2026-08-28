"""Интеграционный тест HTTP-клиента Ollama на мини-сервере, повторяющем формат API.

Настоящая Ollama в CI недоступна, поэтому проверяем контракт: какие запросы
уходят на /api/embed и /api/chat и как разбираются ответы.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from techdoc_assistant.cli import main
from techdoc_assistant.config import Config, EmbeddingConfig, LLMConfig, OllamaConfig
from techdoc_assistant.embeddings import OllamaEmbedder
from techdoc_assistant.llm import OllamaLLM
from techdoc_assistant.ollama_client import OllamaClient, OllamaError
from techdoc_assistant.rag import RagPipeline

REQUESTS: list[tuple[str, dict]] = []


class FakeOllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # тишина в выводе тестов
        pass

    def _send(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - имя задаёт http.server
        if self.path == "/api/version":
            self._send({"version": "0.test"})
        elif self.path == "/api/tags":
            self._send({"models": [{"name": "bge-m3:latest"}, {"name": "qwen3.5:9b"}]})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        REQUESTS.append((self.path, payload))
        if self.path == "/api/embed":
            texts = payload["input"]
            # Детерминированные «эмбеддинги»: длина текста и число слов.
            vectors = [[float(len(t)), float(len(t.split())), 1.0] for t in texts]
            self._send({"model": payload["model"], "embeddings": vectors})
        elif self.path == "/api/chat":
            user = payload["messages"][-1]["content"]
            answer = "Код перегрева — E12 [1]." if "E12" in user else "Ответ по контексту [1]."
            if payload.get("format") == "json":
                answer = json.dumps({"faithfulness": 1, "completeness": 0.8, "unsupported_claims": []})
            self._send({"model": payload["model"], "message": {"role": "assistant", "content": answer}, "done": True})
        else:
            self._send({"error": "unknown"}, 404)


@pytest.fixture(scope="module")
def fake_ollama():
    server = HTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_client_embed_and_chat_contract(fake_ollama):
    client = OllamaClient(OllamaConfig(host=fake_ollama))
    assert client.is_available()
    assert client.version() == "0.test"
    assert client.has_model("bge-m3") and client.has_model("qwen3.5:9b") and not client.has_model("llama3")

    REQUESTS.clear()
    vectors = client.embed("bge-m3", ["раз два", "три"])
    assert len(vectors) == 2 and len(vectors[0]) == 3
    assert REQUESTS[-1] == ("/api/embed", {"model": "bge-m3", "input": ["раз два", "три"]})

    text = client.chat("qwen3.5:9b", [{"role": "user", "content": "E12?"}], temperature=0.2, num_ctx=4096, max_tokens=64, think=False)
    assert "E12" in text
    path, payload = REQUESTS[-1]
    assert path == "/api/chat"
    assert payload["stream"] is False and payload["think"] is False
    assert payload["options"] == {"temperature": 0.2, "num_ctx": 4096, "num_predict": 64}


def test_embedder_normalizes_and_batches(fake_ollama):
    client = OllamaClient(OllamaConfig(host=fake_ollama))
    embedder = OllamaEmbedder(client, EmbeddingConfig(model="bge-m3", batch_size=2))
    REQUESTS.clear()
    matrix = embedder.embed(["a", "bb", "ccc", "dddd", "eeeee"])
    assert matrix.shape == (5, 3) and embedder.dim == 3
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0)
    assert [len(p["input"]) for _, p in REQUESTS] == [2, 2, 1]


def test_pipeline_end_to_end_over_http(fake_ollama, sample_documents, tmp_path):
    cfg = Config(ollama=OllamaConfig(host=fake_ollama), llm=LLMConfig(model="qwen3.5:9b", think=False))
    cfg.index_dir = tmp_path / "index"
    client = OllamaClient(cfg.ollama)
    pipeline = RagPipeline(cfg, embedder=OllamaEmbedder(client, cfg.embeddings), llm=OllamaLLM(client, cfg.llm))
    assert pipeline.ingest_documents(sample_documents) > 0
    answer = pipeline.ask("Какой код ошибки означает перегрев шпинделя E12?")
    assert "E12" in answer.text and not answer.refused
    assert answer.citations and answer.citations[0].number == 1
    # системный промпт ушёл первым сообщением
    _, payload = next(r for r in reversed(REQUESTS) if r[0] == "/api/chat")
    assert payload["messages"][0]["role"] == "system"
    assert "Контекст:" in payload["messages"][1]["content"]


def test_doctor_reports_ok_with_fake_server(fake_ollama, tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    cfg = Config(ollama=OllamaConfig(host=fake_ollama))
    cfg.index_dir = tmp_path / "no-index"
    cfg.dump(config_path)
    assert main(["doctor", "-c", str(config_path)]) == 0
    out = capsys.readouterr().out
    assert "всё готово" in out and "qwen3.5:9b — есть" in out


def test_connection_error_is_explained():
    client = OllamaClient(OllamaConfig(host="http://127.0.0.1:1", timeout=2))
    assert not client.is_available()
    with pytest.raises(OllamaError, match="ollama serve"):
        client.embed("bge-m3", ["x"])
