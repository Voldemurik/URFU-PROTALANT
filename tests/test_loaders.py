from pathlib import Path

import pytest

from techdoc_assistant.chunking import split_document
from techdoc_assistant.config import ChunkingConfig
from techdoc_assistant.documents import Chunk, Document
from techdoc_assistant.embeddings import HashingEmbedder
from techdoc_assistant.llm import FakeLLM
from techdoc_assistant.loaders import (
    _clean_pdf_pages,
    _layout_tables_to_markdown,
    load_documents,
    read_text,
)
from techdoc_assistant.prompts import is_refusal
from techdoc_assistant.rag import IndexMismatchError, RagPipeline

TEXT = "Регламент обслуживания: проверка затяжки клемм ежемесячно.\n"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1251", "koi8-r", "utf-16"])
def test_read_text_guesses_encoding(tmp_path: Path, encoding: str):
    path = tmp_path / f"doc-{encoding}.txt"
    path.write_bytes(TEXT.encode(encoding))
    assert read_text(path) == TEXT


def test_doc_id_is_relative_to_ingest_root(tmp_path: Path):
    (tmp_path / "линия-1").mkdir()
    (tmp_path / "линия-2").mkdir()
    (tmp_path / "линия-1" / "паспорт.md").write_text("# Паспорт 1\n\nТекст первый.\n", encoding="utf-8")
    (tmp_path / "линия-2" / "паспорт.md").write_text("# Паспорт 2\n\nТекст второй.\n", encoding="utf-8")
    docs = load_documents([tmp_path])
    assert sorted(d.doc_id for d in docs) == ["линия-1/паспорт.md", "линия-2/паспорт.md"]
    # Одиночный файл — просто имя.
    single = load_documents([tmp_path / "линия-1" / "паспорт.md"])
    assert single[0].doc_id == "паспорт.md"


def test_unsupported_and_missing_paths_are_skipped(tmp_path: Path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    assert load_documents([tmp_path / "image.png", tmp_path / "nope.md"]) == []


def test_docx_paragraphs_headings_and_tables(tmp_path: Path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Регламент ПЛК-200", level=1)
    document.add_paragraph("Общие положения регламента.")
    document.add_heading("Индикаторы", level=2)
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Индикатор"
    table.rows[0].cells[1].text = "Значение"
    table.rows[1].cells[0].text = "ERR"
    table.rows[1].cells[1].text = "ошибка | ввода-вывода"
    path = tmp_path / "reglament.docx"
    document.save(str(path))

    docs = load_documents([path])
    assert len(docs) == 1
    text = docs[0].text
    assert docs[0].title == "Регламент ПЛК-200"
    assert "## Индикаторы" in text
    assert "| Индикатор | Значение |" in text and "| ERR | ошибка \\| ввода-вывода |" in text
    chunks = split_document(docs[0], ChunkingConfig())
    assert any(c.section == "Индикаторы" and "ERR" in c.text for c in chunks)


def test_code_fences_are_not_headings():
    text = "# Инструкция\n\n```bash\n# скачать модель\nollama pull bge-m3\n```\n\nДалее текст.\n"
    doc = Document(doc_id="d.md", source="d.md", text=text, title="Инструкция")
    chunks = split_document(doc, ChunkingConfig(chunk_size=500, chunk_overlap=0))
    assert {c.section for c in chunks} == {"Инструкция"}
    assert "ollama pull bge-m3" in chunks[0].text


def test_label_and_index_text_skip_duplicate_title():
    chunk = Chunk(chunk_id="d#0", doc_id="d.md", source="d.md", text="Текст", position=0, title="Руководство", section="Руководство")
    assert chunk.label() == "Руководство"
    assert chunk.index_text() == "Руководство\nТекст"
    chunk.section = "Коды ошибок"
    assert chunk.label() == "Руководство › Коды ошибок"
    assert chunk.index_text() == "Руководство\nКоды ошибок\nТекст"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("В предоставленной документации нет информации для ответа на этот вопрос.", True),
        ("К сожалению, в документации нет сведений о пароле администратора.", True),
        ("Данные о гарантийном сроке в документации отсутствуют.", True),
        ("", True),
        ("Перегреву шпинделя соответствует код E12 [1].", False),
        ("В документации нет информации о гарантии, но есть сведения о хранении: от −10 до +40 °C [2].", False),
    ],
)
def test_is_refusal(text: str, expected: bool):
    assert is_refusal(text) is expected


