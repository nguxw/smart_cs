from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.services import create_knowledge_store
from app.rag.embeddings import create_embedding_provider
from app.rag.knowledge_store import create_seeded_knowledge_store
from app.rag.qdrant_store import QdrantKnowledgeStore


@dataclass(frozen=True)
class RagEvalCase:
    id: str
    query: str
    expected_sources: tuple[str, ...]


def load_cases(path: Path | None = None) -> list[RagEvalCase]:
    case_path = path or Path(__file__).resolve().parent / "cases" / "rag_retrieval.jsonl"
    cases: list[RagEvalCase] = []
    for line in case_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            RagEvalCase(
                id=str(payload["id"]),
                query=str(payload["query"]),
                expected_sources=tuple(payload["expected_sources"]),
            )
        )
    return cases


def build_store(backend: str) -> Any:
    if backend == "memory":
        return create_seeded_knowledge_store()
    if backend == "qdrant":
        seed_dir = Path(__file__).resolve().parents[2] / "data" / "kb"
        embedding_provider = create_embedding_provider(
            provider=settings.embedding_provider,
            vector_size=settings.qdrant_vector_size,
            model_name=settings.embedding_model,
        )
        store = QdrantKnowledgeStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            vector_size=settings.qdrant_vector_size,
            embedding_provider=embedding_provider,
        )
        store.ping()
        store.ingest_markdown_dir(seed_dir)
        return store
    return create_knowledge_store(settings)


def evaluate(backend: str = "memory", top_k: int = 3) -> dict[str, Any]:
    cases = load_cases()
    store = build_store(backend)
    rows: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []

    for case in cases:
        docs = store.search(case.query, top_k=max(top_k, 3))
        sources = [doc.source for doc in docs]
        expected = set(case.expected_sources)
        rank = next(
            (index + 1 for index, source in enumerate(sources) if source in expected),
            0,
        )
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        rows.append(
            {
                "id": case.id,
                "query": case.query,
                "expected_sources": list(case.expected_sources),
                "actual_sources": sources[:top_k],
                "recall_at_1": bool(sources[:1] and sources[0] in expected),
                "recall_at_3": any(source in expected for source in sources[:3]),
                "rank": rank,
            }
        )

    count = len(rows) or 1
    return {
        "backend": backend,
        "cases": len(rows),
        "recall@1": round(sum(row["recall_at_1"] for row in rows) / count, 4),
        "recall@3": round(sum(row["recall_at_3"] for row in rows) / count, 4),
        "mrr": round(sum(reciprocal_ranks) / count, 4),
        "citation_hit_rate": round(sum(row["recall_at_3"] for row in rows) / count, 4),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SmartCS RAG retrieval eval.")
    parser.add_argument("--backend", choices=("memory", "qdrant", "auto"), default="memory")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    result = evaluate(backend=args.backend, top_k=args.top_k)
    print("RAG Retrieval Eval")
    print(f"- backend: {result['backend']}")
    print(f"- cases: {result['cases']}")
    print(f"- recall@1: {result['recall@1']:.2%}")
    print(f"- recall@3: {result['recall@3']:.2%}")
    print(f"- mrr: {result['mrr']:.2%}")
    print(f"- citation hit rate: {result['citation_hit_rate']:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
