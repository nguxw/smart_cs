from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    vector_size: int

    def embed(self, text: str) -> list[float]:
        """Return one embedding vector for text."""


@dataclass
class DeterministicEmbeddingProvider:
    """Offline fallback embedding provider used for tests and no-key demos."""

    vector_size: int = 384

    def embed(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.vector_size:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for byte in digest:
                values.append((byte / 127.5) - 1.0)
                if len(values) == self.vector_size:
                    break
            counter += 1
        norm = sum(value * value for value in values) ** 0.5 or 1.0
        return [value / norm for value in values]


@dataclass
class SentenceTransformerEmbeddingProvider:
    """Local semantic embedding provider for realistic offline demos."""

    model_name: str
    vector_size: int = field(init=False)
    _model: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency boundary
            raise RuntimeError(
                "Install backend[local-embeddings] to use sentence-transformers embeddings."
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        dimension = self._model.get_sentence_embedding_dimension()
        if dimension is None:
            dimension = len(self._model.encode("dimension probe", normalize_embeddings=True))
        self.vector_size = int(dimension)

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector.tolist()]


def create_embedding_provider(
    provider: str = "local",
    vector_size: int = 384,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> EmbeddingProvider:
    normalized = provider.strip().lower()
    if normalized in {"sentence-transformers", "sentence_transformers", "local_semantic"}:
        return SentenceTransformerEmbeddingProvider(model_name=model_name)
    return DeterministicEmbeddingProvider(vector_size=vector_size)
