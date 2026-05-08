from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from app.models.schemas import KnowledgeDoc

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def chunk_text(text: str, chunk_size: int = 450, overlap: int = 80) -> list[str]:
    clean = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(clean) <= chunk_size:
        return [clean]
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunks.append(clean[start:end].strip())
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


class HybridKnowledgeStore:
    """Local hybrid lexical retrieval with a Qdrant-compatible public boundary."""

    def __init__(self) -> None:
        self._docs: dict[str, KnowledgeDoc] = {}

    def clear(self) -> None:
        self._docs.clear()

    def add_document(
        self,
        title: str,
        content: str,
        source: str,
        category: str,
        tags: Iterable[str] | None = None,
    ) -> list[KnowledgeDoc]:
        created: list[KnowledgeDoc] = []
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
            self._docs[doc_id] = doc
            created.append(doc)
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
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return []
        tag_set = set(tags or [])
        scored: list[KnowledgeDoc] = []
        for doc in self._docs.values():
            if category and doc.category != category:
                continue
            if tag_set and not tag_set.issubset(set(doc.tags)):
                continue
            doc_tokens = set(tokenize(f"{doc.title}\n{doc.content}\n{' '.join(doc.tags)}"))
            overlap = len(query_tokens & doc_tokens)
            char_hits = sum(1 for token in query_tokens if token in doc.content.lower())
            category_bonus = 1.5 if category and doc.category == category else 0.0
            score = overlap * 2.0 + char_hits * 0.7 + category_bonus
            if score > 0:
                copied = KnowledgeDoc(**asdict(doc))
                copied.score = round(score, 4)
                scored.append(copied)
        scored.sort(key=lambda doc: doc.score, reverse=True)
        return scored[:top_k]

    def all_documents(self) -> list[KnowledgeDoc]:
        return list(self._docs.values())


def create_seeded_knowledge_store() -> HybridKnowledgeStore:
    store = HybridKnowledgeStore()
    seed_dir = Path(__file__).resolve().parents[2] / "data" / "kb"
    if seed_dir.exists():
        store.ingest_markdown_dir(seed_dir)
    return store