def test_index_mismatch_is_reported(offline_pipeline, offline_config):
    directory = offline_pipeline.save_index()
    other = RagPipeline(offline_config, embedder=HashingEmbedder(dim=64), llm=FakeLLM("x"))
    with pytest.raises(IndexMismatchError, match="hashing:512"):
        other.load_index(directory)


def test_empty_question_is_refused_without_llm(offline_pipeline, fake_llm):
    calls = len(fake_llm.calls)
    answer = offline_pipeline.ask("   ")
    assert answer.refused and answer.hits == []
    assert len(fake_llm.calls) == calls

def test_pdf_repeated_headers_and_page_numbers_are_removed():
    pages = [
        "ACME Manual 1 / 3\n1. Safety\nDisconnect power before service.",
        "ACME Manual 2 / 3\n2. Errors\nE12 means motor overheating.",
        "ACME Manual 3 / 3\n3. Service\nWait 20 minutes before restart.",
    ]

    cleaned = _clean_pdf_pages(pages)

    assert len(cleaned) == 3
    assert all("ACME Manual" not in page for page in cleaned)
    assert "Disconnect power before service." in cleaned[0]
    assert "E12 means motor overheating." in cleaned[1]
    assert "Wait 20 minutes before restart." in cleaned[2]

def test_pdf_page_number_at_margin_is_removed():
    pages = ["Safety instructions\nDisconnect power.\n42"]

    cleaned = _clean_pdf_pages(pages)

    assert "Disconnect power." in cleaned[0]
    assert not cleaned[0].endswith("42")

def test_pdf_hyphenated_word_is_joined():
    pages = ["The display shows Posi-\ntion: Relative Actual."]

    cleaned = _clean_pdf_pages(pages)

    assert "Position: Relative Actual." in cleaned[0]

def test_pdf_short_technical_hyphen_is_preserved():
    pages = ["Use G-\ncode commands carefully."]

    cleaned = _clean_pdf_pages(pages)

    assert "G-code" in cleaned[0]

def test_layout_table_is_converted_to_markdown():
    text = (
        "Code    Description       Action\n"
        "E12     Overheating       Stop machine\n"
        "E13     Low pressure      Check pump"
    )

    converted = _layout_tables_to_markdown(text)

    assert "| Code | Description | Action |" in converted
    assert "| --- | --- | --- |" in converted
    assert "| E12 | Overheating | Stop machine |" in converted
    assert "| E13 | Low pressure | Check pump |" in converted

def test_regular_paragraph_is_not_converted_to_table():
    text = "First ordinary line.\nSecond ordinary line."

    assert _layout_tables_to_markdown(text) == text

def test_clean_pdf_pages_preserves_document_order():
    pages = ["First page content.", "Second page content."]

    cleaned = _clean_pdf_pages(pages)

    assert cleaned == pages


def test_toc_lines_with_dot_leaders_are_not_converted_to_table():
    text = (
        "1.3.2.2 AMD-64 ImageusingGUItools   ........................   8\n"
        "1.3.2.3 CommandLine-Linux           ........................   8"
    )

    assert _layout_tables_to_markdown(text) == text


def test_toc_lines_with_spaced_dot_leaders_are_not_converted_to_table():
    text = (
        "1.1 About LinuxCNC          . . . . .   2\n"
        "1.2 System Requirements     . . . . .   4"
    )

    assert _layout_tables_to_markdown(text) == text
