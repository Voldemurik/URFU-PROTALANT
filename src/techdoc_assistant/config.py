"""Конфигурация пайплайна.

Все настройки собраны в датаклассы с разумными значениями по умолчанию,
поэтому система запускается без единого конфигурационного файла. При
необходимости параметры переопределяются YAML-файлом (см.
``config.example.yaml``) или аргументами командной строки.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class OllamaConfig:
    """Подключение к локальному серверу Ollama."""

    host: str = "http://localhost:11434"
    timeout: float = 600.0  # секунд; первая загрузка модели может быть долгой


@dataclass
class EmbeddingConfig:
    """Модель эмбеддингов (векторных представлений текста)."""

    model: str = "bge-m3"  # многоязычная, хорошо работает с русским
    batch_size: int = 16


@dataclass
class LLMConfig:
    """Генеративная модель."""

    model: str = "qwen3.5:9b"
    temperature: float = 0.1
    num_ctx: int = 8192  # размер контекстного окна в токенах
    think: bool = False  # для «думающих» моделей: отключаем цепочку рассуждений
    max_tokens: int = 1024


@dataclass
class ChunkingConfig:
    """Разбиение документов на фрагменты (чанки)."""

    chunk_size: int = 900  # символов
    chunk_overlap: int = 150  # символов перекрытия между соседними чанками
    min_chunk_size: int = 80  # слишком короткие хвосты приклеиваются к предыдущему чанку


@dataclass
class RetrievalConfig:
    """Параметры поиска."""

    top_k: int = 5  # сколько фрагментов попадёт в контекст модели
    candidates: int = 20  # сколько кандидатов берём из каждого поиска перед слиянием
    hybrid: bool = True  # объединять векторный и лексический (BM25) поиск
    rrf_k: int = 60  # константа Reciprocal Rank Fusion
    min_score: float = 0.0  # отсечка по RRF-скору (0 — без отсечки); шкала: максимум 2/(rrf_k+1) ≈ 0.033


@dataclass
class Config:
    """Корневая конфигурация."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    embeddings: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    index_dir: Path = Path("storage/index")

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """Загрузить конфигурацию из YAML; без пути — значения по умолчанию."""
        if path is None:
            return cls()
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Конфигурация {path} должна быть YAML-словарём")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Config:
        cfg = cls()
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(
                f"Неизвестные секции конфигурации: {sorted(unknown)}; допустимые: {sorted(known)}"
            )
        for f in fields(cls):
            if f.name not in raw:
                continue
            value = raw[f.name]
            current = getattr(cfg, f.name)
            if is_dataclass(current):
                if not isinstance(value, dict):
                    raise ValueError(
                        f"Секция «{f.name}» должна быть словарём параметров, а не {type(value).__name__}"
                    )
                setattr(cfg, f.name, _update_dataclass(current, value))
            elif f.name == "index_dir":
                cfg.index_dir = Path(value)
            else:
                setattr(cfg, f.name, value)
        return cfg

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["index_dir"] = str(self.index_dir)
        return data

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(
            yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def _update_dataclass(instance: Any, values: dict[str, Any]) -> Any:
    known = {f.name for f in fields(instance)}
    unknown = set(values) - known
    if unknown:
        raise ValueError(
            f"Неизвестные параметры в секции {type(instance).__name__}: {sorted(unknown)}"
        )
    for key, value in values.items():
        setattr(instance, key, value)
    return instance
