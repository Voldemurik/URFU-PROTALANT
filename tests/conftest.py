from pathlib import Path

import pytest

from techdoc_assistant.baselines import ExtractiveLLM
from techdoc_assistant.config import Config
from techdoc_assistant.embeddings import HashingEmbedder
from techdoc_assistant.llm import FakeLLM
from techdoc_assistant.loaders import load_documents
from techdoc_assistant.rag import RagPipeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DOCS = ROOT / "data" / "sample_docs"
SAMPLE_QA = ROOT / "data" / "eval" / "sample_qa.jsonl"


@pytest.fixture(scope="session")
def sample_docs_dir() -> Path:
    return SAMPLE_DOCS


@pytest.fixture(scope="session")
def sample_qa_path() -> Path:
    return SAMPLE_QA


@pytest.fixture(scope="session")
def sample_documents():
    docs = load_documents([SAMPLE_DOCS])
    assert len(docs) == 3
    return docs


@pytest.fixture
def offline_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.index_dir = tmp_path / "index"
    return cfg


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM("Перегреву шпинделя соответствует код E12 [1]. Дайте шпинделю остыть 20 минут [1].")


@pytest.fixture
def offline_pipeline(offline_config: Config, sample_documents, fake_llm: FakeLLM) -> RagPipeline:
    pipeline = RagPipeline(offline_config, embedder=HashingEmbedder(), llm=fake_llm)
    pipeline.ingest_documents(sample_documents)
    return pipeline


@pytest.fixture
def extractive_pipeline(offline_config: Config, sample_documents) -> RagPipeline:
    pipeline = RagPipeline(offline_config, embedder=HashingEmbedder(), llm=ExtractiveLLM())
    pipeline.ingest_documents(sample_documents)
    return pipeline
