"""Диагностика извлечения текста из PDF текущим загрузчиком."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from techdoc_assistant.loaders import load_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--name", default="audit")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/pdf_audit"))
    args = parser.parse_args()

    document = load_file(args.pdf)
    if document is None:
        raise SystemExit(f"Не удалось загрузить {args.pdf}")

    text = document.text
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Строки, повторяющиеся в документе, — кандидаты в колонтитулы.
    repeated = [
        {"count": count, "line": line}
        for line, count in Counter(lines).most_common(30)
        if count > 1
    ]

    suspicious = [
        line
        for line in lines
        if re.search(r"Ð.|Ñ.|Ã.|â€|�", line)
    ]

    report = {
        "file": str(args.pdf),
        "title": document.title,
        "characters": len(text),
        "lines": len(lines),
        "replacement_characters": text.count("�"),
        "suspicious_encoding_lines": len(suspicious),
        "suspicious_encoding_examples": suspicious[:20],
        "markdown_table_rows": sum(
            line.startswith("|") and line.endswith("|") for line in lines
        ),
        "repeated_lines": repeated,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.name}.json"
    text_path = args.output_dir / f"{args.name}.txt"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    text_path.write_text(text, encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nJSON: {json_path}")
    print(f"Текст: {text_path}")

if __name__ == "__main__":
    main()
