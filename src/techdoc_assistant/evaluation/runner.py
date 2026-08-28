"""Прогон оценочного набора через пайплайн и сводный отчёт."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from techdoc_assistant.evaluation import metrics as m
from techdoc_assistant.evaluation.dataset import EvalSample
from techdoc_assistant.evaluation.judge import JudgeVerdict, LLMJudge
from techdoc_assistant.rag import Answer, RagPipeline

log = logging.getLogger(__name__)


@dataclass
class SampleResult:
    sample_id: str
    question: str
    answer: str
    refused: bool
    retrieved_docs: list[str]
    cited_docs: list[str]
    recall_at_k: float
    hit_rate: float
    mrr: float
    token_f1: float
    must_include_coverage: float
    citation_precision: float
    citation_recall: float
    refusal_correct: bool
    latency_s: float
    tags: list[str] = field(default_factory=list)
    answerable: bool = True
    judge: dict[str, Any] | None = None


@dataclass
class EvalReport:
    results: list[SampleResult]
    config: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------ aggregate
    def aggregate(self) -> dict[str, float]:
        """Сводные метрики. Ключи без единого наблюдения (нет ловушек, все отказы) опускаются."""
        answerable = [r for r in self.results if r.answerable]
        answered = [r for r in answerable if not r.refused]
        traps = [r for r in self.results if not r.answerable]
        judged = [r for r in self.results if r.judge and r.judge.get("parsed")]

        summary: dict[str, float] = {"samples": float(len(self.results))}

        def put(key: str, values: list[float]) -> None:
            if values:
                summary[key] = m.mean(values)

        put("retrieval/recall@k", [r.recall_at_k for r in answerable])
        put("retrieval/hit_rate", [r.hit_rate for r in answerable])
        put("retrieval/mrr", [r.mrr for r in answerable])
        put("answer/token_f1", [r.token_f1 for r in answerable])
        put("answer/must_include", [r.must_include_coverage for r in answerable])
        put("citations/precision", [r.citation_precision for r in answered])
        put("citations/recall", [r.citation_recall for r in answered])
        put("citations/answered_with_citation", [1.0 if r.cited_docs else 0.0 for r in answered])
        put("hallucination/false_refusal_rate", [1.0 if r.refused else 0.0 for r in answerable])
        put("hallucination/trap_refusal_rate", [1.0 if r.refused else 0.0 for r in traps])
        put("latency/mean_s", [r.latency_s for r in self.results])
        if judged:
            summary["judge/faithfulness"] = m.mean(r.judge["faithfulness"] for r in judged)  # type: ignore[index]
            summary["judge/completeness"] = m.mean(r.judge["completeness"] for r in judged)  # type: ignore[index]
            summary["judge/hallucination_rate"] = 1.0 - summary["judge/faithfulness"]
        return summary

    # -------------------------------------------------------------- export
    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "config": self.config,
            "summary": self.aggregate(),
            "results": [asdict(r) for r in self.results],
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def render_markdown(self) -> str:
        summary = self.aggregate()
        lines = ["## Сводка", "", "| Метрика | Значение |", "|---|---|"]
        for key, value in summary.items():
            shown = f"{int(value)}" if key == "samples" else f"{value:.3f}"
            lines.append(f"| `{key}` | {shown} |")
        lines += ["", "## По вопросам", "", "| id | recall@k | F1 | факты | цит. P | отказ | ответ |", "|---|---|---|---|---|---|---|"]
        for r in self.results:
            answer = r.answer.replace("|", "\\|").replace("\n", " ")
            if len(answer) > 90:
                answer = answer[:87] + "…"
            refused = "да" if r.refused else "нет"
            if r.answerable:
                cells = f"{r.recall_at_k:.2f} | {r.token_f1:.2f} | {r.must_include_coverage:.2f} | {r.citation_precision:.2f}"
            else:  # для вопросов-ловушек важен только факт отказа
                cells = "— | — | — | —"
                refused += " ✔" if r.refusal_correct else " ✘ (ловушка)"
            lines.append(f"| {r.sample_id} | {cells} | {refused} | {answer} |")
        return "\n".join(lines) + "\n"


def evaluate(
    pipeline: RagPipeline,
    samples: list[EvalSample],
    *,
    judge: LLMJudge | None = None,
    progress: Callable[[int, int, SampleResult], None] | None = None,
) -> EvalReport:
    """Прогнать пайплайн по набору и посчитать метрики для каждого вопроса."""
    results: list[SampleResult] = []
    for number, sample in enumerate(samples, start=1):
        answer = pipeline.ask(sample.question)
        result = score_sample(sample, answer)
        if judge is not None:
            verdict = judge.judge(sample.question, answer.context_chunks, sample.reference_answer, answer.text)
            result.judge = _verdict_dict(verdict)
        results.append(result)
        if progress:
            progress(number, len(samples), result)
    return EvalReport(results=results, config=pipeline.config.to_dict())


def score_sample(sample: EvalSample, answer: Answer) -> SampleResult:
    retrieved = _unique(hit.chunk.doc_id for hit in answer.hits)
    cited = answer.cited_doc_ids
    refusal_correct = answer.refused if not sample.answerable else not answer.refused
    return SampleResult(
        sample_id=sample.id,
        question=sample.question,
        answer=answer.text,
        refused=answer.refused,
        retrieved_docs=retrieved,
        cited_docs=cited,
        recall_at_k=m.recall_at_k(retrieved, sample.relevant_docs),
        hit_rate=m.hit_rate(retrieved, sample.relevant_docs),
        mrr=m.mrr(retrieved, sample.relevant_docs),
        token_f1=m.token_f1(answer.text, sample.reference_answer),
        must_include_coverage=m.must_include_coverage(answer.text, sample.must_include),
        citation_precision=m.citation_precision(cited, sample.relevant_docs),
        citation_recall=m.citation_recall(cited, sample.relevant_docs),
        refusal_correct=refusal_correct,
        latency_s=answer.latency_s,
        tags=list(sample.tags),
        answerable=sample.answerable,
    )


def _verdict_dict(verdict: JudgeVerdict) -> dict[str, Any]:
    return {
        "faithfulness": verdict.faithfulness,
        "completeness": verdict.completeness,
        "unsupported_claims": verdict.unsupported_claims,
        "parsed": verdict.parsed,
    }


def _unique(items) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
