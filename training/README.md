# Дообучение (LoRA) — этап 2

Эта папка относится ко второму этапу программы (февраль–июнь 2027). Сейчас здесь
подготовлен полный контур: сборка обучающего набора → дообучение адаптера →
подключение адаптера к модели → сравнение метрик «до/после» той же системой оценки.

## Зачем дообучать, если есть RAG

RAG даёт модели *знания* из документации, но не меняет её *поведение*. Дообучение нужно,
чтобы модель стабильно:

- отвечала строго по контексту и не «додумывала»;
- ставила ссылки `[n]` после каждого утверждения;
- честно отказывалась, когда в документации нет ответа;
- использовала терминологию и стиль конкретного предприятия.

LoRA (Low-Rank Adaptation) обучает небольшие добавочные матрицы поверх замороженных весов
базовой модели — адаптер весит десятки мегабайт, а обучение 7B-модели в 4-битном режиме
(QLoRA) с включённым gradient checkpointing укладывается в одну видеокарту с 16 ГБ памяти
(при `max_seq_len: 4096`, `batch_size: 1–2`). Функция потерь считается только на ответе
ассистента — токены промпта и контекста маскируются, иначе модель учится пересказывать
документацию, а не отвечать по ней.

## Шаги

```bash
# 1. Проиндексировать документацию (как обычно)
techdoc ingest data/sample_docs

# 2. Собрать обучающие диалоги: контекст из индекса + эталонный ответ
python training/prepare_sft_dataset.py data/eval/sample_qa.jsonl -o training/data/sft.jsonl

# 3. Проверить данные и конфигурацию без GPU
python training/train_lora.py --config training/lora_config.yaml --dry-run

# 4. Обучить (нужны torch, transformers, peft, datasets, accelerate, bitsandbytes)
pip install -e ".[train]" bitsandbytes
python training/train_lora.py --config training/lora_config.yaml
```

## Подключение адаптера к Ollama

Базовая модель для дообучения задаётся в `lora_config.yaml` (`Qwen/Qwen2.5-7B-Instruct` с
Hugging Face). Адаптер совместим только с **той же самой** моделью, поэтому для сравнения
«до/после» в Ollama используется её точный аналог `qwen2.5:7b-instruct`, а не модель по
умолчанию из `config.example.yaml`. Сравнивать нужно три конфигурации на одном наборе:
базовая модель без адаптера, базовая модель с адаптером и «боевая» модель приложения.

Ollama подключает LoRA-адаптеры в формате GGUF через `Modelfile`. Адаптер PEFT (safetensors)
сначала конвертируется скриптом из llama.cpp:

```bash
# один раз: git clone https://github.com/ggml-org/llama.cpp
python llama.cpp/convert_lora_to_gguf.py training/output/lora-techdoc \
    --base Qwen/Qwen2.5-7B-Instruct --outfile training/output/lora-techdoc.gguf
```

```
FROM qwen2.5:7b-instruct
ADAPTER ./training/output/lora-techdoc.gguf
```

```bash
ollama create techdoc-qwen -f Modelfile
techdoc eval data/eval/holdout.jsonl -c config.yaml   # в config.yaml: llm.model: techdoc-qwen
```

Запасной путь, если конвертация адаптера для архитектуры не поддерживается: слить адаптер
в веса (`model.merge_and_unload()` в PEFT), сохранить модель целиком и импортировать её в
Ollama через `FROM ./merged` (Ollama сама сконвертирует safetensors в GGUF).

## Формат данных

`training/data/sft.jsonl` — по одному диалогу на строку:

```json
{"id": "q01",
 "messages": [
   {"role": "system", "content": "Ты — ассистент инженера…"},
   {"role": "user", "content": "Контекст:\n[1] Источник: …\n\nВопрос: …"},
   {"role": "assistant", "content": "Перегреву шпинделя соответствует код E12 [1]. …"}
 ]}
```

Для качественного дообучения нужен набор из нескольких сотен пар «вопрос — ответ со ссылками»,
размеченных по реальной документации партнёра. Учебный набор из 13 вопросов здесь только
демонстрирует контур.

## Что измеряем после дообучения

Та же команда `techdoc eval` на отложенной выборке вопросов, которых не было в обучении:
`citations/precision`, `hallucination/trap_refusal_rate`, `judge/faithfulness` и
`answer/must_include` — до и после. Результаты фиксируются в `docs/evaluation.md`.
