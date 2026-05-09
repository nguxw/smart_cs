from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


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


def create_embedding_provider(provider: str = "local", vector_size: int = 384) -> EmbeddingProvider:
    # External providers can be plugged in here without changing store/query callers.
    return DeterministicEmbeddingProvider(vector_size=vector_size)
