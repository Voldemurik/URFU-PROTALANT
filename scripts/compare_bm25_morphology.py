"""Сравнить BM25 token/lemma на наборе с разметкой relevant_chunks."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from techdoc_assistant.chunking import split_documents
from techdoc_assistant.documents import Chunk
from techdoc_assistant.evaluation import metrics as m
from techdoc_assistant.evaluation.dataset import EvalSample, load_dataset
from techdoc_assistant.lexical import BM25Index
from techdoc_assistant.loaders import load_documents


def run_mode(
    chunks: list[Chunk], samples: list[EvalSample], mode: str, top_k: int
) -> dict[str, Any]:
    started = time.perf_counter()
    index = BM25Index(normalization=mode).build(chunk.index_text() for chunk in chunks)
    build_s = time.perf_counter() - started

    results: list[dict[str, Any]] = []
    search_s = 0.0
    for sample in samples:
        started = time.perf_counter()
        found = index.search(sample.question, top_k=top_k)
        search_s += time.perf_counter() - started
        retrieved = [chunks[i].chunk_id for i, _ in found]
        rank = next(
            (rank for rank, chunk_id in enumerate(retrieved, start=1) if chunk_id in sample.relevant_chunks),
            None,
        )
        results.append(
            {
                "id": sample.id,
                "question": sample.question,
                "tags": sample.tags,
                "relevant_chunks": sample.relevant_chunks,
                "retrieved_chunks": retrieved,
                "rank": rank,
                "recall_at_k": m.recall_at_k(retrieved, sample.relevant_chunks),
                "hit_rate": m.hit_rate(retrieved, sample.relevant_chunks),
                "mrr": m.mrr(retrieved, sample.relevant_chunks),
            }
        )

    return {
        "summary": {
            "samples": len(samples),
            "recall@k": m.mean(r["recall_at_k"] for r in results),
            "hit_rate": m.mean(r["hit_rate"] for r in results),
            "mrr": m.mean(r["mrr"] for r in results),
            "build_s": build_s,
            "mean_search_ms": 1000 * search_s / len(results) if results else 0.0,
        },
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    token = report["modes"]["token"]["summary"]
    lemma = report["modes"]["lemma"]["summary"]
    comparison = report["comparison"]
    lines = [
        "# Сравнение морфологии BM25",
        "",
        f"Документы: `{report['documents']}`; набор: `{report['dataset']}`.",
        f"Чанков: {report['chunks']}; top_k: {report['top_k']}; только BM25, без векторного поиска и LLM.",
        "",
        "| Метрика | token | lemma | Разность |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, label in [
        ("recall@k", "recall@k"),
        ("hit_rate", "hit_rate"),
        ("mrr", "MRR"),
        ("build_s", "Построение, с"),
        ("mean_search_ms", "Поиск, мс"),
    ]:
        lines.append(f"| {label} | {token[key]:.6f} | {lemma[key]:.6f} | {lemma[key] - token[key]:+.6f} |")
    lines += [
        "",
        f"По MRR улучшено: {comparison['improved']}; ухудшено: {comparison['worsened']}; "
        f"без изменений: {comparison['unchanged']}.",
        "",
        "Абсолютные BM25 score между режимами не сравниваются: меняются частоты терминов.",
        "",
        "| id | Ранг token | Ранг lemma | Δ MRR | Вопрос |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    token_results = report["modes"]["token"]["results"]
    lemma_results = report["modes"]["lemma"]["results"]
    for before, after in zip(token_results, lemma_results, strict=True):
        question = before["question"].replace("|", "\\|")
        lines.append(
            f"| {before['id']} | {before['rank'] or '—'} | {after['rank'] or '—'} | "
            f"{after['mrr'] - before['mrr']:+.3f} | {question} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", help="Файл или каталог документов")
    parser.add_argument("dataset", help="JSONL с обязательным relevant_chunks")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k должен быть положительным")

    documents = load_documents([args.documents])
    chunks = split_documents(documents)
    samples = load_dataset(args.dataset)
    unlabeled = [sample.id for sample in samples if not sample.relevant_chunks]
    if not samples or unlabeled:
        parser.error(f"Набор пуст или не содержит relevant_chunks: {unlabeled}")

    modes = {mode: run_mode(chunks, samples, mode, args.top_k) for mode in ("token", "lemma")}
    before = modes["token"]["results"]
    after = modes["lemma"]["results"]
    deltas = [b["mrr"] - a["mrr"] for a, b in zip(before, after, strict=True)]
    report = {
        "created_at": time.time(),
        "documents": args.documents,
        "dataset": args.dataset,
        "chunks": len(chunks),
        "top_k": args.top_k,
        "modes": modes,
        "comparison": {
            "improved": sum(delta > 0 for delta in deltas),
            "worsened": sum(delta < 0 for delta in deltas),
            "unchanged": sum(delta == 0 for delta in deltas),
        },
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "morphology_bm25_comparison.json"
    md_path = output_dir / "morphology_bm25_comparison.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"token": modes["token"]["summary"], "lemma": modes["lemma"]["summary"]}, ensure_ascii=False, indent=2))
    print(f"JSON-отчёт: {json_path}")
    print(f"Markdown-отчёт: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
