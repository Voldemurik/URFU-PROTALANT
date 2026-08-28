from techdoc_assistant.config import Config
from techdoc_assistant.embeddings import HashingEmbedder
from techdoc_assistant.llm import FakeLLM
from techdoc_assistant.prompts import NO_ANSWER_MARKER, SYSTEM_PROMPT
from techdoc_assistant.rag import RagPipeline


def test_ask_returns_answer_with_citations(offline_pipeline, fake_llm):
    answer = offline_pipeline.ask("Какой код ошибки означает перегрев шпинделя?")
    assert "E12" in answer.text
    assert not answer.refused
    assert [c.number for c in answer.citations] == [1]
    assert answer.cited_doc_ids == ["fs400_rukovodstvo_po_ekspluatacii.md"]
    assert answer.latency_s >= 0
    # Модель получила системный промпт и контекст с нумерованными фрагментами.
    system, user = fake_llm.calls[-1]
    assert system == SYSTEM_PROMPT
    assert "[1] Источник:" in user and "Вопрос:" in user


def test_citations_ignore_out_of_range_numbers(offline_config, sample_documents):
    llm = FakeLLM("Ответ [1] и ещё [1] и несуществующий [99].")
    pipeline = RagPipeline(offline_config, embedder=HashingEmbedder(), llm=llm)
    pipeline.ingest_documents(sample_documents)
    answer = pipeline.ask("прогрев шпинделя", top_k=2)
    assert [c.number for c in answer.citations] == [1]


def test_refusal_is_detected(offline_config, sample_documents):
    llm = FakeLLM(NO_ANSWER_MARKER)
    pipeline = RagPipeline(offline_config, embedder=HashingEmbedder(), llm=llm)
    pipeline.ingest_documents(sample_documents)
    answer = pipeline.ask("Какой пароль администратора?")
    assert answer.refused
    assert answer.citations == []


def test_empty_index_refuses_without_calling_llm(offline_config):
    llm = FakeLLM("не должно вызываться")
    pipeline = RagPipeline(offline_config, embedder=HashingEmbedder(), llm=llm)
    answer = pipeline.ask("вопрос")
    assert answer.refused and answer.hits == []
    assert llm.calls == []


def test_index_save_and_load(offline_pipeline, offline_config):
    directory = offline_pipeline.save_index()
    assert (directory / "chunks.jsonl").exists()
    fresh = RagPipeline(offline_config, embedder=HashingEmbedder(), llm=FakeLLM("x [1]"))
    count = fresh.load_index()
    assert count == len(offline_pipeline.store)
    hits = fresh.retrieve("датчик схода ленты RESET", top_k=2)
    assert hits[0].chunk.doc_id == "kl12_konveyer_poisk_neispravnostey.md"


def test_render_lists_sources(offline_pipeline):
    answer = offline_pipeline.ask("перегрев шпинделя")
    rendered = answer.render()
    assert "Источники:" in rendered
    assert "fs400_rukovodstvo_po_ekspluatacii.md" in rendered


def test_config_round_trip(tmp_path):
    cfg = Config()
    cfg.llm.model = "qwen3.5:4b"
    cfg.retrieval.top_k = 3
    path = tmp_path / "config.yaml"
    cfg.dump(path)
    loaded = Config.load(path)
    assert loaded.llm.model == "qwen3.5:4b"
    assert loaded.retrieval.top_k == 3
    assert str(loaded.index_dir) == str(cfg.index_dir)


def test_config_rejects_unknown_keys(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("llm:\n  modle: qwen\n", encoding="utf-8")
    try:
        Config.load(path)
    except ValueError as exc:
        assert "modle" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ожидалась ошибка на неизвестный ключ")
