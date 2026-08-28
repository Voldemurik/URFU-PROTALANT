"""Загрузка документов из файлов.

Поддерживаются текстовые форматы (``.txt``, ``.md``, ``.rst``), PDF (через
``pypdf``) и DOCX (через ``python-docx``). Зависимости для PDF и DOCX
необязательные: без них соответствующие файлы пропускаются с понятным
предупреждением, а не роняют весь пайплайн.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from techdoc_assistant.documents import Document

log = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst"}
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | PDF_SUFFIXES | DOCX_SUFFIXES


def iter_files(paths: Iterable[str | Path]) -> Iterator[tuple[Path, Path | None]]:
    """Рекурсивно обойти пути; отдаёт ``(файл, корень)`` для поддерживаемых форматов.

    Корень — каталог, который передали на индексацию; относительно него
    строится ``doc_id``. Для одиночного файла корень отсутствует.
    """
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                    yield child, path
        elif path.is_file():
            if path.suffix.lower() in SUPPORTED_SUFFIXES:
                yield path, None
            else:
                log.warning("Пропускаю %s: формат %s не поддерживается", path, path.suffix)
        else:
            log.warning("Путь не найден: %s", path)


def load_documents(paths: Iterable[str | Path]) -> list[Document]:
    """Загрузить все поддерживаемые документы по указанным путям."""
    documents: list[Document] = []
    seen: set[str] = set()
    for file, root in iter_files(paths):
        doc = load_file(file, root)
        if doc is None or not doc.text.strip():
            log.warning("Пустой или нечитаемый документ: %s", file)
            continue
        if doc.doc_id in seen:
            log.warning("Повторяющийся идентификатор документа %s — пропускаю %s", doc.doc_id, file)
            continue
        seen.add(doc.doc_id)
        documents.append(doc)
    return documents


def load_file(path: Path, root: Path | None = None) -> Document | None:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = read_text(path)
    elif suffix in PDF_SUFFIXES:
        text = _read_pdf(path)
    elif suffix in DOCX_SUFFIXES:
        text = _read_docx(path)
    else:
        return None
    if text is None:
        return None
    text = normalize_text(text)
    return Document(
        doc_id=make_doc_id(path, root),
        source=str(path),
        text=text,
        title=guess_title(text, fallback=path.stem),
        metadata={"suffix": suffix, "chars": len(text)},
    )


def make_doc_id(path: Path, root: Path | None) -> str:
    """Идентификатор документа — путь относительно корня индексации (с прямыми слэшами)."""
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.name


# ------------------------------------------------------------------ текст
_LOWER_CYRILLIC_RE = re.compile(r"[а-яё]")
_UPPER_CYRILLIC_RE = re.compile(r"[А-ЯЁ]")


def read_text(path: Path) -> str:
    """Прочитать текст, угадав кодировку.

    Порядок: UTF-8 (с BOM или без) → UTF-16 по BOM → однобайтовые кириллические
    кодировки. CP1251 и KOI8-R «декодируют» почти любые байты в кириллицу, но
    у чужой кодировки регистр букв «переворачивается» (рЕТЕЗТЕЧ), поэтому
    выбираем ту, где строчных букв больше, чем прописных.
    """
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    best_text, best_score = "", -1.0
    for encoding in ("cp1251", "koi8-r"):
        try:
            candidate = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        lower = len(_LOWER_CYRILLIC_RE.findall(candidate))
        upper = len(_UPPER_CYRILLIC_RE.findall(candidate))
        score = lower / max(lower + upper, 1)
        if score > best_score:
            best_text, best_score = candidate, score
    return best_text or data.decode("utf-8", errors="replace")


def _read_pdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - зависит от окружения
        log.warning("Для чтения PDF установите пакет pypdf: pip install pypdf (%s)", path)
        return None
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(pages)


def _read_docx(path: Path) -> str | None:
    """DOCX: абзацы и таблицы в порядке следования; таблицы — в Markdown-строки."""
    try:
        import docx  # type: ignore[import-not-found]
        from docx.table import Table  # type: ignore[import-not-found]
        from docx.text.paragraph import Paragraph  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - зависит от окружения
        log.warning("Для чтения DOCX установите python-docx: pip install python-docx (%s)", path)
        return None
    document = docx.Document(str(path))
    parts: list[str] = []
    for element in document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(element, document)
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            text = paragraph.text.strip()
            if not text:
                continue
            level = _heading_level(style)
            parts.append(f"{'#' * level} {text}" if level else text)
        elif tag == "tbl":
            parts.append(_table_to_markdown(Table(element, document)))
    return "\n\n".join(p for p in parts if p)


def _heading_level(style_name: str) -> int:
    m = re.match(r"(?:Heading|Заголовок)\s*(\d)", style_name, re.I)
    if m:
        return min(int(m.group(1)), 6)
    return 1 if style_name.lower() in {"title", "название"} else 0


def _table_to_markdown(table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [" ".join(cell.text.split()).replace("|", "\\|") for cell in row.cells]
        # Объединённые ячейки python-docx возвращает повторно — схлопываем дубли подряд.
        deduped: list[str] = []
        for cell in cells:
            if not deduped or cell != deduped[-1]:
                deduped.append(cell)
        rows.append(deduped)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    lines = []
    for i, row in enumerate(rows):
        row = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(row) + " |")
        if i == 0:
            lines.append("|" + "---|" * width)
    return "\n".join(lines)


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def guess_title(text: str, fallback: str) -> str:
    """Заголовок документа — первый Markdown-заголовок либо первая непустая строка."""
    for line in text.splitlines()[:20]:
        m = _HEADING_RE.match(line)
        if m:
            return m.group(1).strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:120]
    return fallback


def normalize_text(text: str) -> str:
    """Унифицировать переводы строк и убрать лишние пустые строки."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
