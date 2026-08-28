# Обзор аналогов

Локальные «чаты с документами» — популярный класс инструментов. Обзор нужен, чтобы
не изобретать велосипед там, где он есть, и чётко понимать, в чём вклад проекта.

## Готовые локальные RAG-системы

| Проект | Что это | Что берём | Чего не хватает для нашей задачи |
|---|---|---|---|
| [PrivateGPT](https://github.com/zylon-ai/private-gpt) | Один из первых полностью локальных RAG-серверов | Идея «данные не покидают контур», API | Общее назначение, нет оценки качества, нет фокуса на русском |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | Настольное приложение с чатом по документам | UX: рабочие пространства, подсветка источников | Закрытая для экспериментов логика поиска, нет метрик |
| [Open WebUI](https://github.com/open-webui/open-webui) | Веб-интерфейс к Ollama со встроенным RAG | Кандидат в интерфейс на этапе 2 | RAG «как есть», без измерения качества |
| [RAGFlow](https://github.com/infiniflow/ragflow) | Корпоративный RAG с продвинутым парсингом документов | Идеи по разбору таблиц и вёрстки PDF | Тяжёлая инфраструктура (Elasticsearch, MySQL, Redis) |
| [Kotaemon](https://github.com/Cinnamon/kotaemon) | Фреймворк RAG-приложений с UI | Гибридный поиск, переранжирование | Ориентирован на английский, сложная кодовая база |
| [LightRAG](https://github.com/HKUDS/LightRAG) | RAG с графом знаний | Идея графа сущностей для «перекрёстных» вопросов | Избыточно для регламентов и руководств |
| [Onyx](https://github.com/onyx-dot-app/onyx) (ex-Danswer) | Корпоративный поиск по коннекторам | Коннекторы к Confluence и т. п. (этап 2+) | Большая система, не для одной машины |

Общий вывод: инструментов много, но все они — «чёрные ящики» с точки зрения
качества. Ни один не даёт из коробки ответ на вопрос «насколько этому ассистенту
можно верить на *моей* документации».

## Фреймворки оценки RAG

| Проект | Подход | Ограничения для нас |
|---|---|---|
| [RAGAS](https://github.com/explodinggradients/ragas) | Faithfulness, answer relevancy, context precision/recall через LLM-судью | Английские промпты судьи, по умолчанию OpenAI |
| [DeepEval](https://github.com/confident-ai/deepeval) | Юнит-тесты для LLM, набор метрик, LLM-судья | То же; тяжёлая зависимость |
| [TruLens](https://github.com/truera/trulens) | «Триада RAG»: контекст ↔ ответ ↔ вопрос | Ориентация на трассировку приложений, не на офлайн |
| [BEIR](https://github.com/beir-cellar/beir) / [MTEB](https://github.com/embeddings-benchmark/mteb) | Бенчмарки поиска и эмбеддингов | Оценивают модели, а не конкретный пайплайн на конкретных документах |

Полезны как ориентир для определений метрик (faithfulness, context recall).
Для русскоязычных эмбеддингов есть бенчмарк [ruMTEB](https://arxiv.org/abs/2408.12503)
(Snegirev et al., NAACL 2025), по которому выбираются кандидаты (`bge-m3`, `qwen3-embedding`, `multilingual-e5`).

## Ключевые методы

- **RAG**: Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, 2020.
- **Гибридный поиск и RRF**: Cormack, Clarke, Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods*, SIGIR 2009.
- **BM25**: Robertson, Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond*, 2009.
- **LoRA / QLoRA**: Hu et al., *LoRA: Low-Rank Adaptation of Large Language Models*, 2021; Dettmers et al., *QLoRA*, 2023.
- **LLM-as-a-judge**: Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, 2023.
- **Оценка RAG**: Es et al., *RAGAS: Automated Evaluation of Retrieval Augmented Generation*, 2023.

## В чём вклад проекта

1. Пайплайн, заточенный под русскоязычную промышленную документацию: структурный
   чанкинг с таблицами, гибридный поиск для кодов и артикулов, ссылки на источники.
2. Локальная система оценки с «жёсткими» метриками (ловушки, обязательные факты,
   ссылки), не зависящая от облачных судей.
3. Замкнутый цикл: оценка → выявление слабых мест → дообучение LoRA → повторная
   оценка на той же системе.
4. Прозрачный код без тяжёлых фреймворков — каждое решение можно объяснить и защитить.
