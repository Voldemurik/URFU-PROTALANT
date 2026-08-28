import numpy as np

from techdoc_assistant.embeddings import HashingEmbedder, l2_normalize
from techdoc_assistant.lexical import BM25Index, tokenize
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
