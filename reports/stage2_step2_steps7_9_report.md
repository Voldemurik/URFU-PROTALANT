# Отчёт по шагам 7 и 9 — контрольная индексация и финальная проверка

- **Дата:** 08.11.2026.
- **Ветка:** `feature/stage2-step2-pdf-loaders`.
- **Документ:** `data/test_docs/LinuxCNC_Getting_and_Running_10_pages.md`
  (разделы 1.3 «Getting LinuxCNC» и 1.4 «Running LinuxCNC», страницы 61–70
  исходного PDF LinuxCNC_Documentation_2.9).
- **Окружение:** techdoc-assistant 1.1.2, Python 3.14.7, faiss, Ollama 0.40.15,
  эмбеддинги `qwen3-embedding:0.6b`, LLM `qwen3.5:0.8b` (`techdoc doctor`: «всё готово»).

Запросы адаптированы под содержимое документа: в разделах 1.3–1.4 нет систем
координат G53/G54 из исходного плана, поэтому контрольные вопросы взяты по теме
загрузки и проверки образа LinuxCNC. Это smoke-тест работоспособности, а не
сравнение качества «до/после» — метрики выполняются на шаге 3.

## Шаг 7. Контрольная индексация

### 7.1. Офлайн-режим (хэш-эмбеддинги)

Команда:

```powershell
techdoc ingest data\test_docs\LinuxCNC_Getting_and_Running_10_pages.md `
    --offline --index-dir storage\index-getting-running-offline
```

Результат: **39 фрагментов за 0,3 с** (бэкенд faiss), индекс сохранён.

Поиск — обе проверки дают точный топ-1 с ожидаемым разделом:

| Запрос | Топ-1 результат | score | dense / bm25 |
| --- | --- | --- | --- |
| `zsync download image` | 1.3.1.2 Download using zsync | 0.0328 | 1 / 1 |
| `verify checksum sha256sum` | 1.3.1.3 Verify the image | 0.0328 | 1 / 1 |

Проверка чанков (`storage/index-getting-running-offline/chunks.jsonl`):

- чанков: **39**;
- повторяющихся колонтитулов `LinuxCNC V2.9.7` — **0**;
- разделы корректно привязаны к чанкам (например, 6 чанков раздела
  «1.4.2 Configuration Launcher»).

### 7.2. Полноценная индексация через Ollama

Команда:

```powershell
techdoc ingest data\test_docs\LinuxCNC_Getting_and_Running_10_pages.md `
    --index-dir storage\index-getting-running
```

Результат: **39 фрагментов за 415,7 с** (~7 минут на CPU), индекс сохранён
в `storage/index-getting-running` (`chunks.jsonl`, `vectors.npy`, `meta.json`).
Ошибок эмбеддингов не возникло.

Поиск:

```powershell
techdoc search "How to verify the LinuxCNC image checksum?" `
    --index-dir storage\index-getting-running -k 5
```

Топ-1 — раздел **1.3.1.3 Verify the image** (score=0.0328, dense=1, bm25=1),
фрагмент содержит команды `md5sum` / `sha256sum` и контрольные суммы. Выдача
релевантна.

Контрольный вопрос:

```powershell
techdoc ask "What real-time kernels does LinuxCNC require to operate machinery?" `
    --index-dir storage\index-getting-running --show-context
```

- Ответ получен за 164,3 с и содержит ключевой факт документа: для работы
  станка LinuxCNC требуется ядро реального времени — **preempt-rt, RTAI или
  Xenomai**; для тестирования и симуляции возможен запуск `linuxcnc-uspace`
  на обычном ядре.
- Ссылки на источники проставлены и ведут на правильные разделы:
  [1] — 1.3 Getting LinuxCNC (нужная заметка о ядрах), [2] — 1.4.4 Simulator
  Configurations, [3] — 1.3.7.3 Installing on Raspbian 12.
- Контекст из 5 фрагментов релевантен вопросу.

Замечание о качестве: формулировки ответа модели `qwen3.5:0.8b` местами
корявые и повторяются. На итог smoke-теста это не влияет; оценка качества
ответов — задача шага 3 (для неё имеет смысл рассмотреть модель крупнее).

## Шаг 9. Финальные проверки

| Проверка | Результат |
| --- | --- |
| `python -m pytest` | **73 passed** за 9,21 с |
| `python -m ruff check src tests scripts` | **All checks passed!** |
| `git diff --check` (текстовые файлы) | чисто |
| `techdoc doctor` | всё готово |

Примечание: `git diff --check` без фильтра выводит предупреждения
«trailing whitespace» по `docs/LinuxCNC_Documentation_2.9.pdf` — это бинарный
файл, заменённый локально на укороченную версию; к коду и текстовым файлам
предупреждения отношения не имеют. Изменение PDF, каталоги `data/test_docs/`
и `reports/pdf_audit/linuxcnc_25_pages_qa/` оставлены незакоммиченными как
локальные рабочие материалы.

## Итог

- Загрузка, очистка, структурный чанкинг и оба режима индексации работают
  на реальном документе LinuxCNC: офлайн и через Ollama.
- Гибридный поиск возвращает релевантные фрагменты с точной привязкой
  к разделам; колонтитулов в чанках нет.
- RAG отвечает на контрольный вопрос по существу и со ссылками на источники.
- Тесты и линтер зелёные. Шаги 7 и 9 для данного документа выполнены.
- Полный набор метрик и расширение eval-набора не выполнялись — это шаг 3.
