# История изменений

## Unreleased — этап 3, шаг 2

### Добавлено
- Номера страниц PDF в ссылках на источники: загрузчик сохраняет `page_map` (смещение → исходный номер страницы), чанки получают `page_start`/`page_end`, подпись источника дополняется «(стр. N)» или «(стр. N–M)» в ответах и в `techdoc search`.
- Скрипт `scripts/verify_pdf_pages.py`: переиндексация PDF и независимая сверка содержимого чанков с указанными страницами; на 25-страничном фрагменте LinuxCNC подтверждены 67/67 чанков.
- Демо «ссылка > страница» с примерами ссылок `документ.pdf#page=N`: `reports/stage3_step2/`.

## Unreleased — этап 3, шаг 1

### Добавлено
- Опциональная лемматизация русских слов в BM25 (`retrieval.bm25_normalization: lemma`, extra `morphology` на `pymorphy3`); технические коды, числа и латинские токены сохраняются без изменений.
- Необязательная разметка `relevant_chunks` и метрики `retrieval/chunk_recall@k`, `retrieval/chunk_hit_rate`, `retrieval/chunk_mrr` для оценки поиска на уровне фрагментов.
- Диагностический набор из 30 русскоязычных запросов и воспроизводимое сравнение BM25 `token`/`lemma` с отчётами «до/после» и измерением производительности.

## 1.0.0 — 28.08.2026

### Добавлено
- RAG-пайплайн: загрузка TXT/MD/PDF/DOCX, структурное разбиение на фрагменты с сохранением
  заголовков разделов и шапок таблиц, эмбеддинги и генерация через Ollama.
- Гибридный поиск: векторный (FAISS/NumPy) + BM25 с объединением по Reciprocal Rank Fusion.
- Ответы со ссылками на источники `[n]` и честным отказом, если ответа в документации нет.
- Система оценки: recall@k, hit rate, MRR, token-F1, покрытие обязательных фактов,
  precision/recall ссылок, доля ложных отказов и отказов на вопросах-ловушках, LLM-судья.
- Экстрактивный бейзлайн для сравнения с LLM; первый эксперимент — индексация заголовков
  документа и раздела вместе с текстом фрагмента (`must_include` 0.46 → 0.68 на учебном наборе).
- CLI `techdoc`: `doctor`, `ingest`, `search`, `ask`, `chat`, `eval`, `init-config`.
- Учебный корпус из трёх вымышленных промышленных документов и 13 оценочных вопросов.
- Контур дообучения LoRA: сборка SFT-набора, скрипт обучения, инструкция по подключению к Ollama.
- Тесты (работают без Ollama), CI на GitHub Actions, шаблоны issue/PR.

[Unreleased]: https://github.com/Voldemurik/URFU-PROTALANT/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Voldemurik/URFU-PROTALANT/releases/tag/v0.1.0

## 1.0.1 — 06.10.2026

### Добавлено
- незначительные изменения и корректировки репозитория (кликабельность ссылок, уточнение dead-лайнов)

## 1.1.1 — 11.10.2026
- Реализация [этапа 1 шага 1](https://github.com/Voldemurik/URFU-PROTALANT/blob/main/docs/roadmap.md#%D1%8D%D1%82%D0%B0%D0%BF-1-%D0%B7%D0%B0%D0%BF%D1%83%D1%81%D0%BA-%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D1%8B-%D0%BD%D0%B0-%D1%80%D0%B5%D0%B0%D0%BB%D1%8C%D0%BD%D0%BE%D0%B9-%D0%BC%D0%BE%D0%B4%D0%B5%D0%BB%D0%B8-%D0%B8-%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D0%B4%D0%B5%D0%BD%D0%B8%D0%B5-%D1%80%D0%B5%D0%BF%D0%BE%D0%B7%D0%B8%D1%82%D0%BE%D1%80%D0%B8%D1%8F-%D0%B2-%D0%BF%D0%BE%D1%80%D1%8F%D0%B4%D0%BE%D0%BA): добавлены [бейджи в шапке](https://github.com/Voldemurik/URFU-PROTALANT/blob/main/README.md), описание и topics в README.
- Унификация целевой модели между README и [контуром обучения](https://github.com/Voldemurik/URFU-PROTALANT/blob/main/config.example.yaml).
