"""Проверить структуру JSONL-набора и связи вопросов с документами."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from techdoc_assistant.evaluation import load_dataset


def validate(dataset_path: Path, docs_root: Path, min_samples: int, min_traps: int) -> list[str]:
    """Вернуть список ошибок разметки, не изменяя проверяемые файлы."""
    errors: list[str] = []
    try:
        samples = load_dataset(dataset_path)
    except (OSError, ValueError) as exc:
        return [str(exc)]

    if len(samples) < min_samples:
        errors.append(f"Вопросов {len(samples)}, требуется не менее {min_samples}")
    traps = sum(not sample.answerable for sample in samples)
    if traps < min_traps:
        errors.append(f"Ловушек {traps}, требуется не менее {min_traps}")

    for value, count in Counter(sample.id for sample in samples).items():
        if count > 1:
            errors.append(f"Повторяющийся id {value!r}: {count} записей")
    for value, count in Counter(sample.question.strip().casefold() for sample in samples).items():
        if count > 1:
            errors.append(f"Повторяющийся вопрос {value!r}: {count} записей")

    for sample in samples:
        prefix = f"{sample.id}: "
        if not sample.id.strip():
            errors.append(prefix + "пустой id")
        if not sample.question.strip():
            errors.append(prefix + "пустой вопрос")
        if not sample.reference_answer.strip():
            errors.append(prefix + "пустой эталонный ответ")
        if not sample.tags:
            errors.append(prefix + "нет тегов")
        if sample.answerable and not sample.relevant_docs:
            errors.append(prefix + "для отвечаемого вопроса не указан relevant_docs")
        if not sample.answerable and sample.relevant_docs:
            errors.append(prefix + "у ловушки relevant_docs должен быть пустым")
        if not sample.answerable and sample.must_include:
            errors.append(prefix + "у ловушки must_include должен быть пустым")
        if sample.answerable and not sample.must_include:
            errors.append(prefix + "для отвечаемого вопроса нет обязательных фактов")
        if any(not fact.strip() for fact in sample.must_include):
            errors.append(prefix + "пустой элемент must_include")

        for doc_id in sample.relevant_docs:
            doc_path = Path(doc_id)
            if doc_path.is_absolute() or ".." in doc_path.parts:
                errors.append(prefix + f"небезопасный путь документа {doc_id!r}")
            elif not (docs_root / doc_path).is_file():
                errors.append(prefix + f"документ не найден: {docs_root / doc_path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--docs-root", type=Path, required=True)
    parser.add_argument("--min-samples", type=int, default=1)
    parser.add_argument("--min-traps", type=int, default=0)
    args = parser.parse_args()

    errors = validate(args.dataset, args.docs_root, args.min_samples, args.min_traps)
    if errors:
        for error in errors:
            print(f"ОШИБКА: {error}")
        return 1

    samples = load_dataset(args.dataset)
    traps = sum(not sample.answerable for sample in samples)
    documents = {doc for sample in samples for doc in sample.relevant_docs}
    print(
        f"OK: {len(samples)} вопросов, {traps} ловушек "
        f"({traps / len(samples):.1%}), документов: {len(documents)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
