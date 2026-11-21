"""Разбиение документов на фрагменты (чанки).

Стратегия — «структурная»: текст режется по абзацам и заголовкам, абзацы
склеиваются в чанки заданного размера с перекрытием, а для каждого чанка
запоминается ближайший заголовок раздела. Это сохраняет контекст
(например, «Коды ошибок › E12») и делает ссылки на источники точнее, чем
слепое разбиение по фиксированному числу символов.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterable

from techdoc_assistant.config import ChunkingConfig
from techdoc_assistant.documents import Chunk, Document

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+(?=[А-ЯA-Z0-9«\"(])")


def split_document(doc: Document, cfg: ChunkingConfig | None = None) -> list[Chunk]:
    """Разбить документ на чанки согласно конфигурации."""
    cfg = cfg or ChunkingConfig()
    pieces = _merge_tiny(list(_iter_chunk_texts(doc.text, cfg)), cfg.min_chunk_size)
    page_map = doc.metadata.get("page_map") or []
    chunks: list[Chunk] = []
    for position, (section, text, start, end) in enumerate(pieces):
        metadata = dict(doc.metadata)
        # Карта страниц нужна только на этапе разбиения; дублировать её
        # в каждый чанк индекса нельзя — она одна на весь документ.
        metadata.pop("page_map", None)
        if page_map and start is not None and end is not None:
            page_start, page_end = _pages_for_span(page_map, start, end)
            metadata["page_start"] = page_start
            metadata["page_end"] = page_end
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{position}",
                doc_id=doc.doc_id,
                source=doc.source,
                text=text,
                position=position,
                title=doc.title,
                section=section,
                metadata=metadata,
            )
        )
    return chunks


def _pages_for_span(page_map: list, start: int, end: int) -> tuple[int, int]:
    """Номера страниц, на которые попадает диапазон [start, end) текста документа."""
    offsets = [offset for offset, _ in page_map]
    first = max(bisect_right(offsets, start) - 1, 0)
    last = max(bisect_right(offsets, max(start, end - 1)) - 1, first)
    return page_map[first][1], page_map[last][1]


def _merge_tiny(pieces: list[tuple], min_size: int) -> list[tuple]:
    """Короткие «хвосты» раздела приклеиваем к предыдущему чанку того же раздела.

    Короткий чанк с собственным заголовком не трогаем: одинокая строка под
    заголовком — это всё же отдельный раздел, и ссылка на него должна быть точной.
    """
    merged: list[tuple] = []
    for section, text, start, end in pieces:
        if merged and len(text) < min_size and section == merged[-1][0]:
            prev_section, prev_text, prev_start, prev_end = merged[-1]
            merged[-1] = (
                prev_section,
                f"{prev_text}\n\n{text}",
                prev_start,
                end if end is not None else prev_end,
            )
        else:
            merged.append((section, text, start, end))
    return merged


def split_documents(docs: Iterable[Document], cfg: ChunkingConfig | None = None) -> list[Chunk]:
    result: list[Chunk] = []
    for doc in docs:
        result.extend(split_document(doc, cfg))
    return result


def _iter_chunk_texts(text: str, cfg: ChunkingConfig):
    """Отдаёт (заголовок раздела, текст чанка, начало, конец).

    Начало и конец — смещения содержимого чанка в исходном тексте документа;
    по ним чанку назначаются номера страниц. Перекрытие (хвост предыдущего
    чанка) в диапазон не входит: ссылка должна вести на новое содержимое.
    """
    blocks = _split_into_blocks(text)
    buffer: list[tuple[str, int | None, int | None]] = []
    buffer_len = 0
    current_section = ""
    buffer_section = ""

    def flush():
        nonlocal buffer, buffer_len
        if not buffer:
            return None
        chunk_text = "\n\n".join(piece for piece, _, _ in buffer).strip()
        spans = [(s, e) for _, s, e in buffer if s is not None and e is not None]
        start = min((s for s, _ in spans), default=None)
        end = max((e for _, e in spans), default=None)
        buffer, buffer_len = [], 0
        return chunk_text, start, end

    for is_heading, block, block_start in blocks:
        if is_heading:
            # Заголовок начинает новый раздел: закрываем предыдущий чанк.
            done = flush()
            if done:
                yield buffer_section, *done
            current_section = block
            buffer_section = current_section
            continue

        cursor = block_start
        for piece in _split_long_block(block, cfg.chunk_size):
            start, end = _locate(piece, text, cursor)
            cursor = max(cursor, end)
            piece_len = len(piece)
            if buffer and buffer_len + piece_len + 2 > cfg.chunk_size:
                done = flush()
                if done:
                    yield buffer_section, *done
                # Перекрытие: переносим хвост предыдущего чанка в начало нового
                # (кроме таблиц — у их кусков и так повторяется шапка).
                overlap = "" if piece.lstrip().startswith("|") else _tail(done[0] if done else "", cfg.chunk_overlap)
                if overlap:
                    buffer.append((overlap, None, None))
                    buffer_len = len(overlap)
            if not buffer:
                buffer_section = current_section
            buffer.append((piece, start, end))
            buffer_len += piece_len + 2

    done = flush()
    if done:
        yield buffer_section, *done


def _locate(piece: str, text: str, cursor: int) -> tuple[int, int]:
    """Найти (начало, конец) содержимого куска в тексте, начиная с cursor.

    Куски идут в порядке следования в документе, поэтому поиск от cursor
    однозначен. Кусок таблицы с повторённой шапкой не лежит в тексте подряд:
    тогда диапазон восстанавливаем по строкам — шапка остаётся за cursor
    и в диапазон не попадает.
    """
    pos = text.find(piece, cursor)
    if pos >= 0:
        return pos, pos + len(piece)
    start = end = -1
    scan = cursor
    for line in piece.splitlines():
        if not line.strip():
            continue
        pos = text.find(line, scan)
        if pos < 0:
            continue
        if start < 0:
            start = pos
        end = pos + len(line)
        scan = end
    if start < 0:
        return cursor, cursor
    return start, end


def _split_into_blocks(text: str) -> list[tuple[bool, str, int]]:
    """Разделить текст на заголовки и абзацы. Возвращает (is_heading, text, offset)."""
    blocks: list[tuple[bool, str, int]] = []
    paragraph: list[str] = []
    paragraph_start = 0
    offset = 0
    in_fence = False  # внутри ```-блока кода «# комментарий» — не заголовок

    def close_paragraph():
        if paragraph:
            block = "\n".join(paragraph).strip()
            start = text.find(block, paragraph_start)
            blocks.append((False, block, start if start >= 0 else paragraph_start))
            paragraph.clear()

    for line in text.split("\n"):
        line_start = offset
        offset += len(line) + 1
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if not paragraph:
                paragraph_start = line_start
            paragraph.append(line.rstrip())
            continue
        m = None if in_fence else _HEADING_RE.match(line)
        if m:
            close_paragraph()
            heading = m.group(2).strip()
            start = text.find(heading, line_start)
            blocks.append((True, heading, start if start >= 0 else line_start))
        elif not line.strip() and not in_fence:
            close_paragraph()
        else:
            if not paragraph:
                paragraph_start = line_start
            paragraph.append(line.rstrip())
    close_paragraph()
    return [(h, t, s) for h, t, s in blocks if t]


def _split_long_block(block: str, limit: int) -> list[str]:
    """Блок длиннее лимита режем по строкам (таблицы, списки), затем по предложениям.

    Для Markdown-таблиц заголовок таблицы повторяется в каждом куске, чтобы
    строка «E12 | Перегрев шпинделя | …» не теряла смысл без шапки.
    """
    if len(block) <= limit:
        return [block]
    lines = block.split("\n")
    if len(lines) > 1:
        return _pack_lines(lines, limit)
    return _split_sentences(block, limit)


def _pack_lines(lines: list[str], limit: int) -> list[str]:
    header: list[str] = []
    if _is_table(lines):
        header = lines[:2]
        lines = lines[2:]
    header_text = "\n".join(header)
    pieces: list[str] = []
    current: list[str] = list(header)
    current_len = len(header_text)
    for line in lines:
        for part in _split_sentences(line, limit) if len(line) > limit else [line]:
            if current_len + len(part) + 1 > limit and len(current) > len(header):
                pieces.append("\n".join(current))
                current, current_len = list(header), len(header_text)
            current.append(part)
            current_len += len(part) + 1
    if len(current) > len(header):
        pieces.append("\n".join(current))
    return pieces


def _is_table(lines: list[str]) -> bool:
    return (
        len(lines) >= 3
        and lines[0].lstrip().startswith("|")
        and re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", lines[1]) is not None
    )


def _split_sentences(block: str, limit: int) -> list[str]:
    """Режем по предложениям, а «предложение» длиннее лимита — по символам."""
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_RE.split(block):
        while len(sentence) > limit:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:limit])
            sentence = sentence[limit:]
        if current and len(current) + len(sentence) + 1 > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, size: int) -> str:
    """Последние ``size`` символов текста, выровненные по границе слова."""
    if size <= 0 or not text:
        return ""
    if len(text) <= size:
        return text
    tail = text[-size:]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < len(tail) - 1 else tail
