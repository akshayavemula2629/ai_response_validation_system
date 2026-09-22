"""
Data cleaning and standardization for benchmark QA datasets (TruthfulQA and SQuAD).
"""
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class KBRecord:
    """Standardized knowledge base item."""
    document_id: str
    dataset: str
    question: str
    answer: str
    context: str
    source: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clean_text(text: Optional[str]) -> str:
    """Cleans whitespace, strips control characters, and standardizes punctuation."""
    if not text:
        return ""
    # Replace carriage returns and excessive whitespace
    text = re.sub(r'\r\n|\r', '\n', str(text))
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def standardize_squad_record(record: Dict[str, Any], index: int) -> KBRecord:
    """Standardizes a raw SQuAD dataset record into a KBRecord."""
    doc_id = f"squad_{record.get('id', str(index))}"
    question = clean_text(record.get("question", ""))
    context = clean_text(record.get("context", ""))
    title = clean_text(record.get("title", "SQuAD Article"))

    # SQuAD answers are stored as dict {"text": [...], "answer_start": [...]}
    answers_dict = record.get("answers", {})
    answers_list = answers_dict.get("text", []) if isinstance(answers_dict, dict) else []
    answer = clean_text(answers_list[0]) if answers_list else ""

    return KBRecord(
        document_id=doc_id,
        dataset="SQuAD",
        question=question,
        answer=answer,
        context=context if context else answer,
        source=f"SQuAD v1.1 - {title}",
        metadata={"title": title, "answers": answers_list}
    )


def standardize_truthfulqa_record(record: Dict[str, Any], index: int) -> KBRecord:
    """Standardizes a raw TruthfulQA dataset record into a KBRecord."""
    doc_id = f"truthfulqa_{index}"
    question = clean_text(record.get("Question", record.get("question", "")))
    best_answer = clean_text(record.get("Best Answer", record.get("best_answer", "")))
    category = clean_text(record.get("Category", record.get("category", "General")))

    # Fallback if 'Best Answer' is not present
    if not best_answer:
        correct_answers = record.get("Correct Answers", record.get("correct_answers", ""))
        if isinstance(correct_answers, list) and correct_answers:
            best_answer = clean_text(correct_answers[0])
        elif isinstance(correct_answers, str):
            best_answer = clean_text(correct_answers.split(";")[0])

    source_url = clean_text(record.get("Source", record.get("source", "TruthfulQA Benchmark")))

    return KBRecord(
        document_id=doc_id,
        dataset="TruthfulQA",
        question=question,
        answer=best_answer,
        context=f"Question: {question} Reference Answer: {best_answer}",
        source=f"TruthfulQA - {category}",
        metadata={"category": category, "source_url": source_url}
    )
