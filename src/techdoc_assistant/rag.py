"""RAG-пайплайн: индексация документов и ответы на вопросы со ссылками.

Схема работы::

    документы ──► чанки ──► эмбеддинги ──► VectorStore (+ BM25)
                                                   │
    вопрос ──► HybridRetriever ──► top-k чанков ──► промпт ──► LLM ──► Answer
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from techdoc_assistant.chunking import split_documents
from techdoc_assistant.config import Config
from techdoc_assistant.documents import Chunk, Document
from techdoc_assistant.embeddings import Embedder, OllamaEmbedder
from techdoc_assistant.llm import LLM, OllamaLLM
from techdoc_assistant.loaders import load_documents
from techdoc_assistant.ollama_client import OllamaClient
from techdoc_assistant.prompts import NO_ANSWER_MARKER, SYSTEM_PROMPT, build_user_prompt, is_refusal
from techdoc_assistant.retriever import Hit, HybridRetriever
from techdoc_assistant.vector_store import VectorStore

log = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[(\d{1,3})\]")


@dataclass
class Citation:
    number: int
    chunk: Chunk

    @property
    def doc_id(self) -> str:
        return self.chunk.doc_id


@dataclass
class Answer:
    question: str
    text: str
    hits: list[Hit]
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False  # модель честно сказала, что ответа в документации нет
    latency_s: float = 0.0

    @property
    def context_chunks(self) -> list[Chunk]:
        return [hit.chunk for hit in self.hits]

    @property
    def cited_doc_ids(self) -> list[str]:
        seen: list[str] = []
        for citation in self.citations:
            if citation.doc_id not in seen:
                seen.append(citation.doc_id)
        return seen

    def render(self) -> str:
        """Текст ответа плюс список источников — для консоли."""
        lines = [self.text.strip(), ""]
        if self.citations:
            lines.append("Источники:")
            for citation in self.citations:
                lines.append(f"  [{citation.number}] {citation.chunk.label()} — {citation.chunk.source}")
        return "\n".join(lines).rstrip()


class IndexMismatchError(RuntimeError):
    """Индекс построен другим эмбеддером — векторы несовместимы."""


class RagPipeline:
    """Связывает загрузку, индексацию, поиск и генерацию."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        embedder: Embedder | None = None,
        llm: LLM | None = None,
        store: VectorStore | None = None,
    ):
        self.config = config or Config()
        client: OllamaClient | None = None
        if embedder is None or llm is None:
            client = OllamaClient(self.config.ollama)
        self.embedder: Embedder = embedder or OllamaEmbedder(client, self.config.embeddings)  # type: ignore[arg-type]
        self.llm: LLM = llm or OllamaLLM(client, self.config.llm)  # type: ignore[arg-type]
        self.store = store or VectorStore(embedder_name=self.embedder.name)
        self.retriever = HybridRetriever(self.store, self.embedder, self.config.retrieval)

    # ------------------------------------------------------------- indexing
    def ingest_documents(self, documents: Iterable[Document]) -> int:
        """Разбить документы на чанки, посчитать эмбеддинги и добавить в индекс."""
        chunks = split_documents(documents, self.config.chunking)
        if not chunks:
            return 0
        started = time.perf_counter()
        # Индексируем текст вместе с названием документа и раздела: вопросы часто
        # содержат имя оборудования или раздела, которых нет в самом фрагменте.
        vectors = self.embedder.embed([c.index_text() for c in chunks])
        self.store.embedder_name = self.embedder.name
        self.store.add(chunks, vectors)
        self.retriever.refresh()
        log.info(
            "Проиндексировано %d фрагментов за %.1f с (бэкенд: %s)",
            len(chunks),
            time.perf_counter() - started,
            self.store.backend,
        )
        return len(chunks)

    def ingest_paths(self, paths: Iterable[str | Path]) -> int:
        documents = load_documents(paths)
        log.info("Загружено документов: %d", len(documents))
        return self.ingest_documents(documents)

    def save_index(self, directory: str | Path | None = None) -> Path:
        directory = Path(directory or self.config.index_dir)
        self.store.save(directory)
        return directory

    def load_index(self, directory: str | Path | None = None) -> int:
        directory = Path(directory or self.config.index_dir)
        store = VectorStore.load(directory)
        if store.embedder_name and store.embedder_name != self.embedder.name:
            raise IndexMismatchError(
                f"Индекс в {directory} построен эмбеддером «{store.embedder_name}», "
                f"а сейчас используется «{self.embedder.name}». Переиндексируйте документы "
                "(`techdoc ingest …`) той же моделью или укажите другой каталог через --index-dir."
            )
        self.store = store
        self.retriever = HybridRetriever(self.store, self.embedder, self.config.retrieval)
        return len(self.store)

    # ---------------------------------------------------------------- query
    def retrieve(self, question: str, top_k: int | None = None) -> list[Hit]:
        return self.retriever.retrieve(question, top_k)

    def ask(self, question: str, top_k: int | None = None) -> Answer:
        started = time.perf_counter()
        question = question.strip()
        hits = self.retrieve(question, top_k) if question else []
        if not hits:
            return Answer(
                question=question,
                text=NO_ANSWER_MARKER,
                hits=[],
                refused=True,
                latency_s=time.perf_counter() - started,
            )
        chunks = [hit.chunk for hit in hits]
        raw = self.llm.generate(SYSTEM_PROMPT, build_user_prompt(question, chunks))
        text = raw.strip()
        refused = is_refusal(text)
        citations = [] if refused else _extract_citations(text, chunks)
        return Answer(
            question=question,
            text=text,
            hits=hits,
            citations=citations,
            refused=refused,
            latency_s=time.perf_counter() - started,
        )


def _extract_citations(text: str, chunks: list[Chunk]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[int] = set()
    for match in _CITATION_RE.finditer(text):
        number = int(match.group(1))
        if number in seen or not (1 <= number <= len(chunks)):
            continue
        seen.add(number)
        citations.append(Citation(number=number, chunk=chunks[number - 1]))
    return citations
