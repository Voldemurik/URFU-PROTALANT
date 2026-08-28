"""Подготовка обучающего набора для дообучения (SFT — supervised fine-tuning).

Из оценочного JSONL (вопрос + эталонный ответ) и проиндексированной
документации собирается набор диалогов в формате чата::

    {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}

Пользовательское сообщение содержит тот же контекст из top-k фрагментов,
что модель увидит в бою, а ответ ассистента — эталон со ссылками на те
фрагменты, где действительно есть нужные факты. Так модель учится именно
формату работы ассистента: отвечать по контексту и ставить ссылки.

Примеры, для которых поиск не нашёл нужный документ, **пропускаются**: иначе
модель училась бы отвечать без опоры на контекст, то есть галлюцинировать.

Пример::

    python training/prepare_sft_dataset.py data/eval/sample_qa.jsonl -o training/data/sft.jsonl
    python training/prepare_sft_dataset.py data/eval/sample_qa.jsonl -o /tmp/sft.jsonl --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from techdoc_assistant.config import Config
from techdoc_assistant.documents import Chunk
from techdoc_assistant.embeddings import HashingEmbedder
from techdoc_assistant.evaluation import EvalSample, load_dataset
from techdoc_assistant.evaluation.metrics import must_include_coverage
from techdoc_assistant.llm import FakeLLM
from techdoc_assistant.prompts import NO_ANSWER_MARKER, SYSTEM_PROMPT, build_user_prompt
from techdoc_assistant.rag import IndexMismatchError, RagPipeline


def _supporting_chunks(sample: EvalSample, chunks: list[Chunk]) -> list[int]:
    """Номера фрагментов (с 1), на которые должен ссылаться эталонный ответ."""
    relevant = [n for n, c in enumerate(chunks, start=1) if c.doc_id in sample.relevant_docs]
    if sample.must_include:
        with_facts = [n for n in relevant if must_include_coverage(chunks[n - 1].text, sample.must_include) > 0]
        if with_facts:
            return with_facts[:3]
    return relevant[:1]


def build_examples(pipeline: RagPipeline, samples, *, top_k: int | None = None) -> tuple[list[dict], list[str]]:
    examples, skipped = [], []
    for sample in samples:
        hits = pipeline.retrieve(sample.question, top_k)
        chunks = [hit.chunk for hit in hits]
        if sample.answerable:
            cited = _supporting_chunks(sample, chunks)
            if not cited:
                skipped.append(sample.id)
                continue
            answer = sample.reference_answer.strip()
            if "[" not in answer:
                answer = f"{answer} " + "".join(f"[{n}]" for n in cited)
        else:
            answer = NO_ANSWER_MARKER
        examples.append(
            {
                "id": sample.id,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(sample.question, chunks)},
                    {"role": "assistant", "content": answer},
                ],
            }
        )
    return examples, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", nargs="+", help="JSONL с вопросами и эталонными ответами")
    parser.add_argument("-o", "--output", required=True, help="куда записать SFT-набор (JSONL)")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--index-dir", default=None)
    parser.add_argument("--docs", nargs="*", default=None, help="проиндексировать эти документы вместо загрузки индекса")
    parser.add_argument("-k", "--top-k", type=int, default=None)
    parser.add_argument("--offline", action="store_true", help="хэш-эмбеддинги вместо Ollama (для проверки скрипта)")
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    if args.index_dir:
        config.index_dir = Path(args.index_dir)
    pipeline = RagPipeline(
        config,
        embedder=HashingEmbedder() if args.offline else None,
        llm=FakeLLM(""),  # генерация здесь не нужна
    )
    if args.docs:
        pipeline.ingest_paths(args.docs)
    else:
        try:
            pipeline.load_index()
        except (FileNotFoundError, IndexMismatchError) as exc:
            sys.exit(f"Ошибка: {exc}")

    samples = [s for path in args.dataset for s in load_dataset(path)]
    examples, skipped = build_examples(pipeline, samples, top_k=args.top_k)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for example in examples:
            fh.write(json.dumps(example, ensure_ascii=False) + "\n")
    print(f"Записано примеров: {len(examples)} -> {output}")
    if skipped:
        print(f"Пропущено (нужный документ не найден поиском): {len(skipped)} — {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
