from __future__ import annotations

from typing import Any

from app.models.schemas import KnowledgeDoc
from app.rag.grounding import annotate_grounding
from app.rag.reranker import rerank_documents


class HybridRetriever:
    """Small retrieval control layer: base search, rerank, and grounding metadata."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> list[KnowledgeDoc]:
        docs = self.store.search(
            query=query,
            top_k=max(top_k * 2, top_k),
            category=category,
            tags=tags,
        )
        return annotate_grounding(query, rerank_documents(query, docs))[:top_k]
