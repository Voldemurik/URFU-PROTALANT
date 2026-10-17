# История изменений

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — [SemVer](https://semver.org/lang/ru/).

## Unreleased

### Планируется
- Оценка на реальной документации индустриального партнёра.
- Переранжирование кандидатов кросс-энкодером.
- Веб-интерфейс.

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
- Реализация [этапа 1 шага 1]([https://github.com/Voldemurik/URFU-PROTALANT/blob/main/plan-rabot.md](https://github.com/Voldemurik/URFU-PROTALANT/blob/main/docs/roadmap.md#%D1%8D%D1%82%D0%B0%D0%BF-1-%D0%B7%D0%B0%D0%BF%D1%83%D1%81%D0%BA-%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D1%8B-%D0%BD%D0%B0-%D1%80%D0%B5%D0%B0%D0%BB%D1%8C%D0%BD%D0%BE%D0%B9-%D0%BC%D0%BE%D0%B4%D0%B5%D0%BB%D0%B8-%D0%B8-%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D0%B4%D0%B5%D0%BD%D0%B8%D0%B5-%D1%80%D0%B5%D0%BF%D0%BE%D0%B7%D0%B8%D1%82%D0%BE%D1%80%D0%B8%D1%8F-%D0%B2-%D0%BF%D0%BE%D1%80%D1%8F%D0%B4%D0%BE%D0%BA)): добавлены [бейджи в шапке](https://github.com/Voldemurik/URFU-PROTALANT/blob/main/README.md), описание и topics в README.
- Унификация целевой модели между README и [контуром обучения](https://github.com/Voldemurik/URFU-PROTALANT/blob/main/config.example.yaml).
