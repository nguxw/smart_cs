from __future__ import annotations

import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import Settings
from app.data.postgres_repository import PostgresRepository
from app.data.repository import DemoRepository
from app.rag.embeddings import create_embedding_provider
from app.rag.knowledge_store import HybridKnowledgeStore
from app.rag.qdrant_store import QdrantKnowledgeStore
from app.runtime.redis_runtime import NullRuntimeService, RedisRuntimeService


def create_repository(settings: Settings) -> Any:
    backend = settings.data_backend.lower()
    if backend == "memory":
        return DemoRepository()
    if backend in {"postgres", "postgresql", "auto"}:
        if backend == "auto" and not _tcp_available(settings.database_url, default_port=5432):
            return DemoRepository()
        try:
            repository = PostgresRepository(settings.database_url)
            repository.ping()
            return repository
        except Exception:
            if backend != "auto":
                raise
    return DemoRepository()


def create_runtime_service(settings: Settings) -> RedisRuntimeService | NullRuntimeService:
    backend = settings.redis_backend.lower()
    if backend == "memory":
        return NullRuntimeService()
    if backend in {"redis", "auto"}:
        if backend == "auto" and not _tcp_available(settings.redis_url, default_port=6379):
            return NullRuntimeService()
        try:
            return RedisRuntimeService(settings.redis_url, settings.rate_limit_per_minute)
        except Exception:
            if backend != "auto":
                raise
    return NullRuntimeService()


def create_knowledge_store(settings: Settings) -> QdrantKnowledgeStore | HybridKnowledgeStore:
    seed_dir = Path(__file__).resolve().parents[2] / "data" / "kb"
    backend = settings.kb_backend.lower()
    if backend == "memory":
        local_store = HybridKnowledgeStore()
        if seed_dir.exists():
            local_store.ingest_markdown_dir(seed_dir)
        return local_store
    if backend in {"qdrant", "auto"}:
        if backend == "auto" and not _tcp_available(settings.qdrant_url, default_port=6333):
            store = HybridKnowledgeStore()
            if seed_dir.exists():
                store.ingest_markdown_dir(seed_dir)
            return store
        try:
            embedding_provider = create_embedding_provider(
                provider=settings.embedding_provider,
                vector_size=settings.qdrant_vector_size,
                model_name=settings.embedding_model,
            )
            qdrant_store = QdrantKnowledgeStore(
                url=settings.qdrant_url,
                collection_name=settings.qdrant_collection,
                vector_size=settings.qdrant_vector_size,
                embedding_provider=embedding_provider,
            )
            qdrant_store.ping()
            qdrant_store.ingest_markdown_dir(seed_dir)
            return qdrant_store
        except Exception:
            if backend != "auto":
                raise
    store = HybridKnowledgeStore()
    if seed_dir.exists():
        store.ingest_markdown_dir(seed_dir)
    return store


def _tcp_available(url: str, default_port: int, timeout: float = 0.25) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
