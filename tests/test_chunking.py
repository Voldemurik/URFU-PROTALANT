import json

from techdoc_assistant.chunking import split_document, split_documents
from techdoc_assistant.config import ChunkingConfig
from techdoc_assistant.documents import Document


def _doc(text: str) -> Document:
    return Document(doc_id="doc.md", source="doc.md", text=text, title="Тест")


def _pdf_doc(page_texts: list[str]) -> Document:
    """Документ с картой страниц: page_map хранит (смещение, номер страницы)."""
    parts: list[str] = []
    page_map: list[tuple[int, int]] = []
    offset = 0
    for number, text in enumerate(page_texts, start=1):
        if not text.strip():
            continue  # пустые страницы в текст не попадают, нумерация сохраняется
        page_map.append((offset, number))
        parts.append(text)
        offset += len(text) + 2  # разделитель страниц "\n\n"
    return Document(
        doc_id="doc.pdf",
        source="doc.pdf",
        text="\n\n".join(parts),
        title="Тест",
        metadata={"page_map": page_map},
    )


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


def test_document_without_page_map_has_no_page_numbers():
    chunks = split_document(_doc("Обычный текст без страниц.\n"), ChunkingConfig())
    assert len(chunks) == 1
    assert "page_start" not in chunks[0].metadata
    assert "page_end" not in chunks[0].metadata


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


def test_chunks_on_one_pdf_page_get_its_number():
    doc = _pdf_doc([
        "Первая страница: общие сведения об установке оборудования.",
        "Вторая страница: коды ошибок и действия оператора при неисправности.",
        "Третья страница: регламент технического обслуживания и смазки узлов.",
    ])
    chunks = split_document(doc, ChunkingConfig(chunk_size=80, chunk_overlap=0, min_chunk_size=0))

    by_page = {c.metadata["page_start"]: c for c in chunks}
    assert by_page[1].metadata["page_end"] == 1
    assert "коды ошибок" in by_page[2].text
    assert by_page[2].metadata["page_end"] == 2
    assert "обслуживания" in by_page[3].text
    assert by_page[3].metadata["page_end"] == 3


def test_chunk_spanning_two_pages_gets_page_range():
    doc = _pdf_doc([
        "Первая страница заканчивается этим абзацем о безопасности.",
        "Вторая страница начинается с перечня кодов ошибок станка.",
    ])
    chunks = split_document(doc, ChunkingConfig(chunk_size=500, chunk_overlap=0))

    assert len(chunks) == 1
    assert chunks[0].metadata["page_start"] == 1
    assert chunks[0].metadata["page_end"] == 2


def test_chunking_keeps_page_map_json_serializable():
    doc = _pdf_doc(["Только одна страница текста."])
    chunks = split_document(doc, ChunkingConfig(chunk_size=500, chunk_overlap=0))

    assert json.dumps([c.to_dict() for c in chunks])
