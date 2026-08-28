from techdoc_assistant.chunking import split_document, split_documents
from techdoc_assistant.config import ChunkingConfig
from techdoc_assistant.documents import Document


def _doc(text: str) -> Document:
    return Document(doc_id="doc.md", source="doc.md", text=text, title="Тест")


def test_chunks_respect_size_and_have_unique_ids(sample_documents):
    cfg = ChunkingConfig(chunk_size=500, chunk_overlap=100)
    chunks = split_documents(sample_documents, cfg)
    assert chunks, "документы должны давать хотя бы один чанк"
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    # Допуск: чанк может превысить лимит только за счёт перекрытия и разделителей.
    assert all(len(c.text) <= cfg.chunk_size + cfg.chunk_overlap + 4 for c in chunks)
    assert all(c.text.strip() for c in chunks)


def test_sections_are_tracked_from_headings():
    text = "# Руководство\n\nВводный абзац.\n\n## Коды ошибок\n\nE12 — перегрев шпинделя.\n"
    chunks = split_document(_doc(text), ChunkingConfig(chunk_size=200, chunk_overlap=0))
    sections = {c.section for c in chunks}
    assert "Коды ошибок" in sections
    error_chunk = next(c for c in chunks if c.section == "Коды ошибок")
    assert "E12" in error_chunk.text


def test_overlap_carries_tail_of_previous_chunk():
    paragraphs = [f"Абзац номер {i} содержит уникальное слово слово{i}." for i in range(30)]
    text = "\n\n".join(paragraphs)
    chunks = split_document(_doc(text), ChunkingConfig(chunk_size=200, chunk_overlap=60))
    assert len(chunks) > 3
    # Начало второго чанка должно повторять хвост первого.
    first_tail_word = chunks[0].text.split()[-1]
    assert first_tail_word in chunks[1].text


def test_long_paragraph_is_split_by_sentences():
    text = " ".join(f"Предложение номер {i} довольно длинное и содержательное." for i in range(40))
    chunks = split_document(_doc(text), ChunkingConfig(chunk_size=300, chunk_overlap=0))
    assert len(chunks) >= 5
    assert all(len(c.text) <= 300 for c in chunks)


def test_empty_document_gives_no_chunks():
    assert split_document(_doc("\n\n"), ChunkingConfig()) == []


def test_markdown_table_is_split_by_rows_with_repeated_header():
    rows = "\n".join(f"| E{i:02d} | Описание ошибки номер {i} | Действие оператора {i} |" for i in range(1, 40))
    text = "## Коды ошибок\n\n| Код | Описание | Действия |\n|---|---|---|\n" + rows + "\n"
    chunks = split_document(_doc(text), ChunkingConfig(chunk_size=400, chunk_overlap=0))
    assert len(chunks) > 2
    for chunk in chunks:
        assert chunk.section == "Коды ошибок"
        assert "| Код | Описание | Действия |" in chunk.text  # шапка таблицы повторена
        assert len(chunk.text) <= 400
    # Ни одна строка таблицы не разрезана посередине.
    assert all(line.startswith("|") and line.endswith("|") for c in chunks for line in c.text.splitlines())
