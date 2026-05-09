from __future__ import annotations

import re
from dataclasses import asdict

from app.models.schemas import KnowledgeDoc

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def rerank_documents(query: str, docs: list[KnowledgeDoc]) -> list[KnowledgeDoc]:
    query_tokens = set(_tokenize(query))
    ranked: list[KnowledgeDoc] = []
    for doc in docs:
        copied = KnowledgeDoc(**asdict(doc))
        blob = f"{doc.title}\n{doc.content}\n{' '.join(doc.tags)}".lower()
        exact_hits = sum(1 for token in query_tokens if token and token in blob)
        category_bonus = 0.4 if doc.category in query.lower() else 0.0
        copied.score = round(float(doc.score) + exact_hits * 0.25 + category_bonus, 4)
        ranked.append(copied)
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked
