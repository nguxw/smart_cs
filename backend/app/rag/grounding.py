from __future__ import annotations

import re
from dataclasses import asdict

from app.models.schemas import KnowledgeDoc

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def grounding_score(answer: str, docs: list[KnowledgeDoc]) -> float:
    answer_tokens = {token.lower() for token in TOKEN_RE.findall(answer)}
    evidence_tokens = {
        token.lower()
        for doc in docs
        for token in TOKEN_RE.findall(f"{doc.title}\n{doc.content}")
    }
    if not answer_tokens:
        return 0.0
    return round(len(answer_tokens & evidence_tokens) / len(answer_tokens), 4)


def annotate_grounding(query: str, docs: list[KnowledgeDoc]) -> list[KnowledgeDoc]:
    query_tokens = {token.lower() for token in TOKEN_RE.findall(query)}
    annotated: list[KnowledgeDoc] = []
    for doc in docs:
        copied = KnowledgeDoc(**asdict(doc))
        doc_tokens = {
            token.lower()
            for token in TOKEN_RE.findall(f"{doc.title}\n{doc.content}\n{' '.join(doc.tags)}")
        }
        copied.grounding_score = round(
            len(query_tokens & doc_tokens) / max(1, len(query_tokens)),
            4,
        )
        annotated.append(copied)
    return annotated
