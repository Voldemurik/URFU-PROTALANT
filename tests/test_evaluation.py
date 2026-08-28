import json

import pytest

from techdoc_assistant.evaluation import EvalSample, LLMJudge, evaluate, load_dataset
from techdoc_assistant.evaluation import metrics as m
from techdoc_assistant.evaluation.judge import parse_verdict
from techdoc_assistant.llm import FakeLLM


# ------------------------------------------------------------------ metrics
def test_retrieval_metrics():
    assert m.recall_at_k(["a", "b"], ["a", "c"]) == pytest.approx(0.5)
    assert m.recall_at_k([], []) == 1.0
    assert m.hit_rate(["x", "a"], ["a"]) == 1.0
    assert m.hit_rate(["x"], ["a"]) == 0.0
    assert m.mrr(["x", "a"], ["a"]) == pytest.approx(0.5)
    assert m.mrr(["x"], ["a"]) == 0.0


def test_token_f1_ignores_stopwords_and_case():
    assert m.token_f1("Код ошибки E12", "код ошибки e12") == pytest.approx(1.0)
    assert m.token_f1("совсем другое", "код ошибки E12") == 0.0
    assert 0 < m.token_f1("код E12 и перегрев", "код ошибки E12") < 1


def test_must_include_coverage_is_loose_on_numbers_and_case():
    assert m.must_include_coverage("Давление 0.6 МПа", ["0,6 мпа"]) == 1.0
    assert m.must_include_coverage("нет данных", ["E12", "20 минут"]) == 0.0
    assert m.must_include_coverage("остыть 20 минут", ["E12", "20 минут"]) == pytest.approx(0.5)
    assert m.must_include_coverage("что угодно", []) == 1.0


def test_citation_metrics():
    assert m.citation_precision(["a", "b"], ["a"]) == pytest.approx(0.5)
    assert m.citation_precision([], ["a"]) == 0.0
    assert m.citation_recall(["a"], ["a", "b"]) == pytest.approx(0.5)
    assert m.citation_recall([], []) == 1.0


# ------------------------------------------------------------------ dataset
def test_load_sample_dataset(sample_qa_path):
    samples = load_dataset(sample_qa_path)
    assert len(samples) == 13
    assert sum(1 for s in samples if not s.answerable) == 2
    assert all(s.relevant_docs for s in samples if s.answerable)


def test_dataset_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"question": "ok"}\n{not json}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_dataset(path)


# -------------------------------------------------------------------- judge
def test_parse_verdict_handles_noise_and_garbage():
    verdict = parse_verdict('Вот оценка: {"faithfulness": 0.75, "completeness": 1.4, "unsupported_claims": ["x"]} спасибо')
    assert verdict.parsed
    assert verdict.faithfulness == pytest.approx(0.75)
    assert verdict.completeness == 1.0  # обрезано до [0, 1]
    assert verdict.unsupported_claims == ["x"]
    assert verdict.hallucination == pytest.approx(0.25)

    broken = parse_verdict("модель не вернула JSON")
    assert not broken.parsed and broken.faithfulness == 0.0


def test_llm_judge_uses_json_mode():
    llm = FakeLLM(json.dumps({"faithfulness": 1, "completeness": 0.5, "unsupported_claims": []}))
    verdict = LLMJudge(llm).judge("вопрос", [], "эталон", "ответ")
    assert verdict.faithfulness == 1.0 and verdict.completeness == 0.5


# ------------------------------------------------------------------- runner
def test_evaluate_extractive_baseline_on_sample_dataset(extractive_pipeline, sample_qa_path):
    samples = load_dataset(sample_qa_path)
    report = evaluate(extractive_pipeline, samples)
    summary = report.aggregate()
    assert summary["samples"] == 13
    # Поиск по лексически близким вопросам должен находить нужные документы.
    assert summary["retrieval/hit_rate"] >= 0.8
    assert summary["retrieval/recall@k"] >= 0.7
    assert 0.0 <= summary["answer/must_include"] <= 1.0
    assert "judge/faithfulness" not in summary

    markdown = report.render_markdown()
    assert "## Сводка" in markdown and "q01" in markdown
    payload = report.to_dict()
    assert len(payload["results"]) == 13
    assert payload["config"]["retrieval"]["top_k"] == 5


def test_evaluate_with_judge_and_progress(extractive_pipeline):
    samples = [
        EvalSample(id="a", question="код ошибки E12 перегрев шпинделя", reference_answer="E12", relevant_docs=["fs400_rukovodstvo_po_ekspluatacii.md"], must_include=["E12"]),
        EvalSample(id="trap", question="пароль администратора", answerable=False),
    ]
    judge = LLMJudge(FakeLLM('{"faithfulness": 0.5, "completeness": 0.5, "unsupported_claims": []}'))
    seen = []
    report = evaluate(extractive_pipeline, samples, judge=judge, progress=lambda i, n, r: seen.append((i, n)))
    assert seen == [(1, 2), (2, 2)]
    summary = report.aggregate()
    assert summary["judge/faithfulness"] == pytest.approx(0.5)
    assert summary["judge/hallucination_rate"] == pytest.approx(0.5)
    assert report.results[0].must_include_coverage == 1.0


def test_report_save_json(extractive_pipeline, tmp_path):
    report = evaluate(extractive_pipeline, [EvalSample(id="x", question="датчик схода ленты", relevant_docs=["kl12_konveyer_poisk_neispravnostey.md"])])
    path = tmp_path / "report.json"
    report.save_json(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["retrieval/hit_rate"] == 1.0
