# Демо «ссылка > страница» — этап 3, шаг 2

**Дата:** 21.11.2026
**Ветка:** `feature/stage3-step2-implementation`
**Документ:** `docs/LinuxCNC_Documentation_2.9.pdf` (25 страниц, 67 чанков)

Цель шага: ссылки на источники в ответах и результатах поиска ведут не просто
на документ, а на конкретную страницу PDF.

## Как это работает

1. **Загрузчик** (`loaders.py`) читает PDF постранично и сохраняет в
   `Document.metadata["page_map"]` карту «смещение в тексте > исходный номер
   страницы». Пустые страницы пропускаются без сдвига нумерации.
2. **Чанкинг** (`chunking.py`) отслеживает смещения каждого блока и куска
   текста, поэтому каждый чанк получает `page_start`/`page_end`. Перекрытие
   (хвост предыдущего чанка) в диапазон не входит — ссылка указывает на новое
   содержимое. Сама карта страниц в метаданные чанков не копируется.
3. **Подпись источника** (`Chunk.label()`) дописывает «(стр. N)» или
   «(стр. N–M)»; её автоматически подхватывают цитаты в ответах (`rag.py`)
   и вывод `techdoc search` (`cli.py`). Ссылка на страницу в просмотрщике PDF:
   `docs/LinuxCNC_Documentation_2.9.pdf#page=N`.

## Проверка точности (независимая сверка)

`scripts/verify_pdf_pages.py` заново извлекает текст указанных страниц через
pypdf (без использования `page_map`) и ищет в нём содержимое чанка.

| Проверка | Результат |
| --- | --- |
| Чанков с номерами страниц | 67 / 67 |
| Содержимое чанка найдено на указанных страницах | **67 / 67 (100 %)** |
| Карта страниц покрывает документ | 25 / 25 страниц |
| Номера не убывают по позиции чанка | да |
| Номера в пределах документа | да |
| `page_map` не дублируется в чанки | да |

Полные данные: `page_number_verification.json`.

## Демо-запросы

Офлайн-индекс: `storage/index-linuxcnc-pages-offline` (HashingEmbedder, без
Ollama). Все приведённые ссылки проверены сверкой содержимого со страницей
(`page_verified: true`, данные в `page_links_demo.json`).

### 1. Which real-time kernel extensions can LinuxCNC use to operate machinery?

| # | Источник | Ссылка на страницу |
| --- | --- | --- |
| 1 | PartI (стр. 5) | `docs/LinuxCNC_Documentation_2.9.pdf#page=5` |
| 2 | PartI (стр. 9) | `docs/LinuxCNC_Documentation_2.9.pdf#page=9` |
| 3 | PartI (стр. 11–12) | `docs/LinuxCNC_Documentation_2.9.pdf#page=11` |

### 2. Can LinuxCNC be tested on a stock kernel, and which application is used?

| # | Источник | Ссылка на страницу |
| --- | --- | --- |
| 1 | PartI (стр. 5) | `docs/LinuxCNC_Documentation_2.9.pdf#page=5` |
| 2 | PartI (стр. 12) | `docs/LinuxCNC_Documentation_2.9.pdf#page=12` |
| 3 | PartI (стр. 9) | `docs/LinuxCNC_Documentation_2.9.pdf#page=9` |

### 3. What is the outlined four-step process for a fresh LinuxCNC installation?

| # | Источник | Ссылка на страницу |
| --- | --- | --- |
| 1 | PartI (стр. 12) | `docs/LinuxCNC_Documentation_2.9.pdf#page=12` |
| 2 | PartI (стр. 5–6) | `docs/LinuxCNC_Documentation_2.9.pdf#page=5` |
| 3 | PartI (стр. 6) | `docs/LinuxCNC_Documentation_2.9.pdf#page=6` |

Пример «ссылка > страница»: третий результат вопроса 3 ведёт на страницу 6,
где действительно находится четырёхшаговый процесс установки:

> The outline of the process looks like this: 1. Download the Live/Install
> Image. 2. Write the image to a USB storage device or DVD. 3. Boot the Live…

## CLI-транскрипт

```
$ techdoc search --offline --index-dir storage/index-linuxcnc-pages-offline --top-k 2 \
    "What is the outlined four-step process for a fresh LinuxCNC installation?"
INFO techdoc: Загружен индекс: 67 фрагментов (faiss)
[1] PartI (стр. 12)  (score=0.0328, dense=1 bm25=1)
    | apt-get | purge | linuxcnc-doc* | | sudo | apt-get | install | linuxcnc |  Rebootthemachine,…
[2] PartI (стр. 5–6)  (score=0.0320, dense=3 bm25=2)
    AswithXenomaiyouwillneedto compilefromsourcetodothis.  1.2.3    Problematic Hardware  …
```

## Воспроизведение

```bash
.venv/Scripts/python scripts/verify_pdf_pages.py
```

Скрипт пересобирает индекс, повторяет сверку всех чанков и перезаписывает
`page_number_verification.json` и `page_links_demo.json`.

## Замечания

- В демо использован 25-страничный фрагмент документации LinuxCNC, который
  сейчас лежит в `docs/`; на полном документе (1347 страниц) механизм тот же —
  сверка масштабируется линейно по числу чанков.
- Качество самого поиска (релевантность top-k) в этом шаге не менялось:
  изменился только формат ссылок на источники.
