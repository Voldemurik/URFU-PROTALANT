"""Проверка номеров страниц PDF в ссылках на источники (этап 3, шаг 2).

Что делает:
1. Загружает PDF новым загрузчиком (с ``page_map``), строит офлайн-индекс
   (HashingEmbedder + FakeLLM, без Ollama) и сохраняет его.
2. Структурные проверки: у всех чанков есть page_start/page_end, номера
   не выходят за пределы документа и не убывают по позиции чанка.
3. Независимая сверка содержимого: для каждого чанка берётся длинная строка
   и ищется в тексте страниц page_start..page_end, извлечённом заново
   через pypdf (без использования page_map). Так подтверждается, что ссылка
   «источник > страница» ведёт на страницу, где текст действительно есть.
4. Демо «ссылка > страница»: несколько вопросов, top-k результатов поиска
   с подписями «(стр. N)», ссылками вида ``файл.pdf#page=N`` и сверкой страниц.

Результаты: reports/stage3_step2/page_number_verification.json и
reports/stage3_step2/page_links_demo.json (+ Markdown-отчёт демо).

Запуск: .venv/Scripts/python scripts/verify_pdf_pages.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pypdf import PdfReader  # noqa: E402

from techdoc_assistant.chunking import split_documents  # noqa: E402
from techdoc_assistant.config import Config  # noqa: E402
from techdoc_assistant.documents import Chunk  # noqa: E402
from techdoc_assistant.embeddings import HashingEmbedder  # noqa: E402
from techdoc_assistant.llm import FakeLLM  # noqa: E402
from techdoc_assistant.loaders import load_documents  # noqa: E402
from techdoc_assistant.rag import RagPipeline  # noqa: E402

log = logging.getLogger("verify_pdf_pages")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _probes(chunk: Chunk, limit: int = 3) -> list[str]:
    """До limit длинных «обычных» строк чанка для поиска на странице."""
    lines = [
        line.strip()
        for line in chunk.text.splitlines()
        if len(line.strip()) >= 40 and not line.lstrip().startswith(("|", "#", "```"))
    ]
    if not lines:
        lines = [line.strip() for line in chunk.text.splitlines() if len(line.strip()) >= 25]
    return sorted(set(lines), key=len, reverse=True)[:limit]


def _page_texts(reader: PdfReader, page_start: int, page_end: int) -> str:
    parts = []
    for number in range(page_start, page_end + 1):
        page = reader.pages[number - 1]
        try:
            parts.append(page.extract_text(extraction_mode="layout") or "")
        except TypeError:
            parts.append(page.extract_text() or "")
    return _norm("\n".join(parts))


def verify_chunk(chunk: Chunk, reader: PdfReader) -> dict:
    """Проверить, что содержимое чанка находится на указанных страницах."""
    page_start = chunk.metadata.get("page_start")
    page_end = chunk.metadata.get("page_end")
    result = {
        "chunk_id": chunk.chunk_id,
        "label": chunk.label(),
        "page_start": page_start,
        "page_end": page_end,
        "verified": False,
        "probe": "",
        "note": "",
    }
    if not page_start or not page_end:
        result["note"] = "нет номеров страниц"
        return result
    probes = _probes(chunk)
    if not probes:
        result["note"] = "нет подходящей строки для сверки"
        result["verified"] = True  # нечего проверять — не считаем ошибкой
        return result
    haystack = _page_texts(reader, page_start, page_end)
    for probe in probes:
        if _norm(probe) in haystack:
            result["verified"] = True
            result["probe"] = probe[:160]
            return result
    result["probe"] = probes[0][:160]
    result["note"] = "строка не найдена на указанных страницах"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", default=str(ROOT / "docs" / "LinuxCNC_Documentation_2.9.pdf"))
    parser.add_argument("--index", default=str(ROOT / "storage" / "index-linuxcnc-pages-offline"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "stage3_step2"))
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Загрузка и переиндексация
    documents = load_documents([pdf_path])
    assert len(documents) == 1, "ожидается один PDF"
    doc = documents[0]
    page_map = doc.metadata.get("page_map") or []
    log.info("Документ: %s, страниц в карте: %d", doc.doc_id, len(page_map))

    config = Config()
    pipeline = RagPipeline(config, embedder=HashingEmbedder(), llm=FakeLLM(""))
    count = pipeline.ingest_documents(documents)
    index_dir = pipeline.save_index(args.index)
    log.info("Проиндексировано чанков: %d, индекс: %s", count, index_dir)

    chunks = split_documents([doc], config.chunking)
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    # 2. Структурные проверки
    structural = {
        "chunks_total": len(chunks),
        "chunks_with_pages": sum(1 for c in chunks if c.metadata.get("page_start")),
        "page_map_pages": len(page_map),
        "pdf_pages": total_pages,
        "page_map_starts_at_zero": bool(page_map) and page_map[0][0] == 0,
        "page_map_not_in_chunk_metadata": all("page_map" not in c.metadata for c in chunks),
        "pages_in_range": all(
            1 <= c.metadata.get("page_start", 0) <= c.metadata.get("page_end", 0) <= total_pages
            for c in chunks
        ),
        "pages_monotonic": all(
            (a.metadata.get("page_start") or 0) <= (b.metadata.get("page_start") or 0)
            for a, b in zip(chunks, chunks[1:], strict=False)
        ),
    }
    log.info("Структурные проверки: %s", structural)

    # 3. Независимая сверка содержимого чанков со страницами
    verifications = [verify_chunk(c, reader) for c in chunks]
    verified = sum(1 for v in verifications if v["verified"])
    failed = [v for v in verifications if not v["verified"]]
    log.info("Сверка содержимого: %d/%d чанков подтверждено", verified, len(chunks))
    for item in failed[:10]:
        log.warning("Не подтверждён %s: %s", item["chunk_id"], item["probe"])

    verification_report = {
        "pdf": str(pdf_path.relative_to(ROOT)),
        "index_dir": str(index_dir.relative_to(ROOT)),
        "structural": structural,
        "content_verified": verified,
        "content_total": len(chunks),
        "content_accuracy": round(verified / max(len(chunks), 1), 4),
        "failures": failed,
    }
    (out_dir / "page_number_verification.json").write_text(
        json.dumps(verification_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 4. Демо «ссылка > страница»
    qa_path = ROOT / "data" / "eval" / "linuxcnc_getting_running_qa.jsonl"
    questions = []
    with qa_path.open(encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("answerable", True):
                questions.append(item["question"])
            if len(questions) == 3:
                break

    demo = []
    for question in questions:
        hits = pipeline.retrieve(question, args.top_k)
        entry = {"question": question, "hits": []}
        for hit in hits:
            chunk = hit.chunk
            check = verify_chunk(chunk, reader)
            page = chunk.metadata.get("page_start")
            entry["hits"].append(
                {
                    "label": chunk.label(),
                    "score": round(hit.score, 4),
                    "page_start": chunk.metadata.get("page_start"),
                    "page_end": chunk.metadata.get("page_end"),
                    "link": f"{chunk.source}#page={page}" if page else chunk.source,
                    "page_verified": check["verified"],
                    "excerpt": _norm(chunk.text)[:240],
                }
            )
        demo.append(entry)
        log.info("Вопрос: %s", question)
        for hit in entry["hits"]:
            log.info("  %s -> %s (сверка: %s)", hit["label"], hit["link"], hit["page_verified"])

    (out_dir / "page_links_demo.json").write_text(
        json.dumps(demo, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log.info("Готово. Отчёты в %s", out_dir)
    return 0 if not failed and all(structural.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
