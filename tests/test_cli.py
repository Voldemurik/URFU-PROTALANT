from pathlib import Path

import pytest

from techdoc_assistant.cli import main


def test_offline_ingest_search_eval_flow(tmp_path: Path, sample_docs_dir: Path, sample_qa_path: Path, capsys):
    index_dir = str(tmp_path / "index")

    assert main(["ingest", str(sample_docs_dir), "--offline", "--index-dir", index_dir]) == 0
    out = capsys.readouterr().out
    assert "Проиндексировано фрагментов" in out
    assert (tmp_path / "index" / "chunks.jsonl").exists()

    assert main(["search", "перегрев шпинделя E12", "--offline", "--index-dir", index_dir, "-k", "2"]) == 0
    out = capsys.readouterr().out
    assert "[1]" in out and "Коды ошибок" in out

    assert main(["ask", "Что делать при ошибке E12?", "--offline", "--index-dir", index_dir]) == 0
    out = capsys.readouterr().out
    assert "Источники:" in out

    report_md = tmp_path / "report.md"
    report_json = tmp_path / "report.json"
    code = main([
        "eval", str(sample_qa_path), "--offline", "--index-dir", index_dir,
        "--report-md", str(report_md), "--report-json", str(report_json),
    ])
    assert code == 0
    assert report_md.exists() and report_json.exists()
    assert "retrieval/hit_rate" in capsys.readouterr().out


def test_search_without_index_exits_with_hint(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main(["search", "вопрос", "--offline", "--index-dir", str(tmp_path / "nope")])
    assert "techdoc ingest" in str(exc.value)


def test_init_config_creates_file(tmp_path: Path, capsys):
    path = tmp_path / "config.yaml"
    assert main(["init-config", str(path)]) == 0
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "ollama" in text and "llm" in text
    with pytest.raises(SystemExit):
        main(["init-config", str(path)])  # без --force повторно не перезаписываем


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "techdoc-assistant" in capsys.readouterr().out
