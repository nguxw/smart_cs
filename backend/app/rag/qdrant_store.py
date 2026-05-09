from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.models.schemas import KnowledgeDoc
from app.rag.embeddings import DeterministicEmbeddingProvider
from app.rag.grounding import annotate_grounding
from app.rag.knowledge_store import HybridKnowledgeStore, chunk_text
from app.rag.reranker import rerank_documents


def stable_embedding(text: str, vector_size: int = 384) -> list[float]:
    """Deterministic local embedding used when no external embedding service is configured."""

    return DeterministicEmbeddingProvider(vector_size=vector_size).embed(text)


class QdrantKnowledgeStore:
    """Qdrant-backed vector knowledge store with local deterministic embeddings."""

    backend_name = "qdrant"

    def __init__(
        self,
        url: str,
        collection_name: str,
        vector_size: int = 384,
    ) -> None:
        self.url = url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.client = QdrantClient(url=url, timeout=2, check_compatibility=False)
        self._ensure_collection()

    def ping(self) -> bool:
        self.client.get_collections()
        return True

    def _ensure_collection(self) -> None:
        exists = False
        try:
            exists = bool(self.client.collection_exists(self.collection_name))
        except Exception:
            try:
                self.client.get_collection(self.collection_name)
                exists = True
            except Exception:
                exists = False
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

    def clear(self) -> None:
        self.client.delete_collection(self.collection_name)
        self._ensure_collection()

    def add_document(
        self,
        title: str,
        content: str,
        source: str,
        category: str,
        tags: Iterable[str] | None = None,
    ) -> list[KnowledgeDoc]:
        created: list[KnowledgeDoc] = []
        points: list[models.PointStruct] = []
        for index, chunk in enumerate(chunk_text(content)):
            doc_id = f"{source}:{index}"
            doc = KnowledgeDoc(
                id=doc_id,
                title=title,
                content=chunk,
                source=source,
                category=category,
                tags=list(tags or []),
            )
            created.append(doc)
            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, doc_id)),
                    vector=stable_embedding(f"{title}\n{chunk}", self.vector_size),
                    payload=asdict(doc),
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return created

    def ingest_markdown_dir(self, directory: str | Path) -> int:
        path = Path(directory)
        count = 0
        for file_path in sorted(path.glob("*.md")):
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            title = lines[0].lstrip("# ").strip() if lines else file_path.stem
            category = file_path.stem.split("_")[0]
            count += len(
                self.add_document(
                    title=title,
                    content=content,
                    source=file_path.name,
                    category=category,
                    tags=[category, "seed"],
                )
            )
        return count

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> list[KnowledgeDoc]:
        query_vector = stable_embedding(query, self.vector_size)
        query_filter = _build_filter(category=category, tags=tags)
        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
            points = response.points
        except AttributeError:
            points = cast(Any, self.client).search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
        docs: list[KnowledgeDoc] = []
        for point in points:
            payload = point.payload or {}
            doc = KnowledgeDoc(
                id=str(payload.get("id", point.id)),
                title=str(payload.get("title", "")),
                content=str(payload.get("content", "")),
                source=str(payload.get("source", "")),
                category=str(payload.get("category", "")),
                tags=list(payload.get("tags", [])),
                score=round(float(point.score or 0.0), 4),
            )
            docs.append(doc)
        return annotate_grounding(query, rerank_documents(query, docs))[:top_k]

    def all_documents(self) -> list[KnowledgeDoc]:
        docs: list[KnowledgeDoc] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
            )
            for point in points:
                payload = point.payload or {}
                docs.append(KnowledgeDoc(**payload))
            if offset is None:
                break
        return docs


def create_qdrant_or_local_store(
    url: str,
    collection_name: str,
    seed_dir: Path,
    vector_size: int = 384,
) -> QdrantKnowledgeStore | HybridKnowledgeStore:
    try:
        store: QdrantKnowledgeStore | HybridKnowledgeStore
        store = QdrantKnowledgeStore(url, collection_name, vector_size)
        store.ping()
        store.ingest_markdown_dir(seed_dir)
        return store
    except Exception:
        store = HybridKnowledgeStore()
        if seed_dir.exists():
            store.ingest_markdown_dir(seed_dir)
        return store


def _build_filter(category: str | None, tags: list[str] | None) -> models.Filter | None:
    conditions: list[Any] = []
    if category:
        conditions.append(
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value=category),
            )
        )
    for tag in tags or []:
        conditions.append(
            models.FieldCondition(
                key="tags",
                match=models.MatchAny(any=[tag]),
            )
        )
    return models.Filter(must=cast(Any, conditions)) if conditions else None
