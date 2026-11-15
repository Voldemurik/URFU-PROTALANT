import builtins

import numpy as np
import pytest

from techdoc_assistant.config import Config, RetrievalConfig
from techdoc_assistant.embeddings import HashingEmbedder, l2_normalize
from techdoc_assistant.lexical import BM25Index, TokenNormalizer, tokenize
from techdoc_assistant.vector_store import VectorStore


def test_tokenize_lowercases_and_folds_yo():
    assert tokenize("Ёмкость бака СОЖ — 120 л") == ["емкость", "бака", "сож", "120", "л"]


def test_bm25_finds_exact_error_code():
    texts = [
        "E12 — перегрев шпинделя, температура выше 70 градусов",
        "Ежедневно очищать рабочую зону от стружки",
        "E21 — потеря связи с контроллером",
    ]
    index = BM25Index().build(texts)
    results = index.search("что делать при ошибке E12")
    assert results and results[0][0] == 0


def test_bm25_empty_query_returns_nothing():
    index = BM25Index().build(["текст"])
    assert index.search("") == []
    assert index.search("!!!") == []


def test_token_normalizer_preserves_current_behavior():
    text = "Ёмкость бака СОЖ — 120 л"
    assert TokenNormalizer("token").tokenize(text) == tokenize(text)


def test_lemma_normalizer_matches_russian_word_forms():
    normalizer = TokenNormalizer("lemma")
    assert normalizer.tokenize("Перегревом шпинделя") == ["перегрев", "шпиндель"]
    assert normalizer.tokenize("Станки работают") == ["станок", "работать"]


def test_lemma_normalizer_preserves_technical_tokens():
    normalizer = TokenNormalizer("lemma")
    text = "E12 PREEMPT_RT CR2032 G01 120 0.5 СОЖ linuxcnc-uspace"
    assert normalizer.tokenize(text) == [
        "e12",
        "preempt_rt",
        "cr2032",
        "g01",
        "120",
        "0",
        "5",
        "сож",
        "linuxcnc",
        "uspace",
    ]


def test_bm25_lemma_finds_document_with_different_word_forms():
    texts = [
        "При перегреве шпинделя остановите станок",
        "Ежедневно очищайте рабочую зону от стружки",
    ]
    query = "Перегрев шпиндель"
    assert BM25Index(normalization="token").build(texts).search(query) == []
    lemma = BM25Index(normalization="lemma").build(texts)
    results = lemma.search(query)
    assert results and results[0][0] == 0
    assert lemma.search(query) == results


def test_invalid_bm25_normalization_is_rejected():
    with pytest.raises(ValueError, match="lemma.*token"):
        TokenNormalizer("stem")
    with pytest.raises(ValueError, match="bm25_normalization"):
        RetrievalConfig(bm25_normalization="stem")


def test_lemma_mode_is_loaded_from_config():
    cfg = Config.from_dict({"retrieval": {"bm25_normalization": "lemma"}})
    assert cfg.retrieval.bm25_normalization == "lemma"


def test_missing_morphology_dependency_has_actionable_error(monkeypatch):
    original_import = builtins.__import__

    def import_without_pymorphy(name, *args, **kwargs):
        if name == "pymorphy3":
            raise ModuleNotFoundError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_pymorphy)
    with pytest.raises(ModuleNotFoundError, match=r"techdoc-assistant\[morphology\]"):
        TokenNormalizer("lemma")


def test_hashing_embedder_is_deterministic_and_normalized():
    embedder = HashingEmbedder(dim=128)
    a = embedder.embed(["Перегрев шпинделя"])
    b = embedder.embed(["Перегрев шпинделя"])
    assert np.allclose(a, b)
    assert np.allclose(np.linalg.norm(a, axis=1), 1.0)


def test_hashing_embedder_similarity_reflects_lexical_overlap():
    embedder = HashingEmbedder()
    vectors = embedder.embed(["перегрев шпинделя станка", "шпиндель перегрелся", "смазка конвейера"])
    close = float(vectors[0] @ vectors[1])
    far = float(vectors[0] @ vectors[2])
    assert close > far


def test_vector_store_search_and_roundtrip(tmp_path, sample_documents):
    from techdoc_assistant.chunking import split_documents

    chunks = split_documents(sample_documents)
    embedder = HashingEmbedder()
    store = VectorStore()
    store.add(chunks, embedder.embed([c.text for c in chunks]))
    assert len(store) == len(chunks)

    query = embedder.embed(["перегрев шпинделя E12"])[0]
    hits = store.search(query, top_k=3)
    assert len(hits) == 3
    assert hits[0][1] >= hits[1][1] >= hits[2][1]
    assert any("E12" in store.chunks[i].text for i, _ in hits)

    store.save(tmp_path)
    loaded = VectorStore.load(tmp_path)
    assert len(loaded) == len(store)
    assert loaded.chunks[0].chunk_id == store.chunks[0].chunk_id
    assert loaded.search(query, top_k=1)[0][0] == hits[0][0]


def test_vector_store_numpy_matches_faiss_ordering():
    rng = np.random.default_rng(0)
    vectors = l2_normalize(rng.normal(size=(50, 16)))
    from techdoc_assistant.documents import Chunk

    chunks = [Chunk(chunk_id=str(i), doc_id="d", source="d", text=str(i), position=i) for i in range(50)]
    store = VectorStore()
    store.add(chunks, vectors)
    query = l2_normalize(rng.normal(size=(1, 16)))[0]
    expected = np.argsort(-(vectors @ query))[:5].tolist()
    got = [i for i, _ in store.search(query, top_k=5)]
    assert got == expected


def test_hybrid_retriever_prefers_relevant_document(offline_pipeline):
    hits = offline_pipeline.retrieve("Какой код ошибки означает перегрев шпинделя?", top_k=3)
    assert hits
    assert hits[0].chunk.doc_id == "fs400_rukovodstvo_po_ekspluatacii.md"
    # Фрагмент с кодом E12 должен быть среди первых трёх — BM25 «вытягивает» точный код.
    assert any("E12" in hit.chunk.text for hit in hits)
    assert all(hit.dense_rank is not None or hit.lexical_rank is not None for hit in hits)


def test_hybrid_refresh_preserves_lemma_mode(offline_pipeline):
    offline_pipeline.config.retrieval.bm25_normalization = "lemma"
    offline_pipeline.retriever.refresh()
    assert offline_pipeline.retriever.bm25.normalization == "lemma"
    hits = offline_pipeline.retrieve("Перегрев шпиндель", top_k=3)
    assert any(
        hit.chunk.doc_id == "fs400_rukovodstvo_po_ekspluatacii.md" and hit.lexical_rank is not None
        for hit in hits
    )
