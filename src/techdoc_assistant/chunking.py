"""Разбиение документов на фрагменты (чанки).

Стратегия — «структурная»: текст режется по абзацам и заголовкам, абзацы
склеиваются в чанки заданного размера с перекрытием, а для каждого чанка
запоминается ближайший заголовок раздела. Это сохраняет контекст
(например, «Коды ошибок › E12») и делает ссылки на источники точнее, чем
слепое разбиение по фиксированному числу символов.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from techdoc_assistant.config import ChunkingConfig
from techdoc_assistant.documents import Chunk, Document

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+(?=[А-ЯA-Z0-9«\"(])")


def split_document(doc: Document, cfg: ChunkingConfig | None = None) -> list[Chunk]:
    """Разбить документ на чанки согласно конфигурации."""
    cfg = cfg or ChunkingConfig()
    pieces = _merge_tiny(list(_iter_chunk_texts(doc.text, cfg)), cfg.min_chunk_size)
    chunks: list[Chunk] = []
    for position, (section, text) in enumerate(pieces):
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{position}",
                doc_id=doc.doc_id,
                source=doc.source,
                text=text,
                position=position,
                title=doc.title,
                section=section,
                metadata=dict(doc.metadata),
            )
        )
    return chunks


def _merge_tiny(pieces: list[tuple[str, str]], min_size: int) -> list[tuple[str, str]]:
    """Короткие «хвосты» раздела приклеиваем к предыдущему чанку того же раздела.

    Короткий чанк с собственным заголовком не трогаем: одинокая строка под
    заголовком — это всё же отдельный раздел, и ссылка на него должна быть точной.
    """
    merged: list[tuple[str, str]] = []
    for section, text in pieces:
        if merged and len(text) < min_size and section == merged[-1][0]:
            prev_section, prev_text = merged[-1]
            merged[-1] = (prev_section, f"{prev_text}\n\n{text}")
        else:
            merged.append((section, text))
    return merged


def split_documents(docs: Iterable[Document], cfg: ChunkingConfig | None = None) -> list[Chunk]:
    result: list[Chunk] = []
    for doc in docs:
        result.extend(split_document(doc, cfg))
    return result


def _iter_chunk_texts(text: str, cfg: ChunkingConfig):
    """Отдаёт пары (заголовок раздела, текст чанка)."""
    blocks = _split_into_blocks(text)
    buffer: list[str] = []
    buffer_len = 0
    current_section = ""
    buffer_section = ""

    def flush():
        nonlocal buffer, buffer_len
        if not buffer:
            return None
        chunk_text = "\n\n".join(buffer).strip()
        buffer, buffer_len = [], 0
        return chunk_text

    for is_heading, block in blocks:
        if is_heading:
            # Заголовок начинает новый раздел: закрываем предыдущий чанк.
            done = flush()
            if done:
                yield buffer_section, done
            current_section = block
            buffer_section = current_section
            continue

        pieces = _split_long_block(block, cfg.chunk_size)
        for piece in pieces:
            piece_len = len(piece)
            if buffer and buffer_len + piece_len + 2 > cfg.chunk_size:
                done = flush()
                if done:
                    yield buffer_section, done
                # Перекрытие: переносим хвост предыдущего чанка в начало нового
                # (кроме таблиц — у их кусков и так повторяется шапка).
                overlap = "" if piece.lstrip().startswith("|") else _tail(done or "", cfg.chunk_overlap)
                if overlap:
                    buffer.append(overlap)
                    buffer_len = len(overlap)
            if not buffer:
                buffer_section = current_section
            buffer.append(piece)
            buffer_len += piece_len + 2

    done = flush()
    if done:
        yield buffer_section, done


def _split_into_blocks(text: str) -> list[tuple[bool, str]]:
    """Разделить текст на заголовки и абзацы. Возвращает (is_heading, text)."""
    blocks: list[tuple[bool, str]] = []
    paragraph: list[str] = []
    in_fence = False  # внутри ```-блока кода «# комментарий» — не заголовок

    def close_paragraph():
        if paragraph:
            blocks.append((False, "\n".join(paragraph).strip()))
            paragraph.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            paragraph.append(line.rstrip())
            continue
        m = None if in_fence else _HEADING_RE.match(line)
        if m:
            close_paragraph()
            blocks.append((True, m.group(2).strip()))
        elif not line.strip() and not in_fence:
            close_paragraph()
        else:
            paragraph.append(line.rstrip())
    close_paragraph()
    return [(h, t) for h, t in blocks if t]


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
