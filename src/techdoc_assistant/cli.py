"""Консольная утилита ``techdoc``.

Команды::

    techdoc doctor                       # проверить окружение (Ollama, модели, индекс)
    techdoc ingest data/sample_docs      # проиндексировать документы
    techdoc search "перегрев шпинделя"   # найти фрагменты без генерации
    techdoc ask "Что делать при E12?"    # ответ со ссылками на источники
    techdoc chat                         # интерактивный диалог
    techdoc eval data/eval/sample_qa.jsonl --report-md report.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

from techdoc_assistant import __version__
from techdoc_assistant.baselines import ExtractiveLLM
from techdoc_assistant.config import Config
from techdoc_assistant.embeddings import HashingEmbedder
from techdoc_assistant.evaluation import LLMJudge, evaluate, load_dataset
from techdoc_assistant.llm import OllamaLLM
from techdoc_assistant.ollama_client import OllamaClient, OllamaError
from techdoc_assistant.rag import IndexMismatchError, RagPipeline

log = logging.getLogger("techdoc")


# ------------------------------------------------------------------ helpers
def _build_pipeline(args: argparse.Namespace, *, need_llm: bool = True) -> RagPipeline:
    config = Config.load(args.config)
    if getattr(args, "index_dir", None):
        config.index_dir = Path(args.index_dir)
    offline = getattr(args, "offline", False)
    embedder = HashingEmbedder() if offline else None
    llm = ExtractiveLLM() if (offline or getattr(args, "answerer", "") == "extractive") else None
    if offline and need_llm:
        log.warning("Офлайн-режим: хэш-эмбеддинги и экстрактивный ответ без LLM (только для демонстрации)")
    return RagPipeline(config, embedder=embedder, llm=llm)


def _load_or_die(pipeline: RagPipeline) -> None:
    try:
        count = pipeline.load_index()
    except (FileNotFoundError, IndexMismatchError) as exc:
        sys.exit(f"Ошибка: {exc}")
    log.info("Загружен индекс: %d фрагментов (%s)", count, pipeline.store.backend)


# ----------------------------------------------------------------- commands
def cmd_doctor(args: argparse.Namespace) -> int:
    config = Config.load(args.config)
    ok = True
    print(f"techdoc-assistant {__version__}")
    print(f"Python {sys.version.split()[0]}")

    try:
        import faiss  # type: ignore[import-not-found]  # noqa: F401

        print("faiss: установлен (быстрый векторный поиск)")
    except ImportError:
        print("faiss: не установлен — используется NumPy (это нормально для небольших корпусов)")

    client = OllamaClient(config.ollama)
    if not client.is_available():
        print(f"Ollama: НЕДОСТУПНА по адресу {config.ollama.host}. Запустите `ollama serve`.")
        ok = False
    else:
        print(f"Ollama: доступна, версия {client.version()}")
        try:
            models = set(client.list_models())
        except OllamaError as exc:
            print(f"Ollama: не удалось получить список моделей — {exc}")
            models = set()
            ok = False
        for role, name in (("эмбеддинги", config.embeddings.model), ("LLM", config.llm.model)):
            wanted = name if ":" in name else f"{name}:latest"
            if wanted in models:
                print(f"  модель {role}: {name} — есть")
            else:
                print(f"  модель {role}: {name} — НЕ НАЙДЕНА, выполните `ollama pull {name}`")
                ok = False

    index_dir = Path(config.index_dir)
    if (index_dir / "chunks.jsonl").exists():
        print(f"Индекс: найден в {index_dir}")
    else:
        print(f"Индекс: отсутствует ({index_dir}); выполните `techdoc ingest <документы>`")
    print("Итог:", "всё готово" if ok else "есть проблемы (см. выше)")
    return 0 if ok else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    pipeline = _build_pipeline(args, need_llm=False)
    try:
        count = pipeline.ingest_paths(args.paths)
    except OllamaError as exc:
        sys.exit(f"Ошибка: {exc}")
    if count == 0:
        sys.exit("Не найдено ни одного документа для индексации")
    directory = pipeline.save_index()
    print(f"Проиндексировано фрагментов: {count}. Индекс сохранён в {directory}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    pipeline = _build_pipeline(args, need_llm=False)
    _load_or_die(pipeline)
    hits = pipeline.retrieve(args.query, args.top_k)
    if not hits:
        print("Ничего не найдено")
        return 1
    for number, hit in enumerate(hits, start=1):
        ranks = f"dense={hit.dense_rank or '-'} bm25={hit.lexical_rank or '-'}"
        print(f"[{number}] {hit.chunk.label()}  (score={hit.score:.4f}, {ranks})")
        print("    " + hit.chunk.text[:300].replace("\n", " ") + ("…" if len(hit.chunk.text) > 300 else ""))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    if not args.question.strip():
        sys.exit("Вопрос пустой")
    pipeline = _build_pipeline(args)
    _load_or_die(pipeline)
    try:
        answer = pipeline.ask(args.question, args.top_k)
    except OllamaError as exc:
        sys.exit(f"Ошибка: {exc}")
    if args.show_context:
        print("=== Контекст ===")
        for number, chunk in enumerate(answer.context_chunks, start=1):
            print(f"[{number}] {chunk.label()}\n{chunk.text}\n")
        print("=== Ответ ===")
    print(answer.render())
    print(f"\n(время: {answer.latency_s:.1f} с)")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    pipeline = _build_pipeline(args)
    _load_or_die(pipeline)
    print("Задавайте вопросы по документации. Пустая строка или Ctrl+C — выход.")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            break
        try:
            print(pipeline.ask(question, args.top_k).render())
        except OllamaError as exc:
            print(f"Ошибка: {exc}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    pipeline = _build_pipeline(args)
    _load_or_die(pipeline)
    samples = load_dataset(args.dataset)
    if not samples:
        sys.exit("Оценочный набор пуст")
    for path in (args.report_json, args.report_md):
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    judge = None
    if args.judge:
        if args.offline:
            log.warning("LLM-судья недоступен в офлайн-режиме — пропускаю")
        else:
            # Судья — всегда LLM через Ollama, независимо от того, кто отвечает
            # (в том числе при --answerer extractive); модель можно переопределить.
            judge_cfg = pipeline.config.llm
            if args.judge_model:
                judge_cfg = replace(judge_cfg, model=args.judge_model)
            judge = LLMJudge(OllamaLLM(OllamaClient(pipeline.config.ollama), judge_cfg))

    def progress(done: int, total: int, result) -> None:
        status = "отказ" if result.refused else f"F1={result.token_f1:.2f}"
        print(f"[{done}/{total}] {result.sample_id}: recall@k={result.recall_at_k:.2f}, {status}")

    try:
        report = evaluate(pipeline, samples, judge=judge, progress=progress)
    except OllamaError as exc:
        sys.exit(f"Ошибка: {exc}")

    print()
    for key, value in report.aggregate().items():
        shown = f"{int(value):8d}" if key == "samples" else f"{value:8.3f}"
        print(f"{key:40s} {shown}")
    if args.report_json:
        report.save_json(args.report_json)
        print(f"\nJSON-отчёт: {args.report_json}")
    if args.report_md:
        Path(args.report_md).write_text(report.render_markdown(), encoding="utf-8")
        print(f"Markdown-отчёт: {args.report_md}")
    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        sys.exit(f"{path} уже существует (используйте --force для перезаписи)")
    Config().dump(path)
    print(f"Конфигурация по умолчанию записана в {path}")
    return 0


# ------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="techdoc",
        description="Локальный LLM-ассистент по технической документации (RAG + оценка качества).",
    )
    parser.add_argument("--version", action="version", version=f"techdoc-assistant {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="подробный лог")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, *, llm: bool = True) -> None:
        p.add_argument("-c", "--config", default=None, help="путь к YAML-конфигурации")
        p.add_argument("--index-dir", default=None, help="каталог индекса (по умолчанию storage/index)")
        p.add_argument(
            "--offline",
            action="store_true",
            help="без Ollama: хэш-эмбеддинги" + (" и экстрактивный ответ" if llm else ""),
        )

    p = sub.add_parser("doctor", help="проверить окружение")
    p.add_argument("-c", "--config", default=None)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("ingest", help="проиндексировать документы (существующий индекс заменяется)")
    p.add_argument("paths", nargs="+", help="файлы или каталоги с документацией")
    common(p, llm=False)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("search", help="поиск фрагментов без генерации ответа")
    p.add_argument("query")
    p.add_argument("-k", "--top-k", type=int, default=None)
    common(p, llm=False)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("ask", help="задать вопрос")
    p.add_argument("question")
    p.add_argument("-k", "--top-k", type=int, default=None)
    p.add_argument("--show-context", action="store_true", help="показать фрагменты, переданные модели")
    common(p)
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("chat", help="интерактивный режим")
    p.add_argument("-k", "--top-k", type=int, default=None)
    common(p)
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("eval", help="оценить качество на наборе вопросов")
    p.add_argument("dataset", help="JSONL-файл с вопросами")
    p.add_argument("--judge", action="store_true", help="дополнительно оценить ответы LLM-судьёй")
    p.add_argument("--judge-model", default=None, help="модель судьи (по умолчанию — llm.model из конфигурации)")
    p.add_argument("--answerer", choices=["ollama", "extractive"], default="ollama", help="кто отвечает")
    p.add_argument("--report-json", default=None)
    p.add_argument("--report-md", default=None)
    common(p)
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("init-config", help="создать файл конфигурации со значениями по умолчанию")
    p.add_argument("path", nargs="?", default="config.yaml")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows: при перенаправлении вывода в файл кодировка по умолчанию — cp1251,
    # в которой нет «→», «−» и части символов из документации. Не падаем на этом.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace", **({} if stream.isatty() else {"encoding": "utf-8"}))
            except (ValueError, OSError):  # pragma: no cover - закрытый/нестандартный поток
                pass
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
